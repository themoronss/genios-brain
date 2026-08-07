"""Layer 5.2 · the Delivery Gate — the one place a message is admitted, held, or stopped.

``policy.py`` answers *may this travel at all?*  ``timing.py`` answers *is this the moment?*
Neither knows the other exists, and neither can read a database.  This module is what makes
them a system: it resolves their inputs from live tenant state, folds their verdicts, and hands
``outbox.py`` a single decision with a reason code attached.

**Why the gate runs at drain, not at enqueue.**  Enqueue happens inside the 6-hourly sweep; a
row can then sit queued for hours.  Evaluating quiet hours against the enqueue clock would ask
"is 14:00 a humane moment?" about a message that lands at 03:00, which is the bug this layer
exists to fix.  The codebase already settled this question once — authority is re-validated
immediately before the send, never trusted from queue time — and admission obeys the same law
for the same reason.  Enqueue's job is to *materialise* the delivery object onto the row; the
gate's job is to judge it against the world as it is at the instant of sending.

**Why the gate runs before authority re-validation.**  Both can stop a delivery, and the gate is
local, cheap and takes no locks, while the authority check holds `for share` locks on the graph
across an outbound HTTP call.  Holding those to discover the recipient is asleep would be paying
the expensive question to answer the cheap one.  A message deferred past its card's expiry is not
lost work either — the authority check runs when the deferral opens and cancels it there, so
staleness stays owned by the one predicate that already owns it.

**The merge is pure; only the reads are not.**  ``build_context`` takes plain values and returns
the two frozen inputs the units need.  ``PgDeliveryContext`` is the only thing here that touches
a connection.  That split is what lets the whole admission path be proven in a suite with no
service containers, and it is the same shape as ``SeatDirectory``/``PgSeatDirectory`` elsewhere
in this layer.

**Bad configuration degrades, it does not detonate.**  A tenant who types `Amercia/New_York`
into a timezone field must not stop every *other* tenant's messages draining.  Every resolved
value is validated here, an unusable one falls back to the protective default, and the reason
travels in ``DeliveryContext.config_error`` into the audit row — so the setting is visibly wrong
rather than silently ignored.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.delivery import (
    BAND_ORDER,
    INTRUSIVE_CHANNEL_CLASSES,
    DeliveryCandidate,
    DeliveryDecision,
    DeliveryVerdict,
)
from genios_engine.contracts.execution import ChannelClass
from genios_engine.deliver.policy import DeliveryPolicy, describe_policy, evaluate_policy
from genios_engine.deliver.timing import (
    AttentionProfile,
    AttentionState,
    describe_profile,
    evaluate_timing,
)
from genios_engine.executive.communication import CHAT_CHANNELS

GATE_VERSION = "gate.v1"
UNIT = "gate"

#: The "applies to everyone / every channel" key in ``delivery_preferences``.  A sentinel rather
#: than NULL because NULLs never compare equal inside a primary key, which would let two org-wide
#: default rows coexist and make resolution depend on physical row order.
WILDCARD = "*"

#: The rolling window the burst limiter measures over.  Mirrors ``timing._BURST_WINDOW``; stated
#: here because this module is what *counts* the interruptions the unit then judges.
BURST_WINDOW = timedelta(hours=1)

#: The floor a deferral is clamped to.  A ``not_before`` that has already passed would re-drain
#: on the very next tick, spinning the sweep against a constraint it cannot satisfy.
_MIN_DEFER = timedelta(minutes=1)

#: Channel classes that count toward the burst limit — the same set the candidate's ``intrusive``
#: property is defined by, expressed as strings for the SQL predicate.
_INTRUSIVE_VALUES: tuple[str, ...] = tuple(sorted(c.value for c in INTRUSIVE_CHANNEL_CLASSES))

#: Preference specificity, most specific first.  A person's own setting beats an org-wide rule
#: about a channel: the seat is a statement about a human, the channel is a statement about a
#: pipe, and when they disagree the human wins.
_SPECIFICITY: tuple[tuple[bool, bool], ...] = (
    (True, True),      # (seat, channel)  — this person, this channel
    (True, False),     # (seat, '*')      — this person, everywhere
    (False, True),     # ('*', channel)   — everyone, this channel
    (False, False),    # ('*', '*')       — the tenant default
)


@dataclass(frozen=True, slots=True)
class DeliveryContext:
    """Everything the pure units need, resolved for one (org, recipient, channel) triple."""

    policy: DeliveryPolicy
    profile: AttentionProfile
    state: AttentionState
    config_error: str | None = None      # a setting that could not be used, and why

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"policy": describe_policy(self.policy),
                "profile": describe_profile(self.profile),
                "busy_until": (self.state.busy_until.isoformat()
                               if self.state.busy_until else None),
                "current_activity": self.state.current_activity,
                "current_surface": self.state.current_surface,
                "interrupts_last_hour": self.state.interrupts_last_hour,
                "config_error": self.config_error}


# ── the delivery object ───────────────────────────────────────────────────────────────
def channel_class_for(channel: str) -> ChannelClass:
    """The physics of a concrete adapter — does arriving here cost unrequested attention?

    Reads Layer 5's ``CHAT_CHANNELS`` rather than keeping a list, so registering a second chat
    adapter makes it interruptive in both layers at once.  A channel this does not recognise is
    treated as an in-app surface: an unknown adapter is far more likely to be a dashboard than a
    pager, and guessing "pager" would gate a surface nobody was going to be woken by.
    """
    name = str(channel)
    if name in CHAT_CHANNELS:
        return ChannelClass.CHAT
    if name == "email":
        return ChannelClass.EMAIL
    if name == "digest":
        return ChannelClass.DIGEST
    if name == "agent":
        return ChannelClass.AGENT
    return ChannelClass.IN_APP


def candidate_from_row(row: Mapping[str, Any]) -> DeliveryCandidate:
    """An outbox row → the delivery the gate judges.  Coerces; never raises.

    The columns were written by this codebase and carry sane defaults, so the realistic failure
    is a value from a future adapter or a hand-edited row.  Every fallback here is the *cautious*
    reading rather than the permissive one — an unrecognised channel class becomes CHAT, so an
    unknown surface is assumed to be able to wake somebody and is gated accordingly, and an
    unreadable band becomes ``standard``, which cannot break glass.  Fail-safe, not fail-open:
    a raise would take the whole drain down with it, and a shrug would page somebody at 03:00.
    """
    raw_class = str(row.get("channel_class") or "").strip().lower()
    try:
        channel_class = ChannelClass(raw_class)
    except ValueError:
        channel_class = ChannelClass.CHAT

    band = str(row.get("band") or "").strip().lower()
    if band not in BAND_ORDER:
        band = BAND_ORDER[0]

    recipient = row.get("recipient")
    recipient = str(recipient).strip() or None if recipient is not None else None

    return DeliveryCandidate(
        org_id=str(row["org_id"]), subject_id=str(row["card_id"]),
        channel=str(row["channel"]), channel_class=channel_class, band=band,
        interrupt=bool(row.get("interrupt")), recipient=recipient)


# ── the composition ───────────────────────────────────────────────────────────────────
def evaluate_delivery(candidate: DeliveryCandidate, context: DeliveryContext, *,
                      now: datetime) -> DeliveryDecision:
    """Fold every unit's judgement into the one answer the outbox acts on.

    Policy is asked first and short-circuits on SUPPRESS.  Not an optimisation — a correctness
    statement about the audit row: when a person has opted out *and* it happens to be 3am, the
    honest reason is the opt-out.  Computing a humane delivery window for a message that will
    never be sent would put "quiet_hours" in the row and send an operator looking at the clock.

    Everything else composes through ``DeliveryDecision.combine``, whose intersection semantics
    guarantee that adding a unit can only ever make this layer quieter.

    Timing is folded *first* even though policy is *asked* first, and only one case can tell the
    difference: both units saying SEND, where ``combine`` keeps the earliest argument.  Timing's
    reason is the one worth keeping there — ``override_band_critical`` records that something
    deliberately broke through quiet hours, which is precisely the send anyone reviewing this
    layer wants to find.  ``policy:permitted`` would say only that nothing objected.
    """
    permission = evaluate_policy(candidate, context.policy, now=now)
    if permission.verdict is DeliveryVerdict.SUPPRESS:
        return permission

    moment = evaluate_timing(candidate, context.profile, context.state, now=now)
    return DeliveryDecision.combine(moment, permission)


def defer_until(decision: DeliveryDecision, now: datetime) -> datetime:
    """When a deferred row should next be looked at.

    Clamped strictly forward.  A window that has already opened — a stale ``busy_until``, a clock
    that skewed, a sweep that was paused over the weekend — would otherwise make the row due
    immediately and spin the drain against a constraint it just failed.  One minute is enough to
    guarantee progress without meaningfully delaying anything.
    """
    target = decision.not_before or now
    return max(target, now + _MIN_DEFER)


# ── resolution: pure ──────────────────────────────────────────────────────────────────
def _rank(row: Mapping[str, Any], seat: str, channel: str) -> int:
    """Position in ``_SPECIFICITY`` — lower is more specific.  Non-matching rows sort last."""
    key = (str(row.get("seat_id") or WILDCARD) == seat and seat != WILDCARD,
           str(row.get("channel") or WILDCARD) == channel)
    try:
        return _SPECIFICITY.index(key)
    except ValueError:                                      # pragma: no cover - unreachable
        return len(_SPECIFICITY)


def resolve_preferences(rows: Iterable[Mapping[str, Any]], seat: str,
                        channel: str) -> dict[str, Any]:
    """Collapse the (at most four) rows that could apply into one flat set of settings.

    Field-by-field rather than row-by-row, and that distinction is the whole point.  A person who
    sets only their timezone should not thereby discard their tenant's quiet hours — picking a
    winning *row* would do exactly that.  Null means *inherit*, so each column independently walks
    from most specific to least and takes the first opinion it finds.
    """
    ordered = sorted(rows, key=lambda row: _rank(row, seat, channel))
    resolved: dict[str, Any] = {}
    for row in ordered:
        for column, value in row.items():
            if value is not None and column not in resolved:
                resolved[column] = value
    for structural in ("org_id", "seat_id", "channel", "created_at", "updated_at", "updated_by"):
        resolved.pop(structural, None)
    return resolved


@dataclass(slots=True)
class _Errors:
    """Collects unusable settings so the gate can report them instead of raising."""

    notes: list[str] = field(default_factory=list)

    def bad(self, label: str, value: Any) -> None:
        self.notes.append(f"{label}={value!r}")

    def summary(self) -> str | None:
        return ("unusable delivery preferences: " + ", ".join(self.notes)) if self.notes else None


def _as_bool(value: Any, fallback: bool, label: str, errors: _Errors) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):          # sqlite hands booleans back as ints
        return bool(value)
    errors.bad(label, value)
    return fallback


def _as_hour(value: Any, fallback: int, label: str, errors: _Errors) -> int:
    if value is None:
        return fallback
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 23:
        return value
    errors.bad(label, value)
    return fallback


def _as_count(value: Any, fallback: int, label: str, errors: _Errors) -> int:
    if value is None:
        return fallback
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    errors.bad(label, value)
    return fallback


def _as_band(value: Any, fallback: str, label: str, errors: _Errors) -> str:
    if value is None:
        return fallback
    if isinstance(value, str) and value in BAND_ORDER:
        return value
    errors.bad(label, value)
    return fallback


def _as_moment(value: Any, label: str, errors: _Errors) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value
    errors.bad(label, value)
    return None


def build_context(preferences: Mapping[str, Any], *, channel_enabled: bool,
                  recipient_active: bool, interrupts_last_hour: int = 0,
                  oldest_interrupt_at: datetime | None = None,
                  busy_until: datetime | None = None,
                  current_activity: str | None = None,
                  current_surface: str | None = None) -> DeliveryContext:
    """Resolved settings + live signals → the two frozen inputs the units consume.

    Pure, and total: it never raises.  Every branch that could fail resolves to the *default*
    rather than to the permissive answer, because the defaults were chosen to be safe — a broken
    timezone falls back to UTC quiet hours, not to no quiet hours.  A tenant with a typo gets
    slightly wrong-hour politeness; the alternative on a raise is a drain loop that dies on one
    row and stops delivering for everybody.
    """
    errors = _Errors()
    defaults_policy, defaults_profile = DeliveryPolicy(), AttentionProfile()

    delivery_enabled = _as_bool(preferences.get("delivery_enabled"),
                                defaults_policy.delivery_enabled, "delivery_enabled", errors)
    hold_until = _as_moment(preferences.get("hold_until"), "hold_until", errors)
    # A stop and a pause are different promises and the contract refuses to hold both. When a row
    # somehow carries both, the stop wins: it is the quieter reading, and this layer's whole
    # composition law is that ambiguity resolves toward silence rather than toward noise.
    if hold_until is not None and not delivery_enabled:
        errors.bad("hold_until", "set alongside delivery_enabled=false")
        hold_until = None

    quiet_start = _as_hour(preferences.get("quiet_start_hour"),
                           defaults_profile.quiet_start_hour, "quiet_start_hour", errors)
    quiet_end = _as_hour(preferences.get("quiet_end_hour"),
                         defaults_profile.quiet_end_hour, "quiet_end_hour", errors)
    quiet_enabled = _as_bool(preferences.get("quiet_enabled"),
                             defaults_profile.quiet_enabled, "quiet_enabled", errors)
    # Equal bounds are the ambiguous config the contract refuses — zero hours of quiet, or
    # twenty-four? One reading mutes the tenant forever. Falling back to the default window keeps
    # the protective intent of whoever set it while refusing to guess which they meant.
    if quiet_enabled and quiet_start == quiet_end:
        errors.bad("quiet_start_hour", "equal to quiet_end_hour")
        quiet_start, quiet_end = (defaults_profile.quiet_start_hour,
                                  defaults_profile.quiet_end_hour)

    timezone_name = preferences.get("tz_name") or defaults_profile.timezone
    try:
        profile = AttentionProfile(
            timezone=str(timezone_name),
            quiet_enabled=quiet_enabled,
            quiet_start_hour=quiet_start,
            quiet_end_hour=quiet_end,
            quiet_weekends=_as_bool(preferences.get("quiet_weekends"),
                                    defaults_profile.quiet_weekends, "quiet_weekends", errors),
            max_interrupts_per_hour=_as_count(
                preferences.get("max_interrupts_per_hour"),
                defaults_profile.max_interrupts_per_hour, "max_interrupts_per_hour", errors),
            override_band=_as_band(preferences.get("override_band"),
                                   defaults_profile.override_band, "override_band", errors))
    except ValueError:
        # Reachable through an unknown timezone, which is the one field with no cheap local
        # validation. Everything else was coerced above.
        errors.bad("tz_name", timezone_name)
        profile = defaults_profile

    policy = DeliveryPolicy(
        delivery_enabled=delivery_enabled,
        hold_until=hold_until,
        channel_enabled=bool(channel_enabled),
        channel_min_band=_as_band(preferences.get("min_band"),
                                  defaults_policy.channel_min_band, "min_band", errors),
        recipient_active=bool(recipient_active),
        recipient_opted_out=_as_bool(preferences.get("opted_out"),
                                     defaults_policy.recipient_opted_out, "opted_out", errors))

    state = AttentionState(busy_until=busy_until,
                           interrupts_last_hour=max(0, int(interrupts_last_hour)),
                           oldest_interrupt_at=oldest_interrupt_at,
                           current_activity=current_activity,
                           current_surface=current_surface)
    return DeliveryContext(policy=policy, profile=profile, state=state,
                           config_error=errors.summary())


# ── resolution: the Postgres provider ─────────────────────────────────────────────────
class PgDeliveryContext:
    """Reads live tenant state so the pure units can decide.

    Memoised per (org, recipient, channel) for the life of one drain pass, because a pass
    routinely holds several messages for the same person and re-reading their timezone once per
    message is pure waste.

    The one thing that is *not* memoised is the interruption count, and that omission is the
    interesting part.  Ten intrusive messages can come due in the same pass; if the count were
    frozen at zero for all ten, a limit of three would let every one of them through — the exact
    flood the limiter exists to prevent.  Each successful send is committed before the next
    candidate resolves, and ``_release`` gives the next count query a fresh transaction, so the
    fourth message sees the three that preceded it seconds earlier.
    """

    def __init__(self, conn) -> None:
        self._conn = conn
        self._settings: dict[tuple[str, str, str], tuple[dict[str, Any], bool, bool]] = {}

    # -- keys ---------------------------------------------------------------------------
    @staticmethod
    def attention_key(candidate: DeliveryCandidate) -> str:
        """Whose attention this spends.

        An org-wide surface — a shared Slack webhook, the daily digest — has no single owner, and
        the wildcard is the honest answer rather than a placeholder: the tenant's own quiet hours
        are what should govern a channel the whole team reads.  It also makes the burst limiter
        do the right thing for free, counting a shared channel's traffic as one stream.
        """
        return candidate.recipient or WILDCARD

    # -- reads --------------------------------------------------------------------------
    def _read_settings(self, candidate: DeliveryCandidate) -> tuple[dict[str, Any], bool, bool]:
        seat = self.attention_key(candidate)
        key = (candidate.org_id, seat, candidate.channel)
        if key in self._settings:
            return self._settings[key]

        rows = self._conn.execute(text(
            "select * from delivery_preferences where org_id=:o "
            "and seat_id in (:seat, :any) and channel in (:ch, :any)"),
            {"o": candidate.org_id, "seat": seat, "ch": candidate.channel,
             "any": WILDCARD}).mappings().all()
        preferences = resolve_preferences([dict(row) for row in rows], seat, candidate.channel)

        channel_enabled = self._conn.execute(text(
            "select 1 from org_channels where org_id=:o and channel=:ch and active"),
            {"o": candidate.org_id, "ch": candidate.channel}).first() is not None

        # A wildcard recipient is an org surface, not a seat, so there is no seat to be
        # deactivated. Asking org_seats for '*' would find nothing and suppress every card.
        if candidate.recipient is None:
            recipient_active = True
        else:
            recipient_active = self._conn.execute(text(
                "select 1 from org_seats where org_id=:o and seat_id=:s and active"),
                {"o": candidate.org_id, "s": candidate.recipient}).first() is not None

        self._settings[key] = (preferences, channel_enabled, recipient_active)
        return self._settings[key]

    def _burst(self, candidate: DeliveryCandidate,
               now: datetime) -> tuple[int, datetime | None]:
        """How many intrusive messages this recipient has taken in the last hour, and when the
        window opened — the two numbers the burst limiter needs to say when it clears."""
        since = now - BURST_WINDOW
        recipient_clause = ("recipient is null" if candidate.recipient is None
                            else "recipient = :r")
        params: dict[str, Any] = {"o": candidate.org_id, "since": since,
                                  "classes": list(_INTRUSIVE_VALUES)}
        if candidate.recipient is not None:
            params["r"] = candidate.recipient
        row = self._conn.execute(text(
            "select count(*) as sent, min(delivered_at) as oldest from delivery_outbox "
            f"where org_id=:o and {recipient_clause} and status='delivered' "
            "and delivered_at > :since and channel_class = any(:classes)"),
            params).mappings().first()

        return int((row or {}).get("sent") or 0), (row or {}).get("oldest")

    def _presence(self, candidate: DeliveryCandidate, now: datetime) \
            -> tuple[datetime | None, str | None, str | None]:
        """Resolve one live, leased product-surface context for this recipient.

        Org-wide surfaces have no person whose activity can be inferred. Expired rows are
        ignored in SQL and again by the contract, so a client crash can never create a permanent
        focus hold.
        """
        if candidate.recipient is None:
            return None, None, None
        try:
            row = self._conn.execute(text(
                "select org_id, seat_id, activity, surface, focus_mode, busy_until, "
                "observed_at, expires_at from delivery_presence "
                "where org_id=:o and seat_id=:s and expires_at>:now"),
                {"o": candidate.org_id, "s": candidate.recipient,
                 "now": now}).mappings().first()
        except Exception:  # noqa: BLE001 — optional context must survive a rolling migration
            # Presence is an additive politeness signal. During a rolling deploy an old schema,
            # or a context provider that is temporarily unavailable, must not turn a healthy
            # outbox into transport failures. Quiet hours and burst policy still apply.
            return None, None, None
        if row is None:
            return None, None, None
        from genios_engine.deliver.presence import presence_from_row
        presence = presence_from_row(dict(row))
        return (presence.effective_busy_until(now), presence.activity.value,
                presence.surface)

    # -- the interface the outbox uses ---------------------------------------------------
    def resolve(self, candidate: DeliveryCandidate, *, now: datetime) -> DeliveryContext:
        preferences, channel_enabled, recipient_active = self._read_settings(candidate)
        interrupts, oldest = self._burst(candidate, now)
        busy_until, activity, surface = self._presence(candidate, now)
        self._release()
        return build_context(preferences, channel_enabled=channel_enabled,
                             recipient_active=recipient_active,
                             interrupts_last_hour=interrupts, oldest_interrupt_at=oldest,
                             busy_until=busy_until, current_activity=activity,
                             current_surface=surface)

    def _release(self) -> None:
        """End the read transaction between rows.

        These are read-only queries, so a rollback costs nothing and buys two things. The
        connection stops sitting `idle in transaction` across an outbound HTTP call — which
        holds a snapshot and blocks vacuum for as long as Slack takes to answer — and each
        resolve gets a fresh snapshot, so a delivery this pass committed a second ago is
        visible to the next one rather than hidden behind a stale view.

        Guarded because the injected reader in tests is a plain object with no transaction.
        """
        rollback = getattr(self._conn, "rollback", None)
        if callable(rollback):
            rollback()

def admit(candidate: DeliveryCandidate, resolver: PgDeliveryContext, *,
          now: datetime) -> tuple[DeliveryDecision, DeliveryContext]:
    """Resolve and decide in one call — the shape ``outbox.drain`` wants.

    Returns the context alongside the verdict so the caller can put the resolved settings into
    the audit row.  "It was held because quiet hours" is only half an answer; "…and this tenant's
    quiet hours are 21:00–08:00 Asia/Kolkata" is the half that ends the support ticket.
    """
    context = resolver.resolve(candidate, now=now)
    return evaluate_delivery(candidate, context, now=now), context


def describe_decision(decision: DeliveryDecision, context: DeliveryContext) -> dict[str, Any]:
    """The loggable record of one admission — verdict, reason, and the settings behind it."""
    record: dict[str, Any] = {"verdict": decision.verdict.value, "unit": decision.unit,
                              "reason_code": decision.reason_code,
                              "not_before": (decision.not_before.isoformat()
                                             if decision.not_before else None),
                              "detail": dict(decision.detail)}
    if context.config_error:
        record["config_error"] = context.config_error
    return record


__all__ = ["BURST_WINDOW", "GATE_VERSION", "UNIT", "WILDCARD", "DeliveryContext",
           "PgDeliveryContext", "admit", "build_context", "candidate_from_row",
           "channel_class_for", "defer_until", "describe_decision", "evaluate_delivery",
           "resolve_preferences"]

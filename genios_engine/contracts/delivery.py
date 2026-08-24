"""The delivery admission contract — what Layer 5.2 is allowed to answer, and nothing else.

Layer 5 decides **whether a person should be told something**.  This contract is the vocabulary
of the question that comes after: *given that they should be told, may it happen now, to them,
on this channel?*  Those are genuinely different questions and conflating them is how a system
starts either paging people at 3am or quietly deciding on their behalf that a churn alert was
not worth their evening.

Exactly three answers exist, and the set is deliberately closed:

  ``SEND``      the moment is fine — hand it to the adapter.
  ``DEFER``     the message is right, the moment is wrong.  It waits until ``not_before``.
  ``SUPPRESS``  it must never travel this way.  Not later, not louder.

**Why DEFER is not a failure.**  This is the single most important distinction in the file.
The outbox already has a retry ladder for *failures* — a webhook timing out, a 500 from Slack —
and that ladder is bounded, because a channel that never works must eventually stop being tried.
Deferral is the opposite kind of event: nothing is broken, the recipient is simply asleep.  If
deferral consumed retry attempts, a message queued at 22:00 would burn its four attempts against
quiet hours and be declared permanently undeliverable by breakfast — the exact message the
recipient most wanted.  ``deliver/outbox.py`` therefore routes a DEFER through a path that moves
the clock and touches nothing else, and ``tests/test_delivery_gate.py`` locks that behaviour.

**Why the composition rule is "most restrictive wins".**  Several units judge the same delivery
independently — policy asks whether it is permitted, timing asks whether the moment is humane —
and a delivery must satisfy *all* of them.  ``combine`` is therefore an intersection, not a vote:
one SUPPRESS ends it, and among deferrals the *latest* window is the binding one, because
satisfying the earliest would violate the other.  Adding a fourth unit later is adding a decision
to the fold; it can only ever make the system quieter, never louder, which is the correct
direction for a mechanism that spends human attention.

Import rule: this module sits in ``contracts/`` and may import nothing above ``platform``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

import hashlib

from genios_engine.contracts.execution import AudienceClass, ChannelClass
from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_bool,
    require_enum,
    require_identifier,
)
from genios_engine.platform.canonical import canonical_dumps

DELIVERY_VERSION = "delivery.v1"

#: Layer 5.2's one output projection — the materialised delivery, distinct from the v1 admission
#: verdict above. v1 answers "may this travel now?"; v2 *is* the delivery: a durable, fenced,
#: deduped row with its own lifecycle, route ladder and priority. The two versions coexist because
#: the gate (v1) still runs inside the orchestrator that builds the object (v2).
DELIVERY_RESULT_VERSION = "delivery-result.v2"

#: The three urgency names, weakest first.  This orders them; it does not *assign* them —
#: ``deliver/bands.py`` cuts a band from a score using the pack's own thresholds, and those
#: thresholds stay the single tenant-facing dial.  Ordering and assignment are different
#: concerns, and only the second one is configurable, so stating the order here duplicates no
#: knob: a tenant who redefines what "critical" means redefines it in exactly one place.
BAND_ORDER: tuple[str, ...] = ("standard", "high", "critical")

#: Channel classes whose arrival makes a device buzz in somebody's pocket.
#:
#: Only ``CHAT`` for now, and the omissions are deliberate rather than pending.  ``IN_APP`` and
#: ``DIGEST`` are surfaces a person visits when *they* choose to; gating them on quiet hours
#: would delay a dashboard card that was never going to wake anyone.  ``EMAIL`` is absent
#: because email is the channel people already treat as asynchronous — an inbox at 03:00 is not
#: an interruption, it is a queue — and the day an email adapter ships with different semantics,
#: this set is the one line that changes.
INTRUSIVE_CHANNEL_CLASSES: frozenset[ChannelClass] = frozenset({ChannelClass.CHAT})


class DeliveryVerdict(str, Enum):
    """The closed set of answers to "may this be delivered now?"."""

    SEND = "send"
    DEFER = "defer"
    SUPPRESS = "suppress"


#: How much each verdict constrains the delivery.  ``combine`` folds on this, so the ordering
#: *is* the composition law: nothing a unit can return may loosen what another unit decided.
_RESTRICTIVENESS: Mapping[DeliveryVerdict, int] = MappingProxyType({
    DeliveryVerdict.SEND: 0,
    DeliveryVerdict.DEFER: 1,
    DeliveryVerdict.SUPPRESS: 2,
})


@dataclass(frozen=True, slots=True)
class DeliveryCandidate:
    """One delivery awaiting admission — the subject every unit judges.

    Deliberately thin.  It carries what a unit needs to decide *whether this may travel now* and
    nothing about what it says: no headline, no facts, no payload.  A timing unit that could read
    the message body would eventually be asked to make an exception for an important-sounding one,
    and at that point "should I interrupt?" has quietly become a second reasoning engine sitting
    below the real one.  Loudness was decided upstairs; this layer only decides admissibility.
    """

    org_id: str
    subject_id: str                  # the outbox key — a card id, digest key, or exec: reminder
    channel: str                     # the concrete adapter: 'slack'
    channel_class: ChannelClass      # the intent: chat, digest, in_app, agent
    band: str                        # standard | high | critical
    interrupt: bool                  # Layer 5's judgement that this is worth someone's attention
    recipient: str | None = None     # seat id; None = an org-wide surface with no single owner

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "subject_id", require_identifier(self.subject_id, "subject id"))
        setattr_(self, "channel", require_identifier(self.channel, "channel"))
        setattr_(self, "channel_class",
                 require_enum(self.channel_class, ChannelClass, "channel class"))
        setattr_(self, "interrupt", require_bool(self.interrupt, "interrupt"))
        band = require_identifier(self.band, "band")
        if band not in BAND_ORDER:
            raise ValueError(f"band must be one of {BAND_ORDER}, got {band!r}")
        setattr_(self, "band", band)
        if self.recipient is not None:
            setattr_(self, "recipient", require_identifier(self.recipient, "recipient"))

    @property
    def band_rank(self) -> int:
        return BAND_ORDER.index(self.band)

    @property
    def intrusive(self) -> bool:
        """Does landing this message cost the recipient attention they did not choose to spend?

        This — not ``interrupt`` — is what quiet hours key on.  Layer 5 sets ``interrupt`` to mean
        "this deserves attention"; a high-band card is pushed to Slack with ``interrupt=False``,
        and it still pings a phone at midnight.  Gating on the channel's physics rather than on
        the sender's intent is what closes that gap.
        """
        return self.channel_class in INTRUSIVE_CHANNEL_CLASSES

    def at_least(self, band: str) -> bool:
        """True when this candidate is at or above ``band`` — the break-glass comparison."""
        if band not in BAND_ORDER:
            raise ValueError(f"band must be one of {BAND_ORDER}, got {band!r}")
        return self.band_rank >= BAND_ORDER.index(band)

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "subject_id": self.subject_id, "channel": self.channel,
                "channel_class": self.channel_class.value, "band": self.band,
                "interrupt": self.interrupt, "recipient": self.recipient}


@dataclass(frozen=True, slots=True)
class DeliveryDecision:
    """One unit's verdict on one delivery, with the reason it reached it.

    ``unit`` and ``reason_code`` are both mandatory and both identifiers.  When somebody asks
    "why didn't I get told about this?" — and that question is asked far more often, and far more
    angrily, than "why did I get told about this?" — the answer has to already be in the row.
    A bare boolean would make every such question a debugging session against a clock that has
    since moved on.
    """

    verdict: DeliveryVerdict
    unit: str
    reason_code: str
    not_before: datetime | None = None
    detail: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "verdict", require_enum(self.verdict, DeliveryVerdict, "delivery verdict"))
        setattr_(self, "unit", require_identifier(self.unit, "deciding unit"))
        setattr_(self, "reason_code", require_identifier(self.reason_code, "delivery reason code"))
        if self.not_before is not None:
            setattr_(self, "not_before", require_aware(self.not_before, "not_before"))
        setattr_(self, "detail", freeze_mapping(self.detail))

        # The two halves of the same invariant.  A DEFER without a clock is a message that waits
        # forever; a SEND *with* one is a unit that meant to defer and forgot to say so.  Both are
        # silent-loss bugs in production, so both are construction-time errors here.
        if self.verdict is DeliveryVerdict.DEFER and self.not_before is None:
            raise ValueError(
                f"{self.unit} deferred '{self.reason_code}' without a not_before: "
                "a deferral with no clock never wakes up")
        if self.verdict is not DeliveryVerdict.DEFER and self.not_before is not None:
            raise ValueError(
                f"{self.unit} returned {self.verdict.value} with a not_before; "
                "only a deferral carries a clock")

    # ---- derived -----------------------------------------------------------------------

    @property
    def restrictiveness(self) -> int:
        return _RESTRICTIVENESS[self.verdict]

    @property
    def blocks_delivery(self) -> bool:
        return self.verdict is not DeliveryVerdict.SEND

    def is_satisfied_at(self, now: datetime) -> bool:
        """Has this constraint stopped biting by ``now``?

        A deferral whose window has already opened is satisfied — the constraint was "not before
        08:00", and it is 08:30.  Written as a comparison rather than assumed away because clocks
        skew, sweeps get paused, and a deferral that outlived its own reason must not keep a
        message hostage; the failure mode of the alternative is a queue that silently never
        drains.  A suppression is never satisfied by the passage of time, which is exactly what
        distinguishes it from a deferral.
        """
        if self.verdict is DeliveryVerdict.SEND:
            return True
        if self.verdict is DeliveryVerdict.SUPPRESS:
            return False
        return require_aware(now, "now") >= self.not_before        # type: ignore[operator]

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "unit": self.unit,
                "reason_code": self.reason_code, "not_before": self.not_before,
                "detail": self.detail}

    def describe(self) -> str:
        when = f" until {self.not_before.isoformat()}" if self.not_before else ""
        return f"{self.verdict.value}{when} · {self.unit}:{self.reason_code}"

    # ---- constructors ------------------------------------------------------------------

    @classmethod
    def send(cls, unit: str, reason_code: str, **detail: Any) -> DeliveryDecision:
        return cls(verdict=DeliveryVerdict.SEND, unit=unit, reason_code=reason_code,
                   detail=detail)

    @classmethod
    def defer(cls, unit: str, reason_code: str, not_before: datetime,
              **detail: Any) -> DeliveryDecision:
        return cls(verdict=DeliveryVerdict.DEFER, unit=unit, reason_code=reason_code,
                   not_before=not_before, detail=detail)

    @classmethod
    def suppress(cls, unit: str, reason_code: str, **detail: Any) -> DeliveryDecision:
        return cls(verdict=DeliveryVerdict.SUPPRESS, unit=unit, reason_code=reason_code,
                   detail=detail)

    # ---- composition -------------------------------------------------------------------

    @staticmethod
    def combine(*decisions: DeliveryDecision) -> DeliveryDecision:
        """Fold independent judgements into the one a delivery must actually obey.

        Intersection semantics, and the tie-breaks are all *deterministic* rather than merely
        correct.  Two units that both suppress must always name the same reason in the audit row,
        or the same delivery blocked twice would be explained two different ways depending on
        dictionary ordering — the kind of nondeterminism that turns an incident review into
        an argument.  So: first SUPPRESS in argument order wins; among DEFERs the latest window
        wins, breaking ties on argument order; otherwise the first SEND.
        """
        if not decisions:
            raise ValueError("combine() requires at least one decision")
        if any(not isinstance(item, DeliveryDecision) for item in decisions):
            raise TypeError("combine() takes DeliveryDecision instances")

        strongest = max(item.restrictiveness for item in decisions)
        binding = [item for item in decisions if item.restrictiveness == strongest]
        if strongest == _RESTRICTIVENESS[DeliveryVerdict.DEFER]:
            # max() keeps the first maximum, so equal windows resolve to argument order.
            return max(binding, key=lambda item: item.not_before)   # type: ignore[arg-type,return-value]
        return binding[0]


# =======================================================================================
# Layer 5.2 control plane — the v2 DeliveryObject and its vocabulary.
# =======================================================================================


class DeliveryPriority(str, Enum):
    """Five business-priority classes the scheduler orders due work by (section 5.6 of the spec).

    This is *scheduling* priority, distinct from ``band`` (which is loudness) and from
    ``interrupt`` (which is Layer 5's attention judgement). Ordered weakest-first by
    ``_PRIORITY_RANK`` so the scheduler can compare without a second table.
    """

    BACKGROUND = "background"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_PRIORITY_RANK: Mapping[str, int] = MappingProxyType({
    DeliveryPriority.BACKGROUND.value: 0,
    DeliveryPriority.LOW.value: 1,
    DeliveryPriority.MEDIUM.value: 2,
    DeliveryPriority.HIGH.value: 3,
    DeliveryPriority.CRITICAL.value: 4,
})


def priority_from_band(band: str, interrupt: bool) -> DeliveryPriority:
    """Map (loudness, attention) → scheduling class deterministically. No model, no config drift.

    ``critical`` + an attention request is the only thing that earns CRITICAL scheduling; a
    critical card nobody asked to be interrupted for is still HIGH. ``standard`` band splits on
    interrupt so a routine nudge does not starve behind batch work forever.
    """
    if band not in BAND_ORDER:
        raise ValueError(f"band must be one of {BAND_ORDER}, got {band!r}")
    if band == "critical":
        return DeliveryPriority.CRITICAL if interrupt else DeliveryPriority.HIGH
    if band == "high":
        return DeliveryPriority.HIGH if interrupt else DeliveryPriority.MEDIUM
    return DeliveryPriority.LOW if interrupt else DeliveryPriority.BACKGROUND


class DeliveryFormat(str, Enum):
    """The concrete shape the Channel Planner renders — never chosen by a model (routing law)."""

    INLINE_SUGGESTION = "inline_suggestion"
    CARD = "card"
    CHAT_MESSAGE = "chat_message"        # Slack / Teams
    WEBHOOK_PAYLOAD = "webhook_payload"
    AGENT_ENVELOPE = "agent_envelope"
    REST_RESOURCE = "rest_resource"


class DeliveryLifecycle(str, Enum):
    """Public engagement lifecycle, separate from raw transport state (section 5.2).

    Transport ``failed`` is one terminal; ``suppressed`` (policy said never) and ``cancelled``
    (the subject died before send) are distinct terminals with different meanings and different
    fixes — collapsing them makes "why did nothing arrive?" unanswerable from the row.
    """

    QUEUED = "queued"
    DEFERRED = "deferred"
    DELIVERED = "delivered"
    VIEWED = "viewed"
    IGNORED = "ignored"
    ACCEPTED = "accepted"
    EXECUTED = "executed"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


#: queued → deferred → delivered → viewed → ignored ; delivered → accepted → executed | failed ;
#: most live states may expire where legal. suppressed/cancelled/expired/executed/failed/ignored
#: are terminal. The Tracker (Phase 4) enforces this; the vocabulary lives here so the migration's
#: CHECK constraints and the tracker share one source of truth.
ALLOWED_DELIVERY_TRANSITIONS: MappingProxyType = MappingProxyType({
    DeliveryLifecycle.QUEUED:    (DeliveryLifecycle.DEFERRED, DeliveryLifecycle.DELIVERED,
                                  DeliveryLifecycle.SUPPRESSED, DeliveryLifecycle.CANCELLED,
                                  DeliveryLifecycle.FAILED, DeliveryLifecycle.EXPIRED),
    DeliveryLifecycle.DEFERRED:  (DeliveryLifecycle.DELIVERED, DeliveryLifecycle.SUPPRESSED,
                                  DeliveryLifecycle.CANCELLED, DeliveryLifecycle.FAILED,
                                  DeliveryLifecycle.EXPIRED),
    DeliveryLifecycle.DELIVERED: (DeliveryLifecycle.VIEWED, DeliveryLifecycle.ACCEPTED,
                                  DeliveryLifecycle.IGNORED, DeliveryLifecycle.EXPIRED,
                                  DeliveryLifecycle.FAILED),
    DeliveryLifecycle.VIEWED:    (DeliveryLifecycle.ACCEPTED, DeliveryLifecycle.IGNORED,
                                  DeliveryLifecycle.EXPIRED),
    DeliveryLifecycle.ACCEPTED:  (DeliveryLifecycle.EXECUTED, DeliveryLifecycle.FAILED,
                                  DeliveryLifecycle.EXPIRED),
    DeliveryLifecycle.EXECUTED:  (),
    DeliveryLifecycle.IGNORED:   (),
    DeliveryLifecycle.FAILED:    (),
    DeliveryLifecycle.SUPPRESSED: (),
    DeliveryLifecycle.CANCELLED: (),
    DeliveryLifecycle.EXPIRED:   (),
})

TERMINAL_DELIVERY_STATES: frozenset[DeliveryLifecycle] = frozenset({
    DeliveryLifecycle.EXECUTED, DeliveryLifecycle.IGNORED, DeliveryLifecycle.FAILED,
    DeliveryLifecycle.SUPPRESSED, DeliveryLifecycle.CANCELLED, DeliveryLifecycle.EXPIRED})


def delivery_can_transition(current: DeliveryLifecycle, target: DeliveryLifecycle) -> bool:
    return target in ALLOWED_DELIVERY_TRANSITIONS.get(current, ())


@dataclass(frozen=True, slots=True)
class DeliveryObject:
    """One materialised delivery — Layer 5.2's single output (section 5.8).

    It is the durable spine: one logical row per insight, carrying the execution lineage it was
    authorised by, the audience/recipient/destination it resolved to, the concrete channel/format
    the planner chose, its scheduling priority and daily budget, the dedupe key that makes ten
    destinations one delivery, and the route ladder a fallback advances along. It is frozen and
    content-addressed on the fields that define *what this delivery is* — never the routing cursor
    or the clock, so a fallback or a retry is the same delivery, not a new one.
    """

    org_id: str
    delivery_id: str                     # the logical delivery identity (one per insight)
    execution_id: str                    # Layer 5 lineage — the only thing that authorises a send
    execution_hash: str                  # the exact persisted ExecutionObject hash
    audience: AudienceClass
    channel: str                         # concrete adapter: slack | teams | webhook | api | ...
    channel_class: ChannelClass
    fmt: DeliveryFormat
    priority: DeliveryPriority
    band: str
    dedupe_key: str
    route_ladder: tuple[str, ...]        # primary → fallback channels, in order
    recipient: str | None = None         # seat/agent id; None = org-wide surface
    destination: str | None = None       # registered destination id, if any
    route_cursor: int = 0                # which rung of route_ladder is live (not part of identity)
    retry_generation: int = 0            # bumped only by a definite-non-delivery replay
    daily_budget: int | None = None      # snapshotted attention ceiling for the recipient/day
    source: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    authority_expires_at: datetime | None = None
    schema_version: str = DELIVERY_RESULT_VERSION

    def __post_init__(self) -> None:
        s = object.__setattr__
        s(self, "org_id", require_identifier(self.org_id, "org id"))
        s(self, "delivery_id", require_identifier(self.delivery_id, "delivery id"))
        s(self, "execution_id", require_identifier(self.execution_id, "execution id"))
        s(self, "execution_hash", require_identifier(self.execution_hash, "execution hash"))
        s(self, "audience", require_enum(self.audience, AudienceClass, "audience"))
        s(self, "channel", require_identifier(self.channel, "channel"))
        s(self, "channel_class", require_enum(self.channel_class, ChannelClass, "channel class"))
        s(self, "fmt", require_enum(self.fmt, DeliveryFormat, "format"))
        s(self, "priority", require_enum(self.priority, DeliveryPriority, "priority"))
        band = require_identifier(self.band, "band")
        if band not in BAND_ORDER:
            raise ValueError(f"band must be one of {BAND_ORDER}, got {band!r}")
        s(self, "band", band)
        s(self, "dedupe_key", require_identifier(self.dedupe_key, "dedupe key"))
        ladder = tuple(self.route_ladder)
        if not ladder:
            raise ValueError("a delivery with no route ladder cannot be delivered")
        if any(not isinstance(rung, str) or not rung for rung in ladder):
            raise ValueError("every route-ladder rung must be a non-empty channel name")
        s(self, "route_ladder", ladder)
        if self.channel != ladder[0] and self.channel not in ladder:
            raise ValueError("the live channel must be a rung of its own route ladder")
        if self.recipient is not None:
            s(self, "recipient", require_identifier(self.recipient, "recipient"))
        if self.destination is not None:
            s(self, "destination", require_identifier(self.destination, "destination"))
        for name in ("route_cursor", "retry_generation"):
            val = getattr(self, name)
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.route_cursor >= len(ladder):
            raise ValueError("route_cursor points past the end of the ladder")
        if self.daily_budget is not None:
            if not isinstance(self.daily_budget, int) or isinstance(self.daily_budget, bool) \
                    or self.daily_budget < 0:
                raise ValueError("daily_budget must be a non-negative integer or None")
        if self.authority_expires_at is not None:
            s(self, "authority_expires_at",
              require_aware(self.authority_expires_at, "authority_expires_at"))
        s(self, "source", freeze_mapping(self.source))
        s(self, "schema_version", require_identifier(self.schema_version, "schema version"))

    @property
    def priority_rank(self) -> int:
        return _PRIORITY_RANK[self.priority.value]

    @property
    def live_channel(self) -> str:
        """The channel actually being tried right now — the ladder rung under the cursor."""
        return self.route_ladder[self.route_cursor]

    @property
    def identity(self) -> Mapping[str, Any]:
        """The fields that define *what this delivery is* — excludes cursor, retry and clocks.

        Advancing the route ladder or replaying must not mint a new delivery for the deduper or
        the learner to chase separately, so those live-state fields are deliberately out.
        """
        return MappingProxyType({
            "schema_version": self.schema_version, "org_id": self.org_id,
            "delivery_id": self.delivery_id, "execution_id": self.execution_id,
            "execution_hash": self.execution_hash, "audience": self.audience.value,
            "recipient": self.recipient, "destination": self.destination,
            "channel_class": self.channel_class.value, "band": self.band,
            "dedupe_key": self.dedupe_key, "route_ladder": list(self.route_ladder)})

    def semantic_hash(self) -> str:
        """Content address over ``identity`` — stable across fallback and retry."""
        return hashlib.sha256(canonical_dumps(dict(self.identity)).encode()).hexdigest()

    def advanced(self) -> "DeliveryObject":
        """The same delivery, moved to the next route rung. Raises if the ladder is exhausted."""
        if self.route_cursor + 1 >= len(self.route_ladder):
            raise ValueError("route ladder exhausted — no further fallback")
        nxt = self.route_ladder[self.route_cursor + 1]
        return replace(self, route_cursor=self.route_cursor + 1, channel=nxt)

    def to_semantic_dict(self) -> dict[str, Any]:
        return {**dict(self.identity), "fmt": self.fmt.value, "priority": self.priority.value,
                "channel": self.channel, "route_cursor": self.route_cursor,
                "retry_generation": self.retry_generation, "daily_budget": self.daily_budget,
                "authority_expires_at": self.authority_expires_at, "source": dict(self.source)}


__all__ = ["ALLOWED_DELIVERY_TRANSITIONS", "BAND_ORDER", "DELIVERY_RESULT_VERSION",
           "DELIVERY_VERSION", "INTRUSIVE_CHANNEL_CLASSES", "TERMINAL_DELIVERY_STATES",
           "DeliveryCandidate", "DeliveryDecision", "DeliveryFormat", "DeliveryLifecycle",
           "DeliveryObject", "DeliveryPriority", "DeliveryVerdict", "delivery_can_transition",
           "priority_from_band"]

"""The delivery outbox — every outbound human notification is a ROW, never a blocking
HTTP call inside the reasoning sweep.

Why this shape: the agent-webhook path does its POST synchronously inside the 6-hourly
cross-org thread, so one slow endpoint degrades every tenant's reasoning — the failure
that reads as "GeniOS is down". Human channels start correct instead: ENQUEUE (fast,
idempotent, deduped by (org, card, channel)) → DRAIN (claimed with FOR UPDATE SKIP
LOCKED, bounded backoff, terminal after the schedule ends) → every send lands a
card_events row, so delivered/failed is queryable state, not a log line.

Dispatch policy (mirrors the card pipeline's push law without touching it): HIGH and
CRITICAL band cards notify; STANDARD stays a dashboard rotation. The daily digest goes
once per org per UTC day under a synthetic card id — same dedup machinery, zero
special cases.

Admission (Layer 5.2) sits between the claim and the send. Enqueue *materialises* the
delivery object onto the row — recipient, band, channel class, interrupt — and `drain`
asks `deliver/gate.py` whether that delivery may travel *now*. It runs before the
authority re-validation because it is local and lock-free while that check holds `for
share` locks across an outbound POST, and it produces three outcomes rather than two:

  SEND      → the existing path, unchanged.
  DEFER     → move `next_attempt_at`, bump `defer_count`, touch NOTHING else. A hold is
              not a failure, and if it spent an `attempts` slot a message queued at 22:00
              would be `failed_terminal` by breakfast — the exact one somebody wanted.
  SUPPRESS  → status `suppressed`, distinct from `cancelled`. Cancelled means the subject
              stopped being live; suppressed means this person, or this tenant, said no.
              Collapsing them makes "why did nothing arrive?" unanswerable from the row."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.contracts.delivery import DeliveryVerdict
from genios_engine.contracts.execution import ChannelClass
from genios_engine.platform.logging import get_logger
from genios_engine.deliver.channels import get_channel
from genios_engine.deliver.channels.slack import format_card_message, format_digest_message
from genios_engine.deliver.executive_bridge import (
    enqueue_executive_messages,
    executive_delivery_is_live,
    is_executive_delivery,
    link_commitment_cards,
)
from genios_engine.deliver.gate import (
    PgDeliveryContext,
    admit,
    candidate_from_row,
    channel_class_for,
    defer_until,
)
from genios_engine.executive.communication import may_interrupt
from genios_engine.executive.execution import execution_config
from genios_engine.platform.ids import new_id
from genios_engine.reason.authority import (
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
)

# retry schedule (minutes after the Nth failure); after the last slot → failed_terminal.
BACKOFF_MINUTES: tuple[int, ...] = (5, 30, 120, 720)
NOTIFY_BANDS = ("high", "critical")

#: The row could not travel because this org has NOWHERE to send it — no adapter for the channel,
#: or no active `org_channels`/`agent_registry` row backing it. Deliberately its own status, and
#: deliberately NOT terminal.
#:
#: It used to be `failed_terminal` with `attempts=1`, and that single choice is what poisoned the
#: card permanently: both the enqueue dedupe (`not exists … ob.channel=:ch`) and the unique index
#: `delivery_outbox_once` ignore status, so once a row existed for (org, card, channel) no later
#: enqueue could ever produce another one. Registering a channel afterwards rescued nothing —
#: production's entire delivery history is 3 such rows, and all 3 stay dead for cards that are
#: otherwise still live.
#:
#: `failed_terminal` was also just wrong as a description. Nothing was attempted and nothing
#: failed: there was no transport to fail. A failure is a fact about the message; this is a fact
#: about the tenant's configuration, and it stops being true the moment they configure one —
#: which is exactly why `revive_undeliverable` can un-park it without guessing.
UNDELIVERABLE = "undeliverable"

#: The exact `last_error` the drain wrote before `UNDELIVERABLE` existed. Kept verbatim as the
#: healing key: it was only ever written by the no-transport branch, so matching on it repairs
#: rows burned by the old code without touching a row that genuinely failed in transport.
NO_TRANSPORT_ERROR = "channel unregistered or inactive"

_log = get_logger("genios.deliver.outbox")


def card_confidence_bp(score_block) -> int:
    """The reasoner's confidence in this card, in basis points.

    ``score_block.C`` is the 0..100 confidence percentage — the same number ``authority.py``
    projects out of ``confidence_bp`` and ``composer.py`` converts back with ``* 100``. Reusing
    that conversion rather than introducing a third shape is what keeps a card that Postgres
    calls authoritative from disagreeing with the interrupt rule about how sure the system is.

    A card with no recorded confidence returns 0, and 0 cannot clear any interrupt floor. That is
    the intended reading: an unmeasured conclusion is not a confident one, and the cost of being
    wrong here is somebody's sleep.
    """
    block = _as_dict(score_block)
    if not block:
        return 0
    try:
        return int(round(float(block.get("C", 0)))) * 100
    except (TypeError, ValueError):
        return 0


def _as_dict(value) -> dict:
    """A jsonb column as a dict, whatever the driver handed back. Never raises."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def communication_config(effective_config) -> dict:
    """The tenant's own interrupt settings, from the config snapshot the card scored under.

    Not the *current* pack config — the snapshot this specific card was authorised by, which the
    authority join already carries. That matters: a tenant who tightens `interrupt_band` while a
    card is queued should not have the old card re-judged by the new rule, because the card's
    band was cut by the old one. Reading both from the same snapshot is what keeps the two ends
    of the comparison talking about the same configuration.

    Empty when a pack has not opted into tuning, which every unit reads as "use the defaults".
    """
    return dict(execution_config(_as_dict(effective_config)).get("communication") or {})


def next_attempt_delay(attempts: int) -> int | None:
    """Pure: minutes until the next try after `attempts` failures; None = terminal."""
    if attempts < 1:
        return 0
    if attempts <= len(BACKOFF_MINUTES):
        return BACKOFF_MINUTES[attempts - 1]
    return None


def digest_card_id(day) -> str:
    """Synthetic card id for the daily digest → the (org, card, channel) unique index
    dedups it exactly like a real card."""
    return f"digest:{day.isoformat()}"


def _current_digest_payload(engine, org_id: str, evaluation_time: datetime) -> dict:
    """Build a non-actionable digest from current authority immediately before send."""
    from genios_engine.executive.summary import build_summary

    class _SummaryStore:
        pass

    store = _SummaryStore()
    store.engine = engine
    return format_digest_message(
        build_summary(store, org_id, "one_minute", eval_time=evaluation_time))


# ── channel resolution ────────────────────────────────────────────────────────────
def deliverable_channels(conn, org_id: str) -> list[str]:
    """The channels this org can ACTUALLY be pushed on, right now.

    Two conditions, and every historical delivery failure in this database is one of them
    being assumed rather than checked:

      1. the tenant registered it (`org_channels`, active), and
      2. we have a transport for it (`channels/base.get_channel` returns an adapter).

    Both halves are load-bearing. Measured on production 2026-08-29: `delivery_outbox` held 3
    rows across its entire history, all `channel='slack'`, all `failed_terminal`, all
    `last_error='channel unregistered or inactive'`, attempts=1 — killed on first look because
    the enqueue paths named 'slack' as a Python default while `org_channels` contained exactly
    two rows, both `in_app`, and never a slack row in either org. Checking condition 1 alone
    would not have helped: `get_channel('in_app')` is None, so an in_app row fails the drain's
    adapter check identically. `in_app` is the PULL surface (`routing.PULL_SURFACE`) — the card
    is already sitting on it, there is nothing to send, and enqueueing one manufactures a
    `failed_terminal` row per card and reports it as delivery work.

    Agent transports are excluded on top of both, and that exclusion is not a detail:
    `routing.AGENT_TRANSPORTS` ('agent_push', 'api') carry MACHINE deliveries, which are
    enqueued by `enqueue_agent_push` with an `agent_id` recipient and resolved by the drain
    against `agent_registry`, not `org_channels`. Routing law 1 says a human delivery may never
    ride an agent transport, and the mechanical consequence here is precise: handing 'agent_push'
    to `enqueue_pending` would write a card row whose recipient is a SEAT, the drain would look
    that seat up in `agent_registry`, find nothing, and write `failed_terminal` — the identical
    defect this function exists to remove, just reached by a different road.

    Empty list = this tenant has no push channel. That is a REAL, reportable condition and the
    caller must name it, not queue a message to a channel that does not exist.
    """
    from genios_engine.deliver.routing import AGENT_TRANSPORTS
    from genios_engine.deliver.units import _implemented_channels

    registered = [r[0] for r in conn.execute(text(
        "select channel from org_channels where org_id=:o and active order by channel"),
        {"o": org_id})]
    deliverable = _implemented_channels() - AGENT_TRANSPORTS
    return [ch for ch in registered if ch in deliverable]


def connected_executors(conn, org_id: str) -> list[str]:
    """The agent executors this org can hand work to right now — the OTHER push lane.

    Resolved from `agent_registry`, never from `org_channels`, because an executor is not a
    surface a tenant configures for themselves: it is a machine that registered a webhook and a
    scope. That separation is routing law 1 and law 2 in table form — a human delivery may never
    ride an agent transport, and an agent may ride only one — and it is why
    `deliverable_channels` subtracts `AGENT_TRANSPORTS` instead of ever returning 'agent_push'.

    The predicate matches `push.py::_active_agent_webhooks` deliberately, clause for clause:

      * `status='active'`   — 0017 added the column `not null default 'active'`, so it is set on
                              every row including the ones 0002 created.
      * `signals.read`      — the payload the drain builds for an agent row is the /v1/signals
                              projection (`push._card_projection`), so pushing it to an agent
                              without that grant would hand a machine, unasked, exactly the data
                              its scope says it may not poll. The enqueue used to skip this check
                              while the poll endpoint enforced it, which made the push path the
                              looser of the two on the same bytes.
      * `webhook_url <> ''` — `channels/agent.py` returns False on an empty url, so an agent
                              registered without one would burn all four retry slots and land in
                              `failed_terminal` for a message that never had anywhere to go.
                              `is not null` alone let the empty string through.
    """
    return [r[0] for r in conn.execute(text(
        "select agent_id from agent_registry "
        "where org_id=:o and coalesce(status,'active')='active' "
        "and 'signals.read'=any(coalesce(allowed_actions, array[]::text[])) "
        "and webhook_url is not null and webhook_url <> '' "
        "order by agent_id"), {"o": org_id})]


def revive_undeliverable(conn, org_id: str, channel: str, *,
                         now: datetime | None = None) -> int:
    """Re-open every row this org parked only because it had nowhere to send it. Returns the count.

    This is the answer to "a card must become deliverable the moment a channel exists". The
    alternative designs were considered and rejected:

      * *A status-aware dedupe* would let a SECOND row be inserted for the same (org, card,
        channel) — except `delivery_outbox_once` is a unique index that does not read status, so
        the insert would simply be swallowed by `on conflict do nothing` and nothing would
        change. Making the index status-aware instead would mean one card could accumulate a row
        per failed attempt-generation, and the audit trail stops being "one row per logical
        delivery" — the property `delivery_id` and the whole L7 fact feed depend on.
      * *Re-enqueueing from scratch* throws away the row's history: when it was first decided,
        what its authority stamps were, what it was deferred for. The delivery is the same
        delivery; only the world around it changed.

    So the row is REVIVED in place. It keeps its identity, its authority stamps and its audit
    trail, and it re-enters the queue with a clean ladder because none of its slots were ever
    spent on a real attempt.

    Two shapes are healed. `UNDELIVERABLE` is what the drain writes now. The `failed_terminal`
    clause repairs rows burned by the code this replaces — that exact `last_error` string was
    written by one branch and one branch only, so it cannot match a row that failed in transport.

    Reviving a stale card is SAFE, and that is not an accident of ordering: the drain re-proves
    graph/pack/card authority immediately before every send, so a revived row whose card has since
    expired or been revoked is `cancelled` on its way out rather than delivered. Waking an old
    message and letting the authority check kill it is strictly better than leaving it dead,
    because the second option cannot tell "we chose not to send" from "we lost it".
    """
    moment = now or datetime.now(timezone.utc)
    return conn.execute(text(
        "update delivery_outbox set status='queued', next_attempt_at=:now, attempts=0, "
        "last_error=null "
        "where org_id=:o and channel=:ch "
        "and (status=:parked or (status='failed_terminal' and last_error=:legacy))"),
        {"o": org_id, "ch": channel, "now": moment,
         "parked": UNDELIVERABLE, "legacy": NO_TRANSPORT_ERROR}).rowcount


def card_backlog_counts(conn, org_id: str, now: datetime) -> tuple[int, int]:
    """(band_starved, unrouted) for this org's live cards — diagnostics, not delivery.

    Extracted from `enqueue_pending` so the sweep can report them for an org with NO channel
    too. Previously they were only ever computed as a side effect of enqueueing, so the one
    tenant whose delivery is completely unconfigured — the tenant these numbers are actually
    about — produced neither. They are also per-ORG, not per-channel: computing them inside a
    per-channel loop would multiply the same backlog by the number of channels.
    """
    starved = conn.execute(text(
        "select count(*) from cards k "
        "where k.org_id=:o and k.state in ('queued','surfaced') and k.expires_at>:now "
        "and k.urgency_band not in ('high','critical')"),
        {"o": org_id, "now": now}).scalar() or 0
    unrouted = conn.execute(text(
        "select count(*) from cards k "
        "where k.org_id=:o and k.state in ('queued','surfaced') and k.expires_at>:now "
        "and k.assignee is null"),
        {"o": org_id, "now": now}).scalar() or 0
    return int(starved), int(unrouted)


def commitment_backlog_counts(conn, org_id: str) -> tuple[int, int]:
    """(open commitments, of which nobody can be reached about) — diagnostics, not delivery.

    The card counts above answer "how much intelligence is sitting unsent". They cannot answer
    "how much WORK is sitting untracked-by-anyone", and that is the number that was invisible
    while Layer 5 was silent: on 2026-08-30 this org had 167 commitments `pending`, every one of
    them unreachable, and every pass of every sweep reported a clean zero.

    `assignee is null` is the honest test for the second number now that the column holds the
    RECIPIENT rather than the owner: a null there means no owner AND no admin to triage it, so
    the commitment cannot be nudged, escalated or delivered by any path at all.
    """
    row = conn.execute(text(
        "select count(*) as open_now, count(*) filter (where assignee is null) as unreachable "
        "from executions where org_id=:o and closed_at is null"), {"o": org_id}).first()
    return (int(row.open_now or 0), int(row.unreachable or 0)) if row else (0, 0)


# ── enqueue ───────────────────────────────────────────────────────────────────────
#
#: The FROM + WHERE that decides whether a card may be PUSHED at all, shared VERBATIM by both
#: push lanes. Binds ``:o`` and ``:authority_time``; the caller appends its own select list, its
#: own dedupe clause and its own locking.
#:
#: Extracted rather than retyped, because "the agent lane got a looser gate than the human lane"
#: is the specific way this wiring goes wrong, and it goes wrong SILENTLY: the human lane's
#: filter is nine joins and a 40-clause authority predicate, so a second copy that drops one
#: clause still returns plausible cards. It would show up as an external machine being handed a
#: card no person was allowed to see — a card whose pack was paused, whose decision was
#: superseded, or which expired — and the only visible symptom would be that the agent got MORE
#: than the dashboard. One string means the two lanes cannot disagree about what "pushable"
#: means, even by accident.
PUSHABLE_CARDS_SQL = (
    "from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id " +
    AUTHORITATIVE_SIGNAL_JOINS +
    "where k.org_id=:o and k.state in ('queued','surfaced') "
    "and s.status='open' and k.expires_at>:authority_time and " +
    AUTHORITATIVE_SIGNAL_PREDICATE + " "
    "and k.urgency_band in ('high','critical') "
)
#
# `channel` is REQUIRED on every enqueue path below, and deliberately has no default.
#
# It used to default to the string "slack" in all three (here, `enqueue_digest`, and
# `executive_bridge.enqueue_executive_messages`), and `run_distribution` called all three
# without ever passing one. So every proactive message this product has ever produced was
# addressed to a channel chosen by a Python default rather than by the tenant — and the drain
# terminated each on sight. A default is the wrong shape for this argument: there is no channel
# that is right when the caller has not looked, so the type system should make not-looking
# impossible. Callers resolve it with `deliverable_channels` first.
def enqueue_pending(engine, org_id: str, channel: str,
                    base_url: str = "") -> dict:
    """Queue un-notified HIGH/CRITICAL cards for this org's channel. Idempotent: the
    unique index makes a re-run a no-op. Payload is built from card columns that
    already passed the render validators — the channel adds no words.

    The delivery object is stamped here rather than at send time so a retry three hours later
    judges the *same* delivery it queued, and so the drain needs no extra joins to know whose
    attention a row is about to spend.

    Returns ``{"queued": n, "band_starved": n, "unrouted": n}``. The last two used to be silence.
    Every live card sits at ``urgency_band='standard'`` (scores 42-60 against thresholds of
    70/85), so the band filter below excludes ALL of them and this function returned 0 — which is
    indistinguishable from "there was nothing to send". A tenant where no card has ever cleared
    the push band is a broken scoring pipeline, not a quiet week, and the two have to be
    tellable apart from the sweep's own output."""
    from genios_engine.deliver.routing import AGENT_TRANSPORTS
    if channel in AGENT_TRANSPORTS:
        # Routing law 1, as an executable statement at the write boundary rather than a sentence
        # in routing.py's docstring. Every row this function writes carries a SEAT as recipient;
        # the drain resolves an agent-class row's config from `agent_registry` by recipient, so a
        # seat id would find no agent and the row would die as `failed_terminal`. Raising here
        # names the mistake at the caller instead of leaving a dead row to explain it later.
        raise ValueError(
            f"{channel!r} is an agent transport; a human card delivery may never ride one "
            "(routing law 1) — agent deliveries go through enqueue_agent_push")
    queued = 0
    now = datetime.now(timezone.utc)
    channel_class = channel_class_for(channel).value
    with engine.begin() as c:
        c.execute(text("select graph_version from graph_versions where org_id=:o for share"),
                  {"o": org_id})
        rows = c.execute(text(
            "select k.card_id,k.signal_id,k.headline,k.situation,k.urgency_band,"
            "k.assignee,k.score_block,authority_cfg.effective as effective_config," +
            AUTHORITATIVE_SCORE_SQL + " as score,s.reasoning_run_id,"
            "s.reasoning_decision_hash,s.authority_pack_revision,s.authority_expires_at " +
            PUSHABLE_CARDS_SQL +
            "and not exists (select 1 from delivery_outbox ob where ob.org_id=k.org_id "
            "and ob.card_id=k.card_id and ob.channel=:ch) "
            "for share of k,s,rr,ro,selected_rc,rcap,authority_ctx,authority_cfg,authority_pack"),
            {"o": org_id, "ch": channel, "authority_time": now}).fetchall()
        for r in rows:
            payload = format_card_message(dict(r._mapping), base_url=base_url)
            # A card is pushed to chat *because* it cleared the push band, so this path never
            # builds a CommunicationPlan — but it still has to say whether the card may break
            # through quiet hours. Asking Layer 5's own predicate, with the tenant's own config
            # snapshot, is what makes `interrupt_band` and `interrupt_min_confidence_bp` one
            # dial rather than two: a tenant who says "too noisy" turns it down once, and both
            # their commitments and their cards go quiet together.
            interrupt = may_interrupt(r.urgency_band, card_confidence_bp(r.score_block),
                                      communication_config(r.effective_config))
            row_id = new_id("ob")
            res = c.execute(text(
                "insert into delivery_outbox (id,org_id,card_id,channel,payload,signal_id,"
                "reasoning_run_id,reasoning_decision_hash,authority_pack_revision,"
                "authority_expires_at,recipient,band,channel_class,interrupt,delivery_id) "
                "values (:i,:o,:c,:ch,cast(:payload as jsonb),"
                ":signal,:run,:decision,:revision,:expires,:seat,:band,:cclass,:interrupt,:i) "
                # matches delivery_outbox_once exactly — recipient joined the key so one card
            # can fan out to several agents without the second row silently deduping away
            "on conflict (org_id, card_id, channel, coalesce(recipient, '')) do nothing"),
                {"i": row_id, "o": org_id, "c": r.card_id, "ch": channel,
                 "payload": json.dumps(payload), "signal": r.signal_id,
                 "run": r.reasoning_run_id, "decision": r.reasoning_decision_hash,
                 "revision": r.authority_pack_revision, "expires": r.authority_expires_at,
                 # An unrouted card has no seat, so it is an org surface and the tenant's own
                 # quiet hours govern it — exactly what the '*' preference row is for.
                 "seat": r.assignee, "band": r.urgency_band, "cclass": channel_class,
                 "interrupt": interrupt})
            queued += res.rowcount

        # What the band filter above threw away. The owning defect is upstream (L4's ranking
        # formula never executes, so `I` is 5000 on every card and nothing reaches 70), but a
        # layer that silently discards its entire input is how an upstream defect stays invisible
        # for months — every L6 metric had an empty denominator and read as "no problem".
        # A card with no assignee has no authorized recipient, so audience and visibility rules
        # cannot even be evaluated for it. Counted rather than absorbed.
        starved, unrouted = card_backlog_counts(c, org_id, now)
    return {"queued": queued, "band_starved": starved, "unrouted": unrouted}


def enqueue_agent_push(engine, org_id: str, card_id: str) -> int:
    """Queue one agent-class delivery per active webhook agent — the outbox replaces the inline
    POST `deliver/push.py` used to fire from inside the card build.

    That inline call was the exact anti-pattern this module's own docstring names as its reason
    to exist: a slow client endpoint degraded the card build for the whole org, and the send
    appeared in no outbox, no retry schedule, no dead letter and no analytics. As a row it gets
    the same lifecycle a human delivery has, and the drain's authority recheck replaces push.py's
    hand-rolled pre-send projection comparison.

    One row PER AGENT (recipient = agent_id) — which is why migration 0068 put recipient into
    the outbox dedup key. AGENT channel class: never intrusive, so the timing unit passes it at
    any hour; policy still applies, so a tenant on hold pushes nothing to its agents either.
    Payload carries only the card reference — the projection is built at SEND time by the drain,
    so a card revoked between enqueue and send is never serialized to an external machine.
    """
    queued = 0
    with engine.begin() as c:
        # `connected_executors`, not a second hand-written predicate. The one this replaced was
        # `status='active' and webhook_url is not null`, which is looser than the registry
        # predicate every other agent surface uses, in two ways that both end badly:
        #
        #   * it never checked `signals.read`, while `deliver/agent_api.py` enforces it on the
        #     POLL of the identical bytes (`push._card_projection` IS the /v1/signals
        #     projection). So the push path handed a machine, unasked, exactly the data its
        #     scope says it may not fetch — the push being the looser of the two on the same
        #     payload is the whole reason scopes stop meaning anything.
        #   * `is not null` admits the empty string, and `channels/agent.py` returns False on an
        #     empty url — so an agent registered without one burned all four retry slots and
        #     landed in `failed_terminal` for a message that never had anywhere to go.
        agents = connected_executors(c, org_id)
        if not agents:
            return 0
        card = c.execute(text(
            "select signal_id from cards where card_id=:c and org_id=:o"),
            {"c": card_id, "o": org_id}).first()
        for agent_id in agents:
            row_id = new_id("ob")
            res = c.execute(text(
                "insert into delivery_outbox (id, org_id, card_id, channel, payload, "
                "signal_id, recipient, channel_class, interrupt, delivery_id) "
                "values (:i, :o, :c, 'agent_push', cast(:p as jsonb), :sig, :agent, "
                ":cclass, false, :i) "
                "on conflict (org_id, card_id, channel, coalesce(recipient, '')) do nothing"),
                {"i": row_id, "o": org_id, "c": card_id,
                 "p": json.dumps({"kind": "agent_card_push", "card_id": card_id}),
                 "sig": card.signal_id if card else None, "agent": agent_id,
                 "cclass": ChannelClass.AGENT.value})
            queued += res.rowcount
    return queued


def enqueue_agent_lane(engine, org_id: str, *, agents: list[str],
                       eval_time: datetime | None = None) -> dict:
    """The agent lane's own pass over this org's pushable cards. Returns ``{"queued", "cards"}``.

    This exists because the agent lane CANNOT be a rung inside the sweep's
    ``for channel in channels:`` loop, and that is a law rather than a preference:
    ``deliverable_channels`` subtracts ``routing.AGENT_TRANSPORTS`` deliberately (law 1 — a human
    delivery may never ride an agent transport), so an executor is invisible to channel
    resolution by construction. Resolution for this lane comes from ``agent_registry``, which is
    a different table describing a different kind of recipient: a machine that registered a
    webhook and a scope, not a surface a tenant configured for a person.

    ``agents`` is passed in, never defaulted and never resolved here, for exactly the reason the
    block comment above ``enqueue_pending`` gives for ``channel``: the caller has to have LOOKED.
    The caller also needs the same answer to decide whether this org is reachable at all, and two
    independent resolutions of "who can we reach" is how the sweep would come to report a state
    it is not acting on.

    The eligibility filter is ``PUSHABLE_CARDS_SQL`` — the human lane's, verbatim, not a copy.
    Everything the dashboard's push respects therefore holds here too: the nine authority joins,
    ``status='open'``, unexpired, and the high/critical band. The consequence worth stating
    plainly is the one that matters most: a card the human lane suppresses is not smuggled to a
    machine through the side door. That leaves the lane strictly NARROWER than
    ``pipeline.py``'s build-time ``enqueue_agent_push``, which pushes every card it builds at any
    band — so wiring this in cannot widen what any existing agent receives.

    Fan-out already-done cards are skipped in Python rather than in SQL: the unique index makes
    ``enqueue_agent_push`` idempotent anyway, so this is only about not opening one transaction
    per card per tick forever. Steady state after the first pass is zero transactions, and the
    check is per (card, agent) so an agent registered LATER still receives the cards that were
    already live when it arrived.
    """
    now = eval_time or datetime.now(timezone.utc)
    if not agents:
        return {"queued": 0, "cards": 0}
    with engine.connect() as c:
        # No `for share` here, unlike `enqueue_pending`. This read is followed by one write
        # transaction PER CARD, so holding the graph and pack rows across the loop would block
        # every reasoning write for the length of it — and it would buy nothing, because the
        # drain re-proves authority (`push._card_projection`) immediately before the POST and
        # cancels the row if it has lapsed. The enqueue is an intent, not a promise to send.
        eligible = [r[0] for r in c.execute(
            text("select k.card_id " + PUSHABLE_CARDS_SQL + "order by k.card_id"),
            {"o": org_id, "authority_time": now})]
        if not eligible:
            return {"queued": 0, "cards": 0}
        covered = {(r[0], r[1]) for r in c.execute(text(
            "select card_id, recipient from delivery_outbox "
            "where org_id=:o and channel='agent_push'"), {"o": org_id})}
    todo = [card_id for card_id in eligible
            if any((card_id, agent_id) not in covered for agent_id in agents)]
    queued = 0
    for card_id in todo:
        queued += enqueue_agent_push(engine, org_id, card_id)
    return {"queued": queued, "cards": len(todo)}


def enqueue_digest(engine, org_id: str, channel: str,
                   eval_time: datetime | None = None) -> int:
    """Claim one daily digest slot.

    The row is only a delivery intent.  Its authority-sensitive content is regenerated from the
    current executive projection in ``drain`` so a queued digest can never send yesterday's
    revoked recommendation after a graph/config/pack change.

    ``channel`` is required (see the block comment above ``enqueue_pending``). The existence
    check below reads ``org_channels`` for this exact channel, so the old "slack" default made
    this function's FIRST statement return 0 for every org on every tick: production's
    ``last_digest_date`` is NULL for both orgs across all of history and no ``digest:`` row has
    ever been written. The digest never failed — it never ran.

    ``last_digest_date`` lives on the ``org_channels`` ROW, so the once-per-day marker is
    per-(org, channel) and a tenant with two push channels gets one digest on each rather than
    the second silently suppressing the first.
    """
    now = eval_time or datetime.now(timezone.utc)
    today = now.date()
    payload = {"kind": "daily_digest_intent", "for_date": today.isoformat()}
    with engine.begin() as c:
        row = c.execute(text(
            "select last_digest_date from org_channels "
            "where org_id=:o and channel=:ch and active for update"),
            {"o": org_id, "ch": channel}).first()
        if row is None or (row.last_digest_date is not None
                           and row.last_digest_date >= today):
            return 0
        c.execute(text("update org_channels set last_digest_date=:d, updated_at=now() "
                       "where org_id=:o and channel=:ch"),
                  {"d": today, "o": org_id, "ch": channel})
        # A digest is a batch somebody chose to read, not an interruption: it carries the DIGEST
        # class so the timing unit lets it through at any hour, and no recipient because the
        # whole team reads it. Policy still applies — a tenant on hold gets no digest either.
        row_id = new_id("ob")
        # `delivery_id` was written by exactly ONE function in the whole codebase —
        # `deliver/spine.py::materialize`, which has no production caller — so
        # `feedback/delivery_facts.py`'s `where delivery_id is not null` predicate excluded
        # every row either live enqueue path (this one and the one above) has ever written. A
        # fully working legacy delivery path still fed L7 zero DeliveryFacts, forever. The row's
        # own id already IS a unique logical-delivery identity for this path, so it doubles as
        # `delivery_id` rather than inventing a second one.
        res = c.execute(text(
            "insert into delivery_outbox "
            "(id, org_id, card_id, channel, payload, channel_class, delivery_id) "
            "values (:i, :o, :c, :ch, cast(:p as jsonb), :cclass, :i) "
            # matches delivery_outbox_once exactly — recipient joined the key so one card
            # can fan out to several agents without the second row silently deduping away
            "on conflict (org_id, card_id, channel, coalesce(recipient, '')) do nothing"),
            {"i": row_id, "o": org_id, "c": digest_card_id(today), "ch": channel,
             "p": json.dumps(payload), "cclass": ChannelClass.DIGEST.value})
        return res.rowcount


# ── drain ─────────────────────────────────────────────────────────────────────────
def drain(engine, *, eval_time: datetime | None = None, limit: int = 50) -> dict:
    """Deliver due rows. Claim with FOR UPDATE SKIP LOCKED (two instances never send
    the same message), send OUTSIDE row-lock scope per row, record the outcome, and
    write a card_events audit row for real cards."""
    now = eval_time or datetime.now(timezone.utc)
    out = {"delivered": 0, "retried": 0, "terminal": 0, "cancelled": 0,
           # `parked` is what used to be counted as `terminal`. A row with nowhere to go was
           # never an attempt and never a failure, and calling it one burned the card forever
           # (see UNDELIVERABLE). It is reported separately so "3 terminal failures" stops
           # meaning "3 tenants never registered a channel".
           "deferred": 0, "suppressed": 0, "parked": 0}

    with engine.begin() as c:
        due = c.execute(text(
            "select id,org_id,card_id,channel,payload,attempts,signal_id,reasoning_run_id,"
            "reasoning_decision_hash,authority_pack_revision,authority_expires_at,"
            "recipient,band,channel_class,interrupt,defer_count,delivery_id "
            "from delivery_outbox "
            # `dedupe_key` is set by exactly one writer — `spine.materialize` — and this legacy
            # drain and `spine.claim_due` were not mechanically disjoint: neither excluded rows
            # the OTHER path could also claim. Risk was zero only because the v2 path has never
            # written a row yet; the moment it does, both workers could select the same one and
            # double-send. `dedupe_key is null` is true of every row this drain's own two writers
            # produce and false of everything `materialize` produces, so it costs no new column.
            "where status='queued' and next_attempt_at <= :now and dedupe_key is null "
            "order by next_attempt_at asc limit :l for update skip locked"),
            {"now": now, "l": max(1, min(int(limit), 200))}).fetchall()
        claimed = [dict(r._mapping) for r in due]
        # mark in-flight rows' next_attempt into the future so a crashed drain retries
        # them on schedule instead of double-sending on the very next tick
        for r in claimed:
            c.execute(text("update delivery_outbox set next_attempt_at=:na where id=:i"),
                      {"na": now + timedelta(minutes=5), "i": r["id"]})

    # One resolver for the whole pass: a tenant's quiet hours are read once, and — the part that
    # matters — the burst counter carries this pass's own sends forward. Ten intrusive messages
    # coming due together against a limit of three must send three and hold seven; a per-row
    # resolver would read "0 delivered this hour" ten times and let every one of them through.
    gate_conn = engine.connect()
    gate = PgDeliveryContext(gate_conn)
    try:
        _drain_claimed(engine, claimed, gate, now, out)
    finally:
        gate_conn.close()
    return out


def _drain_claimed(engine, claimed: list[dict], gate: PgDeliveryContext, now: datetime,
                   out: dict) -> None:
    configs: dict[tuple[str, str], dict | None] = {}
    with engine.connect() as c:
        for r in claimed:
            key = (r["org_id"], r["channel"])
            if key not in configs:
                row = c.execute(text(
                    "select config from org_channels where org_id=:o and channel=:ch "
                    "and active"), {"o": key[0], "ch": key[1]}).first()
                cfg = row.config if row else None
                configs[key] = (cfg if isinstance(cfg, dict)
                                else json.loads(cfg) if cfg else None)

    for r in claimed:
        payload = r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"])
        if r["channel_class"] == ChannelClass.AGENT.value:
            # An agent delivery's "config" is its agent_registry row, keyed by recipient —
            # org_channels describes human surfaces a tenant configures, and an agent is neither.
            with engine.connect() as agent_conn:
                agent_row = agent_conn.execute(text(
                    "select agent_id, webhook_url, webhook_secret from agent_registry "
                    "where org_id=:o and agent_id=:a and status='active'"),
                    {"o": r["org_id"], "a": r["recipient"]}).mappings().first()
            cfg = dict(agent_row) if agent_row else None
        else:
            cfg = configs.get((r["org_id"], r["channel"]))
        ch = get_channel(r["channel"])
        if ch is None or cfg is None:
            # PARKED, not failed. Nothing was attempted, so nothing failed — there was no
            # transport to fail on. `_finish(terminal=True)` here is what wrote production's
            # entire delivery history (3 rows, all `failed_terminal`, all attempts=1, all
            # `last_error='channel unregistered or inactive'`) and, because both the enqueue
            # dedupe and `delivery_outbox_once` ignore status, permanently burned those cards:
            # registering a channel afterwards could never produce a second row for them.
            #
            # The two ways to get here are both facts about CONFIGURATION, and both stop being
            # true the moment the tenant fixes them, which is exactly why the row must stay
            # revivable: `ch is None` = we ship no adapter for this channel (our gap),
            # `cfg is None` = the backing `org_channels`/`agent_registry` row was deactivated or
            # removed between enqueue and drain (theirs).
            _park(engine, r, now,
                  detail=("no adapter for this channel" if ch is None
                          else NO_TRANSPORT_ERROR),
                  out=out)
            continue

        # ── Layer 5.2 admission ──────────────────────────────────────────────────────
        # Before the authority check, which is the expensive one: it takes `for share` locks on
        # the graph and holds them across an outbound POST. Discovering that the recipient is
        # asleep is a local question, and asking it first means a held message costs one cheap
        # read instead of a lock-held round trip.
        candidate = candidate_from_row(r)
        try:
            decision, context = admit(candidate, gate, now=now)
        except Exception as exc:      # noqa: BLE001 — see below; never send un-judged
            # A gate that cannot read must not decide by accident. Sending anyway would page
            # somebody at 03:00 on the strength of a failed query; dropping the row would lose
            # a message because a lookup blipped. So it takes the existing bounded retry ladder:
            # the message survives, nothing goes out un-judged, and a gate that stays broken
            # ends as `failed_terminal` with the reason in the row rather than silently.
            # Caught per row so one tenant's bad state cannot stop the whole pass draining.
            delay = next_attempt_delay(r["attempts"] + 1)
            _finish(engine, r, now, ok=False, detail=f"delivery gate unavailable: {exc}"[:300],
                    terminal=delay is None, out=out, delay_minutes=delay)
            continue
        if decision.verdict is DeliveryVerdict.SUPPRESS:
            _suppress(engine, r, decision, context, out)
            continue
        if decision.verdict is DeliveryVerdict.DEFER:
            _defer(engine, r, decision, context, now, out)
            continue

        if is_executive_delivery(r["card_id"]):
            # A Layer 5 commitment message. Same law as a card — prove the subject is still live
            # *now*, not merely that it was when queued. A reminder can sit through a retry
            # backoff, and the customer can reply inside that window: sending it then is the
            # exact nudge the whole executive layer exists to never send.
            with engine.begin() as authority_conn:
                live = executive_delivery_is_live(authority_conn, r["org_id"], r["card_id"],
                                                  now=now)
                res = ch.send(payload, cfg) if live else None
            if res is None:
                _cancel(engine, r, "commitment closed before delivery", out)
                continue
        elif r["channel_class"] == ChannelClass.AGENT.value:
            # The row carries only the card reference; the projection is built NOW, under the
            # same authority the human path proves, so a card revoked between enqueue and send
            # is cancelled instead of serialized to an external machine. Replaces push.py's
            # hand-rolled pre-send projection comparison with the drain's own recheck.
            from genios_engine.deliver.push import _card_projection
            with engine.begin() as authority_conn:
                proj = _card_projection(authority_conn, r["org_id"], r["card_id"])
                res = (ch.send({"type": "signal.created", "org_id": r["org_id"],
                                "signal": proj}, cfg)
                       if proj is not None else None)
            if res is None:
                _cancel(engine, r, "card no longer authoritative", out)
                continue
        elif not str(r["card_id"]).startswith("digest:"):
            # Hold the same graph/pack/card authority locks through the outbound POST. This is a
            # deliberately short human notification call; safety wins over sending a revoked card.
            with engine.begin() as authority_conn:
                authority_conn.execute(text(
                    "select graph_version from graph_versions where org_id=:o for share"),
                    {"o": r["org_id"]})
                live = authority_conn.execute(text(
                    "select 1 from cards k join signals s "
                    "on s.signal_id=k.signal_id and s.org_id=k.org_id " +
                    AUTHORITATIVE_SIGNAL_JOINS +
                    "where k.org_id=:o and k.card_id=:card and k.signal_id=:signal "
                    "and s.reasoning_run_id=:run and s.reasoning_decision_hash=:decision "
                    "and s.authority_pack_revision=:revision and s.status='open' "
                    "and k.state in ('queued','surfaced') and k.expires_at>:authority_time "
                    "and " + AUTHORITATIVE_SIGNAL_PREDICATE +
                    " for share of k,s,rr,ro,selected_rc,rcap,authority_ctx,authority_cfg,"
                    "authority_pack"),
                    {"o": r["org_id"], "card": r["card_id"], "signal": r["signal_id"],
                     "run": r["reasoning_run_id"], "decision": r["reasoning_decision_hash"],
                     "revision": r["authority_pack_revision"], "authority_time": now}).first()
                if live is None:
                    res = None
                else:
                    res = ch.send(payload, cfg)
            if res is None:
                _cancel(engine, r, "decision authority revoked before delivery", out)
                continue
        else:
            try:
                payload = _current_digest_payload(engine, r["org_id"], now)
            except Exception as exc:  # noqa: BLE001 - never send stale fallback bytes
                delay = next_attempt_delay(r["attempts"] + 1)
                _finish(engine, r, now, ok=False,
                        detail=f"current digest projection unavailable: {exc}"[:300],
                        terminal=delay is None, out=out, delay_minutes=delay)
                continue
            res = ch.send(payload, cfg)
        if res.ok:
            _finish(engine, r, now, ok=True, detail="", terminal=False, out=out,
                    decision=decision)
            # `_finish` commits before the next candidate resolves. The gate deliberately
            # re-reads the burst count in a fresh transaction, so this row is visible exactly
            # once to the next decision.
        else:
            delay = next_attempt_delay(r["attempts"] + 1)
            _finish(engine, r, now, ok=False, detail=res.detail,
                    terminal=delay is None, out=out, delay_minutes=delay)


def _mark_lifecycle(c, row: dict, lifecycle: str, kind: str, now: datetime,
                    detail: dict | None = None) -> None:
    """The one canonical lifecycle writer for the legacy drain — column + event row together.

    Every terminal writer here used to update `status` alone: `lifecycle` stayed 'queued' on a
    row whose Slack message had already been delivered or terminally failed, so an operator
    asking "what failed?" through the delivery APIs (which read `lifecycle`, the public
    vocabulary) got an empty answer while transport calls were demonstrably happening, and
    analytics reported `by_status: {queued: N}` for delivered rows. Same job
    `spine.log_delivery_event` does for the v2 claimer — one vocabulary, whichever path sent.

    Called inside the writer's own transaction so the column and the event row cannot disagree.
    The event needs a `delivery_id`; rows enqueued before L6-05 stamped one get the column
    update only, which still fixes what the APIs read.
    """
    c.execute(text("update delivery_outbox set lifecycle=:l where id=:i"),
              {"l": lifecycle, "i": row["id"]})
    if row.get("delivery_id"):
        from genios_engine.deliver.spine import log_delivery_event
        log_delivery_event(c, org_id=row["org_id"], delivery_id=row["delivery_id"],
                           kind=kind, at=now, actor="legacy_drain", detail=detail)


def _defer(engine, row: dict, decision, context, now: datetime, out: dict) -> None:
    """Hold a message until its window opens — and spend nothing to do it.

    The single most important update statement in this layer. It moves the clock, counts the
    hold, and records why. It does **not** touch ``attempts``, and it does not write
    ``last_error``, because nothing failed. A quiet-hours hold that consumed a retry would spend
    the whole backoff ladder overnight and mark the message ``failed_terminal`` at 05:00 —
    turning the politeness feature into a delivery-loss bug.

    Staleness is deliberately not handled here either. A card that expires while held is caught
    by the authority re-validation the moment the window opens, which is the predicate that
    already owns expiry; a second age check here would be a second, weaker copy of it.
    """
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set next_attempt_at=:na, defer_count=defer_count+1, "
            "gate_unit=:u, gate_reason=:r where id=:i and status='queued'"),
            {"na": defer_until(decision, now), "u": decision.unit,
             "r": decision.reason_code, "i": row["id"]})
        _mark_lifecycle(c, row, "deferred", "deferred", now,
                        {"reason": decision.reason_code})
    out["deferred"] += 1


def _suppress(engine, row: dict, decision, context, out: dict) -> None:
    """Stop a message for good, and say who stopped it.

    Terminal, and distinct from both ``cancelled`` (the subject stopped being live) and
    ``failed_terminal`` (the transport gave up). Three different fixes, so three different
    statuses: an operator seeing ``suppressed`` should look at preferences, not at Slack's
    status page. The reason travels into ``last_error`` as well as ``gate_reason`` so the
    existing operator queries — which all read ``last_error`` — surface it without changing.
    """
    note = f"{decision.unit}:{decision.reason_code}"
    if context.config_error:
        note = f"{note} ({context.config_error})"
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set status='suppressed', gate_unit=:u, gate_reason=:r, "
            "last_error=:e where id=:i and status='queued'"),
            {"u": decision.unit, "r": decision.reason_code, "e": note[:300], "i": row["id"]})
        _mark_lifecycle(c, row, "suppressed", "suppressed",
                        datetime.now(timezone.utc), {"reason": decision.reason_code})
    out["suppressed"] += 1


def _cancel(engine, row: dict, detail: str, out: dict) -> None:
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set status='cancelled',attempts=attempts+1,last_error=:e "
            "where id=:i and status='queued'"),
            {"i": row["id"], "e": detail[:300]})
        _mark_lifecycle(c, row, "cancelled", "cancelled",
                        datetime.now(timezone.utc), {"detail": detail[:120]})
    out["cancelled"] += 1


def _park(engine, row: dict, now: datetime, *, detail: str, out: dict) -> None:
    """Park a row that had nowhere to go: `UNDELIVERABLE`, not a failure, and revivable.

    This function was CALLED and never defined — a `NameError` waiting in the drain's
    no-transport branch, and `drain()` runs outside `run_distribution`'s per-org `try`, so the
    first row to reach it would have taken down the whole sweep for every tenant rather than one.
    It became reachable the moment an executor could be deactivated between enqueue and drain.

    Attempts are deliberately NOT incremented. The retry ladder counts transport failures, and
    nothing was attempted here — burning a slot would march a correctly-configured tenant toward
    `failed_terminal` for the time they spent unconfigured. `next_attempt_at` is left alone for
    the same reason: `revive_undeliverable` sets it when the configuration actually changes, and
    a parked row must not wake itself on a timer to discover the same missing adapter.

    The status and `last_error` written here are exactly what `revive_undeliverable` selects on,
    which is what makes "a card becomes deliverable the moment a channel exists" true rather
    than aspirational.
    """
    with engine.begin() as c:
        c.execute(text(
            "update delivery_outbox set status=:parked, last_error=:e where id=:i"),
            {"parked": UNDELIVERABLE, "e": detail, "i": row["id"]})
        _mark_lifecycle(c, row, "undeliverable", "undeliverable", now,
                        detail={"reason": detail})
    out["undeliverable"] = out.get("undeliverable", 0) + 1


def _finish(engine, row: dict, now: datetime, *, ok: bool, detail: str, terminal: bool,
            out: dict, delay_minutes: int | None = None, decision=None) -> None:
    with engine.begin() as c:
        if ok:
            # The verdict that let this through is written on success too, not only on a hold.
            # Without it a row that was deferred overnight keeps the *stale* `quiet_hours`
            # reason after it finally sends, and — worse — a message that woke somebody at 02:00
            # cannot say why. `override_band_critical` in the row is the whole answer to "who
            # authorised this at 2am?", which is a question that does get asked.
            c.execute(text(
                "update delivery_outbox set status='delivered', delivered_at=:t, "
                "attempts=attempts+1, last_error=null, gate_unit=:u, gate_reason=:r "
                "where id=:i"),
                {"t": now, "i": row["id"],
                 "u": decision.unit if decision else None,
                 "r": decision.reason_code if decision else None})
            _mark_lifecycle(c, row, "delivered", "delivered", now)
            out["delivered"] += 1
            if not str(row["card_id"]).startswith("digest:") \
                    and not is_executive_delivery(row["card_id"]):
                c.execute(text(
                    "insert into card_events (id, org_id, card_id, kind, cause, detail) "
                    "values (:i, :o, :c, 'notification.sent', :ch, cast(:d as jsonb))"),
                    {"i": new_id("ce"), "o": row["org_id"], "c": row["card_id"],
                     "ch": row["channel"], "d": json.dumps({"outbox_id": row["id"]})})
        elif terminal:
            c.execute(text(
                "update delivery_outbox set status='failed_terminal', attempts=attempts+1, "
                "last_error=:e where id=:i"), {"e": detail[:300], "i": row["id"]})
            # `failed`, not `failed_terminal`: lifecycle is the PUBLIC vocabulary (the enum the
            # APIs and analytics read), and it names one failure terminal. The transport-status
            # column keeps its own word; the two columns answer different questions.
            _mark_lifecycle(c, row, "failed", "failed", now, {"error": detail[:120]})
            out["terminal"] += 1
        else:
            c.execute(text(
                "update delivery_outbox set attempts=attempts+1, last_error=:e, "
                "next_attempt_at=:na where id=:i"),
                {"e": detail[:300], "na": now + timedelta(minutes=delay_minutes or 5),
                 "i": row["id"]})
            out["retried"] += 1


def shadow_resolve_v2(engine, org_id: str, *, now: datetime) -> dict:
    """Run the v2 control plane's RESOLUTION over this org's live cards — measure, send nothing.

    Ten of the layer's 28 modules (orchestrator, audience, presence, routing, scheduler, spine…)
    had zero production reach: ~700 lines of Atlas-shaped machinery proven by tests and exercised
    by nothing. A cutover decided from that state is a leap; this pass is the measurement that
    makes it a step. `orchestrator.resolve` is PURE — no row is written, no channel touched — so
    the ten modules execute against real cards, real seats and real channel config, and the sweep
    reports how the v2 path WOULD have routed: per-channel counts and per-reason unroutables,
    directly comparable with what the legacy enqueue actually did in the same tick.

    Per-org failures isolate into a count: a shadow must never be able to break the live sweep
    it is shadowing.
    """
    from genios_engine.contracts.execution import AudienceClass
    from genios_engine.deliver.orchestrator import Unroutable, resolve
    from genios_engine.executive.assignment import PgSeatDirectory

    counts: dict = {"resolved": 0, "by_channel": {}, "unroutable": {}, "errors": 0}
    with engine.connect() as c:
        channels = [r[0] for r in c.execute(text(
            "select channel from org_channels where org_id=:o and active"), {"o": org_id})]
        cards = c.execute(text(
            "select card_id, signal_id, assignee, urgency_band from cards "
            "where org_id=:o and state in ('queued','surfaced') and expires_at > :now"),
            {"o": org_id, "now": now}).fetchall()
        directory = PgSeatDirectory(conn=c, org_id=org_id)
        for card in cards:
            try:
                obj = resolve(
                    org_id=org_id, delivery_id=f"shadow:{card.card_id}",
                    execution_id=f"shadow:{card.signal_id}", execution_hash="shadow",
                    band=card.urgency_band or "standard", interrupt=False,
                    audience=(AudienceClass.OWNER if card.assignee
                              else AudienceClass.ADMIN_QUEUE),
                    recipient=card.assignee, dedupe_key=f"shadow:{card.card_id}",
                    directory=directory, available_channels=channels,
                    # Org-scope default until card rows carry the evidence ACL — matches what
                    # the legacy path enforces today, so the comparison stays apples-to-apples.
                    can_view=lambda _seat: True,
                    now=now)
                counts["resolved"] += 1
                counts["by_channel"][obj.channel] = counts["by_channel"].get(obj.channel, 0) + 1
            except Unroutable as u:
                counts["unroutable"][u.reason_code] = counts["unroutable"].get(u.reason_code, 0) + 1
            except Exception:      # noqa: BLE001 — a shadow never breaks the sweep it shadows
                counts["errors"] += 1
    return counts


# ── the sweep entrypoint ──────────────────────────────────────────────────────────
def run_distribution(engine, *, base_url: str | None = None,
                     eval_time: datetime | None = None) -> dict:
    """One distribution pass: for every org, resolve the channels it can actually be reached
    on, enqueue new high/critical cards + the daily digest + Layer 5's reminders onto each,
    then drain everything due. Called from the maintenance sweep; per-org failures isolate.

    ``base_url`` defaults to the configured dashboard URL rather than to ``""``. The only
    production caller (``api/routes.py``) never passed one, and ``channels/slack.py`` drops the
    "Open the card →" link when it is empty — so every message this sweep has ever built had no
    way back into the product (measured: all 3 production payloads, 238/260/248 bytes, headline
    and situation only, no link). An unset setting still yields no link, because inventing a
    hostname would be worse than omitting the line.
    """
    now = eval_time or datetime.now(timezone.utc)
    if base_url is None:
        from genios_engine.platform.config import get_settings
        base_url = get_settings().dashboard_url
    totals = {"orgs": 0, "queued": 0, "digests": 0, "reminders": 0, "linked": 0,
              # Named conditions, not silence. `band_starved` on every org means the scoring
              # pipeline is broken upstream; `unrouted` means cards exist with nobody to send
              # them to. Both previously presented as a clean zero.
              "band_starved": 0, "unrouted": 0, "org_failures": 0,
              # Layer 5's backlog, which has its own two failure modes and used to have no
              # counter at all: work that exists (`open_commitments`) and work that exists with
              # nobody able to receive it (`unreachable_commitments`).
              "open_commitments": 0, "unreachable_commitments": 0,
              # Rows queued to this org's registered EXECUTORS. Kept out of `queued` on purpose:
              # that number answers "how much did we ask of a person this tick", and folding
              # machine deliveries into it makes the human load unreadable — an org with four
              # agents would report five times the attention it actually spent.
              "agent_pushed": 0,
              # Orgs with reasoning worth delivering and NO LANE AT ALL to deliver it on —
              # neither a human channel nor a registered executor. This is the live tenant's
              # actual state and it used to be invisible: the sweep queued to a hardcoded
              # 'slack', the drain wrote `failed_terminal`, and the pass reported `queued: 1` —
              # delivery work that had already failed before anyone read the number.
              #
              # "no human channel" is NOT the same condition and must not be counted here. An
              # org whose only recipient is an agent is reached on every tick; calling it
              # unreachable would send an operator to fix a tenant whose delivery works, and
              # would make the one number that is supposed to mean "nothing we produce can get
              # out" mean something weaker. That org gets a log line naming the real gap
              # instead.
              "no_deliverable_channel": 0,
              # The v2 control plane's shadow resolution: how the unwired path WOULD have routed
              # the same cards this tick. The measurement a cutover decision needs.
              "v2_shadow_resolved": 0, "v2_shadow_unroutable": 0}
    with engine.connect() as c:
        # NOT `org_channels` alone. That equated "this tenant has delivery" with "this tenant has
        # configured a channel row", and with the table empty the sweep enumerated nothing and
        # returned success — zero deliveries, no error, for every tenant, forever. An org with
        # live cards has delivery work by definition; the pull surface is a floor it always has,
        # not an integration it opts into.
        orgs = [r[0] for r in c.execute(text(
            "select org_id from org_channels where active "
            "union "
            "select distinct org_id from cards "
            "where state in ('queued','surfaced') and expires_at > :now"),
            {"now": now})]
    for org in orgs:
        totals["orgs"] += 1
        try:
            # Backlog diagnostics are per-ORG and hold whether or not anything can be sent, so
            # they are computed once and OUTSIDE the channel loop. An org with no channel still
            # reports them — it is the org whose numbers matter most.
            with engine.connect() as c:
                channels = deliverable_channels(c, org)
                # The OTHER push lane, and it has to be resolved separately rather than found
                # among the channels above: `deliverable_channels` subtracts the agent
                # transports on purpose (law 1), so an executor is invisible to channel
                # resolution by construction. Resolved here, once, because the same answer
                # decides two things — whether the agent lane runs, and whether this org is
                # unreachable — and those two must never be able to disagree.
                agents = connected_executors(c, org)
                starved, unrouted = card_backlog_counts(c, org, now)
                # The commitment backlog, reported alongside the card backlog because the two
                # fail independently and only together say what this tenant is actually missing.
                open_commitments, unreachable = commitment_backlog_counts(c, org)
            totals["band_starved"] += starved
            totals["unrouted"] += unrouted
            totals["open_commitments"] += open_commitments
            totals["unreachable_commitments"] += unreachable
            if unreachable:
                # Never silent. A commitment nobody can be reached about is not nudged, not
                # escalated and not delivered — it simply accumulates, which is exactly what 170
                # rows did for a week while every counter here read zero. This is a SEATS
                # problem, not a channel problem, and the two need different fixes.
                _log.warning(
                    "org=%s has %d open commitment(s), %d of which nobody can be reached "
                    "about — no owner and no active admin seat to triage them. They are "
                    "tracked and will never be nudged. Add an admin seat to org_seats.",
                    org, open_commitments, unreachable)

            # Linking is bookkeeping on our own rows, not a send, so it runs regardless of
            # whether there is anywhere to send — and it runs BEFORE the reminder enqueue so a
            # reminder can name the card it belongs to.
            totals["linked"] += link_commitment_cards(engine, org)

            if not channels and not agents:
                # Fail loudly, write nothing. Queueing here is not "trying" — the drain has
                # already decided the outcome, so a row would be a failure we manufactured and
                # then reported as work. The tenant has to register a channel
                # (PUT /api/org/{org}/channels/slack); until then this is the honest state.
                totals["no_deliverable_channel"] += 1
                _log.warning(
                    "org=%s has no deliverable channel and no registered executor — nothing "
                    "proactive can be sent. %d card(s) below the push band, %d unrouted, "
                    "%d open commitment(s) with reminders that cannot leave the building. "
                    "Register one with PUT /api/org/%s/channels/slack.",
                    org, starved, unrouted, open_commitments, org)
            elif not channels:
                # A different fact, and saying "nothing can be sent" here would be false: the
                # agent lane below reaches this org on every tick. What is missing is a surface
                # for a PERSON, so nobody sees the same cards their machines are acting on —
                # worth an operator's attention, but not the same failure and not the same fix.
                _log.warning(
                    "org=%s has no human channel — %d registered executor(s) still receive its "
                    "pushable cards, but no person does. %d card(s) below the push band, "
                    "%d unrouted. Add a human surface with PUT /api/org/%s/channels/slack.",
                    org, len(agents), starved, unrouted, org)
            for channel in channels:
                pending = enqueue_pending(engine, org, channel, base_url=base_url)
                totals["queued"] += pending["queued"]
                totals["digests"] += enqueue_digest(engine, org, channel, eval_time=now)
                # Layer 5 decided somebody needed nudging and wrote it down; this is where it
                # actually leaves the building.
                totals["reminders"] += enqueue_executive_messages(
                    engine, org, channel, base_url=base_url)
            # The agent lane, OUTSIDE the loop above and unreachable from inside it. The loop
            # walks channels the tenant registered for people; this walks executors the tenant's
            # machines registered for themselves, from `agent_registry`. Same cards, same
            # eligibility filter, different recipient table — which is the whole of routing laws
            # 1 and 2 expressed as two passes instead of one. An org with no executor never
            # enters it: `agents` is empty and the call is a return, not a query.
            totals["agent_pushed"] += enqueue_agent_lane(
                engine, org, agents=agents, eval_time=now)["queued"]
            shadow = shadow_resolve_v2(engine, org, now=now)
            totals["v2_shadow_resolved"] += shadow["resolved"]
            totals["v2_shadow_unroutable"] += sum(shadow["unroutable"].values())
            totals.setdefault("v2_shadow_detail", {})[org] = shadow
        except Exception:      # noqa: BLE001 — one org's enqueue never blocks the rest
            # Isolate, but never silently: a bare `pass` here makes the most likely activation
            # failure (one tenant's malformed channel config) indistinguishable from "nothing
            # to send". Compare api/routes.py, which isolates the same way and does log.
            totals["org_failures"] += 1
            _log.exception("distribution enqueue failed org=%s", org)
    totals.update(drain(engine, eval_time=now))
    return totals

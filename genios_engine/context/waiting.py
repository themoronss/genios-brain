"""Derived WAITING state — the facts that only exist because nothing happened.

Every other L2 writer records something that occurred: a message arrived, a commitment was made,
a stage moved.  The intelligence a user actually asks for is the opposite shape — "they have not
replied", "no follow-up was sent", "we have not heard from them in three weeks".  No source system
emits that.  It has to be derived against a clock, from the gaps between the events we hold.

Without these five fields the whole stack could see WHO and WHAT but never HOW LONG or WHOSE TURN
FOR HOW LONG, so a card could say "a decision is sitting with them" and nothing more specific,
however good the authored expertise behind it was.

THE TIMELINE SOURCE IS `graph_source_refs`, NOT the facts themselves.  `thread.last_outbound` and
`thread.last_inbound` are single-valued: a second outbound overwrites the first, so the fact rows
hold the LATEST message, never the sequence.  But every write — including a corroborating no-op —
attaches a `graph_source_refs` row bound to the event that caused it, and the field name on that
row carries the direction.  Joining refs back to `source_events` therefore reconstructs the full
directed message timeline per counterparty, which is the only place a follow-up COUNT or a reply
CADENCE can come from.

Deterministic and LLM-free, like `derived.py`: these are arithmetic over timestamps already
committed, so the same graph yields the same numbers on every run.
"""
from __future__ import annotations

from genios_engine.context.vocabulary import kinds_where

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import bindparam, text

from genios_engine.context.derived import _write_fact, retire_facts

#: How far back the timeline is reconstructed.  A follow-up count is about the CURRENT exchange,
#: and `situations.DORMANT_AFTER_DAYS` already declares that a conversation older than 45 days has
#: ended and reopens as a new generation.  180 gives four of those generations of headroom while
#: keeping the join bounded on a founder inbox with years of mail in it.
_WINDOW_DAYS = 180

#: The two fields whose source refs ARE the message timeline, mapped to direction.
_DIRECTION_FIELD = {"thread.last_outbound": "out", "thread.last_inbound": "in"}

#: Observation kinds that mean WE PUT A QUESTION TO THEM — the difference between waiting for an
#: answer and merely not having written lately. Without one of these, silence is not a failure to
#: respond, and a card that treats it as one is inventing an obligation nobody took on.
#:
#: DERIVED FROM THE ONE MEANING TABLE, not a second literal. This was a frozenset here,
#: `_PROGRESS_KINDS` was another in `derived.py`, and polarity was a third in `vocabulary.py` —
#: three files deciding what one kind means. A kind added to the extractor's vocabulary and not
#: to all three scored zero in whichever it was missing from, silently. `observations/kinds.yaml`
#: answers all three per kind, in one row.
#:
#: THE SHIPPED SET IS THE FALLBACK, for the reason `load_meanings` records: a file that will not
#: parse must not make every waiting row read "we just have not written lately".
_ASK_KINDS_FALLBACK: frozenset[str] = frozenset({
    "question", "meeting_request", "proposal_sent", "demo_requested",
    "contract_requested", "next_step_agreed",
    "approval_requested", "information_requested", "intro_requested", "investor_update_sent",
})

_ASK_KINDS: frozenset[str] = kinds_where(is_ask=True) or _ASK_KINDS_FALLBACK

_TIMELINE = (
    "select f.subject_node_id as node_id, f.field as field, se.occurred_at as at "
    "from graph_source_refs r "
    "join graph_facts f on f.fact_version_id = r.fact_version_id and f.org_id = r.org_id "
    "join source_events se on se.event_id = r.event_id "
    "where r.org_id = :o and f.field in ('thread.last_outbound', 'thread.last_inbound') "
    "and se.occurred_at >= :since"
)

#: AN ASK WE MADE, not an ask that mentions them. The distinction is the whole point of
#: `response_expected` and the previous read had it backwards in both directions.
#:
#: MEASURED ON THE PILOT. Outbound mail produced 425 observations across just TWO subject nodes,
#: because an observation from a message we sent is attributed to the sender — us. So when Rohit
#: pitched eleven VCs, the ask landed on Rohit's own node and never on theirs, and every one of
#: Peak XV, Afore, Neon, Together, 3one4, Surge, Z Fellows and Hub71 read as
#: `response_expected = false`: "we just have not written lately", about a fundraise.
#: Exactly one waiting person in the tenant had the flag set.
#:
#: AND THE FALSE POSITIVES WERE WORSE THAN THE MISSES. The old read matched any ask-kind
#: observation on the node whatever its direction, so `question` observations extracted from
#: THEIR inbound mail — Evokoa Team, Lalitha A R, Sehan Sanjula, Pablo Llanos, Prema Roman —
#: marked us as awaiting THEIR answer when they were awaiting ours. It also matched
#: `mrrohitswerashi@gmail.com`, the founder's own node.
#:
#: This read asks the only question the flag means: was there an ask-kind observation on a
#: message WE SENT THIS NODE. `thread.last_outbound` is written per counterparty and
#: `graph_source_refs` maps its fact version back to the event, which is the same join the
#: absence receipt uses and it resolves for every waiting node on the tenant.
#:
#: `in :kinds` with an expanding bindparam rather than `= any(:kinds)`: the array cast is
#: Postgres-only, and a correctness argument that can only be demonstrated against production is
#: one nobody can check.
#: person -> their firm, the same `works_at` edge `outreach_situations._EMPLOYERS` reads. One
#: spelling would be better still; this query is kept local because `waiting.py` runs before the
#: readings and must not import from them (they import from it).
_FIRMS = (
    "select e.from_node_id as person, e.to_node_id as company "
    "from graph_edges e "
    "join graph_nodes n on n.org_id = e.org_id and n.node_id = e.to_node_id "
    "     and n.valid_to is null and n.node_type = 'company' "
    "where e.org_id = :o and e.edge_type = 'works_at' and e.valid_to is null"
)

_ASKS = (
    "select distinct f.subject_node_id as subject_node_id "
    "from graph_facts f "
    "join graph_source_refs r "
    "  on r.fact_version_id = f.fact_version_id and r.org_id = f.org_id "
    "join graph_observations o "
    "  on o.org_id = f.org_id and o.created_by_event_id = r.event_id "
    "where f.org_id = :o and f.field = 'thread.last_outbound' and f.status = 'active' "
    "  and o.status = 'active' and o.kind in :kinds"
)


def _days(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds() // 86400))


def _reply_gaps(timeline: list[tuple[str, datetime]]) -> list[float]:
    """Days between each outbound and the counterparty's NEXT inbound.

    Only the first reply after an outbound counts: a thread where they answered once and then sent
    four more messages describes one reply latency, not five.  Consecutive outbounds with no reply
    between them contribute nothing — an unanswered message has no latency yet, and scoring it as
    zero would make a silent counterparty look fast.
    """
    gaps: list[float] = []
    pending: datetime | None = None
    for direction, at in timeline:
        if direction == "out":
            if pending is None:
                pending = at
        elif pending is not None:
            gaps.append((at - pending).total_seconds() / 86400.0)
            pending = None
    return gaps


#: THE FACTS THAT STOP BEING TRUE THE MOMENT THEY REPLY, retired through `derived.retire_facts`
#: — the shared statement, because two copies of "no longer true" are how two writers come to
#: disagree about it. This module was the first to need one and grew its own; `derived.py` now
#: owns it and the commitment reading uses the same one.
#:
#: Written only while waiting, so retired together the moment waiting ends. `thread.last_heard_days`
#: and `party.reply_cadence_days` are NOT here: they stay true after a reply and are rewritten
#: every sweep from the same timeline.
WAITING_ONLY_FIELDS: tuple[str, ...] = (
    "thread.days_waiting", "thread.follow_up_count", "thread.response_expected")


#: WHERE A REPLY CADENCE COMES FROM WHEN THE PERSON HAS NOT GIVEN US ONE, in order.
#:
#: THE GATE BELOW USED TO BE THE WHOLE ANSWER: two replies from the same person, or nothing. It is
#: the right test and it is almost never satisfiable — measured on the pilot, `party.reply_cadence
#: _days` was set on 0 of 453 nodes, because in a fundraise nobody replies twice. Every reading
#: built on "later than THEIR normal" was therefore permanently false, and a card reporting
#: "0 people past their usual reply time" reads as good news rather than as no measurement.
#:
#: SO THE MEASUREMENT WIDENS RATHER THAN WEAKENS. A person with two replies keeps their own
#: median. Failing that, the people at their FIRM answer for them — two partners at one fund
#: behave more like each other than like a stranger. Failing that, the tenant's own median across
#: every counterparty who has ever replied twice. Only when none of those exists does a declared
#: floor apply, and the floor is not a cadence: it is the admission that there is no evidence.
#:
#: WHICH LEVEL ANSWERED TRAVELS WITH THE NUMBER. `party.reply_cadence_basis` is what keeps this
#: honest — "they usually reply in two days" and "people at this firm usually reply in two days"
#: are different claims, and a card that cannot tell them apart will make the first on the
#: evidence of the second. `condition_situations._is_owner` keeps the same discipline for names.
#: One name per line, not tuple-unpacked. `tests/test_no_missing_module_deps` walks the AST for
#: `Assign` nodes with a `Name` target, so a tuple assignment defines a symbol the scanner cannot
#: see — and a module whose exports are invisible to that scan is one nobody can check imports
#: against.
CADENCE_PERSON = "person"
CADENCE_FIRM = "firm"
CADENCE_TENANT = "tenant"
CADENCE_FLOOR = "floor"

#: The minimum gaps that describe a HABIT rather than an anecdote. Unchanged, and applied at every
#: level: a firm median built from one reply is the same invented normal as a person's.
MIN_GAPS_FOR_CADENCE = 2

#: Used only when nothing above it exists. Deliberately NOT a plausible reply time — it is the
#: value that says "no evidence", and `party.reply_cadence_basis` says so out loud so a reading
#: can refuse to compare against it.
CADENCE_FLOOR_DAYS = 3.0


def cadence_for(node_id: str, gaps_by_node: Mapping[str, list[float]],
                firm_of: Mapping[str, str]) -> tuple[float, str]:
    """`(days, basis)` for one counterparty — person, then firm, then tenant, then floor.

    PURE, so the cascade can be read and tested without a database, and so the rule lives in one
    place rather than in each caller's idea of a fallback.
    """
    own = gaps_by_node.get(node_id) or []
    if len(own) >= MIN_GAPS_FOR_CADENCE:
        return round(median(own), 2), CADENCE_PERSON

    firm = firm_of.get(node_id)
    if firm:
        # EVERY COLLEAGUE'S GAPS, the person's own included — they are evidence about the firm
        # even when there are too few to describe the person.
        pooled = [g for other, gs in gaps_by_node.items() if firm_of.get(other) == firm for g in gs]
        if len(pooled) >= MIN_GAPS_FOR_CADENCE:
            return round(median(pooled), 2), CADENCE_FIRM

    everyone = [g for gs in gaps_by_node.values() for g in gs]
    if len(everyone) >= MIN_GAPS_FOR_CADENCE:
        return round(median(everyone), 2), CADENCE_TENANT
    return CADENCE_FLOOR_DAYS, CADENCE_FLOOR


def reply_gaps_of(timeline: list[tuple[str, datetime]]) -> list[float]:
    """This counterparty's reply latencies. Exposed so the cascade can pool them across a firm."""
    return _reply_gaps(sorted(timeline, key=lambda pair: pair[1]))


def _state(timeline: list[tuple[str, datetime]], now: datetime) -> dict:
    """One counterparty's waiting state from their directed message timeline."""
    outs = [at for direction, at in timeline if direction == "out"]
    ins = [at for direction, at in timeline if direction == "in"]
    last_out = max(outs) if outs else None
    last_in = max(ins) if ins else None

    state: dict[str, object] = {}
    if last_in is not None:
        state["thread.last_heard_days"] = _days(now, last_in)

    waiting = last_out is not None and (last_in is None or last_in < last_out)
    if waiting:
        state["thread.days_waiting"] = _days(now, last_out)
        # The first message is the ask; only what came AFTER it is a follow-up.  Counted against
        # the last inbound rather than against the whole history, so a thread that went quiet,
        # revived, and went quiet again reports the current streak instead of a lifetime total.
        since = [at for at in outs if last_in is None or at > last_in]
        state["thread.follow_up_count"] = max(0, len(since) - 1)

    # THE CADENCE IS NO LONGER DECIDED HERE. This function sees one counterparty's timeline and
    # cannot know their colleagues' or the tenant's, which is exactly what the cascade needs —
    # see `cadence_for`. `compute_waiting` pools the gaps and writes both the number and the
    # basis it came from.
    return state


def _firms(conn, org_id: str) -> Mapping[str, str]:
    """person -> firm, and NEVER at the cost of the pass that needs it.

    The firm level of the cascade is an enhancement: without it a counterparty falls to the
    tenant's median, which is exactly what happened before firms existed. So a graph with no
    `graph_nodes` — a fixture, a tenant mid-migration, a driver difference — must lose the firm
    level and keep the rest.

    A SAVEPOINT, NOT A try/except. Postgres aborts the whole transaction on a failed statement, so
    catching the exception without rolling back leaves every later write in `compute_waiting`
    failing silently. That is the defect `outreach_situations._optional` was written for after it
    emptied eleven gathers on the live tenant; this is the same guard, kept local because
    `waiting.py` runs before the readings and must not import from them.
    """
    try:
        with conn.begin_nested():
            return {str(r.person): str(r.company)
                    for r in conn.execute(text(_FIRMS), {"o": org_id})}
    except Exception:      # noqa: BLE001 — one level of the cascade, never the sweep
        from genios_engine.platform.logging import get_logger
        get_logger("genios.l2").warning(
            "employer map unavailable for org=%s; reply cadence falls back to the tenant median",
            org_id, exc_info=True)
        return {}


def compute_waiting(store, org_id: str, *, now: datetime | None = None) -> int:
    """Write the waiting/absence facts for every counterparty in the org. Returns rows written."""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=_WINDOW_DAYS)

    with store.engine.begin() as c:
        rows = c.execute(text(_TIMELINE), {"o": org_id, "since": since}).all()
        asked = {r[0] for r in c.execute(
            text(_ASKS).bindparams(bindparam("kinds", expanding=True)),
            {"o": org_id, "kinds": sorted(_ASK_KINDS)}).all()}

        per_node: dict[str, list[tuple[str, datetime]]] = {}
        for node_id, field, at in rows:
            direction = _DIRECTION_FIELD.get(str(field))
            if direction is None or at is None:
                continue
            # A DRIVER MAY HAND BACK A STRING. Postgres returns a datetime; SQLite does not, and
            # this module could therefore only be exercised against production — the failure
            # `situation_bso._L1_BY_EVENT_SELECT` and `correlation_conversation` both record
            # ("a query whose correctness can only be demonstrated against production is a query
            # nobody can hold to account"). Coerced here, exactly as `_rows_to_campaigns` does.
            if isinstance(at, str):
                try:
                    at = datetime.fromisoformat(at.replace("Z", "+00:00"))
                except ValueError:
                    continue
            moment = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
            per_node.setdefault(str(node_id), []).append((direction, moment))

        written = 0
        # POOLED BEFORE ANYTHING IS WRITTEN, because the cascade needs every counterparty's gaps
        # to answer for the one that has none of its own.
        gaps_by_node = {node_id: reply_gaps_of(timeline) for node_id, timeline in per_node.items()}
        firm_of = _firms(c, org_id)

        for node_id, timeline in per_node.items():
            state = _state(timeline, now)
            days, basis = cadence_for(node_id, gaps_by_node, firm_of)
            # THE FLOOR IS NOT A CADENCE and is not written as one. A number with no evidence
            # behind it would be indistinguishable from a measured one the moment it left this
            # function, and every reading downstream compares against it.
            if basis != CADENCE_FLOOR:
                state["party.reply_cadence_days"] = days
                state["party.reply_cadence_basis"] = basis
            if "thread.days_waiting" not in state:
                # THEY ANSWERED, or we never wrote to them. Either way the waiting facts are no
                # longer true and must be retired rather than left standing — see
                # `_RETIRE_WAITING`. Runs for every non-waiting node on every sweep and is a
                # no-op after the first, because the second pass finds nothing active to close.
                #
                # IT DOES NOT `continue`. The first cut did, and that was wrong in the direction
                # that matters: `thread.last_heard_days` is MORE true once they answer, and
                # skipping the write loop deleted the very evidence that the wait had ended.
                # Retire what stopped being true, then write what still is.
                written += retire_facts(c, org_id, node_id, WAITING_ONLY_FIELDS, now)
            else:
                # Written ONLY while waiting, and written as False rather than omitted when we
                # never asked: "we are waiting and put no question to them" is a real and
                # different situation from "we are waiting on an answer", and the two need
                # opposite advice.  Absent would collapse them into one.
                state["thread.response_expected"] = node_id in asked
            for field, value in state.items():
                if isinstance(value, bool):
                    _write_fact(c, org_id, node_id, field, "true" if value else "false",
                                "bool", now)
                else:
                    _write_fact(c, org_id, node_id, field, repr(value), "number", now)
                written += 1
    return written


__all__ = [
    "CADENCE_FIRM", "CADENCE_FLOOR", "CADENCE_FLOOR_DAYS", "CADENCE_PERSON",
    "CADENCE_TENANT", "MIN_GAPS_FOR_CADENCE", "cadence_for", "reply_gaps_of","WAITING_ONLY_FIELDS", "compute_waiting"]

"""L2.7.7-U1 · M-4 RESOLUTION DETECTION — the third way a situation can end.

    HubSpot stage -> closed-won        resolved before this unit existed
    someone clicks "handled"           resolved before this unit existed
    "All sorted, we signed yesterday"  bumped `last_seen_at` and looked MORE ACTIVE
    a commitment fulfilled in an email never detected
    a decision made in a thread        never detected

A stated resolution used to make a situation look more alive, not less — the exact inversion of
what the founder experiences, and the shortest path to *"it told me about a contract I cancelled
last week"*. This module is the pass that reads those sentences, and it is written so that the
only thing it can do WRONG cheaply is miss one.

THE FIVE ORDERED STEPS, and the file each one lives in:

    1 GATE       `gate.py`     status, a new signal, and terminal_by_fact is False. No call
                               otherwise — the volume control and the cost control.
    2 CANDIDATE  `gate.py`     L1 already read this message; a `DecisionState` with
                               `state == "made"` on this subject is a prior, never a verdict.
    3 CALL       `prompt.py`   one T2 call: does THIS message say THIS THING is complete?
    4 VALIDATE   `judge.py`    ALG-08 on the quote, the speaker-authority table, the floors.
    5 APPLY      here          the ledger is re-reduced and `decide_lifecycle` decides.

WHAT THIS FUNCTION ITSELF DOES IS STEP 5 AND THE ORCHESTRATION, and the orchestration has one
property worth stating: **the deterministic half runs even when the model does not.** With no
model configured, or with the budget spent, the claims already stored are still re-reduced and
the lifecycle is still re-derived — so a resolution recorded yesterday survives a sweep that
could not afford a call today, and a contradiction recorded yesterday still reopens. Doc 11's
fallback rule is *"falls back to `terminal_by_fact` and LOGS"*, and what falls back is the
DETECTION of new statements, not the memory of the old ones.

EVERY FAILURE DEGRADES TOWARD DOING LESS. A model that does not answer, an answer that does not
parse, a quote that is not in the source, a speaker we cannot identify, a budget that is spent:
every one of them ends with the situation still open and a counted reason. There is no path
through this module that closes a situation on anything except a verified quote from a weighable
speaker above the floor.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from sqlalchemy import text

from genios_engine.context.lifecycle import gate as gate_mod
from genios_engine.context.lifecycle import store as store_mod
from genios_engine.context.lifecycle.authority import role_for_scope
from genios_engine.context.lifecycle.contract import (
    DECISION_APPLY,
    DECISION_REVIEW,
    PROMPT_VERSION,
    DetectionSweep,
    Message,
)
from genios_engine.context.lifecycle.judge import judge
from genios_engine.context.lifecycle.ledger import derive_statement_state
from genios_engine.context.lifecycle.prompt import build_prompt, parse_description
from genios_engine.context.model_audit import record_model_run
from genios_engine.context.situations import (
    RESOLVED_BY_STATEMENT,
    STATEMENT_NONE,
    STATEMENT_PARTIAL,
    STATEMENT_RESOLVED,
    STATUS_ACTIVE,
    _TERMINAL_DEAL_STAGES,
    decide_lifecycle,
    normalize_stage,
)
from genios_engine.platform.logging import get_logger

__all__ = ["MAX_OUTPUT_TOKENS", "detect_resolutions"]

log = get_logger("genios.l2.resolution")

#: One verdict, one band, one short quote and its offsets. A cap rather than a default because
#: this call has no reason to be long, and a long answer to this question is a model explaining
#: itself into a close.
MAX_OUTPUT_TOKENS = 500


def _internal_emails(store, org_id: str) -> frozenset[str]:
    """Who counts as US — the drain's own answer, not a second one.

    Imported lazily and from `context.runner` on purpose: that module already derives the set
    from seats, the account owner and the connected mailbox, and its docstring records what an
    empty "us" set cost the last time two places disagreed about it. The import is inside the
    function because `runner` imports THIS package to reach the drain seam, and a module-level
    import would close that circle.
    """
    from genios_engine.context.runner import _internal_emails as drain_internal_emails
    return drain_internal_emails(store, org_id)


def _terminal_by_fact(deal_stage: Any) -> bool:
    """The one rule that outranks everything below it, read off the row the situations query
    already carried. Same vocabulary as `refresh_situations` — imported, not restated."""
    return normalize_stage(deal_stage) in _TERMINAL_DEAL_STAGES


_ATTEMPTS = (
    "select subject_ref, count(*) as n from l2_model_runs "
    "where org_id = :o and site = 'resolution' and called_at >= :since "
    "group by subject_ref"
)


def _subject_ref(situation_id: str, event_id: str) -> str:
    """The audit key for one (situation, message) call. ONE spelling, because the writer below
    and the reader above must agree exactly — two f-strings is how a budget silently counts
    nothing."""
    return f"situation:{situation_id}:event:{event_id}"


def _attempts_by_subject(conn, org_id: str, *, now: datetime) -> dict[str, int]:
    """Model calls already spent per message, from the audit rows every call already writes.

    Never fatal: a tenant whose audit table is unreadable gets the OLD behaviour — it tries
    again — which is the safe direction for a bound whose only job is to stop paying twice.
    """
    try:
        since = now - timedelta(days=store_mod.LOOKBACK_DAYS)
        return {str(r[0]): int(r[1] or 0)
                for r in conn.execute(text(_ATTEMPTS), {"o": org_id, "since": since}).all()}
    except Exception:      # noqa: BLE001 — a budget hint, never a reason to skip the sweep
        log.info("m4 resolution: could not read prior attempts for org=%s", org_id)
        return {}


def detect_resolutions(store, org_id: str, *, llm: Any | None = None,
                       eval_time: datetime | None = None,
                       internal_emails: Iterable[str] | None = None) -> DetectionSweep:
    """Read this org's new messages for stated resolutions, and re-derive every lifecycle.

    `eval_time` is the sweep's one instant, passed down from the drain — the budget's day
    boundary and the dormancy comparison are both measured against it, and nothing in this call
    tree reads a clock of its own.
    """
    now = eval_time or datetime.now(timezone.utc)
    internal = frozenset(internal_emails) if internal_emails is not None else _internal_emails(
        store, org_id)

    with store.engine.connect() as conn:
        situations = store_mod.situations_to_examine(conn, org_id)
        if not situations:
            return DetectionSweep()
        correlation_ids = [s.correlation_id for s in situations]
        obligations_by_correlation = store_mod.obligations_for(conn, org_id, correlation_ids)
        messages = store_mod.unexamined_messages(conn, org_id, correlation_ids, eval_time=now)
        extractions = store_mod.extraction_outputs(
            conn, org_id, [m["event_id"] for m in messages])
        org_calls, per_situation_calls = store_mod.calls_today(conn, org_id, eval_time=now)
        stored_claims = store_mod.claims_for(conn, org_id, [s.situation_id for s in situations])
        # HOW MANY TIMES WE HAVE ALREADY PAID FOR EACH MESSAGE. One statement, on the same
        # connection as every other gather above, and empty on a tenant that has made no calls.
        attempts = _attempts_by_subject(conn, org_id, now=now)

    by_situation = {s.situation_id: s for s in situations}
    pending: dict[str, list] = {sid: [] for sid in by_situation}
    calls = claims_written = queued = gated_out = 0
    budget_hit = False
    notes: list[str] = []

    if llm is None and messages:
        # Doc 11's fallback, and it LOGS rather than passing quietly: a silent degradation is
        # indistinguishable from a bug, and would be discovered as "the product got worse and
        # nobody knows when".
        log.info("m4 resolution: no model configured for org=%s — %d unexamined messages fall "
                 "back to terminal_by_fact only", org_id, len(messages))
        notes.append("no_model")

    for row in messages:
        situation = by_situation.get(row["situation_id"])
        if situation is None:                     # a situation that left the set mid-sweep
            continue
        obligations = obligations_by_correlation.get(situation.correlation_id, ())
        role = _role_for(row, obligations, internal)
        decision = gate_mod.gate_decision(
            status=situation.status, resolved_by=situation.resolved_by,
            terminal_by_fact=_terminal_by_fact(situation.deal_stage),
            has_new_signal=True,
            # THE REFUSAL THAT WAS UNREACHABLE. `False` was hardcoded here, so a message whose
            # call fails or returns unparseable output — which stores no claim, on purpose:
            # "storing a rejection would make one bad minute a permanent blind spot" — was
            # re-read and re-called on EVERY sweep for the whole lookback, spending the two
            # daily budgets on a message that had already failed twice. The attempts were
            # recorded all along by `record_model_run`; nothing read them back.
            already_examined=attempts.get(
                _subject_ref(situation.situation_id, row["event_id"]), 0
            ) >= gate_mod.MAX_ATTEMPTS_PER_MESSAGE,
            has_text=bool((row["text"] or "").strip()), speaker_role=role,
            calls_today_for_situation=per_situation_calls.get(situation.situation_id, 0),
            calls_today_for_org=org_calls)
        if not decision.fires:
            gated_out += 1
            if decision.budget_exhausted:
                budget_hit = True
                if decision.reason not in notes:
                    notes.append(decision.reason)
                    log.info("m4 resolution: %s for org=%s — statements in newer messages will "
                             "be read on the next sweep", decision.reason, org_id)
            continue
        if llm is None:
            continue

        message = Message(event_id=row["event_id"], text=row["text"],
                          sender_email=row["sender_email"], occurred_at=row["occurred_at"])
        subject = _subject_for(situation, obligations)
        prior = gate_mod.candidate_prior(
            (extractions.get(row["event_id"]) or {}).get("decision_states"), subject)
        prompt = build_prompt(subject=subject, obligations=obligations, message=message,
                              prior=prior)

        calls += 1
        org_calls += 1
        per_situation_calls[situation.situation_id] = (
            per_situation_calls.get(situation.situation_id, 0) + 1)
        started = perf_counter()
        result = llm.call(prompt, max_tokens=MAX_OUTPUT_TOKENS)
        record_model_run(
            store.engine, org_id=org_id, site="resolution",
            subject_ref=_subject_ref(situation.situation_id, row["event_id"]),
            prompt_version=PROMPT_VERSION, prompt=prompt, result=result, called_at=now,
            max_tokens=MAX_OUTPUT_TOKENS,
            latency_ms=max(0, int((perf_counter() - started) * 1000)))
        if not getattr(result, "ok", False):
            # A transient failure is NOT a judgement about the message: nothing is stored, so the
            # next sweep reads it again. Storing a rejection here would make one bad minute a
            # permanent blind spot for that message.
            log.info("m4 resolution: call failed for org=%s event=%s: %s", org_id,
                     row["event_id"], getattr(result, "error", "unknown"))
            continue
        description = parse_description(getattr(result, "parsed", None))
        if description is None:
            log.info("m4 resolution: unusable answer for org=%s event=%s", org_id,
                     row["event_id"])
            continue

        claim = judge(description, situation_id=situation.situation_id, message=message,
                      obligations=obligations, internal_emails=internal,
                      model=getattr(llm, "model", "") or "")
        review_state = "pending" if claim.decision == DECISION_REVIEW else None
        with store.engine.begin() as conn:
            store_mod.write_claim(conn, org_id, claim, review_state=review_state)
        claims_written += 1
        if review_state:
            queued += 1
        pending.setdefault(situation.situation_id, []).append(claim)

    resolved = partial = reopened = 0
    for situation in situations:
        claims = list(stored_claims.get(situation.situation_id, ()))
        claims.extend(pending.get(situation.situation_id, ()))
        obligations = obligations_by_correlation.get(situation.correlation_id, ())
        state = derive_statement_state(
            claims, [ob.obligation_id for ob in obligations])
        if state.state == STATEMENT_NONE and situation.resolved_by != RESOLVED_BY_STATEMENT:
            # Nothing to say, and nothing of ours to undo. `refresh_situations` owns this row's
            # ordinary lifecycle and this pass does not touch it.
            continue
        lifecycle = decide_lifecycle(
            current_status=situation.status, resolved_by=situation.resolved_by,
            last_seen_at=situation.last_seen_at, resolved_at=situation.resolved_at,
            terminal_by_fact=_terminal_by_fact(situation.deal_stage), now=now,
            stated_resolution=state.state)
        if (lifecycle.status == situation.status
                and lifecycle.resolved_by == situation.resolved_by):
            continue
        note = _note_for(state, claims)
        with store.engine.begin() as conn:
            store_mod.apply_lifecycle(
                conn, org_id, situation_id=situation.situation_id, status=lifecycle.status,
                resolved_by=lifecycle.resolved_by,
                resolved_at=state.resolved_at if lifecycle.resolved_by == RESOLVED_BY_STATEMENT
                else None,
                note=note if lifecycle.resolved_by == RESOLVED_BY_STATEMENT else None)
        if lifecycle.reopened or lifecycle.status == STATUS_ACTIVE:
            reopened += 1
        elif state.state == STATEMENT_RESOLVED:
            resolved += 1
        elif state.state == STATEMENT_PARTIAL:
            partial += 1

    return DetectionSweep(
        situations_examined=len(situations), gated_out=gated_out, calls=calls,
        claims_written=claims_written, resolved=resolved, partial=partial, reopened=reopened,
        queued_for_review=queued, budget_exhausted=budget_hit,
        fell_back_to_fact=budget_hit or llm is None, notes=tuple(notes))


def _role_for(row: dict, obligations, internal: frozenset[str]) -> str | None:
    # At the gate the speaker is weighed against EVERY open obligation, because the scope is not
    # known until the model answers. The machine and unknown-sender tests are what this call is
    # for, and neither depends on which obligation is meant.
    return role_for_scope(row.get("sender_email"), obligations, internal_emails=internal)


def _subject_for(situation, obligations) -> str:
    """What the situation is ABOUT, in one line the model is asked about.

    Built from what this pass already read rather than from a second query: the anchor's display
    name is not on the situations row, so the obligations name the subject when they exist and
    the situation id backs it when they do not. A thin subject makes the model's job harder in
    the safe direction — it has less to agree with.
    """
    if obligations:
        return "; ".join(ob.subject for ob in obligations[:5])
    return f"situation {situation.situation_id}"


def _note_for(state, claims) -> str:
    """The `resolution_note` a human reads on the card — the receipt, in one sentence."""
    applied = [c for c in claims if c.decision == DECISION_APPLY and c.quote]
    if not applied:
        return f"stated resolution ({PROMPT_VERSION})"
    latest = max(applied, key=lambda c: (c.stated_at, c.event_id))
    who = latest.speaker_email or latest.speaker_role
    scope = ", ".join(state.covered) if state.covered else "this situation"
    return f'stated resolved by {who} ({latest.speaker_role}) — "{latest.quote}" [{scope}]'

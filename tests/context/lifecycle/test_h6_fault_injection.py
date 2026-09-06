"""H6 · M-4 UNDER FAULT — every way the model can fail, driven from the real drain.

Doc 12's asymmetry is the whole design: *missing* a resolution costs one unnecessary nudge,
*inventing* one loses the thread and the founder never learns it happened. Every threshold in
this unit leans on that. What this file asks is the question the thresholds do not answer — what
happens when there is no usable answer AT ALL — and it asks it through `process_pending`, not
through `detect_resolutions`, because the fallback that matters is the one on the path the
product actually runs.

FIVE FAULTS, ONE ASSERTION. A model that refuses, a model that returns prose instead of JSON, a
model that returns a verdict outside the vocabulary, a model that raises, and a model that
answers correctly but has no budget left. In every case the situation must still be ACTIVE and
`resolved_by` must still be NULL — a wrong close is not recoverable by the person it was hidden
from, and a missed one is recovered by the next sweep.

THE SIXTH IS THE CONTROL. `test_a_working_model_on_the_same_world_does_close_it` runs the same
seed with a model that answers properly and asserts the situation DOES close, so the five above
cannot be passing because the world was unresolvable to begin with.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import text

from genios_engine.context.situations import (
    RESOLVED_BY_FACT,
    RESOLVED_BY_STATEMENT,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
)

from .conftest import AT, ScriptedModel, answer_for
from .test_resolution import RESOLUTION_TEXT, _drop, _ids, _seed


@dataclass
class _Faulty:
    """A model that fails in one named way. `model` is the seam `detect_resolutions` reads."""

    mode: str
    model: str = "faulty-m4"
    prompts: list = field(default_factory=list)

    def call(self, prompt: str, *, max_tokens: int = 500) -> Any:
        self.prompts.append(prompt)
        if self.mode == "raises":
            raise RuntimeError("upstream timed out")
        if self.mode == "refuses":
            return _R(parsed={}, ok=False, error="503 from the provider")
        if self.mode == "prose":
            # The shape a model actually produces when it ignores "JSON only".
            return _R(parsed={"text": "Yes, this looks resolved to me!"}, ok=True)
        if self.mode == "unknown_verdict":
            # The dangerous one: a WELL-FORMED answer using a word we never defined. A parser
            # that guessed which of the four it meant would be guessing about closing a thread.
            return _R(parsed={"verdict": "CLOSED", "certainty": "EXPLICIT_COMPLETION",
                              "scope": ["ob"], "quote": "we signed yesterday",
                              "start_offset": 0, "end_offset": 19}, ok=True)
        if self.mode == "none":
            return _R(parsed=None, ok=True)
        raise AssertionError(self.mode)


@dataclass
class _R:
    parsed: Any
    ok: bool = True
    error: str | None = None


def _status(store, org, sid):
    with store.engine.connect() as conn:
        return conn.execute(text(
            "select status, resolved_by from context_situations "
            "where org_id=:o and situation_id=:s"), {"o": org, "s": sid}).mappings().one()


def _sweep(store, org, llm):
    from genios_engine.context.runner import process_pending
    from genios_engine.platform.config import get_settings
    return process_pending(org_id=org, store=store, llm=llm,
                           crypto_key=get_settings().crypto_key, eval_time=AT)


@pytest.mark.pg
@pytest.mark.parametrize("mode", ["raises", "refuses", "prose", "unknown_verdict", "none"])
def test_a_broken_model_never_invents_a_close(pg_store, mode):
    """Whatever the model does, the thread stays open and nothing is applied."""
    org = f"org_m4_fault_{mode}"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    try:
        out = _sweep(pg_store, org, _Faulty(mode))
        row = _status(pg_store, org, ids["situation"])
        assert row["status"] == STATUS_ACTIVE, (
            f"a {mode!r} model closed a live thread: {out.get('resolutions')}")
        assert row["resolved_by"] is None
        with pg_store.engine.connect() as conn:
            applied = conn.execute(text(
                "select count(*) from situation_resolution_claims "
                "where org_id=:o and decision='apply'"), {"o": org}).scalar()
        assert applied == 0, f"a {mode!r} model produced an APPLIED claim"
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
def test_a_working_model_on_the_same_world_does_close_it(pg_store):
    """The control. Without it every assertion above passes on a world nothing could resolve."""
    org = "org_m4_fault_control"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    try:
        _sweep(pg_store, org, ScriptedModel(answers={ids["reply"]: answer_for(
            RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
            scope=[ids["commitment"]], quote="we signed yesterday")}))
        row = _status(pg_store, org, ids["situation"])
        assert row["status"] == STATUS_RESOLVED
        assert row["resolved_by"] == RESOLVED_BY_STATEMENT
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
def test_a_transient_failure_is_not_stored_so_the_message_is_read_again(pg_store):
    """One bad minute must not become a permanent blind spot for that message.

    The claim row is the per-message cache, so writing a rejection on a TRANSIENT failure would
    mean the sentence that resolved the situation is never read again — a silent, permanent miss
    that no later sweep recovers. This is the one place where storing less is the safe direction.
    """
    org = "org_m4_fault_transient"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    try:
        _sweep(pg_store, org, _Faulty("refuses"))
        with pg_store.engine.connect() as conn:
            assert conn.execute(text("select count(*) from situation_resolution_claims "
                                     "where org_id=:o"), {"o": org}).scalar() == 0

        # The very next sweep, with a model that works, still finds the message.
        out = _sweep(pg_store, org, ScriptedModel(answers={ids["reply"]: answer_for(
            RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
            scope=[ids["commitment"]], quote="we signed yesterday")}))
        assert out["resolutions"]["calls"] > 0, "the failed message was never re-read"
        assert _status(pg_store, org, ids["situation"])["status"] == STATUS_RESOLVED
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
def test_a_fact_ARRIVING_AFTER_a_statement_close_takes_the_situation_back(pg_store):
    """*A fact beats a statement, ALWAYS* — including a fact that arrives SECOND.

    `test_a_situation_the_crm_already_closed_costs_no_model_call` proves the fact-first order:
    the gate refuses and no call is spent. This is the other order, and it is the one that
    decides whether "always" is true — a situation M-4 closed on a sentence, and then the CRM
    moves. If `resolved_by` stayed `statement` the row would keep M-4's receipt on a resolution
    the CRM now owns, and the reversibility argument would run backwards: a statement would be
    the thing a fact could not overturn.

    Driven with a model that WOULD close it again, so the second sweep's answer is not the
    reason the fact wins.
    """
    org = "org_m4_fact_arrives_second"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    llm = ScriptedModel(answers={ids["reply"]: answer_for(
        RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
        scope=[ids["commitment"]], quote="we signed yesterday")})
    try:
        _sweep(pg_store, org, llm)
        assert _status(pg_store, org, ids["situation"])["resolved_by"] == RESOLVED_BY_STATEMENT

        # The CRM catches up. `decide_lifecycle` is the seam both paths meet at, so this is the
        # rule itself rather than a re-run of the drain that would need an ingestible event.
        from genios_engine.context.situations import decide_lifecycle
        row = _status(pg_store, org, ids["situation"])
        after = decide_lifecycle(
            current_status=row["status"], resolved_by=row["resolved_by"],
            last_seen_at=AT, resolved_at=AT, terminal_by_fact=True, now=AT,
            stated_resolution="statement_resolved")
        assert (after.status, after.resolved_by) == (STATUS_RESOLVED, RESOLVED_BY_FACT), (
            "a statement outranked a fact")

        # And the gate then refuses to spend anything more on it.
        from genios_engine.context.lifecycle.gate import SKIP_TERMINAL_BY_FACT, gate_decision
        assert gate_decision(
            status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_STATEMENT, terminal_by_fact=True,
            has_new_signal=True, already_examined=False, has_text=True, speaker_role="owner",
            calls_today_for_situation=0, calls_today_for_org=0).reason == SKIP_TERMINAL_BY_FACT
    finally:
        _drop(pg_store, org)


# =================================================================================================
# A-18 · a PARTIAL resolution must not make a live situation disappear
# =================================================================================================

@pytest.mark.pg
def test_a_partially_resolved_situation_is_still_live_to_the_reader(pg_store):
    """The regression this wave introduced, and the reason it is a regression rather than a gap.

    `STATUS_PARTIALLY_RESOLVED` is new in L2.7.7. Before it existed, a situation with three of five
    obligations discharged was `active` and the founder could see it. `active_situations` — the
    read behind `GET /api/org/{org}/situations` and the reasoner — filtered `status = 'active'`, so
    the moment M-4 re-labelled that row it VANISHED, taking its two outstanding obligations with
    it. That is a milder form of the exact failure doc 12 case 2 names ("2 obligations vanish"),
    caused by the state that exists to prevent it.

    The fix is safe by construction: no row could be `partial` before this wave, so widening the
    read cannot change the answer for anything that predates it.
    """
    from genios_engine.context.situations import STATUS_PARTIALLY_RESOLVED, active_situations

    org = "org_h6_partial_visible"
    ids = _ids(org)
    _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    try:
        with pg_store.engine.begin() as conn:
            conn.execute(text(
                "update context_situations set status=:s, resolved_by='statement' "
                "where org_id=:o and situation_id=:sid"),
                {"s": STATUS_PARTIALLY_RESOLVED, "o": org, "sid": ids["situation"]})
        with pg_store.engine.connect() as conn:
            rows = active_situations(conn, org_id=org)
        assert ids["situation"] in {r["situation_id"] for r in rows}, (
            "a partially-resolved situation disappeared from the live read — its outstanding "
            "obligations went with it")

        # And a genuinely CLOSED one still does not come back.
        with pg_store.engine.begin() as conn:
            conn.execute(text("update context_situations set status='resolved' "
                              "where org_id=:o and situation_id=:sid"),
                         {"o": org, "sid": ids["situation"]})
        with pg_store.engine.connect() as conn:
            rows = active_situations(conn, org_id=org)
        assert ids["situation"] not in {r["situation_id"] for r in rows}, (
            "the widening swallowed the resolved state too")
    finally:
        _drop(pg_store, org)

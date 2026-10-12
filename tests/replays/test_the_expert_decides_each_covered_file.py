"""STEP-12 · M33's acceptance — the review decides each covered file, on the golden set.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_the_expert_decides_each_covered_file.py -q

Tree `yc2_w27_s12` M33.C2.L-integration.V1.U02, under `06` D1. Every founder case runs through the REAL
chain with the expert switched on and the ideal reader answering from the case's cassette (`06` D49 — no
spend), and four things are measured:

  * THE DECIDER IS ASKED NOTHING A COVERED FILE'S REVIEW EXPLAINS. Every reasoning call is recorded
    where the decider and R-1 sit — the compiled lane's (`domain_shadow.reason_native_capability`), each
    pack rule's (`runner.reason_legacy_rule`) and the shadow native lane's (`runner.reason_native_capability`)
    — with what it rested on at that instant: its
    subject, and the events behind it (the situation's, or the source events of the facts the rule
    reads). None may be explained (`reason/expert/cover`) by a file the same sweep covered — for a pack
    rule, a file the compiled lane decided on the live lane (a file decided in shadow keeps its cards
    on today's path, by design);
  * F01, F02, F09, F11, F15, F16, F17 and F47 — the must-detect cases whose files never reached the
    decider before STEP-12 (STEP-12 §8.1) — each get a decision about their file: an audited expert
    run whose subject is the file the case is about;
  * every must-abstain case holds;
  * a replay asks no model — every expert decision the case persisted replays from its stored review,
    matching, with every model door poisoned (`reason/replay.replay_persisted`, `03` F139).
"""
from __future__ import annotations

import os
import re

import pytest

from tests.replays.founder_case import load_cases
from tests.replays.marking import PASS, judge

CASES = load_cases()
NEVER_REACHED_THE_DECIDER = ("F01", "F02", "F09", "F11", "F15", "F16", "F17", "F47")


def _stem(text: str) -> str:
    """A name as letters and digits only — "Lattice Capital" and `latticecap.test` compare by it."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _about(key: str, about: set[str]) -> bool:
    """Is the decided file's key the one the case is about — its domain's first label, or the person,
    against each name the case's expected cards are about?"""
    stem = _stem(str(key).split("@")[-1].split(".")[0])
    return bool(stem) and any(_stem(a).startswith(stem) or stem.startswith(_stem(a))
                              for a in about if _stem(a))


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_the_review_decides_each_covered_file(case, monkeypatch):
    _scratch_db()
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.reason import (domain_shadow, llm_decision_maker, llm_interpretation, llm_sites,
                                      runner)
    from genios_engine.reason.expert import decide as expert
    from genios_engine.reason.expert import sweep
    from genios_engine.reason.expert.cover import Covers, covers_for
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry
    from genios_engine.reason.replay import replay_persisted
    from genios_engine.reason.store import ReasoningStore
    from tests.replays import cassettes
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    engine_of = lambda: routes._graph.engine                       # noqa: E731 — bound at import
    sweep_state: dict = {"covered": Covers(), "decided": Covers()}
    asked: list[tuple[str, str, str]] = []                        # (lane, subject, why it is wrong)
    original_pass, original_compile = sweep.expert_pass, domain_shadow.shadow_compile
    original_native, original_legacy = domain_shadow.reason_native_capability, runner.reason_legacy_rule
    original_runner_native = runner.reason_native_capability

    def _covers(org_id, files, people):
        with engine_of().connect() as c:
            return covers_for(c, org_id, files or {}, people or {})

    def _pass(**kw):
        receipt = original_pass(**kw)
        receipt = receipt if isinstance(receipt, dict) else {}
        sweep_state["people"] = receipt.get("people") or {}
        sweep_state["covered"] = _covers(kw["org_id"], receipt.get("covered"), sweep_state["people"])
        sweep_state["decided"] = Covers()
        return receipt

    def _compile(**kw):
        result = original_compile(**kw)
        decided = (result or {}).get("decided") if isinstance(result, dict) else None
        sweep_state["decided"] = _covers(kw["org_id"], decided, sweep_state.get("people"))
        return result

    def _native(**kw):
        projection, ctx = kw.get("projection"), kw["context"]
        events: list[str] = []
        if projection is not None:
            with engine_of().connect() as c:
                events = list(c.execute(text(
                    "select m.event_id from context_situations s join context_correlation_members m "
                    "  on m.org_id = s.org_id and m.correlation_id = s.correlation_id "
                    " where s.org_id = :o and s.situation_id = :s"),
                    {"o": kw["org_id"], "s": projection.situation_id}).scalars())
        cover = sweep_state["covered"].explaining(ctx.node_id, ctx.node_type, events)
        if cover is not None:
            asked.append(("compiled", ctx.node_id, f"explained by {cover.file_id}"))
        return original_native(**kw)

    def _legacy(**kw):
        ctx, rule = kw["context"], kw["rule"]
        facts = {ctx.node_id: ctx.facts}
        behind = runner._events_behind(ctx, rule, runner._fact_events(
            routes._graph, kw["org_id"], facts, [ctx.node_id]))
        cover = sweep_state["decided"].explaining(ctx.node_id, ctx.node_type, behind)
        if cover is not None:
            asked.append(("pack", f"{rule.id}:{ctx.node_id}", f"explained by {cover.file_id}"))
        return original_legacy(**kw)
    def _runner_native(**kw):
        ctx = kw["context"]
        behind = runner._node_events(ctx, runner._fact_events(
            routes._graph, kw["org_id"], {ctx.node_id: ctx.facts}, [ctx.node_id]))
        cover = sweep_state["decided"].explaining(ctx.node_id, ctx.node_type, behind)
        if cover is not None:
            asked.append(("native", ctx.node_id, f"explained by {cover.file_id}"))
        return original_runner_native(**kw)
    monkeypatch.setattr(sweep, "expert_pass", _pass)
    monkeypatch.setattr(runner, "reason_native_capability", _runner_native)
    monkeypatch.setattr(domain_shadow, "shadow_compile", _compile)
    monkeypatch.setattr(domain_shadow, "reason_native_capability", _native)
    monkeypatch.setattr(runner, "reason_legacy_rule", _legacy)
    run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    engine = engine_of()
    try:
        assert asked == [], f"{case.case_id}: the decider's path was asked what a review explains: {asked}"
        with engine.connect() as c:
            runs = c.execute(text(
                "select r.run_id, n.canonical_key from reasoning_runs r "
                "  left join graph_nodes n on n.org_id = r.org_id and n.node_id = r.root_node_id "
                "       and n.valid_to is null "
                " where r.org_id = :o and r.capability_id = :cap"),
                {"o": run.org_id, "cap": expert.CAPABILITY_ID}).fetchall()
        if case.case_id in NEVER_REACHED_THE_DECIDER:
            about = {a for e in case.cards if e.min >= 1 for a in e.about}
            decided = {str(r.canonical_key or "") for r in runs}
            assert runs, f"{case.case_id}: no decision about its file"
            assert any(_about(key, about) for key in decided), \
                f"{case.case_id}: decided {sorted(decided)}, about {sorted(about)}"
        if case.kind == "must_abstain":
            assert judge(case, run).verdict == PASS, f"{case.case_id}: the must-abstain case broke"

        def _poisoned(*_a, **_k):
            raise AssertionError("a model was asked during a replay")
        monkeypatch.setattr(llm_decision_maker, "enabled_for", lambda org_id: True)
        monkeypatch.setattr(llm_decision_maker, "decide_with_llm", _poisoned)
        monkeypatch.setattr(llm_interpretation, "interpret_request", _poisoned)
        monkeypatch.setattr(llm_sites, "make_site_client", _poisoned)
        store = ReasoningStore(engine=engine)
        # The case ran at its own instants, weeks before the wall clock; the store keeps a context
        # payload for its retention window from when it was written, so the replay is made the way the
        # founder would have had it then — this tenant's payloads still held (retention is not the
        # subject; `tests/reason/expert/test_replay_asks_no_model.py` proves a replay on fresh rows).
        with engine.begin() as c:
            c.execute(text("update reasoning_context_payloads set expires_at = now() + interval '1 day' "
                           " where org_id = :o"), {"o": run.org_id})
        for r in runs:
            _exec, comparison = replay_persisted(
                store=store, org_id=run.org_id, run_id=r.run_id,
                orchestrator=ReasoningOrchestrator(default_registry()))
            assert comparison.matches, (case.case_id, r.run_id, comparison.differences)
    finally:
        remove_tenant(engine, run.org_id)

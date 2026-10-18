"""STEP-13 · a question to you is authorised as a question — never through a decision's authority.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/test_a_question_is_authorised.py

Tree `yc2_w27_s13` M36.C2.L-logic.V1.U04 (`reason/authority.QUESTION_SIGNAL_JOINS`, `QUESTION_SIGNAL_PREDICATE`;
`03` F184, `06` D60). A find-out decision has no candidate — the decision contract forbids one — and the
delivery authority (`AUDITED_SIGNAL_PREDICATE`) proves a SELECTED move, so a question had no road to the
founder. A question signal is authorised by its own fragment: the expert's audited, completed, live run
that ended INSUFFICIENT on its answer, the signal bound to that run's decision hash and unexpired, in the
Investigation lane, with no candidate, and the file's question asked by that run still open. It never passes
the decision's fragment, and a decision never passes it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import founder_questions as Q
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.authority import (AUTHORITATIVE_SIGNAL_JOINS, AUTHORITATIVE_SIGNAL_PREDICATE,
                                            QUESTION_SIGNAL_JOINS, QUESTION_SIGNAL_PREDICATE)
from genios_engine.reason.expert import decide as D
from genios_engine.reason.expert import store as R
from genios_engine.reason.store import ReasoningStore
from tests.reason.expert.checks import as_written

pytestmark = pytest.mark.pg

ORG = "org_s13_question_authority"
NOW = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
FILE = "node_question_fund"
QUESTION = "Did Neel ask to move the first call?"
FIND_OUT = {
    "facts": [{"claim": "Neel wrote about the first call", "evidence": ["evt_neel_0927"]}],
    "frames": {"primary": "a first call with a fund, its date unsure", "rivals": ["a call that stands"]},
    "expected_vs_actual": {"stage": None, "expected": "a fixed date", "actual": "a date in doubt"},
    "scenarios": {"do_nothing": "the call is missed", "act": "the date is confirmed", "best": "a meeting",
                  "worst": "a pass", "signals_to_watch": ["a reply"]},
    "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible", "reasons": ["close"]},
    "mode": "find_out",
    "next_move": {"who": "you", "what": QUESTION, "for_whom": "Neel", "by_when": None,
                  "rests_on": ["fact:1"]},
    "alternative": "ask on the call", "wait_or_stop": "ask once", "done_when": "the date is known"}
ACT = {**FIND_OUT, "mode": "act", "next_move": {**FIND_OUT["next_move"], "what": "Send Neel a pre-read"}}


def _run(pg_store, raw: dict, fingerprint: str) -> dict:
    review = ExpertReview.from_mapping(raw)
    with pg_store.engine.begin() as c:
        assert R.write_review(c, org_id=ORG, file_id=FILE, fingerprint=fingerprint, model="claude-sonnet-5",
                              prompt_version="expert-review.v3", dossier_digest="d" * 64, status=R.VALID,
                              reason=None, review=review, input_tokens=10, output_tokens=10, cost_micro_usd=1,
                              at=NOW, inputs={"events": ["evt_neel_0927"]},
                              triggers=[{"kind": "first_look", "says": "never judged"}],
                              checked=as_written(review))
        row = R.read_review(c, ORG, FILE, fingerprint)
    # The run is bound to its config, as a live one is (`signals_linked_run_requires_config`): a snapshot of
    # the founder office's pack, content-addressed (`packs/snapshot`, as `test_bundle_doctrine` makes one).
    import json

    from genios_engine.packs.snapshot import snapshot_id
    effective = {"pack_id": "founder_office", "version": "1.0.0"}
    with pg_store.engine.begin() as c:
        c.execute(text("insert into config_snapshots (snapshot_id, org_id, pack_id, effective, cause) "
                       "values (:s, :o, 'founder_office', cast(:e as jsonb), 'test') on conflict do nothing"),
                  {"s": snapshot_id(effective), "o": ORG, "e": json.dumps(effective)})
    request = D.request_for(row, org_id=ORG, root_entity_type="company", domain="founder_office",
                            eval_time=NOW, graph_version=3, config_snapshot_id=snapshot_id(effective))
    execution = D.decide(request)
    bundle = persist_execution(store=ReasoningStore(engine=pg_store.engine), execution=execution)
    return {"run_id": bundle["run"]["run_id"], "hash": bundle["output"]["decision_hash"],
            "config": bundle["run"]["config_snapshot_id"],
            "expires": execution.decision.expires_at, "outcome": execution.decision.outcome.value}


@pytest.fixture
def world(pg_store):
    from tests.test_admin_support_packs import _erase_tenant, _seed_org
    _seed_org(pg_store, ORG)
    _erase_tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        c.execute(text("delete from expert_reviews where org_id = :o"), {"o": ORG})
    try:
        yield pg_store
    finally:
        _erase_tenant(pg_store, ORG)


def _question_signal(c, run, sid="sig_question", **over) -> str:
    row = {"s": sid, "o": ORG, "n": FILE, "run": run["run_id"], "hash": run["hash"], "exp": run["expires"],
           "cfg": run["config"],
           "lane": "investigation", "why": "we cannot conclude, and naming what is missing is the output",
           "version": 0, "cand": None, "t": NOW}
    row.update(over)
    c.execute(text(
        "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, eval_time, "
        "reasoning_run_id, reasoning_candidate_id, reasoning_decision_hash, authority_expires_at, "
        "authority_binding_version, output_lane, lane_reason, status, config_snapshot_id) values (:s, :o, "
        "'founder_question', :n, 0, 'founder_question', :t, :run, :cand, :hash, :exp, :version, :lane, :why, "
        "'open', :cfg)"), row)
    return sid


def _authorised(c, *, at=NOW) -> list[str]:
    return [r[0] for r in c.execute(text(
        "select s.signal_id from signals s " + QUESTION_SIGNAL_JOINS +
        " where s.org_id = :o and s.status = 'open' and " + QUESTION_SIGNAL_PREDICATE),
        {"o": ORG, "authority_time": at})]


def _as_a_decision(c) -> list[str]:
    return [r[0] for r in c.execute(text(
        "select s.signal_id from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
        " where s.org_id = :o and s.status = 'open' and " + AUTHORITATIVE_SIGNAL_PREDICATE),
        {"o": ORG, "authority_time": NOW})]


def _ask(c, run):
    return Q.ask(c, org_id=ORG, file_id=FILE, fingerprint="ffp-q", run_id=run["run_id"], question=QUESTION,
                 why="the expert must find out first", at=NOW)


def test_the_question_of_a_run_that_ended_insufficient_is_authorised(world):
    run = _run(world, FIND_OUT, "ffp-q")
    assert run["outcome"] == "insufficient_context"
    with world.engine.begin() as c:
        _ask(c, run)
        sid = _question_signal(c, run)
        assert _authorised(c) == [sid]
        assert _as_a_decision(c) == [], "never through the decision's fragment: it has no selected move"


# (A signal bound to another run's hash, or another config, the schema itself refuses — the run's own
# foreign keys — so the fragment's equalities there are defence in depth, not tested twice.)
@pytest.mark.parametrize("change", ["answered", "retired", "expired", "decision_lane"])
def test_a_question_that_is_not_one_any_more_is_not_authorised(world, change):
    run = _run(world, FIND_OUT, "ffp-q")
    with world.engine.begin() as c:
        asked = _ask(c, run)
        over = {"decision_lane": {"lane": "decision"}}.get(change, {})
        _question_signal(c, run, **over)
        if change == "answered":
            Q.answer(c, org_id=ORG, question_id=asked.question_id, words="Yes, to Thursday.", by="u", at=NOW)
        if change == "retired":
            Q.retire(c, org_id=ORG, file_id=FILE, why=Q.NO_LONGER_ASKED, at=NOW)
        at = run["expires"] + timedelta(seconds=1) if change == "expired" else NOW
        assert _authorised(c, at=at) == []


def test_a_decision_is_never_a_question(world):
    run = _run(world, ACT, "ffp-act")
    assert run["outcome"] == "decision"
    with world.engine.begin() as c:
        _ask(c, run)
        _question_signal(c, run, sid="sig_act")
        assert _authorised(c) == []


def test_a_run_asks_only_about_its_own_file(world):
    """The run's root is the file the question is about: the same run cannot authorise a question about
    another file, though one were filed for it."""
    run = _run(world, FIND_OUT, "ffp-q")
    with world.engine.begin() as c:
        Q.ask(c, org_id=ORG, file_id="node_another_file", fingerprint="ffp-q", run_id=run["run_id"],
              question=QUESTION, why="the expert must find out first", at=NOW)
        _question_signal(c, run, sid="sig_elsewhere", n="node_another_file")
        assert _authorised(c) == []


# (A run that did not complete the schema refuses outright — `reasoning_runs_status_check` holds only
# 'completed' — so the fragment's status equality is defence in depth, not tested twice.)
@pytest.mark.parametrize("change", ["capability_id = 'sales.deal_cooling'", "mode = 'shadow'"])
def test_only_the_experts_live_run_asks(world, change):
    """A run of any other capability, or a shadow run, is no question to the founder, though it ended
    insufficient."""
    import os

    from sqlalchemy import create_engine
    run = _run(world, FIND_OUT, "ffp-q")
    replica = create_engine(os.environ["GENIOS_TEST_DATABASE_URL"],
                            connect_args={"options": "-c session_replication_role=replica"})
    with replica.begin() as c:                  # the audit rows are immutable to everyone but this test
        c.execute(text(f"update reasoning_runs set {change} where org_id = :o and run_id = :r"),
                  {"o": ORG, "r": run["run_id"]})
    with world.engine.begin() as c:
        _ask(c, run)
        _question_signal(c, run)
        assert _authorised(c) == []

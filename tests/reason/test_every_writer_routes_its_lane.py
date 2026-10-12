"""STEP-13 · every writer of a signal writes its lane (`03` F10, F186).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/test_every_writer_routes_its_lane.py [-k legacy|native|deal_health|team]

Tree `yc2_w27_s13` M36.C1.L-data.V0.U02 (the legacy rule lane, `reason/runner._emit`), U03 (the native
publication, `reason/publication`), U04 (the deal-health composer, `reason/composer`), U05 (the team emitter,
`reason/team/emit`). Five writers left a signal's `output_lane` NULL, so a card could not say whether it was a
thing to do, to find out, to rule on or to watch (`signals.output_lane`, 0189). Each now writes the lane and
its reason beside the row: the legacy lane, the native publication and the composer the lane of the
decision they publish — routed where it was made (`decision_maker`, `llm_decision_maker`) — and the team
emitter the lane of what a post-pass observed: a discrepancy between two sources is a conflict to rule on,
a team situation something to watch. No writer routes a lane of its own from a model.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.contracts.reasoning import OutputLane

ORG = "org_s13_every_lane"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def _scratch() -> str:
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    return url


@pytest.fixture
def engine():
    eng = create_engine(_scratch())
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'lanes@every.test')"),
                  {"o": ORG})
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    with eng.begin() as c:
        for table in ("card_events", "cards", "signals"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _without_references():
    """Sessions that skip FOREIGN KEY triggers: the row binds a reasoning run, and persisting a whole
    decision is not what these tests are about (`test_every_card_expiry_says_why._without_references`)."""
    return create_engine(_scratch(), connect_args={"options": "-c session_replication_role=replica"})


def _lane(eng, signal_id: str) -> tuple[str | None, str | None]:
    with eng.connect() as c:
        row = c.execute(text("select output_lane, lane_reason from signals where signal_id = :s"),
                        {"s": signal_id}).first()
    return (row.output_lane, row.lane_reason) if row else (None, None)


def _decision(lane: OutputLane, reason: str, **kw) -> SimpleNamespace:
    return SimpleNamespace(output_lane=lane, lane_reason=reason, do_nothing_consequence=None,
                           uncertainty=(), outcome_window_days=7, candidates=(),
                           expires_at=AT + timedelta(days=2), **kw)


# ── U02 · the legacy rule lane ───────────────────────────────────────────────────────────────────
def test_legacy_the_payload_carries_the_decisions_lane():
    from genios_engine.reason.runner import _decision_payload
    selected = SimpleNamespace(play_id="reply", parameters={"steps": ["Reply today"]})
    payload = _decision_payload(_decision(OutputLane.MONITOR, "under the floor"), selected)
    assert (payload["output_lane"], payload["lane_reason"]) == ("monitor", "under the floor")
    assert payload["candidate_steps"] == ["Reply today"], "the payload it always carried, unchanged"


@pytest.mark.pg
def test_legacy_emit_writes_the_lane(engine):
    from genios_engine.reason.runner import _emit
    rule = SimpleNamespace(id="r_lane", version=1, level="prescriptive", reason_code="rc")
    sid = _emit(SimpleNamespace(engine=_without_references()), ORG, rule, "n1", 60, {}, [], AT, "cs_1",
                "run_1", "cand_1", "hash_1", AT + timedelta(days=2), "play", 1, "pk", "1",
                decision_payload={"output_lane": "monitor", "lane_reason": "under the floor"})
    assert _lane(engine, sid) == ("monitor", "under the floor")


# ── U03 · the native publication ────────────────────────────────────────────────────────────────
def test_native_the_publication_carries_its_decisions_lane():
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.publication import build_native_publication
    from genios_engine.reason.reasoners import default_registry
    from tests.test_native_publication import BUNDLE, DELIVERABLE_V2, _request
    execution = ReasoningOrchestrator(default_registry()).execute(_request(DELIVERABLE_V2))
    publication = build_native_publication(execution=execution, audit_bundle=BUNDLE)
    assert execution.decision.output_lane is not None
    assert (publication.output_lane, publication.lane_reason) == (
        execution.decision.output_lane.value, execution.decision.lane_reason)


@pytest.mark.pg
def test_native_publish_writes_the_lane(engine):
    from genios_engine.reason.publication import publish_native_signal
    publication = SimpleNamespace(
        rule_id="r_native", rule_version=1, level="prescriptive", subject_node_id="n2", score=60,
        score_inputs={}, reason_code="rc", evidence=(), play="play", reasoning_run_id="run_2",
        reasoning_candidate_id="cand_2", reasoning_decision_hash="hash_2",
        authority_expires_at=AT + timedelta(days=2), output_lane="decision",
        lane_reason="a decision at 7000 bp, at or above the 6000 bp floor")
    sid = publish_native_signal(SimpleNamespace(engine=_without_references()), org_id=ORG,
                                publication=publication, eval_time=AT, config_snapshot_id="cs_2",
                                pack_id="pk", pack_version="1", authority_pack_revision=1)
    assert _lane(engine, sid) == ("decision", "a decision at 7000 bp, at or above the 6000 bp floor")

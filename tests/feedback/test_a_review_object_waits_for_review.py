"""STEP-18 B4 · a learning the weekly sweep sends to a human waits for that human — and can be reviewed.

    GENIOS_TEST_DATABASE_URL=… pytest tests/feedback/test_a_review_object_waits_for_review.py -q

`yc2_w27_s18` M48.C1.L-data.V0.U02 (L6 Learning, `feedback/`).

⛔ WHAT WAS WRONG. The weekly sweep persists every proposal at `governed`
(`feedback/orchestrator.run_learning`, and `feedback/brain_pipeline.admit_proposals` the same way),
then `publisher.publish` dispatches it. For one governance routes to a human — a knowledge
suggestion, an Organization brain edit, a constrained visibility — `publish` LOGGED
`governed → human_review` in `learning_transitions` and never moved the row, so the row stayed
`governed`: `POST /v1/learning/objects/{id}/review` answered 409 (*"object is governed, not
human_review"*) and the console's queue — `state = 'human_review'` — never listed it. A learning
that waits for a human could never be shown to one.

Driven the way the sweep drives it — `govern`, `persist` at `governed`, `publish` — on Postgres, then
reviewed through the real route over HTTP.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.learning import (LearningEvidence, LearningObject, LearningState,
                                              LearningTarget, Visibility, VisibilityScope)

ORG = "org_s18_review_waits"
NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the learning ledger is Postgres's")
    from genios_engine.platform.db import get_engine
    from scripts.brain_pilot_seed import ensure_org

    eng = get_engine(live_db_url)
    _wipe(eng)
    ensure_org(eng, ORG, at=NOW)
    yield eng
    _wipe(eng)


def _wipe(engine) -> None:
    with engine.begin() as conn:
        for table in ("knowledge_suggestions", "learned_brain_entries", "temporary_memories",
                      "learning_transitions", "learning_object_evaluations", "learning_objects",
                      "learning_policies", "authority_rules"):
            savepoint = conn.begin_nested()
            try:
                conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
                savepoint.commit()
            except Exception:                                  # noqa: BLE001 — a table not here
                savepoint.rollback()
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _proposal(target: LearningTarget, subject: str) -> LearningObject:
    return LearningObject(
        org_id=ORG, unit="outcome_analysis", target=target, subject=subject,
        proposed_value={"statement": f"{subject} is how this company works"},
        evidence=LearningEvidence(observations=6, independent_refs=6, distinct_days=4,
                                  positive=6, negative=0, confidence_bp=9_000,
                                  business_value_bp=8_000, distinct_entities=4),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        first_seen_at=NOW, last_seen_at=NOW, policy_key="pk_s18")


def _sweep(engine, obj: LearningObject) -> tuple[LearningState, str]:
    """The weekly sweep's own sequence for one admitted proposal (`orchestrator.py:270-286`)."""
    from genios_engine.feedback.governance import govern
    from genios_engine.feedback.orchestrator import load_or_seed_policy
    from genios_engine.feedback.publisher import persist, publish

    with engine.begin() as conn:
        policy = load_or_seed_policy(conn, ORG, now=NOW)
        decision = govern(obj, policy)
        assert persist(conn, obj, state=LearningState.GOVERNED, at=NOW,
                       policy_revision=policy.revision) == "inserted"
        sink = publish(conn, obj, target_state=decision.target_state, at=NOW)
    return decision.target_state, str(sink)


def _state(engine, obj: LearningObject) -> str:
    with engine.connect() as conn:
        return conn.execute(text("select state from learning_objects where org_id = :o and "
                                 "learning_id = :l"), {"o": ORG, "l": obj.learning_id}).scalar()


@contextmanager
def _console(engine):
    """The real learning router over HTTP, as the tenant's owner, bound to the scratch database."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import learning_routes as routes
    from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner

    class _Graph:
        def __init__(self, e):
            self.engine = e

    previous = routes._graph
    routes._graph = _Graph(engine)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[require_owner] = lambda: AuthCtx(org_id=ORG, actor_id="owner_s18",
                                                              scopes=None)
    app.dependency_overrides[get_current_org] = lambda: ORG
    try:
        with TestClient(app) as client:
            yield client
    finally:
        routes._graph = previous


@pytest.mark.parametrize("target, why", [
    (LearningTarget.KNOWLEDGE_SUGGESTION, "knowledge_review"),
    (LearningTarget.ORGANIZATION, "organization_review"),
])
def test_a_learning_sent_to_a_human_rests_at_human_review(engine, target, why):
    obj = _proposal(target, f"subject_{target.value}")
    state, _sink = _sweep(engine, obj)
    assert state is LearningState.HUMAN_REVIEW, f"governance no longer sends {why} to a human"
    assert _state(engine, obj) == "human_review", (
        "the ledger says governed → human_review and the row still says governed: the review "
        "route refuses it (409) and the console's queue never lists it")


def test_the_console_lists_it_and_the_owner_can_approve_it(engine):
    obj = _proposal(LearningTarget.KNOWLEDGE_SUGGESTION, "subject_approve")
    _sweep(engine, obj)
    with _console(engine) as client:
        listed = client.get("/v1/learning/objects", params={"state": "human_review"})
        reviewed = client.post(f"/v1/learning/objects/{obj.learning_id}/review",
                               json={"approve": True})
    assert listed.status_code == 200, listed.text
    assert obj.learning_id in {o.get("learning_id") for o in listed.json().get("objects", ())}
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["state"] == "promoted"
    assert _state(engine, obj) == "promoted"


def test_the_owner_can_reject_it(engine):
    obj = _proposal(LearningTarget.ORGANIZATION, "subject_reject")
    _sweep(engine, obj)
    with _console(engine) as client:
        reviewed = client.post(f"/v1/learning/objects/{obj.learning_id}/review",
                               json={"approve": False})
    assert reviewed.status_code == 200, reviewed.text
    assert _state(engine, obj) == "rejected"


def test_a_learning_published_without_a_human_does_not_join_the_queue(engine):
    """The negative half: only a review-routed object rests at `human_review`. A metric is
    published, never reviewed (`governance.govern`), and must not appear in a human's queue."""
    obj = _proposal(LearningTarget.METRICS, "subject_metric")
    state, sink = _sweep(engine, obj)
    assert state is LearningState.PROMOTED and sink == "metric_published"
    assert _state(engine, obj) != "human_review"


def test_a_second_sweep_of_the_same_proposal_leaves_the_waiting_object_alone(engine):
    """`persist` answers `unchanged` for a row past `observed`/`candidate`, so next week's sweep of
    the same proposal neither re-queues nor reopens it."""
    from genios_engine.feedback.publisher import persist

    obj = _proposal(LearningTarget.KNOWLEDGE_SUGGESTION, "subject_twice")
    _sweep(engine, obj)
    with engine.begin() as conn:
        assert persist(conn, obj, state=LearningState.GOVERNED, at=NOW) == "unchanged"
    assert _state(engine, obj) == "human_review"

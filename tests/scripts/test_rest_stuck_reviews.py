"""STEP-18 S18-X09 · a review object persisted before B4's fix waits for review again.

    GENIOS_TEST_DATABASE_URL=… pytest tests/scripts/test_rest_stuck_reviews.py -q

`yc2_w27_s18` M48.C1.L-data.V1.U14 (L6 Learning, `feedback/`; the one-off `scripts/rest_stuck_reviews.py`).

⛔ WHAT WAS WRONG. B4 (`feedback/publisher._rest_for_review`) rests a NEW review object at
`human_review`. One the weekly sweep sent for review before the fix stays at `governed`: the ledger
says `governed → human_review`, the row says `governed`, `persist` answers `unchanged` every week so
nothing publishes it again, the review route answers 409 and the console never lists it. The script
moves exactly those rows — `governed`, latest edge to `human_review` — dry run first.

An object stuck the old way is made here as the sweep made it before the fix: the sweep's own
sequence, then the row put back at `governed`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.learning import (LearningEvidence, LearningObject, LearningState,
                                              LearningTarget, Visibility, VisibilityScope)
from scripts import rest_stuck_reviews as RS

ORG = "org_s18_rest_stuck_reviews"
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
        first_seen_at=NOW, last_seen_at=NOW, policy_key="pk_s18_rest")


def _sweep(engine, obj: LearningObject) -> LearningState:
    """The weekly sweep's own sequence (`orchestrator.py`): govern, persist at governed, publish —
    persist and publish at ONE instant, as the sweep does."""
    from genios_engine.feedback.governance import govern
    from genios_engine.feedback.orchestrator import load_or_seed_policy
    from genios_engine.feedback.publisher import persist, publish

    with engine.begin() as conn:
        policy = load_or_seed_policy(conn, ORG, now=NOW)
        decision = govern(obj, policy)
        persist(conn, obj, state=LearningState.GOVERNED, at=NOW, policy_revision=policy.revision)
        publish(conn, obj, target_state=decision.target_state, at=NOW)
    return decision.target_state


def _stuck_the_old_way(engine, obj: LearningObject) -> None:
    """What the sweep left before B4's fix: the edge logged, the row at governed."""
    assert _sweep(engine, obj) is LearningState.HUMAN_REVIEW
    with engine.begin() as conn:
        conn.execute(text("update learning_objects set state = 'governed' where org_id = :o "
                          "and learning_id = :l"), {"o": ORG, "l": obj.learning_id})


def _state(engine, obj: LearningObject) -> str:
    with engine.connect() as conn:
        return conn.execute(text("select state from learning_objects where org_id = :o and "
                                 "learning_id = :l"), {"o": ORG, "l": obj.learning_id}).scalar()


def _world(engine) -> dict[str, LearningObject]:
    """One object stuck at governed; one resting at human_review already (built after B4); one
    published without a human; one reviewed and promoted; one persisted and never published; and
    one whose row moved on (promoted) with no edge of its own — the ledger's latest still says
    `human_review`, and only a `governed` row is the script's."""
    from genios_engine.feedback.publisher import persist

    objs = {name: _proposal(target, f"subject_{name}") for name, target in (
        ("stuck", LearningTarget.KNOWLEDGE_SUGGESTION), ("resting", LearningTarget.ORGANIZATION),
        ("metric", LearningTarget.METRICS), ("reviewed", LearningTarget.ORGANIZATION),
        ("unpublished", LearningTarget.KNOWLEDGE_SUGGESTION),
        ("moved_on", LearningTarget.ORGANIZATION))}
    _stuck_the_old_way(engine, objs["stuck"])
    _sweep(engine, objs["resting"])
    _sweep(engine, objs["metric"])
    _sweep(engine, objs["reviewed"])
    with engine.begin() as conn:
        conn.execute(text("update learning_objects set state = 'promoted' where org_id = :o "
                          "and learning_id = :l"), {"o": ORG, "l": objs["reviewed"].learning_id})
        conn.execute(text(
            "insert into learning_transitions (id, org_id, learning_id, from_state, to_state, "
            "reason_code, actor, occurred_at) values ('ltr_s18_rev', :o, :l, 'human_review', "
            "'promoted', 'approved', 'owner', :at)"),
            {"o": ORG, "l": objs["reviewed"].learning_id, "at": NOW + timedelta(hours=1)})
        persist(conn, objs["unpublished"], state=LearningState.GOVERNED, at=NOW)
    _sweep(engine, objs["moved_on"])
    with engine.begin() as conn:
        conn.execute(text("update learning_objects set state = 'promoted' where org_id = :o "
                          "and learning_id = :l"), {"o": ORG, "l": objs["moved_on"].learning_id})
    return objs


def test_the_dry_run_names_the_stuck_object_and_writes_nothing(engine, live_db_url, capsys):
    objs = _world(engine)
    assert RS.main(["--database-url", live_db_url, "--org", ORG]) == 0
    out = capsys.readouterr().out
    assert "would move 1 review object(s) from governed to human_review, in 1 org(s)" in out, out
    assert objs["stuck"].learning_id in out and "DRY RUN" in out
    assert _state(engine, objs["stuck"]) == "governed", "a dry run writes nothing"


def test_apply_moves_exactly_the_stuck_object(engine, live_db_url, capsys):
    objs = _world(engine)
    assert RS.main(["--database-url", live_db_url, "--org", ORG, "--apply"]) == 0
    assert "moved 1 review object(s)" in capsys.readouterr().out
    assert {name: _state(engine, obj) for name, obj in objs.items()} == {
        "stuck": "human_review", "resting": "human_review", "metric": "governed",
        "reviewed": "promoted", "unpublished": "governed", "moved_on": "promoted"}
    with engine.connect() as conn:
        assert RS.stuck(conn, ORG) == [], "a second run finds nothing"


def test_a_moved_object_can_be_reviewed(engine):
    """The point of it: the console's queue (`state = 'human_review'`) lists it, and the review route
    takes a `human_review` row (`tests/feedback/test_a_review_object_waits_for_review.py`)."""
    objs = _world(engine)
    RS.rest(engine, ORG)
    with engine.connect() as conn:
        queue = {r[0] for r in conn.execute(text(
            "select learning_id from learning_objects where org_id = :o and state = 'human_review'"),
            {"o": ORG})}
    assert objs["stuck"].learning_id in queue


def test_the_latest_edge_at_one_instant_is_the_one_with_a_predecessor(engine):
    """The sweep persists (`→ governed`) and publishes (`governed → human_review`) at ONE instant;
    between two edges of one instant the one with a `from_state` is the later, whatever their ids."""
    obj = _proposal(LearningTarget.KNOWLEDGE_SUGGESTION, "subject_tie")
    _stuck_the_old_way(engine, obj)
    with engine.begin() as conn:
        conn.execute(text("delete from learning_transitions where org_id = :o and learning_id = :l"),
                     {"o": ORG, "l": obj.learning_id})
        for tid, before, after in (("ltr_a", "governed", "human_review"), ("ltr_z", None, "governed")):
            conn.execute(text(
                "insert into learning_transitions (id, org_id, learning_id, from_state, to_state, "
                "reason_code, occurred_at) values (:i, :o, :l, :f, :t, 'r', :at)"),
                {"i": tid, "o": ORG, "l": obj.learning_id, "f": before, "t": after, "at": NOW})
    with engine.connect() as conn:
        assert RS.stuck(conn, ORG) == [(ORG, obj.learning_id)]


def test_an_object_whose_latest_edge_left_review_is_not_moved(engine):
    obj = _proposal(LearningTarget.KNOWLEDGE_SUGGESTION, "subject_left")
    _stuck_the_old_way(engine, obj)
    with engine.begin() as conn:
        conn.execute(text(
            "insert into learning_transitions (id, org_id, learning_id, from_state, to_state, "
            "reason_code, occurred_at) values ('ltr_left', :o, :l, 'human_review', 'rejected', "
            "'rejected', :at)"), {"o": ORG, "l": obj.learning_id, "at": NOW + timedelta(hours=1)})
    with engine.connect() as conn:
        assert RS.stuck(conn, ORG) == []


def test_the_script_names_its_target_and_never_the_configured_database(monkeypatch):
    from scripts._db import TARGET_URL_ENV, UnsafeDatabaseTarget

    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    with pytest.raises(UnsafeDatabaseTarget):
        RS.main(["--org", ORG])

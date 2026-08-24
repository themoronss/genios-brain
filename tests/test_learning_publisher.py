"""Layer 6 · Phase 5 — persistence, publishers and rollback, against real PostgreSQL (rolled back)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningState,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.feedback import publisher

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _obj(org, *, target=LearningTarget.BEHAVIOR, subject="rule_x", value=None,
         scope=VisibilityScope.ORGANIZATION, expires_at=None):
    return LearningObject(
        org_id=org, unit="u", target=target, subject=subject, proposed_value=value or {"v": 1},
        evidence=LearningEvidence(observations=5, independent_refs=3, distinct_days=2, positive=4,
                                  negative=1, confidence_bp=7000),
        visibility=Visibility(scope=scope), first_seen_at=NOW, last_seen_at=NOW,
        policy_key="policy:o:1", expires_at=expires_at)


@pytest.fixture()
def conn():
    try:
        from genios_engine.platform.config import get_settings
        from genios_engine.platform.db import get_engine
        from sqlalchemy import text
        url = get_settings().database_url
        if not url:
            pytest.skip("no database configured")
        c = get_engine(url).connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no live database: {exc}")
    from sqlalchemy import text
    tx = c.begin()
    if not c.execute(text("select to_regclass('public.learned_brain_entries')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0045 not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def test_persist_is_idempotent_and_never_reopens_terminal(conn):
    c, org = conn
    obj = _obj(org)
    assert publisher.persist(c, obj, state=LearningState.OBSERVED, at=NOW) == "inserted"
    assert publisher.persist(c, obj, state=LearningState.OBSERVED, at=NOW) == "reevaluated"
    # move it terminal, then a re-persist is a no-op (cannot reopen)
    from sqlalchemy import text
    c.execute(text("update learning_objects set state='published' where org_id=:o and learning_id=:l"),
              {"o": org, "l": obj.learning_id})
    assert publisher.persist(c, obj, state=LearningState.OBSERVED, at=NOW) == "unchanged"


def test_brain_versions_and_no_material_change(conn):
    c, org = conn
    v1 = _obj(org, value={"tone": "warm"})
    assert publisher.publish_brain(c, v1, at=NOW) == "published_v1"
    # byte-identical re-publish makes no version noise
    assert publisher.publish_brain(c, _obj(org, value={"tone": "warm"}), at=NOW) == "no_material_change"
    # a materially new value supersedes to v2
    assert publisher.publish_brain(c, _obj(org, value={"tone": "firm"}), at=NOW) == "published_v2"


def test_rollback_restores_the_exact_predecessor(conn):
    from sqlalchemy import text
    c, org = conn
    publisher.publish_brain(c, _obj(org, value={"tone": "warm"}), at=NOW)     # v1
    publisher.publish_brain(c, _obj(org, value={"tone": "firm"}), at=NOW)     # v2 active
    result = publisher.rollback_brain(c, org_id=org, brain="behavior", subject="rule_x", at=NOW)
    assert result == "restored_v1"
    active = c.execute(text("select version, value from learned_brain_entries "
                            "where org_id=:o and brain='behavior' and subject='rule_x' and active"),
                       {"o": org}).mappings().first()
    assert active["version"] == 1


def test_rollback_of_a_first_version_goes_to_empty(conn):
    from sqlalchemy import text
    c, org = conn
    publisher.publish_brain(c, _obj(org, value={"tone": "warm"}), at=NOW)     # v1 only
    assert publisher.rollback_brain(c, org_id=org, brain="behavior", subject="rule_x", at=NOW) \
        == "rolled_back_to_empty"
    n = c.execute(text("select count(*) from learned_brain_entries "
                       "where org_id=:o and subject='rule_x' and active"), {"o": org}).scalar()
    assert n == 0


def test_metric_identity_conflict_is_not_a_false_publish(conn):
    c, org = conn
    m = _obj(org, target=LearningTarget.METRICS, subject="channel:slack")
    assert publisher.publish_metric(c, m, at=NOW) == "metric_published"
    assert publisher.publish_metric(c, m, at=NOW) == "metric_identity_conflict"


def test_knowledge_stops_at_review_expert_untouched(conn):
    from sqlalchemy import text
    c, org = conn
    k = _obj(org, target=LearningTarget.KNOWLEDGE_SUGGESTION, subject="play:x")
    assert publisher.publish_knowledge(c, k, at=NOW) == "knowledge_review"
    state = c.execute(text("select state from knowledge_suggestions where org_id=:o and subject='play:x'"),
                      {"o": org}).scalar()
    assert state == "human_review"


def test_runtime_publishes_a_temporary_lease(conn):
    from sqlalchemy import text
    c, org = conn
    r = _obj(org, target=LearningTarget.RUNTIME, subject="ctx:x", scope=VisibilityScope.PRIVATE,
             expires_at=NOW + timedelta(hours=1))
    assert publisher.publish_runtime(c, r, at=NOW) == "temporary_published"
    n = c.execute(text("select count(*) from temporary_memories where org_id=:o and subject='ctx:x' and active"),
                  {"o": org}).scalar()
    assert n == 1

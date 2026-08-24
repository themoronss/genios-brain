"""Layer 6 · consumer seam — production-grade safety, against real PostgreSQL (rolled back)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.learning import (
    BrainTarget,
    LearningEvidence,
    LearningObject,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.feedback import publisher
from genios_engine.feedback.consumer import CONSUMER_ALLOWLIST, may_consume, snapshot

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def test_allowlist_gates_each_consumer():
    assert may_consume("context", BrainTarget.ORGANIZATION) is True
    assert may_consume("context", BrainTarget.BEHAVIOR) is False     # not on context's allowlist
    assert may_consume("delivery", BrainTarget.RUNTIME) is True
    assert may_consume("unknown", BrainTarget.ORGANIZATION) is False


def _obj(org, *, target, subject, value, scope=VisibilityScope.ORGANIZATION,
         principals=(), expires_at=None):
    return LearningObject(
        org_id=org, unit="u", target=target, subject=subject, proposed_value=value,
        evidence=LearningEvidence(observations=5, independent_refs=3, distinct_days=2, positive=4,
                                  negative=1, confidence_bp=7000),
        visibility=Visibility(scope=scope, principals=tuple(principals)),
        first_seen_at=NOW, last_seen_at=NOW, policy_key="policy:o:1", expires_at=expires_at)


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


def test_reads_only_the_active_version_and_reflects_rollback(conn):
    c, org = conn
    publisher.publish_brain(c, _obj(org, target=LearningTarget.ORGANIZATION, subject="rule_z",
                                    value={"v": "one"}), at=NOW)
    publisher.publish_brain(c, _obj(org, target=LearningTarget.ORGANIZATION, subject="rule_z",
                                    value={"v": "two"}), at=NOW)
    snap = snapshot(c, org_id=org, consumer="context", subject="rule_z", now=NOW)
    assert snap.brain("organization") == {"v": "two"}          # active version only
    publisher.rollback_brain(c, org_id=org, brain="organization", subject="rule_z", at=NOW)
    snap2 = snapshot(c, org_id=org, consumer="context", subject="rule_z", now=NOW)
    assert snap2.brain("organization") == {"v": "one"}         # rollback reflected immediately


def test_a_disallowed_brain_is_not_readable_even_if_published(conn):
    c, org = conn
    publisher.publish_brain(c, _obj(org, target=LearningTarget.BEHAVIOR, subject="rule_z",
                                    value={"tone": "warm"}), at=NOW)
    # context is not allowed to read the behavior brain
    assert snapshot(c, org_id=org, consumer="context", subject="rule_z", now=NOW).brain("behavior") is None
    # executive is
    assert snapshot(c, org_id=org, consumer="executive", subject="rule_z", now=NOW).brain("behavior") == {"tone": "warm"}


def test_expired_runtime_memory_is_not_read(conn):
    c, org = conn
    live = _obj(org, target=LearningTarget.RUNTIME, subject="ctx_z", value={"hint": "x"},
                scope=VisibilityScope.ORGANIZATION, expires_at=NOW + timedelta(hours=1))
    publisher.publish_runtime(c, live, at=NOW)
    assert snapshot(c, org_id=org, consumer="delivery", subject="ctx_z", now=NOW).runtime.get("ctx_z") == {"hint": "x"}
    # once the TTL passes, the same read returns nothing (fail-closed on time)
    assert snapshot(c, org_id=org, consumer="delivery", subject="ctx_z",
                    now=NOW + timedelta(hours=2)).runtime == {}


def test_private_value_needs_the_viewer_among_principals(conn):
    c, org = conn
    publisher.publish_brain(c, _obj(org, target=LearningTarget.BEHAVIOR, subject="rule_z",
                                    value={"p": 1}, scope=VisibilityScope.PRIVATE,
                                    principals=("seat_a",)), at=NOW)
    # a viewer not in principals cannot see it
    assert snapshot(c, org_id=org, consumer="executive", subject="rule_z", now=NOW,
                    viewer_principals={"seat_b"}).brain("behavior") is None
    # the authorised viewer can
    assert snapshot(c, org_id=org, consumer="executive", subject="rule_z", now=NOW,
                    viewer_principals={"seat_a"}).brain("behavior") == {"p": 1}


def test_no_learned_value_is_a_deterministic_empty_fallback(conn):
    c, org = conn
    snap = snapshot(c, org_id=org, consumer="reasoning", subject="never_learned", now=NOW)
    assert snap.is_empty and snap.brain("organization") is None

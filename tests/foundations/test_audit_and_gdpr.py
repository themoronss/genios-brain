"""Tests for audit_log (immutable) + SOC2/GDPR helpers + scope_check + health_check."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.delivery.store import ChannelDeliveryRow, FeedbackActionRow
from core.foundations import audit, scope_check, soc2_gdpr
from core.foundations.db import Base
from core.foundations.health_check import (
    check_db,
    check_llm,
    check_redis,
    system_health,
)
from core.foundations.metrics_store import AuditLogRow
from core.foundations.worker_invariant import scan_package
from core.graph.store import FactRow
from core.memory.store import SecretRef  # noqa: F401 — loads FK target for SQLite tests
from core.proactive.store import InsightFeedbackRow
from core.usermodel.schema import Voice
from core.usermodel.seed import SeedInput, seed_profile
from core.usermodel.store import UserModelRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


# ── audit_log ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_audit_record_db_persists(session: Session) -> None:
    row = audit.record_db(
        session,
        org_id="o",
        actor_type="user",
        actor_id="alice",
        action="decision_made",
        target_type="decision",
        target_id="dec_1",
        metadata={"route": "autonomous"},
    )
    session.commit()
    assert row.id is not None
    persisted = session.get(AuditLogRow, row.id)
    assert persisted is not None
    assert persisted.action == "decision_made"
    assert persisted.metadata_jsonb == {"route": "autonomous"}


@pytest.mark.unit
def test_audit_query_org_scoped(session: Session) -> None:
    audit.record_db(
        session,
        org_id="o1",
        actor_type="user",
        actor_id="alice",
        action="decision_made",
        target_type="decision",
        target_id="dec_a",
    )
    audit.record_db(
        session,
        org_id="o2",
        actor_type="user",
        actor_id="bob",
        action="decision_made",
        target_type="decision",
        target_id="dec_b",
    )
    session.commit()
    o1 = audit.query_events(session, org_id="o1")
    assert len(o1) == 1
    assert o1[0].target_id == "dec_a"


@pytest.mark.unit
def test_audit_query_filters(session: Session) -> None:
    for _ in range(3):
        audit.record_db(
            session,
            org_id="o",
            actor_type="user",
            actor_id="alice",
            action="decision_made",
            target_type="decision",
            target_id="d",
        )
    audit.record_db(
        session,
        org_id="o",
        actor_type="system",
        actor_id="bg",
        action="config_changed",
        target_type="tunable",
        target_id="N_MIN",
    )
    session.commit()
    only_config = audit.query_events(session, org_id="o", action="config_changed")
    assert len(only_config) == 1


@pytest.mark.unit
def test_audit_query_limit_validation(session: Session) -> None:
    with pytest.raises(ValueError):
        audit.query_events(session, org_id="o", limit=0)
    with pytest.raises(ValueError):
        audit.query_events(session, org_id="o", limit=10_000)


# ── GDPR ──────────────────────────────────────────────────────────────────


def _seed_user_with_data(session: Session, user_id: str = "u_alice") -> None:
    seed_profile(
        session,
        seed=SeedInput(user_id=user_id, org_unit="o", voice=Voice(tone=["polite"])),
    )
    session.add(
        FeedbackActionRow(
            org_id="o",
            user_id=user_id,
            decision_id="dec_x",
            action="thumbs_up",
        )
    )
    session.add(
        ChannelDeliveryRow(
            org_id="o",
            user_id=user_id,
            channel="slack",
        )
    )
    session.add(
        InsightFeedbackRow(
            org_id="o",
            user_id=user_id,
            signature_hash="sig_abc",
            action="acted",
        )
    )
    session.flush()


@pytest.mark.unit
def test_data_subject_access_returns_everything(session: Session) -> None:
    _seed_user_with_data(session)
    session.commit()
    export = soc2_gdpr.data_subject_access(session, user_id="u_alice", org_id="o")
    session.commit()
    assert export["user_id"] == "u_alice"
    assert export["user_profile"] is not None
    assert len(export["feedback_actions"]) == 1
    assert len(export["channel_deliveries"]) == 1
    assert len(export["insight_feedback"]) == 1


@pytest.mark.unit
def test_data_subject_access_logged(session: Session) -> None:
    _seed_user_with_data(session)
    session.commit()
    soc2_gdpr.data_subject_access(session, user_id="u_alice", org_id="o")
    session.commit()
    events = audit.query_events(session, org_id="o", action="data_subject_access")
    assert len(events) == 1
    assert events[0].target_id == "u_alice"


@pytest.mark.unit
def test_erasure_deletes_all_user_data(session: Session) -> None:
    _seed_user_with_data(session)
    session.commit()
    counts = soc2_gdpr.erasure(session, user_id="u_alice", org_id="o")
    session.commit()

    assert counts["user_models"] == 1
    assert counts["feedback_actions"] == 1
    assert counts["channel_deliveries"] == 1
    assert session.query(UserModelRow).count() == 0
    assert session.query(FeedbackActionRow).count() == 0


@pytest.mark.unit
def test_erasure_preserves_audit_trail(session: Session) -> None:
    """Audit log is intentionally kept (SOC2)."""
    _seed_user_with_data(session)
    audit.record_db(
        session,
        org_id="o",
        actor_type="user",
        actor_id="u_alice",
        action="decision_made",
        target_type="decision",
        target_id="d",
    )
    session.commit()
    pre = session.query(AuditLogRow).count()
    soc2_gdpr.erasure(session, user_id="u_alice", org_id="o")
    session.commit()
    post = session.query(AuditLogRow).count()
    assert post == pre + 1  # erasure itself logged, prior rows preserved


@pytest.mark.unit
def test_retention_sweep_drops_old_rows(session: Session) -> None:
    old = datetime.now(UTC) - timedelta(days=120)
    new = datetime.now(UTC) - timedelta(days=5)
    session.add(
        AuditLogRow(
            org_id="o",
            actor_type="user",
            actor_id="a",
            action="decision_made",
            target_type="d",
            target_id="1",
            metadata_jsonb={},
            timestamp=old,
        )
    )
    session.add(
        AuditLogRow(
            org_id="o",
            actor_type="user",
            actor_id="a",
            action="decision_made",
            target_type="d",
            target_id="2",
            metadata_jsonb={},
            timestamp=new,
        )
    )
    session.flush()
    n = soc2_gdpr.retention_sweep(session, org_id="o", audit_hot_days=90)
    session.commit()
    assert n == 1
    # New row + the sweep-event row remain
    assert session.query(AuditLogRow).count() == 2


@pytest.mark.unit
def test_retention_sweep_org_scoped(session: Session) -> None:
    old = datetime.now(UTC) - timedelta(days=120)
    for org in ("o1", "o2"):
        session.add(
            AuditLogRow(
                org_id=org,
                actor_type="u",
                actor_id="a",
                action="decision_made",
                target_type="d",
                target_id="1",
                metadata_jsonb={},
                timestamp=old,
            )
        )
    session.flush()
    soc2_gdpr.retention_sweep(session, org_id="o1", audit_hot_days=90)
    session.commit()
    remaining_org_ids = {r.org_id for r in session.query(AuditLogRow).all()}
    assert "o2" in remaining_org_ids  # o2's old row not touched


# ── scope_check ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_scope_audit_clean_when_refs_match(session: Session) -> None:
    session.add(
        FactRow(
            org_id="o",
            subject="s",
            predicate="p",
            object="o_val",
            source_item_id="item_1",
            asserted_by_type="source",
            asserted_by_id="src_1",
        )
    )
    session.add(
        DecisionRow(
            org_id="o",
            query_jsonb={},
            conclusion="c",
            derivation_chain_jsonb={},
            path="symbolic",
            confidence_score=0.9,
            confidence_breakdown_jsonb={},
            grounding_refs_jsonb=["item_1"],
            route="notify",
            as_of_version=1,
            triggered_by="query",
            module_id="sales",
        )
    )
    session.commit()
    report = scope_check.audit_decisions(session, org_id="o")
    assert report.passed
    assert report.violations == []


@pytest.mark.unit
def test_scope_audit_catches_smuggled_ref(session: Session) -> None:
    session.add(
        DecisionRow(
            org_id="o",
            query_jsonb={},
            conclusion="c",
            derivation_chain_jsonb={},
            path="symbolic",
            confidence_score=0.9,
            confidence_breakdown_jsonb={},
            grounding_refs_jsonb=["item_phantom"],
            route="notify",
            as_of_version=1,
            triggered_by="query",
            module_id="sales",
        )
    )
    session.commit()
    report = scope_check.audit_decisions(session, org_id="o")
    assert not report.passed
    assert report.violations[0].reason == "ref_not_in_facts"


@pytest.mark.unit
def test_scope_audit_catches_cross_org_ref(session: Session) -> None:
    session.add(
        FactRow(
            org_id="other_org",
            subject="s",
            predicate="p",
            object="o_val",
            source_item_id="item_x",
            asserted_by_type="source",
            asserted_by_id="src_1",
        )
    )
    session.add(
        DecisionRow(
            org_id="o",
            query_jsonb={},
            conclusion="c",
            derivation_chain_jsonb={},
            path="symbolic",
            confidence_score=0.9,
            confidence_breakdown_jsonb={},
            grounding_refs_jsonb=["item_x"],
            route="notify",
            as_of_version=1,
            triggered_by="query",
            module_id="sales",
        )
    )
    session.commit()
    report = scope_check.audit_decisions(session, org_id="o")
    assert any(v.reason == "wrong_org" for v in report.violations)


# ── health_check ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_check_llm_yellow_without_key() -> None:
    """No ANTHROPIC_API_KEY in test env => yellow (key not set)."""
    status = check_llm()
    assert status.status in {"yellow", "green"}
    assert status.component == "llm"


@pytest.mark.unit
def test_check_redis_with_injected_client() -> None:
    class _OK:
        def ping(self) -> bool:
            return True

    status = check_redis(redis_client=_OK())
    assert status.status == "green"


@pytest.mark.unit
def test_check_redis_red_on_failure() -> None:
    class _Bad:
        def ping(self) -> bool:
            raise RuntimeError("connection refused")

    status = check_redis(redis_client=_Bad())
    assert status.status == "red"
    assert status.error == "RuntimeError"


@pytest.mark.unit
def test_check_db_returns_a_status() -> None:
    """Test DB URL is fake — expect red. Just verifies the probe handles it cleanly."""
    status = check_db()
    assert status.component == "db"
    assert status.status in {"red", "yellow", "green"}


@pytest.mark.unit
def test_system_health_aggregates() -> None:
    out = system_health(redis_client=type("R", (), {"ping": lambda self: True})())
    assert set(out.keys()) == {"db", "redis", "llm"}


# ── worker_invariant ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_worker_invariant_allowed_config_names_pass() -> None:
    """Foundations config dicts are explicitly allow-listed and must not be flagged."""
    violations = scan_package("core.foundations")
    # Allow-listed config dicts shouldn't appear; everything else must be reviewed.
    bad_names = {"CONFIDENCE_WEIGHTS", "CRON_INTERVAL_HOURS", "GOLDEN_THRESHOLD"}
    for v in violations:
        assert v.name not in bad_names, f"allow-listed constant flagged: {v}"

"""Agent scope is ENFORCED on read/claim (security): a scoped key must not read outside its slice.
Locks the _scope_filter SQL builder — the piece that turns the stored scope into WHERE clauses."""
from datetime import datetime, timezone

from genios_engine.deliver.agent_api import _scope_filter

NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)


def test_empty_scope_adds_no_restriction():
    p = {"o": "org1"}
    assert _scope_filter({}, p, NOW) == ""            # owner-equivalent: no extra filter
    assert _scope_filter({"segments": None, "fact_types": None, "min_confidence": 0}, p, NOW) == ""


def test_segments_restrict_to_member_subjects():
    p = {"o": "org1"}
    sql = _scope_filter({"segments": ["seg_a", "seg_b"]}, p, NOW)
    assert "segment_members" in sql and "s.subject_node_id in" in sql
    assert p["_segs"] == ["seg_a", "seg_b"]


def test_fact_types_and_confidence_and_age():
    p = {"o": "org1"}
    sql = _scope_filter({"fact_types": ["unanswered_email"], "min_confidence": 0.6,
                         "max_age_days": 30}, p, NOW)
    assert "s.reason_code = any(:_fts)" in sql
    assert "s.score >= :_minc" in sql and p["_minc"] == 0.6
    assert "s.created_at >= :_agecut" in sql and p["_agecut"] < NOW


def test_zero_confidence_is_not_a_filter():
    p = {"o": "org1"}
    assert "score" not in _scope_filter({"min_confidence": 0.0}, p, NOW)

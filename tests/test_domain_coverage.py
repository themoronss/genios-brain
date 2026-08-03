from __future__ import annotations

from genios_engine.capture.coverage.model import compute_coverage
from genios_engine.capture.domain.hints import domain_hints


def test_domain_hint_from_source_prior():
    hints = domain_hints("hubspot", None)
    assert any(h.domain == "sales" and h.source == "scope" for h in hints)


def test_domain_hint_from_keyword():
    hints = domain_hints("gmail", "your invoice is overdue, please pay GST")
    assert any(h.domain == "admin" and h.source == "keyword" for h in hints)


def test_coverage_ready_when_required_fresh():
    cov = compute_coverage("sales", {"communication": "fresh", "crm": "fresh"})
    assert cov["coverage_ready"] is True
    assert cov["readiness"]["can_evaluate_no_reply"] is True


def test_coverage_not_ready_and_absence_not_negative():
    # calendar not connected → can_evaluate_no_meeting is False (don't conclude "no meeting")
    cov = compute_coverage("sales", {"communication": "fresh"})   # crm missing
    assert cov["coverage_ready"] is False
    assert "crm" in cov["missing_required"]
    assert cov["readiness"]["can_evaluate_no_meeting"] is False

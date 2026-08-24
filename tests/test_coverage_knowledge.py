from __future__ import annotations

from genios_engine.capture.coverage.model import compute_coverage

# The coverage dashboard derived readiness only from connected APPS, so written company knowledge
# (policies/pricing/SOPs) was invisible — it showed "not connected" no matter how much was written.
# Knowledge is now surfaced as its own non-app dimension, WITHOUT faking live-signal capabilities.


def test_written_knowledge_is_surfaced_as_evidence():
    cov = compute_coverage("sales", {}, company_knowledge_count=3)
    assert cov["company_knowledge"] == {"present": True, "count": 3}
    assert cov["readiness"]["has_company_canon"] is True


def test_no_knowledge_is_reported_honestly():
    cov = compute_coverage("sales", {})
    assert cov["company_knowledge"] == {"present": False, "count": 0}
    assert cov["readiness"]["has_company_canon"] is False


def test_knowledge_does_not_fake_app_capabilities():
    # writing policies must NOT make sales 'ready' — crm/communication still need real connected apps
    cov = compute_coverage("sales", {}, company_knowledge_count=10)
    assert cov["coverage_ready"] is False
    assert "crm" in cov["missing_required"]

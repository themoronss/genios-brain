from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.connectors.fake import FakeGmailConnector
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event


def _fake_raw():
    return FakeGmailConnector().incremental_changes().objects[0]


def test_full_pipeline_emits_gated_event_with_full_trace():
    repo = InMemorySourceEventRepository()
    res = capture_event(_fake_raw(), org_id="o", connection_id="c", repo=repo)

    assert res.outcome == "emitted"
    assert res.gated is not None
    assert res.gated.route == "needs_extraction"
    assert res.gated.triage_lane in {"P0", "P1", "P2", "P3"}
    # trace shows every L1 stage in order
    stages = [r.stage for r in res.trace.records]
    assert stages == ["landing", "preprocess", "S0", "S1", "S2", "triage", "emit"]


def test_duplicate_stops_at_landing():
    repo = InMemorySourceEventRepository()
    capture_event(_fake_raw(), org_id="o", connection_id="c", repo=repo)
    res2 = capture_event(_fake_raw(), org_id="o", connection_id="c", repo=repo)
    assert res2.outcome == "duplicate"
    assert res2.gated is None
    assert [r.stage for r in res2.trace.records] == ["landing"]


class _DropClassifier:
    """Stub S2 LLM junk-gate that drops (stands in for the real LLM in a hermetic test)."""

    def classify(self, ctx, prepared):
        from genios_engine.capture.gate.relevance import RelevanceVerdict
        return RelevanceVerdict(False, 0.1, disposition="drop", reason="marketing")


def test_noise_dropped_before_extraction():
    # Rules-first junk removal: an automated/bulk no-reply sender with no attachment is dropped
    # deterministically at S1 (N-03) BEFORE L2, so it never costs an LLM gate or extraction call.
    # A receipt/invoice from noreply@ carries a PDF and is exempted by has_attachment.
    raw = RawObject(source="gmail", object_type="email_message",
                    source_object_id="m_noise",
                    occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
                    actor_email="no-reply@promo.io",
                    raw={"subject": "Sale!", "snippet": "50% off this week"})
    repo = InMemorySourceEventRepository()
    res = capture_event(raw, org_id="o", connection_id="c", repo=repo,
                        relevance=_DropClassifier())
    assert res.outcome == "dropped"
    assert res.gated is None
    assert res.trace.records[-1].reason_code == "N-03"


def test_structured_event_emits_structured_route():
    raw = RawObject(source="hubspot", object_type="deal",
                    source_object_id="deal_9912",
                    occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
                    actor_type="system",
                    raw={})
    repo = InMemorySourceEventRepository()
    res = capture_event(raw, org_id="o", connection_id="c", repo=repo,
                        is_structured=True, structured_fields={"deal.stage": "proposal"})
    assert res.outcome == "emitted"
    assert res.gated.route == "structured"
    assert res.gated.structured_fields == {"deal.stage": "proposal"}
    # structured skips preprocess + email N-codes
    assert [r.stage for r in res.trace.records] == ["landing", "S0", "S1.5", "triage", "emit"]

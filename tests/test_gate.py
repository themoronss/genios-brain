from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace


def _event(email: str, actor_type: str = "external_contact") -> SourceEvent:
    return SourceEvent(
        event_id="evt_x", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type=actor_type, email=email), occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )


def _trace() -> EventTrace:
    return EventTrace(org_id="o", event_id="evt_x")


def test_business_email_routes_to_extraction():
    ctx = GateContext(event=_event("priya@acme.com"),
                      raw={"subject": "Revised contract",
                           "snippet": "Can you send the contract by Friday?"})
    tr = _trace()
    res = run_gate(ctx, tr)
    assert res.action == "route" and res.route == "needs_extraction"
    assert [r.stage for r in tr.records] == ["S0", "S1", "S2"]


def test_no_reply_sender_dropped_at_s1():
    ctx = GateContext(event=_event("no-reply@newsletter.com"),
                      raw={"subject": "Weekly digest", "snippet": "..."})
    tr = _trace()
    res = run_gate(ctx, tr)
    assert res.action == "drop" and res.reason_code == "N-03"
    assert tr.records[-1].stage == "S1" and tr.records[-1].action.value == "drop"


def test_known_sender_bypasses_bulk_drop():
    # bulk marker present, but sender is known → whitelist W-01 bypasses the drop
    ctx = GateContext(event=_event("news@acme.com"), sender_known=True,
                      raw={"subject": "Product update",
                           "headers": {"List-Unsubscribe": "<mailto:u@acme.com>"},
                           "snippet": "New feature launched."})
    res = run_gate(ctx, _trace())
    assert res.action == "route"


def test_structured_event_with_mapping_short_circuits():
    ev = SourceEvent(
        event_id="evt_d", org_id="o", connection_id="c", source="hubspot",
        object_type="deal", source_object_id="deal_1", dedup_key="hubspot:deal:deal_1",
        actor=Actor(type="system"), occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    tr = _trace()
    res = run_gate(GateContext(event=ev, is_structured=True), tr)
    assert res.action == "short_circuit" and res.route == "structured"
    assert tr.records[-1].reason_code == "structured_mapped"


def test_unknown_structured_type_parks_for_mapping_review():
    ev = SourceEvent(
        event_id="evt_u", org_id="o", connection_id="c", source="weirdapp",
        object_type="thing", source_object_id="t1", dedup_key="weirdapp:thing:t1",
        actor=Actor(type="system"), occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    tr = _trace()
    res = run_gate(GateContext(event=ev, is_structured=True), tr)
    assert res.action == "park" and res.reason_code == "mapping_missing"

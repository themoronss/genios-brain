"""N-05 — an out-of-office / leave / auto-reply message is MARKED and routed, never dropped.

It used to be a subject-line drop, which threw away exactly the message team intelligence needs.
It now reaches L2 with a marker (auto_reply | leave_notice), skips the S2 junk gate (which would
call a responder "automated"), and drains last (P3)."""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.gate.rules import (AUTO_REPLY, LEAVE_NOTICE, availability_marker,
                                              noise_rule)
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace

T = datetime(2026, 9, 10, 9, tzinfo=timezone.utc)


def _event(email: str) -> SourceEvent:
    return SourceEvent(
        event_id="evt_a", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type="external_contact", email=email), occurred_at=T)


class _WouldDrop:
    """An S2 junk gate that calls everything automated. It must never be consulted for N-05."""
    called = False

    def classify(self, ctx, prepared):
        _WouldDrop.called = True
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated")


def _gate(email: str, raw: dict):
    trace = EventTrace(org_id="o", event_id="evt_a")
    _WouldDrop.called = False
    return run_gate(GateContext(event=_event(email), raw=raw), trace, relevance=_WouldDrop()), trace


def test_subject_ooo_is_routed_not_dropped():
    res, trace = _gate("anisha@acme.io", {"subject": "Out of Office: Re: audit docs",
                                           "snippet": "I am on leave till 22nd."})
    assert res.action == "route" and res.route == "needs_extraction"
    assert res.availability == AUTO_REPLY
    assert trace.records[-1].reason_code == "N-05"
    assert _WouldDrop.called is False            # the junk gate never sees a responder


def test_gmail_vacation_responder_header_marks_auto_reply():
    # Gmail keeps the original subject; only the header says a responder wrote it.
    raw = {"subject": "Re: pricing", "snippet": "I'm travelling until Monday.",
           "headers": {"Auto-Submitted": "auto-replied", "Precedence": "bulk"}}
    res, _ = _gate("rohit@acme.io", raw)
    assert res.action == "route" and res.availability == AUTO_REPLY


def test_human_leave_notice_is_a_leave_notice():
    res, _ = _gate("anisha@acme.io", {"subject": "On leave 15-22 Sept",
                                       "snippet": "Priya will cover the audit."})
    assert res.action == "route" and res.availability == LEAVE_NOTICE


def test_hinglish_chutti_subject_is_kept():
    assert availability_marker({"subject": "kal se 3 din chutti"}) == LEAVE_NOTICE


def test_machine_ack_without_ooo_still_drops():
    res, _ = _gate("person@realco.com", {"subject": "Delivery receipt", "snippet": "received",
                                         "headers": {"Auto-Submitted": "auto-generated"}})
    assert res.action == "drop" and res.reason_code == "N-01"


def test_automated_sender_auto_reply_still_drops():
    # a helpdesk "Automatic reply: ticket received" from noreply@ is nobody's leave
    res, _ = _gate("no-reply@helpdesk.io", {"subject": "Automatic reply: ticket #42",
                                             "snippet": "We received your request."})
    assert res.action == "drop" and res.reason_code == "N-03"


def test_body_mention_does_not_mark():
    raw = {"subject": "Contract", "snippet": "Legal is out of office today, will revert."}
    assert availability_marker(raw) is None
    ctx = GateContext(event=_event("priya@acme.io"), raw=raw)
    assert noise_rule(ctx) is None


def test_header_names_are_case_insensitive():
    assert availability_marker({"subject": "Re: x",
                                "headers": {"auto-submitted": "auto-replied"}}) == AUTO_REPLY


def test_capture_emits_marked_event_in_the_last_lane():
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="ooo-1",
                    occurred_at=T, actor_email="anisha@acme.io", actor_type="external_contact",
                    raw={"subject": "Automatic reply: urgent contract", "body": "I am out of "
                         "office until Monday. Urgent? Contact priya@acme.io.", "snippet": ""})
    res = capture_event(raw, org_id="o", connection_id="c", repo=InMemorySourceEventRepository())
    assert res.outcome == "emitted"
    assert res.gated.availability_marker == AUTO_REPLY
    assert res.gated.triage_lane == "P3"          # "urgent" in a responder never preempts real mail

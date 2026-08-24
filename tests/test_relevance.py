from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate.relevance import DeterministicRelevanceClassifier
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event


def _raw(snippet: str, email: str = "someone@unknown.io"):
    return RawObject("gmail", "email_message", f"m_{hash(snippet) & 0xffff}",
                     datetime(2026, 7, 28, tzinfo=timezone.utc),
                     actor_email=email, raw={"snippet": snippet})


def test_relevance_off_by_default_routes_everything_past_gate():
    repo = InMemorySourceEventRepository()
    res = capture_event(_raw("hey lets grab coffee sometime"), org_id="o",
                        connection_id="c", repo=repo)     # no classifier
    assert res.outcome == "emitted"                       # deterministic gate only


def test_relevance_on_parks_non_business_chatter():
    repo = InMemorySourceEventRepository()
    rc = DeterministicRelevanceClassifier()
    res = capture_event(_raw("hey lets grab coffee sometime"), org_id="o",
                        connection_id="c", repo=repo, relevance=rc)
    assert res.outcome == "parked"
    assert res.trace.records[-1].reason_code == "low_relevance"


def test_relevance_on_passes_business_email():
    repo = InMemorySourceEventRepository()
    rc = DeterministicRelevanceClassifier()
    res = capture_event(_raw("can you send the contract and pricing?"), org_id="o",
                        connection_id="c", repo=repo, relevance=rc)
    assert res.outcome == "emitted"
    assert res.trace.records[-1].stage == "emit"


def test_relevance_on_passes_known_sender_regardless():
    repo = InMemorySourceEventRepository()
    rc = DeterministicRelevanceClassifier()
    res = capture_event(_raw("hi", email="priya@acme.com"), org_id="o",
                        connection_id="c", repo=repo, relevance=rc, sender_known=True)
    assert res.outcome == "emitted"

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


def test_a_parked_object_says_WHY_it_was_parked():
    """The park branch used to record `low_relevance` and nothing else.

    MEASURED on production 2026-10-08: 429 of 897 screen objects for one tenant were parked under
    that bare code, so a chat the insight model judged PERSONAL (desirable), a thread it judged not
    worth remembering, and a page no gate could judge (a real gap) were indistinguishable. Half a
    tenant's screen data could not be called right or wrong by anyone.
    """
    from genios_engine.capture.gate.relevance import RelevanceVerdict

    class Judged:
        """A classifier that parks with a NAMED reason, as the screen gate does."""

        def __init__(self, reason: str, relevance: float) -> None:
            self.reason, self.relevance = reason, relevance

        def classify(self, ctx, prepared=None):          # noqa: ARG002 — gate contract
            return RelevanceVerdict(False, self.relevance, disposition="park", reason=self.reason)

    for reason, score in (("insight_personal", 0.30), ("insight_no_memory", 0.35)):
        repo = InMemorySourceEventRepository()
        res = capture_event(_raw("kal milte hain yaar"), org_id="o", connection_id="c",
                            repo=repo, relevance=Judged(reason, score))
        last = res.trace.records[-1]
        assert res.outcome == "parked"
        # The retry class is unchanged — `parked/drain.py` keys on it.
        assert last.reason_code == "low_relevance"
        # …and the reason now travels with it.
        assert last.detail.get("reason") == reason, last.detail
        assert last.detail.get("relevance") == score

    # And the ordinary email gate gains the same thing for free — it always had a reason to give,
    # and this branch was the one place that dropped it.
    repo = InMemorySourceEventRepository()
    res = capture_event(_raw("hey lets grab coffee sometime"), org_id="o", connection_id="c",
                        repo=repo, relevance=DeterministicRelevanceClassifier())
    assert res.trace.records[-1].detail.get("reason") == "no_business_signal"

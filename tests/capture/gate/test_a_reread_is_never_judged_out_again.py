"""STEP-05 · a re-read is of a mail already kept — the gate reads it and never judges it out again.

    pytest tests/capture/gate/test_a_reread_is_never_judged_out_again.py -q

`capture/gate/gate.run_gate` (tree `yc2_w27_s05 · M23.C4.L-logic.V1.U05`). Every recovery path flipped a
row to `emitted` and nothing read it (`speedrun008/YC-II W27/` STEP-05 §8.2); STEP-05 re-reads it through
the capture door (`capture/landing/unread`). That door runs the gate — and the gate re-asked the question
the recovery had already answered: a park re-admitted for `low_relevance` met the classifier that parked
it, and an archive promoted out of N-02 met the unsubscribe rule that archived it. A re-read carries
`rereading` (why it is read again), the gate whitelists it as W-06 and skips its two JUDGMENTS — the noise
rules (S1b) and the relevance classifier (S2). Every check that is not a judgment about keeping the mail
still applies: scope, versionability, provenance, the structured route, whether it can be read at all,
and the availability notice.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace

_BODY = {"subject": "Intro: Pankaj, meet the founder", "snippet": "Happy to connect you both."}
_UNSUBSCRIBE = {**_BODY, "headers": {"List-Unsubscribe": "<mailto:u@boardy.test>"}}


def _event(email: str = "intros@boardy.test") -> SourceEvent:
    return SourceEvent(
        event_id="evt_r", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type="external_contact", email=email),
        occurred_at=datetime(2026, 10, 6, tzinfo=timezone.utc))


def _run(raw: dict, *, rereading: str | None, relevance=None, email="intros@boardy.test", **ctx):
    trace = EventTrace(org_id="o", event_id="evt_r")
    result = run_gate(GateContext(event=_event(email), raw=raw, rereading=rereading, **ctx),
                      trace, relevance=relevance)
    return result, trace


class _Classifier:
    def __init__(self, disposition: str, relevance: float = 0.1) -> None:
        self.disposition, self.relevance, self.asked = disposition, relevance, 0

    def classify(self, ctx, prepared):
        self.asked += 1
        return RelevanceVerdict(False, self.relevance, disposition=self.disposition,
                                reason="marketing")


def test_a_promoted_archive_is_not_archived_again_by_its_own_rule():
    result, trace = _run(_UNSUBSCRIBE, rereading="promoted:N-02")
    assert (result.action, result.route, result.whitelist_code) == ("route", "needs_extraction",
                                                                    "W-06")
    s1 = next(r for r in trace.records if r.stage == "S1")
    assert (s1.action.value, s1.detail.get("rereading")) == ("pass", "promoted:N-02")


@pytest.mark.parametrize("disposition, relevance", [("drop", 0.1), ("drop", 0.4), ("park", 0.2)])
def test_a_readmitted_park_never_meets_the_classifier_again(disposition, relevance):
    model = _Classifier(disposition, relevance)
    result, _ = _run(_BODY, rereading="readmitted:low_relevance", relevance=model)
    assert (result.action, result.route) == ("route", "needs_extraction")
    assert model.asked == 0, "a re-read was judged again"


def test_the_same_mail_not_being_reread_is_still_judged():
    """The control: without `rereading` the rule and the model decide exactly as before."""
    assert _run(_UNSUBSCRIBE, rereading=None)[0].action == "archive"
    model = _Classifier("drop", 0.1)
    assert _run(_BODY, rereading=None, relevance=model)[0].action == "archive"
    assert model.asked == 1


@pytest.mark.parametrize("raw, ctx, verdict", [
    ({**_BODY, "document": {"status": "fetch_failed"}}, {}, ("park", "DOC-05")),   # unreadable
    ({"subject": "Re:", "snippet": ""}, {}, ("archive", "N-10")),                   # nothing to read
    (_BODY, {"in_scope": False}, ("drop", "out_of_scope")),                         # scope
])
def test_what_is_not_a_judgment_about_keeping_still_applies(raw, ctx, verdict):
    result, _ = _run(raw, rereading="extraction_never_ran", **ctx)
    assert (result.action, result.reason_code) == verdict


def test_an_availability_notice_keeps_its_marker():
    raw = {"subject": "Out of office: back Monday",
           "snippet": "I am on leave until Monday with limited access to email.",
           "headers": {"Auto-Submitted": "auto-replied"}}
    result, _ = _run(raw, rereading="readmitted:low_relevance", email="ira@northwind.test")
    assert result.action == "route" and result.availability is not None


def test_a_reread_is_never_primed_for_the_classifier():
    """The page priming batches S2 for a page; a re-read never reaches S2, so it is not a
    candidate — a primed re-read would buy a model call nothing reads."""
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.capture.pipeline import prime_relevance_page

    primed: list = []

    class _Page:
        def prime(self, candidates, **_kw):
            primed.extend(c.page_key for c in candidates)

    semantic = type("S", (), {"relevance_page": _Page()})()
    at = datetime(2026, 10, 6, tzinfo=timezone.utc)
    objects = [RawObject(source="gmail", object_type="email_message", source_object_id="new",
                         occurred_at=at, raw=_BODY),
               RawObject(source="gmail", object_type="email_message", source_object_id="again",
                         occurred_at=at, raw=_BODY, rereading="extraction_never_ran")]
    prime_relevance_page(objects, semantic)
    assert primed == ["new"]

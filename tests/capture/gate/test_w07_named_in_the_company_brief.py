"""STEP-07 · a sender the founder's company brief names is kept, and the gate says why: W-07.

    pytest tests/capture/gate/test_w07_named_in_the_company_brief.py -q

Tree `yc2_w27_s07 · M25.C4.L-logic.V1.U01`. The portal's status mail sits on Gmail's Promotions label
(N-06), the intro agent's carries an unsubscribe header (N-02), and the AI filter, asked about either,
answers "automated" (`speedrun008/YC-II W27/` STEP-07 §8.1, golden F01–F03, F09). When the brief names
the sender — a connector's address, a key person's, a watchlist domain — the gate whitelists it as
W-07, ahead of W-01, and neither noise rule nor classifier judges it. Every check that is not a
judgment about keeping the mail still applies: whether it can be read at all comes first.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.attention import DEEP, attention_for
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.gate.rules import REASON_LABELS, whitelist
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace

_PROMOTIONS = {"subject": "Application SSR-2026-48213: status updated",
               "snippet": "Your application has moved to the stage: Under Examination.",
               "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"]}
_UNSUBSCRIBE = {"subject": "Intro: meet Kestrel Capital", "snippet": "Happy to connect you both.",
                "headers": {"List-Unsubscribe": "<mailto:unsubscribe@introly.test>"}}


def _event(email: str) -> SourceEvent:
    return SourceEvent(
        event_id="evt_w7", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type="external_contact", email=email),
        occurred_at=datetime(2026, 9, 24, tzinfo=timezone.utc))


class _Junk:
    """A classifier that would archive anything it is asked about."""

    def __init__(self) -> None:
        self.asked = 0

    def classify(self, ctx, prepared):
        self.asked += 1
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated")


def _run(raw, email, **ctx):
    trace = EventTrace(org_id="o", event_id="evt_w7")
    junk = _Junk()
    result = run_gate(GateContext(event=_event(email), raw=raw, **ctx), trace, relevance=junk)
    return result, trace, junk


def test_w07_has_a_label():
    assert REASON_LABELS["W-07"] == "named_in_company_brief"


def test_the_brief_comes_before_the_known_sender():
    ctx = GateContext(event=_event("updates@startupsetu.gov.test"), sender_known=True,
                      named_in_brief="watchlist:startupsetu.gov.test")
    assert whitelist(ctx) == "W-07"
    assert whitelist(GateContext(event=_event("x@y.test"), sender_known=True)) == "W-01"


def test_a_watchlisted_portal_on_promotions_is_kept_and_read():
    result, trace, junk = _run(_PROMOTIONS, "updates@startupsetu.gov.test", sender_known=True,
                               named_in_brief="watchlist:startupsetu.gov.test")
    assert (result.action, result.route, result.whitelist_code) == ("route", "needs_extraction",
                                                                    "W-07")
    assert junk.asked == 0, "the founder named the sender; the AI filter does not judge it"
    s1 = next(r for r in trace.records if r.stage == "S1")
    assert (s1.action, s1.detail.get("whitelist")) == ("pass", "W-07")
    assert s1.detail.get("named_in_brief") == "watchlist:startupsetu.gov.test"
    assert attention_for("emitted", result) == (DEEP, "W-07")


def test_a_named_connectors_unsubscribe_header_does_not_archive_it():
    result, _trace, junk = _run(_UNSUBSCRIBE, "hello@introly.test", sender_known=True,
                                named_in_brief="connector:hello@introly.test")
    assert (result.action, result.whitelist_code) == ("route", "W-07") and junk.asked == 0


def test_without_the_brief_the_same_mail_is_archived_as_before():
    result, _trace, _junk = _run(_PROMOTIONS, "updates@startupsetu.gov.test")
    assert (result.action, result.reason_code) == ("archive", "N-06")


def test_whether_it_can_be_read_still_comes_first():
    unreadable = {**_PROMOTIONS, "document": {"status": "unsupported"}}
    result, _trace, _junk = _run(unreadable, "updates@startupsetu.gov.test", sender_known=True,
                                 named_in_brief="watchlist:startupsetu.gov.test")
    assert (result.action, result.reason_code) == ("park", "DOC-02")

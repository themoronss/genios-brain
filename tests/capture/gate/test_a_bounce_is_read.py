"""STEP-10 · a delivery report the gate keeps is also READ — the junk filter never judges it out.

    GENIOS_TEST_DATABASE_URL=… pytest tests/capture/gate/test_a_bounce_is_read.py -q

`capture/gate/gate.run_gate` (tree `yc2_w27_s10 · M29.C3.L-logic.V0.U04`, `06` D38). STEP-10's first cut
kept a report `capture/delivery_status.is_delivery_status` recognises out of N-01 … N-04
(`test_a_bounce_is_kept.py`), and the gate's very next step undid it: S2 asked the model junk filter,
whose prompt says to drop automated mail — golden F16's report, whose recorded read is "drop", was
archived at S2 as `llm_junk` instead of at N-03, and production's filter called all five real bounces
junk. An archived report reaches memory without its payload, so `context/delivery` wrote nothing for
it. Now S2 never judges a report the parser recognises — exactly as it already skips a re-read
(STEP-05) and a sender the company brief names (STEP-07) — and the report is routed to be read like
any kept mail, a delay notice as much as a failure. The question is asked once, by
`gate/rules.is_a_delivery_report`, of the three inputs `capture/pipeline._delivery_status` hands the
parser, so the rule that keeps a report and the step that reads it cannot disagree. What does not
change: a person forwarding a bounce is still judged by the filter, and an ordinary machine mail is
still archived at S1.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.gate.rules import is_a_delivery_report, noise_rule
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace

#: Golden F16's report, as its case spec has it (`tests/replays/specs/founder/F16.json`): a daemon,
#: no headers, no attachment, Gmail's sentence.
GOLDEN_DAEMON = "mailer-daemon@mailhost.test"
GOLDEN = {"subject": "Delivery Status Notification (Failure)",
          "body": "Address not found\n\nYour message wasn't delivered to "
                  "partners@lattice-capital.test because the domain lattice-capital.test couldn't "
                  "be found. Check for typos or unnecessary spaces and try again.",
          "labelIds": ["INBOX"]}

#: Production's: Gmail's daemon, its envelope, the original attached. The body leaves out Gmail's
#: `** Address not found **` headline, so only the SUBJECT names the report.
DAEMON = "mailer-daemon@googlemail.com"
PRODUCTION = {"subject": "Delivery Status Notification (Failure)",
              "body": "Your message wasn't delivered to madison@afore.vc because the address "
                      "couldn't be found or is unable to receive email.",
              "headers": {"Auto-Submitted": "auto-replied", "Precedence": "bulk"},
              "has_attachment": True, "labelIds": ["INBOX"]}

#: Surge's: still being retried. Not a failure — and still read, because whether delivery FAILED
#: is the reader's question (`context/delivery`), not the gate's.
DELAY = {"subject": "Delivery Status Notification (Delay)",
         "body": "There was a temporary problem delivering your message to apply@surgeahead.com. "
                 "Gmail will retry for 47 more hours.",
         "headers": {"Auto-Submitted": "auto-replied"}, "labelIds": ["INBOX"]}

#: A colleague forwarding a bounce: the words without the thing (`capture/delivery_status`'s own
#: example). No list or machine header, so it passes S1 and meets the filter like any mail.
FORWARD = {"subject": "Fwd: Delivery Status Notification (Failure)",
           "body": "Can you resend this one?\n\n---------- Forwarded message ----------\n"
                   "Your message wasn't delivered to partners@lattice-capital.test because the "
                   "address couldn't be found.",
           "labelIds": ["INBOX"]}


class _Junk:
    """The S2 filter as production answered every real bounce: confident junk, so a mail it is
    asked about is ARCHIVED as `llm_junk`. Records the subject of every mail it was asked about."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def classify(self, ctx, prepared):
        self.asked.append(str(ctx.raw.get("subject") or ""))
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated notification")


def _event(email: str) -> SourceEvent:
    return SourceEvent(
        event_id="evt_dsn", org_id="o", connection_id="c", source="gmail",
        object_type="email_message", source_object_id="m1", dedup_key="gmail:email_message:m1",
        actor=Actor(type="external_contact", email=email),
        occurred_at=datetime(2026, 8, 11, 6, 0, 20, tzinfo=timezone.utc))


def _ctx(raw: dict, email: str) -> GateContext:
    """The context `capture/pipeline.capture_event` builds: the subject and the body (else the
    snippet) prepared together, beside the raw fields."""
    subject = str(raw.get("subject") or "")
    text = str(raw.get("body") or raw.get("snippet") or "")
    prepared = preprocess(f"{subject}\n\n{text}" if subject else text, event_id="evt_dsn")
    return GateContext(event=_event(email), prepared=prepared, raw=raw)


def _gate(raw: dict, email: str, relevance=None):
    trace = EventTrace(org_id="o", event_id="evt_dsn")
    result = run_gate(_ctx(raw, email), trace, relevance=relevance)
    return result, trace


def _read_and_never_judged(raw: dict, email: str) -> None:
    model = _Junk()
    result, trace = _gate(raw, email, model)
    assert model.asked == [], "the junk filter judged a delivery report"
    assert (result.action, result.route, result.reason_code) == ("route", "needs_extraction", None)
    last = trace.records[-1]
    assert (last.stage, last.action.value) == ("S2", "pass")


# ── the report is read, and the filter is never asked ──────────────────────────────────────────

def test_the_golden_bounce_is_read_not_archived_as_junk():
    _read_and_never_judged(GOLDEN, GOLDEN_DAEMON)


def test_productions_bounce_is_read_not_archived_as_junk():
    _read_and_never_judged(PRODUCTION, DAEMON)


def test_a_delay_notice_is_read_as_well():
    _read_and_never_judged(DELAY, DAEMON)


def test_a_report_named_only_in_its_body_is_read():
    """S1 kept it on its body; S2 asks the same question of the same body."""
    _read_and_never_judged({"subject": "Returned mail",
                            "body": "Message not delivered: the address priya@acme.test does not "
                                    "exist."}, DAEMON)


def test_a_report_named_only_in_its_list_snippet_is_read():
    """A message settled from its list fields arrives with a snippet and no body — the fallback
    `capture/pipeline._delivery_status` reads, and S1 keeps on."""
    _read_and_never_judged({"subject": "Returned mail",
                            "snippet": "Message not delivered: the address priya@acme.test does "
                                       "not exist."}, DAEMON)


def test_the_trace_says_why_the_filter_was_not_asked():
    """A trace that read `S2 pass` alone could not tell a report from a gate with no filter wired."""
    _, trace = _gate(GOLDEN, GOLDEN_DAEMON, _Junk())
    assert trace.records[-1].detail == {"route": "needs_extraction", "delivery_report": True}
    _, trace = _gate(FORWARD, "priya@acme.test")
    assert "delivery_report" not in trace.records[-1].detail


# ── what does not change ───────────────────────────────────────────────────────────────────────

def test_a_forwarded_bounce_from_a_person_still_meets_the_filter():
    """The control that proves the filter WOULD drop: the same words from a person are judged, and
    archived as junk exactly as before."""
    model = _Junk()
    result, trace = _gate(FORWARD, "priya@acme.test", model)
    assert model.asked == [FORWARD["subject"]]
    assert (result.action, result.reason_code) == ("archive", "llm_junk")
    assert (trace.records[-1].stage, trace.records[-1].action.value) == ("S2", "archive")


@pytest.mark.parametrize("raw, email", [
    ({"subject": "Your weekly digest", "body": "Five new posts this week."}, "no-reply@portal.test"),
    # A delivery daemon's OWN notice is not a delivery report: both conditions, never one.
    ({"subject": "Your mailbox is 95% full", "body": "Please delete old messages."},
     "postmaster@acme.test"),
])
def test_an_ordinary_machine_mail_is_still_archived_at_s1(raw, email):
    model = _Junk()
    result, trace = _gate(raw, email, model)
    assert (result.action, result.reason_code) == ("archive", "N-03")
    assert (trace.records[-1].stage, trace.records[-1].action.value) == ("S1", "archive")
    assert model.asked == []


def test_a_report_the_provider_filed_as_spam_is_still_archived_at_s1():
    """Backscatter is the provider's to judge — the filter is not reached, and S2's skip does not
    reach back past S1's verdict."""
    model = _Junk()
    result, _ = _gate({**GOLDEN, "labelIds": ["SPAM"]}, GOLDEN_DAEMON, model)
    assert (result.action, result.reason_code) == ("archive", "N-09")
    assert model.asked == []


# ── one question, one set of inputs ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, email", [
    (GOLDEN, GOLDEN_DAEMON),
    (PRODUCTION, DAEMON),
    (DELAY, DAEMON),
    (FORWARD, "priya@acme.test"),
    ({"subject": "Your mailbox is 95% full", "body": "Please delete old messages."},
     "postmaster@acme.test"),
    # The body is read BEFORE the snippet, by the parser and by the gate: a body that does not
    # name a report is not overruled by a snippet that does.
    ({"subject": "Returned mail", "body": "See the transcript below.",
      "snippet": "Message not delivered: the address priya@acme.test does not exist."}, DAEMON),
    ({"subject": "Returned mail",
      "snippet": "Message not delivered: the address priya@acme.test does not exist."}, DAEMON),
    ({"subject": None, "body": None, "snippet": None}, DAEMON),
])
def test_the_gate_asks_exactly_what_the_parser_reads(raw, email):
    """`is_a_delivery_report` and `capture/pipeline._delivery_status` — the reader of the report —
    answer the same for every shape, and S1's keep and S2's skip are that one answer."""
    from genios_engine.capture.pipeline import _delivery_status

    parsed = _delivery_status(SimpleNamespace(actor=SimpleNamespace(email=email)), raw) is not None
    assert is_a_delivery_report(raw, sender_email=email) is parsed


def test_a_mail_with_no_sender_or_no_payload_is_not_a_report():
    assert is_a_delivery_report(GOLDEN, sender_email=None) is False
    assert is_a_delivery_report(None, sender_email=DAEMON) is False


def test_s1_keeps_on_the_same_question():
    """`noise_rule` asks through the shared helper too: a report named only in its list snippet,
    from a sender the machine table matches, passes S1 — the N-03 it would otherwise meet."""
    raw = {"subject": "Returned mail",
           "snippet": "Message not delivered: the address priya@acme.test does not exist."}
    assert noise_rule(_ctx(raw, "mailer-daemon@googlemail.com")) is None

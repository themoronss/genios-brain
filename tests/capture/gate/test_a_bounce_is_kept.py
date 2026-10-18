"""STEP-10 · a delivery report the parser recognises is kept and read — never archived as a machine's mail.

    pytest tests/capture/gate/test_a_bounce_is_kept.py -q

`capture/gate/rules.noise_rule` (tree `yc2_w27_s10 · M29.C3.L-logic.V0.U01`, `06` D38). A founder's
pitch to a fund bounced, and the report never reached the parser that reads it: the golden set's
bounce (F16 — a daemon, no headers, no attachment) was archived at N-03, and production's shape (Gmail
sends it with `Auto-Submitted: auto-replied` and the original attached) at N-01 — 0 `DELIVERY_FAILURE`
signals, and the pitch still read "waiting" (`speedrun008/YC-II W27/` STEP-10 §8.1). Now a report
`capture/delivery_status.is_delivery_status` recognises — a delivery daemon sent it AND it reads as a
delivery report — passes the traffic-shape rules and is routed to be read, a delay notice as much as a
failure. What does not change: a report the provider filed as spam is still archived, an ordinary
machine mail is still archived at N-03, and a person forwarding a bounce is not a delivery report,
whatever its words.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.rules import noise_rule
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace

#: Golden F16's report, as its case spec has it: no headers, no attachment, the Gmail sentence.
GOLDEN_DAEMON = "mailer-daemon@mailhost.test"
GOLDEN = {"subject": "Delivery Status Notification (Failure)",
          "body": "Address not found\n\nYour message wasn't delivered to "
                  "partners@lattice-capital.test because the domain lattice-capital.test couldn't "
                  "be found. Check for typos or unnecessary spaces and try again.",
          "labelIds": ["INBOX"]}

#: Production's: Gmail's daemon, its envelope (`tests/capture/test_delivery_failure.py`), the
#: original attached. The body leaves out Gmail's `** Address not found **` headline, so only the
#: SUBJECT names the report — the gate must read it.
DAEMON = "mailer-daemon@googlemail.com"
PRODUCTION = {"subject": "Delivery Status Notification (Failure)",
              "body": "Your message wasn't delivered to madison@afore.vc because the address "
                      "couldn't be found or is unable to receive email.",
              "headers": {"Auto-Submitted": "auto-replied", "Precedence": "bulk"},
              "has_attachment": True, "labelIds": ["INBOX"]}


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


def _gate(raw: dict, email: str):
    trace = EventTrace(org_id="o", event_id="evt_dsn")
    result = run_gate(_ctx(raw, email), trace)
    return result, trace.records[-1]


def _kept_and_read(raw: dict, email: str) -> None:
    assert noise_rule(_ctx(raw, email)) is None
    result, last = _gate(raw, email)
    assert (result.action, result.route, result.reason_code) == ("route", "needs_extraction", None)
    assert (last.stage, last.action.value) == ("S2", "pass")


# ── the bounce is kept ──────────────────────────────────────────────────────────────────────────

def test_the_golden_bounce_is_not_archived_at_n03():
    _kept_and_read(GOLDEN, GOLDEN_DAEMON)


def test_productions_bounce_is_not_archived_at_n01():
    _kept_and_read(PRODUCTION, DAEMON)


def test_a_report_named_only_in_its_body_is_kept():
    """The parser reads the subject OR the body; so does the gate."""
    _kept_and_read({"subject": "Returned mail",
                    "body": "Message not delivered: the address priya@acme.test does not exist."},
                   DAEMON)


def test_a_report_named_only_in_its_list_snippet_is_kept():
    """A message settled from its list fields arrives with a snippet and no body — the same
    fallback `capture/pipeline._delivery_status` reads."""
    _kept_and_read({"subject": "Returned mail",
                    "snippet": "Message not delivered: the address priya@acme.test does not exist."},
                   DAEMON)


def test_a_report_with_a_bulk_precedence_is_not_archived_at_n04():
    """`mail-delivery@` is a delivery daemon to the parser and a person to the machine table, so N-03
    passes it — and the bulk precedence every report carries archived it at N-04."""
    _kept_and_read({"subject": "Delivery Status Notification (Failure)",
                    "body": "Your message wasn't delivered to priya@acme.test.",
                    "headers": {"Precedence": "bulk"}},
                   "mail-delivery@relay.acme.test")


def test_a_delay_notice_is_kept_as_well():
    """Whether delivery FAILED is the reader's question (`context/delivery`), not the gate's: a
    report still being retried is kept and read, and the reader writes nothing for it."""
    _kept_and_read({"subject": "Delivery Status Notification (Delay)",
                    "body": "There was a temporary problem delivering your message to "
                            "apply@surgeahead.com. Gmail will retry for 47 more hours.",
                    "headers": {"Auto-Submitted": "auto-replied"}},
                   DAEMON)


# ── what does not change ────────────────────────────────────────────────────────────────────────

def test_a_report_the_provider_filed_as_spam_is_still_archived():
    """Backscatter — reports for mail somebody forged in our name — is the provider's to judge."""
    result, last = _gate({**GOLDEN, "labelIds": ["SPAM"]}, GOLDEN_DAEMON)
    assert (result.action, result.reason_code) == ("archive", "N-09")
    assert (last.stage, last.action.value) == ("S1", "archive")


@pytest.mark.parametrize("raw, email", [
    ({"subject": "Your weekly digest", "body": "Five new posts this week."}, "no-reply@portal.test"),
    # A delivery daemon's OWN notice is not a delivery report: both conditions, never one.
    ({"subject": "Your mailbox is 95% full", "body": "Please delete old messages."},
     "postmaster@acme.test"),
])
def test_an_ordinary_machine_mail_is_still_archived_at_n03(raw, email):
    result, last = _gate(raw, email)
    assert (result.action, result.reason_code) == ("archive", "N-03")
    assert (last.stage, last.action.value) == ("S1", "archive")


@pytest.mark.parametrize("headers, code", [
    ({"List-Id": "<team.acme.test>"}, "N-02"),
    ({"Auto-Submitted": "auto-generated"}, "N-01"),
])
def test_a_forwarded_bounce_from_a_person_is_not_a_delivery_report(headers, code):
    """The words without the thing (`capture/delivery_status`'s own example): a colleague forwarding
    a bounce to the team's list, or a forwarding rule passing it on, is the mail it looks like — and
    is archived as such mail always was."""
    raw = {"subject": "Fwd: Delivery Status Notification (Failure)",
           "body": "Can you resend this one?\n\n---------- Forwarded message ----------\n"
                   "Your message wasn't delivered to partners@lattice-capital.test because the "
                   "address couldn't be found.",
           "headers": headers}
    result, _ = _gate(raw, "priya@acme.test")
    assert (result.action, result.reason_code) == ("archive", code)

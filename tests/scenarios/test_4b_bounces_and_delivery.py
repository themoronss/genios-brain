"""§4b · S07–S12 — bounces and delivery.

    pytest tests/scenarios/test_4b_bounces_and_delivery.py -q

⛔ **THREE OF THESE SIX ARE F20 — manufactured certainty — and F20 is the class §3 says to watch
hardest**, because it is *"the failure that loses trust rather than quality"*.

Telling a founder their pitch bounced while Gmail is still delivering it is not a quality problem.
It is the product being wrong about something the founder can check.

The pilot's own numbers are the argument: **every one of the org's five bounces was filed as noise**,
because a delivery report carries `Auto-Submitted: auto-replied` and N-01 drops on that header.
Surge's delay notice took **47 hours** to resolve — for 47 hours, "failed" would have been a lie.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)

DAEMON = "mailer-daemon@googlemail.com"


def _gate_ctx(raw: dict, *, sender: str = "stranger@unknown.test", sender_known: bool = False):
    """A `GateContext` over a real `SourceEvent` — §6 condition 4: drive the real path."""
    from genios_engine.capture.gate.context import GateContext
    from genios_engine.contracts.source_event import SourceEvent

    event = SourceEvent(event_id="e1", org_id="o", connection_id="c", source="gmail",
                        object_type="email_message", source_object_id="m1",
                        dedup_key="gmail:email_message:m1", occurred_at=NOW,
                        actor={"email": sender, "type": "external_contact"})
    return GateContext(event=event, raw=raw, sender_known=sender_known)


# =================================================================================================
# S07 · F01 — a hard bounce IS a delivery failure
# =================================================================================================
def test_s07_a_hard_bounce_reads_as_failed_and_names_its_recipient():
    """5.1.1 — the address does not exist. Permanent, and the recipient is what makes it joinable
    back to the sent message."""
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(
        sender=DAEMON, subject="Delivery Status Notification (Failure)",
        text="Your message wasn't delivered to priya@acme.com because the address couldn't be "
             "found.\nFinal-Recipient: rfc822; priya@acme.com\n5.1.1 user unknown")

    assert status is not None and status.kind == "failed" and status.failed is True
    assert status.recipient == "priya@acme.com"


# =================================================================================================
# S08 · F20 — a soft bounce is NOT a failure
# =================================================================================================
def test_s08_a_soft_4xx_bounce_is_not_a_failure():
    """⛔ **F20.** A 4.x.x is temporary — the provider is still trying. Reporting it as failed is
    manufactured certainty in the direction that costs trust."""
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(
        sender=DAEMON, subject="Delivery Status Notification (Delay)",
        text="There was a temporary problem delivering your message to priya@acme.com. "
             "Gmail will retry for 47 more hours.\n4.2.2 mailbox full")

    assert status.kind == "delayed"
    assert status.failed is False, "a message still being retried has not failed"


def test_s08_delay_is_read_before_failure_because_a_delay_notice_says_incomplete():
    """The ordering bug that would cause S08 to regress. A delay notice contains *"delivery
    incomplete"*, which a looser failure pattern reads as permanent — so `_DELAY_MARKERS` is
    checked **first**, and this asserts the order rather than the patterns."""
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(
        sender=DAEMON, subject="Delivery incomplete",
        text="Delivery incomplete — there was a temporary problem. 4.7.0")

    assert status.kind == "delayed"


# =================================================================================================
# S09 · F20 — Surge's 47-hour delay
# =================================================================================================
def test_s09_a_delay_notice_still_retrying_is_never_reported_as_failed():
    """The pilot's real case. For **47 hours** this message was in flight, and for 47 hours
    *"your pitch bounced"* would have been false."""
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(
        sender=DAEMON, subject="Delivery Status Notification (Delay)",
        text="** Message delayed ** Gmail will retry for 47 more hours.")

    assert status.failed is False


def test_s09_an_unclassifiable_report_is_unknown_and_not_failed():
    """The third value, and the one that keeps this honest. `UNKNOWN` is *"a recognised report with
    an unstated outcome"* — distinct from `None`, which means *not a delivery report at all*.

    Collapsing the two would make every odd provider format read as a bounce.
    """
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(sender=DAEMON, subject="Delivery Status Notification",
                                  text="Something happened with your message.")

    assert status is not None and status.kind == "unknown" and status.failed is False
    assert read_delivery_status(sender="priya@acme.com", subject="Re: proposal",
                                text="sounds good") is None, "ordinary mail is not a report"


# =================================================================================================
# S10 · F12 — a bounce with no parseable recipient still publishes
# =================================================================================================
def test_s10_a_bounce_whose_address_cannot_be_read_is_still_a_bounce():
    """⛔ **The evidence rule, applied to a negative.** A bounce we cannot join is **still
    recognised** — so it is not refused as bulk mail — and the address is left `None` rather than
    guessed.

    *"A wrong address in a 'your message never arrived' card costs more than an incomplete one."*
    """
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(
        sender=DAEMON, subject="Delivery Status Notification (Failure)",
        text="Your message was not delivered. 5.7.1 blocked by the receiving server.")

    assert status.kind == "failed", "recognised, so it does not fall through to the noise rules"
    assert status.recipient is None, "and the address is absent rather than invented"


def test_s10_the_structured_rfc3464_field_is_preferred_over_the_prose():
    """When both are present the standard wins — it is unambiguous, and the prose pattern has to
    guess which address after which preposition."""
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(
        sender=DAEMON, subject="Delivery Status Notification (Failure)",
        text="Your message wasn't delivered to old@acme.com.\n"
             "Final-Recipient: rfc822; real@acme.com\n5.1.1")

    assert status.recipient == "real@acme.com"


# =================================================================================================
# S11 · GUARD — an out-of-office keeps the N-05 path
# =================================================================================================
def test_s11_an_out_of_office_from_a_human_is_not_dropped_by_n01():
    """A vacation responder carries `Auto-Submitted`, which N-01 drops on — and it is *"the one
    message that says who is away"*.

    A GUARD: it works today, and this proves sixteen steps did not cost it.
    """
    from genios_engine.capture.gate.rules import noise_rule

    verdict = noise_rule(_gate_ctx(
        {"subject": "Automatic reply: Out of office until 3 October",
         "headers": {"Auto-Submitted": "auto-replied"}},
        sender="priya@acme.com"))

    assert verdict is None, "the availability notice was dropped as a machine acknowledgement"


def test_s11_a_helpdesk_auto_reply_still_drops_because_it_is_nobody_s_leave():
    """The exemption's boundary. *"A helpdesk 'Automatic reply: ticket received' is nobody's
    leave."* A guard that only proved the permissive half would let the exemption widen unnoticed."""
    from genios_engine.capture.gate.rules import noise_rule

    verdict = noise_rule(_gate_ctx(
        {"subject": "Automatic reply: ticket received",
         "headers": {"Auto-Submitted": "auto-replied"}},
        sender="noreply@helpdesk.test"))

    assert verdict is not None and verdict[1] == "drop"


# =================================================================================================
# S12 · GUARD — the noreply exemption must NOT widen
# =================================================================================================
def test_s12_a_noreply_newsletter_still_drops():
    """§4b calls this *"the exemption must not widen"*, and that is the risk: step 1 exempted
    attachment-bearing mail from N-02/03/04 so a vendor invoice from `noreply@` survives. A
    newsletter with **no** attachment must still go."""
    from genios_engine.capture.gate.rules import noise_rule

    verdict = noise_rule(_gate_ctx(
        {"subject": "This week in AI", "headers": {"List-Unsubscribe": "<https://x.test/u>"}},
        sender="noreply@newsletter.test"))

    assert verdict is not None and verdict[0] in ("N-02", "N-03") and verdict[1] == "drop"


def test_s12_the_same_sender_with_a_real_attachment_survives():
    """The exemption itself, which is the thing that could widen. A vendor invoice routinely comes
    from `noreply@` — and it is the message carrying the contract."""
    from genios_engine.capture.gate.rules import noise_rule

    verdict = noise_rule(_gate_ctx(
        {"subject": "Your invoice", "has_attachment": True,
         "headers": {"List-Unsubscribe": "<https://x.test/u>"}},
        sender="noreply@vendor.test"))

    assert verdict is None


def test_s12_provider_classified_spam_drops_regardless_of_an_attachment():
    """The hard floor under the exemption. `SPAM`/`TRASH` and Gmail's own PROMOTIONS guess are
    *"highest-confidence noise"* and drop **regardless** — otherwise attaching a file to spam would
    buy it a route into the layer."""
    from genios_engine.capture.gate.rules import noise_rule

    verdict = noise_rule(_gate_ctx({"subject": "WIN NOW", "has_attachment": True,
                                    "labelIds": ["SPAM"]}, sender="x@spam.test"))

    assert verdict == ("N-09", "drop")

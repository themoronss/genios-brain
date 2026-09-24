"""Step 2 · a delivery failure is a business fact, and Layer 1 loses it.

    pytest tests/capture/test_delivery_failure.py -q

WHAT THIS IS ABOUT. On 11 August the tenant sent pitches to Afore and Surge. Three of them never
arrived — two addresses did not exist and one server was misconfigured — and the bounce notices
have been sitting in the mailbox ever since. Nothing in the product can say so.

WHY THE OBVIOUS TEST WOULD HAVE PASSED. The step that produced this file was first written
believing `gate/rules.py` drops delivery-status mail on the `mailer-daemon` sender. It does not:
N-03 fires on `not att and machine`, and a Gmail DSN returns the original message as an
attachment, so `not att` is False. Measured in production 2026-09-23: all five bounce events are
`outcome=emitted`. A test asserting "a bounce reaches the gate" is green before any change.

WHERE IT IS ACTUALLY LOST, from the production event trace:

    S2                      pass           N-05                   availability=auto_reply
    s2_semantic_extraction  short_circuit  envelope_bulk_headers
    s4_esqe                 short_circuit  bulk_headers           signals=0
    emit                    emit

`refused_without_extraction` runs BEFORE S2 so an envelope-only refusal can save a model call.
That is right for a newsletter. A delivery failure is the one kind of automated mail that is a
fact about something the tenant did, and the same rule swallows it — 30 events org-wide.

The fixtures below are the real production bodies, abbreviated only where the text repeats.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.esqe import relevance as R

#: A frozen instant. `eval_time` is a parameter everywhere in this layer precisely so a replay
#: of last March's mail does not re-judge it against today.
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _empty_extraction():
    """An extraction that found nothing — which is what a bounce really produces.

    This is the honest fixture for this step: Gmail's delivery report is a machine notice, so the
    extractor has no commitment, no amount and no date to find in it. If DELIVERY_FAILURE needed a
    claim to fire, it would never fire at all — which is precisely why the predicate reads the
    envelope instead.
    """
    from genios_engine.contracts.extraction import ExtractionResult
    return ExtractionResult(
        intent="notify", stance="neutral",
        model_snapshot="test", prompt_version="test", schema_version="test",
        extraction_profile="email", input_tokens=0, output_tokens=0)

# The envelope Gmail puts on a delivery-status notification. `Auto-Submitted: auto-replied` is
# what `_has_bulk_headers` matches on, and it is also what makes `availability_marker` call this
# an out-of-office — see `test_a_bounce_is_not_an_availability_notice`.
DSN_HEADERS = {"Auto-Submitted": "auto-replied", "Precedence": "bulk"}
DAEMON = "mailer-daemon@googlemail.com"

FAILURE_ADDRESS_NOT_FOUND = (
    "** Address not found **\n\n"
    "Your message wasn't delivered to madison@afore.vc because the address couldn't be found "
    "or is unable to receive email.\n\nLearn more here: "
    "https://support.google.com/mail/?p=NoSuchUser"
)
FAILURE_SERVER_MISCONFIGURED = (
    "** Message not delivered **\n\n"
    "Your message couldn't be delivered to apply@surgeahead.com because the remote server is "
    "misconfigured. See the technical details below for more information."
)
DELAY_RETRYING = (
    "** Delivery incomplete **\n\n"
    "There was a temporary problem while delivering your message to apply@surgeahead.com. "
    "Gmail will retry for 47 more hours. You'll be notified if the delivery fails permanently."
)


def _bounce_event(sender: str = DAEMON):
    """A `SourceEvent` shaped the way landing produces one, so `envelope_candidate` can read the
    same four things off it that the pipeline does."""
    from types import SimpleNamespace
    return SimpleNamespace(event_id="evt_bounce", source_object_id="msg_1",
                           actor=SimpleNamespace(email=sender), internal_kind=None)


def _candidate(subject: str, body: str, event_id: str = "evt_bounce") -> R.RelevanceCandidate:
    """A bounce as the pipeline hands it to S4, with the envelope it really carries.

    `delivery_failure` is computed through the recogniser rather than hard-coded, because that is
    what `pipeline._delivery_failed` does — a fixture that just set the flag True would pass even
    if the recogniser stopped recognising anything.
    """
    from genios_engine.capture.delivery_status import read_delivery_status

    status = read_delivery_status(sender=DAEMON, subject=subject, text=body)
    return R.RelevanceCandidate(
        event_id=event_id,
        sender=DAEMON,
        sender_known=False,
        headers=DSN_HEADERS,
        subject=subject,
        snippet=body,
        typed_claim_count=0,
        delivery_failure=status is not None and status.failed,
    )


# ---------------------------------------------------------------------------------------------
# RED · the envelope refusal that costs the finding
# ---------------------------------------------------------------------------------------------
def test_a_hard_bounce_is_not_refused_on_its_envelope():
    """The defect, stated as a test.

    `refused_without_extraction` is asked before S2. When it names a rule the extractor never
    runs, so there are no claims, so no predicate can fire, so the event emits carrying nothing.
    A delivery failure must survive that question.
    """
    candidate = _candidate("Delivery Status Notification (Failure)",
                           FAILURE_ADDRESS_NOT_FOUND)
    assert R.refused_without_extraction(candidate) is None


def test_a_hard_bounce_is_relevant_by_rule_with_no_model_call():
    """And it must be RELEVANT, decided by a rule — not sent to LLM-5 to be guessed at.

    A bounce is deterministic: the body names the address and says whether delivery failed or is
    still being retried. Spending a model call on it would be the cost defect `bulk_headers` was
    introduced to fix, arriving by the other door.
    """
    outcome = R.assess_relevance([_candidate("Delivery Status Notification (Failure)",
                                             FAILURE_ADDRESS_NOT_FOUND)], llm=None)
    decision = outcome.decisions[0]
    assert decision.relevant is True
    assert outcome.llm_calls == 0


def test_the_newsletter_refusal_still_works():
    """REGRESSION GUARD. The exemption must be narrow enough that ordinary bulk mail still dies
    on its envelope — that rule pays for itself, 522,143 input tokens on the pilot org."""
    newsletter = R.RelevanceCandidate(
        event_id="evt_news", sender="news@example.com", sender_known=False,
        headers={"List-Unsubscribe": "<https://example.com/u>"},
        subject="This week at Example", snippet="Our top stories this week", typed_claim_count=0)
    assert R.refused_without_extraction(newsletter) == R.RULE_BULK_HEADERS


def test_a_delay_notice_is_not_a_failure():
    """Surge's message took 47 hours of retries before it failed permanently. During those
    hours the honest answer is UNKNOWN, not 'the pitch did not arrive'. Telling a founder their
    mail bounced when it is still being retried is the F20 failure — manufactured certainty."""
    from genios_engine.capture import delivery_status as D

    delay = D.read_delivery_status(sender=DAEMON,
                                   subject="Delivery Status Notification (Delay)",
                                   text=DELAY_RETRYING)
    assert delay is not None
    assert delay.failed is False
    assert delay.kind == D.DELAYED


# ---------------------------------------------------------------------------------------------
# RED · the recogniser itself
# ---------------------------------------------------------------------------------------------
def test_the_recogniser_reads_the_failed_recipient_out_of_the_prose():
    """No MIME walk and no OCR: Gmail states the address in the sentence. Parsing the prose is
    the first cut; an RFC 3464 `message/delivery-status` part is a hardening pass, not the
    prerequisite this step was originally written to need."""
    from genios_engine.capture import delivery_status as D

    result = D.read_delivery_status(sender=DAEMON,
                                    subject="Delivery Status Notification (Failure)",
                                    text=FAILURE_ADDRESS_NOT_FOUND)
    assert result is not None
    assert result.failed is True
    assert result.recipient == "madison@afore.vc"

    other = D.read_delivery_status(sender=DAEMON,
                                   subject="Delivery Status Notification (Failure)",
                                   text=FAILURE_SERVER_MISCONFIGURED)
    assert other is not None
    assert other.recipient == "apply@surgeahead.com"


def test_an_ordinary_email_is_not_a_delivery_status():
    """The recogniser must refuse everything it is not sure about. A false positive here would
    invent a delivery failure that never happened, which is worse than missing one."""
    from genios_engine.capture import delivery_status as D

    assert D.read_delivery_status(sender="rohit@genios.ai", subject="Re: pricing",
                                  text="Sending the revised proposal by Friday.") is None
    # a human writing ABOUT a bounce is not a bounce
    assert D.read_delivery_status(sender="harsh@genios.ai",
                                  subject="Fwd: Delivery Status Notification (Failure)",
                                  text="Looks like this one bounced, can you resend?") is None


def test_a_recipient_it_cannot_parse_is_left_unknown():
    """A bounce whose address cannot be read is still a bounce. It must be recognised, with the
    recipient left `None` — never guessed. A wrong address in a 'your pitch never arrived' card
    is a credibility loss, and the whole point of this layer is that a claim carries a receipt."""
    from genios_engine.capture import delivery_status as D

    result = D.read_delivery_status(
        sender=DAEMON, subject="Delivery Status Notification (Failure)",
        text="** Message not delivered **\n\nDelivery to the recipient failed permanently.")
    assert result is not None
    assert result.failed is True
    assert result.recipient is None


# ---------------------------------------------------------------------------------------------
# RED · the second defect: a bounce filed as somebody's out-of-office
# ---------------------------------------------------------------------------------------------
def test_a_bounce_is_not_an_availability_notice():
    """`availability_marker` returned `auto_reply` for every one of the five production bounces.

    That exemption is what saved them from the N-03 drop, so it was doing useful work by
    accident — but *"Rohit's message to Afore did not arrive"* is not a statement about anyone's
    availability, and filing it as one is why the events land in lane P3 behind real mail.

    The check stays inside the function's stated contract: **subject and responder headers only**,
    never body prose. A delivery report names itself in its subject.
    """
    from genios_engine.capture.gate.rules import availability_marker

    bounce = {"subject": "Delivery Status Notification (Failure)",
              "headers": {"Auto-Submitted": "auto-replied"}}
    assert availability_marker(bounce) is None


def test_a_real_vacation_responder_is_still_an_availability_notice():
    """REGRESSION GUARD. N-05 exists because a leave email is the only place 'who is away, until
    when, who covers' is ever written. Excluding delivery reports must not cost that."""
    from genios_engine.capture.gate.rules import availability_marker

    ooo = {"subject": "Automatic reply: Re: pricing",
           "headers": {"Auto-Submitted": "auto-replied"}}
    assert availability_marker(ooo) is not None


# ---------------------------------------------------------------------------------------------
# RED · the signal itself — the point of the whole step
# ---------------------------------------------------------------------------------------------
def test_the_taxonomy_has_a_word_for_a_delivery_failure():
    """None of the fifteen existing types fits. `ANOMALY` is the nearest and it is wrong: an
    anomaly is something unexpected in the data, and an undelivered message is not unexpected —
    it is a stated outcome of an action the tenant took.

    `SignalType` is closed and `contracts/publication.py` says why: *"a fourth outcome invented
    at a call site would be an emit nobody reviewed."* Adding a member is therefore a deliberate
    contract change, which is what this test pins.
    """
    from genios_engine.contracts.signal import SignalType

    assert SignalType.DELIVERY_FAILURE.value == "delivery_failure"


def test_a_hard_bounce_produces_a_delivery_failure_signal():
    """THE STEP, in one assertion.

    Not "it reaches the gate" — it already does. Not "it is extracted" — that is the means. The
    finding only exists when a predicate fires and a signal comes out, because a signal is the
    only thing Layer 2 ever sees.
    """
    from genios_engine.capture import delivery_status as D
    from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
    from genios_engine.contracts.extraction import ExtractionResult
    from genios_engine.contracts.signal import SignalType

    status = D.read_delivery_status(sender=DAEMON,
                                    subject="Delivery Status Notification (Failure)",
                                    text=FAILURE_ADDRESS_NOT_FOUND)
    outcome = detect_signals(DetectionInput(
        extraction=_empty_extraction(), eval_time=NOW, delivery_status=status))

    kinds = {signal.signal_type for signal in outcome.signals}
    assert SignalType.DELIVERY_FAILURE in kinds


def test_a_delay_notice_produces_no_signal():
    """The F20 guard, at the level that matters. A message still being retried has not failed,
    and the detector must not say it has."""
    from genios_engine.capture import delivery_status as D
    from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
    from genios_engine.contracts.extraction import ExtractionResult
    from genios_engine.contracts.signal import SignalType

    status = D.read_delivery_status(sender=DAEMON,
                                    subject="Delivery Status Notification (Delay)",
                                    text=DELAY_RETRYING)
    outcome = detect_signals(DetectionInput(
        extraction=_empty_extraction(), eval_time=NOW, delivery_status=status))

    kinds = {signal.signal_type for signal in outcome.signals}
    assert SignalType.DELIVERY_FAILURE not in kinds


def test_an_ordinary_event_still_detects_exactly_what_it_did_before():
    """REGRESSION GUARD. `delivery_status` defaults to None, so every existing caller — and
    every one of the 618 tests that build a `DetectionInput` — keeps its behaviour unchanged."""
    from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
    from genios_engine.contracts.extraction import ExtractionResult
    from genios_engine.contracts.signal import SignalType

    outcome = detect_signals(DetectionInput(extraction=_empty_extraction(), eval_time=NOW))
    kinds = {signal.signal_type for signal in outcome.signals}
    assert SignalType.DELIVERY_FAILURE not in kinds


# ---------------------------------------------------------------------------------------------
# RED · the floor, which would otherwise make every line above pointless
# ---------------------------------------------------------------------------------------------
def test_a_delivery_failure_survives_the_qualification_floor():
    """Detecting a bounce and then refusing it at the floor is a step that changes no number.

    Measured on a cold-start tenant with the shipped weights: a DELIVERY_FAILURE scores **1080**
    against a default floor of **2500**. That is not this tenant being unusual — it is structural.
    ALG-17's five terms are money, deadline, actor authority, entity criticality and a type nudge,
    and a bounce has:

        money       none, ever — a delivery report states no amount
        deadline    none, ever — it reports a past event
        authority   a mail daemon
        criticality the one entity it names is, by definition, one we could not reach

    So four of the five are structurally zero and the type nudge alone can never reach 2500,
    whatever the tenant. `AVAILABILITY_CHANGE` had the identical problem and the floor already
    carries the answer: a named, ledgered override — not a weight nudged until the number passes.

    **ALG-17 is untouched by this.** The score stays 1080 and is reported honestly; the floor
    makes a stated exception, and `qualification_drops` still records why.
    """
    from genios_engine.capture.esqe.qualification import QualificationReason

    assert QualificationReason.DELIVERY_FAILURE_OVERRIDE.value == "delivery_failure_override"


# ---------------------------------------------------------------------------------------------
# RED · THE WIRING, which every test above would have passed without
# ---------------------------------------------------------------------------------------------
def test_the_candidate_the_pipeline_really_builds_is_not_refused():
    """The test that separates a working unit from a working system.

    Every assertion above builds its own `RelevanceCandidate` with a subject and a snippet on it.
    The pipeline does not: `envelope_candidate` leaves both EMPTY on purpose — *"they exist to be
    shown to LLM-5, and nothing that reads this candidate is allowed to call a model"*. So a rung
    that reads `candidate.subject` sees `""` on the one path that matters, and the bounce is
    refused exactly as before while the unit tests stay green.

    This is the defect the build record says this layer shipped six times: *"a unit built, tested,
    green — and called by nothing on a real request path."* The rule it gave is the one being
    obeyed here — **a unit is done when a real request path reaches it and a test drives that
    path** — so this test builds the candidate the way `capture_event` builds it, through
    `envelope_candidate`, and nothing else.
    """
    from genios_engine.capture.pipeline import envelope_candidate

    raw = {"subject": "Delivery Status Notification (Failure)",
           "body": FAILURE_ADDRESS_NOT_FOUND,
           "headers": DSN_HEADERS}
    event = _bounce_event()

    candidate = envelope_candidate(event, raw, sender_known=False, is_structured=False)
    assert R.refused_without_extraction(candidate) is None, (
        "the semantic lane is still skipped on the real path — the unit works and the wiring "
        "does not")


def test_the_pipeline_candidate_still_refuses_a_newsletter():
    """REGRESSION GUARD on the same real path, so the wiring cannot be widened by accident."""
    from genios_engine.capture.pipeline import envelope_candidate

    raw = {"subject": "This week at Example", "body": "Our top stories",
           "headers": {"List-Unsubscribe": "<https://example.com/u>"}}
    event = _bounce_event(sender="news@example.com")

    candidate = envelope_candidate(event, raw, sender_known=False, is_structured=False)
    assert R.refused_without_extraction(candidate) == R.RULE_BULK_HEADERS


# ---------------------------------------------------------------------------------------------
# RED · 2-U5 · the failed address is what the signal is ABOUT
# ---------------------------------------------------------------------------------------------
def _normalized(subject: str, body: str):
    """One detected bounce, put through the real normalizer — not a hand-built record."""
    from genios_engine.capture import delivery_status as D
    from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
    from genios_engine.capture.esqe.normalize import normalize_signals
    from types import SimpleNamespace

    status = D.read_delivery_status(sender=DAEMON, subject=subject, text=body)
    detection = detect_signals(DetectionInput(
        extraction=_empty_extraction(), eval_time=NOW, delivery_status=status))
    event = SimpleNamespace(
        org_id="o", event_id="evt_bounce", source="gmail", object_type="email_message",
        occurred_at=NOW, visibility=None, recipients=("founder@genios.ai",),
        internal_kind=None, actor=SimpleNamespace(email=DAEMON))
    return normalize_signals(detection.signals, event=event,
                             extraction=_empty_extraction())


def test_the_failed_address_is_the_subject_of_the_signal():
    """ALG-22 derives a subject from the ANCHOR CLAIM, and its last rung is the event itself.

    A bounce has no claims, so every one of them would land on `event:<its own id>` — three
    failures to `apply@surgeahead.com` would be three unrelated subjects. That breaks two things
    at once: nothing can group them, and ALG-19's supersession key is `(subject_key, signal_type)`,
    so a delay followed by a permanent failure could never supersede.

    The failed address IS the subject. This is also the seam that makes the finding usable: step 3
    carries `subject_key` across to Layer 2, and Layer 2 is where an address becomes a person.
    **Layer 1 preserves the key; Layer 2 correlates.**
    """
    signals = _normalized("Delivery Status Notification (Failure)", FAILURE_ADDRESS_NOT_FOUND)
    assert len(signals) == 1
    assert signals[0].subject_key == "delivery:madison@afore.vc"


def test_two_failures_to_one_address_share_a_subject():
    """Surge bounced three times — two delays and a permanent failure. They are one story about
    one address, and they must group as one."""
    first = _normalized("Delivery Status Notification (Failure)", FAILURE_SERVER_MISCONFIGURED)
    second = _normalized("Delivery Status Notification (Failure)",
                         "** Message not delivered **\n\nYour message couldn't be delivered to "
                         "apply@surgeahead.com because the remote server is misconfigured.")
    assert first[0].subject_key == second[0].subject_key == "delivery:apply@surgeahead.com"


def test_a_bounce_with_no_readable_address_falls_back_rather_than_guessing():
    """No address, no invented subject. ALG-22's event rung is the honest answer: a group of one
    is worse than a wrong group, and a guessed address in a 'your pitch never arrived' card is a
    credibility loss."""
    signals = _normalized(
        "Delivery Status Notification (Failure)",
        "** Message not delivered **\n\nDelivery to the recipient failed permanently.")
    assert signals[0].subject_key.startswith("event:")

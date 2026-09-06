"""G6 · ALG-15, L1.6.1-U1 — the detection predicate table.

Enterprise Signal Qualification: the step that turns "this message contained a commitment and a
pending decision" into named enterprise signals. The gate is an EXACT set, not a superset — on
the doc-04 worked example the detector must produce exactly

    {CONTRACT_RENEWAL, DECISION_PENDING, APPROVAL_REQUESTED}

    pytest tests/capture/esqe -q

Exactness is the whole assertion. A detector graded on recall alone drifts toward firing on
everything, and a signal set that always contains the right answer among nine wrong ones is what
produced 115 live cards of which four were worth reading.

Three things this file refuses to do:

* it never asserts a string appears in a source file — every row constructs an extraction and
  reads what the predicate concluded;
* it never hand-counts a span offset — `span_of` finds the quote or raises;
* it never reads a clock — `eval_time` is the frozen instant every horizon is measured from, so
  the 7-day boundary rows are true on a Tuesday and true in March.

The last test drives `capture_event`, the real production entry point, because a predicate table
nothing calls is the defect this build has already shipped three times.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.esqe.detector import (MAX_SIGNALS_PER_EVENT, DetectionInput,
                                                 detect_signals)
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.conflict import (Authority, Conflict, ConflictClaim,
                                              ConflictResolution)
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.units import DateCertainty

WAVE = "W6"
GATE = "G6"

T = SignalType


def _detect(extraction, eval_time, **over):
    return detect_signals(DetectionInput(extraction=extraction, eval_time=eval_time, **over))


def _types(outcome) -> set[SignalType]:
    return set(outcome.types)


# ---------------------------------------------------------------------------------------------
# One row per predicate in doc 06's ALG-15 table.
# ---------------------------------------------------------------------------------------------

def test_an_extraction_with_nothing_in_it_is_not_a_signal(result, eval_time):
    """The floor. `intent=inform`, `stance=neutral`, no claims — a "thanks!" is not a signal, and
    a detector that fired here would put a card on every acknowledgement in the mailbox."""
    outcome = _detect(result(), eval_time)
    assert outcome.signals == ()
    assert outcome.is_signal is False
    assert outcome.fired == 0


def test_an_unconditional_promise_is_commitment_made(result, commitment, eval_time):
    outcome = _detect(result(commitments=[commitment()]), eval_time)
    assert _types(outcome) == {T.COMMITMENT_MADE}


def test_a_conditional_promise_is_not_a_commitment_made(result, commitment, eval_time):
    """`Commitment`'s own docstring: *"I'll send the contract once legal confirms" is not a
    promise with a date, and a system that stores it as one produces a false overdue.* This is
    also what makes the worked example produce three signals rather than four."""
    outcome = _detect(result(commitments=[commitment(is_conditional=True)]), eval_time)
    assert T.COMMITMENT_MADE not in _types(outcome)


@pytest.mark.parametrize("days, due_fires", [
    (0, True),          # due today
    (7, True),          # exactly on the horizon — `<=`, inclusive
    (8, False),         # one day past it
    (-3, True),         # already overdue is still due
])
def test_commitment_due_fires_only_inside_the_seven_day_horizon(
        result, commitment, dated, eval_time, days, due_fires):
    outcome = _detect(result(commitments=[commitment(due=dated(days))]), eval_time)
    assert (T.COMMITMENT_DUE in _types(outcome)) is due_fires


def test_an_undated_commitment_is_never_due(result, commitment, eval_time):
    """`due is None` means no date was stated. It does not mean "due now" — the contract says so,
    and reading it that way is what makes a founder get chased about a deliverable nobody set."""
    outcome = _detect(result(commitments=[commitment()]), eval_time)
    assert T.COMMITMENT_DUE not in _types(outcome)


@pytest.mark.parametrize("certainty, fires", [
    (DateCertainty.EXACT, True),
    (DateCertainty.RANGE, True),
    (DateCertainty.RELATIVE, False),        # "pretty soon" is not a deadline
])
def test_deadline_stated_only_at_exact_or_range_certainty(
        result, dated, eval_time, certainty, fires):
    outcome = _detect(result(dates_mentioned=[dated(3, certainty)]), eval_time)
    assert (T.DEADLINE_STATED in _types(outcome)) is fires


def test_a_date_attached_to_a_commitment_is_not_a_free_standing_deadline(
        result, commitment, dated, eval_time):
    """"...and no commitment attached". The same date reached through a promise is that promise's
    deadline, not a second signal about the same Friday."""
    when = dated(3)
    outcome = _detect(result(commitments=[commitment(due=when)], dates_mentioned=[when]),
                      eval_time)
    assert T.DEADLINE_STATED not in _types(outcome)
    assert T.COMMITMENT_DUE in _types(outcome)


@pytest.mark.parametrize("state, expected", [
    ("pending", T.DECISION_PENDING),
    ("blocked", T.DECISION_PENDING),
    ("made", T.DECISION_MADE),
    ("deferred", None),         # a choice to wait is not an open loop
    ("abandoned", None),        # nor is a choice to stop
])
def test_decision_states_map_to_pending_made_or_neither(
        result, decision, eval_time, state, expected):
    outcome = _detect(result(decision_states=[decision(state)]), eval_time)
    decision_kinds = _types(outcome) & {T.DECISION_PENDING, T.DECISION_MADE}
    assert decision_kinds == ({expected} if expected else set())


def test_an_approval_dependency_is_an_approval_request(result, dependency, eval_time):
    outcome = _detect(result(dependencies=[dependency("approval")]), eval_time)
    assert T.APPROVAL_REQUESTED in _types(outcome)


def test_a_non_approval_dependency_is_not_an_approval_request(result, dependency, eval_time):
    outcome = _detect(result(dependencies=[dependency("delivery")]), eval_time)
    assert T.APPROVAL_REQUESTED not in _types(outcome)


def test_the_approve_intent_alone_is_an_approval_request(result, eval_time):
    outcome = _detect(result(intent="approve"), eval_time)
    assert _types(outcome) == {T.APPROVAL_REQUESTED}


@pytest.mark.parametrize("topics, fires", [
    (["contract_renewal"], True),
    (["Contract Renewal"], True),        # topics are free text; casing must not decide
    (["renewal"], True),
    (["budget"], False),
])
def test_a_renewal_topic_is_a_contract_renewal(result, eval_time, topics, fires):
    outcome = _detect(result(topics=topics), eval_time)
    assert (T.CONTRACT_RENEWAL in _types(outcome)) is fires


def test_money_plus_a_recurrence_is_a_contract_renewal_without_the_topic(
        result, money, eval_time):
    """The second half of the predicate: *"a Money AND a recurrence"*. The recurrence is read off
    the source's own wording, because 8_400_000 minor units cannot say whether it repeats."""
    recurring = _detect(result(amounts=[money(as_written="$84K annual")]), eval_time)
    one_off = _detect(result(amounts=[money(as_written="$84K")]), eval_time)
    assert T.CONTRACT_RENEWAL in _types(recurring)
    assert T.CONTRACT_RENEWAL not in _types(one_off)


def test_money_with_a_due_date_is_a_financial_obligation(
        result, money, commitment, dated, eval_time):
    outcome = _detect(result(amounts=[money()], commitments=[commitment(due=dated(3))]), eval_time)
    assert T.FINANCIAL_OBLIGATION in _types(outcome)


def test_money_committed_to_unconditionally_is_a_financial_obligation(
        result, money, commitment, eval_time):
    outcome = _detect(result(intent="commit", amounts=[money()], commitments=[commitment()]),
                      eval_time)
    assert T.FINANCIAL_OBLIGATION in _types(outcome)


def test_money_in_a_conditional_negotiation_is_not_yet_an_obligation(
        result, money, commitment, eval_time):
    """The worked example's own shape: `$84K`, `intent == commit`, and one CONDITIONAL promise.
    A price somebody might agree to is a negotiation, not a payable."""
    outcome = _detect(result(intent="commit", amounts=[money()],
                             commitments=[commitment(is_conditional=True)]), eval_time)
    assert T.FINANCIAL_OBLIGATION not in _types(outcome)


def test_money_with_no_date_and_no_promise_is_not_an_obligation(result, money, eval_time):
    outcome = _detect(result(amounts=[money()]), eval_time)
    assert T.FINANCIAL_OBLIGATION not in _types(outcome)


def test_a_negative_stance_about_a_named_party_is_a_risk(result, entity, eval_time):
    outcome = _detect(result(stance="negative", entity_mentions=[entity()]), eval_time)
    assert T.RISK_FLAGGED in _types(outcome)


def test_a_negative_stance_with_nobody_named_is_not_a_risk(result, eval_time):
    """A risk attributed to nobody is a risk nobody can act on."""
    outcome = _detect(result(stance="negative"), eval_time)
    assert T.RISK_FLAGGED not in _types(outcome)


def test_a_risk_topic_is_a_risk_without_a_negative_stance(result, eval_time):
    outcome = _detect(result(topics=["delivery risk"]), eval_time)
    assert T.RISK_FLAGGED in _types(outcome)


def test_a_positive_stance_with_a_next_step_is_an_opportunity(result, eval_time):
    outcome = _detect(result(stance="positive", implied_actions=["send the expansion quote"]),
                      eval_time)
    assert T.OPPORTUNITY_SIGNAL in _types(outcome)


def test_a_positive_stance_with_no_next_step_is_not_an_opportunity(result, eval_time):
    outcome = _detect(result(stance="positive"), eval_time)
    assert T.OPPORTUNITY_SIGNAL not in _types(outcome)


def test_a_decision_that_settles_a_conditional_promise_is_an_opportunity(
        result, decision, commitment, eval_time):
    """*"A satisfied condition"* — something was waiting on a condition and this message records
    the decision that closes it."""
    outcome = _detect(result(decision_states=[decision("made")],
                             commitments=[commitment(is_conditional=True)]), eval_time)
    assert T.OPPORTUNITY_SIGNAL in _types(outcome)


def test_a_role_assertion_is_a_relationship_change(result, eval_time):
    outcome = _detect(result(roles=[{"party": "Priya", "role": "new AWS owner",
                                     "evidence_text": "Priya is taking this over"}]), eval_time)
    assert T.RELATIONSHIP_CHANGE in _types(outcome)


def test_a_new_party_on_a_known_thread_is_a_relationship_change(result, entity, eval_time):
    outcome = _detect(result(entity_mentions=[entity("Priya", "person")]), eval_time,
                      thread_parties=frozenset({"Rohit", "Finance"}))
    assert T.RELATIONSHIP_CHANGE in _types(outcome)


def test_a_party_the_thread_already_knew_is_not_a_change(result, entity, eval_time):
    outcome = _detect(result(entity_mentions=[entity("Rohit", "person")]), eval_time,
                      thread_parties=frozenset({"rohit"}))
    assert T.RELATIONSHIP_CHANGE not in _types(outcome)


def test_an_unknown_thread_history_never_fires_a_relationship_change(result, entity, eval_time):
    """`thread_parties=None` means the caller does not know who was on this thread. That is not
    the same as "nobody was", and guessing would make every first-seen name a change."""
    outcome = _detect(result(entity_mentions=[entity("Priya", "person")]), eval_time)
    assert T.RELATIONSHIP_CHANGE not in _types(outcome)


def _conflict(field: str, detected_at: datetime, span) -> Conflict:
    """Two sources disagreeing about one field, built the way ALG-12 builds one."""
    claims = [
        ConflictClaim(value=value, authority=authority, authority_rank=rank, evidence=[span])
        for value, authority, rank in
        [("84000", Authority.EMAIL_PROSE, 2), ("74000", Authority.SIGNED_DOCUMENT, 6)]
    ]
    return Conflict(field=field, claims=claims,
                    resolution=ConflictResolution.RESOLVED_BY_AUTHORITY,
                    resolved_value="74000", detected_at=detected_at)


def test_a_conflict_on_a_material_field_is_an_information_conflict(result, a_span, eval_time):
    outcome = _detect(result(), eval_time,
                      conflicts=(_conflict("contract.value", eval_time, a_span),))
    assert T.INFORMATION_CONFLICT in _types(outcome)


def test_a_conflict_on_an_immaterial_field_is_not_a_signal(result, a_span, eval_time):
    """Materiality is ALG-12's own table, reused rather than re-listed — a second list here would
    disagree with the detector's on the first row somebody added to one of them."""
    outcome = _detect(result(), eval_time,
                      conflicts=(_conflict("meeting.room", eval_time, a_span),))
    assert T.INFORMATION_CONFLICT not in _types(outcome)


def test_the_escalate_intent_is_an_escalation(result, eval_time):
    outcome = _detect(result(intent="escalate"), eval_time)
    assert T.ESCALATION in _types(outcome)


@pytest.mark.parametrize("prior, current, fires", [
    (2, 5, True),           # the CFO was added to the thread
    (5, 5, False),          # same authority, no escalation
    (5, 2, False),          # de-escalation is not an escalation
    (None, 5, False),       # one rank alone says nothing about a change
])
def test_authority_increase_in_the_recipient_set_is_an_escalation(
        result, eval_time, prior, current, fires):
    outcome = _detect(result(), eval_time, prior_recipient_authority_rank=prior,
                      recipient_authority_rank=current)
    assert (T.ESCALATION in _types(outcome)) is fires


def test_a_structurally_non_routine_event_that_matches_nothing_else_is_an_anomaly(
        result, decision, eval_time):
    """An abandoned decision fires no named predicate, but a message that abandons a decision is
    not routine. ANOMALY is the catch-all — *"a recognised kind with no recognised cause"*."""
    outcome = _detect(result(decision_states=[decision("abandoned")]), eval_time)
    assert _types(outcome) == {T.ANOMALY}


def test_an_anomaly_never_fires_alongside_a_named_kind(result, decision, eval_time):
    """*"None of the above"* is part of the predicate, not a garnish."""
    outcome = _detect(result(decision_states=[decision("pending"), decision("abandoned")]),
                      eval_time)
    assert T.ANOMALY not in _types(outcome)


def test_the_open_lane_alone_is_never_an_anomaly(result, a_span, eval_time):
    """No rule may read `unclassified_observations` — a detector that fired on a label the model
    invented would be a detector whose behaviour changes when the model's phrasing does."""
    outcome = _detect(result(unclassified_observations=[
        {"proposed_kind": "vibe_shift", "description": "tone changed",
         "evidence": [a_span], "confidence_bp": 5000}]), eval_time)
    assert outcome.signals == ()


# ---------------------------------------------------------------------------------------------
# Multiplicity and the cap.
# ---------------------------------------------------------------------------------------------

def test_one_event_may_produce_more_than_one_signal(
        result, commitment, dated, eval_time):
    """Doc 06, in as many words: an email containing a commitment and a deadline is two signals."""
    outcome = _detect(result(commitments=[commitment()], dates_mentioned=[dated(3)]), eval_time)
    assert _types(outcome) == {T.COMMITMENT_MADE, T.DEADLINE_STATED}


def test_more_than_five_kinds_are_capped_and_the_overflow_is_recorded(
        result, commitment, decision, dependency, dated, money, entity, a_span, eval_time):
    """*"Cap at 5 per event."* The overflow is RETURNED, not dropped: a suppressed signal that
    leaves no record is indistinguishable from a predicate that never fired."""
    outcome = _detect(result(
        intent="escalate", stance="negative", topics=["contract_renewal", "delivery risk"],
        amounts=[money()], entity_mentions=[entity()],
        commitments=[commitment(due=dated(3))],
        decision_states=[decision("pending"), decision("made")],
        dependencies=[dependency("approval")],
        dates_mentioned=[dated(5)],
    ), eval_time, conflicts=(_conflict("contract.value", eval_time, a_span),))

    assert outcome.fired > MAX_SIGNALS_PER_EVENT
    assert len(outcome.signals) == MAX_SIGNALS_PER_EVENT
    assert len(outcome.suppressed) == outcome.fired - MAX_SIGNALS_PER_EVENT
    # kept by ALG-16 precedence, highest first — the only deterministic order that exists at S4
    assert outcome.types[:3] == (T.INFORMATION_CONFLICT, T.ESCALATION, T.APPROVAL_REQUESTED)
    assert not set(outcome.types) & {s.signal_type for s in outcome.suppressed}


def test_detection_is_reproducible_across_two_runs(result, commitment, decision, eval_time):
    extraction = result(commitments=[commitment()], decision_states=[decision("pending")])
    first = _detect(extraction, eval_time)
    second = _detect(extraction, eval_time)
    assert first == second


def test_a_naive_eval_time_is_refused(result):
    """A naive instant compared against a tz-aware `ResolvedDate` is a TypeError at best and a
    wrong answer in the timezone that made it comparable."""
    with pytest.raises(ValueError, match="tz-aware"):
        DetectionInput(extraction=result(), eval_time=datetime(2026, 1, 14, 9, 0))


def test_a_predicate_firing_on_a_message_level_field_cites_no_span(result, eval_time):
    """`intent`, `stance` and `topics` carry no `EvidenceSpan` — they are properties of the whole
    message. The detection is left with an EMPTY receipt rather than the nearest unrelated span:
    a quote that did not produce the claim reads as verified and is worse than none."""
    outcome = _detect(result(topics=["contract_renewal"]), eval_time)
    assert outcome.signals[0].evidence == ()


def test_a_predicate_firing_on_a_claim_carries_that_claims_receipt(
        result, commitment, a_span, eval_time):
    outcome = _detect(result(commitments=[commitment()]), eval_time)
    assert outcome.signals[0].evidence == (a_span,)


# ---------------------------------------------------------------------------------------------
# THE GATE · doc 04 L1.4.3-U2, through the real pipeline.
# ---------------------------------------------------------------------------------------------

def _worked_example_extraction(span_of, eval_time):
    """The doc-04 fixture as an `ExtractionResult`, row for row from its table."""
    from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                    EntityMention, ExtractionResult)
    from genios_engine.contracts.units import Money, ResolvedDate

    return ExtractionResult(
        intent="commit", stance="cautious", topics=["contract_renewal", "budget"],
        entity_mentions=[
            EntityMention(surface_form="Rohit", entity_type="person",
                          evidence=[span_of("Rohit")], confidence_bp=9000),
            EntityMention(surface_form="Finance", entity_type="organization",
                          evidence=[span_of("Finance")], confidence_bp=8800)],
        amounts=[Money(minor_units=8_400_000, currency="USD", as_written="$84K")],
        # "pretty soon" is RELATIVE — a heuristic window, never a stated deadline. That single
        # certainty band is what keeps DEADLINE_STATED out of the emitted set.
        dates_mentioned=[ResolvedDate(
            as_written="pretty soon", earliest=eval_time + timedelta(days=7),
            latest=eval_time + timedelta(days=30), certainty=DateCertainty.RELATIVE,
            resolved_against=eval_time, evidence=[span_of("pretty soon")])],
        commitments=[Commitment(
            actor="Finance", action="confirm absorption of increase", is_conditional=True,
            condition_text="we can probably move forward",
            evidence=[span_of("I still need Finance to confirm whether we can absorb the "
                              "increase")], confidence_bp=8200)],
        decision_states=[DecisionState(
            subject="annual contract", state="pending", blocked_on="Finance confirmation",
            evidence=[span_of("we can probably move forward with the $84K annual contract")],
            confidence_bp=8000)],
        dependencies=[Dependency(
            blocker="Finance", blocked="Rohit", dependency_type="approval",
            evidence=[span_of("I still need Finance to confirm")], confidence_bp=7900)],
        implied_actions=["Finance needs to confirm"],
        model_snapshot="fake-model-1", prompt_version="p1", schema_version="1",
        extraction_profile="email", input_tokens=1000, output_tokens=200)


@pytest.mark.gate
def test_worked_example_yields_exactly_three_named_signals(span_of, eval_time):
    """Set equality against {CONTRACT_RENEWAL, DECISION_PENDING, APPROVAL_REQUESTED}.

    Not a superset. COMMITMENT_MADE does not fire because the promise is conditional;
    FINANCIAL_OBLIGATION does not fire because $84K is attached to that same conditional promise
    and to no date; DEADLINE_STATED does not fire because "pretty soon" never became a date.
    """
    extraction = _worked_example_extraction(span_of, eval_time)
    outcome = _detect(extraction, eval_time)

    assert _types(outcome) == {T.CONTRACT_RENEWAL, T.DECISION_PENDING, T.APPROVAL_REQUESTED}
    assert len(outcome.signals) == 3


def _cite(text: str, quote: str) -> list[dict]:
    """A model-shaped citation with the offset FOUND, exactly as the extractor's own tests build
    one — the pipeline verifies these against the prepared text, so a counted number would make
    this test pass or fail on typography."""
    start = text.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


def _worked_example_payload(text: str) -> dict:
    """The answer a correct model gives for doc 04's worked example, in the MODEL's output shape.

    Written as JSON rather than as contract objects on purpose: this test's claim is that the
    REAL pipeline qualifies a real extraction, and a hand-built `ExtractionResult` would have
    skipped the parse, the span verification and the seam that were the thing being proven.
    """
    return {
        "intent": "commit", "stance": "cautious",
        "topics": ["contract_renewal", "budget"],
        "entity_mentions": [
            {"surface_form": "Rohit", "entity_type": "person",
             "evidence": _cite(text, "Rohit"), "confidence_bp": 9000},
            {"surface_form": "Finance", "entity_type": "organization",
             "evidence": _cite(text, "Finance"), "confidence_bp": 8800}],
        "amounts": [{"minor_units": 8_400_000, "currency": "USD", "as_written": "$84K"}],
        "dates_mentioned": [{"as_written": "pretty soon", "certainty": "relative",
                             "evidence": _cite(text, "pretty soon")}],
        "commitments": [
            {"actor": "Finance", "action": "confirm absorption of increase",
             "beneficiary": None, "is_conditional": True,
             "condition_text": "we can probably move forward",
             "evidence": _cite(
                 text, "I still need Finance to confirm whether we can absorb the increase"),
             "confidence_bp": 8200}],
        "decision_states": [
            {"subject": "annual contract", "state": "pending",
             "blocked_on": "Finance confirmation",
             "evidence": _cite(text, "we can probably move forward with the $84K annual contract"),
             "confidence_bp": 8000}],
        "dependencies": [
            {"blocker": "Finance", "blocked": "Rohit", "dependency_type": "approval",
             "evidence": _cite(text, "I still need Finance to confirm"), "confidence_bp": 7900}],
        "implied_actions": ["Finance needs to confirm"], "questions": [],
    }


@pytest.mark.gate
def test_the_real_pipeline_qualifies_the_worked_example(fake_llm, worked_example_text):
    """THE WIRING GATE — `capture_event`, the production entry point, not the unit in isolation.

    Three units have already shipped in this build with no production caller (`extract()`, the
    scheduler, the cost governor), so the assertion that matters is not "the predicate table is
    correct" but "an event that reaches L1 comes out the other side carrying its qualification".
    A `CaptureResult` whose `detection` is `None` on an emitted event with an extraction means
    S4 is dead weight again, however green the unit tests are.
    """
    owner = "founder@genios.ai"
    when = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
    llm = fake_llm(_worked_example_payload(worked_example_text))
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m_esqe_1",
                    occurred_at=when, actor_email="buyer@acme.com", recipients=(owner,),
                    raw={"subject": "Annual contract", "body": worked_example_text})

    res = P.capture_event(raw, org_id="org_esqe", connection_id="con_esqe",
                          repo=InMemorySourceEventRepository(), mailbox_owner=owner,
                          semantic=P.SemanticLane(llm=llm, eval_time=when))

    assert res.outcome == "emitted"
    assert res.extraction is not None, "no extraction — this test would prove nothing about S4"
    assert res.detection is not None, "S4 was built but never called from the pipeline"
    assert set(res.detection.types) == {T.CONTRACT_RENEWAL, T.DECISION_PENDING,
                                        T.APPROVAL_REQUESTED}
    assert res.qualification is not None
    assert res.qualification.primary is T.APPROVAL_REQUESTED
    assert P.ESQE_STAGE in [r.stage for r in res.trace.records], (
        "a qualification that leaves no trace is unauditable")
    row = next(r for r in res.trace.records if r.stage == P.ESQE_STAGE)
    assert row.detail["signal_type"] == T.APPROVAL_REQUESTED.value


def test_an_event_with_no_extraction_is_not_qualified_at_all(fake_llm):
    """No lane wired, no extraction, therefore no detection — `None`, not an empty outcome. The
    two are different facts: one says S4 had nothing to read, the other says it read the event
    and found nothing to act on, and only the second belongs in `no_signal_rate`."""
    when = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m_esqe_2",
                    occurred_at=when, actor_email="buyer@acme.com",
                    recipients=("founder@genios.ai",), raw={"subject": "Hi", "body": "Thanks!"})

    res = P.capture_event(raw, org_id="org_esqe", connection_id="con_esqe",
                          repo=InMemorySourceEventRepository(),
                          mailbox_owner="founder@genios.ai")

    assert res.outcome == "emitted"
    assert res.detection is None and res.qualification is None

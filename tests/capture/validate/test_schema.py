"""G1 · L1.5.6 Schema Validator — the structural gate between the model's answer and S3.

The unit under test answers one question — does this `ExtractionResult` conform to the closed
schema — and its whole value is that a NO names the field. So every row here asserts on two
things: the rule that fired and the exact field path it fired on. Asserting only "it failed"
would pass just as happily against a validator that rejected everything, and a validator that
rejects everything is indistinguishable, from the tenant's side, from an extractor that
produces nothing.

Three deliberate shapes in this file:

* **The conformant fixture is built through the real constructor.** If it were assembled with
  `model_construct` the suite could not tell "the validator agrees with the contract" from
  "the fixture was never legal in the first place", and the pass row would be worthless.
* **Every failing row is built with `model_construct` / `model_copy(update=...)`.** Those are
  the two documented routes past a pydantic validator, and they are the routes a cached row,
  an extractor repair path and a well-meaning caller actually take. A defect that the
  constructor already refuses is not evidence about this unit — so each row here is an object
  that a constructor would never have produced but that S3 can genuinely be handed.
* **Boundary rows are assertions about what this unit must NOT do.** An unverified span, an
  UNKNOWN currency and a thirty-day "pretty soon" window all conform, because verifying spans
  is ALG-08, parsing money is ALG-10 and resolving dates is ALG-09. Without those rows nothing
  stops L1.5.6 from quietly growing into a second, weaker copy of all three.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import datetime, timedelta
from typing import Any

import pytest

from genios_engine.capture.validate.schema import (ARRIVAL_ONLY_RULES, ExtractionVocabulary,
                                                   SchemaRule, ValidationStage,
                                                   validate_extraction_schema)
from genios_engine.capture.validate.spans import apply_verdicts
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate

WAVE = "W1"
GATE = "G1"

#: The two seams, named here so every row in this file says which object it is holding. There is
#: no bare `validate_extraction_schema(x, vocabulary=v)` anywhere below on purpose: the stage
#: decides whether S-9 runs, and a call that leaves it to the default is a call whose author had
#: not decided. `test_every_call_site_names_its_stage` enforces that for the whole repo.
ARRIVAL = ValidationStage.EXTRACTOR_OUTPUT
POST_VERIFICATION = ValidationStage.POST_VERIFICATION

#: The doc-04 L1.4.4-U1 closed sets, restated here because W3 has not landed `vocabulary.py`
#: yet and the unit deliberately takes the sets as a parameter rather than owning a copy. When
#: W3 lands, this fixture becomes an import and `tests/capture/semantic/test_vocabulary.py`
#: owns the words — which is the point of passing them in.
DOC_04_VOCABULARY = ExtractionVocabulary(
    intent=frozenset({"inform", "request", "commit", "decide", "escalate", "schedule",
                      "negotiate", "approve", "reject", "question", "acknowledge", "introduce"}),
    entity_type=frozenset({"person", "organization", "vendor", "product", "document", "project"}),
    decision_state=frozenset({"pending", "made", "blocked", "deferred", "abandoned"}),
    dependency_type=frozenset({"approval", "information", "delivery", "decision"}),
    stance=frozenset({"positive", "neutral", "cautious", "negative", "mixed"}),
    extraction_profile=frozenset({"email", "chat", "transcript", "document", "crm_note"}),
)

#: The eight fields `ExtractionResult` declares without a default. They are the only ones that
#: can actually go ABSENT — `model_construct` fills every defaulted field — so they are the
#: honest parametrization for S-1 rather than a list somebody chose.
NO_DEFAULT_FIELDS = tuple(name for name, field in ExtractionResult.model_fields.items()
                          if field.is_required())


@pytest.fixture
def vocabulary() -> ExtractionVocabulary:
    return DOC_04_VOCABULARY


@pytest.fixture
def conformant_data(span_of, eval_time: datetime) -> dict[str, Any]:
    """Every field of a well-formed extraction of the doc-04 worked example.

    Returned as kwargs rather than as a built object so a row can remove one key, replace one
    claim, or rebuild the whole thing through `model_construct` — which is how a defect that
    the constructor refuses gets in front of the validator at all.
    """
    amount_span = span_of("$84K annual contract")
    finance_span = span_of("Finance to confirm whether we can absorb the increase")
    renewal_span = span_of("our renewal is coming up pretty soon")
    commitment_span = span_of("we can probably move forward with the $84K annual contract")

    renewal_window = ResolvedDate(
        as_written="pretty soon", earliest=eval_time, latest=eval_time + timedelta(days=30),
        certainty=DateCertainty.RELATIVE, resolved_against=eval_time, evidence=[renewal_span])

    return {
        "intent": "commit",
        "topics": ["annual contract", "renewal"],
        "stance": "cautious",
        "entity_mentions": [
            EntityMention(surface_form="Finance", entity_type="organization",
                          evidence=[finance_span], confidence_bp=8200),
        ],
        "amounts": [Money(minor_units=8_400_000, currency="USD", as_written="$84K")],
        "dates_mentioned": [renewal_window],
        "commitments": [
            Commitment(actor="the sender", action="move forward with the annual contract",
                       beneficiary="Rohit", due=renewal_window, is_conditional=True,
                       condition_text="once Finance confirms", evidence=[commitment_span],
                       confidence_bp=7100),
        ],
        "decision_states": [
            DecisionState(subject="the annual contract", state="blocked",
                          blocked_on="Finance confirmation", owner="Finance",
                          evidence=[finance_span], confidence_bp=6600),
        ],
        "dependencies": [
            Dependency(blocker="Finance confirmation", blocked="the annual contract",
                       dependency_type="approval", evidence=[finance_span], confidence_bp=6000),
        ],
        "implied_actions": ["ask Finance whether the increase can be absorbed"],
        "questions": [],
        "roles": [{"party": "Finance", "role": "approver"}],
        "relationships": [{"from": "the sender", "to": "Rohit", "kind": "corresponded_with"}],
        "scheduling_proposals": [],
        "unclassified_observations": [
            UnclassifiedObservation(proposed_kind="budget_absorption_doubt",
                                    description="the buyer is unsure the increase fits budget",
                                    evidence=[finance_span], confidence_bp=5400),
        ],
        "field_confidence": {"intent": 9000, "commitments": 7100},
        "all_evidence": [amount_span, finance_span, renewal_span, commitment_span],
        "model_snapshot": "fake-model-1-20260114",
        "prompt_version": "l1.4.3-2026-01-14",
        "schema_version": "2",
        "extraction_profile": "email",
        "input_tokens": 1200,
        "output_tokens": 340,
    }


@pytest.fixture
def conformant(conformant_data: dict[str, Any]) -> ExtractionResult:
    """Built through the REAL constructor — so a failure here is the fixture, not the unit."""
    return ExtractionResult(**conformant_data)


def bypassed(data: dict[str, Any], **overrides: Any) -> ExtractionResult:
    """An `ExtractionResult` that skipped validation, the way a cached row or a repair path can.

    `model_construct` is pydantic's documented no-validation constructor: it fills defaults and
    accepts whatever else it is given. Passing `None` for a key removes it entirely, which is
    how a row exercises an ABSENT field rather than a null one — the two are different defects
    and S-1 reports them differently.
    """
    merged = {**data, **overrides}
    return ExtractionResult.model_construct(**{key: value for key, value in merged.items()
                                               if value is not _REMOVE})


class _Remove:
    """Sentinel: this key is not passed to `model_construct` at all."""


_REMOVE = _Remove()


def violations_on(report: Any, field: str) -> list[Any]:
    """Every violation reported against one exact field path."""
    return [violation for violation in report.violations if violation.field == field]


def rules_on(report: Any, field: str) -> set[SchemaRule]:
    return {violation.rule for violation in violations_on(report, field)}


# --------------------------------------------------------------------------------------
# the pass row
# --------------------------------------------------------------------------------------

def test_a_conformant_extraction_conforms_with_no_violations(conformant, vocabulary):
    """The whole worked example, every field populated, every claim carrying a receipt."""
    report = validate_extraction_schema(conformant, vocabulary=vocabulary, stage=ARRIVAL)
    assert report.violations == ()
    assert report.conforms is True
    assert report.failed_fields == ()


def test_empty_claim_lists_conform(conformant_data, vocabulary):
    """An extraction that found nothing is well-formed, not malformed.

    A message can genuinely contain no commitment and no dependency; if the validator read an
    empty list as a missing field it would reject most of an inbox, which is the failure mode
    that makes a gate get switched off.
    """
    empty = {**conformant_data, "commitments": [], "decision_states": [], "dependencies": [],
             "entity_mentions": [], "amounts": [], "dates_mentioned": [],
             "unclassified_observations": [], "topics": [], "implied_actions": [],
             "roles": [], "relationships": [], "field_confidence": {}, "all_evidence": []}
    report = validate_extraction_schema(ExtractionResult(**empty), vocabulary=vocabulary,
                                        stage=ARRIVAL)
    assert report.violations == ()


def test_the_structured_lane_shape_conforms(conformant_data, vocabulary):
    """L1.3.9's mapping lane: every confidence at 10000 and zero tokens spent.

    S3 is required to be unable to tell the two lanes apart, so a validator that treated
    `input_tokens == 0` or a 10000 confidence as suspicious would reintroduce the split the
    shared shape exists to remove.
    """
    mapped = ExtractionResult(**{**conformant_data, "input_tokens": 0, "output_tokens": 0,
                                 "field_confidence": {"amounts": 10_000}})
    report = validate_extraction_schema(mapped, vocabulary=vocabulary, stage=ARRIVAL)
    assert report.violations == ()
    assert mapped.is_structured_lane is True


# --------------------------------------------------------------------------------------
# S-1 · presence
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("field", NO_DEFAULT_FIELDS)
def test_an_absent_field_fails_s1_and_names_that_field(conformant_data, vocabulary, field):
    """One row per field the schema requires without a default — the only ones that can vanish."""
    report = validate_extraction_schema(bypassed(conformant_data, **{field: _REMOVE}),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert report.conforms is False
    assert SchemaRule.S1 in rules_on(report, field)
    assert field in report.failed_fields


def test_the_no_default_field_list_is_not_empty():
    """Guards the parametrization above: if `is_required()` ever returned nothing, the eight
    S-1 rows would silently become zero rows and the suite would still be green."""
    assert len(NO_DEFAULT_FIELDS) >= 8
    assert "intent" in NO_DEFAULT_FIELDS and "extraction_profile" in NO_DEFAULT_FIELDS


@pytest.mark.parametrize("field", ["commitments", "topics", "field_confidence", "all_evidence"])
def test_a_null_field_fails_s1_separately_from_an_absent_one(conformant_data, vocabulary, field):
    """`None` is not an empty list. The schema declares no nullable field, so a null is an
    extractor that answered the question with nothing rather than one that found nothing."""
    report = validate_extraction_schema(bypassed(conformant_data, **{field: None}),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S1 in rules_on(report, field)


def test_a_missing_field_is_reported_once_not_cascaded(conformant_data, vocabulary):
    """A null `commitments` is ONE defect. Reporting it again as a shape failure and again as a
    missing receipt turns a diagnosis into a wall nobody reads.

    Null rather than absent because every list field carries a `default_factory`, so
    `model_construct` fills it: the only way a claim list arrives missing is that the extractor
    answered the question with nothing, which is precisely the case that must not cascade.
    """
    report = validate_extraction_schema(bypassed(conformant_data, commitments=None),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert [violation.rule for violation in report.violations
            if violation.field.startswith("commitments")] == [SchemaRule.S1]


# --------------------------------------------------------------------------------------
# S-3 · closed vocabulary
# --------------------------------------------------------------------------------------

def _with_entity(data: dict[str, Any], entity_type: str) -> dict[str, Any]:
    mention = data["entity_mentions"][0]
    return {**data, "entity_mentions": [EntityMention.model_construct(
        surface_form=mention.surface_form, entity_type=entity_type, canonical_hint=None,
        evidence=list(mention.evidence), confidence_bp=mention.confidence_bp)]}


def _with_state(data: dict[str, Any], state: str) -> dict[str, Any]:
    decision = data["decision_states"][0]
    return {**data, "decision_states": [DecisionState.model_construct(
        subject=decision.subject, state=state, blocked_on=decision.blocked_on,
        owner=decision.owner, evidence=list(decision.evidence),
        confidence_bp=decision.confidence_bp)]}


def _with_dependency(data: dict[str, Any], dependency_type: str) -> dict[str, Any]:
    dependency = data["dependencies"][0]
    return {**data, "dependencies": [Dependency.model_construct(
        blocker=dependency.blocker, blocked=dependency.blocked,
        dependency_type=dependency_type, evidence=list(dependency.evidence),
        confidence_bp=dependency.confidence_bp)]}


def _with_certainty(data: dict[str, Any], certainty: Any) -> dict[str, Any]:
    date = data["dates_mentioned"][0]
    broken = ResolvedDate.model_construct(
        as_written=date.as_written, earliest=date.earliest, latest=date.latest,
        certainty=certainty, resolved_against=date.resolved_against,
        evidence=list(date.evidence))
    return {**data, "dates_mentioned": [broken]}


@pytest.mark.parametrize("mutate,field,why", [
    (lambda d: {**d, "intent": "celebrate"}, "intent",
     "a twelve-member intent set the prompt named; a thirteenth is drift"),
    (lambda d: {**d, "stance": "optimistic"}, "stance",
     "the plausible synonym is the dangerous case — no rule matches it"),
    (lambda d: {**d, "stance": "Positive"}, "stance",
     "membership is case-sensitive; title-casing a value for the caller hides the drift"),
    (lambda d: {**d, "extraction_profile": "voicemail"}, "extraction_profile",
     "a replay cannot re-run a profile that does not exist"),
    (lambda d: _with_entity(d, "robot"), "entity_mentions[0].entity_type",
     "the path names the claim, not just the list"),
    (lambda d: _with_state(d, "parked"), "decision_states[0].state",
     "'parked' is a real word elsewhere in the system and still not a decision state"),
    (lambda d: _with_dependency(d, "vibes"), "dependencies[0].dependency_type",
     "the kind decides who gets escalated to"),
    (lambda d: _with_certainty(d, "probably"), "dates_mentioned[0].certainty",
     "a band nobody can read is a window nothing may treat as a deadline"),
])
def test_a_value_outside_its_closed_set_fails_s3_and_names_the_path(
        conformant_data, vocabulary, mutate, field, why):
    """One row per closed set. The failure must name the exact path, because the fix is always
    in the prompt or the vocabulary and neither is findable from 'the extraction was bad'."""
    report = validate_extraction_schema(bypassed(mutate(conformant_data)),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S3 in rules_on(report, field), why
    assert report.conforms is False


def test_an_out_of_set_value_is_never_coerced_to_a_neighbour(conformant_data, vocabulary):
    """The validator reports; it does not repair. A silently corrected value is a drift nobody
    ever sees, and the extraction that reaches the store is not the one the model produced."""
    broken = bypassed({**conformant_data, "stance": "optimistic"})
    validate_extraction_schema(broken, vocabulary=vocabulary, stage=ARRIVAL)
    assert broken.stance == "optimistic"


def test_field_confidence_keyed_on_an_unknown_name_fails_s3(conformant_data, vocabulary):
    """The recorded v1 failure in miniature: the extractor writes `deal.status`, every reader
    looks for a field of that name, and the number is dead on arrival."""
    report = validate_extraction_schema(
        bypassed(conformant_data, field_confidence={"deal.status": 9000}),
        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S3 in rules_on(report, "field_confidence['deal.status']")


# --------------------------------------------------------------------------------------
# S-4 · every claim carries a receipt
# --------------------------------------------------------------------------------------

def _evidenceless(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Rebuild the first claim in `name` with an empty evidence list, past the constructor."""
    claim = data[name][0]
    fields = {key: getattr(claim, key) for key in type(claim).model_fields}
    fields["evidence"] = []
    return {**data, name: [type(claim).model_construct(**fields)]}


@pytest.mark.parametrize("name,path", [
    ("entity_mentions", "entity_mentions[0].evidence"),
    ("commitments", "commitments[0].evidence"),
    ("decision_states", "decision_states[0].evidence"),
    ("dependencies", "dependencies[0].evidence"),
    ("dates_mentioned", "dates_mentioned[0].evidence"),
    ("unclassified_observations", "unclassified_observations[0].evidence"),
])
def test_a_claim_with_no_evidence_fails_s4_and_names_the_claim(
        conformant_data, vocabulary, name, path):
    """Universal rule 4, one row per claim type that carries a receipt — including the open
    lane, which doc 04 requires span-validated exactly like any other claim."""
    report = validate_extraction_schema(bypassed(_evidenceless(conformant_data, name)),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S4 in rules_on(report, path)
    assert report.conforms is False


def test_a_commitments_nested_due_date_needs_its_own_receipt(conformant_data, vocabulary):
    """The nested `ResolvedDate` is a claim too — it is what the deadline term reads."""
    commitment = conformant_data["commitments"][0]
    undated = ResolvedDate.model_construct(
        as_written=commitment.due.as_written, earliest=commitment.due.earliest,
        latest=commitment.due.latest, certainty=commitment.due.certainty,
        resolved_against=commitment.due.resolved_against, evidence=[])
    broken = Commitment.model_construct(
        **{**{key: getattr(commitment, key) for key in Commitment.model_fields}, "due": undated})
    report = validate_extraction_schema(bypassed(conformant_data, commitments=[broken]),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S4 in rules_on(report, "commitments[0].due.evidence")


def test_an_amount_is_not_accused_of_missing_a_receipt(conformant_data, vocabulary):
    """`Money` declares no evidence field, so the checks it earns are the ones it declares.

    A validator that demanded a receipt from every element of every list would reject every
    extraction that contains an amount — the sort of false rejection that gets a gate disabled
    rather than fixed.
    """
    report = validate_extraction_schema(bypassed(conformant_data), vocabulary=vocabulary,
                                        stage=ARRIVAL)
    assert not [violation for violation in report.violations
                if violation.field.startswith("amounts")]


def test_evidence_holding_a_non_span_fails_the_shape(conformant_data, vocabulary):
    """A receipt that is a bare string cannot be resolved by ALG-08 and cannot be shown."""
    commitment = conformant_data["commitments"][0]
    broken = Commitment.model_construct(
        **{**{key: getattr(commitment, key) for key in Commitment.model_fields},
           "evidence": ["we can probably move forward"]})
    report = validate_extraction_schema(bypassed(conformant_data, commitments=[broken]),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S2 in rules_on(report, "commitments[0].evidence[0]")
    assert SchemaRule.S4 in rules_on(report, "commitments[0].evidence")


# --------------------------------------------------------------------------------------
# S-5 · scores are exact integers in range
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("score,why", [
    (10_001, "one past the ceiling — the range is closed at 10000"),
    (-1, "a negative confidence is not a small error, it is a different kind of value"),
    (8000.0, "a whole number written as a ratio still composes irreproducibly"),
    ("8000", "text that looks like a score would be coerced by a lax annotation"),
    (True, "a bool is an int in Python and would pass an isinstance check"),
    (None, "an absent score reads as zero confidence downstream"),
])
def test_a_claim_confidence_out_of_range_fails_s5_and_names_the_claim(
        conformant_data, vocabulary, score, why):
    """One row per way a confidence stops being integer basis points."""
    commitment = conformant_data["commitments"][0]
    broken = Commitment.model_construct(
        **{**{key: getattr(commitment, key) for key in Commitment.model_fields},
           "confidence_bp": score})
    report = validate_extraction_schema(bypassed(conformant_data, commitments=[broken]),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S5 in rules_on(report, "commitments[0].confidence_bp"), why


@pytest.mark.parametrize("score", [10_001, -5, 0.87, "9000"])
def test_a_field_confidence_value_out_of_range_fails_s5(conformant_data, vocabulary, score):
    """The dict is where a ratio gets in: the `dict[str, int]` annotation alone would let lax
    coercion round one and call it a confidence."""
    report = validate_extraction_schema(
        bypassed(conformant_data, field_confidence={"intent": score}),
        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S5 in rules_on(report, "field_confidence['intent']")


@pytest.mark.parametrize("field,value", [
    ("input_tokens", -1), ("output_tokens", -200), ("input_tokens", 1200.5),
])
def test_a_negative_or_fractional_token_count_fails_s5(conformant_data, vocabulary,
                                                       field, value):
    """Token counts are a count of things that happened, and they land in cost attribution."""
    report = validate_extraction_schema(bypassed(conformant_data, **{field: value}),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S5 in rules_on(report, field)


def test_the_range_boundaries_themselves_conform(conformant_data, vocabulary):
    """0 and 10000 are inside the closed range — an off-by-one here would reject every
    structured-lane extraction, all of which stamp exactly 10000."""
    commitment = conformant_data["commitments"][0]
    floor = Commitment.model_construct(
        **{**{key: getattr(commitment, key) for key in Commitment.model_fields},
           "confidence_bp": 0})
    ceiling = Commitment.model_construct(
        **{**{key: getattr(commitment, key) for key in Commitment.model_fields},
           "confidence_bp": 10_000})
    report = validate_extraction_schema(
        bypassed(conformant_data, commitments=[floor, ceiling],
                 field_confidence={"intent": 0, "commitments": 10_000}, input_tokens=0),
        vocabulary=vocabulary, stage=ARRIVAL)
    assert report.violations == ()


# --------------------------------------------------------------------------------------
# S-6 · the two forbidden scores
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("field,value", [("importance_bp", 7000), ("priority_bp", 3)])
def test_a_forbidden_score_fails_s6(conformant, vocabulary, field, value):
    """`model_copy(update=...)` writes straight into the instance, which is exactly the route a
    caller takes when a prompt starts emitting a score. The model describes; S4 scores."""
    smuggled = conformant.model_copy(update={field: value})
    report = validate_extraction_schema(smuggled, vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S6 in rules_on(report, field)
    assert report.conforms is False


# --------------------------------------------------------------------------------------
# S-7 · all_evidence is the index ALG-08 walks
# --------------------------------------------------------------------------------------

def test_a_claims_span_missing_from_all_evidence_fails_s7(conformant_data, vocabulary):
    """A span left out of the index is never verified AND never reported unverified — a
    fabricated quote surviving the whole anti-hallucination mechanism by omission."""
    commitment_span = conformant_data["commitments"][0].evidence[0]
    thinned = [span for span in conformant_data["all_evidence"] if span != commitment_span]
    report = validate_extraction_schema(
        ExtractionResult(**{**conformant_data, "all_evidence": thinned}),
        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S7 in rules_on(report, "all_evidence")


def test_a_span_in_all_evidence_attached_to_no_claim_is_allowed(conformant, vocabulary):
    """The reverse direction is unattributed, not invalid — the contract's own docstring says
    comparing the two lists is how such a span is FOUND, so this unit must not refuse it."""
    report = validate_extraction_schema(conformant, vocabulary=vocabulary, stage=ARRIVAL)
    assert report.violations == ()
    assert len(conformant.all_evidence) > len(conformant.evidence_from_claims())


# --------------------------------------------------------------------------------------
# S-8 · the open-lane cap is advisory
# --------------------------------------------------------------------------------------

def test_over_cap_open_lane_is_reported_but_still_conforms(conformant_data, vocabulary):
    """The cap is a prompt instruction, not a validator: failing the extraction over it would
    let one over-eager extractor destroy a whole message. Reported so a drifting profile is
    visible before the weekly report, non-blocking so nothing is lost."""
    observation = conformant_data["unclassified_observations"][0]
    report = validate_extraction_schema(
        ExtractionResult(**{**conformant_data, "unclassified_observations": [observation] * 6}),
        vocabulary=vocabulary, stage=ARRIVAL)
    marks = violations_on(report, "unclassified_observations")
    assert [violation.rule for violation in marks] == [SchemaRule.S8]
    assert marks[0].blocking is False
    assert report.conforms is True
    assert report.failed_fields == ()


def test_exactly_at_the_cap_is_not_reported(conformant_data, vocabulary):
    """Five is the cap, not the first value over it."""
    observation = conformant_data["unclassified_observations"][0]
    report = validate_extraction_schema(
        ExtractionResult(**{**conformant_data, "unclassified_observations": [observation] * 5}),
        vocabulary=vocabulary, stage=ARRIVAL)
    assert report.violations == ()


# --------------------------------------------------------------------------------------
# S-2 · shape
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("override,field,why", [
    ({"commitments": "one commitment"}, "commitments",
     "a string is a Sequence and would be walked one character at a time"),
    ({"topics": ["annual contract", "   "]}, "topics[1]",
     "a blank topic renders as a blank line and counts in every tally above"),
    ({"topics": "annual contract"}, "topics", "a bare string is not a list of strings"),
    ({"field_confidence": [("intent", 9000)]}, "field_confidence",
     "a list of pairs is not a mapping"),
    ({"roles": [{"party": "Finance"}, "approver"]}, "roles[1]",
     "the untyped lanes are still lists of objects"),
    ({"intent": ""}, "intent", "empty text is not a vocabulary value"),
    ({"extraction_profile": 3}, "extraction_profile", "a profile id is text"),
], ids=["claim-list-is-text", "blank-topic", "topics-is-text", "confidence-is-pairs",
        "role-is-text", "empty-intent", "profile-is-number"])
def test_a_wrong_shape_fails_s2_and_names_the_field(conformant_data, vocabulary, override,
                                                    field, why):
    report = validate_extraction_schema(bypassed(conformant_data, **override),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S2 in rules_on(report, field), why


def test_a_claim_of_the_wrong_type_fails_s2(conformant_data, vocabulary):
    """A `DecisionState` sitting in `commitments` has the wrong fields entirely, and every
    reader below would ask it for an actor it does not have."""
    report = validate_extraction_schema(
        bypassed(conformant_data, commitments=[conformant_data["decision_states"][0]]),
        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S2 in rules_on(report, "commitments[0]")


@pytest.mark.parametrize("flag", ["yes", 1, None])
def test_a_non_bool_is_conditional_fails_s2(conformant_data, vocabulary, flag):
    """Truthiness coercion is how a conditional promise becomes an unconditional one, and an
    unconditional promise with a date becomes a false overdue — the second false chase is the
    last time a founder reads a nudge from us."""
    commitment = conformant_data["commitments"][0]
    broken = Commitment.model_construct(
        **{**{key: getattr(commitment, key) for key in Commitment.model_fields},
           "is_conditional": flag})
    report = validate_extraction_schema(bypassed(conformant_data, commitments=[broken]),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S2 in rules_on(report, "commitments[0].is_conditional")


def test_a_due_that_is_not_a_resolved_date_fails_s2(conformant_data, vocabulary):
    """A bare timestamp cannot say whether it came from 'October 15' or from 'pretty soon'."""
    commitment = conformant_data["commitments"][0]
    broken = Commitment.model_construct(
        **{**{key: getattr(commitment, key) for key in Commitment.model_fields},
           "due": "2026-02-01"})
    report = validate_extraction_schema(bypassed(conformant_data, commitments=[broken]),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert SchemaRule.S2 in rules_on(report, "commitments[0].due")


# --------------------------------------------------------------------------------------
# the report itself
# --------------------------------------------------------------------------------------

def test_every_defect_is_reported_not_just_the_first(conformant_data, vocabulary):
    """Two defects are two upstream bugs. Stopping at the first means fixing one reveals the
    other a release later, and the pipeline stays broken for three releases."""
    broken = bypassed(_evidenceless({**conformant_data, "stance": "optimistic",
                                     "input_tokens": -1}, "commitments"),
                      extraction_profile=_REMOVE)
    report = validate_extraction_schema(broken, vocabulary=vocabulary, stage=ARRIVAL)
    assert report.failed_rules == (SchemaRule.S1, SchemaRule.S3, SchemaRule.S4, SchemaRule.S5)
    assert set(report.failed_fields) == {"extraction_profile", "stance", "input_tokens",
                                         "commitments[0].evidence"}


def test_violations_are_grouped_by_rule_in_rule_order(conformant_data, vocabulary):
    """A reader sees all the missing fields together rather than interleaved with vocabulary
    misses — the difference between a report that is read and one that is skimmed."""
    broken = bypassed({**conformant_data, "stance": "optimistic"},
                      intent=_REMOVE, extraction_profile=_REMOVE)
    report = validate_extraction_schema(broken, vocabulary=vocabulary, stage=ARRIVAL)
    order = [violation.rule for violation in report.violations]
    assert order == sorted(order, key=lambda rule: list(SchemaRule).index(rule))
    assert order == [SchemaRule.S1, SchemaRule.S1, SchemaRule.S3]


def test_a_refusal_is_returned_not_raised(conformant_data, vocabulary):
    """S3 may flag; it may not drop. A traceback out of a publisher loop is a log line, and the
    next question a tenant asks is about the message that produced nothing."""
    report = validate_extraction_schema(bypassed(conformant_data, intent=_REMOVE),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert report.conforms is False
    assert str(report.violations[0]).startswith("S-1 intent:")


def test_validation_does_not_mutate_the_extraction(conformant, vocabulary):
    """A caller that logs the extraction after a refusal must log what it actually handed over."""
    before = conformant.model_dump()
    validate_extraction_schema(conformant, vocabulary=vocabulary, stage=ARRIVAL)
    assert conformant.model_dump() == before


# --------------------------------------------------------------------------------------
# the vocabulary is a parameter, and it fails closed
# --------------------------------------------------------------------------------------

def test_an_empty_vocabulary_set_is_refused_at_construction():
    """An empty closed set rejects every extraction that has the field, and a pipeline
    producing nothing reads as a broken extractor for as long as it takes somebody to find the
    empty frozenset. Point at the caller instead."""
    with pytest.raises(ValueError):
        ExtractionVocabulary(intent=frozenset(), entity_type=frozenset({"person"}),
                             decision_state=frozenset({"pending"}),
                             dependency_type=frozenset({"approval"}),
                             stance=frozenset({"neutral"}),
                             extraction_profile=frozenset({"email"}))


def test_a_promoted_vocabulary_member_is_accepted_without_touching_this_unit(conformant_data):
    """L1.4.5-U2: promotion adds a word to `vocabulary.py` and bumps the schema version. If the
    sets were constants in the validator, a promotion would need an edit here — and until
    somebody made it, the pipeline would reject the value the prompt had just been told to
    emit."""
    promoted = DOC_04_VOCABULARY.model_copy(
        update={"stance": DOC_04_VOCABULARY.stance | {"optimistic"}})
    report = validate_extraction_schema(bypassed(conformant_data, stance="optimistic"),
                                        vocabulary=promoted, stage=ARRIVAL)
    assert report.violations == ()


# --------------------------------------------------------------------------------------
# the boundary — what this unit must NOT do
# --------------------------------------------------------------------------------------

def test_unverified_spans_conform_because_verification_is_alg_08(conformant, vocabulary):
    """Every span an extractor produces has `verified=False`; only L1.5.1 may set it True. If
    this unit rejected them it would reject every extraction ever handed to S3."""
    assert all(span.verified is False for span in conformant.all_evidence)
    assert validate_extraction_schema(conformant, vocabulary=vocabulary,
                                      stage=ARRIVAL).violations == ()


def test_an_unknown_currency_conforms_because_parsing_is_alg_10(conformant_data, vocabulary):
    """ALG-10 answers an ambiguous symbol with `UNKNOWN` rather than a guess. That is a
    normalization outcome, not a schema defect, and a validator that refused it would push the
    normalizer back towards defaulting to USD."""
    unknown = Money(minor_units=8_400, currency="UNKNOWN", as_written="$84")
    report = validate_extraction_schema(
        ExtractionResult(**{**conformant_data, "amounts": [unknown]}),
        vocabulary=vocabulary, stage=ARRIVAL)
    assert report.violations == ()


def test_a_wide_relative_window_conforms_because_resolution_is_alg_09(conformant_data,
                                                                     vocabulary, eval_time):
    """'pretty soon' resolves to a thirty-day RELATIVE window. Whether that window is the right
    one is ALG-09's question; whether the band is a word at all is this unit's."""
    date = conformant_data["dates_mentioned"][0]
    assert date.certainty is DateCertainty.RELATIVE
    assert date.latest - date.earliest == timedelta(days=30)
    assert date.resolved_against == eval_time
    report = validate_extraction_schema(ExtractionResult(**conformant_data),
                                        vocabulary=vocabulary, stage=ARRIVAL)
    assert report.violations == ()


# --------------------------------------------------------------------------------------
# S-9 · the extractor may not stamp its own receipts
# --------------------------------------------------------------------------------------


def test_a_span_arriving_pre_stamped_verified_fails_s9(conformant_data, span_of, vocabulary):
    """`EvidenceSpan.verified` documents an invariant that nothing enforced.

    contracts/evidence.py says of the flag: "It is False on every span an extractor produces,
    and only the span validator may construct one with True." Nothing checked it. The field has
    an ordinary default and an ordinary bool validator, so the extractor whose claims ALG-08
    exists to check could hand us a fabricated quote already wearing the checkmark — and V-5
    downstream reads that checkmark as a receipt. This is the seam where an extraction is judged
    on its shape, so this is where the claim in that docstring becomes a rule.
    """
    stamped = span_of("Finance to confirm", verified=True)
    result = ExtractionResult(**{**conformant_data,
                                 "all_evidence": [*conformant_data["all_evidence"], stamped]})

    report = validate_extraction_schema(result, vocabulary=vocabulary, stage=ARRIVAL)

    assert [violation.rule for violation in report.violations] == [SchemaRule.S9]
    assert report.conforms is False, "a pre-stamped receipt blocks — it is not advisory"


def test_a_pre_stamped_span_on_a_claim_fails_s9_and_names_the_path(conformant_data, span_of,
                                                                   vocabulary):
    """The path matters: "which claim did the extractor sign for itself" is the diagnosis."""
    stamped = span_of("Finance to confirm whether we can absorb the increase", verified=True)
    mention = EntityMention(surface_form="Finance", entity_type="organization",
                            evidence=[stamped], confidence_bp=8200)
    result = ExtractionResult(**{**conformant_data, "entity_mentions": [mention],
                                 "all_evidence": [*conformant_data["all_evidence"], stamped]})

    report = validate_extraction_schema(result, vocabulary=vocabulary, stage=ARRIVAL)

    fields = {violation.field for violation in report.violations
              if violation.rule is SchemaRule.S9}
    assert "entity_mentions[0].evidence[0].verified" in fields
    assert "all_evidence[4].verified" in fields


# --------------------------------------------------------------------------------------
# S-9 and the STAGE · the one rule here that is about origin rather than shape
# --------------------------------------------------------------------------------------


def test_a_verified_extraction_re_validates_clean_at_the_post_verification_stage(
        conformant, vocabulary, worked_example_text):
    """The round trip: validate -> ALG-08 -> validate again. It has to close.

    S-9 was written as an unconditional rule, and unconditionally it rejects the output of
    `spans.apply_verdicts` — the one object in Layer 1 that is SUPPOSED to carry `verified=True`,
    on exactly the spans L1.5.1 found in the source. Two units in the same package emitting
    mutually incompatible objects is a defect on its own; the way it fails is worse. The report
    reads "an extractor that stamps its own receipt has asserted the conclusion the validator
    exists to reach", so when W6 wires the pipeline and every correctly verified extraction is
    refused, the diagnosis on the screen names the extractor — the one component that did
    nothing wrong.

    Re-validation is an anticipated path, not a hypothetical: `bypassed` in this file exists
    because a cached `l1_extraction_results` row and an extractor repair both re-enter S3, and
    W6 hands S3's own output back to S3. The fix is to let the rule know which seam it is
    standing at, never to clear the flag.
    """
    verified, _counters = apply_verdicts(conformant, worked_example_text)
    assert [span for span in verified.all_evidence if span.verified], \
        "fixture problem: ALG-08 grounded nothing, so there is no round trip to test"

    report = validate_extraction_schema(verified, vocabulary=vocabulary, stage=POST_VERIFICATION)

    assert report.violations == ()
    assert report.conforms is True


def test_the_same_verified_extraction_still_fails_s9_at_the_arrival_stage(
        conformant, vocabulary, worked_example_text):
    """Scoping the rule is not switching it off, and this row is the difference.

    The identical object that conforms one line above is refused here, because at the arrival
    seam a set flag can only have been set by the extractor. If this ever passes, `stage` has
    stopped being a statement about provenance and has become a way to ask for a softer check.
    """
    verified, _counters = apply_verdicts(conformant, worked_example_text)

    report = validate_extraction_schema(verified, vocabulary=vocabulary, stage=ARRIVAL)

    assert report.conforms is False
    assert report.failed_rules == (SchemaRule.S9,)


def test_the_default_stage_is_the_fail_closed_one(conformant, vocabulary, worked_example_text):
    """A forgotten keyword must not be the way past the anti-hallucination lock.

    Of the two stages exactly one is safe to assume: an object whose provenance the caller has
    not thought about is an unchecked one far more often than a graded one, and the cost of
    guessing wrong is asymmetric — a wrong `POST_VERIFICATION` lets a pre-stamped fabrication
    through V-5 unchallenged, while a wrong `EXTRACTOR_OUTPUT` merely refuses an extraction
    loudly, with the field path in the report.
    """
    verified, _counters = apply_verdicts(conformant, worked_example_text)

    # The one call in the repo that omits `stage` on purpose; the trailing marker is what
    # `test_every_call_site_names_its_stage` reads to exempt exactly this line and no other.
    report = validate_extraction_schema(verified,
                                        vocabulary=vocabulary)  # default-stage probe

    assert report.conforms is False
    assert SchemaRule.S9 in report.failed_rules
    default = inspect.signature(validate_extraction_schema).parameters["stage"].default
    assert default is ValidationStage.EXTRACTOR_OUTPUT


def test_post_verification_scopes_s9_and_leaves_every_other_rule_running(conformant_data,
                                                                        span_of, vocabulary):
    """The later stage is still the full structural gate — a stamped span is all it forgives.

    Without this row, `POST_VERIFICATION` could quietly degrade into "skip validation", and the
    read-back path — the one that exists because a cached row was written under an older schema
    version — would be the path with no schema check on it at all.
    """
    stamped = span_of("Finance to confirm", verified=True)
    result = bypassed(conformant_data, stance="optimistic",
                      all_evidence=[*conformant_data["all_evidence"], stamped])

    report = validate_extraction_schema(result, vocabulary=vocabulary, stage=POST_VERIFICATION)

    assert rules_on(report, "stance") == {SchemaRule.S3}
    assert report.conforms is False
    assert [violation for violation in report.violations
            if violation.rule is SchemaRule.S9] == []


def test_neither_stage_ever_repairs_the_flag(conformant_data, span_of, vocabulary):
    """Nothing here clears `verified`, at either stage.

    The docstring on `_check_unstamped` gives the reason and it survives the scoping: an
    extraction that stamps its own receipts is a profile doing something no prompt asked for,
    and a validator that silently unset the bit would let that ship for a year with nobody able
    to name the day it started.
    """
    stamped = span_of("Finance to confirm", verified=True)
    result = ExtractionResult(**{**conformant_data,
                                 "all_evidence": [*conformant_data["all_evidence"], stamped]})

    for stage in ValidationStage:
        validate_extraction_schema(result, vocabulary=vocabulary, stage=stage)
        assert stamped.verified is True
        assert result.all_evidence[-1].verified is True


def test_s9_is_the_only_stage_scoped_rule():
    """The table, asserted — so a later rule cannot become stage-scoped without a reader.

    `ARRIVAL_ONLY_RULES` is what `_enforced` consults, so adding a member to it silently turns
    off a check on every read-back path. S-9 earns its place there because it is the only rule
    about a value's ORIGIN; S-1 through S-8 are about shape and vocabulary, and those stay true
    of the object forever.
    """
    assert ARRIVAL_ONLY_RULES == frozenset({SchemaRule.S9})
    assert set(ValidationStage) == {ValidationStage.EXTRACTOR_OUTPUT,
                                    ValidationStage.POST_VERIFICATION}


def test_every_call_site_names_its_stage():
    """No caller in the repo leaves the seam to the default.

    The default exists to be fail-closed, not to be used. A call that omits `stage` is a call
    whose author had not decided which object they were holding, and the two objects differ by
    the single bit the whole anti-hallucination mechanism rests on — so the decision is made at
    the call site, in writing, where a reviewer reads it.

    The one deliberate exception is `test_the_default_stage_is_the_fail_closed_one`, which is
    asserting on the default itself and carries a `default-stage probe` comment on the closing
    line of the call. The marker has to be ON the call, not above it: a comment on the line
    before would let a stray line drift over any call in the repo and silently exempt it.
    """
    root = pathlib.Path(__file__).resolve().parents[3]
    bare: list[str] = []
    for folder in ("genios_engine", "tests"):
        for path in sorted((root / folder).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "validate_extraction_schema(" not in source:
                continue
            lines = source.splitlines()
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Call):
                    continue
                name = (node.func.id if isinstance(node.func, ast.Name)
                        else node.func.attr if isinstance(node.func, ast.Attribute) else None)
                if name != "validate_extraction_schema":
                    continue
                last = node.end_lineno or node.lineno
                if any("default-stage probe" in lines[number - 1]
                       for number in range(node.lineno, last + 1)):
                    continue
                if not any(keyword.arg == "stage" for keyword in node.keywords):
                    bare.append(f"{path.relative_to(root)}:{node.lineno}")
    assert bare == [], f"call sites that do not name their stage: {bare}"

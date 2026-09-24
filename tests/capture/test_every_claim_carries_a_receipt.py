"""Step 4 · the contract has two tiers, and three predicates fire off the wrong one.

    pytest tests/capture/test_every_claim_carries_a_receipt.py -q

DOCTRINE 3 OF THIS LAYER IS *"no claim without a receipt."* `ExtractionResult` has fifteen claim
lanes. **Eight are typed** and each carries `evidence: EvidenceSpan` and `confidence_bp`. **Seven
are `list[str]` or `list[dict[str, Any]]`** — and those cannot obey the doctrine, not because the
receipts were lost but because **the type has no field to put one in**.

    typed     entity_mentions · amounts · dates_mentioned · commitments · decision_states
              dependencies · business_facts · unclassified_observations
    untyped   topics · implied_actions · questions · roles · relationships
              scheduling_proposals · availability

`esqe/detector.py` fires three real signal types off the untyped half:

    :417  RELATIONSHIP_CHANGE  <- ex.roles
    :424  AVAILABILITY_CHANGE  <- ex.availability
    :469  a decision predicate <- ex.questions

and says so itself — *"it carries no EvidenceSpan (the lane is `list[dict]` by contract), hence no
receipt on that detection."*

WHAT THIS STEP IS **NOT** FOR — corrected 2026-09-23, before any code was written. The plan said
typing these would lift `relationship_change` over the qualification floor. **It will not.**
Measured in production:

    relationship_change   published 4 · DROPPED 54 · band 880-1560   (ceiling BELOW the floor)
    best row's terms:     monetary_exposure_bp 0 · deadline_proximity_bp 0

Those zeros are not an artifact of the untyped bag. `normalize.DATE_POLICY[RELATIONSHIP_CHANGE]`
is `none` and `AMOUNT_POLICY` is `claims_only` **by design** — a role change genuinely states no
amount and no deadline. ALG-17 reads `primary_date`/`primary_amount`, both `None` by policy, so
typing changes the score by zero basis points. That a type's ceiling sits below the floor is a
**floor** question and belongs to step 8.

WHAT IT IS FOR, then:

  1. a citable receipt on every claim — benchmark P1 and P3 both need to quote the source;
  2. zero predicates firing on a claim that cannot carry one;
  3. a per-claim confidence for ALG-13 to compose.

TWO LANES STAY UNTYPED, and that is a decision with a reason rather than an omission. The contract
says `topics` is *"free text by design; topics are for retrieval and grouping, not for rule
matching"*, and `implied_actions` is *"what the message implies somebody should do, in the model's
words"* — a judgement about the message, not a claim about the world. Promoting a label to a claim
adds ceremony without adding truth.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

#: The lanes this step promotes, and the question each one answers about the world.
PROMOTED = {
    "roles": "who somebody is",
    "availability": "when somebody cannot act",
    "questions": "what was asked and not answered",
}

#: The lanes that stay free-form, with the contract's own reason.
KEPT_UNTYPED = {
    "topics": "free text by design — retrieval and grouping, not rule matching",
    "implied_actions": "the model's words about what should happen — a judgement, not a claim",
}


def _claim_types():
    from genios_engine.contracts import extraction as E
    return E


# =============================================================================================
# The types themselves
# =============================================================================================
@pytest.mark.parametrize("lane", sorted(PROMOTED))
def test_a_promoted_lane_carries_evidence_and_a_confidence(lane: str):
    """Every typed claim in this contract carries both. `Commitment` is the reference shape:

        actor · action · beneficiary · due · is_conditional · condition_text
        evidence: EvidenceSpan
        confidence_bp: int

    A promoted lane that carried one and not the other would be half a claim — a receipt nobody
    weighted, or a weight nobody could check.
    """
    from genios_engine.contracts.extraction import ExtractionResult

    field = ExtractionResult.model_fields[lane]
    inner = field.annotation.__args__[0]        # list[X] -> X

    assert inner is not str and inner is not dict, (
        f"`{lane}` is still a bare {inner} — it has nowhere to put a receipt")
    assert "evidence" in inner.model_fields, f"`{lane}` claims carry no EvidenceSpan"
    assert "confidence_bp" in inner.model_fields, f"`{lane}` claims carry no confidence"


@pytest.mark.parametrize("lane", sorted(KEPT_UNTYPED))
def test_a_label_lane_is_deliberately_left_alone(lane: str):
    """REGRESSION GUARD in the opposite direction.

    The pressure after a step like this is to type everything. These two are labels about the
    message rather than claims about the world, the contract says so in its own field notes, and
    promoting them would add a receipt to something there is nothing to check.
    """
    from genios_engine.contracts.extraction import ExtractionResult

    field = ExtractionResult.model_fields[lane]
    assert field.annotation.__args__[0] is str, (
        f"`{lane}` was promoted; the contract calls it {KEPT_UNTYPED[lane]}")


# =============================================================================================
# The predicates — the reason the step exists
# =============================================================================================
def test_no_predicate_fires_on_a_claim_that_cannot_carry_a_receipt():
    """Doctrine 3, enforced rather than documented.

    `detector.py` reads `ex.roles`, `ex.availability` and `ex.questions` to fire three real signal
    types. While those lanes were `list[dict]` the detections had no receipt and the module said
    so in a comment. A comment is not a guard.
    """
    from genios_engine.contracts.extraction import ExtractionResult

    for lane in ("roles", "availability", "questions"):
        inner = ExtractionResult.model_fields[lane].annotation.__args__[0]
        assert hasattr(inner, "model_fields") and "evidence" in inner.model_fields, (
            f"detector.py fires a signal from `{lane}`, which still cannot carry a span")


def test_a_role_claim_resolves_against_the_source_text():
    """The point of a receipt: ALG-08 can grade it, and `verified=True` is something the
    validator stamps rather than the extractor asserting it about itself."""
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import RoleAssertion

    text = "Maya is now the CFO and signs anything over $50k."
    quote = "Maya is now the CFO"
    claim = RoleAssertion(
        party="Maya", role="CFO",
        evidence=[EvidenceSpan(source_ref="prepared_content:pc_1", quote=quote,
                               start_offset=0, end_offset=len(quote))],
        confidence_bp=9000)

    span = claim.evidence[0]
    assert text[span.start_offset:span.end_offset] == span.quote
    assert span.verified is False, "the extractor may not stamp its own receipt — schema rule S-9"


def test_a_claim_the_model_could_not_anchor_is_kept_not_dropped():
    """A role the model read but could not quote is still something it read.

    Forcing a span would make the model invent one, which is the failure this architecture exists
    to prevent — a fabricated quote is worse than a missing one. So `evidence` may be EMPTY and
    the claim travels anyway.

    But the field is still REQUIRED, exactly as it is on `Commitment`: an empty list is the
    extractor SAYING it found no quote, and an omitted field is the extractor saying nothing at
    all. This layer draws that line everywhere else — `unknown` is a real answer and is never
    guessed — and a claim lane is not the place to start blurring it.
    """
    from genios_engine.contracts.extraction import RoleAssertion

    claim = RoleAssertion(party="the enterprise team", role="approver",
                          evidence=[], confidence_bp=4000)
    assert claim.evidence == []


# =============================================================================================
# The read side — every extraction already in the cache was written in the OLD shape
# =============================================================================================
def _legacy_row(**lanes):
    """A row exactly as `l1_extraction_results` holds one written before 2026-09-23."""
    from genios_engine.contracts.extraction import ExtractionResult
    return ExtractionResult.model_validate({
        "intent": "inform", "stance": "neutral", "model_snapshot": "m", "prompt_version": "p",
        "schema_version": "s", "extraction_profile": "email", "input_tokens": 1,
        "output_tokens": 1, **lanes})


def test_a_cached_row_in_the_old_shape_still_loads():
    """THE ONE THAT WOULD HAVE TAKEN LAYER 2 DOWN.

    `context/qes_adapter.adapt_qes_extraction` rehydrates cached rows with
    `ExtractionResult.model_validate(...)` ON THE LIVE L2 PATH. Every row in
    `l1_extraction_results` carries the pre-promotion shape, so without a read-side migration this
    step does not merely change the wire — every cached extraction in every tenant becomes
    unreadable and Layer 2 stops receiving anything from the cache the day it ships.

    The cache is keyed on content version and turns over only when a message changes, so "it will
    age out" is not an answer for a corpus nobody re-sends.
    """
    row = _legacy_row(
        questions=["Can we sign Friday?"],
        roles=[{"party": "Acme", "role": "counterparty", "evidence_text": "Acme will sign"}],
        availability=[{"kind": "ooo", "evidence_text": "away until Monday"}])

    assert row.questions[0].text == "Can we sign Friday?"
    assert row.roles[0].party == "Acme"
    assert row.availability[0].kind == "ooo"
    # `person` absent means THE AUTHOR — an out-of-office names nobody, and requiring a name here
    # would refuse the commonest availability claim there is.
    assert row.availability[0].person is None


def test_the_legacy_receipt_survives_as_a_probe_and_is_never_stamped():
    """`evidence_text` was the free receipt string the old shape carried. It becomes a PROBE span
    — the model's own words at offsets 0..len, `verified=False` — which is the same convention
    `extractor._spans_from_payload` uses for a model that quoted correctly and counted in the
    wrong frame. ALG-08 relocates it against the source.

    DROPPING IT WOULD HAVE BEEN THE OTHER OPTION, and it silently deletes the only receipt a
    legacy claim ever had. STAMPING it verified is the one thing that may never happen: that is
    the extractor asserting the conclusion the validator exists to reach, which is schema rule
    S-9's whole subject.
    """
    row = _legacy_row(
        roles=[{"party": "Acme", "role": "counterparty", "evidence_text": "Acme will sign"}])

    span = row.roles[0].evidence[0]
    assert span.quote == "Acme will sign"
    assert span.verified is False, "the read path stamped its own receipt — see schema rule S-9"
    assert span.source_ref == "legacy_lane:roles", (
        "the provenance must say the span came from a legacy row rather than from the prepared "
        "content, or a replay cannot tell a graded citation from a rehydrated one")


def test_a_legacy_entry_with_no_receipt_is_kept_and_says_so():
    """`evidence=[]` is the honest "this claim was stored without a receipt". The read path may
    not invent a quote to fill it — a fabricated receipt is the failure this whole architecture
    exists to prevent, and V-5 already downgrades what has none."""
    row = _legacy_row(roles=[{"party": "Acme", "role": "counterparty"}])

    assert row.roles[0].evidence == []


def test_a_row_already_in_the_new_shape_is_not_touched_by_the_migration():
    """SENSITIVITY. A read-side migration that also rewrote conforming rows would quietly
    re-confidence every fresh extraction at the legacy default, and nothing would say so."""
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import LEGACY_LANE_CONFIDENCE_BP, RoleAssertion

    graded = EvidenceSpan(source_ref="prepared_content:evt_1", quote="Acme will sign",
                          start_offset=0, end_offset=14)
    row = _legacy_row(roles=[RoleAssertion(party="Acme", role="counterparty",
                                           evidence=[graded], confidence_bp=9100)])

    assert row.roles[0].confidence_bp == 9100 != LEGACY_LANE_CONFIDENCE_BP
    assert row.roles[0].evidence[0].source_ref == "prepared_content:evt_1"


def test_the_legacy_default_never_outranks_a_graded_claim():
    """5000 bp is "somebody said it and nothing corroborates it". It has to sit BELOW anything
    the extractor states for itself, or a rehydrated legacy claim sorts above a claim ALG-08
    actually checked — and ALG-13 composes these into a signal's confidence."""
    from genios_engine.contracts.extraction import LEGACY_LANE_CONFIDENCE_BP

    assert LEGACY_LANE_CONFIDENCE_BP == 5000


# =============================================================================================
# ALG-08 walks the promoted lanes — the defect S-7 surfaced
# =============================================================================================
def test_alg08_grades_the_promoted_lanes_like_any_other_claim():
    """It did not, and the way that showed was oblique: `test_schema.py` began failing S-7
    post-verification, because the span on a `roles` claim stayed unverified while its copy in
    `all_evidence` came back verified, so the two were no longer equal.

    The symptom was S-7. The defect was that `evidence_from_claims()` did not list these three
    lanes and `apply_verdicts` did not rebuild them — so the only three signal types derived from
    unverifiable claims were also the only three whose receipts ALG-08 never saw.
    """
    from genios_engine.capture.validate.spans import apply_verdicts
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import RoleAssertion

    text = "Maya is now the CFO and signs anything over $50k."
    quote = "Maya is now the CFO"
    row = _legacy_row(roles=[RoleAssertion(
        party="Maya", role="CFO", confidence_bp=9000,
        # Offsets deliberately wrong and deliberately IN BOUNDS: the quote is real and the
        # counting is not, which is the case ALG-08's relocation step exists for. Out-of-bounds
        # would grade INVALID_BOUNDS and prove nothing about whether the lane was walked.
        evidence=[EvidenceSpan(source_ref="prepared_content:evt_1", quote=quote,
                               start_offset=25, end_offset=25 + len(quote))])])

    verified, counters = apply_verdicts(row, text)

    assert verified.roles[0].evidence[0].verified is True, (
        "ALG-08 did not walk `roles`, so a fabricated quote in a role assertion is never caught")
    assert verified.roles[0].evidence[0].start_offset == text.index(quote)
    assert counters.verified_relocated == 1, (
        "the span was graded but not RELOCATED, so the lane is being counted and not corrected")


def test_every_promoted_lane_has_an_alg08_drop_policy():
    """`_policy_drops` RAISES on an unlisted type rather than defaulting — "better a loud KeyError
    at the seam than a quiet policy hole". This asserts the three rows exist and says which way
    each one went, so a future edit that flips one is a diff on a decision and not on a blank.
    """
    from genios_engine.capture.validate.spans import _POLICY
    from genios_engine.contracts.extraction import (AvailabilityWindow, OpenQuestion,
                                                    RoleAssertion)

    assert _POLICY[RoleAssertion] is False, "a role is a fact about a PERSON that Layer 2 resolves"
    assert _POLICY[AvailabilityWindow] is True, "an invented window suppresses a real chase"
    assert _POLICY[OpenQuestion] is False, "dropping deletes the awaited item rather than doubting it"


# =============================================================================================
# The predicates cite, which is what the promotion was FOR
# =============================================================================================
def test_the_promoted_lanes_run_the_same_pipeline_as_every_other_claim():
    """The first implementation parsed these three with a separate lenient reader that defaulted
    `evidence=[]`. That built claims schema rule S-4 then REFUSES — "a claim with no receipt is a
    guess" — so one unquotable question triggered a repair retry and then a parked extraction
    that lost every commitment, amount and decision in the same message.

    Being in `CLAIM_FIELDS` is what makes S-4 hold by construction: the binder either grounds a
    claim or drops it, so nothing receipt-less ever reaches the validator.
    """
    from genios_engine.capture.semantic.extractor import CLAIM_FIELDS, _NEEDLE_KEY

    for lane in PROMOTED:
        assert lane in CLAIM_FIELDS, f"`{lane}` bypasses the binder, so S-4 can still refuse it"
        assert lane in _NEEDLE_KEY, f"`{lane}` has no needle, so it can never recover a receipt"


# =============================================================================================
# The bill — this step re-extracts the corpus, and that is a fact somebody has to budget for
# =============================================================================================
def test_promoting_a_lane_changes_the_vocabulary_fingerprint_and_therefore_the_cache_key():
    """MEASURED 2026-09-23: `151b9dabf235` -> `a3d5496aa0d3`.

    `UNTYPED_LANE_KEYS` is folded into `vocabulary_fingerprint()`, which is a component of the
    `l1_extraction_results` key. Removing `roles` and `availability` from it changes the digest,
    so **every cached extraction misses and the whole corpus re-extracts on the first sweep after
    deploy.** That is a real model bill and it is not optional.

    IT IS ALSO CORRECT. The module says why in its own words: *"a promotion cannot be silent:
    adding one word changes what the model was asked to look for, so every cached extraction
    taken under the old wording must stop answering for the new one"* — against the recorded
    failure where *"260 cached extractions survived a prompt fix, the numbers did not move, and
    the conclusion drawn was that the fix had not worked."* `schema_gen` now renders three lanes
    as typed objects instead of open dicts, so the prompt genuinely changed and the old answers
    genuinely do not answer for it.

    This test exists because the cost was nearly shipped unnoticed: nothing in the step's plan
    named it, and a bill discovered from an invoice is a bill nobody approved.
    """
    from genios_engine.capture.semantic.vocabulary import (UNTYPED_LANE_KEYS,
                                                           vocabulary_fingerprint)

    assert set(UNTYPED_LANE_KEYS) == {"relationships", "scheduling_proposals"}, (
        "a lane moved in or out of the closed key set — the fingerprint moved with it, so the "
        "corpus re-extracts again and the number below is stale")
    assert vocabulary_fingerprint() == "a3d5496aa0d3", (
        "the vocabulary fingerprint changed since step 4. That is not a failure — it means the "
        "prompt changed and every cached extraction stops answering. Re-measure the "
        "re-extraction cost, record it, and update this literal.")


def test_an_already_published_signal_still_resolves_to_its_old_extraction_row():
    """WHY THE READ-SIDE MIGRATION IS STILL NEEDED even though the corpus re-extracts.

    The fingerprint change makes FUTURE sweeps write new rows under new keys. It does not touch
    the rows already there, and `context/runner.py` joins

        l1_extraction_results xr on xr.processing_key = q.qes_extraction_ref

    where `qes_extraction_ref` comes off `qualified_signals` — signals PUBLISHED under the old
    key. So old rows keep being read for as long as the signals that point at them live, and
    `_rehydrate_legacy_lanes` is what keeps that path working rather than throwing.
    """
    import inspect

    from genios_engine.context import runner

    source = inspect.getsource(runner)
    assert "xr.processing_key = q.qes_extraction_ref" in source, (
        "the join this test reasons about has moved; re-check whether legacy extraction rows "
        "are still reachable before relying on the rehydration path")

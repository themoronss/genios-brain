"""L2-2-U0/U1/U2 · Observation ≠ Inference ≠ Hypothesis, and who may write which.

⛔ **THE PLAN'S PREMISE SENTENCE IS WRONG, AND CORRECTING IT IS WHAT MAKES THIS STEP BUILDABLE
TODAY.** It says:

    Every field that exists is an observation field. Every field missing is an interpretation
    field. Not a coincidence — the exact signature of a layer that correlates and does not reason.

**Measured against the contract, v2 is already full of interpretation.** Its own field comments
say so:

* `visibility` — *"A situation is a **DERIVED claim**"*
* `coverage_ready` — *"May a **NEGATIVE inference** be made in this situation's domain"*
* `missing_facts` — *"The `GENUINELY_ABSENT` entries are **findings**, not data-quality complaints"*
* `trends`, `anomalies`, `correlations`, `cohort_positions` — governed by V-4…V-7 **precisely
  because** they are inferences: *"a trend is never certain"*, *"correlation is never cause"*

So Layer 2 does not lack interpretation. **It lacks the label saying which field is which**, and
therefore it has nowhere to hang a write-authority rule. That is what this module adds, and it
needs no migration and no new column: **a field that already exists does not need to be invented
to be classified.**

The rule this protects, in one line from L1's `EvidenceSpan.verified`:

    The moment another caller can set that flag, it stops meaning "checked" and starts meaning
    "claimed".

**A model that can write an observation is a model that can invent a fact. So it cannot.**
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_the_three_claim_states_are_closed():
    """Three CLAIM states, plus `envelope` for the fields that are not claims at all.

    Keeping `envelope` inside the same enum rather than outside it is what makes the totality
    check below possible: every field lands in exactly one bucket, and "not a claim" is a bucket
    somebody chose rather than a field nobody classified.
    """
    from genios_engine.contracts.claim_state import CLAIM_STATES, ClaimState

    assert {s.value for s in ClaimState} == {"observed", "inferred", "hypothesised", "envelope"}
    assert {s.value for s in CLAIM_STATES} == {"observed", "inferred", "hypothesised"}
    assert ClaimState.ENVELOPE not in CLAIM_STATES


def test_every_v2_field_is_classified_and_every_row_names_a_real_field():
    """⛔ Both directions, the repo idiom. A field with no row can be written by anybody; a row
    with no field is a rule guarding nothing."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS
    from genios_engine.contracts.situation import BusinessSituationObject as V2

    fields = set(V2.model_fields)
    classified = set(FIELD_CLAIMS)
    assert not (fields - classified), (
        f"unclassified v2 fields: {sorted(fields - classified)}. Say whether each is an "
        f"observation, an inference or a hypothesis — an unclassified field has no write rule")
    assert not (classified - fields), (
        f"FIELD_CLAIMS names fields v2 does not have: {sorted(classified - fields)}")


def test_every_classification_gives_its_reason():
    """A classification with no reason is a label, and this repo has decided that twice."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS

    for name, claim in FIELD_CLAIMS.items():
        assert claim.why, f"{name} is classified {claim.state.value} and says nothing about why"


def test_the_envelope_is_not_a_claim_at_all():
    """`org_id` is not an observation about the world — it is the row's address. Conflating the
    two would put a write rule on a tenant id and none on a trend."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS, ClaimState

    assert FIELD_CLAIMS["org_id"].state is ClaimState.ENVELOPE
    assert FIELD_CLAIMS["schema_version"].state is ClaimState.ENVELOPE
    assert ClaimState.ENVELOPE.value == "envelope"


def test_the_fields_the_contract_itself_calls_inferences_are_classified_as_such():
    """Read from the contract's own words, not from opinion. Each of these has a sentence in
    `contracts/situation.py` calling it derived, inferred or a finding."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS, ClaimState

    for name in ("trends", "anomalies", "correlations", "cohort_positions", "confidence",
                 "missing_facts", "importance"):
        assert FIELD_CLAIMS[name].state is ClaimState.INFERRED, (
            f"{name} is an interpretation — V-4…V-7 exist because it can be wrong")


def test_the_receipts_are_classified_as_observations():
    """`evidence` is verbatim; `signal_ids` are what L1 published. Neither is a judgement."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS, ClaimState

    for name in ("evidence", "signal_ids", "entities", "timeline", "provenance_refs"):
        assert FIELD_CLAIMS[name].state is ClaimState.OBSERVED


# =================================================================================================
# Write authority — the half the whole step exists for.
# =================================================================================================

def test_a_model_may_never_write_an_observation():
    """⛔ **The rule.** L2-5 puts a model on this layer. It must be born into a world where this
    is already enforced, because a rule added after the writer is a rule the writer was built
    around."""
    from genios_engine.contracts.claim_state import ClaimState, model_may_write

    assert model_may_write(ClaimState.INFERRED) is True
    assert model_may_write(ClaimState.HYPOTHESISED) is True
    assert model_may_write(ClaimState.OBSERVED) is False
    assert model_may_write(ClaimState.ENVELOPE) is False


def test_the_fields_a_model_may_propose_are_nameable_as_a_set():
    """L2-5's gate needs this list, and deriving it by hand at the call site is how the list and
    the rule stop agreeing."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS, model_writable_fields

    writable = model_writable_fields()
    assert writable, "no field a model may ever propose makes L2-5 impossible"
    assert "evidence" not in writable
    assert "signal_ids" not in writable
    assert "org_id" not in writable
    assert writable <= set(FIELD_CLAIMS)


def test_a_new_field_defaults_to_refusing_the_model_rather_than_allowing_it():
    """⛔ An unclassified field must not fall into the permissive bucket.

    The totality test above makes an unclassified field a build failure; this proves the failure
    mode if it ever slipped: `model_may_write` on an unknown state refuses.
    """
    from genios_engine.contracts.claim_state import model_may_write

    with pytest.raises((KeyError, ValueError, AssertionError)):
        model_may_write("something_nobody_declared")  # type: ignore[arg-type]

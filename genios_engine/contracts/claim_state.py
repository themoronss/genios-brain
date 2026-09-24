"""L2-2 · Observation ≠ Inference ≠ Hypothesis — as a classification over the fields that exist.

⛔ **THE PLAN SAID LAYER 2 HAD NO INTERPRETATION FIELDS. IT IS FULL OF THEM.** The premise —
*"every field that exists is an observation field, every field missing is an interpretation
field"* — does not survive reading `contracts/situation.py`'s own comments:

    visibility      "A situation is a DERIVED claim"
    coverage_ready  "May a NEGATIVE inference be made in this situation's domain"
    missing_facts   "The GENUINELY_ABSENT entries are FINDINGS, not data-quality complaints"
    trends/anomalies/correlations/cohort_positions
                    governed by V-4…V-7 precisely BECAUSE they can be wrong:
                    "a trend is never certain", "correlation is never cause"

So Layer 2 does not lack interpretation. **It lacks the label saying which field is which**, and
without that label there is nowhere to hang a write-authority rule. This module is that label.

**IT ADDS NO COLUMN AND NEEDS NO MIGRATION.** A field that already exists does not have to be
invented in order to be classified, and inventing `observed_facts` beside `evidence`/`signal_ids`/
`entities` — which ARE the observed facts — would have been the duplication that L2-1 just spent a
step undoing at the type level.

THE RULE IT PROTECTS, carried up from L1's `EvidenceSpan.verified`:

    The moment another caller can set that flag, it stops meaning "checked" and starts meaning
    "claimed".

**A model that can write an observation is a model that can invent a fact. So it cannot** — and
L2-5 puts the first model on this layer, which is why this lands before it rather than after. A
rule added after its writer is a rule the writer was built around.

BOTH DIRECTIONS ARE CHECKED AT IMPORT TIME, the way `LAYERS.py`, `situation_stages.py`,
`PRECEDENCE` and `ANCHOR_FAMILIES` all do it. A v2 field with no row can be written by anybody; a
row with no field is a rule guarding nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClaimState(str, Enum):
    """What KIND of thing a field holds. Three claims, and one bucket that is not a claim."""

    #: Lifted from what a source said or what Layer 1 published. **No model may write one.**
    OBSERVED = "observed"
    #: Concluded from observations. May be wrong, and V-4…V-7 exist because it may.
    INFERRED = "inferred"
    #: Proposed, not concluded. Carries its own confidence and is never rendered as fact.
    HYPOTHESISED = "hypothesised"
    #: Not a claim about the world at all — the row's address, its audience, its schema. Kept in
    #: this enum rather than outside it so that EVERY field lands in a bucket somebody chose,
    #: instead of "not a claim" meaning "nobody classified it".
    ENVELOPE = "envelope"


#: The three that are actually claims. `ENVELOPE` is deliberately not one of them.
CLAIM_STATES: frozenset[ClaimState] = frozenset(
    {ClaimState.OBSERVED, ClaimState.INFERRED, ClaimState.HYPOTHESISED})

#: ⛔ **WHO MAY PROPOSE WHAT.** The one table L2-5's gate reads. A model may offer an
#: interpretation and may never write a fact — and `ENVELOPE` is refused for the same reason an
#: observation is: a model that may set `visibility` may widen an audience.
_MODEL_MAY_WRITE: dict[ClaimState, bool] = {
    ClaimState.OBSERVED: False,
    ClaimState.INFERRED: True,
    ClaimState.HYPOTHESISED: True,
    ClaimState.ENVELOPE: False,
}


@dataclass(frozen=True, slots=True)
class FieldClaim:
    """One v2 field, what kind of claim it carries, and why — in the contract's own words."""

    state: ClaimState
    why: str


def _o(why: str) -> FieldClaim: return FieldClaim(ClaimState.OBSERVED, why)
def _i(why: str) -> FieldClaim: return FieldClaim(ClaimState.INFERRED, why)
def _e(why: str) -> FieldClaim: return FieldClaim(ClaimState.ENVELOPE, why)


#: Every field on `contracts.situation.BusinessSituationObject`. Checked both ways at import.
FIELD_CLAIMS: dict[str, FieldClaim] = {
    # --- envelope: the row's address and audience, not a statement about the world ------------
    "org_id": _e("the tenant boundary — an address, not an observation"),
    "trace_id": _e("which sweep produced this; deliberately outside the content address"),
    "schema_version": _e("which contract this object obeys"),
    "id": _e("the situation's own `context_situations.situation_id`"),
    "visibility": _e("governance. Its OWN comment calls a situation 'a DERIVED claim', and the "
                     "audience is narrowed deterministically from the evidence — but a model that "
                     "may set it may WIDEN an audience, so it is refused like an observation"),
    "metadata": _e("the carrier for everything with no field of its own. It holds both kinds, "
                   "which is exactly why a model may not write the bag: writing the bag is "
                   "writing anything in it"),

    # --- observed: what a source said, or what Layer 1 published -------------------------------
    "signal_ids": _o("the qualified signals this rests on, in every lifecycle state"),
    "evidence": _o("the VERBATIM receipts — 'a claim with no receipt is a guess'"),
    "entities": _o("the real distinct counterparties, read from the graph"),
    "relationships": _o("graph edges, as they were written"),
    "timeline": _o("what happened and when, from the source events"),
    "dependencies": _o("the blocking structure from BLG-05, read from declared facts"),
    "provenance_refs": _o("event and source-object ids — JOIN KEYS, not receipts"),
    "conflict_ids": _o("POINTERS to `signal_conflicts` rows; the rows are the claim, not these"),

    # --- inferred: concluded from the above, and able to be wrong ------------------------------
    "type": _i("the situation TYPE, concluded from the anchor and the domain registry"),
    "state": _i("a lifecycle conclusion — 'is this still live' is judged, not read"),
    "domain_ids": _i("which business domains this belongs to. A classification"),
    "confidence": _i("six axes plus a composed number. A judgement about the other fields"),
    "coverage_ready": _i("its own comment: 'may a NEGATIVE inference be made in this domain'"),
    "conflicts": _i("the disagreements this situation is built across — detected, not stated"),
    "missing_facts": _i("typed absence. 'The GENUINELY_ABSENT entries are FINDINGS'"),
    "importance": _i("the number, its provenance and its terms. A ranking is an opinion"),
    "trends": _i("V-4: 'a trend is never certain'. V-5: 'no trend on noise'"),
    "cohort_positions": _i("V-1/V-2: a comparison against a population is a conclusion"),
    "anomalies": _i("'unusual' is a judgement against a baseline somebody chose"),
    "correlations": _i("V-6/V-7: 'correlation is never cause'"),
    "pattern_id": _i("which authored pattern fired — the match is the inference"),
    "matched_conditions": _i("the per-condition record of that match, WITH its evidence. It is "
                             "the receipt FOR an inference, which makes it one"),

    # --- L2-5 · the interpretation ------------------------------------------------------------
    "hypotheses": FieldClaim(
        ClaimState.HYPOTHESISED,
        "⛔ THE ONLY FIELD IN THIS STATE, AND WHAT MAKES IT REAL. Proposed, never concluded: it "
        "carries its own confidence and is never rendered as fact. Until L2-5 there was a third "
        "claim state and nothing held one, which made it decorative"),
    "implications": _i("why this matters — an inference drawn from another inference, which is "
                       "why it owes a receipt like every other one"),
    "reasoning_trace": _e(
        "the id of the consult that produced the reading, minted by the GATE and not by the "
        "model — for the reason `EvidenceSpan.verified` may not be self-set: the moment a caller "
        "can write its own receipt, the receipt stops meaning 'checked'"),
    "valid_until": _e(
        "when this interpretation stops being current. L2-2's own table put it under the GATE: "
        "'an interpretation expires; a fact does not'. A model that could set it could make its "
        "own reading immortal"),
}


def model_may_write(state: ClaimState) -> bool:
    """⛔ May a model author this kind of claim? Refuses an undeclared state rather than guessing.

    A permissive default here would mean a field nobody classified is a field a model may write,
    which is the precise failure this module exists to prevent.
    """
    if not isinstance(state, ClaimState):
        raise ValueError(
            f"{state!r} is not a ClaimState. An unclassified kind has no write rule, and "
            f"defaulting it to permitted is how a model comes to write a fact.")
    return _MODEL_MAY_WRITE[state]


def model_writable_fields() -> frozenset[str]:
    """Exactly the v2 fields a model may propose. L2-5's gate reads this rather than a hand list."""
    return frozenset(name for name, claim in FIELD_CLAIMS.items()
                     if model_may_write(claim.state))


def fields_in(state: ClaimState) -> frozenset[str]:
    return frozenset(name for name, claim in FIELD_CLAIMS.items() if claim.state is state)


def _check() -> None:
    """Import-time totality, both directions."""
    from genios_engine.contracts.situation import BusinessSituationObject

    fields = set(BusinessSituationObject.model_fields)
    classified = set(FIELD_CLAIMS)
    assert not (fields - classified), (
        f"unclassified v2 fields: {sorted(fields - classified)} — an unclassified field has no "
        f"write rule")
    assert not (classified - fields), (
        f"FIELD_CLAIMS names fields v2 does not have: {sorted(classified - fields)}")
    for name, claim in FIELD_CLAIMS.items():
        assert claim.why, f"{name} is classified and gives no reason"
    assert set(_MODEL_MAY_WRITE) == set(ClaimState), "a ClaimState with no write rule"


__all__ = ["CLAIM_STATES", "FIELD_CLAIMS", "ClaimState", "FieldClaim", "fields_in",
           "model_may_write", "model_writable_fields"]


_check()

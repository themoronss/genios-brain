"""L2-2-U3/U6 · two new laws, and both have real subjects today.

⛔ **V-9 · NO INTERPRETATION WITHOUT A RECEIPT.** The doctrine is already written down in this
file, on the one type that enforces it — `MatchedCondition`:

    matched condition {field_path} must cite the evidence it matched on — "this fired because of
    these facts" is what makes a situation defensible

**Measured 2026-09-24 — four of the seven interpretation types carry no evidence reference at
all**, and every one of them is constructed on a live path:

    Trend                  evidence_points          ✅   context/analytic/trend.py
    MatchedCondition       evidence                 ✅   the pattern matcher
    ConfidenceVector       evidence_bp              ✅   (a score, not a pointer — see below)
    Anomaly                ⛔ NONE                       context/analytic/anomaly.py:336
    MetricCorrelation      ⛔ NONE                       context/analytic/correlator.py:282
    CohortPosition         ⛔ NONE                       context/analytic/cohort.py:1478
    ImportanceAttribution  ⛔ NONE                       context/situation_publisher.py:121

⛔ **V-10 · NO CLAIM OF COMPLETENESS WITHOUT COVERAGE.** An empty `missing_facts` on a situation
whose `coverage_ready` is not true says *"nothing is missing"* on data that was never complete
enough to conclude that. `quality/missing.py` already guards the opposite direction —
*"`GENUINELY_ABSENT` is unconstructible without `coverage_ready=True`"* — and this is the same
rule read the other way.

**NARROWED BY MEASUREMENT.** The plan states it unconditionally. **11 of 37 registered situation
types have no `expected_fields` at all**, and for those an empty `missing_facts` is correct rather
than a claim. So the law fires only where the type's domain declares something to be missing.

⛔ **BOTH LAWS ARE DECLARED `OBSERVE`, NOT `REJECT`, AND THAT IS DELIBERATE.** `LawAction`'s own
docstring asked for exactly this — *"a law that later downgrades or parks is a one-line change
here plus a branch in `validate_situation`"* — and L1's step 10 set the precedent by **gating
itself on a measurement**. Arming these to reject before anyone has counted how many live
situations they would refuse is how a cutover looks like a breakage. The count is Harsh's.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =================================================================================================
# The two laws exist, are declared, and do not reject yet
# =================================================================================================

def test_the_two_new_laws_are_declared_with_an_action():
    from genios_engine.contracts.situation import LAW_ACTIONS, L2Law, LawAction

    assert L2Law.V9 in LAW_ACTIONS and L2Law.V10 in LAW_ACTIONS
    assert LAW_ACTIONS[L2Law.V9] is LawAction.OBSERVE
    assert LAW_ACTIONS[L2Law.V10] is LawAction.OBSERVE


def test_every_law_still_has_a_row_in_the_action_table():
    """The totality that was already here. Two new members must not escape it."""
    from genios_engine.contracts.situation import LAW_ACTIONS, L2Law

    assert set(LAW_ACTIONS) == set(L2Law)


def test_the_eight_rejecting_laws_still_reject():
    """⛔ This step adds laws. It does not weaken one."""
    from genios_engine.contracts.situation import LAW_ACTIONS, L2Law, LawAction

    for law in (L2Law.V1, L2Law.V2, L2Law.V3, L2Law.V4, L2Law.V5, L2Law.V6, L2Law.V7, L2Law.V8):
        assert LAW_ACTIONS[law] is LawAction.REJECT


# =================================================================================================
# V-9 · an interpretation with no receipt
# =================================================================================================

def _situation(**over):
    from tests.contracts.l2_situation_fixture import minimal_situation
    return minimal_situation(**over)


def _expected(situation_type: str) -> tuple[str, ...]:
    """What V-10's caller computes. Layer 2 owns the registry; the contract may not read it."""
    from genios_engine.context.expected_facts import expected_facts_for

    return expected_facts_for(situation_type)


def _anomaly(**over):
    """A bypassed `Anomaly`, which is the only object `validate_situation` is written for."""
    from genios_engine.contracts.situation import Anomaly

    base = dict(metric="account.reply_latency", current_bp=9000, baseline_bp=1000, mad_bp=200,
                deviation_bp=8000, z_like_bp=4000, direction="above", periods_used=8,
                evidence_refs=())
    base.update(over)
    return Anomaly.model_construct(**base)


def test_an_anomaly_with_no_receipt_is_named_by_v9():
    from genios_engine.contracts.situation import L2Law, validate_situation

    anomaly = _anomaly(evidence_refs=())
    decision = validate_situation(_situation(anomalies=(anomaly,)))
    v9 = [f for f in decision.failures if f.law is L2Law.V9]
    assert v9, "an anomaly citing nothing passed the gate in silence"
    assert "anomalies[0]" in v9[0].subject


def test_v9_does_not_reject_while_it_is_observing():
    """⛔ The whole reason the action table is data. The finding is carried; the situation still
    publishes, because nobody has yet counted what arming it would refuse."""
    from genios_engine.contracts.situation import validate_situation

    anomaly = _anomaly(evidence_refs=())
    decision = validate_situation(_situation(anomalies=(anomaly,)))
    assert decision.admitted, "V-9 rejected a situation before anybody measured the blast radius"
    assert decision.situation is not None, "an admitted decision must carry its object"
    assert decision.failures, "observing means CARRYING the failure, not dropping it"


def test_an_interpretation_that_does_cite_evidence_is_not_flagged():
    """Sensitivity — the probe must distinguish, or it is flagging everything."""
    from genios_engine.contracts.situation import L2Law, validate_situation

    anomaly = _anomaly(evidence_refs=("ev-1",))
    decision = validate_situation(_situation(anomalies=(anomaly,)))
    assert not [f for f in decision.failures if f.law is L2Law.V9]


def test_an_observation_field_is_never_asked_for_a_receipt_it_already_is():
    """`evidence` IS the receipt. A law demanding evidence for evidence is a loop.

    ⛔ **WIDENED BY L2-5, AND THE WIDER RULE IS THE TRUE ONE.** This asserted `is INFERRED`,
    which was right only while `HYPOTHESISED` had no members. L2-5 added `hypotheses` — and a
    hypothesis owes a citation MOST of all, being the least certain thing the object carries.

    The claim this test actually makes is that a receipt is owed by an INTERPRETATION and never
    demanded of an OBSERVATION or of the envelope. Asserted that way, it now covers both
    interpreting states and still refuses the loop.
    """
    from genios_engine.contracts.claim_state import CLAIM_STATES, FIELD_CLAIMS, ClaimState
    from genios_engine.contracts.situation import RECEIPT_REQUIRED

    interpreting = {ClaimState.INFERRED, ClaimState.HYPOTHESISED}
    assert interpreting < CLAIM_STATES, "OBSERVED is a claim state and is not an interpretation"

    for field in RECEIPT_REQUIRED:
        state = FIELD_CLAIMS[field].state
        assert state in interpreting, (
            f"{field} is required to carry a receipt and is classified {state.value} — an "
            f"observation IS the receipt, and asking it for one is a loop")


# =================================================================================================
# V-10 · a claim of completeness with no coverage
# =================================================================================================

def test_empty_unknowns_under_low_coverage_is_named_by_v10():
    from genios_engine.contracts.situation import L2Law, validate_situation

    decision = validate_situation(_situation(type="support_case", coverage_ready=False,
                                             missing_facts=()),
                                  expected_facts=_expected("support_case"))
    assert [f for f in decision.failures if f.law is L2Law.V10], (
        "a situation claimed nothing was missing on data too thin to conclude that")


def test_a_type_with_no_expected_fields_is_not_accused_of_hiding_them():
    """⛔ **THE MEASUREMENT THAT NARROWED THIS LAW.** 11 of 37 registered situation types declare
    no `expected_fields`. For those, an empty `missing_facts` is the correct answer and the plan's
    unconditional rule would have rejected every one of them."""
    from genios_engine.contracts.situation import L2Law, validate_situation

    decision = validate_situation(_situation(type="admin_period_review", coverage_ready=False,
                                             missing_facts=()),
                                  expected_facts=_expected("admin_period_review"))
    assert not [f for f in decision.failures if f.law is L2Law.V10]


def test_coverage_ready_true_ends_the_question():
    from genios_engine.contracts.situation import L2Law, validate_situation

    decision = validate_situation(_situation(type="support_case", coverage_ready=True,
                                             missing_facts=()),
                                  expected_facts=_expected("support_case"))
    assert not [f for f in decision.failures if f.law is L2Law.V10]


def test_none_coverage_lands_with_false_exactly_as_the_quality_group_says():
    """*"`coverage_ready` is consulted BEFORE absence is ever concluded, and `None` lands with
    `False`."* The same reading, or the two disagree about one fact."""
    from genios_engine.contracts.situation import L2Law, validate_situation

    decision = validate_situation(_situation(type="support_case", coverage_ready=None,
                                             missing_facts=()),
                                  expected_facts=_expected("support_case"))
    assert [f for f in decision.failures if f.law is L2Law.V10]


def test_the_law_is_not_evaluated_when_its_input_was_never_computed():
    """⛔ `None` means the caller did not compute it — NOT that nothing is expected.

    Those are different facts, and only the second is a judgement. Rendering the first as the
    second is the same mistake L2-0 refused to make with an unscored refusal.
    """
    from genios_engine.contracts.situation import L2Law, validate_situation

    decision = validate_situation(_situation(type="support_case", coverage_ready=False,
                                             missing_facts=()))
    assert not [f for f in decision.failures if f.law is L2Law.V10]


def test_the_production_gate_actually_supplies_v10_its_input():
    """⛔ **THE WIRING CHECK, AS A TEST.** A law whose input nobody passes is a law that never
    fires — *"a unit built, tested, green, and called by nothing on a real request path."*

    `situation_publisher` is the ONE caller of `validate_situation` in the engine. This reads its
    source rather than mocking, because what must be true is that the call site names the
    argument at all.
    """
    import inspect

    from genios_engine.context import situation_publisher

    src = inspect.getsource(situation_publisher)
    assert "validate_situation(" in src
    call = src[src.index("validate_situation(", src.index("def decide_publication")):]
    assert "expected_facts" in call[:300], (
        "the production gate calls validate_situation without expected_facts, so V-10 can never "
        "fire on a real situation")


# =================================================================================================
# ⛔ THE MACHINERY AN OBSERVING LAW OWES, AND THE GUARD THAT DEMANDED IT.
#
# `test_h0_gate.test_the_layer_two_gate_has_no_park_and_no_downgrade_to_drift_into` failed on the
# first run of this step, and it was right to:
#
#     L1's PublicationOutcome has three members and its decision carries a `parked` record and a
#     `confidence_downgrade_bp`; L2's has two and carries neither, so a later edit cannot quietly
#     turn a reject into a park WITHOUT ADDING THE MACHINERY FIRST.
#
# A non-rejecting law whose observation nobody reads is an invisible refusal — the exact defect
# L2-0 spent an entire step on. So the observations land on the surface L2-0 built: the durable
# `situation_admission_decisions.reasons`, which `scripts/l2_refusal_report.py` already reads.
# =================================================================================================

def test_an_admitted_situation_carries_what_the_observing_laws_saw():
    """The publisher's own result must say it, or the ledger never learns it."""
    from genios_engine.context.situation_publisher import observed_reasons

    from genios_engine.contracts.situation import validate_situation

    decision = validate_situation(_situation(anomalies=(_anomaly(),)))
    assert decision.admitted
    reasons = observed_reasons(decision)
    assert reasons, "an admitted decision dropped everything the observing laws noticed"
    assert any(r.startswith("observed:V-9:") for r in reasons), reasons


def test_a_clean_admit_records_nothing_rather_than_an_empty_marker():
    from genios_engine.context.situation_publisher import observed_reasons

    from genios_engine.contracts.situation import validate_situation

    assert observed_reasons(validate_situation(_situation())) == ()


def test_an_observed_reason_is_distinguishable_from_a_hold_reason():
    """⛔ They mean different things and land in the same column. `qes_required` is why a
    situation did NOT publish; `observed:V-9` is something noticed about one that DID."""
    from genios_engine.context.situation_publisher import HoldReason, observed_reasons

    from genios_engine.contracts.situation import validate_situation

    reasons = observed_reasons(validate_situation(_situation(anomalies=(_anomaly(),))))
    holds = {reason.value for reason in HoldReason}
    assert not ({r.split(":", 1)[0] for r in reasons} & holds)


def test_the_report_counts_an_observed_law_instead_of_dropping_it():
    """⛔ L2-0's report keys its table off `HoldReason`, so an unknown key is silently discarded —
    which would make V-9 and V-10 invisible on the one surface built to end invisibility."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(
        decisions=[{"situation_id": "s1", "outcome": "admit",
                    "reasons": ["observed:V-9:anomalies[0]", "observed:V-10:missing_facts"]}],
        refusals=(), dark=())
    assert report.by_law["V-9"] == 1
    assert report.by_law["V-10"] == 1
    assert report.by_law["V-1"] == 0, "every law needs a row, zeros included"


def test_every_law_has_a_row_in_the_report_so_a_new_one_cannot_hide():
    from genios_engine.context.quality.refusals import refusal_report

    from genios_engine.contracts.situation import L2Law

    report = refusal_report(decisions=(), refusals=(), dark=())
    assert set(report.by_law) == {law.value for law in L2Law}

"""L2-8-U5/U6 · technique 3 over the whole layer, and a failure log a TEST counts.

⛔ **NEUTRALISE THE FIX, CONFIRM THE PROBE GOES RED.** L1 step 17: *"a probe that passes with the
fix removed proves nothing."* Every step from L2-0 to L2-7 gets one, and each neutralises **the
rule the fix installed** rather than the code around it — so what is proven is that the layer
depends on the rule, not that its own lines execute.

⛔ **AND THE COUNTS ARE COUNTED.** L1's failure-log counts drifted and were caught *by counting,
not by reading* — the log said 31 CLOSED when the registry said 29. So the registry's totals are
asserted here, and every step that shipped must own at least one row.
"""
from __future__ import annotations

import pytest

from tests.scenarios_l2._registry import (
    CLOSED, GUARD, HARSH, IMPOSSIBLE, OPEN, SCENARIOS, by_owner, by_verdict,
)

pytestmark = pytest.mark.unit


# =================================================================================================
# U6 · the log, counted
# =================================================================================================

def test_the_totals_are_what_the_registry_holds():
    """⛔ Counted, not read. This is the assertion L1 wished it had had."""
    assert len(SCENARIOS) == 40
    assert len(by_verdict(CLOSED)) == 29
    assert len(by_verdict(GUARD)) == 3
    # ⛔ ZERO OPEN, AND THAT IS A CLAIM RATHER THAN A RELIEF. S07 was the one, and the 0→8 sweep
    # closed it. Everything still outstanding is either a database read (HARSH) or a decision
    # somebody has to make (IMPOSSIBLE) — no row is open because nobody got to it.
    assert len(by_verdict(OPEN)) == 0
    assert len(by_verdict(HARSH)) == 7
    assert len(by_verdict(IMPOSSIBLE)) == 1
    assert sum(len(by_verdict(v)) for v in (CLOSED, GUARD, OPEN, HARSH, IMPOSSIBLE)) == 40


def test_every_step_that_shipped_owns_at_least_one_row():
    """A step with no scenario is a step nobody can contradict."""
    for step in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "sweep"):
        assert by_owner(step), f"L2-{step} shipped and has no scenario"


def test_no_verdict_is_quiet():
    """§4: *"An OPEN row with a reason is the output; a quiet one is the failure."*"""
    for scenario in SCENARIOS.values():
        if scenario.verdict in (OPEN, HARSH, IMPOSSIBLE):
            assert len(scenario.note) > 40, f"{scenario.id}: a verdict with no reason is a label"


# =================================================================================================
# U5 · one mutation probe per step — each aimed at the RULE, not the code
# =================================================================================================

def test_l2_0_the_dark_domain_declaration(monkeypatch):
    from genios_engine.context import domain_silence

    assert domain_silence.is_dark("fundraising") is True
    monkeypatch.setattr(domain_silence, "DARK_DOMAINS", {})
    assert domain_silence.is_dark("fundraising") is False, (
        "`is_dark` survived its own table being emptied, so it has a second copy")


def test_l2_1_the_stage_table(monkeypatch):
    from genios_engine.contracts import situation_stages

    assert not situation_stages.undeclared_situation_types()
    monkeypatch.setattr(situation_stages, "SITUATION_STAGES", {})
    monkeypatch.setattr(situation_stages, "NOT_A_STAGE", {})
    assert situation_stages.undeclared_situation_types(), (
        "the guard survived both of its tables being emptied")


def test_l2_2_the_claim_state_write_rule(monkeypatch):
    from genios_engine.contracts import claim_state
    from genios_engine.context.proposal_gate import validate_proposal

    def _clean(**kw):
        return validate_proposal({"evidence": ()}, resolve_refs=lambda r: frozenset(), **kw)

    assert "l2_authority:evidence" in _clean().reason_codes
    monkeypatch.setattr(claim_state, "model_may_write", lambda state: True)
    assert "l2_authority:evidence" not in _clean().reason_codes, (
        "the authority check does not read `model_may_write`")


def test_l2_3_the_slice_silence_declaration(monkeypatch):
    from genios_engine.context import slice_silence

    assert not slice_silence.undeclared_unwritten_fields()
    monkeypatch.setattr(slice_silence, "EMPTY_BY_DESIGN", {})
    assert slice_silence.undeclared_unwritten_fields(), (
        "the guard survived its declaration being emptied")


def test_l2_4_the_unroutable_tally(monkeypatch):
    from genios_engine.context import domain_silence
    from genios_engine.reason.unroutable import tally_unroutable

    counts: dict = {}
    tally_unroutable(counts, l2_domain="fundraising", situation_type="investor_contact")
    assert "unroutable_undeclared" not in counts

    monkeypatch.setattr(domain_silence, "DARK_DOMAINS", {})
    after: dict = {}
    tally_unroutable(after, l2_domain="fundraising", situation_type="investor_contact")
    assert after["unroutable_undeclared"] == 1, (
        "the surprise flag does not read `DARK_DOMAINS`")


def test_l2_5_the_confidence_clamp():
    from genios_engine.reason.situation_reasoner import clamp_confidence

    assert clamp_confidence(proposed_bp=9500, current_bp=4000) == 4000
    # Neutralising the clamp IS `max` — and the probe must be able to tell them apart.
    assert max(9500, 4000) != clamp_confidence(proposed_bp=9500, current_bp=4000)


def test_l2_6_the_receipt_table(monkeypatch):
    from genios_engine.context.proposal_gate import validate_proposal
    from genios_engine.contracts import situation

    proposal = {"hypotheses": ({"claim": "x"},)}

    def _run():
        return validate_proposal(proposal, resolve_refs=lambda r: frozenset()).reason_codes

    assert "l2_receipt:hypotheses[0]" in _run()
    monkeypatch.setattr(situation, "RECEIPT_REQUIRED", {})
    assert "l2_receipt:hypotheses[0]" not in _run(), (
        "the receipt check does not read V-9's table")


def test_l2_7_the_uninterpreted_label():
    from genios_engine.deliver.card_source import CardSource, classify

    assert classify(situation_id=None) is CardSource.UNINTERPRETED
    assert classify(situation_id="sit_1") is CardSource.SITUATION
    # The probe must distinguish, or a renderer that labelled everything would pass.
    assert CardSource.UNINTERPRETED.label != CardSource.SITUATION.label


def test_l2_8_the_cutover_arming_guard(monkeypatch):
    """⛔ The guard that makes the switch table worth having: arm one in code and the row that
    says it is off becomes a lie the build refuses."""
    from genios_engine.contracts import situation as S
    from genios_engine.reason.cutover import is_armed

    assert is_armed("observing_laws") is False
    monkeypatch.setattr(S, "LAW_ACTIONS", {**S.LAW_ACTIONS, S.L2Law.V9: S.LawAction.REJECT})
    assert is_armed("observing_laws") is True, (
        "`is_armed` does not read the code it claims to; the table could say anything")

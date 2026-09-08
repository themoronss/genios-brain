"""K1a — `core.risk` reading with both eyes: momentum AND relationship.

`core.risk` is one of the six units that actually runs on the compiled lane, and two of its three
plugins read priors — `core.temporal`'s `drop_bp` and `core.relationship`'s `relationship_risk_bp`
— that the compiled lane never schedules. So the one evaluative unit on v2's lane has been
observing one of the three things it was built to observe, and its output could not say so: an
exposure nobody measured and an exposure measured at zero produced the identical `risk_bp` and the
identical reason codes.

Scheduling those two units is the roster's job. Telling the difference is this unit's, and this
file pins both halves: what the unit publishes when it can see, and what it says when it cannot.
"""

from __future__ import annotations

from genios_engine.contracts.reasoning import ResultStatus
from genios_engine.reason.reasoners.risk import (
    MOMENTUM_UNMEASURED_REASON,
    RELATIONSHIP_UNMEASURED_REASON,
    RISK_MITIGATION_REASON,
    RISK_REASON_CODE,
    RiskUnit,
)

from .conftest import completed, run

BOTH = {"core.temporal": completed("core.temporal", drop_bp=6_000),
        "core.relationship": completed("core.relationship", relationship_risk_bp=4_000)}


def _findings(result) -> dict:
    return {finding.finding_id: finding for finding in result.findings}


def test_risk_emits_a_momentum_and_a_relationship_observation():
    """The acceptance row, stated as the gate states it: both exposures, on one run, as findings
    an auditor can read without re-deriving the blend."""
    result = run(RiskUnit(), prior=BOTH)

    assert result.status is ResultStatus.COMPLETED
    findings = _findings(result)
    assert findings["risk.momentum_decay"].metrics["drop_bp"] == 6_000
    assert findings["risk.relationship_health"].metrics["relationship_risk_bp"] == 4_000
    assert "momentum_decay_exposure" in findings["risk.momentum_decay"].reason_codes
    assert "relationship_exposure" in findings["risk.relationship_health"].reason_codes


def test_the_blend_is_exactly_what_it_always_was():
    """The wave changes what the unit can SAY, never what it computes. 1,000 floor plus
    (6,000×60 + 4,000×40) / 100."""
    result = run(RiskUnit(), prior=BOTH)

    assert result.metrics["risk_bp"] == 1_000 + 5_200
    assert _findings(result)["risk.do_nothing"].metrics["risk_bp"] == result.metrics["risk_bp"]
    assert RISK_REASON_CODE in result.reason_codes


def test_an_unmeasured_exposure_publishes_no_number_and_names_itself():
    """A `drop_bp: 0` from a plugin that never saw an engagement reading is a claim that the
    engagement is intact. There was nobody to make that claim."""
    result = run(RiskUnit(), prior={})

    findings = _findings(result)
    assert findings["risk.momentum_decay"].metrics == {}
    assert findings["risk.relationship_health"].metrics == {}
    assert MOMENTUM_UNMEASURED_REASON in result.reason_codes
    assert RELATIONSHIP_UNMEASURED_REASON in result.reason_codes
    assert result.metrics["risk_bp"] == 1_000            # the authored floor, and nothing else


def test_a_measured_calm_and_a_blind_spot_are_no_longer_the_same_result():
    """They still produce the same number — that asymmetry is documented and deliberate, because
    `risk_bp` is summed into the ranking math and a withheld metric would read as unknown. What
    changes is that the result now carries the difference instead of swallowing it."""
    blind = run(RiskUnit(), prior={})
    calm = run(RiskUnit(), prior={
        "core.temporal": completed("core.temporal", drop_bp=0),
        "core.relationship": completed("core.relationship", relationship_risk_bp=0)})

    assert blind.metrics["risk_bp"] == calm.metrics["risk_bp"] == 1_000
    assert MOMENTUM_UNMEASURED_REASON in blind.reason_codes
    assert MOMENTUM_UNMEASURED_REASON not in calm.reason_codes
    assert _findings(calm)["risk.momentum_decay"].metrics == {"drop_bp": 0}


def test_half_blind_is_named_as_half_blind():
    """One source scheduled and the other not is the state the compiled lane will pass through on
    its way to both. It must not read as a complete risk assessment."""
    result = run(RiskUnit(), prior={"core.temporal": completed("core.temporal", drop_bp=6_000)})

    assert MOMENTUM_UNMEASURED_REASON not in result.reason_codes
    assert RELATIONSHIP_UNMEASURED_REASON in result.reason_codes
    assert result.metrics["risk_bp"] == 1_000 + 3_600


def test_a_source_that_ran_but_published_nothing_is_unmeasured():
    """Completion is not a reading. A temporal unit that completed without a `drop_bp` measured
    no decay, and treating its silence as a zero would be the same fabrication one level up."""
    result = run(RiskUnit(), prior={"core.temporal": completed("core.temporal")})

    assert MOMENTUM_UNMEASURED_REASON in result.reason_codes


def test_a_capability_may_still_appoint_its_own_exposure_sources():
    prior = {"sales.decay_model": completed("sales.decay_model", drop_bp=9_000),
             "core.relationship": completed("core.relationship", relationship_risk_bp=0)}

    result = run(RiskUnit(), config={"temporal_reasoner": "sales.decay_model"}, prior=prior)

    assert _findings(result)["risk.momentum_decay"].metrics["drop_bp"] == 9_000
    assert MOMENTUM_UNMEASURED_REASON not in result.reason_codes


def test_authored_mitigations_still_travel_as_negative_adjustments_in_sorted_order():
    """Untouched by this wave, pinned because the findings list around it moved: adjustment order
    is inside this result's semantic hash."""
    result = run(RiskUnit(), config={"play_risk_reduction_bp": {"z_play": 500, "a_play": 200}},
                 prior=BOTH)

    assert [(item.play_id, item.delta_bp) for item in result.adjustments] == [
        ("a_play", -200), ("z_play", -500)]
    assert {item.reason_code for item in result.adjustments} == {RISK_MITIGATION_REASON}
    assert "risk.risk_mitigation" not in _findings(result)


def test_the_headline_finding_stays_the_first_thing_a_reader_sees():
    """One claim, then its provenance. A reader of a risk result sees the do-nothing exposure;
    an auditor reading past it sees what built it."""
    result = run(RiskUnit(), prior=BOTH)

    assert [item.finding_id for item in result.findings] == [
        "risk.do_nothing", "risk.momentum_decay", "risk.relationship_health"]
    assert result.matched is None                        # risk is a magnitude, never a gate


# ── the same reading, through the real orchestrator ───────────────────────────────────────────

def test_risk_reads_both_exposures_on_a_capability_that_schedules_both_sources():
    """K1a end to end. The unit tests above prove the arithmetic; this proves the wiring — a real
    capability, the real orchestrator, the real plan — because a unit that only its own test can
    reach is a unit nobody runs."""
    from datetime import datetime, timedelta, timezone

    from genios_engine.contracts.reasoning import (ContextSnapshot, EvidenceRef,
                                                   ReasoningRequest)
    from genios_engine.packs.capabilities.deal_cooling_v2 import DEAL_COOLING_FULL_V2
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry

    moment = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
    inbound = (moment - timedelta(days=10)).isoformat()
    context = ContextSnapshot(
        org_id="org_1", graph_version=21, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=moment, selector_version="deal_cooling.selector.v1",
        facts={"deal.status": {"value": "open"}, "deal.value": {"value": 500_000},
               "derived.engagement": {"value_bp": 4_000},
               "thread.last_inbound": {"value": inbound},
               "relationship.verified_stakeholder_count": {"value": 2}},
        evidence=(EvidenceRef("ev_status", "deal.status", "open", source_ref_id="crm_1",
                              occurred_at=moment - timedelta(days=1), confidence_bp=9_500,
                              authority_rank=3, independence_group="crm"),
                  EvidenceRef("ev_engagement", "derived.engagement", 4_000,
                              source_ref_id="derived_1", occurred_at=moment - timedelta(hours=6),
                              confidence_bp=8_500, authority_rank=2,
                              independence_group="derived")),
        neighbor_facts={"deal.status": "open"}, edge_count=2)

    execution = ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id="org_1", capability=DEAL_COOLING_FULL_V2, context=context,
        evaluation_time=moment, trigger_kind="email.received", config_snapshot_id="cfg_1"))
    risk = execution.result_by_id["core.risk"]
    findings = {finding.finding_id: finding for finding in risk.findings}

    assert findings["risk.momentum_decay"].metrics["drop_bp"] > 0
    assert findings["risk.relationship_health"].metrics["relationship_risk_bp"] > 0
    assert MOMENTUM_UNMEASURED_REASON not in risk.reason_codes
    assert RELATIONSHIP_UNMEASURED_REASON not in risk.reason_codes

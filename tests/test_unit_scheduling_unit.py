"""Executable contract for the Scheduling Unit (core.scheduling).

Timing is where a correct-looking recommendation does real damage: sending the follow-up the night
before the call, chasing four hours after the last email, writing during a stated quiet window.
These tests pin the behaviours that keep that from happening:

* **Silence is a result.** A constraint the snapshot cannot evidence produces no observation. A
  fabricated zero would be indistinguishable from a measured "nothing in the way".
* **A deadline never argues against acting now** — it argues against waiting, and it caps any
  deferral the calendar would otherwise demand.
* **An absolute boundary stays absolute.** Deadline pressure can soften a soft objection; it can
  never talk the system past a quiet window.
* **The unit analyses, never decides.** It publishes timing metrics, touches no reserved shared
  metric, and emits no candidate adjustments or checks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    EvidenceRef,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.scheduling_unit import (
    CadenceSpacingPlugin,
    DeadlinePressurePlugin,
    QuietWindowPlugin,
    SchedulingUnit,
    UpcomingInteractionPlugin,
)
from genios_engine.reason.unit import UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _at(hours: int) -> str:
    """An ISO timestamp `hours` from the frozen evaluation time (negative for the past)."""
    return (NOW + timedelta(hours=hours)).isoformat()


def _request(facts=None, *, config=None, evidence=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.scheduling", "1.0.0", config=config or {}),),
        plays=(PlayDefinition(
            play_id="restore_momentum",
            version="1",
            label="Restore Momentum",
            steps=("Draft a grounded follow-up",),
        ),),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=facts or {},
        evidence=tuple(evidence),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _view(facts=None, *, config=None, evidence=()) -> UnitView:
    """The window a plugin sees, built exactly as the framework's Retriever would build it."""
    request = _request(facts, config=config, evidence=evidence)
    return SchedulingUnit().retrieve(request, request.capability.reasoners[0], {})


def _evaluate(facts=None, *, config=None, evidence=()):
    return SchedulingUnit().evaluate(_request(facts, config=config, evidence=evidence), {})


# ---------------------------------------------------------------------------------------------
# Upcoming interaction — the constraint that makes "follow up today" embarrassing
# ---------------------------------------------------------------------------------------------

def test_a_meeting_in_the_morning_makes_acting_tonight_a_preemption():
    """The follow-up we would send is the agenda of the call already booked for 06:00 tomorrow."""
    observations = UpcomingInteractionPlugin().contribute(
        _view({"calendar.next_meeting_at": _at(18)}))

    assert len(observations) == 1
    observation = observations[0]
    # 18h into a 72h horizon: three quarters of the pre-emption pressure remains.
    assert observation.metrics["against_now_bp"] == 7_500
    assert observation.metrics["hours_ahead"] == 18
    assert observation.metrics["wait_hours"] == 18
    assert observation.reason_codes == ("defer_until_after_meeting",)


def test_a_meeting_beyond_the_horizon_is_not_a_timing_constraint():
    """A call next week must not freeze this week's work — the plugin has nothing to say."""
    assert UpcomingInteractionPlugin().contribute(
        _view({"calendar.next_meeting_at": _at(96)})) == ()


def test_a_meeting_that_already_happened_constrains_nothing():
    """A past calendar entry is history; treating it as a future constraint would defer forever."""
    assert UpcomingInteractionPlugin().contribute(
        _view({"calendar.next_meeting_at": _at(-4)})) == ()


def test_a_missing_calendar_fact_produces_no_observation_rather_than_a_zero():
    """No calendar in the snapshot means unknown, not clear. A zero here would read as 'go now'."""
    assert UpcomingInteractionPlugin().contribute(_view({"deal.status": "open"})) == ()


def test_an_unparseable_meeting_timestamp_is_treated_as_absent():
    """Bad source data must not crash a reasoning run or invent a meeting time."""
    assert UpcomingInteractionPlugin().contribute(
        _view({"calendar.next_meeting_at": "next tuesday-ish"})) == ()


# ---------------------------------------------------------------------------------------------
# Deadline — pressure and a ceiling, never opposition
# ---------------------------------------------------------------------------------------------

def test_a_closing_deadline_creates_pressure_but_never_opposes_acting_now():
    """A deadline is the one constraint that argues only against waiting."""
    observations = DeadlinePressurePlugin().contribute(
        _view({"deal.close_date": _at(84)}))

    assert len(observations) == 1
    observation = observations[0]
    # 84h left of a 336h window: three quarters of the window already spent.
    assert observation.metrics["pressure_bp"] == 7_500
    assert observation.metrics["max_wait_hours"] == 84
    assert "against_now_bp" not in observation.metrics
    assert "act_before_deadline" in observation.reason_codes


def test_a_deadline_outside_the_window_stays_silent():
    """A close date eleven weeks out is a planning fact, not a reason to hurry today."""
    assert DeadlinePressurePlugin().contribute(_view({"deal.close_date": _at(1_000)})) == ()


def test_a_deadline_that_has_already_passed_is_not_a_scheduling_constraint():
    """Nothing can be waited for any more; a missed deadline belongs to core.risk, not here."""
    assert DeadlinePressurePlugin().contribute(_view({"deal.close_date": _at(-24)})) == ()


# ---------------------------------------------------------------------------------------------
# Cadence — the difference between persistence and pestering
# ---------------------------------------------------------------------------------------------

def test_writing_again_six_hours_after_the_last_email_is_crowding():
    """Cadence is measured from when they last heard from us, not from how urgent we feel."""
    observations = CadenceSpacingPlugin().contribute(
        _view({"deal.last_outbound": _at(-6)}))

    assert len(observations) == 1
    observation = observations[0]
    # 6h of a declared 48h gap consumed: seven eighths of the crowding remains.
    assert observation.metrics["against_now_bp"] == 8_750
    assert observation.metrics["wait_hours"] == 42
    assert observation.reason_codes == ("too_soon_after_last_contact",)


def test_a_respected_cadence_gap_produces_no_observation():
    """A constraint that has cleared is not an observation — emitting it would inflate the count."""
    assert CadenceSpacingPlugin().contribute(_view({"deal.last_outbound": _at(-60)})) == ()


def test_a_capability_can_declare_its_own_cadence_gap():
    """Enterprise renewals and support escalations are hours apart; Layer 3 owns that number."""
    observations = CadenceSpacingPlugin().contribute(
        _view({"deal.last_outbound": _at(-6)}, config={"min_gap_hours": 12}))

    assert observations[0].metrics["against_now_bp"] == 5_000
    assert observations[0].metrics["wait_hours"] == 6


def test_never_having_contacted_them_imposes_no_spacing_constraint():
    """A first touch has no cadence to respect."""
    assert CadenceSpacingPlugin().contribute(_view({"deal.status": "open"})) == ()


# ---------------------------------------------------------------------------------------------
# Quiet window — a boundary, not a preference
# ---------------------------------------------------------------------------------------------

def test_a_stated_quiet_window_is_reported_as_an_absolute_constraint():
    """They told us when we may next speak; the unit marks that so nothing can trade it away."""
    observations = QuietWindowPlugin().contribute(
        _view({"schedule.quiet_until": _at(30)}))

    assert observations[0].metrics["against_now_bp"] == 10_000
    assert observations[0].metrics["absolute_bp"] == 10_000
    assert observations[0].metrics["wait_hours"] == 30
    assert observations[0].reason_codes == ("inside_quiet_period",)


def test_an_expired_quiet_window_no_longer_constrains():
    """The boundary was time-boxed; once it passes it stops being a boundary."""
    assert QuietWindowPlugin().contribute(_view({"schedule.quiet_until": _at(-1)})) == ()


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_an_unconstrained_situation_reports_a_perfect_fit_and_says_so():
    """With nothing in the diary and no recent contact, 'now' must not be penalised."""
    result = _evaluate({"deal.status": "open"})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is False
    assert result.metrics["timing_fit_bp"] == 10_000
    assert result.metrics["wait_hours"] == 0
    assert result.metrics["constraint_count"] == 0
    assert result.reason_codes == ("timing_unconstrained",)


def test_the_binding_objection_sets_the_fit_rather_than_the_sum_of_objections():
    """Two soft constraints must not compound into a prohibition on a busy account."""
    result = _evaluate({"calendar.next_meeting_at": _at(18),      # 7_500 against now
                        "deal.last_outbound": _at(-24)})          # 5_000 against now

    assert result.metrics["timing_fit_bp"] == 2_500               # 10_000 - 7_500, not - 12_500
    assert result.metrics["constraint_count"] == 2
    assert result.metrics["wait_hours"] == 24                     # the longest wait, not the sum
    assert result.matched is True


def test_a_closing_deadline_softens_a_soft_objection_by_at_most_half():
    """As the cost of waiting rises the same pre-emption risk becomes more tolerable — but the
    relief is capped so pressure can never manufacture a good moment out of a bad one."""
    result = _evaluate({"calendar.next_meeting_at": _at(18),      # 7_500 against now
                        "deal.close_date": _at(84)})              # 7_500 of pressure

    assert result.metrics["timing_fit_bp"] == 10_000 - 7_500 + 3_750
    assert result.metrics["deadline_pressure_bp"] == 7_500


def test_deadline_pressure_cannot_talk_the_system_past_a_quiet_window():
    """Our deadline is our problem. An absolute boundary withdraws the relief entirely."""
    result = _evaluate({"schedule.quiet_until": _at(30),
                        "deal.close_date": _at(84)})

    assert result.metrics["timing_fit_bp"] == 0
    assert "inside_quiet_period" in result.reason_codes


def test_a_deadline_caps_a_deferral_and_the_conflict_is_named():
    """'Wait for Thursday's meeting' must never be published when the contract expires Wednesday."""
    result = _evaluate({"calendar.next_meeting_at": _at(60),      # clearing takes 60h
                        "deal.close_date": _at(36)})              # only 36h available

    assert result.metrics["wait_hours"] == 36
    assert "timing_conflict_deadline_before_clearance" in result.reason_codes


def test_every_observed_constraint_becomes_an_auditable_finding():
    """Someone will later ask why we wrote the day before a call; the trace must answer."""
    result = _evaluate({"calendar.next_meeting_at": _at(18), "deal.last_outbound": _at(-6)})

    assert sorted(finding.finding_id for finding in result.findings) == [
        "scheduling.cadence_spacing", "scheduling.upcoming_interaction"]
    assert all(finding.kind == "scheduling" for finding in result.findings)


def test_the_evidence_behind_a_constraint_travels_with_the_result():
    """A timing claim with no evidence id cannot be replayed or challenged."""
    facts = {"calendar.next_meeting_at": _at(18)}
    evidence = (EvidenceRef("ev_meeting", "calendar.next_meeting_at", facts[
        "calendar.next_meeting_at"]),)

    result = _evaluate(facts, evidence=evidence)

    assert "ev_meeting" in result.evidence_ids


def test_the_unit_analyses_and_never_decides():
    """No adjustment, no check, no ranking: synthesis belongs to the Decision Maker alone."""
    result = _evaluate({"calendar.next_meeting_at": _at(2), "deal.last_outbound": _at(-1),
                        "deal.close_date": _at(48)})

    assert result.adjustments == ()
    assert result.checks == ()


def test_the_unit_never_touches_a_reserved_shared_metric():
    """confidence_bp, urgency_bp and priority_override_bp belong to their named authorities."""
    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}
    result = _evaluate({"calendar.next_meeting_at": _at(2), "deal.close_date": _at(48)})

    assert reserved.isdisjoint(SchedulingUnit.publishes)
    assert reserved.isdisjoint(result.metrics)


def test_published_metrics_are_exactly_the_declared_ones():
    """The framework raises on an undeclared metric; this pins the declaration itself."""
    result = _evaluate({"calendar.next_meeting_at": _at(18)})

    assert set(result.metrics) <= set(SchedulingUnit.publishes)
    assert set(result.metrics) == {"constraint_count", "deadline_pressure_bp",
                                   "timing_fit_bp", "wait_hours"}


def test_the_same_situation_reasons_identically_twice():
    """Replayability is the whole promise: identical input, byte-identical result."""
    facts = {"calendar.next_meeting_at": _at(18), "deal.last_outbound": _at(-6),
             "deal.close_date": _at(120)}

    first = _evaluate(facts)
    second = _evaluate(facts)

    assert first.metrics == second.metrics
    assert first.reason_codes == second.reason_codes
    assert first.semantic_hash == second.semantic_hash


def test_a_float_threshold_authored_in_layer_three_fails_loudly():
    """Silent coercion of a float would change decision hashes without changing the manifest."""
    with pytest.raises(ValueError):
        _evaluate({"deal.status": "open"}, config={"timing_fit_threshold_bp": 6_000.0})


def test_the_unit_satisfies_the_reasoner_protocol():
    """Layer 4 runs units through one interface; a unit that misses it cannot be scheduled."""
    assert isinstance(SchedulingUnit(), Reasoner)


# ---------------------------------------------------------------------------------------------
# One real scenario, end to end
# ---------------------------------------------------------------------------------------------

def test_the_night_before_the_call_is_reported_as_a_bad_moment_to_write():
    """Northwind renewal, 6 August 12:00 UTC. The buyer's call is at 06:00 tomorrow, we emailed
    them six hours ago, and the contract lapses in nine days. Every instinct says "chase it"; the
    clock says the meeting is tomorrow and we already wrote this morning. The unit must report a
    poor fit for acting now, an 18-hour window to the meeting, and no invented deadline conflict —
    without ever saying what to send."""
    result = _evaluate({
        "deal.status": "open",
        "calendar.next_meeting_at": _at(18),        # 06:00 on 7 August
        "deal.last_outbound": _at(-6),              # we emailed at 06:00 today
        "deal.close_date": _at(216),                # nine days out, inside the 14-day window
    })

    assert result.matched is True
    assert result.metrics["constraint_count"] == 3
    # Cadence is the binding objection (8_750) — stronger than the meeting's 7_500 — and the
    # deadline (3_571bp of pressure) buys back half of that, no more.
    assert result.metrics["deadline_pressure_bp"] == 3_571
    assert result.metrics["timing_fit_bp"] == 10_000 - 8_750 + 1_786
    # Clearing both soft constraints takes 42 hours; the deadline is 216 hours away, so it does
    # not bind and no conflict is claimed.
    assert result.metrics["wait_hours"] == 42
    assert result.reason_codes == ("deadline_within_window", "defer_until_after_meeting",
                                   "too_soon_after_last_contact")
    assert result.adjustments == ()

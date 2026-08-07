"""Executable contract for the Timeline Unit (`core.timeline`).

The timeline is the only unit that reads *sequence*, so these tests pin the properties that make a
sequence trustworthy months later during a replay:

* **Silence beats invention.** No datable event, no declared cadence, fewer than two gaps — each of
  those produces nothing, never a confident zero. A fabricated zero is indistinguishable from a
  measured one and something downstream will eventually act on it.
* **Only real events enter the shape.** Future timestamps have not happened; the same message seen
  through two joins is one moment, not two.
* **Recency, overdue and trend stay separate.** They answer different questions and the unit must
  never average them into a single "timeline score".
* **Determinism.** Identical input yields identical metrics, with no dependence on the order facts
  happened to be written in.
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
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.reasoners.common import active_spec
from genios_engine.reason.reasoners.timeline_unit import (
    CadenceAdherencePlugin,
    EventOrderingPlugin,
    TimelineUnit,
    TrendDirectionPlugin,
)

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _ago(hours: int) -> str:
    """An ISO timestamp `hours` before the frozen evaluation time."""
    return (NOW - timedelta(hours=hours)).isoformat()


def _ahead(hours: int) -> str:
    return (NOW + timedelta(hours=hours)).isoformat()


def _request(facts=None, *, config=None, evidence=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.timeline", "1.0.0", config=config or {}),),
        plays=(PlayDefinition(play_id="restore_momentum", version="1", label="Restore momentum",
                              steps=("Draft a grounded check-in",)),),
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


def _view(request: ReasoningRequest, prior=None):
    unit = TimelineUnit()
    return unit.retrieve(request, active_spec(request, "core.timeline"), prior or {})


def _events(*ages: int) -> tuple[dict[str, str], ...]:
    """An explicit event log, given as ages in hours before the evaluation time."""
    return tuple({"event_id": f"evt_{index}", "occurred_at": _ago(age)}
                 for index, age in enumerate(ages))


# ---------------------------------------------------------------------------------------------
# Event ordering — the base layer every other timeline claim stands on
# ---------------------------------------------------------------------------------------------

def test_ordering_reports_recency_span_and_the_typical_gap():
    """Recency alone cannot tell a broken rhythm from no rhythm; span and typical gap can."""
    view = _view(_request({"timeline.events": _events(500, 400, 100)}))

    (observation,) = EventOrderingPlugin().contribute(view)

    assert observation.metrics["event_count"] == 3
    assert observation.metrics["latest_age_hours"] == 100
    assert observation.metrics["span_hours"] == 400
    assert observation.metrics["gap_hours"] == 200      # median of gaps (100, 300)
    assert observation.metrics["max_gap_hours"] == 300


def test_ordering_uses_the_median_gap_so_one_dormant_stretch_cannot_redefine_normal():
    """A mean would let a single holiday shutdown rewrite what a normal gap looks like forever."""
    view = _view(_request({"timeline.events": _events(1_000, 400, 376, 352, 328)}))
    # gaps are 600, 24, 24, 24: the mean would claim 168h is normal here. It is not — 24h is.

    (observation,) = EventOrderingPlugin().contribute(view)

    assert observation.metrics["gap_hours"] == 24
    assert observation.metrics["max_gap_hours"] == 600


def test_ordering_says_nothing_when_no_event_can_be_dated():
    """An undated situation has no shape. Reporting zero recency would read as "just happened"."""
    view = _view(_request({"deal.status": "open", "deal.value": 40_000}))

    assert EventOrderingPlugin().contribute(view) == ()


def test_a_malformed_timestamp_drops_its_event_rather_than_guessing_a_moment():
    """Half-parsed history is worse than less history: it silently moves every gap around it."""
    view = _view(_request({"timeline.events": (
        {"event_id": "evt_ok", "occurred_at": _ago(48)},
        {"event_id": "evt_bad", "occurred_at": "last tuesday"},
    )}))

    (observation,) = EventOrderingPlugin().contribute(view)

    assert observation.metrics["event_count"] == 1


def test_a_scheduled_future_event_is_not_part_of_the_observed_shape():
    """A meeting booked for Thursday has not happened; it must not become the newest 'event'."""
    view = _view(_request({"timeline.events": (
        {"event_id": "evt_past", "occurred_at": _ago(72)},
        {"event_id": "evt_booked", "occurred_at": _ahead(48)},
    )}))

    (observation,) = EventOrderingPlugin().contribute(view)

    assert observation.metrics["event_count"] == 1
    assert observation.metrics["latest_age_hours"] == 72


def test_one_message_seen_through_two_joins_counts_as_one_moment():
    """deal.last_inbound and thread.last_inbound are routinely the same email.

    Counting it twice would invent an extra event and a zero-hour gap that nobody ever lived.
    """
    view = _view(_request({"deal.last_inbound": _ago(30), "thread.last_inbound": _ago(30)}))

    (observation,) = EventOrderingPlugin().contribute(view)

    assert observation.metrics["event_count"] == 1
    assert "gap_hours" not in observation.metrics
    assert observation.reason_codes == ("timeline_single_event",)


def test_ordering_flags_when_the_current_silence_outlasts_every_prior_silence():
    """This relationship has never gone this quiet before — a fact about shape, not a verdict."""
    view = _view(_request({"timeline.events": _events(500, 400, 300)}))

    (observation,) = EventOrderingPlugin().contribute(view)

    assert observation.metrics["max_gap_hours"] == 100
    assert observation.metrics["latest_age_hours"] == 300
    assert "silence_exceeds_prior_gaps" in observation.reason_codes


def test_ordering_carries_the_evidence_of_the_facts_it_read():
    """A shape nobody can trace back to a source cannot be defended in a review."""
    request = _request(
        {"deal.last_inbound": _ago(30)},
        evidence=(EvidenceRef(evidence_id="ev_inbound", field="deal.last_inbound",
                              value=_ago(30)),),
    )

    (observation,) = EventOrderingPlugin().contribute(_view(request))

    assert observation.evidence_ids == ("ev_inbound",)


# ---------------------------------------------------------------------------------------------
# Cadence adherence — overdue only exists against a declaration
# ---------------------------------------------------------------------------------------------

def test_no_declared_cadence_means_nothing_is_overdue():
    """Three weeks quiet is negligence weekly, normal quarterly. Undeclared means unknowable."""
    view = _view(_request({"timeline.events": _events(500, 100)}))

    assert CadenceAdherencePlugin().contribute(view) == ()


def test_one_full_cadence_period_past_due_reads_as_a_total_breach():
    """Being a whole period late is as late as the metric needs to distinguish."""
    view = _view(_request({"timeline.cadence_hours": 168, "deal.last_inbound": _ago(336)}))

    (observation,) = CadenceAdherencePlugin().contribute(view)

    assert observation.metrics["overdue_hours"] == 168
    assert observation.metrics["breach_bp"] == 10_000
    assert observation.reason_codes == ("cadence_breached",)


def test_inside_the_declared_cadence_is_reported_as_on_track_not_as_absence():
    """A healthy rhythm is a real observation; suppressing it would make health unprovable."""
    view = _view(_request({"timeline.cadence_hours": 168, "deal.last_inbound": _ago(24)}))

    (observation,) = CadenceAdherencePlugin().contribute(view)

    assert observation.metrics["overdue_hours"] == 0
    assert observation.metrics["breach_bp"] == 0
    assert observation.reason_codes == ("cadence_on_track",)


def test_a_relationship_cadence_fact_overrides_the_capability_default():
    """The account said weekly; the capability's monthly default must not excuse the silence."""
    request = _request({"timeline.cadence_hours": 168, "deal.last_inbound": _ago(252)},
                       config={"expected_cadence_hours": 720})

    (observation,) = CadenceAdherencePlugin().contribute(_view(request))

    assert observation.metrics["cadence_hours"] == 168
    assert observation.metrics["overdue_hours"] == 84


def test_a_corrupt_cadence_fact_falls_back_to_config_instead_of_failing_the_run():
    """Bad data degrades to the capability declaration; bad config is an authoring bug (below)."""
    request = _request({"timeline.cadence_hours": "weekly", "deal.last_inbound": _ago(200)},
                       config={"expected_cadence_hours": 168})

    (observation,) = CadenceAdherencePlugin().contribute(_view(request))

    assert observation.metrics["cadence_hours"] == 168
    assert observation.metrics["overdue_hours"] == 32


def test_a_cadence_config_that_is_not_whole_hours_is_rejected_loudly():
    """A mistyped threshold that silently defaults would ship a capability nobody reviewed."""
    request = _request({"deal.last_inbound": _ago(10)},
                       config={"expected_cadence_hours": "168"})

    with pytest.raises(ValueError, match="expected_cadence_hours"):
        CadenceAdherencePlugin().contribute(_view(request))


# ---------------------------------------------------------------------------------------------
# Trend direction — momentum is a derivative, not a level
# ---------------------------------------------------------------------------------------------

def test_a_single_gap_is_not_a_trend():
    """Two events give one interval. Declaring a direction from it would be fabrication."""
    view = _view(_request({"timeline.events": _events(500, 100)}))

    assert TrendDirectionPlugin().contribute(view) == ()


def test_stretching_gaps_read_as_decay_below_the_steady_midpoint():
    """Gaps of 500h then 50h reversed: the rhythm is coming apart even while activity continues."""
    view = _view(_request({"timeline.events": _events(1_000, 500, 100, 50)}))
    # gaps oldest-first: 500, 400, 50 → earlier mean 500, recent mean 50 → strongly accelerating

    (observation,) = TrendDirectionPlugin().contribute(view)

    assert observation.metrics["acceleration_bp"] == 9_500
    assert observation.reason_codes == ("timeline_accelerating",)


def test_widening_gaps_read_as_decay():
    """Twice-weekly became fortnightly: same busy-looking account, opposite direction."""
    view = _view(_request({"timeline.events": _events(1_000, 916, 832, 496, 160)}))
    # gaps oldest-first: 84, 84, 336, 336 → earlier mean 84, recent mean 336

    (observation,) = TrendDirectionPlugin().contribute(view)

    assert observation.metrics["earlier_gap_hours"] == 84
    assert observation.metrics["recent_gap_hours"] == 336
    assert observation.metrics["acceleration_bp"] == 1_250
    assert observation.reason_codes == ("timeline_decaying",)


def test_an_unchanged_rhythm_reads_as_exactly_steady():
    """The midpoint must be reachable, or every stable relationship looks like it is moving."""
    view = _view(_request({"timeline.events": _events(400, 300, 200, 100)}))

    (observation,) = TrendDirectionPlugin().contribute(view)

    assert observation.metrics["acceleration_bp"] == 5_000
    assert observation.reason_codes == ("timeline_steady",)


def test_the_odd_middle_gap_belongs_to_neither_half():
    """A pivot counted on both sides would let one interval vote twice on its own trend."""
    view = _view(_request({"timeline.events": _events(700, 600, 300, 100)}))
    # gaps 100, 300, 200: earlier [100], recent [200], the 300 pivot is excluded

    (observation,) = TrendDirectionPlugin().contribute(view)

    assert observation.metrics["earlier_gap_hours"] == 100
    assert observation.metrics["recent_gap_hours"] == 200
    assert observation.metrics["gap_sample"] == 3


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_the_unit_never_claims_authority_over_a_shared_metric():
    """Publishing confidence or urgency from here would silently re-score every capability."""
    published = set(TimelineUnit.publishes)

    assert published.isdisjoint({"confidence_bp", "urgency_bp", "priority_override_bp"})


def test_an_empty_snapshot_yields_unknown_rather_than_a_healthy_looking_zero():
    """`matched=None` says we cannot see the shape; `False` would say the shape is fine."""
    result = TimelineUnit().evaluate(_request({"deal.status": "open"}), {})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is None
    assert dict(result.metrics) == {"event_count": 0}
    assert result.findings == ()


def test_unmeasurable_quantities_are_absent_rather_than_zero():
    """One event has no gap and no trend; zeros would read as 'instant, steady contact'."""
    result = TimelineUnit().evaluate(_request({"deal.last_inbound": _ago(50)}), {})

    assert result.metrics["event_count"] == 1
    assert result.metrics["elapsed_hours"] == 50
    assert "gap_hours" not in result.metrics
    assert "acceleration_bp" not in result.metrics
    assert "cadence_breach_bp" not in result.metrics


def test_the_unit_publishes_only_metrics_it_declared():
    """The framework raises on undeclared metrics; this pins the declaration against drift."""
    result = TimelineUnit().evaluate(
        _request({"timeline.cadence_hours": 168, "timeline.events": _events(900, 600, 300, 100)}),
        {})

    assert set(result.metrics) <= set(TimelineUnit.publishes)
    assert {"event_count", "elapsed_hours", "span_hours", "gap_hours", "max_gap_hours",
            "cadence_hours", "overdue_hours", "cadence_breach_bp",
            "acceleration_bp"} == set(result.metrics)


def test_identical_input_produces_identical_metrics():
    """Replay is the whole promise: a decision reviewed in six months must recompute exactly."""
    facts = {"timeline.cadence_hours": 168, "timeline.events": _events(912, 720, 552, 216)}

    first = TimelineUnit().evaluate(_request(facts), {})
    second = TimelineUnit().evaluate(_request(facts), {})

    assert dict(first.metrics) == dict(second.metrics)
    assert first.reason_codes == second.reason_codes
    assert first.semantic_hash == second.semantic_hash


def test_fact_write_order_cannot_change_the_shape():
    """Ordering must come from timestamps, never from the order Layer 2 happened to write facts."""
    forward = {"deal.last_inbound": _ago(300), "deal.last_outbound": _ago(200),
               "thread.last_inbound": _ago(100)}
    reversed_write = {"thread.last_inbound": _ago(100), "deal.last_outbound": _ago(200),
                      "deal.last_inbound": _ago(300)}

    assert dict(TimelineUnit().evaluate(_request(forward), {}).metrics) == \
        dict(TimelineUnit().evaluate(_request(reversed_write), {}).metrics)


def test_engagement_drop_corroborates_decay_without_moving_a_single_number():
    """core.temporal may agree with the timeline; it must never be able to re-score it."""
    facts = {"timeline.events": _events(1_000, 916, 832, 496, 160)}
    temporal = ReasonerResult("core.temporal", "1.0.0", ResultStatus.COMPLETED,
                              metrics={"drop_bp": 7_500})

    alone = TimelineUnit().evaluate(_request(facts), {})
    corroborated = TimelineUnit().evaluate(_request(facts), {"core.temporal": temporal})

    assert dict(alone.metrics) == dict(corroborated.metrics)
    assert "decay_corroborated_by_engagement_drop" not in alone.reason_codes
    assert "decay_corroborated_by_engagement_drop" in corroborated.reason_codes


def test_northwind_renewal_a_weekly_account_that_is_late_and_slowing():
    """The end-to-end case the unit exists for.

    Northwind is reviewed weekly (168h). Four touches at 912h, 720h, 552h and 216h ago: the gaps
    stretched from 192h to 336h and the last touch is 48h past the declared review. Both breaks are
    real and independent — late *and* slowing — and the unit must report them separately rather
    than blending them, because a late-but-accelerating account is a different situation.

    The historical maximum gap was 336h, so 216h of silence is overdue against the *declared*
    cadence without being unprecedented for this relationship. That distinction is the point of
    keeping cadence and ordering as separate claims.
    """
    request = _request({
        "timeline.cadence_hours": 168,
        "timeline.events": _events(912, 720, 552, 216),
        "deal.status": "open",
    })

    result = TimelineUnit().evaluate(request, {})

    assert result.matched is True
    assert result.metrics["event_count"] == 4
    assert result.metrics["elapsed_hours"] == 216
    assert result.metrics["span_hours"] == 696
    assert result.metrics["gap_hours"] == 192
    assert result.metrics["max_gap_hours"] == 336
    assert result.metrics["overdue_hours"] == 48
    assert result.metrics["cadence_breach_bp"] == 2_857
    assert result.metrics["acceleration_bp"] == 2_857
    assert "cadence_materially_overdue" in result.reason_codes
    assert "timeline_shape_decaying" in result.reason_codes
    assert "silence_exceeds_prior_gaps" not in result.reason_codes
    assert {finding.finding_id for finding in result.findings} == {
        "timeline.cadence_adherence", "timeline.event_ordering", "timeline.trend_direction"}


def test_a_late_but_tightening_account_is_not_reported_as_decaying():
    """Overdue and decaying are independent claims; ORing them must not blur which one fired."""
    request = _request({"timeline.cadence_hours": 24,
                        "timeline.events": _events(1_000, 500, 100, 50)})

    result = TimelineUnit().evaluate(request, {})

    assert result.matched is True
    assert "cadence_materially_overdue" in result.reason_codes
    assert "timeline_shape_decaying" not in result.reason_codes
    assert result.metrics["acceleration_bp"] == 9_500


def test_a_healthy_weekly_account_is_matched_false_not_none():
    """Seen-and-fine must be distinguishable from never-seen for downstream to trust it."""
    request = _request({"timeline.cadence_hours": 168,
                        "timeline.events": _events(400, 300, 200, 100)})

    result = TimelineUnit().evaluate(request, {})

    assert result.matched is False
    assert result.metrics["cadence_breach_bp"] == 0
    assert result.metrics["acceleration_bp"] == 5_000

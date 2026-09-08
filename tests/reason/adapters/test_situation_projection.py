"""WAVE Z5 · DLG-06 — Layer 2's BSO reaches a reasoning unit, and UNKNOWABLE stays unknown.

Every situation here is built by the REAL Layer 2 producers: `compose_situation_importance` runs
the actual six-modifier composition over real `TrendInput`/`CohortInput`/`AnomalyInput` rows, and
`build_business_situation` / `build_context_slice` publish it exactly as `domain_shadow` does. A
projection test that hand-wrote `metadata['importance_components']` would prove this module
consistent with a fixture and nothing about the seam.

The three states are tested as three states, in both directions, because the failure this wave
exists to prevent is not "the projection is missing" — it is "the projection is there and reads an
UNKNOWABLE as a number".
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from genios_engine.context.importance import (
    AnomalyInput,
    CohortInput,
    DependencyInput,
    ImportanceBase,
    ModifierInputs,
    ModifierName,
    TrendInput,
    compose_situation_importance,
)
from genios_engine.context.quality.inference import ABSENT_FIELDS_KEY, UNKNOWABLE_FIELDS_KEY
from genios_engine.context.situation_bso import (
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
)
from genios_engine.contracts.situation_evidence import AXIS_UNKNOWN_BP, CONFIDENCE_AXES
from genios_engine.reason.adapters import situation_projection as sp

pytestmark = pytest.mark.unit

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
ORG = "org_projection"
ANCHOR = "node_1"

#: The metric names the analytic fixtures use — REGISTERED ones, from `importance.METRIC_POLARITY`
#: and the sampler's trended set. Inventing `metric_a` would have passed the trend and anomaly
#: tests and silently failed the cohort one, which refuses a metric whose polarity is unregistered:
#: the cohort modifier cannot say whether the 95th percentile is the good end or the bad one.
TREND_METRIC = "engagement.touch_count_28d"
COHORT_METRIC = "relationship.response_latency_hours"
ANOMALY_METRIC = "engagement.days_since_contact"


def _composed(*, trends=(), cohorts=(), anomalies=(), dependencies=()):
    """The REAL composition. `compose_situation_importance` decides which terms fire; this test
    supplies inputs and never a verdict."""
    return compose_situation_importance(
        base=ImportanceBase(importance_bp=6_000, source="l1_qualified_signals",
                            signal_id="sig_1", version="alg17@1"),
        signals=(),
        modifiers=ModifierInputs(trends=tuple(trends), cohort_positions=tuple(cohorts),
                                 anomalies=tuple(anomalies), dependencies=tuple(dependencies),
                                 coverage_ready=True, coverage_domain="sales"),
        eval_time=NOW)


def _situation_row(**overrides):
    row = {
        "situation_id": "sit_projection", "situation_type": "deal", "domain": "sales",
        "status": "active", "correlation_id": None,
        "confidence_overall": 82, "coverage": 70,
        "first_seen_at": NOW, "last_seen_at": NOW,
        "anchor_node_id": ANCHOR, "anchor_name": "Fixture", "anchor_type": "company",
    }
    row.update(overrides)
    return row


def _bso(*, composed=None, row=None):
    row = row or _situation_row()
    signal_ids, evidence = gather_evidence_and_signals(None, ORG, None, row["situation_id"])
    return build_business_situation(org_id=ORG, situation=row, signal_ids=signal_ids,
                                    evidence=evidence, trace_id="trace_projection",
                                    composed=composed)


def _slice(*, unknowable=(), absent=()):
    row = _situation_row()
    built = build_context_slice(
        org_id=ORG, situation=row, facts={"deal.status": {"value": "open"}},
        observations=[], neighbor=(2, set(), {}), graph_version=1, eval_time=NOW,
        trace_id="trace_projection")
    metadata = dict(built.metadata)
    if unknowable:
        metadata[UNKNOWABLE_FIELDS_KEY] = list(unknowable)
    if absent:
        metadata[ABSENT_FIELDS_KEY] = list(absent)
    return replace(built, metadata=metadata)


def _project(*, composed=None, row=None, unknowable=(), absent=()):
    return sp.project_situation(situation=_bso(composed=composed, row=row),
                                context=_slice(unknowable=unknowable, absent=absent),
                                root_entity_id=ANCHOR)


# =================================================================================================
# THE K5 ROW · a BSO trend becomes a snapshot fact
# =================================================================================================

def test_a_declining_trend_becomes_a_snapshot_fact_with_its_own_evidence():
    """Doc 06 IN-1's acceptance row. The trend the importance leaned on is a named, evidenced,
    declared fact — not a number buried in a components blob nothing under `reason/` reads."""
    composed = _composed(trends=(TrendInput(metric=TREND_METRIC, subject_node_id=ANCHOR,
                                            direction="declining", trend_confidence_bp=8_000,
                                            point_count=6, fact_version_id="fv_1"),))
    projection = _project(composed=composed)

    name = f"{sp.TREND_PREFIX}{TREND_METRIC}"
    assert name in projection.facts, projection.receipt["analytic"]
    record = projection.facts[name]
    assert record["source"] == sp.PROJECTION_SOURCE
    assert record["value"]["metric"] == TREND_METRIC
    assert record["value"]["trend_confidence_bp"] == 8_000
    assert record["value"]["fact_version_id"] == "fv_1"
    # The reading travels with the fact, so a consumer never has to infer a direction from a
    # namespace it happens to recognise.
    assert "DECLINING" in record["reading"]
    # Evidence: minted, and resolvable to this exact fact.
    refs = [ref for ref in projection.evidence if ref.field == name]
    assert len(refs) == 1
    assert refs[0].source_ref_id == "sit_projection"
    assert refs[0].occurred_at is None


def test_a_trend_that_is_not_declining_projects_as_a_finding_not_as_a_gap():
    """The GENUINELY_ABSENT half. L2 compared and found nothing qualifying — that is a reading,
    and reading it as UNKNOWN would make "the metric is fine" indistinguishable from "we never
    looked"."""
    composed = _composed(trends=(TrendInput(metric=TREND_METRIC, subject_node_id=ANCHOR,
                                            direction="improving", trend_confidence_bp=9_000),))
    projection = _project(composed=composed)

    assert f"{sp.TREND_PREFIX}{TREND_METRIC}" not in projection.facts
    absence = projection.facts[f"{sp.ABSENCE_PREFIX}situation.trend"]
    assert absence["value"]["absence"] == "genuinely_absent"
    assert absence["value"]["licenses_negative_inference"] is True
    assert projection.receipt["analytic"]["trend"]["state"] == "absent"


def test_a_trend_nothing_measured_projects_as_unknown_and_carries_no_value():
    """The UNKNOWABLE half, and the one that matters: `no_input` means no comparison ran, so
    there is no value, no zero, and no `genuinely_absent` claim."""
    projection = _project(composed=_composed())

    assert projection.receipt["analytic"]["trend"] == {
        "state": "unknown", "reason": sp.NO_INPUT_REASON}
    assert "situation.trend" in projection.unknown_fields
    assert f"{sp.ABSENCE_PREFIX}situation.trend" not in projection.facts
    assert not any(name.startswith(sp.TREND_PREFIX) for name in projection.facts)


def test_the_cohort_and_anomaly_families_project_the_same_three_ways():
    composed = _composed(
        cohorts=(CohortInput(metric=COHORT_METRIC, subject_node_id=ANCHOR, percentile_bp=9_500,
                             population_size=40, cohort_id="coh_1"),),
        anomalies=(AnomalyInput(metric=ANOMALY_METRIC, subject_node_id=ANCHOR, flagged=True,
                                periods_used=8, z_like_bp=42_000, direction="up"),))
    projection = _project(composed=composed)
    cohort = projection.facts[f"{sp.COHORT_PREFIX}{COHORT_METRIC}"]
    assert cohort["value"]["percentile_bp"] == 9_500
    assert cohort["value"]["cohort_id"] == "coh_1"
    anomaly = projection.facts[f"{sp.ANOMALY_PREFIX}{ANOMALY_METRIC}"]
    assert anomaly["value"]["z_like_bp"] == 42_000
    # And the untouched family is UNKNOWN, not zero.
    assert "situation.trend" in projection.unknown_fields


def test_the_dependency_count_projects_as_a_count_and_never_as_a_zero():
    composed = _composed(dependencies=(DependencyInput(subject_node_id=ANCHOR, blocked_count=3),))
    projection = _project(composed=composed)
    assert projection.facts[sp.DEPENDENCY_FIELD]["value"] == {"blocked_count": 3}

    nothing = _project(composed=_composed())
    assert sp.DEPENDENCY_FIELD not in nothing.facts
    assert sp.DEPENDENCY_FIELD in nothing.unknown_fields


def test_the_modifier_names_this_module_reads_are_the_ones_layer_2_publishes():
    """The four names are restated as strings because the projection reads a STORED record. If
    `ModifierName` moves, this fails here instead of the projection silently finding nothing."""
    published = {member.value for member in ModifierName}
    named = {name for name, _ in sp.ANALYTIC_TERMS} | {sp.DEPENDENCY_TERM}
    assert named <= published, sorted(named - published)


# =================================================================================================
# THE TYPED-ABSENCE RULE · UNKNOWABLE is never a value
# =================================================================================================

def test_an_unassessed_confidence_axis_projects_as_unknown_and_never_as_a_number():
    """Doc 09's must-not-regress row 3 at this seam. `AXIS_UNKNOWN_BP` is a sentinel, not a score:
    projecting it as a number would rank an unassessed situation below every assessed one."""
    # `confidence_analytic` is NULL on the row -> the axis is unassessed.
    projection = _project(composed=_composed())
    vector = _bso(composed=_composed()).metadata["confidence_vector"]
    assert vector["analytic"] == AXIS_UNKNOWN_BP

    assert f"{sp.CONFIDENCE_PREFIX}analytic" in projection.unknown_fields
    assert f"{sp.CONFIDENCE_PREFIX}analytic" not in projection.facts
    # The assessed axis DID project, so the unknown one is a state and not a total failure.
    # `coverage` is the one this row carries (70%), and it arrives in basis points.
    assert projection.facts[f"{sp.CONFIDENCE_PREFIX}coverage"]["value"]["value_bp"] == 7_000


def test_the_confidence_vector_is_six_facts_and_is_never_collapsed_to_a_scalar():
    row = _situation_row(confidence_evidence=80, confidence_freshness=70,
                         confidence_consistency=60, confidence_identity=90,
                         confidence_analytic=50)
    projection = _project(composed=_composed(), row=row)
    for axis in CONFIDENCE_AXES:
        assert f"{sp.CONFIDENCE_PREFIX}{axis}" in projection.facts, axis
    # And there is no single `situation.confidence` fact that a reader could mistake for the
    # vector — a scalar beside the axes is how the collapse comes back.
    assert "situation.confidence" not in projection.facts


def test_an_unknowable_fact_path_projects_its_absence_type_and_licenses_nothing():
    """L2.5.5's five-state vocabulary, honoured at the L4 consumer. The value is a statement
    ABOUT the gap, never a value FOR the missing fact."""
    projection = _project(composed=_composed(), unknowable=("thread.last_inbound",))
    record = projection.facts[f"{sp.ABSENCE_PREFIX}thread.last_inbound"]
    assert record["value"]["absence"] == "unknowable"
    assert record["value"]["licenses_negative_inference"] is False
    assert record["value"]["fact"] == "thread.last_inbound"
    # The path itself is NOT projected as a fact with a false or a zero.
    assert "thread.last_inbound" not in projection.facts
    assert projection.unknowable_paths == ("thread.last_inbound",)


def test_a_genuinely_absent_fact_path_is_the_only_one_that_licenses_a_negative_inference():
    projection = _project(composed=_composed(), absent=("commitment.due_at",))
    record = projection.facts[f"{sp.ABSENCE_PREFIX}commitment.due_at"]
    assert record["value"]["absence"] == "genuinely_absent"
    assert record["value"]["licenses_negative_inference"] is True
    assert projection.absent_paths == ("commitment.due_at",)


def test_a_path_typed_both_ways_resolves_to_the_conservative_reading():
    """Contradictory stored rows are a real state. UNKNOWABLE wins, because the cost of reading a
    blind spot as a finding is a false negative inference delivered with a receipt."""
    projection = _project(composed=_composed(), unknowable=("thread.last_inbound",),
                          absent=("thread.last_inbound",))
    record = projection.facts[f"{sp.ABSENCE_PREFIX}thread.last_inbound"]
    assert record["value"]["absence"] == "unknowable"
    assert projection.receipt["typed_absence"]["typed_both_ways"] == ["thread.last_inbound"]
    # Reported as a contradiction in the DATA, and not as an internal refusal. `present`'s
    # duplicate guard exists to catch two writers reaching for one name — a projection bug — and a
    # `duplicate_field` count here would describe this module instead of the rows it read.
    assert projection.receipt["refused"] == {}


def test_a_missing_slice_types_nothing_rather_than_claiming_no_absences():
    projection = sp.project_situation(situation=_bso(composed=_composed()), context=None,
                                      root_entity_id=ANCHOR)
    assert projection.receipt["slice_supplied"] is False
    assert projection.unknowable_paths == ()
    assert not any(name.startswith(sp.ABSENCE_PREFIX) and "." in name[len(sp.ABSENCE_PREFIX):]
                   and not name[len(sp.ABSENCE_PREFIX):].startswith("situation.")
                   for name in projection.facts)


# =================================================================================================
# THE PROJECTION'S OWN LAWS
# =================================================================================================

def test_present_and_unknown_are_disjoint():
    projection = _project(composed=_composed())
    assert not set(projection.facts) & set(projection.unknown_fields)
    with pytest.raises(ValueError, match="both present and unknown"):
        replace(projection, unknown_fields=(sp.IMPORTANCE_FIELD,))


def test_every_projected_fact_carries_evidence_from_the_one_builder_and_one_witness():
    """Rule 11 raises confidence only across independence groups. Twelve groups from one situation
    would be twelve independent corroborations of a single witness."""
    composed = _composed(trends=(TrendInput(metric=TREND_METRIC, subject_node_id=ANCHOR,
                                            direction="declining", trend_confidence_bp=8_000),))
    projection = _project(composed=composed)
    assert {ref.field for ref in projection.evidence} == set(projection.facts)
    assert {ref.independence_group for ref in projection.evidence} == {
        sp.independence_group_for("sit_projection")}
    assert len({ref.evidence_id for ref in projection.evidence}) == len(projection.evidence)


def test_the_evidence_ids_are_the_ones_the_backfill_would_reconstruct():
    """`canonical_evidence_id_for` rebuilds a stored ref's id from the SNAPSHOT's root entity. A
    projection seeded from the situation id instead would be unreproducible by the migration."""
    from genios_engine.reason.evidence import canonical_evidence_id_for

    projection = _project(composed=_composed())
    for ref in projection.evidence:
        assert canonical_evidence_id_for(org_id=ORG, root_entity_id=ANCHOR,
                                         ref=ref) == ref.evidence_id


def test_the_projection_is_deterministic_and_clock_free():
    first = _project(composed=_composed())
    second = _project(composed=_composed())
    assert first == second
    source = inspect.getsource(sp)
    for forbidden in ("utcnow", "datetime.now", "random", "sqlalchemy", "LLMClient", "anthropic"):
        assert forbidden not in source, forbidden


def test_an_unprojectable_metric_name_is_refused_and_counted_never_coerced():
    """A metric name arrives from a stored row. One that cannot be a legal `EvidenceRef.field` is
    counted, not sanitised into something that reads like a different metric."""
    composed = _composed(trends=(TrendInput(metric="reply latency", subject_node_id=ANCHOR,
                                            direction="declining", trend_confidence_bp=8_000),))
    projection = _project(composed=composed)
    assert projection.receipt["analytic"]["trend"]["state"] == "refused"
    assert projection.receipt["refused"]["unprojectable_field_name"] == 1
    assert not any(name.startswith(sp.TREND_PREFIX) for name in projection.facts)


def test_a_family_larger_than_the_cap_truncates_and_says_by_how_much():
    """A cap is legitimate; a SILENT cap is not. The stored absence list is unbounded — it is one
    row per expected field per situation — and this projection is hashed into a context snapshot,
    so it is bounded here and anything cut is counted where a reader can see it."""
    paths = tuple(f"probe.field_{index:02d}" for index in range(sp.MAX_PER_FAMILY + 3))
    projection = _project(composed=_composed(), unknowable=paths)
    projected = [name for name in projection.facts if name.startswith(sp.ABSENCE_PREFIX)
                 and name[len(sp.ABSENCE_PREFIX):].startswith("probe.")]
    assert len(projected) == sp.MAX_PER_FAMILY
    assert projection.receipt["truncated"]["unknowable"] == 3
    # The withheld paths are still on the projection for a consumer that must honour them — the
    # cap bounds what enters the SNAPSHOT, never what Layer 2 said.
    assert projection.unknowable_paths == tuple(sorted(paths))


def test_the_lifecycle_and_importance_travel_whole():
    row = _situation_row(status="partial", resolved_by="cmd_1")
    projection = _project(composed=_composed(), row=row)
    lifecycle = projection.facts[sp.LIFECYCLE_FIELD]["value"]
    assert lifecycle == {"state": "partial", "partially_resolved": True, "resolved_by": "cmd_1"}
    importance = projection.facts[sp.IMPORTANCE_FIELD]["value"]
    # The COMPOSED number, and the base's own source beside it. `importance_source` describes the
    # BASE (`importance_base(l1)`, and this fixture supplies no Layer 1 read), so a composed 6000
    # that rests on the documented midpoint says `fallback: true` — which is exactly the
    # distinction `_log_importance_fallback` exists to make and the reason a card must be able to
    # read it off the projection instead of guessing from the number.
    assert importance["value_bp"] == 6_000
    assert importance["fallback"] is True
    assert importance["source"] == "default"
    assert importance["base_bp"] == 6_000


def test_an_uncomposed_situation_projects_the_base_alone_and_types_every_comparison_unknown():
    """A tenant whose sweep predates the composer. The importance is the documented midpoint, it
    says so, and NOT ONE analytic comparison is claimed either way."""
    projection = sp.project_situation(situation=_bso(composed=None), context=_slice(),
                                      root_entity_id=ANCHOR)
    importance = projection.facts[sp.IMPORTANCE_FIELD]["value"]
    assert importance["fallback"] is True
    assert importance["value_bp"] == 5_000
    for name, _ in sp.ANALYTIC_TERMS:
        assert projection.receipt["analytic"][name] == {
            "state": "unknown", "reason": "importance_composition_absent"}

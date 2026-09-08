"""U5 / DLG-04 — urgency derived from validated dates, ending the permanent neutral 5,000.

`urgency_bp` is resolved by the Decision Maker through `core.priority`, whose `MaximumUrgencyPlugin`
takes the loudest reading any prior unit reported. On the compiled lane no prior unit reported one,
so the maximum was taken over nothing, the neutral midpoint was published, and every card in the
org ranked identically on the urgency term. A midpoint is not a measurement.

`core.timeline` already parses the dates, so `core.timeline` computes the ladder. `core.priority`
stays the authority and stays unchanged; this unit is a declared SOURCE, and the roster test
refuses any publisher of `urgency_bp` that does not name the authority it defers to.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.contracts.reasoning import ResultStatus
from genios_engine.reason.decision_maker import priority_metrics
from genios_engine.reason.reasoners.priority import NEUTRAL_URGENCY_BP, PriorityReasoner
from genios_engine.reason.reasoners.timeline_unit import (
    URGENCY_BEYOND_BP,
    URGENCY_LADDER,
    URGENCY_UNDATED_BP,
    TimelineUnit,
    urgency_from_hours,
)

from .conftest import NOW, request, run, spec

DUE = "commitment.due_at"


def _at(hours: int) -> str:
    return (NOW + timedelta(hours=hours)).isoformat()


def _resolved(hours: int, certainty: str, *, span_hours: int = 0) -> dict:
    """A `ResolvedDate` as it reaches Layer 4: a window plus the band L1 resolved it at."""
    return {"as_written": "when they said", "certainty": certainty,
            "earliest": _at(hours), "latest": _at(hours + span_hours)}


def _urgency(facts: dict, **config) -> int:
    result = run(TimelineUnit(), facts=facts, config=config)
    assert result.status is ResultStatus.COMPLETED
    return result.metrics["urgency_bp"]


# ── the ladder ────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours, expected", [
    (-720, 10_000), (-1, 10_000), (0, 10_000),          # already due, or past due
    (1, 9_000), (48, 9_000),                            # within two days
    (49, 7_500), (168, 7_500),                          # within a week
    (169, 6_000), (336, 6_000),                         # within a fortnight
    (337, 4_000), (720, 4_000),                         # within a month
    (721, 2_000), (2_160, 2_000),                       # within a quarter
    (2_161, 500), (20_000, 500),                        # dated, but distant
])
def test_the_ladder_bands_the_distance_to_the_nearest_material_date(hours, expected):
    assert _urgency({DUE: {"value": _at(hours)}}) == expected


def test_an_undated_situation_reads_zero_and_says_so():
    """Not 5,000. An undated situation is not half urgent, it is undated, and a ladder that
    manufactured pressure out of an absent deadline would be inventing the evidence."""
    result = run(TimelineUnit(), facts={})

    assert result.metrics["urgency_bp"] == URGENCY_UNDATED_BP == 0
    assert "no_material_date" in result.reason_codes
    assert "deadline_hours" not in result.metrics


def test_a_date_a_year_out_still_outranks_no_date_at_all():
    """The floor of the ladder is 500, not 0, and that gap is the whole difference between a
    dated obligation and a situation nobody has committed to anything about."""
    assert _urgency({DUE: {"value": _at(20_000)}}) == URGENCY_BEYOND_BP > URGENCY_UNDATED_BP


# ── certainty ─────────────────────────────────────────────────────────────────────────────────

def test_an_exact_date_is_taken_at_full_weight():
    assert _urgency({DUE: _resolved(24, "exact")}) == 9_000


def test_a_range_is_read_at_its_earliest_bound():
    """The obligation becomes live when the window opens, not when it closes — reading the latest
    bound would let a fortnight-wide window hide a deadline that is already two days away."""
    assert _urgency({DUE: _resolved(24, "range", span_hours=500)}) == 9_000


def test_a_relative_date_is_halved():
    """"Soon" is a heuristic window ALG-09 guessed. Half-trusting it is the honest reading: it
    still moves the situation off the floor, and it cannot outrank a date somebody actually gave."""
    assert _urgency({DUE: _resolved(24, "relative")}) == 4_500
    assert _urgency({DUE: _resolved(24, "exact")}) == 9_000


# THESE THREE ASSERTED THE WRONG THING, and the thing they asserted hid a real defect for a whole
# wave. Each one hands the unit a field that CARRIES a value the unit cannot read — an UNRESOLVED
# window, a certainty word from no vocabulary, a timestamp that will not parse — and each one then
# demanded the same number an UNDATED situation publishes.
#
# Doc 02 U5 is explicit that a date which failed validation is UNKNOWN, not zero, three-state all
# the way through. While these two states shared the number 0, the whole org's `commitment.due_at`
# arriving as a NAIVE ISO timestamp (refused by `common.parse_time`, swallowed by `_moment`) was
# indistinguishable from an org that had promised nothing — a legitimate and common state, so
# nobody looked. They now assert the THIRD state: no `urgency_bp` published at all, and a reason
# code that names what happened. `core.priority`'s MaximumUrgencyPlugin reads an absent reading as
# 0 for its maximum, so nothing is manufactured and no ranking moves; what changes is that the
# trace can tell the two apart. See `tests/reason/test_urgency_ladder_supply.py`.

def _unreadable(facts: dict):
    result = run(TimelineUnit(), facts=facts)
    assert result.status is ResultStatus.COMPLETED
    assert "urgency_bp" not in result.metrics
    assert "material_date_unreadable" in result.reason_codes
    assert "no_material_date" not in result.reason_codes
    return result


def test_an_unresolved_date_is_not_a_deadline_and_is_not_a_measured_zero_either():
    """UNRESOLVED carries no window at all. There is nothing to measure a distance against, and
    a phrase the cascade could not resolve must not become a deadline on the way through L4 —
    but the cascade DID look, and reporting that as "undated" throws away the only evidence that
    somebody made a promise nobody can date."""
    _unreadable({DUE: {"as_written": "at some point", "certainty": "unresolved",
                       "earliest": None, "latest": None}})


def test_a_certainty_band_this_unit_does_not_know_is_not_read_as_exact():
    """An unrecognised band is an unread one. Defaulting it to EXACT is precisely the fabrication
    `ResolvedDate` exists to prevent — and defaulting it to a measured zero is the quieter half of
    the same fabrication."""
    _unreadable({DUE: {"as_written": "eventually", "certainty": "vibes", "earliest": _at(1)}})


def test_a_malformed_date_does_not_take_the_run_down():
    """Bad CONFIG raises; bad DATA is a fact of life. A capability's whole reasoning run must not
    die because one source system wrote a timestamp nobody can parse — and it must not report the
    unparseable timestamp as an absence of one."""
    _unreadable({DUE: {"value": "not a date"}})


# ── composition across several dates ──────────────────────────────────────────────────────────

def test_the_strongest_reading_wins_not_the_nearest_date():
    """A firm deadline in three weeks is not outranked by a vague "soon" that resolves nearer:
    the halving is a discount on the reading, so the reading is what has to be compared."""
    facts = {DUE: _resolved(2, "relative"), "renewal.at": {"value": _at(300)}}

    assert _urgency(facts, deadline_fields=[DUE, "renewal.at"]) == 6_000    # the exact fortnight


def test_the_winning_date_is_reported_with_its_distance():
    result = run(TimelineUnit(), facts={DUE: {"value": _at(100)}})

    assert result.metrics["urgency_bp"] == 7_500
    assert result.metrics["deadline_hours"] == 100


def test_an_overdue_commitment_reports_negative_hours():
    """A deadline missed by half an hour is late. Truncation toward zero reports it as `0` hours
    remaining — indistinguishable from a deadline landing exactly now — and that is the one
    rounding error a commitment tracker cannot afford."""
    result = run(TimelineUnit(), facts={DUE: {"value": (NOW - timedelta(minutes=30)).isoformat()}})

    assert result.metrics["deadline_hours"] < 0
    assert "deadline_overdue" in result.reason_codes


def test_which_facts_carry_a_deadline_is_declared_not_hardcoded():
    """Law 5: the unit knows what a dated obligation IS; the manifest knows which field holds
    one. A renewal date is not in the default list and must not need to be."""
    facts = {"subscription.renews_at": {"value": _at(24)}}

    assert _urgency(facts) == URGENCY_UNDATED_BP
    assert _urgency(facts, deadline_fields=["subscription.renews_at"]) == 9_000


def test_a_malformed_deadline_declaration_is_an_authoring_fault():
    with pytest.raises(ValueError):
        run(TimelineUnit(), facts={}, config={"deadline_fields": "commitment.due_at"})


def test_the_reading_is_deterministic_across_identical_runs():
    facts = {DUE: _resolved(30, "range", span_hours=100), "renewal.at": {"value": _at(700)}}
    config = {"deadline_fields": [DUE, "renewal.at"]}

    first = run(TimelineUnit(), facts=facts, config=config)
    second = run(TimelineUnit(), facts=facts, config=config)

    assert first.to_semantic_dict() == second.to_semantic_dict()


# ── the shape verdict must not be collateral damage ───────────────────────────────────────────

def test_a_situation_with_a_deadline_and_no_events_still_reports_an_unknown_shape():
    """The deadline plugin always speaks, so an empty observation list no longer means "we cannot
    see the shape". If `matched` fell to False here, a situation with a due date and no history
    would report a healthy rhythm it has never had."""
    result = run(TimelineUnit(), facts={DUE: {"value": _at(10)}})

    assert result.matched is None
    assert result.metrics["event_count"] == 0
    assert result.metrics["urgency_bp"] == 9_000


# ── the seam into the priority authority ──────────────────────────────────────────────────────

def test_the_priority_authority_resolves_the_timeline_reading_by_max_wins():
    """`priority.py` is untouched. Its `MaximumUrgencyPlugin` was written for exactly this and had
    nothing to resolve until now."""
    timeline = run(TimelineUnit(), facts={DUE: {"value": _at(10)}})

    priority = run(PriorityReasoner(), prior={"core.timeline": timeline})

    assert timeline.metrics["urgency_bp"] == 9_000
    assert priority.metrics["urgency_bp"] == 9_000
    assert priority.metrics["urgency_bp"] != NEUTRAL_URGENCY_BP


def test_the_authority_still_has_the_last_word_over_its_sources():
    """Two publishers is only safe because the scan stops at the authority. If a source could
    overwrite `core.priority`, the winner would be whichever unit happened to run last."""
    timeline = run(TimelineUnit(), facts={DUE: {"value": _at(10)}})
    priority = run(PriorityReasoner(), prior={"core.timeline": timeline})
    req = request(spec("core.timeline"), spec("core.priority"))

    urgency, override = priority_metrics([timeline, priority], req)

    assert urgency == priority.metrics["urgency_bp"]
    assert override is None


def test_an_undated_situation_reaches_the_decision_maker_as_zero_not_neutral():
    """The acceptance row, at the boundary where it matters: the neutral 5,000 that made every
    compiled card score the same is gone even when there is nothing to measure."""
    timeline = run(TimelineUnit(), facts={})
    priority = run(PriorityReasoner(), prior={"core.timeline": timeline})
    req = request(spec("core.timeline"), spec("core.priority"))

    urgency, _ = priority_metrics([timeline, priority], req)

    assert urgency == 0


# ── the distributional gate ───────────────────────────────────────────────────────────────────

def _corpus() -> tuple[tuple[int, int, str], ...]:
    """A deterministic spread of dated and undated situations.

    Offsets walk a fixed stride across a two-year window so every rung of the ladder is exercised
    at a realistic mix, and one situation in seven carries no date at all — because a real org's
    situations are mostly undated and a distribution that hid that would be flattering itself.
    """
    rows = []
    for index in range(320):
        offset = (index * 137) % 3_000 - 400
        certainty = ("exact", "exact", "range", "relative")[index % 4]
        rows.append((index, offset, "" if index % 7 == 6 else certainty))
    return tuple(rows)


def _percentile(values: list[int], nth: int) -> int:
    """Nearest-rank, integer arithmetic only — no statistics module, no floats."""
    ordered = sorted(values)
    rank = max(1, (nth * len(ordered) + 99) // 100)
    return ordered[rank - 1]


def test_the_urgency_distribution_is_not_a_spike_at_five_thousand():
    """The same gate L1's importance and L2's situations had to clear. A constant wearing a
    score's clothes is the defect; the ladder either separates situations or it has not fixed
    anything.
    """
    readings = []
    for index, offset, certainty in _corpus():
        facts = {} if not certainty else (
            {DUE: {"value": _at(offset)}} if certainty == "exact"
            else {DUE: _resolved(offset, certainty, span_hours=48)})
        readings.append(_urgency(facts))

    counts: dict[int, int] = {}
    for value in readings:
        counts[value] = counts.get(value, 0) + 1
    p50, p90 = _percentile(readings, 50), _percentile(readings, 90)
    modal_share = max(counts.values()) * 100 // len(readings)

    assert len(counts) >= 8, f"only {len(counts)} distinct urgency readings: {sorted(counts)}"
    assert p90 - p50 > 0, f"p90 == p50 == {p50}: the ladder is flat"
    assert modal_share < 50, f"one reading holds {modal_share}% of the corpus"
    assert counts.get(NEUTRAL_URGENCY_BP, 0) * 100 // len(readings) < 10


def test_the_neutral_midpoint_is_unreachable_from_a_date_anyone_actually_gave():
    """5,000bp is the value that meant "we have no information". After this wave it can only be
    produced by halving a maximal reading of a RELATIVE date — never by an EXACT or RANGE one at
    any distance — so a 5,000 in the field is a fact about certainty, not a fallback."""
    full_weight = {value for _bound, value in URGENCY_LADDER} | {URGENCY_BEYOND_BP}

    assert NEUTRAL_URGENCY_BP not in full_weight
    assert all(urgency_from_hours(hours) != NEUTRAL_URGENCY_BP
               for hours in range(-1_000, 3_000, 7))


# ── the same reading, through the real orchestrator ───────────────────────────────────────────

def _executed(extra_facts: dict):
    from datetime import datetime, timezone

    from genios_engine.contracts.reasoning import (ContextSnapshot, EvidenceRef,
                                                   ReasoningRequest)
    from genios_engine.packs.capabilities.deal_cooling_v2 import DEAL_COOLING_FULL_V2
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry

    moment = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
    facts = {"deal.status": {"value": "open"}, "deal.value": {"value": 500_000},
             "derived.engagement": {"value_bp": 4_000},
             "thread.last_inbound": {"value": (moment - timedelta(days=10)).isoformat()},
             "relationship.verified_stakeholder_count": {"value": 2}}
    facts.update(extra_facts)
    context = ContextSnapshot(
        org_id="org_1", graph_version=21, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=moment, selector_version="deal_cooling.selector.v1", facts=facts,
        evidence=(EvidenceRef("ev_status", "deal.status", "open", source_ref_id="crm_1",
                              occurred_at=moment - timedelta(days=1), confidence_bp=9_500,
                              authority_rank=3, independence_group="crm"),),
        neighbor_facts={"deal.status": "open"}, edge_count=2)
    return moment, ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id="org_1", capability=DEAL_COOLING_FULL_V2, context=context,
        evaluation_time=moment, trigger_kind="email.received", config_snapshot_id="cfg_1"))


def test_a_capability_that_declares_its_urgency_source_never_sees_the_ladder():
    """`sales.deal_cooling` names `core.temporal` as its `source_reasoner`, which is an assertion
    by the capability author that decay IS urgency for this situation — and the declared path
    deliberately outranks max-wins, so the ladder does not reach the authority here.

    Pinned because it is the seam, not the defect: the neutral 5,000 lived on the COMPILED lane,
    whose `core.priority` declares no source at all (see the next test). A capability that wants
    dated pressure to compete either drops its declaration or names `core.timeline`.
    """
    _moment, execution = _executed({DUE: {"value": "2026-08-01T12:00:00+00:00"}})

    timeline = execution.result_by_id["core.timeline"]
    priority = execution.result_by_id["core.priority"]

    assert timeline.metrics["urgency_bp"] == 10_000         # five days overdue
    assert timeline.metrics["deadline_hours"] == -120
    assert priority.metrics["urgency_bp"] == execution.result_by_id[
        "core.temporal"].metrics["urgency_bp"]


def test_the_ladder_reaches_the_authority_on_a_lane_that_declares_no_source():
    """The compiled lane's shape: `core.priority` with no `source_reasoner`, resolving max-wins
    across whatever ran. Run through the real orchestrator, not by calling units by hand — the
    plan, the topological order and the result sequence are all part of what has to work."""
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry

    from .conftest import capability, context

    from genios_engine.contracts.reasoning import ReasoningRequest

    manifest = capability(spec("core.timeline"),
                          spec("core.priority", dependencies=("core.timeline",)))
    execution = ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id="org_1", capability=manifest,
        context=context({DUE: {"value": _at(10)}}),
        evaluation_time=NOW, trigger_kind="test.trigger", config_snapshot_id="cfg_1"))

    assert execution.result_by_id["core.timeline"].metrics["urgency_bp"] == 9_000
    assert execution.result_by_id["core.priority"].metrics["urgency_bp"] == 9_000
    assert execution.selected_candidate.score_components["urgency"] == 9_000


def test_the_same_lane_without_a_date_ranks_on_zero_rather_than_the_midpoint():
    """The defect this wave exists to end, observed through a run: an undated situation no longer
    borrows a middling urgency it never earned, and its card ranks accordingly."""
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry

    from .conftest import capability, context

    from genios_engine.contracts.reasoning import ReasoningRequest

    manifest = capability(spec("core.timeline"),
                          spec("core.priority", dependencies=("core.timeline",)))
    execution = ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id="org_1", capability=manifest, context=context({}),
        evaluation_time=NOW, trigger_kind="test.trigger", config_snapshot_id="cfg_1"))

    assert execution.result_by_id["core.priority"].metrics["urgency_bp"] == 0
    assert execution.selected_candidate.score_components["urgency"] == 0
    assert execution.result_by_id["core.timeline"].metrics["urgency_bp"] != NEUTRAL_URGENCY_BP


def test_a_priority_that_does_not_declare_the_timeline_falls_back_to_the_midpoint():
    """The trap that would put the 5,000 straight back, and the reason this is a test and not a
    comment: the orchestrator hands a unit only the results of the units it DECLARED. A roster
    that schedules `core.timeline` but leaves it out of `core.priority`'s dependencies gets an
    empty prior map, `MaximumUrgencyPlugin` takes a maximum over nothing, and every card in the
    org goes back to the neutral midpoint — with the ladder computing perfectly, one unit away.
    """
    from genios_engine.contracts.reasoning import ReasoningRequest
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry

    from .conftest import capability, context

    undeclared = capability(spec("core.timeline"), spec("core.priority"))
    execution = ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id="org_1", capability=undeclared, context=context({DUE: {"value": _at(10)}}),
        evaluation_time=NOW, trigger_kind="test.trigger", config_snapshot_id="cfg_1"))

    assert execution.result_by_id["core.timeline"].metrics["urgency_bp"] == 9_000
    assert execution.result_by_id["core.priority"].metrics["urgency_bp"] == NEUTRAL_URGENCY_BP

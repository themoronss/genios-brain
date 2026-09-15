"""566 analytic facts, and not one of them could ever be a card.

    pytest tests/context/test_the_analytic_stratum_was_never_a_subject.py -q

MEASURED READ-ONLY ON THE PILOT, 2026-09-15: 264 `derived.trend.*`, 264 `derived.anomaly.*` and
38 `derived.cohort_position.*` facts, live. Their only reader in the whole engine was BLG-18's
importance modifiers — six of them, which adjust the rank of a card built from something else. So
L2.4 could make another finding sort higher and could never state a finding of its own, and "this
relationship has been going quiet for three sampling periods" was computed every sweep and shown
to nobody.

WHAT THIS READING IS NOT ALLOWED TO BE. The detectors already decided. `trend` publishes a
`direction` from its own closed vocabulary; `anomaly` publishes `flagged` from its own
two-condition conjunction against thresholds that are contract rules from doc 04; `cohort_position`
publishes a position or a `refused`. A second opinion here — "but only if the slope is steep
enough for my taste" — would be a number tuned on the one tenant we happened to look at, applied
to a customer we have never seen. There is no threshold in `analytic_situations` and these tests
fail the build if one appears.

WHAT IT ADMITS is what the detector called a MOVEMENT, and the distinction does real work. FLAT is
a measurement — the thing did not move — and the two insufficiency directions are refusals about
what we hold. Neither is something that happened to the business, and a feed carrying one card per
account saying "we cannot tell you about this account" is the flood the layer exists to prevent.

THE COVERAGE CAVEAT IS PART OF THE CLAIM. On the pilot every single trend was computed over a
window with `coverage_ratio_bp` 6666 and `gcal` silent for four periods. A card asserting a
decline out of that window without saying so is reporting our own missing connector as the
customer's behaviour — which doc 04 names as the worst output this group can produce.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.context.analytic_situations import (ANCHOR_ANALYTIC, MAX_PER_SWEEP, MOVED,
                                                       read_analytic_movements)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
NAMES = {"node_a": "Aditya Dwivedi", "node_b": "Boardy Boardman"}


def trend(metric: str = "engagement.inbound_count_28d", *, direction: str = "declining",
          slope: int = 5000, **extra) -> tuple[str, dict]:
    payload = {"metric": metric, "direction": direction, "relative_slope_bp": slope,
               "streak_periods": 1, "point_count": 8, "trend_confidence_bp": 4265,
               "coverage_ratio_bp": 6666, "gap_corrected": True,
               "gap_reasons": {"silent_sources": ["gcal"],
                               "unknowable_periods": ["2026-06-29T00:00:00+00:00",
                                                      "2026-09-14T00:00:00+00:00"]}}
    payload.update(extra)
    return (f"derived.trend.{metric}", payload)


def anomaly(metric: str = "engagement.days_since_contact", *, flagged: bool = True,
            z: int = 31000) -> tuple[str, dict]:
    return (f"derived.anomaly.{metric}",
            {"metric": metric, "flagged": flagged, "z_like_bp": z, "deviation_bp": 5000,
             "current_bp": 54, "baseline_bp": 36, "direction": "above", "periods_used": 6})


def cohort(metric: str = "account.contact_breadth", **extra) -> tuple[str, dict]:
    payload = {"metric": metric, "percentile_bp": 9200, "population_size": 19,
               "cohort_id": "coh_abc"}
    payload.update(extra)
    return (f"derived.cohort_position.{metric}", payload)


def facts_of(finding) -> dict:
    return {key: value for key, value, _type in finding.facts}


# =================================================================================================
# THE LANE EXISTS AT ALL
# =================================================================================================

def test_a_measured_movement_becomes_a_situation(conn=None) -> None:
    """THE WHOLE DEFECT IN ONE ASSERTION. Before this reading, this fact reached a card only as a
    number that made some OTHER card rank higher."""
    out = read_analytic_movements({"node_a": [trend()]}, NOW, NAMES)
    assert len(out) == 1
    assert out[0].anchor == ANCHOR_ANALYTIC
    assert out[0].concerns_node == "node_a"
    assert "Aditya Dwivedi" in out[0].display_name


def test_all_three_families_can_be_a_subject() -> None:
    """Trend, anomaly and cohort position are three different questions — against its own past,
    against its own baseline, against its peers — and an account can move on one while sitting
    still on the others."""
    rows = {"node_a": [trend(), anomaly(), cohort()]}
    kinds = {facts_of(f)["analytic.kind"] for f in read_analytic_movements(rows, NOW, NAMES)}
    assert kinds == {"trend", "anomaly", "cohort_position"}


# =================================================================================================
# WHAT THE DETECTOR CALLED A MOVEMENT — and nothing else
# =================================================================================================

def test_a_flat_trend_is_a_measurement_and_not_a_situation() -> None:
    """It says the thing did not move, which is the answer to a question nobody asked. On the
    pilot 58 trends read FLAT; a card each would bury the 52 that moved."""
    assert read_analytic_movements({"node_a": [trend(direction="flat")]}, NOW, NAMES) == []


@pytest.mark.parametrize("refusal", ["insufficient_history", "insufficient_coverage"])
def test_a_refusal_is_not_a_finding(refusal: str) -> None:
    """A refusal is information and it belongs on the surface that reports coverage. 94 cards
    reading "we cannot tell you about this account" is one gap, told 94 times."""
    assert read_analytic_movements({"node_a": [trend(direction=refusal)]}, NOW, NAMES) == []


def test_an_unflagged_anomaly_is_not_a_finding() -> None:
    """The detector carries the un-flagged measurement on purpose, so a reader can ask "why
    wasn't this flagged" and get an answer. That is a receipt, not an event — and on the pilot
    ZERO of 264 anomalies were flagged, so a reading that ignored the flag would have invented
    264 findings out of a detector that said nothing."""
    assert read_analytic_movements({"node_a": [anomaly(flagged=False, z=18000)]}, NOW, NAMES) == []


def test_a_refused_cohort_position_is_not_a_finding() -> None:
    """`insufficient_coverage` on 29 of 48 members is a statement about what we hold."""
    rows = {"node_a": [cohort(refused="insufficient_coverage", percentile_bp=None)]}
    assert read_analytic_movements(rows, NOW, NAMES) == []


def test_the_admitted_directions_are_the_detectors_own_words() -> None:
    """Spelled as the detector spells them. A direction added upstream must arrive here as an
    unknown word and be excluded loudly, rather than be silently dropped by an enum this module
    pinned a copy of."""
    assert MOVED == ("rising", "declining")


# =================================================================================================
# THE CAVEAT TRAVELS WITH THE CLAIM
# =================================================================================================

def test_a_movement_computed_over_a_broken_window_says_so() -> None:
    """THE MEASURED CASE. Every trend on the pilot was computed across a window a third of which
    could not be read, with a connector silent throughout. A card asserting a decline from that
    without saying so describes our blind spot as their behaviour."""
    got = facts_of(read_analytic_movements({"node_a": [trend()]}, NOW, NAMES)[0])
    assert got["analytic.coverage_ratio_bp"] == 6666
    assert got["analytic.silent_sources"] == "gcal"
    assert got["analytic.unreadable_periods"] == 2
    assert got["analytic.gap_corrected"] is True


def test_a_clean_window_carries_no_caveat_it_does_not_have() -> None:
    """The mirror. A caveat printed on every card is a caveat nobody reads."""
    clean = trend(gap_corrected=False, coverage_ratio_bp=10_000, gap_reasons={})
    got = facts_of(read_analytic_movements({"node_a": [clean]}, NOW, NAMES)[0])
    assert "analytic.silent_sources" not in got
    assert "analytic.gap_corrected" not in got
    assert got["analytic.coverage_ratio_bp"] == 10_000


def test_the_cause_is_declared_missing() -> None:
    """L2.4 reads shape and never reads a sentence: it knows the count fell and has no access to
    any reason anybody would give for it. A card that supplies one has invented the only part of
    this that matters to a reader."""
    assert read_analytic_movements({"node_a": [trend()]}, NOW, NAMES)[0].missing == \
        ["analytic.cause"]


# =================================================================================================
# WHAT MUST NOT HAVE BEEN ADDED
# =================================================================================================

def test_the_reading_declares_no_threshold_of_its_own() -> None:
    """THE RULE THIS UNIT REFUSES TO WRITE, checked as code rather than by grepping prose. The
    detectors' thresholds are contract rules from doc 04; a second set here would be tuned on one
    tenant and wrong for the next."""
    import ast
    import inspect

    from genios_engine.context import analytic_situations

    tree = ast.parse(inspect.getsource(analytic_situations))
    numeric = [t.id for node in tree.body if isinstance(node, ast.Assign)
               for t in node.targets if isinstance(t, ast.Name)
               and isinstance(node.value, ast.Constant)
               and isinstance(node.value.value, (int, float))
               and not isinstance(node.value.value, bool)]
    assert numeric == ["MAX_PER_SWEEP"], f"a threshold lives here: {numeric}"

    compares = [c for c in ast.walk(tree) if isinstance(c, ast.Compare)
                and any(isinstance(x, ast.Constant) and isinstance(x.value, (int, float))
                        and not isinstance(x.value, bool) and x.value not in (0, 1)
                        for x in c.comparators)]
    assert compares == [], "the reading is comparing a measurement against a number"


def test_the_metric_name_is_rendered_and_never_looked_up() -> None:
    """NO METRIC VOCABULARY. A tenant measuring something this engine has never seen must get a
    readable sentence about it, not silence. That is the difference between a renderer and a rule,
    and a lookup table here would silently drop every metric a future pack introduces."""
    unheard = trend("procurement.days_to_quote", direction="rising")
    out = read_analytic_movements({"node_a": [unheard]}, NOW, NAMES)
    assert len(out) == 1
    assert "days to quote" in out[0].display_name


def test_findings_are_bounded_and_ordered_by_the_detectors_own_magnitude() -> None:
    """The bound is a bound, not a filter: which survive it is decided by a number L2.4 computed,
    so this module forms no opinion about which metric matters."""
    rows = {"node_a": [trend(f"m.metric_{i}", slope=i * 100) for i in range(MAX_PER_SWEEP + 6)]}
    out = read_analytic_movements(rows, NOW, NAMES)
    assert len(out) == MAX_PER_SWEEP
    slopes = [facts_of(f)["analytic.relative_slope_bp"] for f in out]
    assert slopes == sorted(slopes, reverse=True), "the steepest movements were not the survivors"


def test_a_replay_of_one_sweep_produces_the_same_feed() -> None:
    """Ties break on the key, so two metrics that moved by exactly as much do not swap places
    between one run and the next."""
    rows = {"node_a": [trend(f"m.same_{i}", slope=5000) for i in range(MAX_PER_SWEEP + 3)]}
    first = [f.canonical_key for f in read_analytic_movements(rows, NOW, NAMES)]
    second = [f.canonical_key for f in read_analytic_movements(rows, NOW, NAMES)]
    assert first == second


def test_a_malformed_row_costs_one_reading_and_not_the_tenant() -> None:
    """One unreadable payload is one silent finding; an exception is every finding on the org."""
    rows = {"node_a": [("derived.trend.x", "{not json"), trend()]}
    assert len(read_analytic_movements(rows, NOW, NAMES)) == 1


def test_a_node_with_no_name_is_still_reported() -> None:
    """35 of the pilot's 76 people display a bare address because nothing stored the header's
    display name. They must not vanish from a lane that is about their behaviour."""
    out = read_analytic_movements({"node_z": [trend()]}, NOW, NAMES)
    assert len(out) == 1 and out[0].concerns_node == "node_z"


def test_the_reading_is_wired_into_the_registry() -> None:
    """A reading nothing dispatches is a function nobody calls."""
    from genios_engine.context.outreach_situations import READINGS

    assert ANCHOR_ANALYTIC in {anchor for anchor, _ in READINGS}


def test_the_anchor_resolves_to_a_type_the_corpus_can_bind() -> None:
    """The last link. An anchor with no situation type reaches `context_situations` and routes
    to nothing, which is the state five types are in today."""
    from genios_engine.context.domain_spec import domains_declaring, spec_for

    domains = domains_declaring(ANCHOR_ANALYTIC)
    assert domains, f"no domain declares the anchor {ANCHOR_ANALYTIC!r}"
    for domain in domains:
        assert spec_for(domain).situation_types[ANCHOR_ANALYTIC] == "analytic_movement"

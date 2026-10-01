r"""`B6` · `core.tradeoff` says WHICH comparison it could not make, and which unit to go and look at.

⛔ WHAT WAS WRONG. Measured on production 2026-10-01:

    axis_count                      1 on 63% of runs · 2 on 37% · never 3
    tradeoff.cost_vs_benefit        0 firings in 1,200 rows

`axis_count` is honest and was unactionable: it says how many comparisons were possible and never
which one was lost or why. And **nothing outside `tradeoff_unit.py` read it** — grepped.

⛔ AND THE RECEIPT WAS REFUSED ONCE, ON A FALSE PREMISE. `08-AUDIT-AND-PLAN-the-silence-receipt.md`
rejected this fix because it would *"rehash ~100% of 12,170 traces"*. It does not.
`ReasoningStore._verify_replay_bundle` hashes the content **stored inside a bundle** and compares it to
the hash **stored beside it** — it never re-runs a unit. An old run keeps its old output and old hash,
both consistent, and still verifies. `contracts/reasoning.py:845` warns about changing
`to_semantic_dict` — the hashing FUNCTION — which is a different operation.
"""
from __future__ import annotations

import pytest

from genios_engine.reason.reasoners import CORE_UNITS, SUPPLEMENTARY_UNITS
from genios_engine.reason.reasoners.tradeoff_unit import (AXIS_SOURCES, TradeoffUnit, _AXES,
                                                          _absent_side)

from .conftest import completed, run

ALL_UNITS = CORE_UNITS + SUPPLEMENTARY_UNITS


def _all_six() -> dict:
    """Every axis side present, none tied — the state in which nothing should be reported lost."""
    return {
        "core.impact": completed("core.impact", impact_bp=8_000),
        "core.cost": completed("core.cost", effort_bp=3_000),
        "core.opportunity": completed("core.opportunity", opportunity_bp=7_000),
        "core.risk": completed("core.risk", risk_bp=4_000),
        "core.temporal": completed("core.temporal", urgency_bp=6_500),
        "core.confidence": completed("core.confidence", confidence_bp=5_000),
    }


def _metrics(result) -> dict:
    return dict(result.metrics)


def _codes(result) -> set[str]:
    return set(result.reason_codes)


# ── the conditional-inclusion rule, which is the house rule and not a preference ───────────────

def test_with_every_source_present_the_new_metric_is_ABSENT_not_zero():
    """⛔ THE RULE `contracts/reasoning.py:845` RECORDS. A key written on every result *"enters the
    canonical JSON of every finding ever emitted"*. A run with all six sources present must hash
    exactly as it did before this seam existed."""
    result = run(TradeoffUnit(), prior=_all_six())
    assert "axes_unavailable" not in _metrics(result), (
        "the metric is present on a run that lost nothing — every historical run would now differ")
    assert not any(c.startswith("unavailable.") for c in _codes(result))
    assert not any(c.startswith("absent_source.") for c in _codes(result))


def test_all_three_axes_speak_when_all_six_sources_are_present():
    """The baseline the rest of this file measures against. If this fails, nothing below means
    anything — and note that this is the state `tests/reason/test_tradeoff_cost_axis.py` proves, on
    priors the test supplies, while production has never once reached it."""
    result = run(TradeoffUnit(), prior=_all_six())
    assert _metrics(result)["axis_count"] == 3


# ── the receipt itself ────────────────────────────────────────────────────────────────────────

def test_a_lost_axis_names_the_axis_and_the_absent_source():
    """⛔ THE PRODUCTION CASE, REPRODUCED. `core.impact` completes 1,973 times publishing only
    `impact_signal_count`, so `impact_bp` is absent and `cost_vs_benefit` cannot be compared."""
    priors = _all_six()
    priors["core.impact"] = completed("core.impact", impact_signal_count=0)

    result = run(TradeoffUnit(), prior=priors)
    metrics, codes = _metrics(result), _codes(result)

    assert metrics["axis_count"] == 2, "two axes should still speak"
    assert metrics["axes_unavailable"] == 1
    assert "unavailable.cost_vs_benefit" in codes
    assert "absent_source.core.impact.impact_bp" in codes, (
        f"the receipt must name the unit AND the metric a reader has to go and look at; got "
        f"{sorted(c for c in codes if c.startswith('absent_source'))}")


def test_the_two_numbers_must_sum_to_the_three_axes():
    """⛔ TWO NUMBERS THAT ARE SUPPOSED TO AGREE, COMPARED. `axis_count` counts comparisons that
    happened; `axes_unavailable` counts those that could not. This programme has found five times
    that two expressions of one fact which are never compared eventually disagree."""
    for absent in ("core.impact", "core.cost", "core.risk", "core.temporal"):
        priors = _all_six()
        del priors[absent]
        metrics = _metrics(run(TradeoffUnit(), prior=priors))
        assert metrics["axis_count"] + metrics.get("axes_unavailable", 0) == len(_AXES), (
            f"dropping {absent}: {metrics}")


def test_losing_one_unit_can_lose_two_axes_and_both_are_named():
    """`core.temporal` is the `speed_source` AND `core.opportunity`'s momentum source. Dropping it
    costs `speed_vs_certainty` directly, and the receipt must name every axis it took."""
    priors = _all_six()
    del priors["core.temporal"]
    result = run(TradeoffUnit(), prior=priors)
    codes = _codes(result)
    assert "unavailable.speed_vs_certainty" in codes
    assert "absent_source.core.temporal.urgency_bp" in codes
    assert _metrics(result).get("axes_unavailable", 0) >= 1


def test_with_nothing_present_all_three_are_reported_lost():
    result = run(TradeoffUnit(), prior={})
    metrics, codes = _metrics(result), _codes(result)
    assert metrics["axis_count"] == 0
    assert metrics["axes_unavailable"] == 3
    assert {f"unavailable.{axis}" for axis, _, _ in _AXES} <= codes


def test_a_silent_plugin_with_both_sides_readable_is_NOT_reported_as_unavailable():
    """⛔ THE FALSE-POSITIVE THIS RECEIPT MUST NOT PRODUCE. An axis whose sides were both readable and
    which still said nothing is not an availability problem, and reporting it as one would send a
    reader looking for a unit that ran perfectly well."""
    priors = _all_six()
    # both sides readable, and equal — `_weigh` still emits, so this proves the guard by construction
    result = run(TradeoffUnit(), prior=priors)
    assert _metrics(result)["axis_count"] == 3
    assert "axes_unavailable" not in _metrics(result)


# ── the helper is derived, not retyped ────────────────────────────────────────────────────────

def test_the_absent_source_string_is_derived_from_AXIS_SOURCES():
    """⛔ A formatted literal would be a THIRD copy of a fact that lives in one tuple, and the
    seventh axis somebody adds would leave it behind — which is the defect `AXIS_SOURCES`' own
    comment records this unit already shipping once."""
    import inspect

    src = inspect.getsource(_absent_side)
    assert "_AXIS_BY_KEY[key]" in src
    assert '"core.' not in src.split('"""')[-1], "a unit id is hard-coded in the body"


def test_every_axis_side_key_comes_from_AXIS_SOURCES():
    """⛔ `_AXES` names six keys; `AXIS_SOURCES` declares six. If they drift, an axis is checked for
    availability using a key no plugin reads, or an axis is never checked at all."""
    used = {key for _, first, second in _AXES for key in (first, second)}
    declared = {key for key, _, _ in AXIS_SOURCES}
    assert used == declared, f"used={sorted(used)} declared={sorted(declared)}"


def test_there_is_one_axis_entry_per_plugin():
    assert len(_AXES) == len(TradeoffUnit.plugins)
    assert {axis for axis, _, _ in _AXES} == {p.plugin_id for p in TradeoffUnit.plugins}


def test_a_capability_override_is_named_in_the_receipt_not_the_default():
    """⛔ `_absent_side` resolves through `_config_id`, so a capability that appoints its own
    authority gets ITS unit named. Naming the default would send a reader to a unit this manifest
    never scheduled."""
    priors = _all_six()
    del priors["core.impact"]
    result = run(TradeoffUnit(), prior=priors, config={"benefit_source": "core.resource"})
    codes = _codes(result)
    assert "absent_source.core.resource.impact_bp" in codes, sorted(
        c for c in codes if c.startswith("absent_source"))
    assert "absent_source.core.impact.impact_bp" not in codes


# ── the roster invariants this must not break ─────────────────────────────────────────────────

def test_axes_unavailable_is_declared_in_publishes():
    """Nothing validates output-against-`publishes` at runtime, so an undeclared metric would work
    and would be a lie."""
    assert "axes_unavailable" in TradeoffUnit.publishes


def test_no_other_unit_publishes_axes_unavailable():
    """`tests/test_unit_roster.py` allows exactly one declared publisher per metric name."""
    others = [u().spec.reasoner_id for u in ALL_UNITS
              if "axes_unavailable" in getattr(u, "publishes", ())
              and getattr(u, "unit_id", None) != "core.tradeoff"]
    assert others == [], others


def test_axis_count_still_counts_only_comparisons_that_happened():
    """⛔ THE NUMBER THAT MUST NOT MOVE. Its docstring: *"`axis_count` says how many comparisons were
    possible at all, which is how a reviewer tells 'nothing was contested' apart from 'nothing was
    measurable'."* An absence counted as an axis would corrupt exactly that."""
    priors = _all_six()
    del priors["core.cost"]
    assert _metrics(run(TradeoffUnit(), prior=priors))["axis_count"] == 2

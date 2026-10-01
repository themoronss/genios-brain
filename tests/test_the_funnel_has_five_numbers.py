"""S4.F4.2 · the five writers — and the one number this chain honestly cannot produce.

    pytest tests/test_the_funnel_has_five_numbers.py -q

⛔ THE RULE IS ONE SOURCE PER NUMBER. A collector that RECOMPUTED a count could disagree with the pass
that produced it — two answers to "how many situations formed?" and no way to tell which is the
measurement. `_run_l2_chain` relays each pass's own published number and does no arithmetic, which is
what the tests below check on the source.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.platform.funnel import (CAPABILITY_RESOLVED, CARD_DELIVERED, DECISION_EMITTED,
                                           SIGNALS_DETECTED, SITUATIONS_FORMED, STAGE_OWNERS, STAGES)

pytestmark = pytest.mark.unit


def _chain_source() -> str:
    from genios_engine.api import routes

    return inspect.getsource(routes._run_l2_chain)


# =================================================================================================
# 1 · the chain writes the stages it can
# =================================================================================================
@pytest.mark.parametrize("stage_const", ["SITUATIONS_FORMED", "CAPABILITY_RESOLVED",
                                         "DECISION_EMITTED", "CARD_DELIVERED"])
def test_the_chain_counts_each_stage_it_runs(stage_const):
    assert f"_funnel.{stage_const}" in _chain_source()


def test_all_four_counted_stages_share_one_sweep_id():
    """Five rows keyed on one sweep is what makes the funnel a single-key read. Two ids would make it
    a join nobody can write."""
    source = _chain_source()
    assert source.count("_sweep_id = ") == 1
    assert source.count("sweep_id=_sweep_id") == 1


def test_the_sweep_id_is_derived_not_random():
    """This chain is meant to be replayable, and a random id would be the one field a replay could not
    reproduce."""
    source = _chain_source()
    assert '_stable_id("fsweep"' in source


# =================================================================================================
# 2 · ⛔ the number this chain will NOT invent
# =================================================================================================
def test_signals_detected_is_deliberately_not_written_here():
    """⛔ THE TEST THAT MATTERS MOST. `signals_detected` belongs to `capture`, and nothing in this chain
    holds an honest count of it — `_reread_unread` returns a RECOVERY count (mail captured while L1 was
    off), not qualified signals detected.

    Labelling that number `signals_detected` would put a WRONG number where a missing one belongs, and
    a wrong number is worse than `None`: `None` says nobody looked, and a wrong one says we did."""
    source = _chain_source()
    assert "_funnel.SIGNALS_DETECTED" not in source
    assert "_reread_unread" in source, "the recovery call is still there — only its misuse is absent"


def test_the_omission_is_documented_where_it_happens():
    source = _chain_source()
    assert "DELIBERATELY NOT WRITTEN" in source
    assert "RECOVERY count" in source


def test_an_unmeasured_stage_writes_no_row_at_all():
    """⛔ `None` means nobody looked; `0` means the stage ran and counted nothing. The relay must not
    turn the first into the second."""
    source = _chain_source()
    assert "if n is None:" in source
    assert "return" in source.split("if n is None:")[1][:80]


# =================================================================================================
# 3 · ⛔ the chain relays, it does not compute
# =================================================================================================
def test_no_number_is_derived_by_arithmetic_in_the_chain():
    """⛔ THE ONE-SOURCE-PER-NUMBER RULE, ASSERTED ON THE SOURCE. Every value handed to `_count` must be
    read straight off a pass's result dict."""
    source = _chain_source()
    for call in [line.strip() for line in source.splitlines() if "_count(_funnel." in line]:
        assert "+" not in call and "-" not in call and "sum(" not in call and "len(" not in call, call


def test_every_counted_value_comes_from_a_pass_result_dict():
    source = _chain_source()
    counted = source.count("_count(_funnel.")
    assert counted == 4
    for holder in ("result.get(", "_l3 or {}).get(", "_outcomes.get(", "_cards or {}).get("):
        assert holder in source


def test_each_pass_result_is_captured_rather_than_discarded():
    """`run_l3` and `build_cards_for_org` used to be called for effect and their results dropped —
    the `not_carried` shape. A count cannot be relayed from a value nobody kept."""
    source = _chain_source()
    assert "_l3 = run_l3(" in source
    assert "_cards = build_cards_for_org(" in source


# =================================================================================================
# 4 · the owners map matches where the writing happens
# =================================================================================================
def test_the_stages_this_chain_writes_are_owned_by_packages_it_runs():
    for stage in (SITUATIONS_FORMED, CAPABILITY_RESOLVED, DECISION_EMITTED, CARD_DELIVERED):
        assert STAGE_OWNERS[stage] in {"context", "reason", "deliver"}


def test_the_unwritten_stage_is_owned_by_the_package_this_chain_does_not_measure():
    assert STAGE_OWNERS[SIGNALS_DETECTED] == "capture"


def test_the_funnel_is_still_five_stages_even_though_four_are_wired():
    """⛔ A four-stage funnel would quietly redefine the metric. The fifth stage exists and reads
    `None`, which is the honest state."""
    assert len(STAGES) == 5
    assert SIGNALS_DETECTED in STAGES


# =================================================================================================
# 5 · ⛔ a measurement never breaks the chain
# =================================================================================================
def test_the_counting_goes_through_observe_which_swallows_failure():
    """`observe` runs in its own transaction and returns False rather than raising. A funnel write that
    could break ingestion would be a measurement that costs the tenant their mail."""
    source = _chain_source()
    assert "_funnel.observe(" in source
    assert "_funnel.record(" not in source, "record() raises; the chain must use observe()"

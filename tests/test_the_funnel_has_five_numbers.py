"""S4.F4.2 · the five writers, and where each number is allowed to come from.

⛔ THE HEADER USED TO SAY "and the one number this chain honestly cannot produce". That was true
while the only count the chain held for `signals_detected` was `_reread_unread`'s recovery count. It
stopped being true when `_run_ledger` started keeping `FinalizeOutcome.published`. Corrected rather
than deleted, because a stale status line reads as a status somebody checked.

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
@pytest.mark.parametrize("stage_const", ["SIGNALS_DETECTED", "SITUATIONS_FORMED",
                                         "CAPABILITY_RESOLVED", "DECISION_EMITTED",
                                         "CARD_DELIVERED"])
def test_the_chain_counts_each_stage_it_runs(stage_const):
    assert f"_funnel.{stage_const}" in _chain_source()


def test_all_five_counted_stages_share_one_sweep_id():
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
def test_signals_detected_comes_from_the_publisher_and_nothing_else():
    """⛔ THE TEST THAT MATTERS MOST, AND ITS PREMISE MOVED RATHER THAN WEAKENED.

    This stage used to be left unwritten, because the only count the chain held was
    `_reread_unread`'s — a RECOVERY count (mail captured while L1 was off), not qualified signals
    detected. Labelling THAT `signals_detected` is still the defect; it is now rejected by naming the
    one source that is allowed instead of by forbidding the stage outright.

    A wrong number is worse than `None`: `None` says nobody looked, a wrong one says we did.
    """
    source = _chain_source()
    assert "_funnel.SIGNALS_DETECTED" in source, "the funnel's first number has no writer"
    call = next(line for line in source.splitlines() if "_funnel.SIGNALS_DETECTED" in line
                and "_count(" in line)
    assert "_take_signals_published(" in call, (
        f"signals_detected must be popped from capture's published count; got: {call.strip()}")
    assert "_reread_unread" not in call, (
        "the RECOVERY count is being passed as signals_detected — the exact mislabel this test "
        "has always existed to reject")
    assert "_reread_unread" in source, "the recovery call is still there — only its misuse is absent"


def test_the_recovery_count_is_never_this_number_anywhere_in_the_chain():
    """`_reread_unread`'s return must not be handed to `_count` at all, under any stage name."""
    source = _chain_source()
    for line in source.splitlines():
        if "_count(_funnel." in line:
            assert "_reread_unread" not in line, line.strip()


def test_the_published_count_is_relayed_not_recomputed():
    """⛔ ONE WRITER PER NUMBER. The chain pops a value capture produced; it may not count rows itself.
    A re-derived count can disagree with the publisher that produced it."""
    from genios_engine.api import routes

    taker = inspect.getsource(routes._take_signals_published)
    assert ".pop(" in taker, "the pending count must be removed as it is read, or a pass double-counts"
    assert "select" not in taker.lower(), "signals_detected is relayed from capture, never queried"


def test_a_pass_that_published_nothing_writes_no_row():
    """⛔ `None` (nobody looked) and `0` (ran, counted nothing) are different facts. Capture publishing
    nothing since the last pass must reach `_count` as `None`, which writes no row."""
    from genios_engine.api import routes

    with routes._SIGNALS_PUBLISHED_LOCK:
        routes._SIGNALS_PUBLISHED.pop("no_such_org_for_this_test", None)
    assert routes._take_signals_published("no_such_org_for_this_test") is None


def test_the_publisher_count_accumulates_across_connections_then_empties():
    """A tenant with Gmail AND Calendar finalizes twice before the chain exists — both must land in
    the one pass that follows, and the pending total must then be empty."""
    from genios_engine.api import routes

    org = "funnel_accum_probe"
    try:
        routes._note_signals_published(org, 3)
        routes._note_signals_published(org, 4)
        assert routes._take_signals_published(org) == 7
        assert routes._take_signals_published(org) is None, "a popped count was counted twice"
    finally:
        with routes._SIGNALS_PUBLISHED_LOCK:
            routes._SIGNALS_PUBLISHED.pop(org, None)


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
    assert counted == 5, "all five stages have a writer in this chain"
    # Four are read off a pass's result dict; `signals_detected` is popped from the count capture's
    # publisher produced, which is the same rule — a value another pass computed, relayed verbatim.
    for holder in ("result.get(", "_l3 or {}).get(", "_outcomes.get(", "_cards or {}).get(",
                   "_take_signals_published("):
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


def test_the_first_stage_is_owned_by_capture_and_relayed_from_it():
    """⛔ The chain WRITES this number but does not OWN it. The owner stays `capture`, because the
    value is the publisher's own count travelling through `_run_ledger` — if the owners map ever
    said `api`, the one-writer rule would have been quietly transferred to the relay."""
    assert STAGE_OWNERS[SIGNALS_DETECTED] == "capture"


def test_the_funnel_is_five_stages_and_all_five_are_wired():
    """⛔ A four-stage funnel quietly redefines the metric: "we made 28 cards" and "28 out of 4,000
    signals" stop being distinguishable the moment the denominator has no writer."""
    assert len(STAGES) == 5
    assert SIGNALS_DETECTED in STAGES
    assert _chain_source().count("_count(_funnel.") == len(STAGES)


# =================================================================================================
# 5 · ⛔ a measurement never breaks the chain
# =================================================================================================
def test_the_counting_goes_through_observe_which_swallows_failure():
    """`observe` runs in its own transaction and returns False rather than raising. A funnel write that
    could break ingestion would be a measurement that costs the tenant their mail."""
    source = _chain_source()
    assert "_funnel.observe(" in source
    assert "_funnel.record(" not in source, "record() raises; the chain must use observe()"

r"""L5 STEP-02 · the recall guard — `M13.C2.U04`, rewritten, and the rewrite is the finding.

⛔ `tree.yaml` says *"the scalar publication floor is replaced by lane routing"*. Measured
2026-09-30: **there is no scalar confidence floor in `deliver/`.** `gate.py` is moment + permission,
`bands.py` cuts an urgency band from pack config, and the score gate lives at `reason/runner.py:1133`
where it already writes a `below_gate` receipt that `executive/explain.py` already reads. Replacing
it here would have meant building it first in order to remove it.

What is real is the unit's other half — *"the recall guard proves nothing is lost"* — and nothing
proved it. `route`'s docstring says a sub-floor decision *"does not become SUPPRESS"*. A docstring
does not fail a build.
"""
from __future__ import annotations

import inspect
import pathlib

import pytest

from genios_engine.contracts.reasoning import DecisionOutcome, OutputLane
from genios_engine.deliver.lane_display import TALLY_KEYS, UNROUTED, describe, tally_lane
from genios_engine.deliver.lane_recall import (SILENT_LANES, VISIBLE_LANES,
                                               every_lane_is_visible_or_deliberately_silent,
                                               low_confidence_is_never_silent, recall_verdict)
from genios_engine.reason.output_lane import DEFAULT_DECISION_FLOOR_BP, route

REPO = pathlib.Path(__file__).resolve().parents[2]


# ── the property the router only promised in prose ────────────────────────────────────────────

def test_a_decision_under_the_floor_is_shown_not_silenced():
    """⛔ THE WHOLE UNIT. "Going quiet would say 'over' when the thing is still live." """
    assert low_confidence_is_never_silent() == ()


@pytest.mark.parametrize("floor", [1, 2_500, DEFAULT_DECISION_FLOOR_BP, 9_999])
def test_the_property_holds_at_any_floor_a_tenant_could_set(floor):
    """The floor is a parameter, so a guard that only holds at its default proves less than it
    appears to. A tenant raising the floor must not thereby silence more of its own findings."""
    assert low_confidence_is_never_silent(floor_bp=floor) == ()


@pytest.mark.parametrize("confidence", [0, 1, 5_999])
def test_the_sub_floor_lane_is_monitor_specifically(confidence):
    """Not merely "not suppress" — MONITOR, because the reader has to be told it is live."""
    assert route(outcome=DecisionOutcome.DECISION,
                 confidence_bp=confidence).lane is OutputLane.MONITOR


def test_the_guard_walks_the_real_router_and_not_a_copy_of_its_rules():
    """⛔ A re-implementation of the precedence would pass forever while the thing it describes
    drifted, which is the one failure a guard exists to prevent. AST-free and sufficient: the
    function must import and call `route` itself."""
    src = inspect.getsource(low_confidence_is_never_silent)
    assert "route(" in src
    assert "MONITOR" not in src, (
        "naming the expected lane inside the guard turns it into a restatement of the rule")


def test_the_guard_names_its_counter_examples():
    """A failure that says only "something is wrong" costs the next reader the whole investigation.

    Driven through a stub rather than by breaking the router: the guard's own reporting is the
    thing under test, and proving it by making the product wrong would prove nothing about the day
    the product is wrong for a reason nobody anticipated.
    """
    import genios_engine.deliver.lane_recall as recall

    real = recall.route
    try:
        recall.route = lambda **kw: type("C", (), {"lane": OutputLane.SUPPRESS})()
        bad = recall.low_confidence_is_never_silent(floor_bp=1_000)
    finally:
        recall.route = real
    assert bad, "a guard that cannot fail is not a guard"
    assert all(isinstance(bp, int) and lane == "suppress" for bp, lane in bad)


# ── visibility is decided once, for every lane ────────────────────────────────────────────────

def test_every_lane_is_classified_visible_or_deliberately_silent():
    """A lane in neither set has a visibility nobody decided — and an undecided visibility gets
    decided later by whichever reader happens to look at it first."""
    assert every_lane_is_visible_or_deliberately_silent() == ()


def test_monitor_is_visible_because_that_is_the_entire_point_of_it():
    assert OutputLane.MONITOR.value in VISIBLE_LANES
    assert OutputLane.MONITOR.value not in SILENT_LANES


def test_an_unrouted_card_is_shown_not_withheld():
    """⛔ The card whose signal carried no lane is the MAJORITY case today: the API spend limit has
    refused every model call since 2026-09-25, so no production signal has ever been routed. A
    layer that withheld unrouted cards would deliver nothing at all, silently."""
    assert UNROUTED in VISIBLE_LANES


def test_suppress_is_the_only_silent_lane():
    assert SILENT_LANES == {OutputLane.SUPPRESS.value}


# ── the totals must add up ────────────────────────────────────────────────────────────────────

def test_a_pass_that_counted_every_card_balances():
    counts = {"built": 2, "refreshed": 1, **{k: 0 for k in TALLY_KEYS}}
    counts["cards_output_lane_decision"] = 2
    counts["cards_output_lane_monitor"] = 1
    verdict = recall_verdict(counts)
    assert verdict.balanced
    assert "3" in verdict.explain()


def test_a_refreshed_card_is_not_reported_as_a_loss():
    """⛔ `built` ALONE WOULD HAVE BEEN WRONG. `pipeline` tallies a lane on a refresh too, so
    comparing against `built` would report a loss on every pass that improved an existing card —
    and the fix for a recurring false alarm is always to loosen the check."""
    counts = {"built": 0, "refreshed": 4, **{k: 0 for k in TALLY_KEYS}}
    counts["cards_output_lane_unrouted"] = 4
    assert recall_verdict(counts).balanced


def test_a_card_that_vanished_between_the_two_counters_is_named():
    counts = {"built": 5, "refreshed": 0, **{k: 0 for k in TALLY_KEYS}}
    counts["cards_output_lane_decision"] = 3
    verdict = recall_verdict(counts)
    assert not verdict.balanced
    assert "2" in verdict.explain() and "unaccounted" in verdict.explain()


def test_a_card_counted_twice_reads_differently_from_a_card_lost():
    """Both are defects and they have opposite causes; one message for both teaches nothing."""
    counts = {"built": 1, "refreshed": 0, **{k: 0 for k in TALLY_KEYS}}
    counts["cards_output_lane_decision"] = 3
    assert "counted more than once" in recall_verdict(counts).explain()


def test_a_pass_that_stopped_declaring_a_lane_key_is_a_failure_not_a_zero():
    """`pipeline` zeroes all six on purpose. A key that is absent rather than zero means somebody
    removed a declaration, and the totals would still add up while a whole lane went unmeasured."""
    counts = {"built": 1, "refreshed": 0, "cards_output_lane_decision": 1}
    verdict = recall_verdict(counts)
    assert not verdict.balanced
    assert "cards_output_lane_suppress" in verdict.explain()


def test_the_count_and_the_label_cannot_disagree():
    """⛔ THE BUG THIS SIGNATURE EXISTS TO PREVENT, KEPT AS A TEST. `tally_lane` once took the raw
    column and re-resolved it with no reason to hand; `describe` treats a lane without its reason
    as no route at all, so every routed card was DISPLAYED as `decision` and COUNTED as `unrouted`
    in the same pass. Resolving once and counting the result is the only shape in which the two
    cannot diverge."""
    counts: dict = {}
    for lane in OutputLane:
        seen = describe(lane, "the router's recorded reason")
        tally_lane(counts, lane=seen)
        assert counts[f"cards_output_lane_{seen.lane}"] == 1
    assert "cards_output_lane_unrouted" not in counts


def test_a_lane_nobody_declared_is_counted_as_unrouted_not_dropped():
    """A card counted under a key no reader declared is a card missing from every total."""
    counts: dict = {}
    tally_lane(counts, lane="escalation")
    assert counts == {"cards_output_lane_unrouted": 1}


# ── the receipt ───────────────────────────────────────────────────────────────────────────────

def test_the_l5_receipt_count_is_five_and_they_are_the_measured_five():
    """⛔ L4's OWN DOCSTRING PROMISED THIS GUARD EXISTED HERE, AND IT DID NOT.

    `tests/platform/test_activation_changes_the_pass.py` argues for per-layer receipt counts
    instead of a global total — *"the cheap fix for that is to bump the number, which is how a
    decision gate becomes a rubber stamp"* — and ends: *"L5's own count is guarded in
    `tests/deliver/test_nothing_dies_of_low_confidence.py`."* This file held only PRESENCE filters.
    So the rule was stated and half-unenforced, and the sentence pointing here was stale.

    ⛔ TWO -> FIVE ACROSS 2026-10-01, every one a decision rather than a bump:

        the lane receipt            M13 STEP-01  (ERRORs until `0190` is applied)
        decisions become tracked commitments                        pre-existing
        no delivery attempt is left unsettled long enough to be ambiguous   STEP-06
        no card outlives its own window in a live state                     STEP-10
        a card parked for want of a channel is revived when one appears     STEP-10

    ⛔ AND STEP-10 REJECTED TWO CANDIDATES FOR MEASURED REASONS, which is why this is five and not
    seven: a delivery row with no attempt is structurally 0 while the v2 path writes nothing, and a
    card delivered on an adapter-less channel is impossible because `outbox.py:935` parks it first.
    **A receipt that cannot fail is not a gate.**

    ⛔ SCOPED TO L5, like L4's. A sixth means something was added without a decision.
    """
    from genios_engine.platform import receipts as R

    l5 = [r.claim for r in R.receipts(None) if r.layer == "L5"]
    assert len(l5) == 5, f"L5 receipt count moved: {l5}"
    assert set(l5) == {
        "every delivered card carries a lane, or is labelled unrouted",
        "decisions become tracked commitments",
        "no delivery attempt is left unsettled long enough to be ambiguous",
        "no card outlives its own window in a live state",
        "a card parked for want of a channel is revived when one appears",
    }


# ⛔ A SECOND TEST WAS WRITTEN HERE, RAN, AND WAS DELETED — recorded because the reason is the
# useful part. It asserted that this file pins no GLOBAL receipt total, by scanning its own module
# source for `len(receipts(None))`. **It failed on its own assertion string**: the forbidden text
# appears in the `assert` line that forbids it, and excluding the line by value is the exact
# blunt-grep family that has bitten this programme seventeen times.
#
# It cannot be written in that shape, and it does not need to be. The real guard is the count above,
# which counts L5's receipts ONLY — so a global literal added here would not make it pass, it would
# simply be a second, weaker assertion beside a correct one. L4's docstring already carries the
# argument, and the full suite already caught the one time somebody (me, in STEP-06) added a global
# literal anyway. **A convention is enforced by the guard that implements it, not by a test that
# greps for its own prose.**


def test_a_card_with_no_lane_at_all_has_a_receipt():
    from genios_engine.platform import receipts as R

    # ⛔ THE EXACT CLAIM, AND THIS USED TO BE `if "lane" in r.claim` THEN `found[0]`.
    # Three receipts contain the substring: this one, L6's *"the delivery control **p-lane** has
    # run"* — `lane` inside `plane` — and, from 2026-10-03, L1's *"no warm-**lane** row is parked
    # where nothing can see it"*. The test passed only because this one happened to come first in
    # the list, and it broke the day a receipt was added above it. ⛔ *A grep hands over a sentence
    # without its subject*, and a lookup that takes `[0]` of a substring match is that grep.
    # `tests/platform/test_a_receipt_lookup_is_unambiguous.py` now fails on any such collision.
    found = [r for r in R.receipts(None)
             if r.claim == "every delivered card carries a lane, or is labelled unrouted"]
    assert len(found) == 1, (
        "the lane receipt's claim was reworded; name the new wording here rather than widening "
        "the match back to a substring")
    receipt = found[0]
    assert receipt.layer == "L5"
    assert "output_lane is null" in receipt.sql
    assert receipt.expect(0) and not receipt.expect(1)


def test_the_receipt_treats_unrouted_as_an_answer():
    """⛔ It asks for NULL, not for "not routed". `unrouted` means the layer looked and found
    nothing to honour, which is the answer the card displays — failing on it would demand a routing
    decision that, under the spend limit, no production row can currently have."""
    from genios_engine.platform import receipts as R

    receipt = next(r for r in R.receipts(None)
                   if r.claim == "every delivered card carries a lane, or is labelled unrouted")
    assert "unrouted" not in receipt.sql


# ── the finding itself, written down where it cannot be lost ──────────────────────────────────

def test_there_is_still_no_scalar_publication_floor_in_deliver():
    """⛔ THE CROSS-CHECK'S FINDING, AS A TEST. If somebody later adds a confidence floor to
    `deliver/`, this fails and they have to come and read why `U04` was rewritten — rather than
    silently reintroducing the thing the lane vocabulary replaced."""
    for name in ("gate.py", "bands.py"):
        src = (REPO / "genios_engine/deliver" / name).read_text()
        assert "confidence_bp" not in src, (
            f"{name} now has a confidence floor; M13.C2.U04 was rewritten on the measured fact "
            f"that deliver/ had none — see layer-5-delivery/01-CROSSCHECK.md §4")

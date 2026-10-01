r"""L5 · the recall guard — prove nothing died quietly, rather than claiming it did not.

⛔ THIS UNIT WAS REWRITTEN, AND THE REASON IS RECORDED HERE BECAUSE IT IS A CORRECTION TO THE PLAN.
`tree.yaml`'s `M13.C2.U04` says *"the scalar publication floor is replaced by lane routing."*
Measured on 2026-09-30, **there is no scalar confidence floor in `deliver/`**:

    deliver/gate.py   -> moment + permission. Its only "floor" clamps a deferral's `not_before`
    deliver/bands.py  -> an urgency BAND off the score, from pack config: standard/high/critical
    reason/runner.py:1133 -> `out["below_gate"] += 1`   ⛔ the score gate, one layer up
    executive/explain.py  -> already READS that receipt: "real, but not important enough yet"

So the thing to be replaced is in another layer, it works, and its why-not receipt is already read.
Replacing it here would have meant building it first in order to remove it. What IS real is the
unit's second half — *"the recall guard proves nothing is lost"* — and nothing yet PROVES it.

⛔ THE PROPERTY BEING PROVED, AND WHY A COMMENT IS NOT ENOUGH. `reason/output_lane.route` was
written so a sub-floor decision becomes `MONITOR` and explicitly not `SUPPRESS`; its docstring says
*"It does not become SUPPRESS: going quiet would say 'over' when the thing is still live."* That is
a sentence. A sentence does not fail a build. `low_confidence_is_never_silent` walks the actual
router over the confidence range and returns the counter-examples, so the next person who widens a
condition finds out from a red test rather than from a founder who stopped seeing something.

⛔ AND THE COUNTS MUST SUM. `lane_display.tally_lane` counts every card into one of six keys. If
they do not add up to the cards built, cards went somewhere nobody is looking — which is the exact
failure mode `card_source` guards on the other axis: *"fewer cards must come from merging, never
from dropping."* A total that is never checked is a claim, not a measurement.

PURE. No I/O, no clock, no model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from genios_engine.contracts.reasoning import DecisionOutcome, OutputLane
from genios_engine.deliver.lane_display import TALLY_KEYS, UNROUTED
from genios_engine.reason.output_lane import DEFAULT_DECISION_FLOOR_BP, route

#: The lanes that put something in front of a reader. ⛔ `MONITOR` is one of them: "watch this" is
#: an output, and the whole point of the lane is that a real-but-uncertain finding stays visible.
VISIBLE_LANES: frozenset[str] = frozenset({
    OutputLane.DECISION.value, OutputLane.INVESTIGATION.value,
    OutputLane.CONFLICT.value, OutputLane.MONITOR.value,
    # An unrouted card is SHOWN — see `lane_display`. It is visible and labelled, not withheld.
    UNROUTED,
})

#: The one lane that deliberately shows nothing. Recorded, never hidden — `lane_display` still
#: counts it and `0190` still stores it, because a silence nobody can size is a bug in disguise.
SILENT_LANES: frozenset[str] = frozenset({OutputLane.SUPPRESS.value})


@dataclass(frozen=True, slots=True)
class RecallVerdict:
    """Whether a pass can account for every card it built."""

    cards_built: int
    cards_accounted: int
    #: Which declared tally keys the pass never wrote. ⛔ Empty is the only acceptable value:
    #: `pipeline` zeroes all six on purpose, so a missing key means somebody stopped declaring one.
    undeclared: tuple[str, ...] = ()

    @property
    def balanced(self) -> bool:
        return self.cards_built == self.cards_accounted and not self.undeclared

    def explain(self) -> str:
        if self.balanced:
            return f"all {self.cards_built} cards accounted for by lane"
        if self.undeclared:
            return (f"{self.cards_built} cards built, {self.cards_accounted} counted; lane keys "
                    f"never declared: {', '.join(self.undeclared)}")
        lost = self.cards_built - self.cards_accounted
        direction = "unaccounted for" if lost > 0 else "counted more than once"
        return (f"{self.cards_built} cards built, {self.cards_accounted} counted by lane — "
                f"{abs(lost)} {direction}")


def recall_verdict(counts: Mapping[str, Any]) -> RecallVerdict:
    """Do the per-lane tallies add up to the cards this pass built?

    ⛔ `built` + `refreshed`, NOT `built` ALONE. `pipeline` tallies a lane on every draft it
    composes, and a refresh composes one — an earlier reading of this that compared against `built`
    would have reported a loss on every pass that improved an existing card, and the "fix" for a
    false alarm is always to loosen the check.
    """
    built = int(counts.get("built", 0) or 0) + int(counts.get("refreshed", 0) or 0)
    accounted = sum(int(counts.get(k, 0) or 0) for k in TALLY_KEYS)
    undeclared = tuple(sorted(k for k in TALLY_KEYS if k not in counts))
    return RecallVerdict(cards_built=built, cards_accounted=accounted, undeclared=undeclared)


def low_confidence_is_never_silent(*, floor_bp: int = DEFAULT_DECISION_FLOOR_BP
                                   ) -> tuple[tuple[int, str], ...]:
    """Walk the real router: no decision under the floor may land in a silent lane.

    Returns the counter-examples, so a failure names the confidence and the lane it reached rather
    than only asserting that one exists. An empty tuple is the passing answer.

    ⛔ THE ROUTER ITSELF, NOT A COPY OF ITS RULES. A re-implementation of the precedence here would
    pass forever while the thing it describes drifted — which is what a guard is for.
    """
    bad: list[tuple[int, str]] = []
    for confidence in (0, 1, floor_bp // 2, floor_bp - 1):
        choice = route(outcome=DecisionOutcome.DECISION, confidence_bp=confidence,
                       floor_bp=floor_bp)
        if choice.lane.value in SILENT_LANES:
            bad.append((confidence, choice.lane.value))
    return tuple(bad)


def every_lane_is_visible_or_deliberately_silent() -> tuple[str, ...]:
    """Totality, both directions, over the display vocabulary.

    Every lane a card can carry must be classified as one or the other. A lane in neither set is a
    lane whose visibility nobody decided — and an undecided visibility gets decided later by
    whichever reader happens to look at it first.
    """
    classified = VISIBLE_LANES | SILENT_LANES
    every = {k.removeprefix("cards_output_lane_") for k in TALLY_KEYS}
    return tuple(sorted((every - classified) | (classified - every)))


__all__ = ["SILENT_LANES", "VISIBLE_LANES", "RecallVerdict", "every_lane_is_visible_or_deliberately_silent",
           "low_confidence_is_never_silent", "recall_verdict"]

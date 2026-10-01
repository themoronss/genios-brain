"""S3 · the router — which kind of output a reader gets, decided deterministically.

⛔ A LANE IS A ROUTE, SO NO MODEL PRODUCES IT. `speedrun008/YCW27/00-ARCHITECTURE.md` §4 states the
law: *"If the output is a number, a route or a permission, no model produces it."* A model may word a
card inside a validated vocabulary; it may not decide which lane the card belongs to. This module has
no client, no clock and no database.

⛔ AND IT IS NOT `DecisionOutcome`. See `contracts.reasoning.OutputLane`: the outcome says whether we
reached a decision, the lane says what the reader should receive, and a `decision` outcome routes to
DECISION or MONITOR depending on confidence. Merging them would lose five sixths of a vocabulary the
decision contract explicitly defends.

THE PRECEDENCE, AND WHY IT IS THIS ORDER. Read top to bottom; the first match wins.

  1. ⛔ CONFLICT beats everything, including a confident decision. Two sources or two domains claiming
     opposite things is not resolved by evidence or by confidence — it is resolved by a ruling. A
     confident decision published while the disagreement stands would erase the disagreement by
     omission, which is the principle `situation_publisher.CONFLICT_OPEN` already enforces one layer
     down. A high-confidence decision is the MOST dangerous thing to publish over an open conflict,
     not the least, so confidence cannot be allowed to outrank this.

  2. FAILED and BLOCKED are ours, not the reader's. A crash and a missing permission are not business
     questions, and putting either in front of a founder as one is worse than saying nothing —
     provided the silence is RECORDED, which is exactly what the SUPPRESS lane is. `blocked` goes to
     INVESTIGATION rather than SUPPRESS only when the block is something the reader can act on, which
     the caller states; otherwise it is ours too.

  3. INSUFFICIENT_CONTEXT is the reader's, and naming the gap IS the output. This is the lane that
     turns an internal state into something a person can do something about.

  4. A decision under the confidence floor becomes MONITOR, not DECISION. We have a move and not the
     standing to assert it; asserting anyway is how a card teaches a founder to distrust the product.
     ⛔ It does not become SUPPRESS: going quiet would say "over" when the thing is still live.

  5. DEFER is MONITOR and NO_ACTION is SUPPRESS, and the difference between them is the whole reason
     both lanes exist. "Deliberately waiting" and "deliberately nothing" are different promises.

⛔ EVERY PATH RETURNS A REASON. A card in the wrong lane with no recorded reason is undiagnosable, and
this is the single most consequential new branch in the layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from genios_engine.contracts.reasoning import DecisionOutcome, OutputLane

#: The confidence a decision must carry to be asserted as one. Basis points, integer — like every
#: ratio in this codebase, because a float here would make two runs disagree in the last digit.
#: Below it a decision is real and is shown as something to WATCH rather than something to DO.
DEFAULT_DECISION_FLOOR_BP = 6_000


@dataclass(frozen=True, slots=True)
class LaneChoice:
    """The lane, and why. Both, always — see the module docstring."""

    lane: OutputLane
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError(
                f"a route to {self.lane.value} with no reason is undiagnosable; a card in the wrong "
                f"lane and no record of why is the failure this field exists to prevent")

    def to_semantic_dict(self) -> dict[str, str]:
        return {"lane": self.lane.value, "lane_reason": self.reason}


def route(*, outcome: DecisionOutcome,
          confidence_bp: int,
          conflict_open: bool = False,
          reader_actionable_block: bool = False,
          floor_bp: int = DEFAULT_DECISION_FLOOR_BP) -> LaneChoice:
    """Which lane this decision belongs in. Pure, total, and the first match wins.

    `conflict_open` and `reader_actionable_block` are supplied by the caller rather than inferred from
    the decision: both are facts about the SITUATION, and inferring them from `uncertainty` strings
    would make the route depend on wording that changes whenever somebody improves a sentence.
    """
    if conflict_open:
        # ⛔ FIRST, AND AHEAD OF CONFIDENCE. See the module docstring: a confident decision is the most
        # dangerous thing to publish over an open disagreement, not the least.
        return LaneChoice(OutputLane.CONFLICT,
                          "two sources disagree and the disagreement is open; a ruling settles this, "
                          "not more evidence")

    if outcome is DecisionOutcome.FAILED:
        return LaneChoice(OutputLane.SUPPRESS,
                          "the reasoning failed; that is ours to fix and not a business question, so "
                          "the silence is recorded rather than shown")

    if outcome is DecisionOutcome.BLOCKED:
        if reader_actionable_block:
            return LaneChoice(OutputLane.INVESTIGATION,
                              "something the reader can clear is blocking this, and naming it is the "
                              "output")
        return LaneChoice(OutputLane.SUPPRESS,
                          "blocked by something the reader cannot act on; the silence is recorded")

    if outcome is DecisionOutcome.INSUFFICIENT_CONTEXT:
        return LaneChoice(OutputLane.INVESTIGATION,
                          "we cannot conclude, and naming what is missing is the output")

    if outcome is DecisionOutcome.DEFER:
        return LaneChoice(OutputLane.MONITOR,
                          "deliberately waiting; going quiet would read as over")

    if outcome is DecisionOutcome.NO_ACTION:
        return LaneChoice(OutputLane.SUPPRESS,
                          "deliberately nothing to do; the decision is recorded and not shown")

    # DecisionOutcome.DECISION — the only remaining member, and the only one confidence splits.
    if confidence_bp < floor_bp:
        return LaneChoice(OutputLane.MONITOR,
                          f"a decision at {confidence_bp} bp is under the {floor_bp} bp floor to "
                          f"assert one; shown as something to watch, not something to do")
    return LaneChoice(OutputLane.DECISION,
                      f"a decision at {confidence_bp} bp, at or above the {floor_bp} bp floor")


def reachable_lanes(*, floor_bp: int = DEFAULT_DECISION_FLOOR_BP) -> set[OutputLane]:
    """Every lane `route` can actually return, computed by enumerating its inputs.

    ⛔ THE SECOND HALF OF THE TOTALITY GUARD. The first half is that every input maps to a lane; this
    is that every lane is reachable from some input. A lane nothing can route to is dead vocabulary,
    and dead vocabulary gets "fixed" later by somebody widening a condition until it is reachable —
    at which point the widening, not the design, decides what a reader sees.
    """
    out: set[OutputLane] = set()
    for outcome in DecisionOutcome:
        for conflict in (False, True):
            for block in (False, True):
                for confidence in (0, floor_bp - 1, floor_bp, 10_000):
                    out.add(route(outcome=outcome, confidence_bp=confidence,
                                  conflict_open=conflict, reader_actionable_block=block,
                                  floor_bp=floor_bp).lane)
    return out


__all__ = ["DEFAULT_DECISION_FLOOR_BP", "LaneChoice", "reachable_lanes", "route"]

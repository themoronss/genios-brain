"""L2-3-U0 · what a context slice costs to put in a prompt.

⛔ **L2-5's COST CHECK RESTS ON THIS NUMBER.** The step file says so: *"Before building the
builder: take ten real candidates and compute the slice size in tokens. The cost check for L2-5
depends on this number, and **guessing it would make that check theatre**."*

And the stake, from §2: *"Cost in L2 comes from tokens, not calls, and the difference between a
10,000-token thread and a 900-token slice is the whole bill."*

MEASURED FROM `to_semantic_dict()`, NOT FROM THE DATACLASS. The semantic dict is what the slice
IS — the same bytes that pin its content address — and it deliberately omits `trace_id`,
`evaluation_time` and `graph_version`, which are observation metadata and which no prompt would
carry either. Weighing the dataclass would count three fields no reasoner ever sees.

⛔ **NO TOKENISER, NO MODEL CALL.** A tokeniser is a dependency whose answer changes underneath a
recorded measurement, and this number is going into a plan. The estimate is characters over a
DECLARED divisor, so a reader can check the arithmetic instead of trusting a library — and
`CHARS_PER_TOKEN` is exported for exactly that reason.

PERCENTILES, NEVER A MEAN. A mean hides the one slice that blows the budget, and the tail is the
entire question when the cost is per-token.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

#: Characters per token, for English prose mixed with json punctuation. Declared rather than
#: hidden so the estimate is auditable: multiply back by this to recover the character count.
#: Deliberately conservative — an underestimate of the bill is the expensive direction to be wrong.
CHARS_PER_TOKEN = 4

#: ⛔ **THE BUDGET, AND WHY IT IS A NUMBER RATHER THAN A PARAGRAPH.** Measured 2026-09-24 through
#: the real builder:
#:
#:      facts/obs/neighbors    tokens            facts/obs/neighbors    tokens
#:          3 /  2 /  1          326                 30 / 25 / 20         2509
#:          8 /  6 /  4          714                 60 / 50 / 40         4934
#:         15 / 12 /  9         1279                100 / 80 / 60         8049
#:
#: The step's §2 claims *"the difference between a 10,000-token thread and a 900-token slice is
#: the whole bill."* **That holds for a small node and stops holding for a busy one** — an anchor
#: with a hundred facts produces a slice as expensive as the thread it was meant to replace. The
#: saving comes from the node being small, not from the slice being a slice.
#:
#: 2,000 sits just above the 30-fact shape, which is a well-populated account with its neighbours.
#: It is a LINE TO NOTICE, not a cap: nothing truncates, nothing refuses. A slice over it is
#: reported so L2-5's cost check argues about a number instead of a feeling.
SLICE_TOKEN_BUDGET = 2_000


@dataclass(frozen=True, slots=True)
class SliceWeight:
    """One slice's cost, in the two units anybody asks about."""

    chars: int
    tokens: int


def budget_reason() -> str:
    """Why the line sits where it does, and what would move it."""
    return (f"{SLICE_TOKEN_BUDGET} tokens sits just above a 30-fact anchor with its neighbours "
            f"(2,509 measured), and well below the 100-fact shape (8,049) that costs as much as "
            f"the thread a slice replaces. It REPORTS and never truncates — dropping facts to hit "
            f"a number is how a reasoner concludes from evidence nobody chose to remove. "
            f"ENDS WHEN: L2-5's real prompt cost is known and the line is set from a bill rather "
            f"than from a shape.")


def over_budget(weight: SliceWeight) -> str | None:
    """`None` when it fits. Otherwise the sentence, WITH BOTH NUMBERS — *"too big"* is
    unactionable, *"8049 against a budget of 2000"* is a decision."""
    if weight.tokens <= SLICE_TOKEN_BUDGET:
        return None
    return (f"this slice is {weight.tokens} tokens against a budget of {SLICE_TOKEN_BUDGET} — "
            f"{weight.tokens - SLICE_TOKEN_BUDGET} over")


@dataclass(frozen=True, slots=True)
class WeightReport:
    """A population's cost. `None` where nothing was measured — never zero.

    Zero tokens and nothing measured are different facts, and only the first is a measurement.
    L2-0 drew the same line between a refusal that scored nothing and one that was never scored.
    """

    count: int
    p50: int | None
    p90: int | None
    max: int | None
    #: How many broke `SLICE_TOKEN_BUDGET`. One oversized slice is a curiosity; a tail of them is
    #: the bill, and the tail is what a mean would have hidden.
    over_budget: int = 0

    @property
    def sentence(self) -> str:
        if not self.count:
            return ("nothing was measured — no slice was supplied, which is not the same as a "
                    "slice that weighs nothing")
        return (f"{self.count} slices · p50 {self.p50} tokens · p90 {self.p90} · max {self.max} "
                f"· {self.over_budget} of {self.count} over the {SLICE_TOKEN_BUDGET} budget")


def _canonical(value: Any) -> Any:
    """json cannot serialise a datetime or a frozen mapping; the weigher must not care."""
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def weigh(context_slice: Any) -> SliceWeight:
    """One slice, by its content bytes."""
    payload = json.dumps(_canonical(context_slice.to_semantic_dict()),
                         separators=(",", ":"), sort_keys=True)
    return SliceWeight(chars=len(payload), tokens=len(payload) // CHARS_PER_TOKEN)


def _percentile(ordered: Sequence[int], fraction: float) -> int:
    """Nearest-rank, integers only — V-7's no-floats rule applies to a number in a plan too."""
    rank = max(1, min(len(ordered), int(fraction * len(ordered) + 0.5)))
    return ordered[rank - 1]


def weigh_all(slices: Iterable[Any]) -> WeightReport:
    """A population, reported at the tail."""
    tokens = sorted(weigh(s).tokens for s in slices)
    if not tokens:
        return WeightReport(count=0, p50=None, p90=None, max=None)
    return WeightReport(count=len(tokens), p50=_percentile(tokens, 0.50),
                        p90=_percentile(tokens, 0.90), max=tokens[-1],
                        over_budget=sum(1 for t in tokens if t > SLICE_TOKEN_BUDGET))


__all__ = ["CHARS_PER_TOKEN", "SLICE_TOKEN_BUDGET", "SliceWeight", "WeightReport",
           "budget_reason", "over_budget", "weigh", "weigh_all"]

"""L1.6.x-U0 · HOW MANY REFUSALS WOULD BE WORTH A SECOND LOOK — the measurement, and only that.

Step 10 proposes a fourth publication outcome, `REVIEW`, for a signal that is *"low confidence but
high value"*. Its own §5 makes the measurement the first unit and gives it the power to cancel the
rest:

> *"MEASURE FIRST. Replay the pilot's 68 floor-refused signals and count how many would become
> REVIEW. **68 or 0 both mean the thresholds are wrong** — and 0 means the step is not needed yet."*

**This module is that measurement. It routes nothing, stores nothing and changes no outcome.**
`PublicationOutcome` stays closed at three until a real count says otherwise — its own docstring
says *"a fourth outcome invented at a call site would be an emit nobody reviewed"*, and a fourth
outcome invented before its measurement is the same mistake one step earlier.

⛔ **WHY THE RULE IS NOT "LOW CONFIDENCE", although the step says it is.** `finalize.py` fixes the
order and it is load-bearing:

    conflicts  →  QUALIFY  →  lifecycle  →  PUBLISH

ALG-13 composes confidence inside `publisher.py`, at **publish** — after qualify. So at the moment
the floor refuses a signal **its confidence has not been computed**, and `qualification_drops` has
no confidence column because there is nothing yet to put in one. Routing on it would require moving
composition ahead of qualification: a pipeline reordering with real risk, for a step whose own
measurement might cancel it.

**What the drop point CAN see is `importance_bp`, `floor_bp` and `components` — and step 8 put
`achievable_ceiling_bp` in exactly that reach.** That is the better rule regardless: on a cold-start
tenant *"high value"* cannot mean a high absolute score, because step 8 measured the whole tenant
topping out at 4,640 of 10,000 with the money term unearnable. A signal at 2,400 against a **ceiling
of 3,000** is near-maximal for what it could ever have earned, and an absolute floor of 2,500
refuses it.

That population has a name already: step 4 found `relationship_change` **published 4, dropped 54,
band 880–1560** — *a type whose ceiling sits below the floor*. This module counts it.

PURE: no clock, no I/O, no model. It is handed rows and returns a report, so the same code answers
a fixture here and a tenant in production.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

#: How close to its OWN ceiling a refused signal must sit to be worth a person's attention, in
#: basis points of that ceiling. 8000 = "it earned 80% of everything it could ever have earned".
#:
#: A STARTING POINT FOR THE MEASUREMENT, NOT A SHIPPED THRESHOLD. The whole point of U0 is that a
#: number chosen at a desk is worthless: if this routes every refusal it has renamed the drop
#: ledger, and if it routes none the step waits. `measure_review_population` reports both as
#: `thresholds_are_wrong` rather than as a result. When a real count exists, the threshold becomes
#: a per-tenant row with an owner (E3) — never this constant.
NEAR_CEILING_BP = 8000

#: Full scale, for the share arithmetic. Integer basis points throughout (V-7).
BP_FULL = 10_000


def _ceiling_of(row: Mapping[str, object]) -> int | None:
    """The row's achievable ceiling, or None when it predates step 8.

    **None is never coerced to a full scale**, and that is the most consequential line in this
    module. Every refusal written before `achievable_ceiling_bp` existed has no ceiling; reading
    that as 10000 would make each one look far below its limit and report a confident **zero**
    candidates — a measurement that concludes "the step is not needed" because it could not see.
    """
    value = row.get("achievable_ceiling_bp")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def is_review_candidate(row: Mapping[str, object],
                        *, near_ceiling_bp: int = NEAR_CEILING_BP) -> bool:
    """Would this refused signal be worth putting in front of a person?

    Three conditions, and each one excludes a population that would otherwise turn a review queue
    into a second inbox (E2):

    * **it was actually refused** — a signal that cleared its floor is not up for review, and
      counting it would inflate the population with rows already published;
    * **its ceiling is known** — see `_ceiling_of`;
    * **it sits near that ceiling** — not near the FLOOR. 400 of an achievable 10000 is a weak
      signal on a scale it could have used, and nothing about it says a person should look.
    """
    importance = row.get("importance_bp")
    floor = row.get("floor_bp")
    if not isinstance(importance, int) or not isinstance(floor, int):
        return False
    if importance >= floor:
        return False                                  # it emitted; not a refusal
    ceiling = _ceiling_of(row)
    if ceiling is None:
        return False
    return importance * BP_FULL // ceiling >= near_ceiling_bp


@dataclass(frozen=True, slots=True)
class ReviewPopulation:
    """What U0 found, in the shape `STATUS.md` needs.

    `unassessable` is carried beside the totals rather than folded into them, because a shrinking
    denominator is how a measurement lies. If most of the corpus predates step 8, the honest
    headline is *"we could not assess 900 of 1000"* and not *"3% qualify"*.
    """

    refusals: int = 0
    candidates: int = 0
    #: Rows with no `achievable_ceiling_bp` — written before step 8 and unreadable by this rule.
    unassessable: int = 0
    #: signal_type -> candidates of that type. See `thresholds_are_wrong` for why it matters.
    by_type: dict[str, int] = field(default_factory=dict)

    @property
    def share_bp(self) -> int:
        """Candidates per 10,000 refusals. Truncated, never overstated; 0 refusals reports 0."""
        if self.refusals <= 0:
            return 0
        return self.candidates * BP_FULL // self.refusals

    @property
    def thresholds_are_wrong(self) -> bool:
        """**THE STEP'S OWN GATE**, and it fails in BOTH directions on purpose.

        §5: *"68 or 0 both mean the thresholds are wrong — and 0 means the step is not needed
        yet."* A rule that routes EVERY refusal has not discriminated, it has renamed the drop
        ledger; a rule that routes NONE has found no population. Neither is a result, and a report
        that let either be read as one would hand step 10 a green light it did not earn.

        An EMPTY corpus is not a threshold failure — it is nothing to measure, and saying
        otherwise would report a finding about the thresholds when the finding is about the data.
        """
        if self.refusals <= 0:
            return False
        return self.candidates in (0, self.refusals)


def measure_review_population(rows: Sequence[Mapping[str, object]],
                              *, near_ceiling_bp: int = NEAR_CEILING_BP) -> ReviewPopulation:
    """Count the refusals that would be worth a second look.

    `rows` are `qualification_drops` records — the same shape whether they come from a fixture or
    from the table, which is the point of keeping this pure.

    **The per-type breakdown is what makes the answer actionable rather than merely true.** If one
    type dominates, the fix is not a review queue at all: it is that type's floor, which is step
    8's deferred 8-U3, and step 4 already found `relationship_change` sitting exactly there —
    published 4, dropped 54, its whole band below the bar. A total with no breakdown cannot tell a
    systemic floor problem from a scattered handful of genuinely borderline signals.
    """
    candidates = 0
    unassessable = 0
    by_type: Counter[str] = Counter()

    for row in rows:
        if _ceiling_of(row) is None:
            unassessable += 1
        if is_review_candidate(row, near_ceiling_bp=near_ceiling_bp):
            candidates += 1
            by_type[str(row.get("signal_type") or "unknown")] += 1

    return ReviewPopulation(refusals=len(rows), candidates=candidates,
                            unassessable=unassessable, by_type=dict(by_type))


__all__ = ["BP_FULL", "NEAR_CEILING_BP", "ReviewPopulation", "is_review_candidate",
           "measure_review_population"]

"""Step 10 · 10-U0 — the measurement that decides whether the rest of this step should exist.

    pytest tests/capture/esqe/test_a_refusal_can_be_worth_a_second_look.py -q

**THE STEP'S OWN GATE, in its own words:** *"MEASURE FIRST. Replay the pilot's 68 floor-refused
signals and count how many would become REVIEW. **68 or 0 both mean the thresholds are wrong** —
and 0 means the step is not needed yet."* §8's first criterion is *"U0's measured count is in
`STATUS.md` BEFORE any code was written."*

So this file builds **U0 and only U0**. U1–U4 are deliberately not built, for three reasons that
each stand alone:

  1. **The step says the measurement can cancel them.** Building the outcome, the queue and the
     drain before the count exists is the mistake this whole plan is written against.
  2. **E1 forbids a partial ship:** *"a REVIEW with no drain is a slower drop — the queue and its
     drain ship in the same change."* So U1–U4 are one unit or none.
  3. **The routing rule as written is unbuildable** — §2 below.

⛔ **THE PREMISE CORRECTION: THE ROUTING RULE READS A VALUE THAT DOES NOT EXIST YET.**

10-U2 says *"low confidence + high importance → REVIEW"*. `finalize.py` states the pipeline order
and it is load-bearing:

    conflicts  →  QUALIFY  →  lifecycle  →  PUBLISH

ALG-13 composes confidence inside `publisher.py`, which runs at **publish** — *after* qualify. So
**at the moment the floor refuses a signal, its confidence has not been computed.** `qualification_
drops` has no confidence column because there is no confidence to put in one:

    org_id · drop_id · signal_id · event_id · signal_type · predicate · subject_key
    importance_bp · importance_version · floor_bp · components · payload_ref

Two ways out, and only one is cheap: move composition before qualification (a pipeline reordering
with real risk, for a step whose own measurement might cancel it), or **route on what the drop
point CAN see.** It can see `importance_bp`, `floor_bp` and `components` — and step 8 put
`achievable_ceiling_bp` in exactly that reach.

**That turns out to be the better rule anyway.** *"High value"* on a cold-start tenant cannot mean
"high absolute score": step 8 measured the whole tenant topping out at 4,640 of 10,000 because the
money term was unearnable. A signal at 2,400 against a **ceiling of 3,000** is near-maximal for what
it could ever have earned, and an absolute floor of 2,500 refuses it. That is step 4's
`relationship_change` finding exactly — *a type whose ceiling sits below the floor* — and it is
precisely the population *"low confidence but high value"* was reaching for.

**This file measures that population. It does not act on it.**
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# The measurement — pure, so it can be pointed at a fixture today and a tenant tomorrow
# =============================================================================================
def _drop(*, importance_bp: int, floor_bp: int = 2500, ceiling_bp: int = 10_000,
          signal_type: str = "relationship_change") -> dict:
    """One `qualification_drops` row, in the shape the ledger actually stores."""
    return {"signal_type": signal_type, "importance_bp": importance_bp, "floor_bp": floor_bp,
            "achievable_ceiling_bp": ceiling_bp}


def test_the_measurement_exists_and_is_pure():
    """U0 is a FUNCTION, not a script, so the same code answers the fixture here and the tenant
    Harsh runs it against. A measurement that only exists as SQL in a runbook is a measurement
    nobody can test, and this step's entire gate rests on its answer."""
    import inspect

    from genios_engine.capture.esqe import review_candidates

    source = inspect.getsource(review_candidates)
    for forbidden in ("datetime.now", "utcnow", "sqlalchemy", "text(", "llm"):
        assert forbidden not in source, f"`{forbidden}` makes U0 unrunnable against a fixture"


def test_a_refusal_near_its_own_ceiling_is_a_review_candidate():
    """THE POPULATION THE STEP IS ABOUT, expressed in what the drop point can actually see.

    2,400 of an achievable 3,000 is **80% of everything this signal could ever have earned**, and
    an absolute floor of 2,500 refuses it. That is not a weak signal; it is a signal whose type
    cannot reach the bar — step 4's `relationship_change` finding, measured.
    """
    from genios_engine.capture.esqe.review_candidates import is_review_candidate

    assert is_review_candidate(_drop(importance_bp=2400, floor_bp=2500, ceiling_bp=3000)) is True


def test_a_refusal_far_below_its_own_ceiling_is_not():
    """SENSITIVITY, and the difference between a review queue and a second inbox (E2).

    400 of an achievable 10,000 is a weak signal on a scale it could have used. Nothing about it
    says a person should look, and routing it would make REVIEW the dumping ground §9 forbids by
    name.
    """
    from genios_engine.capture.esqe.review_candidates import is_review_candidate

    assert is_review_candidate(_drop(importance_bp=400, floor_bp=2500, ceiling_bp=10_000)) is False


def test_a_signal_that_cleared_its_floor_is_never_a_candidate():
    """REVIEW is a fourth outcome for REFUSALS. A signal that emitted is not up for review, and a
    measurement that counted it would inflate the population with signals already published."""
    from genios_engine.capture.esqe.review_candidates import is_review_candidate

    assert is_review_candidate(_drop(importance_bp=9000, floor_bp=2500, ceiling_bp=10_000)) is False


def test_a_missing_ceiling_is_not_treated_as_a_full_scale():
    """EVERY ROW WRITTEN BEFORE STEP 8 HAS NO CEILING, and this is where that matters most.

    Defaulting a missing ceiling to 10,000 would make every historical refusal look far below its
    ceiling and report **zero** candidates — a measurement that says "the step is not needed"
    because it could not see. `None` is excluded from the count and reported separately, so the
    answer is "we cannot tell for N rows" rather than a confident nothing.
    """
    from genios_engine.capture.esqe.review_candidates import is_review_candidate

    blind = {"signal_type": "x", "importance_bp": 2400, "floor_bp": 2500,
             "achievable_ceiling_bp": None}
    assert is_review_candidate(blind) is False


# =============================================================================================
# The report — and the two answers that both mean "the thresholds are wrong"
# =============================================================================================
def test_the_report_counts_candidates_against_the_refusals_it_saw():
    """The shape U0 has to produce for `STATUS.md`: a numerator, a denominator, and the share."""
    from genios_engine.capture.esqe.review_candidates import measure_review_population

    rows = [_drop(importance_bp=2400, ceiling_bp=3000)] * 3 + [_drop(importance_bp=200)] * 7
    report = measure_review_population(rows)

    assert (report.refusals, report.candidates) == (10, 3)
    assert report.share_bp == 3000


def test_all_or_nothing_both_report_that_the_thresholds_are_wrong():
    """**THE STEP'S OWN GATE, as an assertion.** §5: *"68 or 0 both mean the thresholds are
    wrong — and 0 means the step is not needed yet."*

    A rule that routes EVERY refusal has not discriminated; it has renamed the drop ledger. A rule
    that routes NONE has found no population, and the honest conclusion is that the step waits.
    Both are failures of the THRESHOLD, and a report that did not say so would let either be read
    as a result.
    """
    from genios_engine.capture.esqe.review_candidates import measure_review_population

    everything = measure_review_population([_drop(importance_bp=2400, ceiling_bp=3000)] * 10)
    nothing = measure_review_population([_drop(importance_bp=100)] * 10)
    some = measure_review_population([_drop(importance_bp=2400, ceiling_bp=3000)]
                                     + [_drop(importance_bp=100)] * 9)

    assert everything.thresholds_are_wrong is True, "routing everything is not discrimination"
    assert nothing.thresholds_are_wrong is True, "routing nothing means the step waits"
    assert some.thresholds_are_wrong is False


def test_rows_with_no_ceiling_are_reported_rather_than_silently_excluded():
    """A denominator that quietly shrinks is how a measurement lies. If most of the corpus predates
    step 8, the honest headline is *"we could not assess 900 of 1000"* and not *"3% qualify"*."""
    from genios_engine.capture.esqe.review_candidates import measure_review_population

    rows = [_drop(importance_bp=2400, ceiling_bp=3000)] + [
        {"signal_type": "x", "importance_bp": 2400, "floor_bp": 2500,
         "achievable_ceiling_bp": None}] * 9
    report = measure_review_population(rows)

    assert report.unassessable == 9
    assert report.refusals == 10, "the denominator hid the rows it could not read"


def test_an_empty_corpus_is_absent_rather_than_zero_percent():
    """Zero refusals is not "zero candidates" — it is "nothing to measure". Reporting 0% would
    read as a finding about the thresholds when it is a finding about the corpus."""
    from genios_engine.capture.esqe.review_candidates import measure_review_population

    report = measure_review_population([])

    assert (report.refusals, report.candidates, report.share_bp) == (0, 0, 0)
    assert report.thresholds_are_wrong is False, (
        "an empty corpus was reported as a threshold failure")


def test_the_per_type_breakdown_names_the_types_a_floor_cannot_reach():
    """The number that makes the finding ACTIONABLE rather than merely true.

    Step 4 established that `relationship_change`'s ceiling sits below the floor. If one type
    dominates this population, the answer is not a review queue at all — it is that type's floor,
    which is step 8's deferred 8-U3. A total with no breakdown cannot tell those apart.
    """
    from genios_engine.capture.esqe.review_candidates import measure_review_population

    rows = ([_drop(importance_bp=2400, ceiling_bp=3000, signal_type="relationship_change")] * 4
            + [_drop(importance_bp=2400, ceiling_bp=3000, signal_type="anomaly")])
    report = measure_review_population(rows)

    assert report.by_type == {"relationship_change": 4, "anomaly": 1}


# =============================================================================================
# What this step may NOT do while its measurement is unrun
# =============================================================================================
def test_the_publication_outcome_is_still_closed_at_three():
    """§9: *"Do not add the outcome at a call site — the contract forbids it in writing."* And
    §8: the measured count lands in `STATUS.md` BEFORE any code.

    The contract's own words: *"closed — a fourth outcome invented at a call site would be an emit
    nobody reviewed."* Until U0 has a number, adding `REVIEW` would be exactly that.
    """
    from genios_engine.contracts.publication import PublicationOutcome

    assert {o.value for o in PublicationOutcome} == {"emit", "park", "reject"}


def test_the_floor_overrides_are_untouched():
    """The three 'travel anyway' rules the step names are now FIVE — `availability_change` and
    `delivery_failure` (step 2) joined them. Uncertain ≠ drop is already partly law, and this step
    may not disturb it while measuring."""
    from genios_engine.capture.esqe.qualification import QualificationReason

    reasons = {r.value for r in QualificationReason}
    assert {"conflict_override", "internal_kind_override", "availability_override",
            "delivery_failure_override"} <= reasons
    # `unscored` is the fifth "travel anyway" rule and is not spelled as an override — doc 06's
    # own words, *"never block on a missing score"*. The step counted three; there are five.
    assert "unscored" in reasons


def test_the_extraction_cache_fingerprint_is_untouched():
    """Qualification is post-extraction and deterministic — no prompt, no vocabulary, no cost."""
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"

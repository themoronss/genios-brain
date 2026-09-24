"""Step 8 · the whole tenant topped out at 4,640 of 10,000, and a third of events were never judged.

    pytest tests/capture/esqe/test_the_ceiling_and_the_allocator.py -q

TWO DEFECTS, both at the top of the scale, and NEITHER IS A FORMULA BUG. §9 of this step forbids
touching ALG-17's weights, its five terms or the sum-to-10000 check, and nothing here does.

**a · EVERY SCORE IS UNDER HALF THE SCALE.** 395 signals, none above 4,700. Arithmetically
unavoidable: `money 3000 · deadline 2500 · criticality 2000 · authority 1500 · signal_type 1000`,
and this inbox carries almost no amounts — so the money term, **30% of the scale**, contributes ~0
for nearly every signal. On a three-week-old graph `entity_criticality` sits at `first_seen` for
nearly every counterparty too. The effective range was roughly 0–5,000 and the tenant used all of
it. **4,640 is not a mediocre score. It is close to the maximum this tenant could earn**, and
nothing anywhere says so.

**b · A THIRD OF EVENTS WERE NEVER JUDGED.** `ambiguous_over_budget` — 69 events, 31%. Above
`AMBIGUOUS_BUDGET_BP` the unit alerts instead of spending, and on a young tenant almost every sender
is unknown, so the guard trips and the component that could have said *"this is a mass programme
announcement"* never runs. The doctrine is right — a high ambiguous share IS a graph-coverage
problem — but its consequence is that the judgement is all-or-nothing when the correct behaviour on
a constrained budget is to spend it where it changes the outcome.

THE PREMISE CHECK CORRECTED 8-U1, checked 2026-09-24 before anything was built. It asks to *"record
when the money term was structurally unearnable"*. **`ImportanceFlag` already does, with ten members
and the plan's own argument in its docstring:** *"a zero term has several causes and they are not
equivalent... Reading them apart from the integer alone is impossible, which is how a missing-data
bug hides inside a plausible score for a year."*

**They are computed on every score and NOTHING READS THEM.** Not `baseline_estimated` — none of the
ten. So 8-U1 is not "record it", it is **"make what is already recorded readable"**, and that is
exactly what the ceiling is: the flags say which terms could not be earned, so the ceiling is the
scale minus their weights. One derivation, no new inputs, no formula change.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# THE GUARD — §9's rule, first, because everything else in this file is near the formula
# =============================================================================================
def test_the_formula_its_weights_and_its_total_are_untouched():
    """T1. The one thing this step may not do.

    `IMPORTANCE_WEIGHTS_V1` is `money 3000 · deadline 2500 · criticality 2000 · authority 1500 ·
    signal_type 1000`, summing to 10000, and the module raises at import if it ever does not. This
    row is the version of that check which fails in a DIFF rather than at startup, so a weight
    edit inside this step is visible to a reviewer instead of merely surviving.
    """
    from genios_engine.capture.esqe.importance import BP_MAX, IMPORTANCE_WEIGHTS_V1 as W

    assert (W.money, W.deadline, W.criticality, W.authority, W.signal_type) == (
        3000, 2500, 2000, 1500, 1000)
    assert W.total == BP_MAX == 10_000


# =============================================================================================
# 8-U1′ + 8-U2 · the ceiling — derived from flags that already exist
# =============================================================================================
def test_a_score_publishes_the_ceiling_it_could_have_reached():
    """4,640 of 10,000 reads as mediocre. 4,640 of an achievable 5,000 reads as near-maximal.

    Same integer, opposite conclusion, and Layer 4 ranks on it.
    """
    from genios_engine.capture.esqe.importance import achievable_ceiling_bp

    assert callable(achievable_ceiling_bp)


def test_the_ceiling_subtracts_exactly_the_terms_that_could_not_be_earned():
    """THE DERIVATION, and it uses only what is already computed.

    `NO_MONEY_BASELINE` means the org has no priced history, so term 1 (3000 bp) was unearnable —
    not scored low, UNEARNABLE. `NO_ENTITY` means term 4 (1500) had nothing to rank. Subtracting
    their weights is the whole of it: no new inputs, no model, no change to the score itself.
    """
    from genios_engine.capture.esqe.importance import ImportanceFlag, achievable_ceiling_bp

    assert achievable_ceiling_bp(()) == 10_000
    assert achievable_ceiling_bp((ImportanceFlag.NO_MONEY_BASELINE,)) == 7_000
    assert achievable_ceiling_bp((ImportanceFlag.NO_MONEY_BASELINE,
                                  ImportanceFlag.NO_ENTITY)) == 5_500


def test_no_money_on_the_signal_is_not_an_unearnable_term():
    """THE DISTINCTION THE WHOLE UNIT RESTS ON, and getting it backwards makes the ceiling a lie.

    `NO_MONEY` means *this signal names no amount* — `ImportanceFlag`'s own words: *"term 1 is 0
    and that is the right answer."* The signal COULD have carried an amount and did not, so the
    scale was available and this one did not use it.

    `NO_MONEY_BASELINE` means *the org has no priced history at all*, so no signal in this tenant
    could earn the term however much money it named. Only the second lowers a ceiling.

    Treating the first as unearnable would raise every ceiling on every unpriced message and make
    a tenant with no amounts look like a tenant scoring perfectly.
    """
    from genios_engine.capture.esqe.importance import ImportanceFlag, achievable_ceiling_bp

    assert achievable_ceiling_bp((ImportanceFlag.NO_MONEY,)) == 10_000
    assert achievable_ceiling_bp((ImportanceFlag.NO_DEADLINE,)) == 10_000


def test_a_ceiling_never_goes_below_the_score_it_describes():
    """A score above its own ceiling is arithmetic nobody can defend, and it would arrive at
    Layer 4 as a ratio over 100%. This is the row that catches a flag added to the unearnable set
    by mistake."""
    from genios_engine.capture.esqe.importance import ImportanceFlag, achievable_ceiling_bp

    every = tuple(ImportanceFlag)
    assert 0 < achievable_ceiling_bp(every) <= 10_000


def test_the_ceiling_reaches_the_score_object():
    """A derivation nothing carries is a derivation Layer 4 never sees — the same loss step 3 spent
    its whole length closing at the L1→L2 seam."""
    from genios_engine.capture.esqe.importance import ImportanceScore

    assert "achievable_ceiling_bp" in ImportanceScore.__dataclass_fields__


def test_the_cold_start_tenant_is_the_case_this_exists_for():
    """T3, end to end over the real scorer: a tenant with no priced history must come out with a
    ceiling BELOW the full scale, and its score must be readable against that rather than against
    10,000.

    This is the whole of defect (a). The tenant was not scoring badly; it was scoring against a
    scale 30% of which it could not reach, and `baseline_estimated` had said so on every row for
    a year with nothing reading it.
    """
    from genios_engine.capture.esqe.importance import ImportanceFlag

    cold = (ImportanceFlag.NO_MONEY_BASELINE, ImportanceFlag.BASELINE_ESTIMATED)
    from genios_engine.capture.esqe.importance import achievable_ceiling_bp

    assert achievable_ceiling_bp(cold) < 10_000, (
        "a tenant with no priced history still reports the full scale as achievable, so every "
        "score it produces reads as worse than it is")


# =============================================================================================
# 8-U5 · an unjudged event is not a relevant one
# =============================================================================================
def test_unjudged_for_budget_is_its_own_provenance_value():
    """E3. Today an event the budget guard skipped and an event judged RELEVANT both arrive as
    "kept", so 31% of the corpus is indistinguishable from the part we actually assessed.

    That is the same class as the drop ledger's founding argument: an absence with no record is
    indistinguishable from a decision.
    """
    from genios_engine.capture.esqe.relevance import UNJUDGED_FOR_BUDGET

    assert isinstance(UNJUDGED_FOR_BUDGET, str) and UNJUDGED_FOR_BUDGET


def test_an_unjudged_event_still_reaches_layer_two():
    """E6 and the never-filter principle: not judging an event is a statement about OUR budget,
    never about the event. It fails OPEN, exactly as a transport failure does."""
    from genios_engine.capture.esqe.relevance import UNJUDGED_FOR_BUDGET, is_kept

    assert is_kept(UNJUDGED_FOR_BUDGET) is True


# =============================================================================================
# 8-U4 · the allocator — spend the budget, do not switch it off
# =============================================================================================
def test_the_allocator_spends_the_budget_top_down_rather_than_refusing_to_spend():
    """THE LOAD-BEARING ROW. §9: *"Do not raise the budget to make the problem go away —
    ALLOCATE it."*

    The guard is currently all-or-nothing: above the ambiguous share it alerts and judges NOTHING.
    An allocator with the same budget judges the head of the ordering and marks the rest
    `unjudged_for_budget`, which is strictly more information for the same spend.
    """
    from genios_engine.capture.esqe.relevance import allocate_budget

    ranked = [f"e{i}" for i in range(10)]
    judged, deferred = allocate_budget(ranked, budget=3)

    assert judged == ("e0", "e1", "e2")
    assert deferred == tuple(ranked[3:])


def test_the_allocator_spends_nothing_it_does_not_have_and_everything_it_does():
    """Two boundaries in one row: a zero budget judges nothing and defers everything; a budget
    larger than the queue judges all of it and defers nothing — never an index error, never a
    negative slice."""
    from genios_engine.capture.esqe.relevance import allocate_budget

    assert allocate_budget(["a", "b"], budget=0) == ((), ("a", "b"))
    assert allocate_budget(["a", "b"], budget=99) == (("a", "b"), ())
    assert allocate_budget([], budget=5) == ((), ())


def test_a_negative_budget_is_treated_as_no_budget_rather_than_reversing_the_slice():
    """`ranked[:-1]` on a negative budget would judge everything EXCEPT the last item — silently
    inverting the unit's purpose while looking like it worked."""
    from genios_engine.capture.esqe.relevance import allocate_budget

    assert allocate_budget(["a", "b", "c"], budget=-1) == ((), ("a", "b", "c"))


def test_the_ordering_is_the_callers_and_the_allocator_never_reorders():
    """E2. Importance is computed AFTER relevance, so the allocator cannot sort by the thing it
    would most like to sort by. It therefore takes the order it is given and **says nothing about
    quality** — the caller owns the proxy and must name it.

    An allocator that sorted by a proxy of its own would bury that choice where no report could
    see it.
    """
    from genios_engine.capture.esqe.relevance import allocate_budget

    judged, _ = allocate_budget(["z", "a", "m"], budget=2)
    assert judged == ("z", "a"), "the allocator re-sorted; the caller's ordering is the contract"


# =============================================================================================
# The rules this step may not break
# =============================================================================================
def test_no_model_can_produce_or_adjust_an_importance_score():
    """§9, and the property mutation testing already protects: `return 5000` inside the scorer
    turns 16 tests red. This is the import-graph half — a scorer that could REACH a model client
    is one edit away from asking it."""
    import inspect

    from genios_engine.capture.esqe import importance

    source = inspect.getsource(importance)
    for forbidden in ("llm", "LLMClient", "openai", "anthropic"):
        assert forbidden not in source.replace("no LLM", "").replace("No LLM", ""), (
            f"`{forbidden}` is reachable from the scorer")


def test_the_extraction_cache_fingerprint_is_untouched():
    """Step 8 is entirely post-extraction — importance, qualification and the relevance allocator
    all run on values the model already produced. Nothing here may change what LLM-2 is asked, so
    nothing here may cost a re-extraction.

    Checked before building, as step 4's lesson requires, and pinned here so a later edit cannot
    quietly undo it.
    """
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"


# =============================================================================================
# BOTH UNITS REACH THE REAL PATH — the check that caught the same defect in steps 5, 6 and 7
# =============================================================================================
def test_the_ceiling_is_populated_by_the_real_scorer():
    """THREE STEPS RUNNING the same defect: a field added, tests green, and nothing filling it.
    Step 5's `claimed_total` was `getattr` against a field no contract had; step 6's
    `domain_tagged` was never incremented.

    `achievable_ceiling_bp` defaults to `BP_MAX`, so a scorer that did not set it would report the
    full scale on every score — which is precisely the defect this unit exists to fix, shipped
    with a green suite. Driven through `score_importance` itself.
    """
    import inspect

    from genios_engine.capture.esqe import importance

    source = inspect.getsource(importance.score_importance)
    assert "achievable_ceiling_bp=achievable_ceiling_bp(" in source, (
        "the scorer never sets the ceiling, so every score claims the full 10000 was reachable")


def test_the_allocator_has_a_real_caller_in_the_budget_guard():
    """`allocate_budget` being green in isolation proves nothing: the whole defect was a branch
    that returned early and judged nothing. Asserted against the guard's source, because that
    early `return self.stats` is exactly what a unit test on the helper cannot see.
    """
    import inspect

    from genios_engine.capture.esqe import relevance

    source = inspect.getsource(relevance)
    assert "judged_head, deferred = allocate_budget(pending, budget=budget)" in source, (
        "the over-budget branch does not allocate — it is back to judging nothing")
    assert "self._closed_rule = UNJUDGED_FOR_BUDGET" in source, (
        "the deferred tail is not marked, so it is indistinguishable from a judged event again")


def test_every_rule_in_the_table_has_a_relevance_rank():
    """THE TOTALITY GUARD THAT CAUGHT ME. Adding `UNJUDGED_FOR_BUDGET` without a row in
    `_RULE_RELEVANCE_BP` raised `KeyError` on the first real page — which is the table working
    exactly as designed, and the reason a new rule cannot be half-added.
    """
    from genios_engine.capture.esqe import relevance as R

    for name in dir(R):
        if name.startswith("RULE_") or name == "UNJUDGED_FOR_BUDGET":
            value = getattr(R, name)
            if isinstance(value, str):
                assert value in R._RULE_RELEVANCE_BP, f"`{name}` has no relevance rank"

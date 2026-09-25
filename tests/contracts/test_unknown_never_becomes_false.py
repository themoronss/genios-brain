"""L3-11 · three-valued predicates exist; what did not exist was a number for the gap they declare.

`PredicateState` is TRUE / FALSE / UNKNOWN and `may_infer_absent` is wired into the one evaluator
that makes negative inferences. The spec's rule — "unknown must never silently become false" — is
implemented, and `context_adapter` states the failure it was built for: "an org with no mailbox
satisfied 'they never replied' on every situation it had".

⛔ WHAT IT ALSO STATES IS A GAP THAT IS STILL OPEN, and states it precisely:

    "`may_infer_absent` is `path not in unknowable`, and `unknowable_fields` holds only what
     somebody DECLARED unknowable — so A PATH NOBODY CLASSIFIED FALLS THROUGH TO 'LICENSED', and
     this branch concludes absence from silence… Closing it means making the coverage map TOTAL…
     and would turn MOST `absent:` answers into abstentions until it is done."

**"Most" is an unmeasured word, and a decision not to act was resting on it.** This file does not
close the gap — closing it is a product decision about abstention rates. It makes the gap COUNTABLE,
which is what turns the argument into a number.
"""
from __future__ import annotations

import inspect

from genios_engine.packs.compiler import context_adapter as CA


# =================================================================================================
# 1 · ⛔ THE THREE VALUES, AND THAT UNKNOWN IS ONE OF THEM
# =================================================================================================

def test_the_predicate_is_three_valued():
    assert {s.value for s in CA.PredicateState} == {"true", "false", "unknown"}


def test_an_unlicensed_absence_abstains_rather_than_asserting():
    """⛔ The rule the whole spec turns on: unknown must never silently become false — and here the
    dangerous direction is the other one, because `{absent: x}` answering TRUE is an assertion
    ABOUT THE WORLD made from an empty slice."""
    # ⛔ COMMENTS STRIPPED. The first draft split on the first `may_infer_absent` in the branch —
    # which is the COMMENT explaining the call, not the call. Eleventh time in this project an
    # assertion matched prose instead of code, and the fix is always the same: read what runs.
    src = inspect.getsource(CA)
    branch = src[src.index('if "absent" in condition:'):]
    branch = branch[:branch.index('if "has_obs" in condition:')]
    code = "\n".join(ln for ln in branch.splitlines() if not ln.lstrip().startswith("#"))
    assert "if not may_infer_absent(" in code
    after_call = code.split("if not may_infer_absent(")[1][:200]
    assert "PredicateState.UNKNOWN" in after_call, (
        "an unlicensed absence must abstain, not assert")


def test_the_licence_is_asked_not_re_derived():
    """Its own reasoning: "this was the call site that spelled the `in` out again, leaving the
    licence with a definition nobody consulted and a copy that decided. Two copies of one rule is
    how the next consumer gets a third"."""
    src = inspect.getsource(CA)
    branch = src[src.index('if "absent" in condition:'):]
    branch = branch[:branch.index('if "has_obs" in condition:')]
    code = "\n".join(ln for ln in branch.splitlines() if not ln.lstrip().startswith("#"))
    assert "may_infer_absent(" in code
    assert "not in self.unknowable_fields" not in code, "the licence rule has a second copy again"


# =================================================================================================
# 2 · ⛔ THE GAP IS DECLARED, AND NOW COUNTABLE
# =================================================================================================

def test_the_gap_is_still_declared_in_the_code_that_has_it():
    """⛔ If this comment is ever deleted, the fail-OPEN default becomes invisible — a default that
    concludes absence from silence, in a module whose every other branch fails closed."""
    src = " ".join(inspect.getsource(CA).split())
    assert "falls through to \"licensed\"" in src or "falls through to 'licensed'" in src, (
        "the fail-open default is no longer declared where it happens")
    assert "THE REAL GAP IS UPSTREAM AND IS NOT FIXED HERE" in src


def test_the_no_op_fix_cannot_come_back():
    """⛔ RECORDED BY THE CODE ITSELF: "A first cut of this comment shipped a `may_infer_absent`
    call here as if it fixed that. It could not: the `unknowable_fields` test three lines above has
    already returned, so the call can only ever answer True. Recorded rather than deleted, because
    A NO-OP WEARING A FIX'S COMMENT IS WORSE THAN THE GAP IT CLAIMS TO CLOSE."

    Pinned so the warning survives the next person who reads the gap and reaches for the same
    call."""
    src = " ".join(inspect.getsource(CA).split())
    assert "a no-op wearing a fix's comment is worse than the gap it claims to close" in src.lower()


def test_every_absent_outcome_is_named_with_its_meaning():
    assert set(CA.ABSENT_OUTCOMES) == {
        "refused_unknowable", "finding_typed_absent", "abstained_missing",
        "unclassified_licensed", "held"}
    for name, meaning in CA.ABSENT_OUTCOMES.items():
        assert len(meaning) > 30, f"{name} counted without saying what it means"
    assert "⛔ THE GAP" in CA.ABSENT_OUTCOMES["unclassified_licensed"], (
        "the gap's own bucket must say it is the gap, or a reader sees five equal categories")


def test_the_tally_is_counted_and_never_gated_on():
    """⛔ A counter that changed a verdict would be a second gate nobody declared. Reading it must
    change nothing — it exists so somebody can say how often the fail-open default decided
    something, not so the evaluator can behave differently when it has."""
    src = inspect.getsource(CA)
    for line in src.splitlines():
        if "absent_outcomes" in line and "if " in line:
            raise AssertionError(f"the tally is being read as a condition: {line.strip()!r}")


def test_the_gap_is_counted_where_it_happens_not_inferred_from_the_verdict():
    """⛔ TRUE from "typed absent" and TRUE from "nobody looked" are THE SAME VALUE. A count taken
    from the outcome could never tell them apart, which is exactly why the gap was invisible.

    ⛔ BEHAVIOURAL. The first draft asserted the counting LINE EXISTED, and stayed green when the
    branch guarding it was turned into `elif False:` — the line was present and unreachable, which
    is the precise shape of the thing this whole project keeps catching. It now RUNS the evaluator.
    """
    from tests.contracts.l2_situation_fixture import minimal_situation

    adapter = CA.ContextAdapter(minimal_situation())
    assert adapter.absent_outcomes == {}, "the adapter starts with an empty tally"

    verdict = adapter.evaluate({"absent": "nobody.ever.classified.this"})
    assert verdict.state is CA.PredicateState.TRUE, (
        "the fail-open default is gone — that may be the right product decision, but it is not "
        "this test's to make silently")
    assert adapter.absent_outcomes["unclassified_licensed"] == 1, (
        "absence was concluded from silence and nothing counted it — the gap is invisible again")


def test_the_adapter_starts_with_an_empty_tally():
    from tests.contracts.l2_situation_fixture import minimal_situation
    assert CA.ContextAdapter(minimal_situation()).absent_outcomes == {}


def test_a_tally_can_never_break_an_evaluation():
    """⛔ L2-7's lesson at a third seam. A first cut initialised the counter in `__init__` and broke
    four tests instantly — `test_the_borrow_reaches_the_rule_gate` builds its adapter with
    `ContextAdapter.__new__(ContextAdapter)`, so the attribute did not exist and EVERY
    `{absent: …}` EVALUATION RAISED. A counter had been given the power to crash the compiler.

    "A receipt that can abort the thing it is a receipt for turns an accounting failure into a
    product failure." A tally may be wrong, empty, or never read. It may not raise.
    """
    bare = CA.ContextAdapter.__new__(CA.ContextAdapter)
    assert bare.absent_outcomes == {}, "an adapter built without __init__ has no tally"
    bare.absent_outcomes["refused_unknowable"] += 1
    assert bare.absent_outcomes["refused_unknowable"] == 1, "the lazy tally does not persist"

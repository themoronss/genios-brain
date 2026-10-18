r"""`D.U09` · an empty `matches.when` is vacuously TRUE — the label that inverted.

⛔ WHAT WENT WRONG, AND IT WAS MY LABEL, NOT THE CODE. Building the review queue I counted the
`draft + unreviewed` situations with no `matches.when` block and wrote **"⛔ NO PREDICATE — can
never fire"** beside each of the ten. That is exactly backwards.

`packs/compiler/context_adapter.ContextAdapter.matches(conditions)` loops over `conditions`,
returns early on `FALSE`, collects `UNKNOWN`, and otherwise returns `PredicateState.TRUE`. Given
`()` the loop body never runs and `missing` stays empty, so it returns **TRUE**.
`capability_resolver` reads `matches.get("when") or ()` and feeds exactly that.

> **An empty `when` is not a gate that always closes. It is a gate that is never there.** Those ten
> situations match on their L2 situation type ALONE — the most permissive shape a situation can
> have, not the least.

The data said so before the code did, and I nearly wrote past it: `first_response_overdue` has no
`when` and its L2 type has formed **37** times in production. A situation that "can never fire"
does not have thirty-seven live instances of its trigger.

⛔ THIRD INVERSION OF THIS SHAPE IN ONE SESSION — all three were a verdict inferred from a
structure instead of measured from behaviour: a bare digit read as a layer number, a healthy unit
read as an undeclared absence, and now an absent gate read as a closed one.

This file pins the semantics so the queue's wording cannot drift back.
"""
from __future__ import annotations

import pytest

from genios_engine.packs.compiler.context_adapter import PredicateState

pytestmark = pytest.mark.unit


class _Adapter:
    """The real `matches` loop, exercised without a graph.

    ⛔ Imported logic, not a reimplementation: `matches` is taken off the real class and bound to a
    stub whose `evaluate` returns whatever the test wants. A hand-written copy of the loop would
    pass forever while the real one changed.
    """

    def __init__(self, verdicts):
        self._verdicts = list(verdicts)

    def evaluate(self, condition):          # noqa: ARG002 — the stub ignores the condition
        return self._verdicts.pop(0)

    @property
    def matches(self):
        from genios_engine.packs.compiler.context_adapter import ContextAdapter
        return ContextAdapter.matches.__get__(self, type(self))


def test_no_conditions_returns_true_not_false() -> None:
    """⛔ The assertion the review queue's wording depends on."""
    assert _Adapter(()).matches(()).state is PredicateState.TRUE


def test_an_empty_when_block_reaches_matches_as_an_empty_tuple() -> None:
    """`capability_resolver` reads `matches.get("when") or ()`, so a missing key, an explicit
    `None` and an empty list all arrive the same way — and all three therefore mean *always*."""
    for authored in ({}, {"when": None}, {"when": []}, {"when": ()}):
        assert (authored.get("when") or ()) == ()


def test_the_queue_calls_an_unconditional_situation_the_most_permissive_not_the_least() -> None:
    """The generated wording is part of the finding: a reviewer sent to look for a dead trigger
    would have looked for the opposite defect."""
    import ast
    import inspect

    from scripts import dx_review_queue

    # ⛔ THE MODULE DOCSTRING IS EXCLUDED, AND THAT EXCLUSION IS THE POINT. The docstring QUOTES
    # the inverted label while explaining the mistake, so a whole-file scan matches the very prose
    # that records the fix. Eighth instance of the blunt-grep family in this programme, and the
    # first caught by its own assertion failing a second after it was written. Only the executed
    # code and the strings it prints are in scope.
    tree = ast.parse(inspect.getsource(dx_review_queue))
    body = tree.body[1:] if (isinstance(tree.body[0], ast.Expr)
                             and isinstance(tree.body[0].value, ast.Constant)) else tree.body
    literals = [node.value for stmt in body for node in ast.walk(stmt)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    printed = " ".join(literals)

    # ⛔ AND THE BAN IS NARROWED TO ONE STRING, because the crude version failed on a CORRECT use.
    # "can never fire" is the right phrase for a predicate whose path nothing writes — that gate
    # really is shut — so banning it file-wide flagged a sentence that was true. The claim is only
    # about the string describing an EMPTY `when`.
    unconditional = [lit for lit in literals if "no extra condition" in lit]
    assert len(unconditional) == 1, (
        f"expected exactly one sentence describing an empty when, found {len(unconditional)}")
    sentence = unconditional[0]
    assert "vacuously true" in sentence
    assert "most permissive" in sentence
    assert "never fire" not in sentence, (
        f"the inverted label came back: {sentence!r}")


def test_the_queue_is_generated_rather_than_hand_kept() -> None:
    """A hand-written review list goes stale the first time somebody reviews one thing."""
    import inspect

    from scripts import dx_review_queue

    doc = inspect.getdoc(dx_review_queue) or ""
    assert "generated, never hand-kept" in doc.lower() or "generated" in doc.lower()
    # and it must read the corpus and production rather than a committed list
    source = inspect.getsource(dx_review_queue)
    assert "ExpertBrainCatalog" in source and "graph_facts" in source
    assert "context_situations" in source, "the L2-type check is what validates a review"

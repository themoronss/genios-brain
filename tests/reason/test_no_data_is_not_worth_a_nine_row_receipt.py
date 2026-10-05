""""We had no data" costs one suppression row, not a nine-row audit bundle.

    pytest tests/reason/test_no_data_is_not_worth_a_nine_row_receipt.py -q

⛔ WHY THIS FILE EXISTS. Measured on production: **165 cards**, against **12,182** `reasoning_runs`,
**34,272** `reasoning_candidates` and **43,200** `reasoning_reasoner_results` — about **6.4 MB of
receipts per card**, roughly 1 GB of a 1.5 GB database. It took the database past its disk quota
into read-only, and a read-only database crash-loops every deploy, because `platform/migrate`
raises when migrations are pending and the server will not accept writes.

The writer was `INSUFFICIENT_CONTEXT`. It means *"I had nothing to decide with"* — `deal.status` has
no writer, so the answer is identical for the same node on every sweep, four times a day, forever.
Persisting it wrote a ~9-row bundle (run + context snapshot + candidates + six reasoner results) to
say one sentence, and re-wrote that sentence every six hours. `core.relationship` alone answered it
708 times.

⛔ AND NOTHING READ IT. The branch that handles the outcome calls `_suppress` and then `continue`s;
that suppression row already carries the outcome, the uncertainty and the in-memory trace run id.
BLOCKED has been handled exactly this way since P2b — this is the same argument, applied to the
other member of the same pair.

⛔ FAILED IS NOT MOVED WITH IT, and that is the point of `test_a_crash_still_keeps_its_bundle`.
The two outcomes sat in one branch and read alike, but they are opposites: "we had no data" is a
fact about the tenant, "we crashed" is a fact about us, and the bundle is the only place a crash's
cause survives.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from genios_engine.contracts.reasoning import DecisionOutcome

pytestmark = pytest.mark.unit


def _persist_branch() -> ast.If:
    """The `if BLOCKED … elif matched/FAILED … else no-op` chain, found by the call it guards."""
    from genios_engine.reason import runner

    tree = ast.parse(textwrap.dedent(inspect.getsource(runner.run)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        calls = {c.func.id for c in ast.walk(node)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        if "persist_execution" in calls and node.orelse:
            return node
    raise AssertionError("the audit-persistence branch is gone from run()")


def _outcomes_in(node: ast.AST) -> set[str]:
    """Every `DecisionOutcome.X` named anywhere under a node."""
    return {a.attr for a in ast.walk(node)
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)
            and a.value.id == "DecisionOutcome"}


def test_no_data_does_not_buy_an_audit_bundle():
    """⛔ THE MUTATION THIS FILE REJECTS: putting INSUFFICIENT_CONTEXT back on the persisting arm."""
    branch = _persist_branch()
    skipped = _outcomes_in(branch.test)
    assert "INSUFFICIENT_CONTEXT" in skipped, (
        "INSUFFICIENT_CONTEXT is persisting a full bundle again — that is 1 GB of 'we had no data', "
        "rewritten every six hours for the same node")
    assert "BLOCKED" in skipped, "BLOCKED must stay on the skip arm (P2b)"


def test_a_crash_still_keeps_its_bundle():
    """FAILED is an exception inside reasoning. It is rare, it is a bug signal, and the bundle is
    where its cause survives — it must NOT be skipped alongside the no-data case."""
    branch = _persist_branch()
    assert "FAILED" not in _outcomes_in(branch.test), (
        "FAILED was moved onto the skip arm with INSUFFICIENT_CONTEXT; a crash would then leave "
        "nothing but a one-line suppression and no way to find its cause")
    persisting = branch.orelse[0] if isinstance(branch.orelse[0], ast.If) else None
    assert persisting is not None and "FAILED" in _outcomes_in(persisting.test), (
        "the persisting arm no longer names FAILED")


def test_the_matched_path_still_persists_in_full():
    """Only `matched` emits a signal, and the emission path reads `audit_bundle['output']`. If this
    ever stops persisting, signals stop — the one thing this optimisation may never touch."""
    branch = _persist_branch()
    persisting = branch.orelse[0]
    names = {n.attr for n in ast.walk(persisting.test) if isinstance(n, ast.Attribute)}
    assert "matched" in names, "the persisting arm no longer checks `reasoned.matched`"


def test_the_no_data_outcome_still_leaves_a_receipt():
    """⛔ SKIPPING THE BUNDLE IS NOT SKIPPING THE RECORD. The suppression row is what makes the
    silence auditable; dropping it too would turn a saving into a blind spot."""
    from genios_engine.reason import runner

    source = textwrap.dedent(inspect.getsource(runner.run))
    tree = ast.parse(source)
    suppress_calls = [c for c in ast.walk(tree)
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                      and c.func.id == "_suppress"]
    reasons = {a.value for call in suppress_calls for a in call.args
               if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    assert "reasoning_failed" in reasons, (
        "the suppression row for the no-data outcome is gone — the bundle was skipped AND the "
        "receipt with it, which is a blind spot rather than a saving")


def test_the_two_outcomes_are_still_distinguishable():
    """A saving that merged them would make "we had no data" and "we crashed" the same row."""
    assert DecisionOutcome.INSUFFICIENT_CONTEXT != DecisionOutcome.FAILED

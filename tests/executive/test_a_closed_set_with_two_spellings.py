r"""`U6` · `is_terminal` had no tests, and the caller that wants it may not import it.

⛔ TWO OF THE FIVE `UNREACHED` ENTRIES CARRIED NO TESTS AT ALL — *"unreached and unexercised,
which is the weaker of the two states"*. `monitor.blocking_action` was one and is now wired (U3).
`lifecycle.is_terminal` is the other, and this file is its first.

⛔ AND ITS DECLARATION PREDICTED EXACTLY WHAT HAPPENED. It said:

> *"`TERMINAL_STATES` is the closed set that decides when a commitment stops being advanced, and a
> named predicate over it is where a future reader will look. **Deleting it would push the next
> caller to re-inline the membership test, which is how a closed set acquires a second spelling.**"*

Measured 2026-10-01: **the second spelling already exists.**
`executive/execution_guard.py:126` opens `validate` with `if state.state in TERMINAL_STATES:` —
the single most authoritative branch in the guard, phrased as a set membership rather than as the
predicate written for it.

⛔ AND IT CANNOT HAVE THE PREDICATE. `lifecycle.py:39` imports `GuardAction` and `GuardVerdict`
**from** `execution_guard`, so the dependency runs `lifecycle -> guard`. Importing `is_terminal`
back would be a circular import. **The one caller that wants it is the one caller that may not have
it** — which is the honest answer to its declared *"MOVES WHEN a caller wants the predicate"*, and
could only be found by reading the imports rather than the call sites.

> ⛔ **An unreached function is not always a forgotten one; sometimes it is an unreachable one.**

## What this file does and does not do

It gives the predicate its first tests and pins the closed sets in **both** directions. ⛔ It does
**not** wire it, because that is the circular import, and it does **not** move it to
`contracts/execution` beside the `TERMINAL_STATES` it reads — which would close the entry and adds
no dependency, since the set is already there. That is a change to a public boundary and nobody
asked for it; it is recorded in the declaration as what would resolve this.

## ⛔ And `CREATED` is in neither set

    all states       ARCHIVED BLOCKED CANCELLED COMPLETED CREATED EXPIRED PENDING RUNNING WAITING
    OPEN_STATES      BLOCKED PENDING RUNNING WAITING
    TERMINAL_STATES  ARCHIVED CANCELLED COMPLETED EXPIRED
    intersection     EMPTY        ✅
    neither          CREATED      ⛔

So the two sets are **disjoint but not exhaustive**, and `CREATED` is neither open nor terminal:
`is_open(CREATED)` and `is_terminal(CREATED)` are both `False`. The tests below **pin that** rather
than assert it is wrong — a commitment that has been built and not yet entered its lifecycle is a
real third thing, and nothing here measured a harm from it.

## Living log

    2026-10-01   9 states · 4 open · 4 terminal · 1 neither (CREATED)
                 the second spelling: execution_guard.py:126
                 why it cannot be replaced: lifecycle.py:39 imports execution_guard
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

from genios_engine.contracts.execution import OPEN_STATES, TERMINAL_STATES, ExecutionState
from genios_engine.executive.lifecycle import is_open, is_terminal

ENGINE = Path(__file__).resolve().parents[2] / "genios_engine"


# ══ 1 · the predicate, which had no tests ════════════════════════════════════════

def test_every_terminal_state_is_terminal() -> None:
    for state in TERMINAL_STATES:
        assert is_terminal(state) is True, f"{state.name} is in TERMINAL_STATES and is not terminal"


def test_no_open_state_is_terminal() -> None:
    """⛔ The two sets must not overlap: a commitment the sweep still advances cannot also be one
    it has stopped advancing, and a state in both would make the guard's first branch suppress
    live work."""
    for state in OPEN_STATES:
        assert is_terminal(state) is False, f"{state.name} is open and reports terminal"


def test_the_predicate_agrees_with_the_set_for_every_state_in_the_enum() -> None:
    """⛔ BOTH DIRECTIONS over the whole enum, not a sample. A closed constant checked one way is
    half a guard — the rule `unit_health`'s totality guards state."""
    for state in ExecutionState:
        assert is_terminal(state) == (state in TERMINAL_STATES), state.name
        assert is_open(state) == (state in OPEN_STATES), state.name


# ══ 2 · the shape of the two sets ════════════════════════════════════════════════

def test_the_sets_are_disjoint() -> None:
    assert set(OPEN_STATES) & set(TERMINAL_STATES) == set()


def test_CREATED_is_in_neither_set_and_that_is_pinned_not_asserted_wrong() -> None:
    """⛔ `CREATED` is neither open nor terminal — a commitment built and not yet in its lifecycle.

    Pinned rather than corrected: nothing measured a harm from it, and the honest record of a
    third state is better than a set widened on a hunch. ⛔ If a later reader adds `CREATED` to
    either set, this test fails and they have to say which and why.
    """
    assert ExecutionState.CREATED not in OPEN_STATES
    assert ExecutionState.CREATED not in TERMINAL_STATES
    assert is_open(ExecutionState.CREATED) is False
    assert is_terminal(ExecutionState.CREATED) is False

    unclassified = set(ExecutionState) - set(OPEN_STATES) - set(TERMINAL_STATES)
    assert unclassified == {ExecutionState.CREATED}, (
        f"the unclassified set changed to {sorted(s.name for s in unclassified)}. Exactly one "
        "state is neither open nor terminal; a second one needs a reason written down")


def test_the_counts_are_what_was_measured() -> None:
    """Literals, so a state added to the enum is a deliberate change to this classification."""
    assert len(ExecutionState) == 9
    assert len(OPEN_STATES) == 4
    assert len(TERMINAL_STATES) == 4


# ══ 3 · the second spelling, and why it cannot be replaced ═══════════════════════

def test_the_guard_still_re_inlines_the_set_which_is_why_the_entry_stays() -> None:
    """⛔ The declaration's prediction, as a test. If this ever stops being true — because the
    predicate moved somewhere the guard can import — the `UNREACHED` entry is stale and the
    both-directions guard in `test_the_executive_says_what_it_does_not_call` will say so."""
    guard = (ENGINE / "executive" / "execution_guard.py").read_text(encoding="utf-8")
    assert "in TERMINAL_STATES" in guard, (
        "`execution_guard` no longer re-inlines the set. If it now calls `is_terminal`, the "
        "UNREACHED entry must be deleted in the same commit")


def test_the_import_direction_is_what_makes_it_unreachable() -> None:
    """⛔ THE FACT THAT ANSWERS THE DECLARED QUESTION, and it is structural.

    `lifecycle` imports FROM `execution_guard`, so the guard cannot import back. Read from the
    AST rather than by grepping for a word, because the claim is about an import statement and a
    mention of `execution_guard` in prose is not one.
    """
    tree = ast.parse((ENGINE / "executive" / "lifecycle.py").read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "genios_engine.executive.execution_guard" in imported, (
        "⛔ `lifecycle` no longer imports `execution_guard`. The cycle that made `is_terminal` "
        "unreachable from its one willing caller is gone, so the guard can now call the predicate "
        "— wire it and delete the UNREACHED entry")

    guard_tree = ast.parse((ENGINE / "executive" / "execution_guard.py").read_text(encoding="utf-8"))
    guard_imports = {node.module for node in ast.walk(guard_tree)
                     if isinstance(node, ast.ImportFrom)}
    assert "genios_engine.executive.lifecycle" not in guard_imports, (
        "the guard imports lifecycle — that is the cycle this test exists to prove absent")


def test_the_predicate_reads_the_set_and_does_not_restate_it() -> None:
    """A second list of state names inside the predicate would be a third spelling."""
    body = textwrap.dedent(inspect.getsource(is_terminal))
    tree = ast.parse(body)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "TERMINAL_STATES" in names, "the predicate must read the closed set by name"
    literals = [node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert literals == [], (
        f"the predicate carries string literals {literals} — a state name spelled here is a "
        "third copy of the set")

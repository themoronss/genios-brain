"""L3-01 · the Decision Object is ONE object with five projections, and the vocabulary is closed.

"The DecisionObject" appeared in six comments across `reason/` and `deliver/` with no type behind
it. The plan that led here assumed that meant five competing definitions to choose between. It did
not: `ReasoningDecision` is the object, fully typed and semantically hashed, and the five rows are
views of it. What was genuinely missing was a guard holding its outcome vocabulary to the database
constraint that stores it — they agree today, and nothing made them.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from genios_engine.contracts.reasoning import (DECISION_PROJECTIONS, DecisionOutcome,
                                               ReasoningDecision)

_ROOT = Path(__file__).resolve().parents[2]


# =================================================================================================
# 1 · ⛔ THE VOCABULARY IS CLOSED IN BOTH DIRECTIONS
# =================================================================================================

def _db_outcome_kinds() -> set[str]:
    """Every value the `reasoning_run_outputs.outcome_kind` check constraint admits."""
    found: set[str] = set()
    for sql in (_ROOT / "migrations").glob("*.sql"):
        text = sql.read_text()
        for m in re.finditer(r"check \(outcome_kind in \(([^)]*)\)", text, re.S):
            found |= set(re.findall(r"'([a-z_]+)'", m.group(1)))
    return found


def test_the_outcome_enum_and_the_database_agree_in_both_directions():
    """⛔ A totality guard that runs one way is half a guard.

    `DecisionOutcome` is what the engine may produce; the check constraint is what the store will
    accept. An enum member the DB rejects is a write that fails at 3am on a real decision; a DB
    value the enum lacks is a row nothing can read back. Neither direction was guarded — they
    happen to agree, which is not the same as being held together.
    """
    enum_values = {m.value for m in DecisionOutcome}
    db_values = _db_outcome_kinds()

    assert db_values, "no `check (outcome_kind in (...))` found in migrations — the guard is blind"
    assert enum_values - db_values == set(), (
        f"DecisionOutcome members the database would REJECT: {sorted(enum_values - db_values)}")
    assert db_values - enum_values == set(), (
        f"outcome_kind values the database admits but DecisionOutcome cannot produce: "
        f"{sorted(db_values - enum_values)} — a row nothing can read back into the contract")


def test_no_action_and_the_other_four_are_real_decisions():
    """⛔ A projection that only carries `decision` loses five sixths of the vocabulary.

    `no_action`, `defer`, `insufficient_context`, `blocked` and `failed` are decisions the product
    has to be able to state. Pinned so a later "simplification" to a boolean is a build failure.
    """
    assert {m.value for m in DecisionOutcome} == {
        "decision", "no_action", "defer", "insufficient_context", "blocked", "failed"}


# =================================================================================================
# 2 · ⛔ THE PROJECTIONS ARE REAL, AND SO ARE THEIR WRITERS
# =================================================================================================

def test_every_projection_names_a_module_that_exists():
    """A table of projections whose writers have moved is worse than no table: it reads as current.

    `signals (decision columns)` is the one that matters most — it is where the card's
    recommendation actually comes from, and `runner.py` calls its assembly point "the last point
    it exists in memory".
    """
    for name, module, _why in DECISION_PROJECTIONS:
        if module == "contracts.reasoning":
            continue                                   # the object itself, not a writer
        path = _ROOT / "genios_engine" / Path(module.replace(".", "/")).with_suffix(".py")
        assert path.exists(), f"projection {name!r} names writer {module!r}, which does not exist"


def test_the_object_itself_is_the_first_projection():
    """Order is the argument: everything below the first row is a VIEW. A table that opened with a
    table name would read as five rivals, which is the reading this step exists to end."""
    assert DECISION_PROJECTIONS[0][0] == "ReasoningDecision"
    assert DECISION_PROJECTIONS[0][1] == "contracts.reasoning"


def test_the_decision_object_says_it_is_the_decision_object():
    """It had no docstring at all — the concept was named in six comments elsewhere and nowhere on
    the type that is it. That is how "which one is the real one?" became a question."""
    doc = ReasoningDecision.__doc__ or ""
    assert "DECISION OBJECT" in doc.upper(), "ReasoningDecision no longer names itself"
    assert "DECISION_PROJECTIONS" in doc, "the docstring must point at the projection table"


# =================================================================================================
# 3 · ⛔ `decisions` IS THE QUERY API'S CACHE AND THE ENGINE MUST NOT WRITE IT
# =================================================================================================

def test_no_engine_package_writes_the_decisions_table():
    """Migration 0031 FKs `signals` to `reasoning_run_outputs`, not to `decisions`: the schema
    already chose which row is authoritative. An engine module writing `decisions` would create a
    second persisted decision with no foreign key holding it to anything."""
    offenders: list[str] = []
    for pkg in ("capture", "context", "packs", "reason", "executive", "deliver", "feedback"):
        for py in (_ROOT / "genios_engine" / pkg).rglob("*.py"):
            text = py.read_text()
            if re.search(r"insert\s+into\s+decisions\b|update\s+decisions\b", text, re.I):
                offenders.append(str(py.relative_to(_ROOT)))
    assert not offenders, (
        "engine modules writing the query API's decision cache: " + ", ".join(offenders))


# =================================================================================================
# 4 · SENSITIVITY — the object still carries what makes it defensible
# =================================================================================================

def test_the_object_still_carries_its_receipt_fields():
    """These are what make "why not X?" answerable from the record instead of from a re-run. A
    field removed here is a card that can no longer defend itself, and `to_semantic_dict` omits
    empties so dropping one would not even move `decision_hash` on old decisions."""
    fields = {f.name for f in __import__("dataclasses").fields(ReasoningDecision)}
    for required in ("candidates", "selected_candidate_id", "uncertainty",
                     "do_nothing_consequence", "citations", "constraints_applied",
                     "confidence_bp", "context_snapshot_id", "expires_at"):
        assert required in fields, f"ReasoningDecision lost {required!r}"


def test_the_projection_table_is_reachable_from_the_module_it_documents():
    """Technique 3's target. If `DECISION_PROJECTIONS` stops being importable from
    `contracts.reasoning`, every reader above is asserting against nothing."""
    tree = ast.parse((_ROOT / "genios_engine/contracts/reasoning.py").read_text())
    names: set[str] = set()
    for n in ast.walk(tree):
        # ⛔ BOTH assignment nodes. The first draft walked `ast.Assign` only and went red on a
        # correct module, because `DECISION_PROJECTIONS: tuple[...] = (...)` is an `AnnAssign` —
        # a typed constant is a different node, and a guard that only sees untyped ones would
        # have quietly stopped covering every annotated constant in this file.
        if isinstance(n, ast.Assign):
            names |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
    assert "DECISION_PROJECTIONS" in names

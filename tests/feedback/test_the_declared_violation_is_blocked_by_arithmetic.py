"""⛔⛔ A TRIPWIRE, not a repair. Atlas Layer 7 #3 / #11.

`target_policy.DURABLE_FROM_A_MEASUREMENT` declares that `unit_recommendation_learning` routes a
measurement into an auto-promoted durable ADAPTIVE brain the compiler reads back to the
recommender — *"the score trains the thing that produced it"*. That is right about the code's
SHAPE and was silent on whether the path is OPEN.

⛔ **It is not open.** The unit pins `evidence.distinct_days = 1`, `LearningPolicy.min_distinct_days`
defaults to 2, and `orchestrator.run_learning` runs `validate_learning` FIRST and `continue`s — so
`preflight` and `govern` never see the object. Every proposal is `held /
insufficient_distinct_days`.

⛔⛔ **AND THAT MAKES THE OBVIOUS REPAIR DANGEROUS.** Measuring `distinct_days` properly is correct
for the five sibling constants (all METRICS or KNOWLEDGE_SUGGESTION, which bypass the gate
entirely), is what `unit_pattern_learning` already does, and the data is in hand. A future engineer
making that fix would silently unblock an auto-promoted durable ADAPTIVE write.

**So this file fails loudly on each of the three things that would open the path, and names the
declaration to read before proceeding. It does not fix anything** — unblocking the unit changes
what the Adaptive brain CONTAINS, which is ADR-10, Rohit's.
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import datetime, timezone
from pathlib import Path

import pytest

from genios_engine.contracts.learning import (LearningEvidence, LearningObject, LearningPolicy,
                                              LearningTarget, Visibility, VisibilityScope)
from genios_engine.feedback import target_policy as TP
from genios_engine.feedback.units import validate_learning

_REPO = Path(__file__).resolve().parents[2]
_ENGINE = _REPO / "genios_engine"
_UNIT = "unit_recommendation_learning"
NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def _default(field: str) -> int:
    return next(f.default for f in dataclasses.fields(LearningPolicy) if f.name == field)


def _proposal(*, target=LearningTarget.ADAPTIVE, distinct_days: int = 1,
              confidence_bp: int = 9_000, observations: int = 12) -> LearningObject:
    """The object `unit_recommendation_learning` actually builds — same target, same evidence
    shape, same org visibility. Not a double: the real contract class, validated by its own
    `__post_init__`."""
    return LearningObject(
        org_id="org_1", unit="recommendation_learning", target=target,
        subject="play:demo_followup",
        proposed_value={"play": "demo_followup", "efficacy_bp": confidence_bp},
        evidence=LearningEvidence(
            observations=observations, independent_refs=observations,
            distinct_days=distinct_days, positive=observations, negative=0,
            confidence_bp=confidence_bp, business_value_bp=confidence_bp),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        first_seen_at=NOW, last_seen_at=NOW, policy_key="pk_1")


# ── the block itself, behaviourally ────────────────────────────────────────────────────────────

def test_the_durable_adaptive_proposal_is_held_before_governance_sees_it():
    ok, reason = validate_learning(_proposal(), LearningPolicy(org_id="org_1", revision=1))
    assert (ok, reason) == (False, "insufficient_distinct_days"), (
        "⛔ THE DECLARED AUTHORITY VIOLATION IS NOW REACHABLE. Read "
        "`target_policy.DURABLE_FROM_A_MEASUREMENT` and `BLOCKED_BY_ARITHMETIC` before going "
        "further: this unit publishes `efficacy_bp` into the `adaptive` brain, the pack compiler "
        "reads that brain into the compiled expertise package, and the recommender reasons from "
        "it. Unblocking it is ADR-10, not a bug fix.")


def test_the_arithmetic_is_what_blocks_it():
    assert _default("min_distinct_days") > 1
    pinned = dict((u, d) for u, t, d in TP.hardcoded_distinct_days())
    assert pinned["recommendation_learning"] == 1
    assert pinned["recommendation_learning"] < _default("min_distinct_days")


def test_the_second_gate_behind_the_first_is_real():
    """⛔ Fixing `distinct_days` alone does not necessarily open the path — declared so that
    neither direction is a surprise to whoever touches the first gate."""
    policy = LearningPolicy(org_id="org_1", revision=1)
    ok, reason = validate_learning(
        _proposal(distinct_days=_default("min_distinct_days"),
                  confidence_bp=_default("min_confidence_bp") - 1), policy)
    assert (ok, reason) == (False, "below_confidence_floor")


def test_with_both_gates_cleared_the_path_IS_open_which_is_the_whole_warning():
    """The tripwire has to be honest about what it is protecting: nothing else stops this."""
    policy = LearningPolicy(org_id="org_1", revision=1)
    ok, reason = validate_learning(
        _proposal(distinct_days=_default("min_distinct_days"),
                  confidence_bp=_default("min_confidence_bp")), policy)
    assert (ok, reason) == (True, "validated")


@pytest.mark.parametrize("target", [LearningTarget.METRICS, LearningTarget.KNOWLEDGE_SUGGESTION])
def test_the_five_sibling_constants_are_harmless_because_artifacts_bypass_the_gate(target):
    ok, reason = validate_learning(_proposal(target=target, distinct_days=1),
                                   LearningPolicy(org_id="org_1", revision=1))
    assert (ok, reason) == (True, "artifact")


def test_only_one_unit_pins_the_day_count_on_a_durable_target():
    measured = {f"unit_{u}" for u in TP.durable_units_pinning_distinct_days()}
    assert measured == set(TP.BLOCKED_BY_ARITHMETIC), (
        f"a unit writing a DURABLE brain now pins `distinct_days` and is undeclared: "
        f"{sorted(measured ^ set(TP.BLOCKED_BY_ARITHMETIC))}")


def test_the_unit_that_does_it_right_is_still_doing_it_right():
    """`unit_pattern_learning` computes `len(g["days"])`. It is the shape the fix would copy, and
    the reason the fix looks obvious."""
    computed = {u for u, _, d in TP.hardcoded_distinct_days() if d is None}
    assert "pattern_learning" in computed


# ── the three things that would open it ────────────────────────────────────────────────────────

def _run_learning_body() -> ast.FunctionDef:
    tree = ast.parse((_ENGINE / "feedback" / "orchestrator.py").read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "run_learning"), None)
    assert fn is not None, "run_learning is gone — the whole ordering argument must be re-read"
    return fn


def test_validation_still_runs_before_governance():
    fn = _run_learning_body()
    first: dict[str, int] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = (node.func.attr if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", None))
            if name in {"validate_learning", "preflight", "govern"}:
                first.setdefault(name, node.lineno)
    assert {"validate_learning", "preflight", "govern"} <= set(first), first
    assert first["validate_learning"] < first["preflight"] < first["govern"], (
        f"⛔ the order changed: {first}. Validation running after governance would let `govern` "
        "promote a proposal validation would have held — read `BLOCKED_BY_ARITHMETIC`")


def test_a_failed_validation_still_short_circuits():
    """Without the `continue`, a held proposal would fall through into `preflight`."""
    fn = _run_learning_body()
    guarded = False
    for node in ast.walk(fn):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp)
                and isinstance(node.test.op, ast.Not)):
            continue
        if not (isinstance(node.test.operand, ast.Name) and node.test.operand.id == "ok"):
            continue
        guarded = any(isinstance(n, ast.Continue) for n in ast.walk(ast.Module(
            body=node.body, type_ignores=[])))
    assert guarded, "`if not ok:` no longer ends in `continue` — a held proposal now falls through"


def test_the_loader_still_takes_the_stored_floor_verbatim():
    """⛔ The SECOND way in. `LearningPolicy`'s docstring used to claim *'a tenant can only narrow
    them'*; nothing enforces it, so a stored `min_distinct_days = 1` opens the path with no code
    change. The guard records the absence rather than inventing a clamp — adding one would change
    which proposals every tenant admits."""
    src = (_ENGINE / "feedback" / "orchestrator.py").read_text(encoding="utf-8")
    assert 'min_distinct_days=row["min_distinct_days"]' in src
    assert "max(" not in src.split("def load_or_seed_policy")[1].split("def ")[0], (
        "the loader now clamps a stored policy. That is a real improvement and it changes what "
        "every tenant admits — update `BLOCKED_BY_ARITHMETIC`, which cites the absence of a clamp "
        "as one of the three ways the declared violation opens")


def test_the_schema_still_has_no_floor_either():
    sql = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((_REPO / "migrations").glob("*.sql")))
    assert "min_distinct_days             int  not null default 2" in sql
    assert "check (min_distinct_days" not in sql.replace("  ", " "), (
        "a CHECK now floors the column — the second way in is closed, which is good news that "
        "`BLOCKED_BY_ARITHMETIC` must stop claiming")


def test_the_corrected_docstring_quotes_the_old_claim_as_a_correction():
    """⛔ Attribution, not absence: the correction must quote *'a tenant can only narrow them'* in
    order to retract it."""
    src = (_ENGINE / "contracts" / "learning.py").read_text(encoding="utf-8")
    stale = "a tenant can only narrow\n    them"
    if stale in src:
        head = src[max(0, src.index(stale) - 400):src.index(stale)]
        assert "CORRECTED" in head


# ── the declaration says enough to act on ──────────────────────────────────────────────────────

def test_the_declaration_names_the_gate_the_numbers_and_the_mover():
    gate, arithmetic, mover = TP.BLOCKED_BY_ARITHMETIC[_UNIT]
    assert "insufficient_distinct_days" in gate
    assert "distinct_days=1" in arithmetic and "min_distinct_days" in arithmetic
    assert mover.startswith(("MOVES WHEN", "MOVES WITH")) or mover.startswith("⛔ MOVES")
    assert "learning_object_evaluations" in mover, (
        "the mover must carry the query that sizes the decision — `S6` built that ledger for "
        "exactly this question")


def test_the_blocked_unit_is_the_declared_violation():
    assert set(TP.BLOCKED_BY_ARITHMETIC) <= set(TP.DURABLE_FROM_A_MEASUREMENT)
    assert TP.UNIT_TARGETS[_UNIT][0] in TP.DURABLE_BRAIN_TARGETS


def test_every_path_the_declarations_cite_exists():
    blob = " ".join(part for v in TP.BLOCKED_BY_ARITHMETIC.values() for part in v)
    blob += " ".join(part for v in TP.DURABLE_FROM_A_MEASUREMENT.values() for part in v)
    import re
    cited = re.findall(r"(?:tests|genios_engine|migrations|speedrun008)/[\w./-]+\.(?:py|sql|md)",
                       blob)
    missing = [c for c in cited if not (_REPO / c).exists()]
    assert not missing, f"the declarations cite paths that no longer exist: {missing}"

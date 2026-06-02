"""Tests for core.reasoning.csp_solver — Z3 hard constraint checks."""

from __future__ import annotations

import pytest

from core.reasoning.csp_solver import ConstraintSolver, Variable, VarType


@pytest.mark.unit
def test_assignment_satisfies_constraints() -> None:
    solver = ConstraintSolver()
    vars_ = [
        Variable(name="discount_pct", type=VarType.REAL),
        Variable(name="margin_pct", type=VarType.REAL),
    ]
    constraints = [
        ("discount_pct", "<=", 30),
        ("margin_pct", ">=", 25),
    ]
    result = solver.check(vars_, constraints, {"discount_pct": 20.0, "margin_pct": 40.0})
    assert result.satisfied is True
    assert result.timed_out is False


@pytest.mark.unit
def test_assignment_violates_hard_constraint() -> None:
    """Per real MD test case: discount=50 with margin floor=25 → violation."""
    solver = ConstraintSolver()
    vars_ = [Variable(name="discount_pct", type=VarType.REAL)]
    constraints = [("discount_pct", "<=", 30)]
    result = solver.check(vars_, constraints, {"discount_pct": 50.0})
    assert result.satisfied is False
    assert result.violating_assignments == {"discount_pct": 50.0}


@pytest.mark.unit
def test_unknown_variable_in_constraint_rejected() -> None:
    solver = ConstraintSolver()
    vars_ = [Variable(name="x", type=VarType.INT)]
    result = solver.check(vars_, [("y", ">", 0)], {"x": 5})
    assert result.satisfied is False
    assert "unknown variable" in result.reason.lower()


@pytest.mark.unit
def test_is_satisfiable_true() -> None:
    solver = ConstraintSolver()
    vars_ = [Variable(name="x", type=VarType.INT)]
    constraints = [("x", ">", 0), ("x", "<", 100)]
    assert solver.is_satisfiable(vars_, constraints).satisfied is True


@pytest.mark.unit
def test_is_satisfiable_false() -> None:
    solver = ConstraintSolver()
    vars_ = [Variable(name="x", type=VarType.INT)]
    constraints = [("x", ">", 100), ("x", "<", 50)]  # impossible
    assert solver.is_satisfiable(vars_, constraints).satisfied is False


@pytest.mark.unit
def test_bool_variable_check() -> None:
    solver = ConstraintSolver()
    vars_ = [Variable(name="approved", type=VarType.BOOL)]
    constraints = [("approved", "==", True)]
    assert solver.check(vars_, constraints, {"approved": True}).satisfied
    assert not solver.check(vars_, constraints, {"approved": False}).satisfied


@pytest.mark.unit
def test_invalid_operator_raises() -> None:
    solver = ConstraintSolver()
    vars_ = [Variable(name="x", type=VarType.INT)]
    with pytest.raises(ValueError):
        solver.check(vars_, [("x", "~~", 5)], {"x": 5})

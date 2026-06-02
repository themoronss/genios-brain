"""Z3-backed CSP solver for hard constraints.

Per MD g-i-2 §2.1.2:
- Model hard limits (margin floors, approval thresholds) as a CSP
- Solve via Z3 (the chosen backend per Group 3 lock)
- Bounded by CSP_TIMEOUT_SECONDS (from config) — fall back if exceeds

Use case in the engine:
- A rule with `hard: true` can be additionally validated via a constraint check
  (e.g. "the proposed discount must respect: discount_pct <= 30 AND margin_pct >= 25")
- The neural layer's output is checked against the same constraints before fusion
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import z3

from core.foundations.config import CSP_TIMEOUT_SECONDS
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


class VarType(StrEnum):
    INT = "int"
    REAL = "real"
    BOOL = "bool"


@dataclass(frozen=True)
class Variable:
    """A CSP variable declaration."""

    name: str
    type: VarType


@dataclass(frozen=True)
class ConstraintCheck:
    """Result of checking a constraint set against an assignment."""

    satisfied: bool
    reason: str
    timed_out: bool = False
    violating_assignments: dict[str, Any] | None = None


class ConstraintSolver:
    """Wraps Z3 for constraint checking.

    Two main use cases:
    1. `check(constraints, assignments)` — does this assignment satisfy these constraints?
    2. `is_satisfiable(constraints)` — is there ANY assignment that satisfies these?

    Constraints are passed as a list of (lhs_var, op, rhs_value) tuples for v1
    simplicity. For more complex expressions (multi-var arithmetic), callers
    construct Z3 expressions directly via build_expression().
    """

    def __init__(self, timeout_seconds: int | None = None) -> None:
        self._timeout_ms = (timeout_seconds or CSP_TIMEOUT_SECONDS) * 1000

    def check(
        self,
        variables: list[Variable],
        constraints: list[tuple[str, str, Any]],
        assignment: dict[str, Any],
    ) -> ConstraintCheck:
        """Check if an assignment satisfies all constraints.

        Returns ConstraintCheck(satisfied=True) iff every constraint holds.
        On timeout, returns timed_out=True (caller decides fallback policy).
        """
        try:
            solver = z3.Solver()
            solver.set("timeout", self._timeout_ms)

            z3_vars = self._declare_vars(variables)

            # Pin the assignment
            for name, value in assignment.items():
                if name in z3_vars:
                    solver.add(z3_vars[name] == self._to_z3_value(value, z3_vars[name]))

            # Add constraints
            for lhs, op, rhs in constraints:
                if lhs not in z3_vars:
                    return ConstraintCheck(
                        satisfied=False,
                        reason=f"Unknown variable in constraint: {lhs}",
                    )
                expr = self._build_op_expr(z3_vars[lhs], op, rhs)
                solver.add(expr)

            result = solver.check()
            if result == z3.unknown:
                log.warning("csp_timeout", timeout_ms=self._timeout_ms)
                return ConstraintCheck(
                    satisfied=False,
                    reason="solver timeout",
                    timed_out=True,
                )
            if result == z3.sat:
                return ConstraintCheck(satisfied=True, reason="all constraints satisfied")
            return ConstraintCheck(
                satisfied=False,
                reason="constraints violated by assignment",
                violating_assignments=assignment,
            )
        except z3.Z3Exception as e:
            log.error("csp_z3_error", error=str(e))
            return ConstraintCheck(satisfied=False, reason=f"Z3 error: {e}")

    def is_satisfiable(
        self,
        variables: list[Variable],
        constraints: list[tuple[str, str, Any]],
    ) -> ConstraintCheck:
        """Is there ANY assignment satisfying all constraints?"""
        try:
            solver = z3.Solver()
            solver.set("timeout", self._timeout_ms)
            z3_vars = self._declare_vars(variables)
            for lhs, op, rhs in constraints:
                if lhs not in z3_vars:
                    return ConstraintCheck(
                        satisfied=False,
                        reason=f"Unknown variable: {lhs}",
                    )
                solver.add(self._build_op_expr(z3_vars[lhs], op, rhs))

            result = solver.check()
            if result == z3.unknown:
                return ConstraintCheck(satisfied=False, reason="solver timeout", timed_out=True)
            return ConstraintCheck(
                satisfied=(result == z3.sat),
                reason="satisfiable" if result == z3.sat else "unsatisfiable",
            )
        except z3.Z3Exception as e:
            return ConstraintCheck(satisfied=False, reason=f"Z3 error: {e}")

    # ─── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _declare_vars(variables: list[Variable]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for v in variables:
            match v.type:
                case VarType.INT:
                    out[v.name] = z3.Int(v.name)
                case VarType.REAL:
                    out[v.name] = z3.Real(v.name)
                case VarType.BOOL:
                    out[v.name] = z3.Bool(v.name)
        return out

    @staticmethod
    def _to_z3_value(value: Any, var_expr: Any) -> Any:
        if isinstance(value, bool):
            return z3.BoolVal(value)
        if isinstance(value, int):
            return z3.IntVal(value) if str(var_expr.sort()) == "Int" else z3.RealVal(value)
        if isinstance(value, float):
            return z3.RealVal(value)
        return value

    @staticmethod
    def _build_op_expr(var: Any, op: str, rhs: Any) -> Any:
        if op == "==":
            return var == rhs
        if op == "!=":
            return var != rhs
        if op == ">":
            return var > rhs
        if op == "<":
            return var < rhs
        if op == ">=":
            return var >= rhs
        if op == "<=":
            return var <= rhs
        raise ValueError(f"Unsupported CSP operator: {op}")

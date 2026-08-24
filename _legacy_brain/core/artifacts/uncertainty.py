"""Uncertainty flags — MANDATORY in every artifact (per MD §6.2.1).

Hiding uncertainty to look confident is the OPPOSITE of the product's value.
Every artifact MUST surface:
- which edges are low-trust (alpha+beta below N_min)
- which weights are 'default' (no evidence yet)
- which parts came from LLM gap-fill (vs symbolic)
- which conclusions rest on candidate (not yet asserted) edges

This module walks a Decision + its supporting graph state + collects flags.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from core.foundations.config import N_MIN_EVIDENCE
from core.graph.store import EdgeRow


class UncertaintyKind(StrEnum):
    """Categories of uncertainty an artifact must surface."""

    LOW_TRUST_EDGE = "low_trust_edge"  # weight derived but evidence < N_min
    BELOW_N_MIN = "below_n_min"  # alpha+beta < N_min on an edge in the proof path
    DEFAULT_WEIGHT = "default_weight"  # weight_source='default' (never had real evidence)
    LLM_GAP_FILL = "llm_gap_fill"  # part of the conclusion came from neural gateway
    CANDIDATE_EDGE = "candidate_edge"  # an edge in the proof path is status='candidate'


@dataclass(frozen=True)
class UncertaintyFlag:
    """One flag surfaced in an artifact. severity in {low, medium, high}."""

    kind: UncertaintyKind
    target: str  # edge_id / rule_id / "conclusion" / etc.
    severity: str
    detail: str


def collect_uncertainty(
    session: Session | None,
    *,
    org_id: str,
    decision_path: str,  # 'symbolic' | 'neural' | 'hybrid'
    edge_ids_in_proof: Iterable[str],
    derivation_chain: list[dict[str, Any]] | None = None,
    n_min: int = N_MIN_EVIDENCE,
) -> list[UncertaintyFlag]:
    """Walk the decision's proof path + flag every uncertain spot.

    Args:
        session: SQLAlchemy session (can be None to skip edge inspection — used in tests
                 that don't have graph rows seeded)
        org_id: per-org scoping
        decision_path: from Decision.path
        edge_ids_in_proof: edges referenced by the derivation chain's graphPath
        derivation_chain: optional, used to detect candidate edges + neural steps
        n_min: minimum evidence threshold

    Returns: list of flags. Empty list is valid (means everything is well-grounded).
    """
    flags: list[UncertaintyFlag] = []

    # LLM gap-fill flag — applies to whole conclusion
    if decision_path in ("neural", "hybrid"):
        flags.append(
            UncertaintyFlag(
                kind=UncertaintyKind.LLM_GAP_FILL,
                target="conclusion",
                severity="medium" if decision_path == "hybrid" else "high",
                detail=(
                    f"Decision path = '{decision_path}'. Part of the conclusion came from "
                    "an LLM gap-fill (validated against constraints, but not symbolic)."
                ),
            )
        )

    # Edge-level flags require graph state
    if session is not None:
        for edge_id in edge_ids_in_proof:
            row = session.get(EdgeRow, edge_id)
            if row is None or row.org_id != org_id:
                continue

            evidence = row.alpha + row.beta
            if evidence < n_min:
                flags.append(
                    UncertaintyFlag(
                        kind=UncertaintyKind.BELOW_N_MIN,
                        target=edge_id,
                        severity="medium" if evidence > n_min // 2 else "high",
                        detail=(
                            f"Edge has {evidence} evidence points (need {n_min} to trust the weight). "
                            f"Treat the derived weight {row.weight:.2f} as low-trust."
                        ),
                    )
                )

            if row.weight_source == "default":
                flags.append(
                    UncertaintyFlag(
                        kind=UncertaintyKind.DEFAULT_WEIGHT,
                        target=edge_id,
                        severity="medium",
                        detail="Edge weight is a default placeholder — no real evidence yet.",
                    )
                )

            if row.status == "candidate":
                flags.append(
                    UncertaintyFlag(
                        kind=UncertaintyKind.CANDIDATE_EDGE,
                        target=edge_id,
                        severity="high",
                        detail=(
                            "Edge has status='candidate' — it was detected via lift but has "
                            "NOT been confirmed by a human. Should not appear in a finalized proof."
                        ),
                    )
                )

    # Hybrid-path low-trust edge flag (derivation_chain may reveal neural steps)
    if derivation_chain:
        for step in derivation_chain:
            if isinstance(step, dict) and step.get("source") == "neural":
                flags.append(
                    UncertaintyFlag(
                        kind=UncertaintyKind.LLM_GAP_FILL,
                        target=step.get("rule_id", "unknown_step"),
                        severity="medium",
                        detail="This step was inferred by the neural gateway, not a symbolic rule.",
                    )
                )

    return flags

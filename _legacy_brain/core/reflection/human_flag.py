"""80/20 routing + structured Correction capture.

Per MD g-i-2 §2.3.2:
    confidence >= theta_act          -> AUTONOMOUS (agent acts, no human)
    theta_flag <= confidence < theta_act -> NOTIFY + recommend (REVERSIBLE only)
    confidence < theta_flag          -> FLAG_FOR_HUMAN

Per MD: user persona (g-i-9) redLines force flag regardless of confidence.

Correction capture (per g-i-7 § humans + g-i-3 § learning):
- When a human overrides an emitted decision -> CorrectionRow persisted
- Per-edge confirm/contradict derived from the diff
- Feeds g-i-3 Bayesian update via core.worldmodel.learning.apply_correction

Theta defaults follow GENIOS_V2_PLAN.md Group 2:
    theta_act  = 0.75  (above this, agent acts autonomously)
    theta_flag = 0.45  (below this, human-only)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.worldmodel.store import CorrectionRow

log = get_logger(__name__)


# Per-module overrides come via core.foundations.config.get_tunable when g-i-8 lands.
DEFAULT_THETA_ACT = 0.75
DEFAULT_THETA_FLAG = 0.45


class Route(StrEnum):
    AUTONOMOUS = "autonomous"
    NOTIFY = "notify"
    FLAG = "flag"


@dataclass(frozen=True)
class RoutingDecision:
    """Output of route_decision(). Returned alongside the engine's conclusion."""

    route: Route
    confidence: float
    reason: str
    redline_triggered: bool = False


def route_decision(
    *,
    confidence: float,
    reversible: bool,
    user_redlines_hit: list[str] | None = None,
    theta_act: float = DEFAULT_THETA_ACT,
    theta_flag: float = DEFAULT_THETA_FLAG,
) -> RoutingDecision:
    """Apply the 80/20 policy.

    Args:
        confidence: external confidence in [0, 1]
        reversible: True if the action can be undone (only reversible actions can be NOTIFY-routed)
        user_redlines_hit: persona redlines that match this decision; non-empty -> force FLAG
        theta_act, theta_flag: routing thresholds
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence must be in [0, 1]; got {confidence}")
    if theta_flag > theta_act:
        raise ValueError(f"theta_flag ({theta_flag}) must be <= theta_act ({theta_act})")

    # Persona redlines ALWAYS force flag (per MD g-i-9 §1)
    if user_redlines_hit:
        return RoutingDecision(
            route=Route.FLAG,
            confidence=confidence,
            reason=f"user redline triggered: {', '.join(user_redlines_hit)}",
            redline_triggered=True,
        )

    if confidence >= theta_act:
        if reversible:
            return RoutingDecision(
                route=Route.AUTONOMOUS,
                confidence=confidence,
                reason=f"confidence {confidence:.2f} >= theta_act {theta_act:.2f}, action reversible",
            )
        # Irreversible high-confidence -> NOTIFY (per MD: only reversible can be autonomous)
        return RoutingDecision(
            route=Route.NOTIFY,
            confidence=confidence,
            reason=(
                f"confidence {confidence:.2f} >= theta_act {theta_act:.2f} "
                f"BUT action is irreversible — notify + wait for human"
            ),
        )

    if confidence >= theta_flag:
        # Mid range: notify only if reversible; flag otherwise
        if reversible:
            return RoutingDecision(
                route=Route.NOTIFY,
                confidence=confidence,
                reason=(
                    f"theta_flag {theta_flag:.2f} <= conf {confidence:.2f} < theta_act, reversible"
                ),
            )
        return RoutingDecision(
            route=Route.FLAG,
            confidence=confidence,
            reason=(
                f"theta_flag {theta_flag:.2f} <= conf {confidence:.2f} < theta_act "
                f"BUT action is irreversible — flag for human"
            ),
        )

    return RoutingDecision(
        route=Route.FLAG,
        confidence=confidence,
        reason=f"confidence {confidence:.2f} < theta_flag {theta_flag:.2f}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Correction capture — the moat's data-entry point (g-i-7 -> g-i-3)
# ─────────────────────────────────────────────────────────────────────────────


def capture_correction(
    session: Session,
    *,
    org_id: str,
    decision_id: str,
    input_context: dict[str, Any],
    engine_decision: dict[str, Any],
    human_decision: dict[str, Any],
    rule_ids: list[str],
    edge_ids: list[str],
    actor: str,
) -> CorrectionRow:
    """Persist a structured human override. Returns the CorrectionRow.

    `diff` is auto-computed from (engine_decision, human_decision). Callers can
    add explicit edges_confirmed / edges_contradicted via the standard pattern
    documented in core.worldmodel.learning.derive_outcomes().
    """
    diff = _compute_diff(engine_decision, human_decision)

    row = CorrectionRow(
        org_id=org_id,
        decision_id=decision_id,
        input_context=input_context,
        engine_decision=engine_decision,
        human_decision=human_decision,
        diff=diff,
        rule_ids=rule_ids,
        edge_ids=edge_ids,
        timestamp=datetime.now(UTC),
        actor=actor,
    )
    session.add(row)
    session.flush()

    audit.record(
        org_id=org_id,
        actor_type="user",
        actor_id=actor,
        action="override_captured",
        target_type="decision",
        target_id=decision_id,
        metadata={
            "correction_id": row.id,
            "rule_ids": rule_ids,
            "edge_ids": edge_ids,
        },
    )

    log.info(
        "correction_captured",
        org_id=org_id,
        decision_id=decision_id,
        correction_id=row.id,
        actor=actor,
    )
    return row


def _compute_diff(
    engine_decision: dict[str, Any], human_decision: dict[str, Any]
) -> dict[str, Any]:
    """Top-level field-by-field diff. Caller can enrich with edges_* keys."""
    diff: dict[str, Any] = {}
    keys = set(engine_decision) | set(human_decision)
    for k in keys:
        e = engine_decision.get(k)
        h = human_decision.get(k)
        if e != h:
            diff[k] = {"engine": e, "human": h}
    return diff

"""80/20 routing + channel discipline + per-user push budget.

Per MD g-i-4 §1.2.2:
    push if priority >= theta_priority AND (risk_score > X OR opportunity_score > Y)

    CALIBRATION GATE: risk_score / opportunity_score are MEANINGFUL ONLY when
    confidence is calibrated (ECE/Brier measured). Until then -> qualitative
    triggers (high/med/low), not numeric thresholds.

    Delivery routing (same 80/20 as g-i-2):
        high-conf + reversible + low blast-radius  -> AUTONOMOUS
        high-conf + irreversible/high-stakes       -> NOTIFY (wait for human)
        low-conf                                    -> FLAG (human-only)

    Channel discipline:
        urgent     -> interrupt (Slack DM)
        non-urgent -> DIGEST batch
        per-user push budget enforced; overflow -> digest
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations.config import PUSH_BUDGET_PER_USER_PER_DAY
from core.foundations.telemetry import get_logger
from core.proactive.store import PushBudgetRow
from core.proactive.types import DeliveryRoute, Insight

log = get_logger(__name__)


Channel = Literal["interrupt", "digest", "flag_queue", "autonomous_action"]


@dataclass(frozen=True)
class ChannelDecision:
    """Output of deliver_insight()."""

    insight_id: str
    route: DeliveryRoute
    channel: Channel
    reason: str
    budget_consumed: bool


def deliver_insight(
    session: Session,
    *,
    insight: Insight,
    user_id: str,
    confidence: float,
    reversible: bool,
    urgent: bool,
    today: str | None = None,
) -> ChannelDecision:
    """Pick route + channel + enforce per-user push budget.

    Args:
        urgent: caller's per-insight urgency flag (drives channel, not route)
        today: YYYY-MM-DD for budget bucket; defaults to today UTC
    """
    today = today or datetime.now(UTC).strftime("%Y-%m-%d")

    # Step 1: 80/20 route from confidence + reversibility
    if confidence >= 0.75 and reversible:
        route = DeliveryRoute.AUTONOMOUS
        channel: Channel = "autonomous_action"
        budget_consumed = False
        reason = "high confidence + reversible -> autonomous"

    elif confidence >= 0.75 and not reversible:
        route = DeliveryRoute.NOTIFY
        # Step 2: budget check before scheduling an interrupt
        if urgent and _budget_available(
            session, org_id=insight.org_id, user_id=user_id, date=today
        ):
            channel = "interrupt"
            _consume_budget(session, org_id=insight.org_id, user_id=user_id, date=today)
            budget_consumed = True
            reason = "high confidence irreversible + urgent + budget OK -> interrupt"
        else:
            channel = "digest"
            budget_consumed = False
            reason = "high confidence irreversible + non-urgent OR no budget left -> digest"

    elif confidence >= 0.45:
        # Mid range
        if reversible:
            route = DeliveryRoute.NOTIFY
            if urgent and _budget_available(
                session, org_id=insight.org_id, user_id=user_id, date=today
            ):
                channel = "interrupt"
                _consume_budget(session, org_id=insight.org_id, user_id=user_id, date=today)
                budget_consumed = True
                reason = "mid confidence reversible + urgent + budget OK -> interrupt"
            else:
                channel = "digest"
                budget_consumed = False
                reason = "mid confidence reversible + non-urgent -> digest"
        else:
            route = DeliveryRoute.FLAG
            channel = "flag_queue"
            budget_consumed = False
            reason = "mid confidence irreversible -> FLAG for human"

    else:
        # Low confidence -> always FLAG (per MD)
        route = DeliveryRoute.FLAG
        channel = "flag_queue"
        budget_consumed = False
        reason = f"low confidence {confidence:.2f} -> FLAG"

    log.info(
        "insight_delivery_routed",
        insight_id=insight.id,
        org_id=insight.org_id,
        user_id=user_id,
        route=route.value,
        channel=channel,
        budget_consumed=budget_consumed,
    )
    return ChannelDecision(
        insight_id=insight.id,
        route=route,
        channel=channel,
        reason=reason,
        budget_consumed=budget_consumed,
    )


# ─── budget helpers ────────────────────────────────────────────────────────


def _budget_available(session: Session, *, org_id: str, user_id: str, date: str) -> bool:
    row = _get_or_init_budget(session, org_id=org_id, user_id=user_id, date=date)
    return row.interrupts_used < row.max_allowed


def _consume_budget(session: Session, *, org_id: str, user_id: str, date: str) -> None:
    row = _get_or_init_budget(session, org_id=org_id, user_id=user_id, date=date)
    row.interrupts_used += 1
    session.flush()


def _get_or_init_budget(session: Session, *, org_id: str, user_id: str, date: str) -> PushBudgetRow:
    row = session.execute(
        select(PushBudgetRow)
        .where(PushBudgetRow.user_id == user_id)
        .where(PushBudgetRow.date == date)
    ).scalar_one_or_none()
    if row is None:
        row = PushBudgetRow(
            org_id=org_id,
            user_id=user_id,
            date=date,
            interrupts_used=0,
            max_allowed=PUSH_BUDGET_PER_USER_PER_DAY,
        )
        session.add(row)
        session.flush()
    return row

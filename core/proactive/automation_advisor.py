"""Automation Advisor — B5 of Manager Mode (Diagnose → Manage → DELEGATE).

Detects work the founder keeps doing MANUALLY and proposes automating it via
the org's connected executor (Hermes / any agent on the existing webhook/MCP
dispatch pipe). Signal: the same recommended action was acted on ≥ N times in
the last 30 days — a human clicking the same play repeatedly IS the automation
spec. Pure SQL over feedback_actions × proactive_insights; no LLM.

Emits a proactive_insight (type=opportunity, category=automation) with the
manager voice: "You've handled 'send payment reminder' manually 4× this month —
automate it via your connected agent?" 30-day signature dedupe so the advisor
suggests once, not weekly.
"""

from __future__ import annotations

import hashlib
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.proactive.store import InsightRow

log = get_logger(__name__)

MIN_REPEATS = 3          # same action acted-on this many times in the window…
WINDOW_DAYS = 30         # …within this window → worth automating
SUPPRESS_DAYS = 30       # re-suggest at most monthly


def _sig(action: str) -> str:
    return hashlib.sha256(f"automation_advisor|{action}".encode()).hexdigest()[:32]


def run_automation_advisor(session: Session, *, org_id: str) -> dict[str, Any]:
    """Scan acted-on feedback for repeated manual actions → automation insights."""
    cutoff = datetime.now(UTC) - timedelta(days=WINDOW_DAYS)

    # Repeated manual actions: acted feedback joined to the insight's
    # recommend_action (in scores_jsonb). Grouped in SQL; tiny result set.
    rows = session.execute(
        text("""
            SELECT COALESCE(pi.scores_jsonb->>'recommend_action',
                            pi.scores_jsonb->>'category',
                            pi.type)                       AS action_key,
                   COUNT(*)                                AS n,
                   MAX(pi.scores_jsonb->>'title')          AS sample_title
            FROM feedback_actions fa
            JOIN proactive_insights pi ON pi.id::text = fa.insight_id::text
            WHERE fa.org_id = :org
              AND fa.action = 'acted'
              AND fa.timestamp >= :cutoff
            GROUP BY 1
            HAVING COUNT(*) >= :minr
            ORDER BY n DESC
            LIMIT 5
        """),
        {"org": org_id, "cutoff": cutoff, "minr": MIN_REPEATS},
    ).fetchall()
    if not rows:
        return {"insights_fired": 0, "candidates": 0}

    # Suppress: already suggested within SUPPRESS_DAYS.
    sup_cut = datetime.now(UTC) - timedelta(days=SUPPRESS_DAYS)
    seen = {
        r[0]
        for r in session.execute(
            text("""
                SELECT signature_hash FROM proactive_insights
                WHERE org_id = :org AND created_at >= :cut
                  AND scores_jsonb->>'category' = 'automation'
            """),
            {"org": org_id, "cut": sup_cut},
        ).fetchall()
    }

    fired = 0
    for r in rows:
        action_key = str(r.action_key or "").strip()
        if not action_key:
            continue
        h = _sig(action_key)
        if h in seen:
            continue
        seen.add(h)

        human_action = action_key.replace("_", " ")
        title = f"Automate: {human_action}"
        genios_view = (
            f"You've handled '{human_action}' manually {int(r.n)}× in the last "
            f"{WINDOW_DAYS} days — this is exactly the kind of work your connected "
            f"agent (e.g. Hermes) can run for you. Want me to route future "
            f"'{human_action}' items straight to it, with you reviewing the first few?"
        )
        memory_view = (
            f"'{human_action}' acted on {int(r.n)}× in {WINDOW_DAYS}d "
            f"(e.g. \"{(r.sample_title or '')[:60]}\") — repeated manual work"
        )
        session.add(
            InsightRow(
                id=str(_uuid.uuid4()),
                org_id=org_id,
                type="opportunity",
                primary_entity=human_action,
                root_cause_edge="",
                derivation_chain_jsonb=[{
                    "rule_id": "automation_advisor:repeated_manual_action",
                    "rule_module": "manager",
                    "conclusion": "automatable_repeated_action",
                    "matched_facts": {"action": action_key, "acted_count": int(r.n),
                                      "window_days": WINDOW_DAYS},
                    "reason": genios_view,
                    "hard": False,
                }],
                foresight_jsonb=None,
                scores_jsonb={
                    "rule_id": "automation_advisor:repeated_manual_action",
                    "priority": "medium",
                    "title": title,
                    "category": "automation",
                    "client_name": human_action,
                    "memory_view": memory_view,
                    "genios_view": genios_view,
                    "recommend_action": "configure_auto_dispatch",
                },
                grounding_refs_jsonb=[],
                signature_hash=h,
                delivery_route="notify",
            )
        )
        fired += 1

    log.info("automation_advisor_run", org_id=org_id, candidates=len(rows), fired=fired)
    return {"insights_fired": fired, "candidates": len(rows)}

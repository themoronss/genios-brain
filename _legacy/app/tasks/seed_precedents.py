"""Seed Precedent graph with B2B SaaS situation templates.

Without seeded patterns, Op.04 (Complete Patterns) has nothing to match
against until ~30 days of feedback accumulate. Seeding with generic but
realistic B2B SaaS templates makes pattern detection alive from Day 1.

Templates are conservative: outcome statistics from broad industry priors,
written in a way that gets dwarfed by the org's real data within weeks.
Only seeded once per org (idempotent guard via SELECT count).

Called from the signup path right after tenant creation.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)


# (stage, sentiment_bucket, days_bucket, entity_type, has_overdue_commit,
#  situation_category, sentiment_trend, action_taken, outcome, outcome_days,
#  context_summary)
_TEMPLATES = [
    # Customer / deal lifecycle
    ("ACTIVE", "POSITIVE", "<7", "CUSTOMER", False, "FOLLOW_UP", "STABLE",
     "Sent personalized follow-up referencing prior context",
     "RECOVERED", 3,
     "Engaged customer, recent positive interaction — low-touch follow-up keeps momentum."),
    ("WARM", "NEUTRAL", "7-14", "CUSTOMER", False, "FOLLOW_UP", "STABLE",
     "Direct check-in with specific question or value-add",
     "RECOVERED", 5,
     "Warm customer cooled slightly — direct re-engagement with specifics restores trust."),
    ("NEEDS_ATTENTION", "NEUTRAL", "14-30", "CUSTOMER", True, "DEAL_STUCK", "DECLINING",
     "Escalated via mutual connection or champion's manager",
     "RECOVERED", 9,
     "Stuck mid-funnel customer with overdue commit — escalation through warm path unsticks."),
    ("NEEDS_ATTENTION", "NEGATIVE", "14-30", "CUSTOMER", True, "CHURN_RISK", "DECLINING",
     "CEO-level outreach + concrete remediation offer",
     "RECOVERED", 14,
     "Churn-risk customer responds best to executive sponsorship + tangible action."),
    ("AT_RISK", "NEGATIVE", "30-60", "CUSTOMER", True, "CHURN_RISK", "DECLINING",
     "Save call with full account team + roadmap commit",
     "STALLED", 21,
     "At-risk customer with persistent silence rarely fully recovers without leadership involvement."),
    ("COLD", "NEUTRAL", ">60", "CUSTOMER", False, "COLD_OUTREACH", "STABLE",
     "Re-introduction via warm referral, not cold email",
     "RECOVERED", 18,
     "Cold former customer re-engages best through trusted intermediary, not direct outreach."),

    # Investor lifecycle
    ("ACTIVE", "POSITIVE", "<7", "INVESTOR", False, "FOLLOW_UP", "STABLE",
     "Tight monthly update with specific metrics + clear ask",
     "RECOVERED", 4,
     "Active investor stays engaged through metric-driven, specific updates with clear next step."),
    ("WARM", "NEUTRAL", "7-14", "INVESTOR", False, "DISCOVERY", "STABLE",
     "Send curated opportunity or signal-of-strength update",
     "RECOVERED", 7,
     "Warm investor wants high-signal, low-noise touchpoints. Generic updates miss."),
    ("NEEDS_ATTENTION", "NEUTRAL", "14-30", "INVESTOR", False, "FOLLOW_UP", "DECLINING",
     "Personalized re-engagement referencing their stated thesis",
     "RECOVERED", 12,
     "Drifting investor responds when re-engaged on their own thesis, not generic updates."),
    ("COLD", "NEGATIVE", ">60", "INVESTOR", False, "COLD_OUTREACH", "STABLE",
     "Acknowledge silence, share concrete progress, no ask",
     "STALLED", 30,
     "Cold investor with negative drift rarely returns — accept and shift focus."),

    # Partner / vendor
    ("ACTIVE", "POSITIVE", "<7", "PARTNER", False, "FOLLOW_UP", "STABLE",
     "Joint customer success story or co-marketing thread",
     "RECOVERED", 5,
     "Active partner stays bonded through joint wins, not just operational follow-ups."),
    ("NEEDS_ATTENTION", "NEUTRAL", "14-30", "PARTNER", True, "DEAL_STUCK", "DECLINING",
     "Re-align on roadmap and renegotiate scope",
     "RECOVERED", 15,
     "Stuck partner relationship usually means scope creep — renegotiation is the unlock."),

    # Team / internal
    ("ACTIVE", "POSITIVE", "<7", "TEAM", False, "FOLLOW_UP", "STABLE",
     "Ack + concrete next step within same day",
     "RECOVERED", 1,
     "Internal team momentum needs same-day acknowledgement + clear action."),
    ("NEEDS_ATTENTION", "NEGATIVE", "7-14", "TEAM", True, "DEAL_STUCK", "DECLINING",
     "1:1 conversation to surface blocker, not async ping",
     "RECOVERED", 4,
     "Internal block surfaced via async usually masks something only a sync call resolves."),

    # General
    ("WARM", "POSITIVE", "<7", "OTHER", False, "FOLLOW_UP", "IMPROVING",
     "Match their tone, keep it short, propose concrete next step",
     "RECOVERED", 3,
     "Positive recent contact — match the energy, don't over-engineer the response."),
]


def seed_for_org(org_id: str) -> int:
    """Insert templates for a freshly-created org. Idempotent — skips if any
    precedent_situations row already exists for this org."""
    db = SessionLocal()
    try:
        existing = db.execute(
            text("SELECT COUNT(*) FROM precedent_situations WHERE org_id = :oid"),
            {"oid": org_id},
        ).scalar() or 0
        if existing > 0:
            logger.info(f"seed_precedents skip org={org_id} already has {existing} rows")
            return 0

        rows = 0
        for tpl in _TEMPLATES:
            db.execute(
                text("""
                    INSERT INTO precedent_situations (
                        org_id, stage, sentiment_bucket, days_bucket,
                        entity_type, has_overdue_commit, situation_category,
                        sentiment_trend, action_taken, outcome, outcome_days,
                        context_summary, source
                    ) VALUES (
                        :org_id, :stage, :sb, :db, :et, :hoc, :sc, :st,
                        :at, :oc, :od, :cs, 'seed'
                    )
                """),
                {
                    "org_id": org_id, "stage": tpl[0], "sb": tpl[1], "db": tpl[2],
                    "et": tpl[3], "hoc": tpl[4], "sc": tpl[5], "st": tpl[6],
                    "at": tpl[7], "oc": tpl[8], "od": tpl[9], "cs": tpl[10],
                },
            )
            rows += 1
        db.commit()
        logger.info(f"seed_precedents inserted {rows} templates for org={org_id}")
        return rows
    except Exception as e:
        db.rollback()
        logger.warning(f"seed_precedents failed org={org_id} err={e}")
        return 0
    finally:
        db.close()

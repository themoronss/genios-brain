"""
Insights Engine — Nightly Signal Detection
Per PDF spec §9: ~40 pre-built signal detection queries that run nightly.
Each query has a threshold and priority tier:
  P1 = act within 24h
  P2 = act this week
  P3 = FYI

No LLM involved in detection — all deterministic graph queries.
LLM only writes the human-readable insight sentence on top of the structured result.
"""

from sqlalchemy import text
from uuid import uuid4
from typing import List, Dict
import json

from app.graph.detectors import ALL_DETECTORS


def run_insights_engine(db, org_id: str) -> List[Dict]:
    """
    Run all signal detection queries for an org.
    Clears stale insights and generates fresh ones.
    Returns list of generated insights.
    """
    # Clear old insights (older than 7 days or dismissed)
    db.execute(
        text("""
            DELETE FROM insights
            WHERE org_id = :org_id
            AND (generated_at < NOW() - INTERVAL '7 days' OR is_dismissed = TRUE)
        """),
        {"org_id": org_id}
    )

    insights = []

    # Run each detection query
    for detector in ALL_DETECTORS:
        try:
            new_insights = detector(db, org_id)
            insights.extend(new_insights)
        except Exception as e:
            print(f"⚠️ Insight detector failed: {e}")
            continue

    # Batch insert all insights
    for insight in insights:
        db.execute(
            text("""
                INSERT INTO insights (id, org_id, insight_type, priority, category,
                    title, detail, contact_id, contact_name, metadata, generated_at, expires_at)
                VALUES (:id, :org_id, :insight_type, :priority, :category,
                    :title, :detail, :contact_id, :contact_name, :metadata, NOW(),
                    NOW() + INTERVAL '7 days')
            """),
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "insight_type": insight.get("insight_type", "relationship"),
                "priority": insight.get("priority", "P3"),
                "category": insight.get("category", "general"),
                "title": insight.get("title", ""),
                "detail": insight.get("detail"),
                "contact_id": insight.get("contact_id"),
                "contact_name": insight.get("contact_name"),
                "metadata": json.dumps(insight.get("metadata", {})),
            }
        )

    db.commit()
    print(f"💡 Generated {len(insights)} insights for org {org_id[:8]}")
    return insights

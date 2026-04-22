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
from app.tasks.proactive_scanner import _generate_insight_text


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

    # Batch insert all insights with LLM synthesis
    for insight in insights:
        # Generate memory_view + genios_view via LLM
        try:
            synthesis = _generate_insight_text(
                anomaly={
                    "anomaly_type": insight.get("category", "general"),
                    "summary": insight.get("detail", insight.get("title", "")),
                    "engagement_z": None,
                    "sentiment_z": None,
                },
                contact={
                    "name": insight.get("contact_name", ""),
                    "company": insight.get("metadata", {}).get("company") if isinstance(insight.get("metadata"), dict) else None,
                    "relationship_stage": None,
                    "days_since_last": insight.get("metadata", {}).get("days_since") if isinstance(insight.get("metadata"), dict) else None,
                    "open_commitments": 0,
                },
                precedents=[],
                org_id=org_id,
            )
        except Exception:
            synthesis = {"memory_view": None, "genios_view": None}

        db.execute(
            text("""
                INSERT INTO insights (id, org_id, insight_type, priority, category,
                    title, detail, contact_id, contact_name, metadata, generated_at, expires_at,
                    memory_view, genios_view)
                VALUES (:id, :org_id, :insight_type, :priority, :category,
                    :title, :detail, :contact_id, :contact_name, :metadata, NOW(),
                    NOW() + INTERVAL '7 days', :memory_view, :genios_view)
                ON CONFLICT DO NOTHING
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
                "memory_view": synthesis.get("memory_view"),
                "genios_view": synthesis.get("genios_view"),
            }
        )

    db.commit()
    print(f"💡 Generated {len(insights)} insights for org {org_id[:8]}")
    return insights

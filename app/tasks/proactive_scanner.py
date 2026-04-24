"""
Phase 6: Proactive Intelligence — the scanner.

Per L2 spec: GeniOS fires without asking. No agent called anything.
Every 6h (and on new data events), the scanner:

1. Runs L5 anomaly detection (reuses anomaly_scanner)
2. For each active anomaly, runs L6 root cause analysis
3. Runs L7 synthesis (LLM generates memory_view + genios_view)
4. Stores insight in `insights` table
5. Delivers via webhook (Phase 6.3)

Credits: 0 (included in Startup plan, per L2 spec).
Cost to GeniOS: ~₹0.033 per insight (one Gemini call).
"""
import json
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _compute_priority(
    anomaly_type: str,
    confidence_score: float,
    relationship_stage: str | None,
    open_commitments: int,
    days_since_last: int | None,
) -> str:
    """Dynamic insight priority — closes the outcome → priority loop.

    confidence_score is fed from context_outcomes by confidence_updater, so a
    brain that has been right about this contact promotes its own future
    alerts; one that has been wrong demotes them.
    """
    base = {"gone_silent": 3, "sentiment_drop": 3, "engagement_drop": 2, "response_slowdown": 1}.get(anomaly_type, 2)
    if confidence_score >= 0.7:
        base += 1
    elif confidence_score < 0.3:
        base -= 1
    stage = (relationship_stage or "").upper()
    if stage in ("NEEDS_ATTENTION", "AT_RISK"):
        base += 1
    elif stage in ("DORMANT", "COLD"):
        base -= 1
    if open_commitments and open_commitments >= 2:
        base += 1
    if days_since_last and days_since_last > 90:
        base -= 1
    if base >= 4:
        return "high"
    return "medium" if base >= 2 else "low"


def _generate_insight_text(anomaly: dict, contact: dict, precedents: list, org_id: str = None) -> dict:
    """
    L7 Synthesis: generate memory_view + genios_view from structured data.
    LLM does NOT generate intelligence — it formats intelligence that already exists.
    """
    # Build the structured input for LLM
    root_cause_data = {
        "contact_name": contact.get("name", "Unknown"),
        "company": contact.get("company"),
        "relationship_stage": contact.get("relationship_stage"),
        "anomaly_type": anomaly.get("anomaly_type"),
        "anomaly_summary": anomaly.get("summary"),
        "engagement_z": anomaly.get("engagement_z"),
        "sentiment_z": anomaly.get("sentiment_z"),
        "days_since_last": contact.get("days_since_last"),
        "precedent_count": len(precedents),
        "precedent_success_rate": precedents[0].get("success_rate") if precedents else None,
        "best_historical_action": precedents[0].get("action_taken") if precedents else None,
        "open_commitments": contact.get("open_commitments", 0),
    }

    prompt = f"""You are formatting a relationship intelligence insight. The analysis is already done — you are converting structured data into two readable views.

Structured data:
{json.dumps(root_cause_data, indent=2)}

Generate TWO views:

1. memory_view: ONE sentence. Just the raw fact. What the data shows.
   Example: "No response from Priya in 28 days"

2. genios_view: 2-3 sentences. The analyzed insight with specific recommendation.
   Example: "Wrong person. Priya is the point of contact but Vikram is the actual decision maker. 5 of 6 similar historical situations recovered when the real decision maker was engaged directly. Contact Vikram this week."

Rules:
- Be specific. Use names, numbers, days.
- genios_view must include a concrete action recommendation.
- If precedent data exists, reference the success rate.
- No generic advice. Every sentence must reference the actual data.

Return ONLY valid JSON:
{{"memory_view": "...", "genios_view": "..."}}"""

    try:
        from app.llm import llm_client
        raw = llm_client.call(
            org_id=org_id, purpose="narrative",
            prompt=prompt, temperature=0.2, max_tokens=512,
        )

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        return {
            "memory_view": result.get("memory_view", anomaly.get("summary", "")),
            "genios_view": result.get("genios_view", anomaly.get("summary", "")),
        }
    except Exception as e:
        logger.warning(f"L7 synthesis failed: {e}")
        # Fallback: use the anomaly summary directly
        return {
            "memory_view": anomaly.get("summary", "Unusual activity detected"),
            "genios_view": anomaly.get("summary", "Unusual activity detected") + " Review this contact.",
        }


def run_proactive_scan(org_id: str = None):
    """
    Full proactive scan: anomalies → root cause → synthesis → store insights.

    Per L2 spec: runs every 6h via Celery Beat.
    For Startup plan only (hustler gets reactive only).
    """
    db = SessionLocal()
    try:
        # Step 1: Run anomaly detection (reuse Phase 4)
        from app.tasks.anomaly_scanner import run_anomaly_scan
        anomaly_result = run_anomaly_scan(org_id)
        logger.info(f"Anomaly scan: {anomaly_result}")

        # Step 2: Get all active anomalies that don't have insights yet
        where = "ca.status = 'active'"
        params = {}
        if org_id:
            where += " AND ca.org_id = :org_id"
            params["org_id"] = org_id

        anomalies = db.execute(
            text(f"""
                SELECT ca.id, ca.contact_id, ca.org_id, ca.anomaly_type,
                       ca.engagement_z, ca.sentiment_z, ca.deviation_score,
                       ca.summary,
                       c.name, c.email, c.company, c.relationship_stage,
                       c.entity_type, c.sentiment_ewma, c.sentiment_trend,
                       c.last_interaction_at, c.interaction_count,
                       COALESCE(c.confidence_score, 0.5) AS confidence_score,
                       (SELECT COUNT(*) FROM commitments cm
                        WHERE cm.contact_id = ca.contact_id AND cm.status = 'OPEN'
                       ) AS open_commitments
                FROM contact_anomalies ca
                JOIN contacts c ON ca.contact_id = c.id
                WHERE {where}
                  AND NOT EXISTS (
                      SELECT 1 FROM insights i
                      WHERE i.anomaly_id = ca.id AND i.is_dismissed = FALSE
                  )
                  -- Brain learning: if the user has dismissed >= 2 insights for
                  -- this (contact, anomaly_type) pair within the last 30 days,
                  -- mute it for the cooldown period. The brain treats repeated
                  -- dismissal as a signal that this alert is noise to this user.
                  AND COALESCE((
                      SELECT COUNT(*) FROM insights di
                      JOIN contact_anomalies dca ON di.anomaly_id = dca.id
                      WHERE di.contact_id = ca.contact_id
                        AND dca.anomaly_type = ca.anomaly_type
                        AND di.is_dismissed = TRUE
                        AND di.generated_at > NOW() - INTERVAL '30 days'
                  ), 0) < 2
                  -- Brain judgment: one-way senders (newsletters that got past
                  -- the broadcast filter, e.g. niche programs) shouldn't fire
                  -- relationship-cooling insights — silence is normal there.
                  AND (c.is_bidirectional IS TRUE OR ca.anomaly_type NOT IN ('gone_silent', 'engagement_drop'))
                ORDER BY ca.deviation_score DESC
                LIMIT 20
            """),
            params,
        ).fetchall()

        if not anomalies:
            logger.info("No new anomalies to generate insights for.")
            return {"anomalies": anomaly_result, "insights_generated": 0}

        insights_created = 0
        for anomaly in anomalies:
            # Step 3: L6 — find precedent matches for this contact
            try:
                from app.graph.fingerprint import build_fingerprint, match_precedents
                contact_data = {
                    "relationship_stage": anomaly.relationship_stage,
                    "entity_type": anomaly.entity_type,
                    "sentiment_ewma": float(anomaly.sentiment_ewma or 0),
                    "sentiment_trend": anomaly.sentiment_trend,
                    "last_interaction_at": anomaly.last_interaction_at,
                }
                fp = build_fingerprint(contact_data)
                precedents = match_precedents(db, str(anomaly.org_id), fp)
            except Exception:
                precedents = []

            # Step 4: L7 — synthesize insight text
            days_since = None
            if anomaly.last_interaction_at:
                last_at = anomaly.last_interaction_at
                if hasattr(last_at, "tzinfo") and last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_at).days

            insight_text = _generate_insight_text(
                anomaly={
                    "anomaly_type": anomaly.anomaly_type,
                    "summary": anomaly.summary,
                    "engagement_z": float(anomaly.engagement_z or 0),
                    "sentiment_z": float(anomaly.sentiment_z or 0),
                },
                contact={
                    "name": anomaly.name,
                    "company": anomaly.company,
                    "relationship_stage": anomaly.relationship_stage,
                    "days_since_last": days_since,
                    "open_commitments": anomaly.open_commitments or 0,
                },
                precedents=precedents,
                org_id=str(anomaly.org_id),
            )

            # Step 5: Store insight
            try:
                insight_id = str(uuid4())
                # Map anomaly_type to insight category
                category_map = {
                    "gone_silent": "relationship_cooling",
                    "engagement_drop": "engagement_risk",
                    "sentiment_drop": "sentiment_alert",
                    "response_slowdown": "response_risk",
                }
                priority = _compute_priority(
                    anomaly_type=anomaly.anomaly_type,
                    confidence_score=float(anomaly.confidence_score or 0.5),
                    relationship_stage=anomaly.relationship_stage,
                    open_commitments=int(anomaly.open_commitments or 0),
                    days_since_last=days_since,
                )

                db.execute(
                    text("""
                        INSERT INTO insights
                            (id, org_id, insight_type, priority, category,
                             title, detail, contact_id, contact_name,
                             memory_view, genios_view,
                             anomaly_id, source_type, delivery_status,
                             generated_at, is_dismissed)
                        VALUES
                            (:id, :oid, 'anomaly', :priority, :category,
                             :title, :detail, :cid, :cname,
                             :memory_view, :genios_view,
                             :anomaly_id, 'proactive', 'pending',
                             NOW(), FALSE)
                    """),
                    {
                        "id": insight_id,
                        "oid": str(anomaly.org_id),
                        "priority": priority,
                        "category": category_map.get(anomaly.anomaly_type, "other"),
                        "title": f"{anomaly.name}: {anomaly.anomaly_type.replace('_', ' ')}",
                        "detail": insight_text["genios_view"],
                        "cid": str(anomaly.contact_id),
                        "cname": anomaly.name,
                        "memory_view": insight_text["memory_view"],
                        "genios_view": insight_text["genios_view"],
                        "anomaly_id": str(anomaly.id),
                    },
                )
                db.commit()
                insights_created += 1
            except Exception as e:
                db.rollback()
                logger.warning(f"Failed to store insight for {anomaly.name}: {e}")

        logger.info(f"Proactive scan: {insights_created} insights generated from {len(anomalies)} anomalies")
        return {
            "anomalies": anomaly_result,
            "insights_generated": insights_created,
        }
    finally:
        db.close()

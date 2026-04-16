"""
Phase 4: L5 Anomaly Detection — Z-score against personal baselines.

Per L2 spec:
  - Compare each entity to ITSELF, not global averages.
  - A 14-day gap is normal for monthly investors but alarming for daily contacts.
  - Z-score > 0.8 (configurable) = flag for investigation.

Two-step process:
  1. compute_baselines() — rolling 90-day stats per contact
  2. scan_anomalies()    — compare recent 7-day window vs baseline

Run as Celery Beat task every 6h, or manually after sync.
"""
import logging
import math
import os
from datetime import datetime, timezone

from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Configurable thresholds via env
ANOMALY_THRESHOLD = float(os.getenv("GENIOS_ANOMALY_THRESHOLD", "0.8"))
BASELINE_WINDOW_DAYS = int(os.getenv("GENIOS_BASELINE_WINDOW_DAYS", "90"))
RECENT_WINDOW_DAYS = int(os.getenv("GENIOS_RECENT_WINDOW_DAYS", "7"))
MIN_INTERACTIONS_FOR_BASELINE = int(os.getenv("GENIOS_MIN_INTERACTIONS_BASELINE", "3"))


def compute_baselines(org_id: str = None):
    """
    Step 1: Compute 90-day rolling baselines for all contacts.

    For each contact, calculates:
      - engagement: avg + std of weekly interaction counts
      - sentiment: avg + std of sentiment values
      - response time: avg + std (if available)

    Results written to contact_baselines table (UPSERT).
    """
    db = SessionLocal()
    try:
        where = ""
        params = {"window_days": BASELINE_WINDOW_DAYS, "min_interactions": MIN_INTERACTIONS_FOR_BASELINE}
        if org_id:
            where = "AND c.org_id = :org_id"
            params["org_id"] = org_id

        # Get all contacts with enough interaction history
        rows = db.execute(
            text(f"""
                WITH contact_stats AS (
                    SELECT
                        c.id AS contact_id,
                        c.org_id,
                        COUNT(i.id) AS total_interactions,
                        -- Engagement: weekly interaction count over the window
                        COUNT(i.id)::FLOAT / GREATEST(1, :window_days / 7) AS weekly_avg,
                        -- Sentiment stats
                        AVG(i.sentiment) AS sentiment_avg,
                        STDDEV_POP(i.sentiment) AS sentiment_std,
                        -- Response time (outbound only, where reply_time exists)
                        AVG(i.reply_time_hours) FILTER (WHERE i.reply_time_hours IS NOT NULL) AS response_avg,
                        STDDEV_POP(i.reply_time_hours) FILTER (WHERE i.reply_time_hours IS NOT NULL) AS response_std
                    FROM contacts c
                    JOIN interactions i ON i.contact_id = c.id AND i.org_id = c.org_id
                    WHERE i.interaction_at >= NOW() - (:window_days || ' days')::interval
                      AND (c.is_archived IS FALSE OR c.is_archived IS NULL)
                      {where}
                    GROUP BY c.id, c.org_id
                    HAVING COUNT(i.id) >= :min_interactions
                )
                SELECT contact_id, org_id, total_interactions,
                       weekly_avg, sentiment_avg, sentiment_std,
                       response_avg, response_std
                FROM contact_stats
            """),
            params,
        ).fetchall()

        if not rows:
            logger.info("No contacts with enough data for baselines.")
            return 0

        # We need per-week std dev — compute from weekly buckets
        updated = 0
        for row in rows:
            # Get weekly interaction counts for std dev
            weekly_counts = db.execute(
                text("""
                    SELECT date_trunc('week', interaction_at) AS week,
                           COUNT(*) AS cnt
                    FROM interactions
                    WHERE contact_id = :cid
                      AND interaction_at >= NOW() - (:window || ' days')::interval
                    GROUP BY week
                """),
                {"cid": str(row.contact_id), "window": BASELINE_WINDOW_DAYS},
            ).fetchall()

            counts = [float(w.cnt) for w in weekly_counts]
            n_weeks = max(1, BASELINE_WINDOW_DAYS // 7)

            # Pad with zeros for weeks with no interactions
            while len(counts) < n_weeks:
                counts.append(0.0)

            eng_avg = sum(counts) / len(counts) if counts else 0
            eng_std = math.sqrt(sum((x - eng_avg) ** 2 for x in counts) / len(counts)) if len(counts) > 1 else 0

            db.execute(
                text("""
                    INSERT INTO contact_baselines
                        (contact_id, org_id, engagement_avg, engagement_std,
                         sentiment_avg, sentiment_std,
                         response_time_avg_hours, response_time_std_hours,
                         baseline_window_days, interactions_in_window, computed_at)
                    VALUES
                        (:cid, :oid, :eng_avg, :eng_std,
                         :sent_avg, :sent_std,
                         :resp_avg, :resp_std,
                         :window, :total, NOW())
                    ON CONFLICT (contact_id) DO UPDATE SET
                        org_id = EXCLUDED.org_id,
                        engagement_avg = EXCLUDED.engagement_avg,
                        engagement_std = EXCLUDED.engagement_std,
                        sentiment_avg = EXCLUDED.sentiment_avg,
                        sentiment_std = EXCLUDED.sentiment_std,
                        response_time_avg_hours = EXCLUDED.response_time_avg_hours,
                        response_time_std_hours = EXCLUDED.response_time_std_hours,
                        interactions_in_window = EXCLUDED.interactions_in_window,
                        computed_at = NOW()
                """),
                {
                    "cid": str(row.contact_id),
                    "oid": str(row.org_id),
                    "eng_avg": round(eng_avg, 4),
                    "eng_std": round(eng_std, 4),
                    "sent_avg": round(float(row.sentiment_avg or 0), 4),
                    "sent_std": round(float(row.sentiment_std or 0), 4),
                    "resp_avg": round(float(row.response_avg), 2) if row.response_avg else None,
                    "resp_std": round(float(row.response_std), 2) if row.response_std else None,
                    "window": BASELINE_WINDOW_DAYS,
                    "total": row.total_interactions,
                },
            )
            updated += 1

        db.commit()
        logger.info(f"Baselines computed for {updated} contacts")
        return updated
    finally:
        db.close()


def scan_anomalies(org_id: str = None):
    """
    Step 2: Compare recent 7-day window against baselines.
    Flag contacts where z-score exceeds threshold.

    Z-score formula:
        z = (recent_value - baseline_avg) / (baseline_std + 0.01)

    Combined deviation:
        deviation = abs(engagement_z) * 0.5 + abs(sentiment_z) * 0.5

    If deviation > ANOMALY_THRESHOLD → create anomaly record.
    """
    db = SessionLocal()
    try:
        where = ""
        params = {"recent_days": RECENT_WINDOW_DAYS, "threshold": ANOMALY_THRESHOLD}
        if org_id:
            where = "AND cb.org_id = :org_id"
            params["org_id"] = org_id

        # Get baselines + recent activity for each contact
        rows = db.execute(
            text(f"""
                SELECT
                    cb.contact_id, cb.org_id,
                    cb.engagement_avg, cb.engagement_std,
                    cb.sentiment_avg, cb.sentiment_std,
                    c.name, c.email,
                    -- Recent engagement (interaction count in last N days)
                    (SELECT COUNT(*) FROM interactions i
                     WHERE i.contact_id = cb.contact_id
                       AND i.interaction_at >= NOW() - (:recent_days || ' days')::interval
                    ) AS recent_interaction_count,
                    -- Recent sentiment
                    (SELECT AVG(i.sentiment) FROM interactions i
                     WHERE i.contact_id = cb.contact_id
                       AND i.interaction_at >= NOW() - (:recent_days || ' days')::interval
                       AND i.sentiment IS NOT NULL
                    ) AS recent_sentiment_avg,
                    -- Days since last interaction
                    (SELECT EXTRACT(DAY FROM NOW() - MAX(i.interaction_at))
                     FROM interactions i WHERE i.contact_id = cb.contact_id
                    ) AS days_since_last
                FROM contact_baselines cb
                JOIN contacts c ON cb.contact_id = c.id
                WHERE cb.engagement_avg IS NOT NULL
                  AND cb.interactions_in_window >= {MIN_INTERACTIONS_FOR_BASELINE}
                  {where}
            """),
            params,
        ).fetchall()

        flagged = 0
        for row in rows:
            eng_avg = row.engagement_avg or 0
            eng_std = max(row.engagement_std or 0, 0.01)
            sent_avg = row.sentiment_avg or 0
            sent_std = max(row.sentiment_std or 0, 0.01)

            # Normalize recent engagement to weekly rate
            recent_weekly = (row.recent_interaction_count or 0) * (7.0 / max(1, RECENT_WINDOW_DAYS))

            # Z-scores
            engagement_z = (recent_weekly - eng_avg) / eng_std
            sentiment_z = 0.0
            if row.recent_sentiment_avg is not None:
                sentiment_z = (float(row.recent_sentiment_avg) - sent_avg) / sent_std

            # Combined deviation (weighted)
            deviation = abs(engagement_z) * 0.5 + abs(sentiment_z) * 0.5

            if deviation < ANOMALY_THRESHOLD:
                continue

            # Determine anomaly type
            if engagement_z < -1.0 and (row.days_since_last or 0) > 14:
                anomaly_type = "gone_silent"
                summary = f"{row.name} has gone silent — {int(row.days_since_last or 0)}d since last interaction, {abs(engagement_z):.1f} std devs below normal engagement"
            elif engagement_z < -0.8:
                anomaly_type = "engagement_drop"
                summary = f"{row.name}'s engagement dropped {abs(engagement_z):.1f} std devs below their normal pattern"
            elif sentiment_z < -0.8:
                anomaly_type = "sentiment_drop"
                summary = f"{row.name}'s sentiment has declined {abs(sentiment_z):.1f} std devs — relationship may be cooling"
            else:
                anomaly_type = "engagement_drop"
                summary = f"{row.name} shows unusual activity pattern (deviation: {deviation:.2f})"

            # Upsert anomaly (only if not already active for this type)
            try:
                db.execute(
                    text("""
                        INSERT INTO contact_anomalies
                            (contact_id, org_id, anomaly_type, engagement_z, sentiment_z,
                             deviation_score, summary, status, detected_at)
                        VALUES
                            (:cid, :oid, :atype, :eng_z, :sent_z,
                             :deviation, :summary, 'active', NOW())
                        ON CONFLICT (contact_id, anomaly_type, status)
                        DO UPDATE SET
                            engagement_z = EXCLUDED.engagement_z,
                            sentiment_z = EXCLUDED.sentiment_z,
                            deviation_score = EXCLUDED.deviation_score,
                            summary = EXCLUDED.summary,
                            detected_at = NOW()
                    """),
                    {
                        "cid": str(row.contact_id),
                        "oid": str(row.org_id),
                        "atype": anomaly_type,
                        "eng_z": round(engagement_z, 3),
                        "sent_z": round(sentiment_z, 3),
                        "deviation": round(deviation, 3),
                        "summary": summary,
                    },
                )
                flagged += 1
            except Exception as e:
                logger.debug(f"Anomaly upsert failed for {row.email}: {e}")
                db.rollback()
                continue

        db.commit()

        # Auto-resolve anomalies where deviation dropped below threshold
        resolved = db.execute(
            text(f"""
                UPDATE contact_anomalies
                SET status = 'resolved', resolved_at = NOW()
                WHERE status = 'active'
                  AND contact_id NOT IN (
                      SELECT contact_id FROM contact_anomalies
                      WHERE status = 'active' AND deviation_score >= :threshold
                  )
                  {'AND org_id = :org_id' if org_id else ''}
            """),
            params,
        ).rowcount
        db.commit()

        logger.info(f"Anomaly scan: {flagged} flagged, {resolved} auto-resolved")
        return {"flagged": flagged, "resolved": resolved}
    finally:
        db.close()


def run_anomaly_scan(org_id: str = None):
    """Full scan: compute baselines → detect anomalies. Run every 6h."""
    logger.info(f"Starting anomaly scan for {'org ' + org_id if org_id else 'all orgs'}...")
    baselines = compute_baselines(org_id)
    results = scan_anomalies(org_id)
    logger.info(f"Anomaly scan complete: {baselines} baselines, {results['flagged']} flagged, {results['resolved']} resolved")
    return {"baselines_computed": baselines, **results}

"""Personal baseline writer — populates `personal_baselines` per contact.

Without per-contact baselines every detector compares against population
averages, which makes "27 days silence" meaningless (normal for some,
alarming for others). This task computes the rolling mean + stddev for a
small set of metrics over a 90-day window and upserts them into the
personal_baselines table.

Runs nightly. Reads interactions, writes baselines. Read-only on contacts.

Metrics produced per contact:
  - response_hours : mean hours from inbound → next outbound for this contact
  - email_words    : mean word count of inbound messages from this contact

Sentiment baselines already exist on contacts.sentiment_ewma — no need to
duplicate. Add new metrics here as they become useful.

Detectors can call `app.graph.baselines.get_baseline(...)` to fetch and
compute z-scores against personal data instead of absolute thresholds.
"""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 90
_MIN_SAMPLES = 3  # below this, the baseline isn't statistically meaningful


def run_baseline_writer(org_id: str | None = None) -> dict:
    """Recompute baselines for all (or one org's) contacts. Returns counters."""
    db = SessionLocal()
    try:
        counts = {
            "response_hours": _refresh_response_hours(db, org_id),
            "email_words":    _refresh_email_words(db, org_id),
        }
        db.commit()
        logger.info(f"baseline_writer org={org_id or 'all'} counts={counts}")
        return counts
    except Exception as e:
        db.rollback()
        logger.exception(f"baseline_writer failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()


def _upsert_metric(db: Session, metric: str, sql: str, params: dict) -> int:
    """Run an aggregate SELECT, then UPSERT the rows into personal_baselines."""
    rows = db.execute(text(sql), params).fetchall()
    if not rows:
        return 0
    written = 0
    for r in rows:
        if r.samples is None or int(r.samples) < _MIN_SAMPLES:
            continue
        db.execute(
            text("""
                INSERT INTO personal_baselines
                    (org_id, contact_id, metric, value, stddev, samples, updated_at)
                VALUES (:oid, :cid, :metric, :val, :std, :n, NOW())
                ON CONFLICT (org_id, contact_id, metric) DO UPDATE SET
                    value = EXCLUDED.value,
                    stddev = EXCLUDED.stddev,
                    samples = EXCLUDED.samples,
                    updated_at = NOW()
            """),
            {
                "oid": str(r.org_id),
                "cid": str(r.contact_id),
                "metric": metric,
                "val": float(r.value or 0),
                "std": float(r.stddev or 0),
                "n": int(r.samples),
            },
        )
        written += 1
    return written


def _refresh_response_hours(db: Session, org_id: str | None) -> int:
    """Per-contact median hours between inbound and the user's next outbound.
    Uses a self-join on interactions ordered by time.
    """
    where_org = "AND org_id = :oid" if org_id else ""
    sql = f"""
        WITH inbound AS (
            SELECT id, org_id, contact_id, interaction_at
            FROM interactions
            WHERE direction = 'inbound'
              AND interaction_at > NOW() - (INTERVAL '1 day' * :lookback)
              {where_org}
        ),
        paired AS (
            SELECT i.org_id, i.contact_id,
                   EXTRACT(EPOCH FROM (
                       (SELECT MIN(o.interaction_at) FROM interactions o
                        WHERE o.contact_id = i.contact_id
                          AND o.direction = 'outbound'
                          AND o.interaction_at > i.interaction_at
                          AND o.interaction_at < i.interaction_at + INTERVAL '14 days'
                       ) - i.interaction_at
                   )) / 3600.0 AS hours_to_reply
            FROM inbound i
        )
        SELECT org_id, contact_id,
               AVG(hours_to_reply)::numeric(10,3)    AS value,
               COALESCE(STDDEV(hours_to_reply), 0)::numeric(10,3) AS stddev,
               COUNT(hours_to_reply)                  AS samples
        FROM paired
        WHERE hours_to_reply IS NOT NULL
        GROUP BY org_id, contact_id
    """
    params = {"lookback": _LOOKBACK_DAYS}
    if org_id:
        params["oid"] = org_id
    return _upsert_metric(db, "response_hours", sql, params)


def _refresh_email_words(db: Session, org_id: str | None) -> int:
    """Mean word count of inbound emails from each contact."""
    where_org = "AND org_id = :oid" if org_id else ""
    sql = f"""
        SELECT org_id, contact_id,
               AVG(GREATEST(1, array_length(regexp_split_to_array(
                   COALESCE(raw_body, summary, ''), '\\s+'), 1)))::numeric(10,3) AS value,
               COALESCE(STDDEV(array_length(regexp_split_to_array(
                   COALESCE(raw_body, summary, ''), '\\s+'), 1)), 0)::numeric(10,3) AS stddev,
               COUNT(*) AS samples
        FROM interactions
        WHERE direction = 'inbound'
          AND interaction_at > NOW() - (INTERVAL '1 day' * :lookback)
          {where_org}
        GROUP BY org_id, contact_id
    """
    params = {"lookback": _LOOKBACK_DAYS}
    if org_id:
        params["oid"] = org_id
    return _upsert_metric(db, "email_words", sql, params)



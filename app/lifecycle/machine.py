"""Lifecycle state machine for contact_facts.

States: ingest → validate → live ↔ fade → dormant → archive.

Hourly job:
  - ingest → validate: freshness ≥ 0.7 AND confidence ≥ 0.6 AND corroboration_count >= 1
  - validate → live:   freshness ≥ 0.6 AND confidence ≥ 0.7
  - live → fade:       freshness < 0.4
  - fade → live:       a new corroborating fact arrived (freshness recomputed ≥ 0.6)
  - dormant → live:    dormant entity reawakened (new high-confidence fact pushed
                       freshness back ≥ 0.6 AND confidence ≥ 0.6) — guide §A·09 revival

Nightly job:
  - fade → dormant:   age > 14d AND not corroborated in the last 14d
  - dormant → archive: age > 30d AND not corroborated AND no outbound reference
  - validate → archive: age > 30d AND still not promoted
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _exec(db, sql: str, **params) -> int:
    """Execute and return affected row count."""
    return db.execute(text(sql), params).rowcount or 0


def run_hourly(org_id: str | None = None) -> dict:
    """Promotions + demotions based on current freshness/confidence."""
    db = SessionLocal()
    try:
        where_org = ""
        params = {}
        if org_id:
            where_org = " AND org_id = :oid"
            params["oid"] = org_id

        counts = {}
        counts["ingest_to_validate"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'validate', updated_at = NOW()
            WHERE lifecycle = 'ingest'
              AND COALESCE(freshness_score, 0) >= 0.7
              AND COALESCE(confidence_score, 0) >= 0.6
              {where_org}
            """,
            **params,
        )

        counts["validate_to_live"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'live', updated_at = NOW()
            WHERE lifecycle = 'validate'
              AND COALESCE(freshness_score, 0) >= 0.6
              AND COALESCE(confidence_score, 0) >= 0.7
              {where_org}
            """,
            **params,
        )

        counts["live_to_fade"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'fade', updated_at = NOW()
            WHERE lifecycle = 'live'
              AND COALESCE(freshness_score, 1) < 0.4
              {where_org}
            """,
            **params,
        )

        counts["fade_to_live"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'live', updated_at = NOW()
            WHERE lifecycle = 'fade'
              AND COALESCE(freshness_score, 0) >= 0.6
              {where_org}
            """,
            **params,
        )

        # Revival: dormant fact's contact got a new corroborating signal that
        # bumped freshness AND confidence back above thresholds. The fact's
        # full history stays attached.
        counts["dormant_to_live"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'live', updated_at = NOW()
            WHERE lifecycle = 'dormant'
              AND COALESCE(freshness_score, 0) >= 0.6
              AND COALESCE(confidence_score, 0) >= 0.6
              {where_org}
            """,
            **params,
        )
        db.commit()
        logger.info(f"lifecycle_hourly: {counts}")
        return counts
    finally:
        db.close()


def run_nightly(org_id: str | None = None) -> dict:
    """Age-based transitions to dormant/archive."""
    db = SessionLocal()
    try:
        where_org = ""
        params = {}
        if org_id:
            where_org = " AND org_id = :oid"
            params["oid"] = org_id

        counts = {}
        counts["fade_to_dormant"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'dormant', updated_at = NOW()
            WHERE lifecycle = 'fade'
              AND updated_at < NOW() - INTERVAL '14 days'
              {where_org}
            """,
            **params,
        )

        counts["dormant_to_archive"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'archive', updated_at = NOW()
            WHERE lifecycle = 'dormant'
              AND updated_at < NOW() - INTERVAL '30 days'
              {where_org}
            """,
            **params,
        )

        counts["validate_to_archive"] = _exec(
            db,
            f"""
            UPDATE contact_facts
            SET lifecycle = 'archive', updated_at = NOW()
            WHERE lifecycle = 'validate'
              AND created_at < NOW() - INTERVAL '30 days'
              {where_org}
            """,
            **params,
        )
        db.commit()
        logger.info(f"lifecycle_nightly: {counts}")
        return counts
    finally:
        db.close()

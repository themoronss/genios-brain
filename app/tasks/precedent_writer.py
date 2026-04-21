"""
Precedent writer — turns recommendation outcomes into learnable precedents.

Every time a recommendation gets `outcome=acted/dismissed/ignored`, that's a
tuple of (situation, action, outcome) the system should remember. The
existing fingerprint.record_stage_transition() writer only fires on stage
changes and ignores the much richer signal of "did the agent act on this?".

This writer:
- Queries `recommendations` with an outcome AND created_at after last run
- Also back-stops pending recs older than STALE_AFTER_DAYS as STALLED
- For each, builds a precedent_situations row reusing the existing
  fingerprint builder (stage, sentiment_bucket, days_bucket, entity_type, …)
- Maps outcome → RECOVERED / STALLED / NO_CHANGE

Runs nightly at 4am via Celery beat. Idempotent: tracks last-run watermark
in Redis under `precedent_writer:last_run:{org_id}` so replay doesn't create
duplicates.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
STALE_AFTER_DAYS = int(os.getenv("GENIOS_PRECEDENT_STALE_DAYS", "7"))
BATCH_SIZE = 500
_WATERMARK_KEY = "precedent_writer:last_run:{}"
_WATERMARK_TTL = 60 * 60 * 24 * 90  # 90 days safety net


# ── Outcome mapping ──────────────────────────────────────────────────────────
# recommendations.outcome  →  precedent_situations.outcome
# - acted:     user/agent followed through on the suggested action
# - dismissed: explicitly rejected (agent decided not to act)
# - ignored:   no response at all within window
_OUTCOME_MAP = {
    "acted": "RECOVERED",
    "dismissed": "NO_CHANGE",
    "ignored": "STALLED",
}


def run_precedent_writer(org_id: str | None = None) -> dict:
    """Harvest recommendation outcomes → precedent_situations."""
    db = SessionLocal()
    counters = {"processed": 0, "written": 0, "skipped": 0, "stalled_backfill": 0}
    try:
        orgs: list[str]
        if org_id:
            orgs = [org_id]
        else:
            orgs = [
                str(r[0])
                for r in db.execute(
                    text("""
                        SELECT DISTINCT org_id FROM recommendations
                        WHERE outcome IS NOT NULL OR created_at > NOW() - INTERVAL '14 days'
                    """)
                ).fetchall()
            ]

        for oid in orgs:
            since = _watermark_get(oid)
            rows = _fetch_labelled_recs(db, oid, since)
            counters["processed"] += len(rows)
            for r in rows:
                ok = _write_precedent(db, r)
                if ok:
                    counters["written"] += 1
                else:
                    counters["skipped"] += 1

            # Back-stop: mark very-old pending recs as STALLED precedents so
            # we don't miss the "agent never responded" signal.
            stalled_rows = _fetch_stale_pending(db, oid, STALE_AFTER_DAYS)
            for r in stalled_rows:
                r = dict(r._mapping)
                r["outcome"] = "ignored"  # imputed
                ok = _write_precedent(db, r)
                if ok:
                    counters["stalled_backfill"] += 1

            _watermark_set(oid)

        logger.info(f"precedent_writer done org={org_id or 'all'} {counters}")
        return counters
    finally:
        db.close()


# ── Internal ──────────────────────────────────────────────────────────────────


def _watermark_get(org_id: str) -> datetime:
    try:
        raw = redis_client.get(_WATERMARK_KEY.format(org_id))
        if raw:
            return datetime.fromisoformat(raw)
    except Exception:
        pass
    # Default: 14 days back on first run
    return datetime.now(timezone.utc) - timedelta(days=14)


def _watermark_set(org_id: str) -> None:
    try:
        redis_client.setex(
            _WATERMARK_KEY.format(org_id),
            _WATERMARK_TTL,
            datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        pass


def _fetch_labelled_recs(db: Session, org_id: str, since: datetime) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT
                r.id              AS rec_id,
                r.org_id,
                r.subject_entity_id AS contact_id,
                r.insight_type,
                r.action,
                r.outcome,
                r.confidence,
                r.priority,
                COALESCE(r.outcome_at, r.created_at) AS event_at
            FROM recommendations r
            WHERE r.org_id = :oid
              AND r.outcome IS NOT NULL
              AND COALESCE(r.outcome_at, r.created_at) > :since
            ORDER BY event_at ASC
            LIMIT :lim
        """),
        {"oid": org_id, "since": since, "lim": BATCH_SIZE},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def _fetch_stale_pending(db: Session, org_id: str, stale_days: int) -> list:
    """Pending recs older than `stale_days` and not yet harvested."""
    return db.execute(
        text("""
            SELECT
                r.id              AS rec_id,
                r.org_id,
                r.subject_entity_id AS contact_id,
                r.insight_type,
                r.action,
                r.confidence,
                r.priority,
                r.created_at      AS event_at
            FROM recommendations r
            WHERE r.org_id = :oid
              AND r.outcome IS NULL
              AND r.created_at < NOW() - CAST(:stale AS interval)
              AND NOT EXISTS (
                  SELECT 1 FROM precedent_situations ps
                  WHERE ps.org_id = r.org_id
                    AND ps.context_summary LIKE '%rec=' || r.id::text || '%'
              )
            ORDER BY r.created_at ASC
            LIMIT 200
        """),
        {"oid": org_id, "stale": f"{stale_days} days"},
    ).fetchall()


def _write_precedent(db: Session, rec: dict) -> bool:
    """Build a precedent_situations row from a recommendation + its contact."""
    contact_id = rec.get("contact_id")
    if not contact_id:
        return False

    contact = db.execute(
        text("""
            SELECT id, org_id, name, entity_type, relationship_stage,
                   sentiment_ewma, sentiment_trend, last_interaction_at,
                   stage_changed_at
            FROM contacts
            WHERE id = :cid
        """),
        {"cid": contact_id},
    ).fetchone()
    if not contact:
        return False

    contact = dict(contact._mapping)

    # Reuse the existing fingerprint encoder so precedents stay consistent
    # with the one populated by stage transitions.
    try:
        from app.graph.fingerprint import build_fingerprint
        fp = build_fingerprint(contact, situation_type=rec.get("insight_type"))
    except Exception as e:
        logger.debug(f"fingerprint build failed rec={rec.get('rec_id')}: {e}")
        return False

    outcome_token = _OUTCOME_MAP.get(rec.get("outcome"), "NO_CHANGE")

    # Only write when this recommendation hasn't already been harvested.
    # We encode the rec_id in `context_summary` so duplicates are idempotent.
    rec_id = str(rec.get("rec_id"))
    try:
        db.execute(
            text("""
                INSERT INTO precedent_situations
                    (org_id, contact_id, stage, sentiment_bucket, days_bucket,
                     entity_type, has_overdue_commit, situation_category,
                     sentiment_trend, action_taken, outcome, outcome_days,
                     context_summary, source)
                SELECT :oid, :cid, :stage, :sb, :db, :et, :hoc, :sc, :st,
                       :action, :outcome, NULL, :summary, 'recommendation_outcome'
                WHERE NOT EXISTS (
                    SELECT 1 FROM precedent_situations
                    WHERE org_id = :oid
                      AND context_summary LIKE :dup_probe
                )
            """),
            {
                "oid": str(contact["org_id"]),
                "cid": str(contact_id),
                "stage": fp["stage"],
                "sb": fp["sentiment_bucket"],
                "db": fp["days_bucket"],
                "et": fp["entity_type"],
                "hoc": fp["has_overdue_commit"],
                "sc": fp["situation_category"] or rec.get("insight_type"),
                "st": fp["sentiment_trend"],
                "action": rec.get("action"),
                "outcome": outcome_token,
                "summary": f"{contact.get('name', 'Unknown')} [rec={rec_id}] {outcome_token}",
                "dup_probe": f"%rec={rec_id}%",
            },
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.debug(f"precedent insert failed rec={rec_id}: {e}")
        return False

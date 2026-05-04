"""
Phase 6: Churn scanner — daily engagement_health snapshot writer.

For each org:
  1. Compute api_calls_7d + api_calls_prev_7d (from context_calls)
  2. Compute dismiss_rate_30d (from recommendations.outcome)
  3. Compute last_login_at + sentiment_avg + sync_errors_7d
  4. Score:
       hard   = sync errors persisting + cancel keyword in support
       soft   = api_calls drop >50% WoW + dismiss_rate >0.7 + login>7d
       context= recent complaints alignment
       churn  = 0.5*hard + 0.3*soft + 0.2*context (clamped 0..1)
  5. UPSERT row in engagement_health (one per org per day)

Detector then reads the row in the next router cycle.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _compute_for_org(db, org_id: str) -> dict:
    """Compute and UPSERT one snapshot for one org. Returns the computed dict."""
    # ── API calls 7d / prev 7d ───────────────────────────────────────────
    api_7d = db.execute(
        text("""
            SELECT COUNT(*) FROM context_calls
            WHERE org_id = :oid
              AND called_at >= NOW() - INTERVAL '7 days'
        """),
        {"oid": org_id},
    ).scalar() or 0

    api_prev_7d = db.execute(
        text("""
            SELECT COUNT(*) FROM context_calls
            WHERE org_id = :oid
              AND called_at >= NOW() - INTERVAL '14 days'
              AND called_at <  NOW() - INTERVAL '7 days'
        """),
        {"oid": org_id},
    ).scalar() or 0

    # ── Dismiss rate over recommendations (last 30d) ─────────────────────
    rec = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE outcome IS NOT NULL) AS labeled,
                COUNT(*) FILTER (WHERE outcome = 'dismissed' OR outcome = 'ignored') AS dismissed
            FROM recommendations
            WHERE org_id = :oid AND created_at >= NOW() - INTERVAL '30 days'
        """),
        {"oid": org_id},
    ).fetchone()
    labeled = int(rec.labeled or 0) if rec else 0
    dismissed = int(rec.dismissed or 0) if rec else 0
    dismiss_rate = (dismissed / labeled) if labeled >= 5 else 0.0

    # ── Last login (best-effort — orgs.last_login_at if exists) ──────────
    # Each best-effort query is wrapped + rolled-back individually so a
    # missing column doesn't poison the rest of the transaction.
    last_login = None
    try:
        row = db.execute(
            text("SELECT last_login_at FROM orgs WHERE id = :oid"),
            {"oid": org_id},
        ).fetchone()
        last_login = row[0] if row else None
    except Exception:
        try: db.rollback()
        except Exception: pass
        last_login = None

    # ── Sync errors in last 7d ───────────────────────────────────────────
    sync_errors = 0
    try:
        sync_errors = db.execute(
            text("""
                SELECT COUNT(*) FROM oauth_tokens
                WHERE org_id = :oid AND sync_status = 'error'
            """),
            {"oid": org_id},
        ).scalar() or 0
    except Exception:
        try: db.rollback()
        except Exception: pass

    # ── Sentiment avg over recent contacts ───────────────────────────────
    sentiment_avg = 0.0
    try:
        s = db.execute(
            text("""
                SELECT COALESCE(AVG(sentiment_ewma), 0.0)
                FROM contacts
                WHERE org_id = :oid AND last_interaction_at >= NOW() - INTERVAL '14 days'
            """),
            {"oid": org_id},
        ).scalar()
        sentiment_avg = float(s or 0.0)
    except Exception:
        try: db.rollback()
        except Exception: pass

    # ── Score breakdown ──────────────────────────────────────────────────
    hard = 0.0
    if sync_errors >= 2:
        hard += 0.5
    if last_login is None or (
        datetime.now(timezone.utc)
        - (last_login if last_login.tzinfo else last_login.replace(tzinfo=timezone.utc))
    ).days > 14:
        hard += 0.3
    hard = min(1.0, hard)

    soft = 0.0
    if api_prev_7d > 0:
        delta = (api_7d - api_prev_7d) / max(1, api_prev_7d)
        if delta < -0.5:  # dropped more than 50%
            soft += 0.4
        elif delta < -0.2:
            soft += 0.2
    if dismiss_rate >= 0.7:
        soft += 0.4
    elif dismiss_rate >= 0.5:
        soft += 0.2
    soft = min(1.0, soft)

    context_score = 0.0
    if sentiment_avg < -0.2:
        context_score += 0.4
    elif sentiment_avg < 0.0:
        context_score += 0.2
    context_score = min(1.0, context_score)

    churn = round(min(1.0, 0.5 * hard + 0.3 * soft + 0.2 * context_score), 4)

    payload = {
        "api_calls_7d": int(api_7d),
        "api_calls_prev_7d": int(api_prev_7d),
        "dismiss_rate_30d": round(dismiss_rate, 4),
        "sync_errors_7d": int(sync_errors),
        "sentiment_avg": round(sentiment_avg, 4),
        "last_login_at": last_login.isoformat() if last_login else None,
    }

    db.execute(
        text("""
            INSERT INTO engagement_health (
                org_id, snapshot_date,
                api_calls_7d, api_calls_prev_7d, dismiss_rate_30d,
                last_login_at, sentiment_avg, sync_errors_7d,
                hard_signal_score, soft_signal_score, context_signal_score,
                churn_score, signals_payload
            ) VALUES (
                :oid, CURRENT_DATE,
                :a7, :ap7, :dr,
                :ll, :sa, :se,
                :hs, :ss, :cs,
                :ch, CAST(:p AS jsonb)
            )
            ON CONFLICT (org_id, snapshot_date) DO UPDATE SET
                api_calls_7d = EXCLUDED.api_calls_7d,
                api_calls_prev_7d = EXCLUDED.api_calls_prev_7d,
                dismiss_rate_30d = EXCLUDED.dismiss_rate_30d,
                last_login_at = EXCLUDED.last_login_at,
                sentiment_avg = EXCLUDED.sentiment_avg,
                sync_errors_7d = EXCLUDED.sync_errors_7d,
                hard_signal_score = EXCLUDED.hard_signal_score,
                soft_signal_score = EXCLUDED.soft_signal_score,
                context_signal_score = EXCLUDED.context_signal_score,
                churn_score = EXCLUDED.churn_score,
                signals_payload = EXCLUDED.signals_payload
        """),
        {
            "oid": org_id,
            "a7": int(api_7d), "ap7": int(api_prev_7d), "dr": dismiss_rate,
            "ll": last_login, "sa": sentiment_avg, "se": int(sync_errors),
            "hs": hard, "ss": soft, "cs": context_score,
            "ch": churn, "p": json.dumps(payload),
        },
    )
    db.commit()

    return {
        "org_id": org_id,
        "churn_score": churn,
        "hard": hard, "soft": soft, "context": context_score,
        "payload": payload,
    }


def run_churn_scan(org_id: str | None = None) -> dict:
    """Compute snapshots for one or all orgs. Best-effort; per-org failures
    don't break the run."""
    db = SessionLocal()
    out = {"computed": 0, "failed": 0, "high_risk": []}
    try:
        if org_id:
            org_ids = [org_id]
        else:
            rows = db.execute(text("SELECT id FROM orgs")).fetchall()
            org_ids = [str(r[0]) for r in rows]

        for oid in org_ids:
            try:
                res = _compute_for_org(db, oid)
                out["computed"] += 1
                if res["churn_score"] >= 0.6:
                    out["high_risk"].append({
                        "org_id": oid,
                        "churn_score": res["churn_score"],
                    })
            except Exception as e:
                out["failed"] += 1
                logger.warning(f"churn_scan failed for {oid}: {e}")
                try: db.rollback()
                except Exception: pass
    finally:
        db.close()
    logger.info(f"churn_scan done: {out['computed']} computed, "
                f"{len(out['high_risk'])} high risk")
    return out

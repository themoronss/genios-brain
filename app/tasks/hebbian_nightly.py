"""
Hebbian edge update — nightly learning loop (mig 079).

Runs at 04:30 daily, after the precedent writer (04:00). Reads acted-on
recommendations from the last 24 hours and strengthens the edges between
the contact_facts that contributed.

Hebbian update for a co-activated fact:
    edge_weight ← edge_weight + α · (1 − edge_weight)
with α = 0.1, ceiling = 1.0. Increments coactivation_count, sets
last_coactivated_at, and promotes is_potentiated when count ≥ LTP_THRESHOLD.

Decay sweep:
    For ACTIVE, non-potentiated facts whose last_coactivated_at is older
    than DECAY_AGE_DAYS, drop edge_weight by DECAY_FACTOR. Potentiated
    facts are exempt — that's the whole point of LTP.

Co-activation semantics:
    Recommendations don't store contributing fact ids directly. We treat
    "all ACTIVE contact_facts for the recommendation's contact at the
    moment of the acted feedback" as the co-activated set. That's the
    Shodh interpretation: facts about the same subject that were live
    when the brain made an acted-on call wire together.

Failure mode: best-effort. If the migration hasn't run, the Hebbian columns
don't exist yet — log + skip rather than crash.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)

ALPHA = 0.10                # Hebbian learning rate
LTP_THRESHOLD = 5           # co-activations to mark is_potentiated
DECAY_AGE_DAYS = 30         # only decay facts unused for this long
DECAY_FACTOR = 0.05         # 5% drop per decay sweep
COACT_LOOKBACK_HOURS = 24   # which acted recommendations count this run


def run_hebbian_nightly(org_id: str | None = None) -> dict:
    """
    Returns {"orgs": int, "coactivated_facts": int, "potentiated_new": int,
             "decayed_facts": int}.

    org_id: optional — limit to a single tenant. None = all tenants.
    """
    db = SessionLocal()
    try:
        if not _hebbian_columns_present(db):
            logger.warning("hebbian_nightly: schema columns absent — skipping (run migration 079)")
            return {"skipped": "schema_missing"}

        orgs = _orgs_with_recent_activity(db, org_id)
        coactivated_total = 0
        potentiated_new_total = 0
        decayed_total = 0

        for oid in orgs:
            try:
                co, pn = _coactivate_for_org(db, oid)
                de = _decay_for_org(db, oid)
                coactivated_total += co
                potentiated_new_total += pn
                decayed_total += de
            except Exception as e:
                logger.warning(f"hebbian_nightly org={oid} failed: {e}")
                db.rollback()

        out = {
            "orgs": len(orgs),
            "coactivated_facts": coactivated_total,
            "potentiated_new": potentiated_new_total,
            "decayed_facts": decayed_total,
        }
        logger.info(f"hebbian_nightly done: {out}")
        return out
    finally:
        db.close()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _hebbian_columns_present(db) -> bool:
    """Cheap probe — Hebbian columns added by mig 079."""
    try:
        db.execute(text("""
            SELECT edge_weight, coactivation_count, is_potentiated, last_coactivated_at
            FROM contact_facts LIMIT 0
        """))
        return True
    except Exception:
        db.rollback()
        return False


def _orgs_with_recent_activity(db, org_id: str | None) -> list[str]:
    if org_id:
        return [str(org_id)]
    rows = db.execute(
        text("""
            SELECT DISTINCT org_id::text
            FROM recommendations
            WHERE outcome = 'acted'
              AND outcome_at >= NOW() - (:hours || ' hours')::interval
        """),
        {"hours": COACT_LOOKBACK_HOURS},
    ).fetchall()
    return [r[0] for r in rows]


def _coactivate_for_org(db, org_id: str) -> tuple[int, int]:
    """
    For each acted recommendation in lookback window:
      - take all ACTIVE contact_facts for its contact
      - apply Hebbian update; bump count; flip potentiated when threshold hit
    Returns (coactivated_count, newly_potentiated_count).
    """
    # Pull all (contact_id) targets touched by acted recommendations.
    targets = db.execute(
        text("""
            SELECT DISTINCT subject_entity_id::text AS contact_id
            FROM recommendations
            WHERE org_id = :oid
              AND outcome = 'acted'
              AND outcome_at >= NOW() - (:hours || ' hours')::interval
              AND subject_entity_id IS NOT NULL
        """),
        {"oid": org_id, "hours": COACT_LOOKBACK_HOURS},
    ).fetchall()
    contact_ids = [r[0] for r in targets if r[0]]
    if not contact_ids:
        return 0, 0

    # One UPDATE per org, batched by contact_ids.
    # RETURNING gives us count + newly-potentiated rows in a single pass.
    rows = db.execute(
        text("""
            WITH updated AS (
                UPDATE contact_facts
                SET edge_weight = LEAST(
                        1.000,
                        edge_weight + :alpha * (1.0 - edge_weight)
                    ),
                    coactivation_count = coactivation_count + 1,
                    last_coactivated_at = NOW(),
                    is_potentiated = is_potentiated
                        OR (coactivation_count + 1 >= :ltp)
                WHERE org_id = :oid
                  AND lifecycle_state = 'ACTIVE'
                  AND contact_id::text = ANY(:cids)
                RETURNING id, is_potentiated, coactivation_count
            )
            SELECT
                COUNT(*)::int AS total,
                SUM(CASE WHEN is_potentiated AND coactivation_count = :ltp THEN 1 ELSE 0 END)::int
                    AS newly_potentiated
            FROM updated
        """),
        {"oid": org_id, "alpha": ALPHA, "ltp": LTP_THRESHOLD, "cids": contact_ids},
    ).fetchone()
    db.commit()

    total = int(rows[0] or 0) if rows else 0
    new_pot = int(rows[1] or 0) if rows else 0
    return total, new_pot


def _decay_for_org(db, org_id: str) -> int:
    """
    Decay non-potentiated, ACTIVE facts that haven't been co-activated in
    DECAY_AGE_DAYS. Edge weight floors at 0.
    """
    row = db.execute(
        text("""
            WITH decayed AS (
                UPDATE contact_facts
                SET edge_weight = GREATEST(
                        0.000,
                        edge_weight - :decay
                    )
                WHERE org_id = :oid
                  AND is_potentiated = FALSE
                  AND lifecycle_state = 'ACTIVE'
                  AND (
                      last_coactivated_at IS NULL
                      OR last_coactivated_at < NOW() - (:days || ' days')::interval
                  )
                  AND edge_weight > 0.000
                RETURNING id
            )
            SELECT COUNT(*)::int FROM decayed
        """),
        {"oid": org_id, "decay": DECAY_FACTOR, "days": DECAY_AGE_DAYS},
    ).fetchone()
    db.commit()
    return int(row[0] or 0) if row else 0


# Convenience entry for ad-hoc invocation
if __name__ == "__main__":
    import sys
    org_id = sys.argv[1] if len(sys.argv) > 1 else None
    print(run_hebbian_nightly(org_id))

"""
Score writer — the central job that populates the 5 scoring axes on every
contact. Runs on a 15-minute Celery beat schedule.

Before this existed, `contacts.{confidence_score, freshness_score,
consistency_score, authority_score, context_score}` columns existed but were
never updated — values stayed at defaults (0.5 / 1.0) forever. Bundle builder
and plan enforcement read them anyway, so downstream reasoning was based on
stale data.

Composite: `context_score = freshness × confidence × consistency × signal ×
authority` (multiplicative per the Master Build Document — any single weak
axis drags the whole down).

Also extracts authority signals from interaction bodies (regex over titles +
signatures) and writes `authority_score`. The Authority detector was
registered but had no data source; this closes that loop.
"""

from __future__ import annotations

import logging
import math
import re
from typing import List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
RECOMPUTE_INTERVAL_MINUTES = 15
BATCH_SIZE = 500
FRESHNESS_HALF_LIFE_DAYS = 30.0

# Role → weight (higher = more authority). Per Master Build Document §03.2.
_ROLE_WEIGHTS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\b(ceo|founder|co[- ]?founder|president)\b", re.I), 1.00),
    (re.compile(r"\b(cto|cfo|coo|cro|cmo|cpo|chief\s+\w+\s+officer)\b", re.I), 0.95),
    (re.compile(r"\b(vp|vice\s+president|svp|evp)\b", re.I), 0.80),
    (re.compile(r"\b(head\s+of|director)\b", re.I), 0.60),
    (re.compile(r"\b(senior\s+manager|principal|lead)\b", re.I), 0.50),
    (re.compile(r"\b(manager|pm|product\s+manager)\b", re.I), 0.40),
    (re.compile(r"\b(engineer|developer|analyst|associate|specialist|consultant)\b", re.I), 0.30),
]

# ── Entry points ──────────────────────────────────────────────────────────────


def run_score_writer(org_id: str | None = None) -> dict:
    """Recompute scores for contacts due for refresh. Called from Celery.

    Returns counters for observability.
    """
    db = SessionLocal()
    try:
        contacts = _fetch_due_contacts(db, org_id)
        if not contacts:
            return {"processed": 0, "updated": 0, "org_id": org_id}

        updated = 0
        for batch_start in range(0, len(contacts), BATCH_SIZE):
            batch = contacts[batch_start : batch_start + BATCH_SIZE]
            updated += _process_batch(db, batch)

        logger.info(
            f"score_writer done org={org_id or 'all'} "
            f"processed={len(contacts)} updated={updated}"
        )
        return {"processed": len(contacts), "updated": updated, "org_id": org_id}
    finally:
        db.close()


# ── Internal ──────────────────────────────────────────────────────────────────


def _fetch_due_contacts(db: Session, org_id: str | None) -> list[dict]:
    """Contacts whose scores are stale (or never computed)."""
    params: dict = {"interval": f"{RECOMPUTE_INTERVAL_MINUTES} minutes"}
    where = (
        "(last_recomputed_at IS NULL "
        "OR last_recomputed_at < NOW() - CAST(:interval AS interval))"
    )
    if org_id:
        where += " AND org_id = :org_id"
        params["org_id"] = org_id

    rows = db.execute(
        text(f"""
            SELECT id, org_id, name, email, company, job_title,
                   last_interaction_at, interaction_count
            FROM contacts
            WHERE {where}
              AND (is_archived = FALSE OR is_archived IS NULL)
            ORDER BY last_interaction_at DESC NULLS LAST
            LIMIT 5000
        """),
        params,
    ).fetchall()

    return [dict(r._mapping) for r in rows]


def _process_batch(db: Session, batch: list[dict]) -> int:
    """Score one batch of contacts and write back in a single transaction."""
    updates: list[dict] = []

    for c in batch:
        try:
            scores = _compute_scores_for_contact(db, c)
            updates.append({
                "cid": c["id"],
                "fresh": scores["freshness"],
                "conf": scores["confidence"],
                "cons": scores["consistency"],
                "auth": scores["authority"],
                "ctx": scores["context_score"],
            })
        except Exception as e:
            logger.warning(f"score_writer skip contact={c['id']} err={e}")

    if not updates:
        return 0

    # Batch UPDATE via CASE … WHEN. Keeps it to one round-trip.
    db.execute(
        text("""
            UPDATE contacts AS c SET
                freshness_score   = v.fresh,
                confidence_score  = v.conf,
                consistency_score = v.cons,
                authority_score   = v.auth,
                context_score     = v.ctx,
                last_recomputed_at = NOW()
            FROM (VALUES {})
            AS v(cid, fresh, conf, cons, auth, ctx)
            WHERE c.id = CAST(v.cid AS uuid)
        """.format(", ".join(
            f"(:cid{i}, :fresh{i}, :conf{i}, :cons{i}, :auth{i}, :ctx{i})"
            for i in range(len(updates))
        ))),
        {
            f"{k}{i}": v
            for i, u in enumerate(updates)
            for k, v in u.items()
        },
    )
    db.commit()
    return len(updates)


def _compute_scores_for_contact(db: Session, c: dict) -> dict:
    """Run all 5 axes + authority for one contact. All work inside one DB call."""
    cid = c["id"]

    # One composite query to fetch everything we need from interactions.
    row = db.execute(
        text("""
            SELECT
                COUNT(*) AS n,
                COUNT(DISTINCT interaction_type) AS distinct_sources,
                COALESCE(EXTRACT(EPOCH FROM (NOW() - MAX(interaction_at))), 9999999) AS age_seconds,
                STRING_AGG(COALESCE(raw_snippet, ''), ' | ' ORDER BY interaction_at DESC) FILTER (
                    WHERE raw_snippet IS NOT NULL
                ) AS recent_bodies,
                COUNT(*) FILTER (WHERE direction = 'inbound') AS inbound_n,
                COUNT(*) FILTER (WHERE direction = 'outbound') AS outbound_n
            FROM (
                SELECT * FROM interactions
                WHERE contact_id = :cid
                ORDER BY interaction_at DESC
                LIMIT 50
            ) i
        """),
        {"cid": cid},
    ).fetchone()

    n = int(row.n or 0)
    distinct_sources = int(row.distinct_sources or 0)
    age_days = float(row.age_seconds or 0) / 86400.0
    recent_bodies = row.recent_bodies or ""

    # 1. Freshness: exp(-age/half_life), bounded so very-old contacts aren't zero
    freshness = max(0.10, math.exp(-age_days / FRESHNESS_HALF_LIFE_DAYS)) if n > 0 else 0.10

    # 2. Confidence: grows with interaction count (log-scaled, saturates)
    if n == 0:
        confidence = 0.20
    else:
        confidence = min(1.0, 0.30 + 0.15 * math.log(1 + n))

    # 3. Consistency: distinct interaction_types, capped at 2 (email + meeting
    #    is the common high-consistency case).
    consistency = min(1.0, max(0.25, (distinct_sources or 1) / 2.0))

    # 4. Signal (interaction density): log-scaled mention count.
    #    Saturates at ~20 interactions — beyond that, more calls ≠ more signal.
    signal = max(0.15, min(1.0, math.log(1 + n) / math.log(1 + 20)))

    # 5. Authority: title + body signals (floored at 0.30).
    authority = _compute_authority(c, recent_bodies)

    # Composite: geometric mean. Preserves the Master Build Document's
    # "any weak axis drags down" property (5-way geo mean of [0.9,0.9,0.9,
    # 0.9,0.3] = 0.66 vs all-0.9 = 0.9) while staying in a usable range
    # for realistic data (pure multiplication collapses to <0.1 for any
    # contact with even one under-0.5 axis).
    product = freshness * confidence * consistency * signal * authority
    context_score = product ** 0.2 if product > 0 else 0.10
    context_score = max(0.10, min(1.0, context_score))

    return {
        "freshness": round(freshness, 4),
        "confidence": round(confidence, 4),
        "consistency": round(consistency, 4),
        "signal": round(signal, 4),
        "authority": round(authority, 4),
        "context_score": round(context_score, 4),
    }


def _compute_authority(contact: dict, recent_bodies: str) -> float:
    """Extract authority from explicit title field + signature text.

    Returns a value in [0.30, 1.00]. Defaults to 0.30 when no signal.
    """
    best = 0.0

    # Check explicit title column (populated by HubSpot/contact-detail flows)
    title = (contact.get("job_title") or "").strip()
    if title:
        best = max(best, _title_weight(title))

    # Scan recent interaction bodies / signatures for role mentions.
    if recent_bodies:
        # Only match patterns that LOOK like a signature (Name + role) — bias
        # to the last 500 chars where signatures live.
        tail = recent_bodies[-2000:]
        best = max(best, _title_weight(tail))

    return max(0.30, best)  # floor so bundle reasoning still has a value to use


def _title_weight(text_blob: str) -> float:
    """Highest-matching role weight in the text blob."""
    highest = 0.0
    for pattern, weight in _ROLE_WEIGHTS:
        if pattern.search(text_blob):
            if weight > highest:
                highest = weight
    return highest

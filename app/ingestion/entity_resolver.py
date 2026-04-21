"""Unified 5-step entity resolver.

Given (org_id, name, email), return the best matching contact_id, a
confidence label, and the match strategy used.

Steps (short-circuit on first hit):
  1. exact email (normalized)
  2. cosine similarity over contacts.embedding ≥ COSINE_THRESHOLD
  3. pg_trgm similarity ≥ TRGM_STRONG
  4. pg_trgm similarity ≥ TRGM_WEAK (returned as 'maybe', caller decides)
  5. LLM tiebreak when 2+ candidates in (3) or (4) are within 0.03

The 4th rule still returns a candidate; callers treat confidence=='maybe'
as a review item rather than an auto-merge.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from app.graph.embedder import embed_text

logger = logging.getLogger(__name__)

COSINE_THRESHOLD = 0.90
TRGM_STRONG = 0.92
TRGM_WEAK = 0.75


@dataclass
class Match:
    contact_id: Optional[str]
    confidence: str  # 'exact' | 'strong' | 'maybe' | 'none'
    strategy: str    # 'email' | 'cosine' | 'trigram_strong' | 'trigram_weak' | 'llm'
    score: float


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()


def _step_email(db, org_id: str, email: str) -> Optional[Match]:
    row = db.execute(
        text("""
            SELECT id FROM contacts
            WHERE org_id = :oid AND LOWER(email) = :em
            LIMIT 1
        """),
        {"oid": org_id, "em": email},
    ).fetchone()
    if row:
        return Match(str(row[0]), "exact", "email", 1.0)
    return None


def _step_cosine(db, org_id: str, name: str) -> Optional[Match]:
    try:
        emb = embed_text(name, org_id=org_id)
    except Exception as e:
        logger.debug(f"embed failed: {e}")
        return None
    # pgvector: 1 - cosine distance = similarity
    row = db.execute(
        text("""
            SELECT id, 1 - (embedding <=> (:e)::vector) AS sim
            FROM contacts
            WHERE org_id = :oid AND embedding IS NOT NULL
            ORDER BY embedding <=> (:e)::vector
            LIMIT 1
        """),
        {"oid": org_id, "e": list(emb)},
    ).fetchone()
    if row and row[1] is not None and float(row[1]) >= COSINE_THRESHOLD:
        return Match(str(row[0]), "strong", "cosine", float(row[1]))
    return None


def _step_trigram(db, org_id: str, name: str) -> Optional[Match]:
    rows = db.execute(
        text("""
            SELECT id, similarity(name, :n) AS sim
            FROM contacts
            WHERE org_id = :oid AND name IS NOT NULL
            ORDER BY name <-> :n
            LIMIT 3
        """),
        {"oid": org_id, "n": name},
    ).fetchall()
    if not rows:
        return None

    top = rows[0]
    top_sim = float(top[1] or 0.0)
    if top_sim >= TRGM_STRONG:
        return Match(str(top[0]), "strong", "trigram_strong", top_sim)
    if top_sim >= TRGM_WEAK:
        # If 2+ candidates are within 0.03 of each other → LLM tiebreak.
        close = [r for r in rows if abs(float(r[1] or 0.0) - top_sim) < 0.03]
        if len(close) >= 2:
            return None  # fall through to llm step
        return Match(str(top[0]), "maybe", "trigram_weak", top_sim)
    return None


def _step_llm_tiebreak(db, org_id: str, name: str) -> Optional[Match]:
    """Ask the LLM to pick the best match when trigram ties cluster."""
    from app.llm import llm_client

    rows = db.execute(
        text("""
            SELECT id, name, company, email, similarity(name, :n) AS sim
            FROM contacts
            WHERE org_id = :oid AND name IS NOT NULL
              AND similarity(name, :n) >= :w
            ORDER BY name <-> :n
            LIMIT 5
        """),
        {"oid": org_id, "n": name, "w": TRGM_WEAK},
    ).fetchall()
    if not rows:
        return None

    options = "\n".join(
        f"{i+1}. id={r[0]} name={r[1]!r} company={r[2] or '-'} email={r[3] or '-'}"
        for i, r in enumerate(rows)
    )
    prompt = (
        f"Candidate to resolve: name={name!r}\n\n"
        f"Existing contacts:\n{options}\n\n"
        'Respond with ONLY JSON: {"pick": <1-based index or null>, "confidence": 0-1}. '
        "Pick only if you are confident it is the same person."
    )
    try:
        raw = llm_client.call(
            org_id=org_id, purpose="classify_email",
            prompt=prompt, temperature=0.0, max_tokens=64,
        )
    except Exception as e:
        logger.warning(f"resolver LLM call failed: {e}")
        return None

    import json
    raw = raw.strip().strip("`")
    if raw.startswith("json"):
        raw = raw[4:].strip()
    try:
        data = json.loads(raw)
    except Exception:
        return None
    pick = data.get("pick")
    conf = float(data.get("confidence") or 0.0)
    if pick and 1 <= int(pick) <= len(rows) and conf >= 0.6:
        chosen = rows[int(pick) - 1]
        return Match(str(chosen[0]), "strong", "llm", conf)
    return None


def resolve(db, org_id: str, name: str, email: Optional[str] = None) -> Match:
    """Return best match. Caller decides what to do with confidence='maybe'."""
    name = (name or "").strip()
    em = _normalize_email(email)

    if em:
        hit = _step_email(db, org_id, em)
        if hit:
            return hit
    if not name:
        return Match(None, "none", "none", 0.0)

    hit = _step_cosine(db, org_id, name)
    if hit:
        return hit

    hit = _step_trigram(db, org_id, name)
    if hit:
        return hit

    hit = _step_llm_tiebreak(db, org_id, name)
    if hit:
        return hit

    return Match(None, "none", "none", 0.0)

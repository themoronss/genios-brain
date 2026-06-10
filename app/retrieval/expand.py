"""
Query expansion — alias-aware lookup before BM25/vector search.

Two pure functions, no LLM calls:

  expand_query(db, org_id, query)
      → returns terms to OR into the BM25 query: original tokens plus any
        alias_text rows whose lower() prefix matches a query token, capped.

  resolve_contacts_by_alias(db, org_id, name, limit=5)
      → returns candidate contact_ids whose aliases trigram-match the input.
        Used when the caller asks about an entity by a partial / mis-spelled
        name (e.g. "3one4" → contact_id of "3one4 Capital").

Both are best-effort: failures degrade silently. The retrieval pipeline
continues with the original query if expansion fails.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Tokens shorter than this are skipped — too noisy for trigram lookup.
_MIN_TOKEN_LEN = 3
# Cap on expansions per query — prevents tsquery blow-up on long inputs.
_MAX_EXPANSIONS = 8
# Trigram similarity floor for alias→contact resolution.
_TRGM_THRESHOLD = 0.40

_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(query: str) -> list[str]:
    """Lowercase word-character tokens, length-filtered."""
    if not query:
        return []
    return [
        t.lower()
        for t in _WORD_RE.findall(query)
        if len(t) >= _MIN_TOKEN_LEN
    ]


def expand_query(
    db: Session,
    org_id: str,
    query: str,
) -> dict:
    """
    Return a dict: {
        "tokens":     [...],   # normalized original tokens
        "aliases":    [...],   # alias_text rows that match a token
        "contact_ids":[...],   # contact_ids reachable via the alias hits
    }
    """
    tokens = _tokenize(query)
    if not tokens:
        return {"tokens": [], "aliases": [], "contact_ids": []}

    # Trigram OR over tokens. Pick top-N alias rows per (alias_text, contact_id).
    placeholders = ",".join(f":t{i}" for i in range(len(tokens)))
    params = {"oid": org_id, "thr": _TRGM_THRESHOLD, "lim": _MAX_EXPANSIONS}
    for i, tok in enumerate(tokens):
        params[f"t{i}"] = tok

    sql = f"""
        SELECT DISTINCT ON (alias_text, contact_id)
               alias_text, contact_id,
               GREATEST({", ".join(
                    f"similarity(lower(alias_text), :t{i})" for i in range(len(tokens))
                )}) AS sim
        FROM entity_aliases
        WHERE org_id = :oid
          AND ({" OR ".join(
                f"similarity(lower(alias_text), :t{i}) >= :thr"
                for i in range(len(tokens))
            )})
        ORDER BY alias_text, contact_id, sim DESC
        LIMIT :lim
    """

    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        # entity_aliases table or pg_trgm may not exist on a stale DB —
        # degrade silently to original tokens.
        logger.debug(f"expand_query: alias lookup skipped: {e}")
        return {"tokens": tokens, "aliases": [], "contact_ids": []}

    aliases = [r.alias_text for r in rows if r.alias_text]
    contact_ids = list({str(r.contact_id) for r in rows if r.contact_id})

    return {
        "tokens": tokens,
        "aliases": aliases,
        "contact_ids": contact_ids,
    }


def resolve_contacts_by_alias(
    db: Session,
    org_id: str,
    name: str,
    limit: int = 5,
    threshold: Optional[float] = None,
) -> list[dict]:
    """
    Trigram lookup on alias_text. Returns up to `limit` candidates, ordered
    by similarity desc.

    Each row: {"contact_id": uuid, "alias_text": str, "alias_kind": str, "similarity": float}
    """
    if not name or not name.strip():
        return []

    needle = name.strip().lower()
    thr = threshold if threshold is not None else _TRGM_THRESHOLD

    try:
        rows = db.execute(
            text("""
                SELECT contact_id, alias_text, alias_kind,
                       similarity(lower(alias_text), :n) AS sim
                FROM entity_aliases
                WHERE org_id = :oid
                  AND similarity(lower(alias_text), :n) >= :thr
                ORDER BY sim DESC
                LIMIT :lim
            """),
            {"oid": org_id, "n": needle, "thr": thr, "lim": limit},
        ).fetchall()
    except Exception as e:
        logger.debug(f"resolve_contacts_by_alias: skipped: {e}")
        return []

    return [
        {
            "contact_id": str(r.contact_id),
            "alias_text": r.alias_text,
            "alias_kind": r.alias_kind,
            "similarity": float(r.sim or 0),
        }
        for r in rows
    ]


def build_expanded_tsquery(expansion: dict) -> str:
    """
    Build a Postgres `to_tsquery`-safe OR expression from an expand_query()
    result. Returns empty string when nothing expandable.

    Original tokens always included; alias hits OR'd in. We strip non-word
    chars to keep the query safe for `to_tsquery`.
    """
    parts: list[str] = []
    seen: set[str] = set()
    for term in (expansion.get("tokens") or []) + (expansion.get("aliases") or []):
        for word in _WORD_RE.findall(str(term)):
            w = word.lower()
            if len(w) < _MIN_TOKEN_LEN or w in seen:
                continue
            seen.add(w)
            parts.append(w)
    return " | ".join(parts)

"""Company Brain — the READING door for the dashboard's three-brain view.

The dashboard Brain page needs one org-scoped call that returns everything GeniOS actually
*knows* about a company, already shaped as executive-readable records. The raw material lives
across several stores that each speak a different dialect:

  • learned_brain_entries   — Layer 6's published organization/behavior/adaptive brain values
  • temporary_memories      — Layer 6's Runtime leases (current, expiring adaptive intelligence)
  • knowledge_suggestions   — Layer 6 candidates parked at human_review (never auto-applied)
  • source_events(internal) — company canon someone wrote in (refund policy, Q3 goal, …)

This module unions them into the SAME normalized record the UI already renders, so the page
stops synthesising a "brain" out of the personal user-model and reads the real org brain. Every
source query is isolated: a missing table or column degrades that one source to empty, never a
500 that blanks the whole page. Confidence/evidence come from the immutable learning_object the
entry was published from (joined by learning_id), never re-derived here.

Empty is a valid, honest answer: a fresh org has published nothing yet, so it returns no records
and the page shows its "still forming" state — not fictional company knowledge.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_log = get_logger("genios.brain")
_graph = make_graph_store()

# The three brains the UI renders. 'runtime' is an internal execution target, never shown as a brain.
_UI_BRAINS = ("organization", "behavior", "adaptive")


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def _statement(value: Any, fallback: str) -> str:
    """Best-effort executive statement out of an opaque learned/written value blob.

    Learned values are unit-shaped JSON; we never assume a schema. We look for the keys a human
    sentence would live under, then fall back to a humanized subject so a record is never blank.
    """
    if isinstance(value, str):
        text_val = value.strip()
        return text_val[:400] if text_val else fallback
    if isinstance(value, dict):
        for key in ("statement", "text", "summary", "title", "claim", "label", "value", "description"):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()[:400]
        # A single scalar field is still a readable value.
        scalars = [f"{k.replace('_', ' ')}: {v}" for k, v in value.items()
                   if isinstance(v, (str, int, float, bool)) and str(v).strip()]
        if scalars:
            return " · ".join(scalars)[:400]
    return fallback


def _humanize(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").strip().title() or slug


def _confidence(evidence: Any) -> float | None:
    if isinstance(evidence, dict):
        bp = evidence.get("confidence_bp")
        if isinstance(bp, (int, float)):
            return max(0.0, min(1.0, bp / 10000.0))
    return None


def _evidence_line(evidence: Any) -> str | None:
    if not isinstance(evidence, dict):
        return None
    obs = evidence.get("observations")
    days = evidence.get("distinct_days")
    refs = evidence.get("independent_refs")
    parts = []
    if isinstance(obs, int) and obs:
        parts.append(f"{obs} observation{'s' if obs != 1 else ''}")
    if isinstance(days, int) and days:
        parts.append(f"across {days} day{'s' if days != 1 else ''}")
    if isinstance(refs, int) and refs:
        parts.append(f"{refs} independent reference{'s' if refs != 1 else ''}")
    return " ".join(parts) if parts else None


_BRAIN_STATE = {"organization": "confirmed", "behavior": "observed", "adaptive": "active"}
_BRAIN_ORIGIN = {"organization": "connected", "behavior": "observed", "adaptive": "current"}
_BRAIN_EFFECT = {
    "organization": "Grounds executive briefs in this confirmed company truth.",
    "behavior": "Shapes how GeniOS prepares work to match how the company actually operates.",
    "adaptive": "Moves this current signal forward in the executive brief while it applies.",
}


def _learned_records(c, org: str) -> list[dict]:
    """Published brain values, joined to the immutable learning_object for evidence/confidence."""
    rows = c.execute(text(
        "select e.brain, e.subject, e.version, e.value, e.created_at, "
        "       o.evidence as evidence, o.unit as unit "
        "from learned_brain_entries e "
        "left join learning_objects o on o.org_id = e.org_id and o.learning_id = e.learning_id "
        "where e.org_id = :o and e.active and e.brain = any(:b) "
        "order by e.brain, e.created_at desc"), {"o": org, "b": list(_UI_BRAINS)}).mappings().all()
    out = []
    for r in rows:
        brain = r["brain"]
        out.append({
            "id": f"brain-{brain}-{r['subject']}-v{r['version']}",
            "area": brain,
            "scope": _humanize(r["subject"]),
            "title": _statement(r["value"], _humanize(r["subject"])),
            "detail": f"Learned and published to the {brain} brain (version {r['version']}).",
            "effect": _BRAIN_EFFECT[brain],
            "state": _BRAIN_STATE[brain],
            "origin": _BRAIN_ORIGIN[brain],
            "source": "Learning engine",
            "sources": ["Company activity"],
            "confidence": _confidence(r["evidence"]),
            "updatedAt": _iso(r["created_at"]),
            "dateLabel": "Updated",
            "evidence": _evidence_line(r["evidence"]),
        })
    return out


def _memory_records(c, org: str) -> list[dict]:
    """Current, expiring adaptive intelligence — Runtime leases the engine is applying now."""
    rows = c.execute(text(
        "select m.memory_id, m.subject, m.value, m.expires_at, m.created_at, o.evidence as evidence "
        "from temporary_memories m "
        "left join learning_objects o on o.org_id = m.org_id and o.learning_id = m.learning_id "
        "where m.org_id = :o and m.active order by m.created_at desc limit 100"),
        {"o": org}).mappings().all()
    out = []
    for r in rows:
        expires = _iso(r["expires_at"])
        out.append({
            "id": f"memory-{r['memory_id']}",
            "area": "adaptive",
            "scope": f"{_humanize(r['subject'])} · temporary",
            "title": _statement(r["value"], _humanize(r["subject"])),
            "detail": "A temporary preference the engine is applying now; it expires and cannot change policy.",
            "effect": "Prioritises this current signal in the daily executive brief until it expires.",
            "state": "active",
            "origin": "current",
            "source": "Current operating phase",
            "sources": ["Current operating phase"],
            "confidence": _confidence(r["evidence"]),
            "updatedAt": _iso(r["created_at"]),
            "dateLabel": "Updated",
            "evidence": _evidence_line(r["evidence"]),
            "nextCheck": f"Active until {expires[:10]} · reviewed or expires automatically" if expires else None,
        })
    return out


def _suggestion_records(c, org: str) -> list[dict]:
    """Candidates parked at human_review — surfaced, never auto-applied."""
    rows = c.execute(text(
        "select suggestion_id, subject, body, created_at from knowledge_suggestions "
        "where org_id = :o and state = 'human_review' order by created_at desc limit 100"),
        {"o": org}).mappings().all()
    out = []
    for r in rows:
        out.append({
            "id": f"suggestion-{r['suggestion_id']}",
            "area": "adaptive",
            "scope": f"{_humanize(r['subject'])} · learning",
            "title": _statement(r["body"], _humanize(r["subject"])),
            "detail": "A learning candidate awaiting review. Nothing changes automatically until it is confirmed.",
            "effect": "If confirmed, this becomes durable knowledge; until then it only surfaces for review.",
            "state": "learning",
            "origin": "observed",
            "source": "Observed signals",
            "sources": ["Observed signals"],
            "updatedAt": _iso(r["created_at"]),
            "dateLabel": "Observed",
            "nextCheck": "Awaiting explicit human review before it can apply",
        })
    return out


def _written_records(c, org: str) -> list[dict]:
    """Company canon someone wrote in through the knowledge door — latest version per assertion."""
    rows = c.execute(text(
        "select distinct on (source_object_id) source_object_id, object_type, occurred_at "
        "from source_events where org_id = :o and source = 'internal' "
        "order by source_object_id, occurred_at desc"), {"o": org}).mappings().all()
    out = []
    for r in rows:
        key = r["source_object_id"]
        slug = key.split(":", 1)[1] if ":" in key else key
        out.append({
            "id": f"written-{key}",
            "area": "organization",
            "scope": _humanize(r["object_type"] or "company knowledge"),
            "title": _humanize(slug),
            "detail": "Company canon written in through the knowledge door and confirmed as true.",
            "effect": "Grounds executive briefs in this confirmed company truth.",
            "state": "confirmed",
            "origin": "manual",
            "source": "Company knowledge (written)",
            "sources": ["Company knowledge (written)"],
            "confidence": 1.0,
            "updatedAt": _iso(r["occurred_at"]),
            "dateLabel": "Recorded",
        })
    return out


_SOURCES = (
    ("learned", _learned_records),
    ("memories", _memory_records),
    ("suggestions", _suggestion_records),
    ("written", _written_records),
)


@router.get("/api/org/{org_id}/brain")
def company_brain(org_id: str, org: str = Depends(_org),
                  include: str = Query("all", description="reserved; all sources are unioned")) -> dict:
    """Every real org-brain record, normalized for the dashboard's three-brain view.

    Sources are queried independently: one failing (a table not yet migrated on an older DB, say)
    logs and degrades to empty for that source rather than failing the page. Records already carry
    the {area, state, origin, confidence, sources, evidence} the UI renders — no client reshaping.
    """
    if _graph is None:
        raise HTTPException(400, "brain store not configured (needs DATABASE_URL)")

    records: list[dict] = []
    source_status: dict[str, Any] = {}
    with _graph.engine.connect() as c:
        for name, fn in _SOURCES:
            try:
                rows = fn(c, org)
                records.extend(rows)
                source_status[name] = len(rows)
            except Exception as ex:  # one broken store must not blank the whole brain
                _log.warning("brain source %s failed for org %s: %s", name, org, ex)
                source_status[name] = "error"

    counts = {b: sum(1 for r in records if r["area"] == b) for b in _UI_BRAINS}
    counts["review"] = sum(1 for r in records if r.get("state") == "learning")
    return {
        "records": records,
        "counts": counts,
        "total": len(records),
        "sources": source_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["router"]

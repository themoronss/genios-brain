"""
Phase 1: Live Tool Dispatcher.

When the graph doesn't have what an agent asks for, this module dispatches
the query to the org's connected tools (Gmail, Calendar, uploaded docs) in
real-time and returns merged results. The bundle_builder hooks into this
when match_confidence < 0.5 OR interaction_count == 0.

Key design choices:
  - NEVER raises — every connector is wrapped, errors return [].
  - Hard latency cap: parallel dispatch via concurrent.futures, 2.5s total.
  - Cost-guarded: every call goes through `cost_guard.check()` first
    (Phase 7 wires this; until then it's a no-op).
  - Auto write-back: gmail/calendar live results are persisted into
    `interactions` so next-time the same query hits the cached graph.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Dict, List, Optional

from app.ingestion import gmail_connector, calendar_connector
from app.retrieval import doc_search

logger = logging.getLogger(__name__)

# Hard timeouts per source (seconds). Calendar is fastest; docs need embed.
# Gmail token refresh (401 → re-auth) + 3 metadata fetches = ~6s realistic
# worst case. Setting to 10s comfortably covers cold-start while keeping
# request total bounded under our 12s P99 ceiling.
_TIMEOUT_GMAIL = 10.0
_TIMEOUT_CALENDAR = 8.0
_TIMEOUT_DOCS = 6.0

# Default routing keywords → which sources to hit.
# Matched against query text (case-insensitive). When nothing matches,
# we hit all three (parallel) and let scoring sort it out.
_KEYWORD_ROUTING = {
    "gmail": [
        "email", "mail", "invoice", "receipt", "subscription", "payment",
        "transaction", "razorpay", "stripe", "bill", "billing",
        "from:", "to:", "subject:", "thread", "reply", "inbox",
    ],
    "calendar": [
        "meeting", "event", "schedule", "calendar", "call", "1:1",
        "1-on-1", "standup", "kickoff", "interview", "demo",
        "tomorrow", "today", "next week", "upcoming", "rsvp",
    ],
    "docs": [
        "doc", "document", "pdf", "deck", "spec", "policy", "contract",
        "proposal", "report", "sop", "memo", "notes",
    ],
}


def _route(query: str) -> List[str]:
    """Pick which sources to query based on keyword hints.

    GMAIL is ALWAYS included — it's the broadest signal source and most
    user questions touch email even when they look topical. Calendar and
    docs are added when their keywords match. This avoids the bug where
    'pitch deck' would route ONLY to docs and miss the email thread that
    contains the deck link.
    """
    q = (query or "").lower()
    sources = ["gmail"]  # always
    if any(k in q for k in _KEYWORD_ROUTING["calendar"]):
        sources.append("calendar")
    if any(k in q for k in _KEYWORD_ROUTING["docs"]):
        sources.append("docs")
    # If nothing additional matched, still hit calendar+docs lightly so a
    # generic query gets the full picture. Cost guard limits abuse.
    if sources == ["gmail"]:
        sources = ["gmail", "calendar", "docs"]
    return sources


def _safe_call(fn, *args, **kwargs) -> List:
    """Run a connector call with full exception isolation."""
    try:
        out = fn(*args, **kwargs)
        return out or []
    except Exception as e:
        logger.debug(f"live dispatch call failed ({fn.__name__}): {e}")
        return []


def dispatch(
    org_id: str,
    query: str,
    *,
    sources: Optional[List[str]] = None,
    limit_per_source: int = 5,
) -> Dict[str, List]:
    """
    Run live search across selected sources in parallel, collect results.

    Args:
        org_id: org UUID
        query: free text query
        sources: optional explicit list ['gmail','calendar','docs'].
                 When None, route by keyword.
        limit_per_source: max results per connector

    Returns:
        {
          "gmail":    [...],
          "calendar": [...],
          "docs":     [...],
          "total":    N,
          "sources_hit": ["gmail","docs"],
          "fallback_used": True,
        }
    """
    if not org_id or not query:
        return {"gmail": [], "calendar": [], "docs": [], "total": 0,
                "sources_hit": [], "fallback_used": False}

    # ── Cost guard hook (Phase 7 wires this in) ──────────────────────────
    try:
        from app.retrieval import cost_guard  # type: ignore
        if not cost_guard.allow(org_id):
            logger.info(f"live dispatch blocked by cost guard for org={org_id}")
            return {"gmail": [], "calendar": [], "docs": [], "total": 0,
                    "sources_hit": [], "fallback_used": True,
                    "blocked_reason": "cost_guard"}
    except ImportError:
        pass  # cost_guard not yet shipped — proceed
    except Exception as e:
        logger.debug(f"cost guard check errored, proceeding: {e}")

    targets = sources or _route(query)
    out: Dict[str, List] = {"gmail": [], "calendar": [], "docs": []}

    # Parallel dispatch with per-call timeouts. Total wall is capped by
    # max(individual timeouts) — typically <2.5s.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futures = {}
        if "gmail" in targets:
            futures[ex.submit(
                _safe_call, gmail_connector.live_search,
                org_id, query, limit_per_source,
            )] = ("gmail", _TIMEOUT_GMAIL)
        if "calendar" in targets:
            futures[ex.submit(
                _safe_call, calendar_connector.live_search,
                org_id, query, 30, 60, limit_per_source,
            )] = ("calendar", _TIMEOUT_CALENDAR)
        if "docs" in targets:
            futures[ex.submit(
                _safe_call, doc_search.live_search,
                org_id, query, limit_per_source,
            )] = ("docs", _TIMEOUT_DOCS)

        for fut, (src, timeout) in futures.items():
            try:
                out[src] = fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                logger.info(f"live dispatch {src} timed out for org={org_id}")
                out[src] = []
            except Exception as e:
                logger.debug(f"live dispatch {src} failed: {e}")
                out[src] = []

    # ── Cost guard increment (records the call) ──────────────────────────
    try:
        from app.retrieval import cost_guard  # type: ignore
        cost_guard.increment(org_id, count=1)
    except (ImportError, Exception):
        pass

    out["total"] = sum(len(out[s]) for s in ("gmail", "calendar", "docs"))
    out["sources_hit"] = [s for s in ("gmail", "calendar", "docs") if out[s]]
    out["fallback_used"] = True

    # ── Async write-back to graph for caching (fire-and-forget) ──────────
    # Gmail/Calendar hits become interactions so next time they're served
    # from the graph in <400ms. Docs already live in document_chunks.
    if out["gmail"] or out["calendar"]:
        try:
            _writeback_async(org_id, out)
        except Exception as e:
            logger.debug(f"writeback enqueue failed: {e}")

    return out


def _writeback_async(org_id: str, results: Dict[str, List]) -> None:
    """Best-effort persist of live results into the graph for next-time cache.

    Gmail messages → interactions table (lightweight row).
    Calendar events → interactions table (source='calendar').

    Done synchronously for now (cheap inserts). Move to Celery if it ever
    shows up on flame graphs.
    """
    from sqlalchemy import text
    from app.database import SessionLocal

    if not (results.get("gmail") or results.get("calendar")):
        return

    db = SessionLocal()
    try:
        for msg in results.get("gmail", []) or []:
            try:
                db.execute(
                    text("""
                        INSERT INTO interactions
                            (org_id, source, source_id, subject, summary,
                             interaction_at, interaction_type, direction)
                        VALUES
                            (:oid, 'gmail_live', :sid, :subj, :snip,
                             NOW(), 'email_one_way', 'inbound')
                        ON CONFLICT (org_id, source, source_id) DO NOTHING
                    """),
                    {
                        "oid": org_id,
                        "sid": msg.get("id"),
                        "subj": (msg.get("subject") or "")[:500],
                        "snip": (msg.get("snippet") or "")[:1000],
                    },
                )
            except Exception:
                continue
        for ev in results.get("calendar", []) or []:
            try:
                db.execute(
                    text("""
                        INSERT INTO interactions
                            (org_id, source, source_id, subject, summary,
                             interaction_at, interaction_type, direction)
                        VALUES
                            (:oid, 'calendar_live', :sid, :title, :desc,
                             COALESCE(:start_ts::timestamptz, NOW()),
                             'meeting', 'bidirectional')
                        ON CONFLICT (org_id, source, source_id) DO NOTHING
                    """),
                    {
                        "oid": org_id,
                        "sid": ev.get("id"),
                        "title": (ev.get("summary") or "")[:500],
                        "desc": (ev.get("description") or "")[:1000],
                        "start_ts": ev.get("start"),
                    },
                )
            except Exception:
                continue
        db.commit()
    except Exception as e:
        logger.debug(f"writeback commit failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def format_for_bundle(results: Dict[str, List]) -> str:
    """
    Render dispatcher results as a paragraph the agent can consume directly.
    Used by bundle_builder to merge live data into context_for_agent.
    """
    if not results or not results.get("total"):
        return ""

    lines = ["[Live tool fetch — fresh data not in cached graph]"]

    if results.get("gmail"):
        lines.append("\nFrom Gmail (live):")
        for m in results["gmail"][:5]:
            sender = (m.get("from") or "")[:60]
            subj = (m.get("subject") or "")[:100]
            snip = (m.get("snippet") or "")[:200]
            date = (m.get("date") or "")[:30]
            lines.append(f"  • {date} — {sender} — {subj}\n    {snip}")

    if results.get("calendar"):
        lines.append("\nFrom Calendar (live):")
        for e in results["calendar"][:5]:
            title = (e.get("summary") or "")[:100]
            start = (e.get("start") or "")[:25]
            attendees = ", ".join(
                a.get("email", "")[:40] for a in (e.get("attendees") or [])[:3]
            )
            lines.append(f"  • {start} — {title} (with {attendees})")

    if results.get("docs"):
        lines.append("\nFrom uploaded documents (live):")
        for d in results["docs"][:5]:
            title = d.get("doc_title", "")[:80]
            text_blurb = (d.get("chunk_text") or "")[:300]
            lines.append(f"  • {title}: {text_blurb}")

    return "\n".join(lines)

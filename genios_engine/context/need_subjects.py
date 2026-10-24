"""G012 H-20 · a need L2 files names something Layer 1 can FETCH — or it is left as it was, and the executor says why.

L2 asks L1 for the one fact that would change its answer (`reason/l2/evidence`), and the model names what the need is
about in its own words. On the design partner's org (local copy, 24 Oct) the queue held 336 open needs and 0 answered —
the fetchers are off until one fetch is run by hand (`capture/acquire/need_fetchers`, `GENIOS_NEED_FETCHERS`) — and
arming them as the queue stood would have CLOSED nearly all of it. A closed need never reopens
(`context/evidence_need_store`: `on conflict do nothing`), so each of these was a question destroyed:

  * 184 `thread:node_…` — the graph's thread NODE, which Gmail's thread fetch refuses (`unavailable`);
  * 20 `thread: <a subject line>`, 55 `node:…` (a meeting, a person, a condition), 16 with no subject and 7 an event,
    a situation or a promise — no fetch at all (`plan_fetch` None, `unavailable`);
  * 36 `signal:…` with no window — the window fetch had no query, "found nothing" (`unavailable`).

`fetchable` resolves a raised need's subject by what memory already holds, before it is filed:

  a thread node                 → its Gmail thread (`graph_nodes.canonical_key`, `thread:<id>`);
  an event, or a signal's event → the thread its message is in (`source_events.parent_object_id`);
  a person or a company         → `party:<address or domain>` — the window fetch scoped to their mail;
  anything else (a meeting, a condition, a situation, no subject at all)
                                → the JUDGED FILE's counterparty, the same way: the need was raised about that work.

A subject already fetchable (a Gmail thread, a document, a party, a signal with a window) and one nothing resolves are
left untouched. Never raises: a need that cannot be resolved is filed as it was asked.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.evidence import EvidenceNeed

#: The subject a need about one counterparty's mail names (`capture/acquire/evidence_need.plan_fetch`).
PARTY = "party:"
THREAD = "thread:"
#: A Gmail thread id as a connector records it — hex, never a graph node's id.
_GMAIL_THREAD = re.compile(r"[0-9a-f]{12,24}")

_NODE = text("select node_type, canonical_key from graph_nodes where org_id = :o and node_id = :n and valid_to is null "
             "order by valid_from desc limit 1")
_EVENT_THREAD = text("select parent_object_id from source_events where org_id = :o and event_id = :e "
                     "and parent_object_id is not null limit 1")
_SIGNAL_EVENT = text("select event_id from qualified_signals where org_id = :o and signal_id = :s limit 1")
#: The kinds of node whose key is an address or a domain a mailbox can be searched by.
_PARTIES = ("person", "company")


def _thread_of(key: str | None) -> str | None:
    rest = str(key or "").strip()
    while rest.startswith(THREAD):
        rest = rest[len(THREAD):].strip()
    return f"{THREAD}{rest}" if _GMAIL_THREAD.fullmatch(rest) else None


def _of_node(conn, org_id: str, node_id: str) -> str | None:
    row = conn.execute(_NODE, {"o": org_id, "n": node_id}).first()
    if row is None:
        return None
    if row.node_type == "thread":
        return _thread_of(row.canonical_key)
    if row.node_type in _PARTIES and row.canonical_key:
        return f"{PARTY}{str(row.canonical_key).strip().lower()}"
    return None


def _of_event(conn, org_id: str, event_id: str) -> str | None:
    return _thread_of(conn.execute(_EVENT_THREAD, {"o": org_id, "e": event_id}).scalar())


def _of_signal(conn, org_id: str, signal_id: str) -> str | None:
    event_id = conn.execute(_SIGNAL_EVENT, {"o": org_id, "s": signal_id}).scalar()
    return _of_event(conn, org_id, event_id) if event_id else None


def resolve_subject(conn, org_id: str, subject_ref: str | None, *, file_id: str | None,
                    has_window: bool = False) -> str | None:
    """The fetchable subject for a need raised about `subject_ref` while judging the file `file_id` — or the subject
    as it was, when it is fetchable already or nothing resolves it."""
    ref = str(subject_ref or "").strip()
    if ref.startswith((PARTY, "document:", "attachment:")) or _thread_of(ref):
        return ref
    if ref.startswith("signal:") and has_window:
        return ref
    found = None
    body = ref.split(":", 1)[1].strip() if ":" in ref else ref
    if ref.startswith((THREAD, "node:")) or ref.startswith("node_"):
        found = _of_node(conn, org_id, body) if body.startswith("node_") else None
    elif ref.startswith(("evt_", "event:")):
        found = _of_event(conn, org_id, body)
    elif ref.startswith("signal:"):
        found = _of_signal(conn, org_id, body)
    if found is None and file_id:
        found = _of_node(conn, org_id, file_id)
        if found is not None and not found.startswith(PARTY):
            found = None               # a file is a counterparty's work: only its party stands in for the subject
    return found or (ref or None)


def fetchable(conn, org_id: str, need: EvidenceNeed, *, file_id: str | None) -> EvidenceNeed:
    """The need with a subject Layer 1 can fetch, when memory resolves one. Never raises."""
    try:
        subject = resolve_subject(conn, org_id, need.subject_ref, file_id=file_id,
                                  has_window=need.window_from is not None)
    except Exception:      # noqa: BLE001 — a need filed as it was asked beats a need lost
        return need
    return need if subject == need.subject_ref else need.model_copy(update={"subject_ref": subject})


__all__ = ["PARTY", "THREAD", "fetchable", "resolve_subject"]

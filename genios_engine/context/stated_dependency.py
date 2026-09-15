"""L2.7 · "the meeting is waiting on your availability" — the 95 claims nobody could use.

`correlation_dependency` resolves both ends of every dependency claim through the identity
cascade and refuses to invent a node for either. That rule is correct and this does not touch it.
Its cost, measured on the pilot, was total: 95 of 95 claims had NEITHER end resolve, because Layer
1 extracts dependencies between OUTCOMES — "Shortlisting and showcase participation", "interview
slot offer for GeniOS", "Meeting between Sehan and Rohit" — and the traversal needs parties. Every
one was counted as `UNRESOLVED_BLOCKED` and dropped.

WHAT SURVIVES THE REFUSAL IS STILL MOST OF THE ANSWER. Somebody said, in a thread with a real
counterparty, that one named thing waits on another. The card is the sentence: *"the meeting with
Sehan is waiting on Rohit's availability this week"*, *"GeniOS advancement at Antler is waiting on
Theresa Hoffmann's reconsideration"*. Both halves are quoted exactly as written, which is what
makes the card checkable without either half being resolved.

NOTHING IS RESOLVED AND NOTHING IS JOINED. The anchor is the party whose THREAD the statement was
made in — a node the graph already held, because the message was written to somebody. The two ends
travel as text. No chain, no edge, no minted node, so `chains`, `circular_wait` and `blocked_count`
are untouched and the module's own rule — a false chain is worse than a missing one — is intact.

WHAT IT REFUSES TO SAY is who or what either end IS. `dependency.blocker_identity` and
`dependency.blocked_identity` are declared missing, because the absence of both is the entire
reason this lane exists rather than an edge.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

#: ONE SPELLING, IMPORTED FROM THE WRITER — the trap `condition_situations` records against its
#: own field name, where a literal copy kept selecting nothing after the prefix moved.
from genios_engine.context.correlation_dependency import FIELD_STATED

#: Its own anchor: one counterparty can carry several stated dependencies and they end separately,
#: the same reason `condition_situations` gives for not anchoring on the person.
ANCHOR_STATED = "stated_dependency"

#: How many reach a feed from one sweep.
MAX_PER_SWEEP = 20

_ROWS = ("select f.subject_node_id as node_id, f.value as value from graph_facts f "
         "where f.org_id = :o and f.field = :field and f.status = 'active' "
         "and f.valid_to is null order by f.subject_node_id")


def statement_key(node_id: str, blocker: str, blocked: str) -> str:
    """The content address of one statement. Hashed rather than interpolated: both ends are free
    text out of somebody's sentence and a canonical key is split on a delimiter elsewhere here."""
    payload = "\x1f".join((node_id.strip(), " ".join(blocker.split()).lower(),
                           " ".join(blocked.split()).lower()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _entries(value: Any) -> tuple[Mapping, ...]:
    """The statements inside one stored row, defensively — a malformed row is one silent
    statement, an exception is every statement on the tenant."""
    if isinstance(value, (str, bytes)):
        try:
            value = json.loads(value)
        except ValueError:
            return ()
    if not isinstance(value, Mapping):
        return ()
    found = value.get("stated")
    return tuple(e for e in found if isinstance(e, Mapping)) if isinstance(found, list) else ()


def gather_stated_dependencies(conn, org_id: str) -> dict[str, object]:
    rows = conn.execute(text(_ROWS), {"o": org_id, "field": FIELD_STATED}).mappings().all()
    return {str(r["node_id"]): r["value"] for r in rows}


def read_stated_dependencies(rows: Mapping[str, object], now: datetime,
                             names: Mapping[str, str] | None = None) -> list:
    """One finding per stated dependency whose two ends are text.

    BOTH ENDS ARE REQUIRED. "Something is waiting on something" names nothing a reader can act on,
    and a card carrying one half would invite the reader to supply the other.
    """
    from genios_engine.context.outreach_situations import _Finding

    findings: list = []
    for node_id, value in rows.items():
        if str(node_id).startswith("_"):
            continue
        for entry in _entries(value):
            blocker = " ".join(str(entry.get("blocker_text") or "").split())
            blocked = " ".join(str(entry.get("blocked_text") or "").split())
            if not blocker or not blocked:
                continue
            if len(findings) >= MAX_PER_SWEEP:
                return findings

            name = str((names or {}).get(str(node_id)) or "").strip() or "this thread"
            facts: list[tuple[str, object, str]] = [
                ("dependency.blocked_text", blocked, "string"),
                ("dependency.blocker_text", blocker, "string"),
                ("dependency.counterparty", name, "string"),
            ]
            quote = str(entry.get("quote") or "").strip()
            if quote:
                facts.append(("dependency.quote", quote, "string"))
            kind = str(entry.get("dependency_type") or "").strip()
            if kind:
                facts.append(("dependency.kind", kind, "enum"))
            stated = str(entry.get("stated_at") or "").strip()
            if stated:
                facts.append(("dependency.stated_at", stated, "string"))

            findings.append(_Finding(
                anchor=ANCHOR_STATED,
                canonical_key=f"stated:{statement_key(str(node_id), blocker, blocked)}",
                display_name=f"{blocked} — waiting on {blocker}"[:120],
                facts=facts,
                concerns_node=str(node_id),
                correlation_id=f"stated:{statement_key(str(node_id), blocker, blocked)}",
                # DECLARED, AND THEIR ABSENCE IS THE POINT. Neither end resolved to anything the
                # graph holds — that is why this is a quoted statement rather than an edge, and a
                # card implying either had been identified would be claiming the resolution the
                # traversal explicitly refused to invent.
                missing=["dependency.blocker_identity", "dependency.blocked_identity"],
                inputs={"reading": ANCHOR_STATED,
                        "derived_from": "correlation_dependency, claims whose both endpoints were "
                                        "text; anchored on the party whose thread carried them"},
            ))
    return findings


__all__ = ["ANCHOR_STATED", "FIELD_STATED", "MAX_PER_SWEEP", "gather_stated_dependencies",
           "read_stated_dependencies", "statement_key"]

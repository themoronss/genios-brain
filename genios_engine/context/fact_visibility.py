"""Who may read a FACT — SCREEN_INTEL_P2 §3.4 / plan §13 P2, §14.

A fact inherits the audience of its evidence only where that evidence is PRIVATE (a seat's screen
session, a personal upload — `source_events.visibility_scope='private'`). Work facts cross seats
anyway: a deal's status or a commitment's due date is the org's business however it was learned.
Everything else learned privately — stance, relationship, sentiment, roles, thread state — is a
SEAT OVERLAY: its own active `graph_facts` version, `visibility_scope='private'` + the source's
principals, beside (never superseding) the org version (`GraphStore.write_fact`).

Only the OWNER's own surfaces read an overlay:
    query retrieval   reason/intelligence._retrieve   — the asking seat's overlay wins its field
    entity 360        context/read_models             — stored model org-only; viewer merge
Every org-level reader excludes it: rules / signals (reason/runner loaders, which also feed the
situation slice), cards (deliver/card_builder.load_node) and the decision prompt
(reason/llm_decision_maker.business_context).

A later org source supersedes the org version normally and retires the overlays; one saying the
same as an overlay widens it to org.
PostgreSQL only: the SQLite test schemas carry neither visibility column, and nothing private is
ever written there.
"""
from __future__ import annotations

from typing import Iterable, Mapping

from sqlalchemy import text

PRIVATE = "private"

#: THE work families (one constant). Derived from the fact keys the engine writes today
#: (`contracts/extraction.BusinessField`, context/pipeline.py, availability, business nouns,
#: correlation writers). An entry ending in "." is a whole family (incl. families with no live
#: key yet: invoice / vendor / opportunity / payment). Anything NOT listed stays private when its
#: only evidence is private — the conservative default.
WORK_FACT_FIELDS: frozenset[str] = frozenset({
    # deal / opportunity status, stage, amounts, dates
    "deal.status", "deal.stage", "deal.stage_age_days", "deal.amount", "deal.value",
    "deal.value_minor_units", "deal.currency", "deal.close_date", "deal.owner",
    "deal.last_inbound", "opportunity.",
    # commitments: what, who, status, due
    "commitment.status", "commitment.due_at", "commitment.last_due_at", "commitment.action",
    "commitment.text", "commitment.owner", "commitment.owner_key", "commitment.owed_to",
    "commitment.delivered_at", "commitment.days_overdue", "commitments.due",
    # availability windows and meeting dates
    "person.availability", "meeting.start_at", "meeting.scheduled", "meeting.status",
    "meeting.occurred",
    # vendor / contract / invoice / payment status and amounts
    "contract.value", "contract.currency", "contract.start_date", "contract.end_date",
    "contract.cancelled_at", "contract.vendor_node_id", "contract.status",
    "invoice.", "vendor.", "payment.",
})


def is_work_fact(field: str | None) -> bool:
    name = str(field or "").strip().lower()
    if name in WORK_FACT_FIELDS:
        return True
    return any(entry.endswith(".") and name.startswith(entry) for entry in WORK_FACT_FIELDS)


def _norm(emails: Iterable[str] | None) -> frozenset[str]:
    return frozenset(str(e).strip().lower() for e in (emails or ()) if str(e or "").strip())


def viewer_may_read(scope: str | None, principals: Iterable[str] | None,
                    viewer: str | None) -> bool:
    """One viewer. Non-private facts are org facts; a private one needs the viewer named."""
    if scope != PRIVATE:
        return True
    v = str(viewer or "").strip().lower()
    return bool(v) and v in _norm(principals)


def audience_may_read(scope: str | None, principals: Iterable[str] | None,
                      audience: Iterable[str] | None) -> bool:
    """A whole audience (a card's recipients, a situation's principals): EVERY member must be named.
    An empty audience (nobody known) may read nothing private."""
    if scope != PRIVATE:
        return True
    who = _norm(audience)
    return bool(who) and who <= _norm(principals)


def situation_audience(visibility) -> frozenset[str] | None:
    """The principals a situation is private to, or None when it is wider than one owner set.

    Only a PRIVATE situation (its narrowest member evidence was private — `narrowest()` in
    contracts/visibility) may reason over private facts, and only its own principals'."""
    if visibility is None or getattr(visibility, "scope", None) != PRIVATE:
        return None
    who = _norm(getattr(visibility, "principals", ()))
    return who or None


def private_fact_index(conn, org_id: str) -> dict[str, dict[str, frozenset[str]]]:
    """node_id → {field: principals} for every ACTIVE private fact of the org. One query; empty
    (and no query) off PostgreSQL."""
    if conn.dialect.name != "postgresql":
        return {}
    out: dict[str, dict[str, frozenset[str]]] = {}
    for r in conn.execute(text(
            "select subject_node_id, field, visibility_principals from graph_facts "
            "where org_id = :o and visibility_scope = 'private' and valid_to is null "
            "and status = 'active'"), {"o": org_id}):
        out.setdefault(r.subject_node_id, {})[r.field] = _norm(r.visibility_principals)
    return out


def drop_unreadable(facts: Mapping, private: Mapping[str, frozenset[str]] | None,
                    audience: Iterable[str] | None) -> dict:
    """`facts` (keyed by field) minus the private fields `audience` may not read."""
    if not private:
        return dict(facts)
    who = _norm(audience)
    return {f: v for f, v in facts.items()
            if f not in private or (who and who <= private[f])}


def readable_fact_idx(fact_idx: Mapping, private_idx: Mapping, audience) -> Mapping:
    """An org-wide per-node fact index with the private fields `audience` may not read removed.
    Returns the SAME object when the org has no private facts (the common, zero-cost path)."""
    if not private_idx:
        return fact_idx
    out = dict(fact_idx)
    for node, fields in private_idx.items():
        if node in out:
            out[node] = drop_unreadable(out[node], fields, audience)
    return out


__all__ = ["WORK_FACT_FIELDS", "is_work_fact", "viewer_may_read", "audience_may_read",
           "situation_audience", "private_fact_index", "drop_unreadable", "readable_fact_idx"]

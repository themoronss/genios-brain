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

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterable, Iterator, Mapping

from sqlalchemy import text

PRIVATE = "private"


# =================================================================================================
# ⛔⛔ L1-08 · WHAT A *MISSING* AUDIENCE MEANS, AT EVERY SITE THAT RESOLVES ONE WITHOUT REFUSING
# =================================================================================================
#
# Atlas **L1-08**: *"`RawObject`, `SourceEvent` and `GatedEvent` do not require visibility."* That
# is literally true — all three declare the field and all three default it to `None`. ⛔ (The
# scorecard's evidence line said *"zero declare a `visibility` field"*, which is a different and
# false claim: optional is not absent, and the two have different fixes.)
#
# ✅ WHY THE CONSEQUENCE DOES NOT HAPPEN. Four layers refuse before `None` can reach a reader, and
# they are named in `MISSING_VISIBILITY_REFUSALS` below so this module's own safety is checkable
# rather than remembered. The gate states the doctrine in its own words:
#
#     An event whose audience no derivation rule can name must not publish under a guessed one…
#     by Layer 2 the recipient list is gone, so THIS IS THE LAST GATE THAT CAN STILL REFUSE.
#
# ⛔⛔ AND THAT IS EXACTLY WHY THIS TABLE EXISTS. Three sites in `context/` read a missing audience
# as PERMITTED and two more default it to ORG-WIDE. They are correct **only because** the four
# refusals upstream mean they never see a `None` — and nothing connected them to that fact. A new
# ingestion path that did not pass the gate (a backfill, an import, an MCP write, a test double
# promoted to production) would make five sites permissive at once, in a layer that by its own
# account can no longer re-derive an audience. **The safety of a privacy default rested on one `if`
# in one file, and the readers that depend on it did not know it existed.**
#
# ⛔ FOUND BY AST, NOT BY GREP, and the sweep is the backward half of the guard. A first pass by
# grep found five sites; the AST sweep found **eight**. The three extra are `visibility_principals
# or ()`, which is a different question — and measuring it rather than assuming showed they are
# **fail-closed**: `Visibility(scope="private", principals=[]).can_view(...)` is `False` for every
# caller, org member or not. An empty principal list under `private` means NOBODY, not "no
# restriction". That is asserted in the guard rather than trusted here.
#
# Checked in BOTH directions by `tests/context/test_a_missing_audience_is_never_a_wide_one.py`: a
# declared site that no longer resolves a missing audience is as much a lie as a new site nobody
# declared, and the per-module COUNT is declared so a second site added to an
# already-declared module cannot slip through.

#: ⛔ `{module under genios_engine/context: (site_count, what a MISSING audience means, mover)}`
MISSING_VISIBILITY_SITES: dict[str, tuple[int, str, str]] = {
    "framing/timeline.py": (
        1, "⛔ OPEN — `e.visibility is None or e.visibility.can_view(…)`. An event carrying no "
           "audience is SHOWN to whoever is asking. Safe only because no such event reaches L3",
        "MOVES WITH framing/headline.py and fact_visibility.py — the three are one decision. ⛔ If "
        "the gate ever stops parking `visibility_unknown`, all three open at once"),
    "framing/headline.py": (
        1, "⛔ OPEN — the same shape over facts rather than events: a fact with no audience is "
           "included, and then `narrowest()` computes the audience from a set that already "
           "contains it",
        "MOVES WITH framing/timeline.py — see that entry"),
    "fact_visibility.py": (
        1, "⛔ OPEN-ISH — `visibility is None or scope != PRIVATE` returns None from "
           "`situation_audience`, i.e. 'wider than one owner set'. A missing audience is therefore "
           "read as NOT PRIVATE, which is the one reading that cannot be recovered from",
        "MOVES WITH framing/timeline.py — see that entry"),
    "situation_bso.py": (
        3, "⛔ TWO SITES DEFAULT TO ORG (`visibility or Visibility(scope='org', …)`) — a situation "
           "whose own audience is unknown is published org-wide. ✅ THE THIRD IS FAIL-CLOSED: "
           "`principals=list(r.visibility_principals or ())` under a `private` scope resolves to "
           "NOBODY, verified against `can_view`",
        "MOVES WHEN a situation can be built from evidence whose audience was never derived — "
        "which the gate's park is what prevents"),
    "correlation_people.py": (
        1, "✅ FAIL-CLOSED — a `private` row with no principals makes the membership test false, so "
           "the row is SKIPPED. A null principal list excludes rather than admits",
        "MOVES WITH graph_store.py — both are the same `visibility_principals or ()` idiom and "
        "both are safe for the same reason"),
    "graph_store.py": (
        1, "✅ FAIL-CLOSED — an empty principal set cannot intersect the viewer's, so no overlay is "
           "selected and the reader falls through to the org version",
        "MOVES WITH correlation_people.py — see that entry"),
}

#: ⛔ `{layer: (what it refuses, where it is)}` — the four reasons the OPEN sites above are safe.
#:
#: Each one is asserted by the guard. ⛔ They are listed in the order an event meets them, because
#: the order is the argument: by the time a reader in this package sees a fact, three refusals and
#: a schema constraint have already happened.
MISSING_VISIBILITY_REFUSALS: dict[str, tuple[str, str]] = {
    "1-derive": ("the landing seam derives an audience from the mailbox owner and the recipients "
                 "rather than requiring the caller to attach one",
                 "capture/landing/normalize.py"),
    "2-park": ("⛔⛔ THE LOAD-BEARING ONE. The gate re-derives, and when no rule names an audience "
               "it PARKS the event with `reason_code='visibility_unknown'` instead of publishing "
               "under a guess",
               "capture/gate/gate.py"),
    "3-still-blocked": ("on re-drain, a parked event whose source still has no rule stays "
                        "`STILL_BLOCKED` — the park is not aged out",
                        "capture/parked/recapture.py"),
    "4-not-null": ("the schema refuses it independently of the code: five of the six `visibility` "
                   "columns are NOT NULL, and the sixth pairs a nullable jsonb with "
                   "`visibility_scope text NOT NULL DEFAULT 'private'` — fail-closed by default",
                   "migrations/"),
}


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


#: P5 · STRICT PRIVATE EVIDENCE. A meeting transcript is its attendees' conversation (plan §2.4,
#: §7 "non-attendee sees nothing"): its commitments are exactly the work facts the rule above lets
#: cross seats, so while Layer 2 writes a transcript event this flag makes EVERY field — work
#: families included — inherit the event's private audience. Set by `context/pipeline.py` for the
#: length of one transcript event's transaction; read by `GraphStore.write_fact`.
_STRICT_PRIVATE: ContextVar[bool] = ContextVar("genios_strict_private_evidence", default=False)


@contextmanager
def strict_private_evidence(on: bool = True) -> Iterator[None]:
    token = _STRICT_PRIVATE.set(bool(on))
    try:
        yield
    finally:
        _STRICT_PRIVATE.reset(token)


def strict_private_active() -> bool:
    return _STRICT_PRIVATE.get()


def audience_checked(field: str | None) -> bool:
    """Does a write of `field` inherit a private event's audience? Outside a strict transcript
    write: every non-work field. Inside one: every field."""
    return strict_private_active() or not is_work_fact(field)


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


#: `source_events se` (left-joined; NULL = no event) / `graph_facts f` readable by `:viewer`
#: (NULL viewer — an API key — reads nothing private). Same rule as reason/moments/common's
#: VISIBLE_EVENT_SQL / VISIBLE_FACT_SQL, NULL-safe so it can be negated.
_READABLE_EVENT = ("(se.event_id is null or se.visibility_scope is distinct from 'private' or "
                   "coalesce(cast(:viewer as text) = any(coalesce(se.visibility_principals, "
                   "cast('{}' as text[]))), false))")
_READABLE_FACT = ("(f.visibility_scope is distinct from 'private' or "
                  "coalesce(cast(:viewer as text) = any(coalesce(f.visibility_principals, "
                  "cast('{}' as text[]))), false))")
_UNREADABLE_NODES = f"""
with priv as (
  select event_id from source_events where org_id = :o and visibility_scope = 'private'
     and not coalesce(cast(:viewer as text) = any(coalesce(visibility_principals,
                                                           cast('{{}}' as text[]))), false)),
cand as (
  select n.node_id from graph_nodes n join priv p on p.event_id = n.created_by_event_id
   where n.org_id = :o and n.valid_to is null
  union
  select o.subject_node_id from graph_observations o join priv p on p.event_id = o.created_by_event_id
   where o.org_id = :o and o.status = 'active'
  union
  select f.subject_node_id from graph_facts f
   where f.org_id = :o and f.valid_to is null and f.status = 'active' and not {_READABLE_FACT}
  union
  select x.node_id from graph_edges e join priv p on p.event_id = e.created_by_event_id
   cross join lateral (values (e.from_node_id), (e.to_node_id)) as x(node_id)
   where e.org_id = :o and e.valid_to is null)
select c.node_id from cand c where c.node_id is not null __AMONG__
  and not exists (select 1 from graph_nodes n join source_events se on se.org_id = n.org_id
       and se.event_id = n.created_by_event_id
       where n.org_id = :o and n.node_id = c.node_id and n.valid_to is null and {_READABLE_EVENT})
  and not exists (select 1 from graph_observations o left join source_events se
       on se.org_id = o.org_id and se.event_id = o.created_by_event_id
       where o.org_id = :o and o.subject_node_id = c.node_id and o.status = 'active'
       and {_READABLE_EVENT})
  and not exists (select 1 from graph_facts f where f.org_id = :o
       and f.subject_node_id = c.node_id and f.valid_to is null and f.status = 'active'
       and {_READABLE_FACT})
  and not exists (select 1 from graph_edges e left join source_events se
       on se.org_id = e.org_id and se.event_id = e.created_by_event_id
       where e.org_id = :o and e.valid_to is null
       and (e.from_node_id = c.node_id or e.to_node_id = c.node_id) and {_READABLE_EVENT})
"""


def unreadable_nodes(conn, org_id: str, viewer: str | None,
                     among: Iterable[str] | None = None) -> frozenset[str]:
    """Nodes `viewer` may not see at all: every piece of their evidence — the event that created
    them, their observations, their facts, their edges — is PRIVATE to other principals (another
    seat's screen session, personal upload …). A node with no evidence rows at all (seeded, manual)
    or with any readable evidence stays visible. `among` narrows the check to those nodes. Empty
    (and no query) off PostgreSQL."""
    if conn.dialect.name != "postgresql":
        return frozenset()
    params: dict = {"o": org_id, "viewer": str(viewer or "").strip().lower() or None}
    clause = ""
    if among is not None:
        ids = sorted({str(n) for n in among if n})
        if not ids:
            return frozenset()
        params["among"] = ids
        clause = "and c.node_id = any(:among)"
    return frozenset(r.node_id for r in conn.execute(
        text(_UNREADABLE_NODES.replace("__AMONG__", clause)), params))


__all__ = ["MISSING_VISIBILITY_REFUSALS", "MISSING_VISIBILITY_SITES",
           "WORK_FACT_FIELDS", "is_work_fact", "viewer_may_read", "audience_may_read",
           "situation_audience", "private_fact_index", "drop_unreadable", "readable_fact_idx",
           "unreadable_nodes"]

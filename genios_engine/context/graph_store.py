from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, get_args

from sqlalchemy import JSON, bindparam, text

from genios_engine.context.identity import register_node_identity
from genios_engine.contracts.extraction import BusinessField
from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id

# B7 commit layer — every graph write goes through here. Versioned + evidence-linked +
# transactional (all writes + version bump + change outbox in ONE transaction).


def _ts(v) -> datetime | None:
    """Normalize to a tz-aware UTC datetime for safe comparison (naive → assume UTC)."""
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def challenger_digest(value: Any) -> str:
    """The identity of a challenger VALUE (P4 §3.3 keep-blocking): a person who kept the held
    value is not asked again about the same challenger — whatever event re-asserts it."""
    blob = json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def fact_write_action(*, held_value_json: str | None, held_rank: int | None,
                      held_occurred_at, new_value_json: str, new_rank: int,
                      new_occurred_at, replay: bool = False) -> str:
    """The write_fact decision, as a pure function → 'insert' | 'noop' | 'historical' |
    'discrepancy' | 'supersede'.

    The load-bearing rule is 'historical': a fact whose occurred_at is OLDER than the held
    row's may never overwrite current state. Without this, any backfill/re-extract replays
    a 2024 `thread.ball_in_court=us` over today's `them` and the correct value is already
    stamped superseded — an unrecoverable corruption. Order of checks matters: staleness is
    decided BEFORE authority, so replaying old low-rank mail doesn't spray discrepancies
    against current system-of-record values either.

    replay=True is the belt-and-braces mode for deliberate reprocessing: it may fill a
    missing fact but NEVER supersedes an active one, regardless of timestamps."""
    if held_value_json is None:
        return "insert"
    if held_value_json == new_value_json:
        return "noop"
    ho, no = _ts(held_occurred_at), _ts(new_occurred_at)
    if ho is not None and no is not None and no < ho:
        return "historical"                       # out-of-order → record, never overwrite
    if replay:
        return "historical"                       # replay may fill gaps, never flip state
    if held_rank is not None and new_rank < held_rank:
        return "discrepancy"                      # lower authority disagrees → flag, keep held
    return "supersede"


# =================================================================================================
# L2.2.7-U1 · THE POINT-IN-TIME READ — *what did GeniOS know when it made that decision?*
# =================================================================================================
#
# `bump_version` above increments a counter, and doc 02 is blunt about what that leaves: "there is
# no `as_of` query anywhere", so the Version Manager's stated purpose — the question every
# enterprise security review asks — is not answerable. Three obligations converge on it. REPLAY:
# L1 v2 makes extraction replayable, and a decision replay also needs the graph that produced it
# or the replay is half-exact. AUDIT: the security-review question. EXPLANATION: "you recommended
# X in March" is only defensible against March's graph.
#
# THE VERSIONING ALREADY EXISTS AND THIS DOES NOT ADD A SECOND ONE. `graph_nodes`, `graph_facts`
# and `graph_edges` each carry `valid_from` / `valid_to`, every writer above sets them, and
# `merge.py` closes edges and nodes by stamping `valid_to` rather than deleting rows. So a
# point-in-time read is one predicate applied consistently to the three tables:
#
#     as at T   ->  valid_from <= T and (valid_to is null or valid_to > T)
#     live      ->  valid_to is null
#
# HALF-OPEN, `[valid_from, valid_to)`, exactly as `contracts/authority.AuthorityRule.applies_at`.
# A row closed at noon and its successor opened at noon must not both match noon, or the read
# returns two contradictory versions of one thing and the replay has no single answer. It also
# makes the out-of-order fact write disappear from history for free: `write_fact` stores a
# `historical` row with `valid_from = valid_to = now()`, an empty window, so a backfilled 2024
# value can never appear in an as-of read of 2024 — it was not known then.
#
# WHY NO `graph_snapshots` TABLE (doc 02 proposes snapshot + delta). The delta path above is
# EXACT on its own, because all three tables are already fully versioned; a snapshot would be a
# materialised cache in front of it. Building one now would add a table, an object-storage
# dependency and a weekly cadence whose only caller would be a read that is already correct
# without it — which is precisely the "unit that nothing calls" this wave exists to stop. When a
# real org makes the delta walk too slow, the snapshot goes in behind this same signature and no
# caller changes. Recorded as a deliberate gap, not an oversight.
#
# HARD RULE, and it is the one that keeps all of this true: SOFT DELETE ONLY. An edge, fact or
# node is closed by setting `valid_to`; a hard `DELETE` makes every earlier read silently change
# its answer and there is no way to recover it. `tests/context/test_point_in_time.py` scans
# `context/` for `delete from graph_*` and fails on one.


#: ⛔ L3-12 · THE NODE VOCABULARY — the sibling of `EDGE_TYPES`, and it had the same hole.
#:
#: `graph_nodes.node_type` is `text not null` with no check constraint, and its comment in
#: migration 0004 ends `-- person | company | deal | meeting | ...`. The `| ...` is the tell: an
#: open-ended list in prose with nothing enforcing it. Ten types are written across the engine, and
#: a typo of any of them mints a node no reader ever asks for.
#:
#: ⛔ `pipeline._NODE_TYPES` IS NOT THIS SET AND MUST NOT BE CONFUSED WITH IT. Its own comment says
#: so: "this whitelist governs ONLY the L2 mention loop below; the structured lane
#: (deal/meeting/subscription/product_account, anchored by source-id) is NOT gated here." It is a
#: narrower rule about which LLM entity mentions may become nodes at all. Two sets of node-type
#: names doing different jobs is exactly how a drift starts, so a test holds this one as the
#: superset.
#:
#: Each entry says what ANCHORS the node, because that is what decides whether two sightings are
#: one node — and getting it wrong is how a company is fragmented or two people are merged.
NODE_TYPES: dict[str, str] = {
    "person":           "anchored by email address. The only type an LLM mention may mint, and "
                        "only with a deterministic address behind it.",
    "company":          "anchored by email domain.",
    "deal":             "anchored by the source system's id, or 'deal:'+company when derived.",
    "meeting":          "anchored by the calendar event's own id — so each OCCURRENCE of a "
                        "recurring series is its own node, and cancelling one cancels one.",
    "thread":           "anchored by the provider's thread id.",
    "commitment":       "anchored by (subject, promise) — the thing somebody said they would do.",
    "task":             "anchored by the source system's id.",
    "subscription":     "anchored by the source system's id.",
    "product_account":  "anchored by the source system's id.",
    "tenant":           "one per org. ⛔ Deliberately NOT in ANCHOR_PRIORITY: a tenant node "
                        "reachable from correspondence would swallow every conversation in the "
                        "org into one situation.",
    # ⛔ THE TWO MINTED THROUGH A NAMED CONSTANT RATHER THAN A LITERAL, which is why the first
    # totality scan missed them: `context.documents.DOCUMENT_NODE_TYPE` and
    # `capture.structured.product_usage.PRODUCT_USAGE_NODE_TYPE`. A guard that only reads
    # `node_type="..."` sees ten of twelve and calls it total.
    "document":           "anchored by content address. See `context.documents.DOCUMENT_NODE_TYPE`.",
    "product_usage_event": "anchored by the source system's event id — the EVENT, not the account; "
                           "its facts describe the usage. See `PRODUCT_USAGE_NODE_TYPE`.",
}


# =================================================================================================
# L3-09 · THE EDGE VOCABULARY — closed, because it was a free string
# =================================================================================================
#
# `graph_edges.edge_type` is `text not null` with no check constraint, and until this constant
# existed there was no list of legal values anywhere in the engine. Six are written; anything else
# would have been accepted silently — including a typo of one of the six, which creates a relation
# no reader queries and an edge that is invisible for ever.
#
# ⛔ THE HAZARD THE SPECS NAME IS THE SAME ONE: "`related_to` must not silently become `blocks`",
# and "co-occurrence cannot produce `causes` or `blocks`". Neither could be prevented, because
# there was no vocabulary to violate.
#
# NOT A MIGRATION. A check constraint would make adding a relation a schema change and would fail
# on any historic row nobody has audited. This repo's idiom for a closed set is a Python constant
# with a totality guard in both directions — `LAYERS`, `PRECEDENCE`, `ANCHOR_FAMILIES`,
# `SYNC_HEALTHS` — and that is what this is.

#: Every relation the graph may assert, with what it means. A seventh entry is a decision: it means
#: something new is claimable about how two entities relate, and every reader that walks edges has
#: to be asked whether it should see it.
EDGE_TYPES: dict[str, str] = {
    "works_at":           "person -> company. Employment, from a domain or a stated role.",
    "attended":           "person -> meeting. Presence on a calendar event, not engagement.",
    "owns":               "company -> deal. The commercial relationship a deal sits inside.",
    "concerns":           "deal|situation -> subject. What a thing is ABOUT, deliberately weak.",
    "raised_in":          "commitment|topic -> thread. Where something was first said.",
    "corresponded_with":  "person -> person. They exchanged mail. NOT a relationship strength.",
}

#: ⛔ RELATIONS THIS GRAPH MAY NOT ASSERT, AND WHY. Each of these is a conclusion wearing an edge's
#: clothes: cheap to write, impossible to distinguish later from an observation, and named in the
#: specs as the exact thing correlation must not produce.
FORBIDDEN_EDGE_TYPES: dict[str, str] = {
    "causes": "a causal claim. CC-35: co-occurrence is not causation, and an edge cannot carry the "
              "evidence that would make it one. If something really does cause something else, it "
              "is a CONCLUSION and belongs where conclusions live, with their slice and their law.",
    "blocks": "a dependency VERDICT. DP-06: temporal order is not a prerequisite. `requires` is a "
              "claim a requirement definition can support; `blocks` is one only a reasoner can.",
    "related_to": "the untyped edge. The specs' own warning is that it "
                  "'must not silently become blocks' — and the way that happens is that somebody "
                  "writes it because the real type was unclear, and a later reader needs it to "
                  "mean something.",
}


def _confidence_bp(value: Any) -> int:
    """`numeric(4,3)` as integer basis points. Deterministic, and never a float.

    The column comes back as a `Decimal`; `float(...)` on it is how a 0.85 confidence becomes
    0.8500000000000001 in one row and 0.85 in another, and two reads of the same graph then
    compare unequal — which would make the live/as-of equivalence property untestable.
    """
    if value is None:
        return 0
    return int((Decimal(str(value)) * 10000).to_integral_value(rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class NodeAt:
    """One node VERSION. `graph_nodes` is keyed `(node_id, version)`, so a node that was amended
    has several rows and exactly one of them contains any given instant."""

    node_id: str
    version: int
    node_type: str
    canonical_key: str | None
    display_name: str | None
    identity_strength: str
    valid_from: datetime
    valid_to: datetime | None

    def as_record(self) -> dict:
        return {"node_id": self.node_id, "version": self.version, "node_type": self.node_type,
                "canonical_key": self.canonical_key, "display_name": self.display_name,
                "identity_strength": self.identity_strength}


@dataclass(frozen=True, slots=True)
class FactAt:
    """One fact version. `status` is carried rather than filtered on, because "superseded" and
    "historical" are facts ABOUT the row and a caller replaying a decision may want to see that
    the value it used was later contested."""

    fact_version_id: str
    subject_node_id: str
    field: str
    value: Any
    value_type: str
    status: str
    authority_rank: int
    occurred_at: datetime | None
    valid_from: datetime
    valid_to: datetime | None

    def as_record(self) -> dict:
        return {"fact_version_id": self.fact_version_id, "subject_node_id": self.subject_node_id,
                "field": self.field, "value": self.value, "value_type": self.value_type,
                "status": self.status, "authority_rank": self.authority_rank,
                "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None}


@dataclass(frozen=True, slots=True)
class EdgeAt:
    """One edge version. `confidence_bp` rather than the raw `numeric` for the reason
    `_confidence_bp` gives — an integer compares equal to itself."""

    edge_version_id: str
    edge_type: str
    from_node_id: str
    to_node_id: str
    confidence_bp: int
    interaction_count: int
    valid_from: datetime
    valid_to: datetime | None

    def as_record(self) -> dict:
        return {"edge_version_id": self.edge_version_id, "edge_type": self.edge_type,
                "from_node_id": self.from_node_id, "to_node_id": self.to_node_id,
                "confidence_bp": self.confidence_bp,
                "interaction_count": self.interaction_count}


@dataclass(frozen=True, slots=True)
class GraphView:
    """The graph as it stood — an IMMUTABLE view, per doc 02's `read_graph` contract.

    `as_of is None` means this is the live read. `content` is what the equivalence property
    compares: `read_graph(as_of=now).content == live_graph().content`, with the instant and the
    version left out because those legitimately differ between the two reads.
    """

    org_id: str
    as_of: datetime | None
    graph_version: int | None
    nodes: tuple[NodeAt, ...]
    facts: tuple[FactAt, ...]
    edges: tuple[EdgeAt, ...]

    @property
    def content(self) -> tuple[tuple[NodeAt, ...], tuple[FactAt, ...], tuple[EdgeAt, ...]]:
        """The graph itself, without the read's own metadata."""
        return (self.nodes, self.facts, self.edges)

    @property
    def is_empty(self) -> bool:
        """True for an instant before anything existed. A read from before the graph began is an
        EMPTY graph, never an error — doc 02 says so explicitly, and a caller replaying an old
        decision needs "we knew nothing" to be a representable answer."""
        return not (self.nodes or self.facts or self.edges)

    def node(self, node_id: str) -> NodeAt | None:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def facts_for(self, node_id: str) -> tuple[FactAt, ...]:
        return tuple(f for f in self.facts if f.subject_node_id == node_id)

    def fact(self, node_id: str, field: str) -> FactAt | None:
        for f in self.facts:
            if f.subject_node_id == node_id and f.field == field:
                return f
        return None

    def edges_touching(self, node_id: str) -> tuple[EdgeAt, ...]:
        return tuple(e for e in self.edges
                     if e.from_node_id == node_id or e.to_node_id == node_id)

    def as_record(self) -> dict:
        return {"org_id": self.org_id,
                "as_of": self.as_of.isoformat() if self.as_of else None,
                "graph_version": self.graph_version,
                "counts": {"nodes": len(self.nodes), "facts": len(self.facts),
                           "edges": len(self.edges)},
                "nodes": [n.as_record() for n in self.nodes],
                "facts": [f.as_record() for f in self.facts],
                "edges": [e.as_record() for e in self.edges]}


#: The window predicate, written once. Both reads below interpolate one of these two so the
#: live read and the as-of read cannot drift apart in one table and not the others.
#: ⛔ L3-04 · `coalesce(recorded_at, valid_from)`, NOT `valid_from`.
#:
#: The three tables this predicate spans did not agree about what `valid_from` means.
#: `graph_nodes` and `graph_facts` take the column's `now()` default, so theirs is the instant we
#: LEARNED the version. `graph_edges` binds it to `coalesce(occurred_at, now())` — the event's own
#: time — so a six-month-old email backfilled today produced an edge stamped six months ago, and an
#: as-of read of five months ago saw a relationship we learned about this morning. That is LCX-02
#: exactly: history rewritten to make the system appear to have known something earlier than it
#: did. `write_fact`'s empty-window trick protects facts from it; nothing protected edges.
#:
#: The edge column is NOT redefined, because `reason/moments/recall` and `.../slice` read it as
#: event time and are right to — changing the write would move their answers silently. Migration
#: 0184 adds `recorded_at` instead, and the coalesce keeps ONE predicate over three tables, which
#: is the property `_view` is built on.
#:
#: Pre-0184 rows carry NULL and fall back to exactly today's behaviour. We do not know when we
#: learned them, and a value that cannot be reconstructed is not fabricated.
_WINDOW_AT = ("coalesce(recorded_at, valid_from) <= :t "
              "and (valid_to is null or valid_to > :t)")
_WINDOW_OPEN = "valid_to is null"

_NODE_COLS = ("node_id, version, node_type, canonical_key, display_name, identity_strength, "
              "valid_from, valid_to")
_FACT_COLS = ("fact_version_id, subject_node_id, field, value, value_type, status, "
              "authority_rank, occurred_at, valid_from, valid_to")
_EDGE_COLS = ("edge_version_id, edge_type, from_node_id, to_node_id, confidence, "
              "interaction_count, valid_from, valid_to")


#: The two shapes `_thread_node` generates when it has nothing better. Recognised so a label this
#: module wrote can be improved later, and a label anybody ELSE wrote never is.
_THREAD_FALLBACK_PREFIXES = ("thread with ", "thread ")


def _is_generated_thread_label(label: str) -> bool:
    low = str(label or "").strip().casefold()
    return any(low.startswith(p) for p in _THREAD_FALLBACK_PREFIXES)


def thread_label(*, objective: str | None = None, counterparty: str | None = None,
                 thread_id: str | None = None) -> str:
    """The name one conversation should carry, from the best of what is known about it.

    NO RULE ABOUT WHAT A CONVERSATION IS. The objective is whatever L1 said this exchange was for,
    in its own words, and the counterparty is whoever the graph already holds — a keyword table
    mapping sentences to categories here would be tuned on one tenant's vocabulary and wrong for
    the next, which is the failure the whole layer is built to avoid.
    """
    who = " ".join(str(counterparty or "").split())
    what = " ".join(str(objective or "").split())
    if what and who:
        return f"{who} — {what}"
    if what:
        return what
    if who:
        return f"Thread with {who}"
    if thread_id:
        return f"Thread {str(thread_id)[:12]}"
    return ""


class GraphStore:
    def __init__(self, database_url: str | None = None, *, engine=None) -> None:
        if engine is None and database_url is None:
            raise ValueError("GraphStore needs a database_url or an engine")
        self._engine = engine if engine is not None else get_engine(database_url)

    @property
    def engine(self):
        return self._engine

    # ── versioning ────────────────────────────────────────────────────────────
    def bump_version(self, conn, org_id: str) -> int:
        conn.execute(text(
            "insert into graph_versions (org_id, graph_version) values (:o, 1) "
            "on conflict (org_id) do update set graph_version = graph_versions.graph_version + 1, "
            "updated_at = now()"), {"o": org_id})
        # P3 hot lane: every graph write takes this step, so the seats holding a live device get
        # a new slice version + a `slice.delta` event in the SAME transaction (one statement,
        # PostgreSQL only). See reason/moments/slice.py for why this is the hook.
        from genios_engine.platform.realtime import bump_slice_versions
        bump_slice_versions(conn, org_id)
        return conn.execute(text("select graph_version from graph_versions where org_id=:o"),
                            {"o": org_id}).scalar()

    # ── identity (B5): find-or-create by deterministic canonical_key ───────────
    def find_or_create_node(self, conn, *, org_id: str, node_type: str,
                            canonical_key: str | None, display_name: str | None,
                            event_id: str | None) -> str:
        if canonical_key:
            row = conn.execute(text(
                "select node_id from graph_nodes where org_id=:o and canonical_key=:k "
                "and valid_to is null limit 1"), {"o": org_id, "k": canonical_key}).first()
            if row:
                # Re-register on every sighting, not just at creation: a node's display
                # name usually arrives AFTER its anchor did (an email gives you acme.io
                # today and the words "Acme Technologies" next week), and that later name
                # is exactly the key a prose mention needs to find it by.
                register_node_identity(conn, org_id=org_id, node_id=row.node_id,
                                       node_type=node_type, canonical_key=canonical_key,
                                       display_name=display_name, event_id=event_id)
                return row.node_id
        node_id = new_id("node")
        conn.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
            # L3-04 · `recorded_at` is stamped by the DATABASE, never handed in. A caller that
            # could supply it could backdate what we knew, which is the one thing an audit read
            # must be unable to express.
            "display_name, identity_strength, created_by_event_id, recorded_at) "
            "values (:id, 1, :o, :nt, :k, :dn, :st, :ev, now())"),
            {"id": node_id, "o": org_id, "nt": node_type, "k": canonical_key,
             "dn": display_name, "st": "strong" if canonical_key else "weak", "ev": event_id})
        # Claim the keys this node can be found by. A key already held by ANOTHER node
        # raises a merge proposal and changes nothing — the first claimant keeps it, so
        # lookups stay stable while a human decides.
        register_node_identity(conn, org_id=org_id, node_id=node_id, node_type=node_type,
                               canonical_key=canonical_key, display_name=display_name,
                               event_id=event_id)
        return node_id

    def name_person_node(self, conn, *, org_id: str, node_id: str,
                         name: str | None) -> bool:
        """Give a person node a human name, but only while it is still called after their address.

        THE THIRD TWIN, and it exists for the same reason as `name_company_node` and
        `name_thread_node`: `find_or_create_node` writes `display_name` when it CREATES a node and
        never again. It re-registers aliases on every later sighting and leaves the label exactly
        as the first event wrote it.

        For a person that first arrival is usually a To/Cc line, which carries a bare address —
        recipients are not described, only senders are. So somebody who was cc'd in March and has
        written to us every week since is still called `theresa.hoffmann@antler.co` on every card,
        while the From header of their own mail has said "Theresa Hoffmann" a hundred times.

        MEASURED ON THE PILOT 2026-09-16: 35 of 76 person nodes displayed a bare address, and for
        8 of them a From-header display name was already sitting in their own `source_events`
        rows, unused. The remaining 27 have never sent us anything — they are named by nobody, and
        this correctly leaves them alone.

        NOTHING IS INFERRED. The caller has already matched the address to THIS node by exact key
        equality; the name comes from `parseaddr` on the From header, not from a model and not
        from similarity.

        Promotion happens only while the display name restates the anchor. A name from anywhere
        else — a connector, a human, an earlier and better sighting — outranks a header line and
        must never be overwritten by one. Returns True when the node was renamed.
        """
        cleaned = str(name or "").strip()
        if not cleaned:
            return False
        row = conn.execute(text(
            "select canonical_key, display_name from graph_nodes "
            "where org_id=:o and node_id=:n and valid_to is null"),
            {"o": org_id, "n": node_id}).first()
        if row is None:
            return False
        current = str(row.display_name or "").strip()
        anchor_key = str(row.canonical_key or "").strip()
        # Compare the rendered strings rather than carry a flag, so this is also true of every
        # node created before the promotion existed — which is all of them.
        if current and current.casefold() != anchor_key.casefold():
            return False
        if cleaned.casefold() == current.casefold():
            return False
        # AND THE NAME MUST NOT BE THE ADDRESS AGAIN. A From header reading
        # `"priya@chat360.io" <priya@chat360.io>` parses to a display name that is the address,
        # and promoting it would rewrite the label with the thing it was supposed to replace —
        # a no-op that reports True and tells a reader the node was named.
        if "@" in cleaned and cleaned.casefold() == anchor_key.casefold():
            return False
        conn.execute(text(
            "update graph_nodes set display_name=:dn "
            "where org_id=:o and node_id=:n and valid_to is null"),
            {"dn": cleaned, "o": org_id, "n": node_id})
        return True

    def name_company_node(self, conn, *, org_id: str, node_id: str,
                          name: str | None) -> bool:
        """Give a company node a human name, but only while it is still called after its anchor.

        A company is anchored on an email domain, so it is created called "devdashlabs.com" and
        the loop above never revisits that: it re-registers aliases on every later sighting and
        leaves `display_name` exactly as the first event wrote it. So the name a card prints was
        decided by the one fact that is guaranteed NOT to be a name. Measured on the design
        partner's org: 19 of 47 live card headlines opened on a hostname — "errorcore.dev: no
        problem documented yet", "rizvi.nu: no problem recorded yet" — while the extractor had
        already pulled "DevDash Labs", "Crescere Labs", "Titan Capital" and "Z Fellows" out of
        that same mailbox.

        The caller has already resolved the name to THIS node by exact key equality against the
        node's own anchor key, so nothing here is inferred from similarity.

        Promotion happens only while the display name restates the anchor. A name from anywhere
        else — a connector, a human, an earlier and better mention — outranks a prose mention and
        must never be overwritten by one. Returns True when the node was renamed.
        """
        cleaned = str(name or "").strip()
        if not cleaned:
            return False
        row = conn.execute(text(
            "select canonical_key, display_name from graph_nodes "
            "where org_id=:o and node_id=:n and valid_to is null"),
            {"o": org_id, "n": node_id}).first()
        if row is None:
            return False
        current = str(row.display_name or "").strip()
        anchor = str(row.canonical_key or "").strip()
        # Compare the rendered strings rather than carry a flag, so this is also true of every
        # node created before the promotion existed — which is all of them.
        if current and current.casefold() != anchor.casefold():
            return False
        if cleaned.casefold() == current.casefold():
            return False
        conn.execute(text(
            "update graph_nodes set display_name=:dn "
            "where org_id=:o and node_id=:n and valid_to is null"),
            {"dn": cleaned, "o": org_id, "n": node_id})
        return True

    def name_thread_node(self, conn, *, org_id: str, node_id: str,
                         objective: str | None = None,
                         counterparty: str | None = None) -> bool:
        """Give a conversation a name a person can recognise. The thread twin of
        `name_company_node`, and it exists for the same reason and follows the same rule.

        WHAT A THREAD IS CALLED TODAY, and why both spellings fail a reader. `_thread_node` builds
        its label as `"Thread with <counterparty>"` when it is handed one and `"Thread <id[:12]>"`
        when it is not. Measured on the pilot: 236 threads, **151 of them named after a hex
        fragment** — because two of the four callers pass `counterparty=None`. And the other 85 are
        no better for the reader they are shown to: one counterparty is in FIFTEEN separate
        conversations and all fifteen nodes are labelled `"Thread with boardy@boardy.ai"`. The node
        identity is exactly right — fifteen key spaces, which is the whole point of the thread node
        — and the name distinguishes none of them.

        THE NAME COMES FROM WHAT THE CONVERSATION IS FOR. `thread.objective` is a one-line
        statement of that, written by L1 and carried on 210 of the 236 threads, so the label
        becomes "Boardy — intro call about the paid sales motion" instead of "Thread 1a07a6e0ca77".
        The counterparty leads it because that is what a reader scans for first, and the objective
        says which of their conversations this is.

        A CASCADE, NOT A REQUIREMENT, because a lane that only names what it fully understands
        leaves everything else unreadable. Objective and counterparty together, then either alone,
        and the raw id survives as the last resort — it is a poor name and it is never a wrong one.

        PROMOTED ONLY WHILE THE LABEL IS STILL ONE THIS FUNCTION GENERATED, exactly as
        `name_company_node` promotes only while the display name restates the anchor. A name from
        a connector, a human, or an earlier and better mention outranks anything derived here and
        must never be overwritten by it. Returns True when the node was renamed.
        """
        label = thread_label(objective=objective, counterparty=counterparty)
        if not label:
            return False
        row = conn.execute(text(
            "select display_name from graph_nodes "
            "where org_id=:o and node_id=:n and valid_to is null"),
            {"o": org_id, "n": node_id}).first()
        if row is None:
            return False
        current = str(row.display_name or "").strip()
        # Compared against the SHAPES this module generates rather than carried as a flag, so it
        # is also true of every thread created before this function existed — which is all of them.
        if current and not _is_generated_thread_label(current):
            return False
        if label.casefold() == current.casefold():
            return False
        conn.execute(text(
            "update graph_nodes set display_name=:dn "
            "where org_id=:o and node_id=:n and valid_to is null"),
            {"dn": label[:120], "o": org_id, "n": node_id})
        return True

    def rename_reading_anchor(self, conn, *, org_id: str, node_id: str,
                              canonical_key: str, display_name: str | None) -> bool:
        """Keep a reading's own anchor wearing the sentence that reading composes today.

        `find_or_create_node` sets `display_name` at creation and never revisits it, which is right
        for a person or a company — a name is a fact about them, and a later sighting must not
        overwrite a better one. A reading anchor is the opposite kind of thing: the node exists
        only to carry one reading's output, its key is minted by that reading, and its label is
        recomposed from current facts on every sweep. Freezing that label means a headline written
        by an older build of the reading survives every later correction.

        THE KEY IS THE PERMISSION. The rename happens only when the node still answers to the
        canonical key the finding was minted under, so this can reach nothing but the reading's own
        namespace. Returns True when the label changed.
        """
        wanted = " ".join(str(display_name or "").split())
        if not wanted or not canonical_key:
            return False
        row = conn.execute(text(
            "select display_name from graph_nodes where org_id=:o and node_id=:n "
            "and canonical_key=:k and valid_to is null"),
            {"o": org_id, "n": node_id, "k": canonical_key}).first()
        if row is None or str(row.display_name or "").strip() == wanted:
            return False
        conn.execute(text(
            "update graph_nodes set display_name=:dn where org_id=:o and node_id=:n "
            "and canonical_key=:k and valid_to is null"),
            {"dn": wanted[:120], "o": org_id, "n": node_id, "k": canonical_key})
        return True

    def map_identity(self, conn, *, org_id: str, source: str, source_object_id: str,
                     node_id: str) -> None:
        conn.execute(text(
            "insert into source_identity_map (org_id, source, source_object_id, node_id) "
            "values (:o, :src, :soid, :n) on conflict (org_id, source, source_object_id) "
            "do nothing"), {"o": org_id, "src": source, "soid": source_object_id, "n": node_id})

    # ── facts / observations / evidence ───────────────────────────────────────
    def write_fact(self, conn, *, org_id: str, subject_node_id: str, field: str,
                   value: Any, value_type: str, confidence: float,
                   occurred_at: datetime | None, event_id: str,
                   evidence: dict, source: str | None, authority_rank: int = 1,
                   relevance: float | None = None,
                   replay: bool = False) -> str | None:
        """B6/B7: authority-aware, no-op-aware, out-of-order-aware, versioned. The decision
        itself lives in fact_write_action() (pure, tested). Returns the new fact_version_id,
        or None on no-op / discrepancy (held value kept). An out-of-order write (older
        occurred_at than the held row, or any conflicting write under replay=True) lands as
        status='historical' — preserved with provenance, never the active value."""
        # WHO MAY READ THIS FACT (SCREEN_INTEL_P2 §3.4). Outside the work families a fact whose
        # evidence is PRIVATE (a seat's screen, a personal upload) is a SEAT OVERLAY: its own
        # active version, `visibility_scope='private'` + the source's principals, BESIDE the org
        # version — never superseding it, so other seats keep the org value and the owner reads
        # their own. Org-level readers (rules, signals, cards, slices) exclude overlays; only the
        # owner's query and entity 360 read them. A later org source supersedes the org version
        # normally and retires the overlays; one saying the same as an overlay widens it to org.
        # The event's audience and every live version ride on ONE statement. PostgreSQL only —
        # the SQLite test schemas carry no visibility columns and never hold a private event.
        # P5: inside a transcript event's write (`strict_private_evidence`) work facts inherit the
        # private audience too — a meeting's commitments are its attendees' business only.
        from genios_engine.context.fact_visibility import audience_checked
        dialect = getattr(getattr(conn, "dialect", None), "name", "")    # test doubles have none
        audience_check = dialect == "postgresql" and audience_checked(field)
        new_private = False
        new_principals: list[str] = []
        overlays: list = []
        if audience_check:
            rows = conn.execute(text(
                "select f.fact_version_id, f.value, f.authority_rank, f.occurred_at, "
                "f.visibility_scope, f.visibility_principals, "
                "se.visibility_scope as ev_scope, se.visibility_principals as ev_principals "
                "from (select 1) one "
                "left join source_events se on se.org_id=:o and se.event_id=:e "
                "left join graph_facts f on f.org_id=:o and f.subject_node_id=:s "
                "and f.field=:f and f.valid_to is null and f.status='active' "
                "order by f.occurred_at desc nulls last, f.fact_version_id desc"
            ).columns(value=JSON), {"o": org_id, "s": subject_node_id, "f": field,
                                    "e": event_id}).fetchall()
            new_private = rows[0].ev_scope == "private"
            new_principals = sorted({str(p).strip().lower() for p in (rows[0].ev_principals or ())
                                     if str(p or "").strip()})
            live = [r for r in rows if r.fact_version_id is not None]
            org_rows = [r for r in live if r.visibility_scope != "private"]
            overlays = [r for r in live if r.visibility_scope == "private"]
            same = json.dumps(value, default=str)
            if new_private:
                mine = set(new_principals)
                own = next((r for r in overlays
                            if mine & {str(p).strip().lower()
                                       for p in (r.visibility_principals or ())}), None)
                if own is not None:
                    held = own                      # this seat's own overlay: the private lane
                elif org_rows and json.dumps(org_rows[0].value, default=str) == same:
                    held = org_rows[0]              # corroborates the org value; no overlay
                else:
                    held = None                     # a NEW overlay; the org version is untouched
            else:
                held = org_rows[0] if org_rows else None
                if held is None:                    # an org source saying what an overlay says
                    held = next((r for r in overlays
                                 if json.dumps(r.value, default=str) == same), None)
        else:
            held = conn.execute(text(
                "select fact_version_id, value, authority_rank, occurred_at from graph_facts "
                "where org_id=:o and subject_node_id=:s and field=:f "
                "and valid_to is null and status='active' "
                "limit 1").columns(value=JSON),
                {"o": org_id, "s": subject_node_id, "f": field}).first()
        new_val = json.dumps(value, default=str)
        held_val = None
        if held is not None:
            # JSON column decoding is explicit for SQLite and native under psycopg. A PG
            # string value is already decoded, not JSON text to pass into json.loads again.
            held_val = json.dumps(held.value, default=str)

        action = fact_write_action(
            held_value_json=held_val, held_rank=held.authority_rank if held else None,
            held_occurred_at=held.occurred_at if held else None,
            new_value_json=new_val, new_rank=authority_rank,
            new_occurred_at=occurred_at, replay=replay)

        # Task 2: a stated purpose outranks a judgement in BOTH arrival orders. Two SQLite
        # regressions exposed older observations being filed as history and same-value R2
        # confirmation leaving R1 active. Restrict this promotion to the nine business fields,
        # an explicitly observed receipt, and a held R1 guess. Replay and R2+ history stay intact.
        if (held is not None and not replay and field in get_args(BusinessField)
                and (evidence or {}).get("standing") == "observed"
                and held.authority_rank == 1 and authority_rank >= 2):
            action = "supersede"

        held_private = held is not None and getattr(held, "visibility_scope", None) == "private"
        lane_private = audience_check and new_private
        if lane_private and action == "discrepancy":
            # A seat's private claim never opens an org-visible discrepancy; it is kept as that
            # seat's history instead.
            action = "historical"

        if action == "noop":
            # CORROBORATION — the cross-intelligence write. A second source asserting the
            # SAME value is not "nothing happened": it is independent confirmation, and it
            # is what the scoring ladder (one:60 / two:85 / three+:100) and engine's
            # src_count read. This branch used to return None before any ref was written,
            # so src_count could never exceed 1 and the whole ladder was dead code —
            # email + CRM agreeing looked identical to email alone. The ref attaches to
            # the HELD (current) version; deduped per event so a re-sync doesn't inflate;
            # distinct-source counting downstream handles same-source repeats.
            already = conn.execute(text(
                "select 1 from graph_source_refs where fact_version_id=:fv "
                "and event_id=:e limit 1"),
                {"fv": held.fact_version_id, "e": event_id}).first()
            if already is None:
                self._write_ref(conn, org_id=org_id, fact_version_id=held.fact_version_id,
                                event_id=event_id, source=source,
                                evidence={**(evidence or {}), "corroborates": True})
                if held_private:
                    self._merge_private_audience(conn, held.fact_version_id,
                                                 private=new_private, principals=new_principals)
            return None
        if action == "discrepancy":
            # held keeps its OWN value (the system-of-record), challenger carries the new one.
            # (Was a bug: both sides recorded the challenger value → 'paid vs paid', real
            #  conflict lost — e.g. Stripe 'paid' R3 vs email 'unpaid' R2.)
            # `fact_version_id` / `occurred_at` let a reader say WHERE and WHEN each side came from
            # (P4 §3.3) and let the seat filter read the held version's audience.
            self.write_discrepancy(conn, org_id=org_id, subject_node_id=subject_node_id,
                                   field=field,
                                   held={"value": json.loads(held_val), "rank": held.authority_rank,
                                         "fact_version_id": held.fact_version_id,
                                         "occurred_at": held.occurred_at},
                                   challenger={"value": value, "rank": authority_rank,
                                               "source": source, "event_id": event_id,
                                               "occurred_at": occurred_at})
            return None
        if action == "supersede":
            conn.execute(text("update graph_facts set valid_to=now(), status='superseded' "
                              "where fact_version_id=:fv"), {"fv": held.fact_version_id})
            # The field has been authoritatively re-decided → any open discrepancy recorded
            # against the OLD value is settled. This is what lets `consistency` recover
            # instead of falling forever. (Not for a seat superseding its own private overlay:
            # the org's field has not been re-decided.)
            if not held_private:
                self.resolve_discrepancies(conn, org_id=org_id, subject_node_id=subject_node_id,
                                           field=field)

        status = "historical" if action == "historical" else "active"
        fv = new_id("factv")
        conn.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "value, value_type, status, authority_rank, confidence, relevance, occurred_at, "
            "created_by_event_id, derivation_type, trace_id, schema_version, source_authority, "
            # L3-04 · knowledge time, stamped by the database. Distinct from `occurred_at`
            # two columns up, which is when the world moved.
            "provenance_refs, recorded_at"
            + (", valid_to" if status == "historical" else "") + ") "
            "values (:fv, :fid, :o, :s, :f, :val, :vt, :st, :ar, :c, :rel, :oc, :ev, "
            "'source_event', :ev, 'graph-fact.v2', :authority, :provenance, now()"
            + (", now()" if status == "historical" else "") + ")").bindparams(
                bindparam("val", type_=JSON), bindparam("provenance", type_=JSON)),
            {"fv": fv, "fid": new_id("fact"), "o": org_id, "s": subject_node_id, "f": field,
             "val": json.loads(new_val), "vt": value_type, "st": status, "ar": authority_rank,
             "c": confidence, "rel": relevance, "oc": occurred_at, "ev": event_id,
             "authority": f"R{authority_rank}",
             "provenance": [f"event:{event_id}"]})
        if lane_private:
            conn.execute(text(
                "update graph_facts set visibility_scope='private', visibility_principals=:p "
                "where fact_version_id=:fv"), {"p": new_principals, "fv": fv})
        elif audience_check and overlays and status == "active":
            # A new ORG value for the field supersedes normally — and the seats' private overlays
            # of the older state with it.
            conn.execute(text(
                "update graph_facts set valid_to=now(), status='superseded' "
                "where org_id=:o and subject_node_id=:s and field=:f and valid_to is null "
                "and status='active' and visibility_scope='private'"),
                {"o": org_id, "s": subject_node_id, "f": field})
        self._write_ref(conn, org_id=org_id, fact_version_id=fv, event_id=event_id,
                        source=source, evidence=evidence)
        return fv

    def _merge_private_audience(self, conn, fact_version_id: str, *, private: bool,
                                principals: list[str]) -> None:
        """A private fact corroborated by another source: a NON-private one widens it to org (the
        org now holds the same knowledge through a channel it may read); another private one adds
        that source's principals (two seats saw it, both may read it)."""
        if not private:
            conn.execute(text(
                "update graph_facts set visibility_scope='org', visibility_principals=null "
                "where fact_version_id=:fv and visibility_scope='private'"),
                {"fv": fact_version_id})
            return
        conn.execute(text(
            "update graph_facts set visibility_principals = (select array_agg(distinct x order "
            "by x) from unnest(coalesce(visibility_principals, cast('{}' as text[])) || "
            "cast(:p as text[])) as x) where fact_version_id=:fv and visibility_scope='private'"),
            {"p": principals, "fv": fact_version_id})

    def write_discrepancy(self, conn, *, org_id, subject_node_id, field, held, challenger) -> None:
        """One OPEN discrepancy per (subject, field). A field is either contested or not, and
        `consistency` scores the COUNT of contested fields — so inserting a fresh row for
        every disagreeing event let a SINGLE recurring conflict (the same stale email
        re-arriving) stack to 3+ and pin the entity's consistency to 0 permanently. If an
        open row already exists for this field, refresh it to the latest disagreement
        instead of stacking a duplicate."""
        payload = {"o": org_id, "s": subject_node_id, "f": field,
                   "h": json.loads(json.dumps(held, default=str)),
                   "c": json.loads(json.dumps(challenger, default=str))}
        if getattr(getattr(conn, "dialect", None), "name", "") == "postgresql":
            self._write_discrepancy_pg(conn, payload,
                                       digest=challenger_digest((challenger or {}).get("value")))
            return
        updated = conn.execute(text(
            "update discrepancies set held=:h, challenger=:c "
            "where org_id=:o and subject_node_id=:s and field=:f and status='open'").bindparams(
                bindparam("h", type_=JSON), bindparam("c", type_=JSON)),
            payload).rowcount
        if not updated:
            conn.execute(text(
                "insert into discrepancies (id, org_id, subject_node_id, field, held, challenger) "
                "values (:id, :o, :s, :f, :h, :c)").bindparams(
                    bindparam("h", type_=JSON), bindparam("c", type_=JSON)),
                {"id": new_id("disc"), **payload})

    def resolve_discrepancies(self, conn, *, org_id, subject_node_id, field) -> int:
        """Close open discrepancies on a field once it has been authoritatively re-decided.
        Without this `consistency` only ever falls: it is what lets a situation RECOVER
        after the sources agree again. Called on supersede — the field's state has moved
        on, so a disagreement recorded against the OLD held value is settled. Returns the
        number closed."""
        if getattr(getattr(conn, "dialect", None), "name", "") == "postgresql":
            # A snoozed disagreement about the OLD value is settled too; the resolution says it
            # was the sources, not a person, that settled it (P4 §3.3, migration 0153).
            return conn.execute(text(
                "update discrepancies set status='resolved', resolution='superseded', "
                "resolved_at=now(), updated_at=now() where org_id=:o and subject_node_id=:s "
                "and field=:f and status in ('open', 'snoozed')"),
                {"o": org_id, "s": subject_node_id, "f": field}).rowcount or 0
        return conn.execute(text(
            "update discrepancies set status='resolved' where org_id=:o "
            "and subject_node_id=:s and field=:f and status='open'"),
            {"o": org_id, "s": subject_node_id, "f": field}).rowcount or 0

    #: A kept challenger is not raised again for this long (P4 §3.3).
    KEEP_DAYS = 30

    def _write_discrepancy_pg(self, conn, payload: dict, *, digest: str) -> None:
        """PostgreSQL: the same one-row-per-field rule, plus P4's resolution state.

        * a challenger a person KEPT (same digest) within KEEP_DAYS is not raised again;
        * a snoozed row is refreshed but stays snoozed until it wakes;
        * `updated_at` moves only when the challenger actually changed — the verify pass reads
          by it, so a re-sync of the same stale email is not a new disagreement."""
        kept = conn.execute(text(
            "select 1 from discrepancies where org_id=:o and subject_node_id=:s and field=:f "
            "and status='kept' and challenger_digest=:d "
            "and resolved_at > now() - make_interval(days => :k) limit 1"),
            {"o": payload["o"], "s": payload["s"], "f": payload["f"], "d": digest,
             "k": self.KEEP_DAYS}).first()
        if kept is not None:
            return
        params = {**payload, "d": digest}
        updated = conn.execute(text(
            "update discrepancies set held=:h, challenger=:c, "
            "updated_at = case when challenger_digest is distinct from :d then now() "
            "else updated_at end, challenger_digest=:d "
            "where org_id=:o and subject_node_id=:s and field=:f "
            "and status in ('open', 'snoozed')").bindparams(
                bindparam("h", type_=JSON), bindparam("c", type_=JSON)), params).rowcount
        if not updated:
            conn.execute(text(
                "insert into discrepancies (id, org_id, subject_node_id, field, held, challenger, "
                "challenger_digest, updated_at) values (:id, :o, :s, :f, :h, :c, :d, now())"
            ).bindparams(bindparam("h", type_=JSON), bindparam("c", type_=JSON)),
                {"id": new_id("disc"), **params})

    def write_observation(self, conn, *, org_id: str, subject_node_id: str | None,
                          kind: str, confidence: float, occurred_at: datetime | None,
                          event_id: str, evidence: dict, source: str | None) -> str:
        obs_id = new_id("obs")
        conn.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "occurred_at, confidence, created_by_event_id) "
            "values (:id, :o, :s, :k, :oc, :c, :ev)"),
            {"id": obs_id, "o": org_id, "s": subject_node_id, "k": kind, "oc": occurred_at,
             "c": confidence, "ev": event_id})
        self._write_ref(conn, org_id=org_id, observation_id=obs_id, event_id=event_id,
                        source=source, evidence=evidence)
        return obs_id

    def write_event_presence(self, conn, *, org_id: str, subject_node_id: str,
                             occurred_at: datetime | None, event_id: str,
                             evidence: dict, source: str | None) -> bool:
        """One event establishes a subject; it does not make that subject the speaker.

        The pilot's 50 calendar events produced zero observations, and 30 non-replying
        people also had none. A stable org/event/subject ID makes replay and concurrent
        retries no-ops; this does not deduplicate or rewrite existing semantic observations.
        """
        digest = hashlib.sha256(json.dumps([org_id, event_id, subject_node_id]).encode()).hexdigest()[:32]
        obs_id = f"obs_presence_{digest}"
        inserted = conn.execute(text(
            "insert into graph_observations (observation_id,org_id,subject_node_id,kind,"
            "occurred_at,confidence,created_by_event_id) "
            "values (:id,:org,:subject,'event_presence',:at,1.0,:event) "
            "on conflict (observation_id) do nothing"),
            {"id": obs_id, "org": org_id, "subject": subject_node_id,
             "at": occurred_at, "event": event_id}).rowcount
        if inserted:
            self._write_ref(conn, org_id=org_id, observation_id=obs_id, event_id=event_id,
                            source=source, evidence=evidence)
        return bool(inserted)

    def write_received_observation(self, conn, *, org_id: str, subject_node_id: str,
                                   kind: str, confidence: float, occurred_at: datetime | None,
                                   event_id: str, evidence: dict, source: str | None) -> bool:
        """What WE said, recorded as evidence about the person we said it to.

        `write_event_presence` above establishes that an event touched a node. It deliberately
        carries no substance, and for a while that was all an outbound recipient ever got — so a
        founder who wrote to an investor twice left two content-free markers on that investor,
        while every commitment, question and observation in those mails was filed against the
        founder's OWN node. Measured on the pilot: 398 of 1001 observations on the mailbox owner,
        and 30 of 60 people carrying zero — the exact people who never replied, which is the
        subject of every "they have gone quiet" reading. `evidence_score` counts observations on
        the anchor, so those anchors scored zero and the publisher held them. Our own work was not
        counted as knowledge about the relationship it was done in.

        THE KIND IS `received:` AND THAT PREFIX IS THE WHOLE SAFETY PROPERTY. A recipient must
        never become the SPEAKER of words they did not write — `test_outbound_recipient_
        observations.py` exists to protect exactly that and its intent is correct. "They were told
        this" and "they said this" are different claims about a person, so they are different
        rows: the prefix cannot be read as speech, and `speaker_node_id` in the evidence names who
        actually wrote it. Any reader selecting on a bare kind sees only what somebody really said.

        CONTENT-ADDRESSED, unlike `write_observation`. That one mints `new_id("obs")` and is
        therefore not replay-safe; it is called once per extraction on one subject, where a
        re-sync is guarded upstream. This fans one event out across every recipient, so a re-sync
        would multiply the very number the evidence axis reads. The id is derived from the event,
        the subject, the kind and the quoted text, which makes a second sweep a no-op.
        """
        digest = hashlib.sha256(json.dumps(
            [org_id, event_id, subject_node_id, kind, str(evidence.get("text") or "")],
        ).encode()).hexdigest()[:32]
        obs_id = f"obs_received_{digest}"
        inserted = conn.execute(text(
            "insert into graph_observations (observation_id,org_id,subject_node_id,kind,"
            "occurred_at,confidence,created_by_event_id) "
            "values (:id,:org,:subject,:kind,:at,:conf,:event) "
            "on conflict (observation_id) do nothing"),
            {"id": obs_id, "org": org_id, "subject": subject_node_id, "kind": kind,
             "at": occurred_at, "conf": confidence, "event": event_id}).rowcount
        if inserted:
            self._write_ref(conn, org_id=org_id, observation_id=obs_id, event_id=event_id,
                            source=source, evidence=evidence)
        return bool(inserted)

    # ── relationships (B7 edges) ──────────────────────────────────────────────
    def write_edge(self, conn, *, org_id: str, edge_type: str, from_node_id: str,
                   to_node_id: str, confidence: float, occurred_at: datetime | None,
                   event_id: str, evidence: dict, source: str | None,
                   authority_rank: int = 2, count_interaction: bool = True) -> str | None:
        """Idempotent relationship edge (e.g. person→attended→meeting, person→works_at→company).
        No self-loops, and an identical active edge (same type+from+to) is a no-op — so re-syncing
        never duplicates edges. Returns the new edge_version_id, or None on skip/no-op.

        `count_interaction=False` is for DERIVED edges a reading re-asserts on every sweep (the
        support and outreach `concerns` links): re-asserting one is not contact, so it advances
        `last_seen_at` without bumping `interaction_count` — otherwise the count measures how
        many sweeps ran, not how often two parties interacted.

        ⛔ L3-09 · `edge_type` IS CHECKED AGAINST A CLOSED SET, AND AN UNKNOWN ONE RAISES.
        The column is free text and was unvalidated, so a typo of an existing type — `attend`,
        `work_at` — wrote a relation no reader queries, and the edge became invisible for ever with
        nothing failing. A raise is right rather than a skip: an edge type is written by a
        programmer, not supplied by data, so an unknown one is a bug in the caller and a silent
        drop would let it ship. Same seam and same argument as `corroborate`'s refusal to lift an
        unnamed confidence.

        `FORBIDDEN_EDGE_TYPES` raises with its own reason, because "causes" and "blocks" are not
        typos — they are conclusions somebody is about to store as observations."""
        if edge_type in FORBIDDEN_EDGE_TYPES:
            raise ValueError(
                f"graph edges may not assert {edge_type!r}: {FORBIDDEN_EDGE_TYPES[edge_type]}")
        if edge_type not in EDGE_TYPES:
            raise ValueError(
                f"unknown edge_type {edge_type!r}. The graph's relations are a closed set "
                f"({', '.join(sorted(EDGE_TYPES))}) — an unlisted one is a relation no reader "
                "queries. Add it to EDGE_TYPES with what it means, or use the one that fits.")
        if not from_node_id or not to_node_id or from_node_id == to_node_id:
            return None
        held = conn.execute(text(
            "select edge_version_id from graph_edges where org_id=:o and edge_type=:t "
            "and from_node_id=:f and to_node_id=:tn and valid_to is null limit 1"),
            {"o": org_id, "t": edge_type, "f": from_node_id, "tn": to_node_id}).first()
        if held is not None:
            # Relationship DEPTH: a repeat interaction is not a no-op — it bumps the
            # edge's interaction_count and advances last_seen_at. This is the difference
            # between a relationship graph and a boolean adjacency list (and the
            # substrate relationship_stage / attention read). Still returns None:
            # no new edge VERSION was created.
            conn.execute(text(
                "update graph_edges set interaction_count = coalesce(interaction_count,1) + :bump, "
                "last_seen_at = greatest(coalesce(last_seen_at, valid_from, now()), "
                "coalesce(cast(:oc as timestamptz), now())) "
                "where edge_version_id=:ev"),
                {"ev": held.edge_version_id, "oc": occurred_at,
                 "bump": 1 if count_interaction else 0})
            return None
        edge_version_id = new_id("edgev")
        conn.execute(text(
            "insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, "
            # ⛔ L3-04 · `valid_from` KEEPS THE EVENT TIME and `recorded_at` carries the
            # knowledge time. The two are genuinely different on this table and both have
            # readers: reason/moments reads valid_from as "when did we last relate to this
            # node", and the as-of read needs "when did we learn of this relationship". Taking
            # the first meaning away to give the second would have moved every moments answer
            # with nothing failing.
            "to_node_id, authority_rank, confidence, valid_from, last_seen_at, "
            "created_by_event_id, recorded_at) "
            "values (:ev, :eid, :o, :t, :f, :tn, :ar, :c, coalesce(:vf, now()), "
            "coalesce(:vf, now()), :e, now())"),
            {"ev": edge_version_id, "eid": new_id("edge"), "o": org_id, "t": edge_type,
             "f": from_node_id, "tn": to_node_id, "ar": authority_rank, "c": confidence,
             "vf": occurred_at, "e": event_id})
        self._write_ref(conn, org_id=org_id, edge_version_id=edge_version_id, event_id=event_id,
                        source=source, evidence=evidence)
        return edge_version_id

    def _write_ref(self, conn, *, org_id, event_id, evidence, source=None,
                   fact_version_id=None, observation_id=None, edge_version_id=None) -> None:
        # `source_object_id` — the PROVIDER's id for the message this receipt came from.
        #
        # The column existed and nothing ever wrote it, so all 3,132 rows carried NULL and there
        # was no path from a card back to the Gmail message that caused it. `evidence` held only
        # derivation labels like {"derived": "email to/cc"}, which say what the engine concluded
        # and not what it read.
        #
        # Filled by subquery rather than threaded through every writer: the value is already in
        # `source_events`, keyed by the `event_id` this ref carries, so a correlated select gets
        # it inside the same statement — no extra round trip, and no signature change across
        # three public write methods and their dozens of call sites, each of which would be a
        # chance to forget one and leave a silent NULL behind.
        conn.execute(text(
            "insert into graph_source_refs (source_ref_id, org_id, fact_version_id, "
            "edge_version_id, observation_id, event_id, source, evidence, extractor_version, "
            "source_object_id) "
            "values (:id, :o, :fv, :ev2, :obs, :e, :src, :ex, :xv, "
            "  (select se.source_object_id from source_events se "
            "   where se.event_id = :e and se.org_id = :o))").bindparams(bindparam("ex", type_=JSON)),
            {"id": new_id("ref"), "o": org_id, "fv": fact_version_id, "ev2": edge_version_id,
             "obs": observation_id, "e": event_id, "src": source,
             "ex": json.loads(json.dumps(evidence, default=str)), "xv": "b3-haiku-1"})

    #: How long the change outbox answers for. Matched to `analytic/history.RETENTION_MONTHS`
    #: rather than chosen independently: `graph_version_at` exists so an audit can resolve the
    #: version a stamped artifact was produced under, and a horizon shorter than the layer's
    #: longest-lived store would leave a retained metric point pointing at a version nothing can
    #: name. Imported lazily in `prune_change_outbox` — `analytic` imports this module.
    OUTBOX_RETENTION_MONTHS = 24

    def prune_change_outbox(self, org_id: str, *, eval_time: datetime,
                            batch_limit: int = 20_000) -> int:
        """Delete outbox rows past the horizon. Returns rows removed.

        ON THE DRAIN, for the two reasons `analytic/history.prune_history_for_drain` gives and
        which apply unchanged: the broker is a quota-limited instance and this layer prefers
        in-process work on a path that already runs, and the drain is the only thing that knows an
        org is active — an org that is not draining is not growing this table either.

        SAFE BECAUSE THE READER SAYS SO. `graph_version_at` already documents that it returns None
        for "an org whose outbox rows have aged out", and a null there is honest where a 0 would
        read as a real version. Nothing else reads this table.

        BOUNDED, because the first prune on a tenant that has been draining for a year is the
        expensive one and it runs inside the sweep's own transaction budget. The drain repeats, so
        a bounded batch drains the backlog over a few sweeps; an unbounded DELETE on a long
        untouched table would be an unbounded transaction on the path that ingests mail.

        IDEMPOTENT WITHIN A MONTH: `months_before` anchors on the month START, so two prunes in
        the same month compute the same cutoff and the second deletes nothing.
        """
        from genios_engine.context.analytic.history import months_before

        cutoff = months_before(eval_time, self.OUTBOX_RETENTION_MONTHS)
        with self._engine.begin() as conn:
            return int(conn.execute(text(
                "delete from graph_change_outbox where change_id in ("
                "  select change_id from graph_change_outbox "
                "  where org_id = :o and created_at < :cut limit :lim)"),
                {"o": org_id, "cut": cutoff, "lim": batch_limit}).rowcount or 0)

    def write_change(self, conn, *, org_id: str, graph_version: int,
                     cause_event_id: str, payload: dict) -> None:
        conn.execute(text(
            "insert into graph_change_outbox (change_id, org_id, graph_version, cause_event_id, "
            "payload) values (:id, :o, :v, :e, cast(:p as jsonb))"),
            {"id": new_id("chg"), "o": org_id, "v": graph_version, "e": cause_event_id,
             "p": json.dumps(payload, default=str)})

    # ── extraction replay cache + cost ─────────────────────────────────────────
    def cache_get(self, processing_key: str, *, org_id: str) -> dict | None:
        # org_id is REQUIRED (no default): the key is already org-scoped, but this guarantees a
        # row can only ever be read back by the tenant that wrote it. It was optional once —
        # which meant every future caller (backfills, bulk loaders) was one omitted kwarg away
        # from a silent cross-tenant cache read that no test would catch.
        if not org_id:
            raise ValueError("cache_get requires a non-empty org_id (tenant isolation)")
        with self._engine.connect() as c:
            r = c.execute(text(
                "select output from l1_extraction_results "
                "where processing_key=:k and org_id=:o"),
                {"k": processing_key, "o": org_id}).first()
        if not r:
            return None
        return r.output if isinstance(r.output, dict) else json.loads(r.output)

    def cache_set(self, *, processing_key, org_id, event_id, output, input_tokens,
                  output_tokens, model) -> None:
        with self._engine.begin() as c:
            c.execute(text(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
                "input_tokens, output_tokens, model_snapshot) "
                "values (:k, :o, :e, cast(:out as jsonb), :it, :ot, :m) "
                "on conflict (processing_key) do nothing"),
                {"k": processing_key, "o": org_id, "e": event_id,
                 "out": json.dumps(output, default=str), "it": input_tokens,
                 "ot": output_tokens, "m": model})

    def record_cost(self, *, org_id, model, purpose, input_tokens, output_tokens,
                    success=True, error=None, event_id=None,
                    subject_ref=None, client_context_id=None, seat_id=None,
                    cache_read_tokens=0, cache_write_tokens=0) -> None:
        # Defaults so BOTH callers work: L2 passes all kwargs; L5 render passes only the core set.
        # (Was a bug: L5's call omitted success/error/event_id → TypeError swallowed → l5_render
        #  spend NEVER recorded, reproducing the old 'V2 LLM cost not tracked' gap.)
        #
        # `subject_ref` ("card:<id>" / "signal:<id>" / "event:<id>") is what makes "cost per
        # useful accepted decision" computable at all: org+purpose was enough for a monthly bill
        # and useless for margin — no way to say WHICH decision a call was spent on. Optional,
        # because background work is genuinely unattributed and forcing a value would invent one.
        #
        # `seat_id` (0175) is the same argument one level down: org+purpose cannot say which
        # PERSON a month's spend belongs to, and per-seat lanes — screen capture, a seat's own
        # mailbox, an authenticated query — all know the answer at the call site. NULL keeps its
        # honest meaning: background work that serves no single seat.
        #
        # `cache_*_tokens` are RECORDED, NEVER PRICED. `input_tokens` is already the
        # cost-equivalent count (uncached + 1.25x/2x writes + 0.1x reads); adding these to it
        # would double-charge the cache. They exist so "is the prompt cache working" is a ledger
        # query rather than a log-grep.
        with self._engine.begin() as c:
            c.execute(text(
                "insert into llm_costs (org_id, model, purpose, input_tokens, output_tokens, "
                "success, error, event_id, subject_ref, client_context_id, seat_id, "
                "cache_read_tokens, cache_write_tokens) "
                "values (:o, :m, :p, :it, :ot, :s, :e, :ev, :sr, :cc, :seat, :crt, :cwt)"),
                {"o": org_id, "m": model, "p": purpose, "it": input_tokens, "ot": output_tokens,
                 "s": success, "e": (error or None), "ev": event_id,
                 "sr": subject_ref, "cc": client_context_id,
                 "seat": (seat_id or None),
                 "crt": int(cache_read_tokens or 0), "cwt": int(cache_write_tokens or 0)})
        # Every LLM call in the engine lands here, so this is the one place that can report spend
        # to PostHog without a per-call-site instrumentation that later drifts. Priced with the same
        # function the admin console uses, so both surfaces quote one dollar figure.
        try:
            from genios_engine.platform import analytics, metrics
            analytics.capture(org_id, "llm_call", {
                "model": model, "purpose": purpose,
                "input_tokens": int(input_tokens or 0), "output_tokens": int(output_tokens or 0),
                "tokens": int(input_tokens or 0) + int(output_tokens or 0),
                "cost_usd": metrics.cost_usd(model, input_tokens or 0, output_tokens or 0),
                "success": bool(success),
                "seat_id": (seat_id or None),
                "cache_read_tokens": int(cache_read_tokens or 0),
                "cache_write_tokens": int(cache_write_tokens or 0),
            })
        except Exception:      # noqa: BLE001 — accounting is recorded; telemetry is best-effort
            pass

    # ── L2.2.7-U1 · point-in-time reads ───────────────────────────────────────
    #
    # Three methods and one predicate. `read_graph` is doc 02's signature; `live_graph` is the
    # same read with the open-row predicate, and it exists so the equivalence property
    # ("read_graph(as_of=now) matches the live graph exactly") is a comparison of two code paths
    # rather than a test transcribing SQL that would then drift from the reader it checks.

    def _rows(self, conn, sql: str, params: dict):
        from sqlalchemy import text
        return conn.execute(text(sql), params).fetchall()

    def _view(self, conn, org_id: str, *, as_of: datetime | None) -> GraphView:
        """One connection, three selects, one immutable view. Shared by both reads so the two
        can only ever differ in the window predicate they are given."""
        where = _WINDOW_OPEN if as_of is None else _WINDOW_AT
        params: dict[str, Any] = {"o": org_id}
        if as_of is not None:
            params["t"] = as_of
        nodes = self._rows(conn, f"select {_NODE_COLS} from graph_nodes where org_id=:o "
                                 f"and {where} order by node_id, version", params)
        facts = self._rows(conn, f"select {_FACT_COLS} from graph_facts where org_id=:o "
                                 f"and {where} order by subject_node_id, field, "
                                 f"fact_version_id", params)
        edges = self._rows(conn, f"select {_EDGE_COLS} from graph_edges where org_id=:o "
                                 f"and {where} order by edge_version_id", params)
        return GraphView(
            org_id=org_id, as_of=as_of,
            graph_version=self.graph_version_at(org_id, as_of=as_of, conn=conn),
            nodes=tuple(NodeAt(node_id=r.node_id, version=int(r.version), node_type=r.node_type,
                               canonical_key=r.canonical_key, display_name=r.display_name,
                               identity_strength=r.identity_strength, valid_from=r.valid_from,
                               valid_to=r.valid_to) for r in nodes),
            facts=tuple(FactAt(fact_version_id=r.fact_version_id,
                               subject_node_id=r.subject_node_id, field=r.field, value=r.value,
                               value_type=r.value_type, status=r.status,
                               authority_rank=int(r.authority_rank), occurred_at=r.occurred_at,
                               valid_from=r.valid_from, valid_to=r.valid_to) for r in facts),
            edges=tuple(EdgeAt(edge_version_id=r.edge_version_id, edge_type=r.edge_type,
                               from_node_id=r.from_node_id, to_node_id=r.to_node_id,
                               confidence_bp=_confidence_bp(r.confidence),
                               interaction_count=int(r.interaction_count or 0),
                               valid_from=r.valid_from, valid_to=r.valid_to) for r in edges))

    def read_graph(self, org_id: str, *, as_of: datetime, conn=None) -> GraphView:
        """The graph as it stood at `as_of` — doc 02's `read_graph(org, as_of)`.

        `as_of` is a PARAMETER and this method reads no clock, so replaying a March decision in
        September returns March's graph rather than March-filtered-by-today. An instant before
        the org's first write returns an EMPTY view, not an error.

        `conn` lets a caller read inside a transaction it already owns — a replay that also
        writes an audit row must see one consistent snapshot, and a second connection would not
        see the caller's uncommitted state.
        """
        if not isinstance(as_of, datetime):
            raise TypeError(
                f"read_graph requires a datetime as_of, got {type(as_of).__name__} — the instant "
                "is a parameter, never a clock, and a string parsed here would make "
                "'2026-03-01' silently mean midnight UTC in whatever the caller assumed")
        at = _ts(as_of)
        if conn is not None:
            return self._view(conn, org_id, as_of=at)
        with self._engine.connect() as c:
            return self._view(c, org_id, as_of=at)

    def live_graph(self, org_id: str, *, conn=None) -> GraphView:
        """The graph as it stands now: every row whose window is still open (`valid_to is null`),
        which is the predicate every existing reader in this engine already uses."""
        if conn is not None:
            return self._view(conn, org_id, as_of=None)
        with self._engine.connect() as c:
            return self._view(c, org_id, as_of=None)

    def graph_version_at(self, org_id: str, *, as_of: datetime | None, conn=None) -> int | None:
        """The `graph_version` the org had reached at `as_of` — the number an audit answer has
        to quote, since read models and reasoning runs are stamped with it.

        Read from `graph_change_outbox`, which records a version WITH the instant it was reached;
        `graph_versions` holds only the current counter and cannot answer for the past. `None`
        when nothing was recorded before that instant (an org with no committed change yet, or
        one whose outbox rows have aged out) — a null is honest here, and a 0 would read as a
        real version.
        """
        from sqlalchemy import text
        sql = ("select max(graph_version) as v from graph_change_outbox where org_id=:o"
               + ("" if as_of is None else " and created_at <= :t"))
        params: dict[str, Any] = {"o": org_id}
        if as_of is not None:
            params["t"] = as_of
        if conn is not None:
            value = conn.execute(text(sql), params).scalar()
        else:
            with self._engine.connect() as c:
                value = c.execute(text(sql), params).scalar()
        return None if value is None else int(value)

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
_WINDOW_AT = "valid_from <= :t and (valid_to is null or valid_to > :t)"
_WINDOW_OPEN = "valid_to is null"

_NODE_COLS = ("node_id, version, node_type, canonical_key, display_name, identity_strength, "
              "valid_from, valid_to")
_FACT_COLS = ("fact_version_id, subject_node_id, field, value, value_type, status, "
              "authority_rank, occurred_at, valid_from, valid_to")
_EDGE_COLS = ("edge_version_id, edge_type, from_node_id, to_node_id, confidence, "
              "interaction_count, valid_from, valid_to")


class GraphStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    @property
    def engine(self):
        return self._engine

    # ── versioning ────────────────────────────────────────────────────────────
    def bump_version(self, conn, org_id: str) -> int:
        conn.execute(text(
            "insert into graph_versions (org_id, graph_version) values (:o, 1) "
            "on conflict (org_id) do update set graph_version = graph_versions.graph_version + 1, "
            "updated_at = now()"), {"o": org_id})
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
            "display_name, identity_strength, created_by_event_id) "
            "values (:id, 1, :o, :nt, :k, :dn, :st, :ev)"),
            {"id": node_id, "o": org_id, "nt": node_type, "k": canonical_key,
             "dn": display_name, "st": "strong" if canonical_key else "weak", "ev": event_id})
        # Claim the keys this node can be found by. A key already held by ANOTHER node
        # raises a merge proposal and changes nothing — the first claimant keeps it, so
        # lookups stay stable while a human decides.
        register_node_identity(conn, org_id=org_id, node_id=node_id, node_type=node_type,
                               canonical_key=canonical_key, display_name=display_name,
                               event_id=event_id)
        return node_id

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
        held = conn.execute(text(
            "select fact_version_id, value, authority_rank, occurred_at from graph_facts "
            "where org_id=:o and subject_node_id=:s and field=:f "
            "and valid_to is null and status='active' "
            "limit 1").columns(value=JSON), {"o": org_id, "s": subject_node_id, "f": field}).first()
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
            return None
        if action == "discrepancy":
            # held keeps its OWN value (the system-of-record), challenger carries the new one.
            # (Was a bug: both sides recorded the challenger value → 'paid vs paid', real
            #  conflict lost — e.g. Stripe 'paid' R3 vs email 'unpaid' R2.)
            self.write_discrepancy(conn, org_id=org_id, subject_node_id=subject_node_id,
                                   field=field,
                                   held={"value": json.loads(held_val), "rank": held.authority_rank},
                                   challenger={"value": value, "rank": authority_rank,
                                               "source": source, "event_id": event_id})
            return None
        if action == "supersede":
            conn.execute(text("update graph_facts set valid_to=now(), status='superseded' "
                              "where fact_version_id=:fv"), {"fv": held.fact_version_id})
            # The field has been authoritatively re-decided → any open discrepancy recorded
            # against the OLD value is settled. This is what lets `consistency` recover
            # instead of falling forever.
            self.resolve_discrepancies(conn, org_id=org_id, subject_node_id=subject_node_id,
                                       field=field)

        status = "historical" if action == "historical" else "active"
        fv = new_id("factv")
        conn.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "value, value_type, status, authority_rank, confidence, relevance, occurred_at, "
            "created_by_event_id, derivation_type, trace_id, schema_version, source_authority, "
            "provenance_refs"
            + (", valid_to" if status == "historical" else "") + ") "
            "values (:fv, :fid, :o, :s, :f, :val, :vt, :st, :ar, :c, :rel, :oc, :ev, "
            "'source_event', :ev, 'graph-fact.v2', :authority, :provenance"
            + (", now()" if status == "historical" else "") + ")").bindparams(
                bindparam("val", type_=JSON), bindparam("provenance", type_=JSON)),
            {"fv": fv, "fid": new_id("fact"), "o": org_id, "s": subject_node_id, "f": field,
             "val": json.loads(new_val), "vt": value_type, "st": status, "ar": authority_rank,
             "c": confidence, "rel": relevance, "oc": occurred_at, "ev": event_id,
             "authority": f"R{authority_rank}",
             "provenance": [f"event:{event_id}"]})
        self._write_ref(conn, org_id=org_id, fact_version_id=fv, event_id=event_id,
                        source=source, evidence=evidence)
        return fv

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
        return conn.execute(text(
            "update discrepancies set status='resolved' where org_id=:o "
            "and subject_node_id=:s and field=:f and status='open'"),
            {"o": org_id, "s": subject_node_id, "f": field}).rowcount or 0

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
        many sweeps ran, not how often two parties interacted."""
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
            "to_node_id, authority_rank, confidence, valid_from, last_seen_at, created_by_event_id) "
            "values (:ev, :eid, :o, :t, :f, :tn, :ar, :c, coalesce(:vf, now()), "
            "coalesce(:vf, now()), :e)"),
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
                    subject_ref=None, client_context_id=None) -> None:
        # Defaults so BOTH callers work: L2 passes all kwargs; L5 render passes only the core set.
        # (Was a bug: L5's call omitted success/error/event_id → TypeError swallowed → l5_render
        #  spend NEVER recorded, reproducing the old 'V2 LLM cost not tracked' gap.)
        #
        # `subject_ref` ("card:<id>" / "signal:<id>" / "event:<id>") is what makes "cost per
        # useful accepted decision" computable at all: org+purpose was enough for a monthly bill
        # and useless for margin — no way to say WHICH decision a call was spent on. Optional,
        # because background work is genuinely unattributed and forcing a value would invent one.
        with self._engine.begin() as c:
            c.execute(text(
                "insert into llm_costs (org_id, model, purpose, input_tokens, output_tokens, "
                "success, error, event_id, subject_ref, client_context_id) "
                "values (:o, :m, :p, :it, :ot, :s, :e, :ev, :sr, :cc)"),
                {"o": org_id, "m": model, "p": purpose, "it": input_tokens, "ot": output_tokens,
                 "s": success, "e": (error or None), "ev": event_id,
                 "sr": subject_ref, "cc": client_context_id})
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

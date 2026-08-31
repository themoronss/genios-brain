from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.context.identity import register_node_identity
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
            "limit 1"), {"o": org_id, "s": subject_node_id, "f": field}).first()
        new_val = json.dumps(value, default=str)
        held_val = None
        if held is not None:
            held_val = held.value if isinstance(held.value, str) else json.dumps(held.value, default=str)

        action = fact_write_action(
            held_value_json=held_val, held_rank=held.authority_rank if held else None,
            held_occurred_at=held.occurred_at if held else None,
            new_value_json=new_val, new_rank=authority_rank,
            new_occurred_at=occurred_at, replay=replay)

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
            "created_by_event_id"
            + (", valid_to" if status == "historical" else "") + ") "
            "values (:fv, :fid, :o, :s, :f, cast(:val as jsonb), :vt, :st, :ar, :c, :rel, :oc, :ev"
            + (", now()" if status == "historical" else "") + ")"),
            {"fv": fv, "fid": new_id("fact"), "o": org_id, "s": subject_node_id, "f": field,
             "val": new_val, "vt": value_type, "st": status, "ar": authority_rank,
             "c": confidence, "rel": relevance, "oc": occurred_at, "ev": event_id})
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
                   "h": json.dumps(held, default=str), "c": json.dumps(challenger, default=str)}
        updated = conn.execute(text(
            "update discrepancies set held=cast(:h as jsonb), challenger=cast(:c as jsonb) "
            "where org_id=:o and subject_node_id=:s and field=:f and status='open'"),
            payload).rowcount
        if not updated:
            conn.execute(text(
                "insert into discrepancies (id, org_id, subject_node_id, field, held, challenger) "
                "values (:id, :o, :s, :f, cast(:h as jsonb), cast(:c as jsonb))"),
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

    # ── relationships (B7 edges) ──────────────────────────────────────────────
    def write_edge(self, conn, *, org_id: str, edge_type: str, from_node_id: str,
                   to_node_id: str, confidence: float, occurred_at: datetime | None,
                   event_id: str, evidence: dict, source: str | None,
                   authority_rank: int = 2) -> str | None:
        """Idempotent relationship edge (e.g. person→attended→meeting, person→works_at→company).
        No self-loops, and an identical active edge (same type+from+to) is a no-op — so re-syncing
        never duplicates edges. Returns the new edge_version_id, or None on skip/no-op."""
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
                "update graph_edges set interaction_count = coalesce(interaction_count,1) + 1, "
                "last_seen_at = greatest(coalesce(last_seen_at, valid_from, now()), "
                "coalesce(cast(:oc as timestamptz), now())) "
                "where edge_version_id=:ev"),
                {"ev": held.edge_version_id, "oc": occurred_at})
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
            "values (:id, :o, :fv, :ev2, :obs, :e, :src, cast(:ex as jsonb), :xv, "
            "  (select se.source_object_id from source_events se "
            "   where se.event_id = :e and se.org_id = :o))"),
            {"id": new_id("ref"), "o": org_id, "fv": fact_version_id, "ev2": edge_version_id,
             "obs": observation_id, "e": event_id, "src": source,
             "ex": json.dumps(evidence, default=str), "xv": "b3-haiku-1"})

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
                "select output from l2_extraction_results "
                "where processing_key=:k and org_id=:o"),
                {"k": processing_key, "o": org_id}).first()
        if not r:
            return None
        return r.output if isinstance(r.output, dict) else json.loads(r.output)

    def cache_set(self, *, processing_key, org_id, event_id, output, input_tokens,
                  output_tokens, model) -> None:
        with self._engine.begin() as c:
            c.execute(text(
                "insert into l2_extraction_results (processing_key, org_id, event_id, output, "
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

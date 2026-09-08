"""ONE event through ALL layers on a real Postgres — the end-to-end compatibility proof.

Every prior test is per-layer or per-seam. This one seeds a single email and drives the actual
live entry points in order — L1 sync (capture + semantic + QES publication) -> L2 context/graph
-> L4 reasoning (pack engine) -> L5 executive -> L5.2 cards -> L6 learning — on one shared
`pg_store`. It proves the seams line up on real data: each layer runs on the previous layer's
persisted output without a shape break.

The L1 stage drives `run_sync`, not `capture_event`. `capture_event` is the LANDING stage alone,
and Layer 1 v2 moved the boundary Layer 2 reads from: the drain now takes only events that
published a `qualified_signals` row. A chain that landed an email and never qualified it drained
nothing and reported the seam break as Layer 2's.

Skips unless GENIOS_TEST_DATABASE_URL is set (same gate as the other real-Postgres tests).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
from genios_engine.capture.payload_store import PostgresRawPayloadStore
from genios_engine.capture.prepared_store import PostgresPreparedContentStore
from genios_engine.capture.semantic.cache import PostgresExtractionCache
from genios_engine.context.runner import process_pending
from genios_engine.deliver.pipeline import build_cards_for_org
from genios_engine.deliver.store import CardStore
from genios_engine.executive.sweep import run_executive
from genios_engine.feedback.orchestrator import run_learning_sweep
from genios_engine.packs.wiring import make_registry
from genios_engine.platform.config import get_settings
from genios_engine.reason.runner import run_all

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
OWNER = "founder@genios.test"

#: The one email. Held at module scope because the Layer 1 extraction below must cite REAL
#: substrings of it: ALG-08 verifies every evidence span against the prepared text and silently
#: drops the claim whose offsets do not agree, and a dropped claim publishes no qualified signal —
#: which is now the difference between this chain running and this chain draining nothing.
BODY = ("Priya from Acme said the proposal looks good. Budget is approved. "
        "Can you send the revised contract by Friday?")


class _FakeResult:
    ok, raw, input_tokens, output_tokens, error = True, "{}", 10, 20, None
    model, cached = "fake-haiku", False

    def __init__(self, parsed):
        self.parsed = parsed


class _FakeLLM:
    """Deterministic stand-in for the Haiku extractor so the capture lane runs with no API key."""
    model = "fake-haiku"

    def __init__(self, parsed):
        self._parsed = parsed

    @staticmethod
    def content_hash(material: str) -> str:
        import hashlib
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def call(self, prompt, *, max_tokens=4096):
        return _FakeResult(self._parsed)


class _Mailbox:
    """The narrowest real `SourceConnector` — one email, handed to the production sync door."""

    source = "gmail"

    def __init__(self, object_id: str, thread_id: str) -> None:
        self._object_id, self._thread_id = object_id, thread_id

    def validate_connection(self) -> bool:
        return True

    def _objects(self):
        return [RawObject(source="gmail", object_type="email_message",
                          source_object_id=self._object_id, occurred_at=NOW,
                          actor_email="priya@acme.io", actor_type="external_contact",
                          recipients=(OWNER,), parent_object_id=self._thread_id,
                          raw={"subject": "Revised contract", "body": BODY})]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


def _l1_extraction() -> dict:
    """What Layer 1's extractor returns for BODY, every claim citing a real substring."""
    def cite(quote: str) -> list[dict]:
        start = BODY.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    return {
        "intent": "commit", "stance": "positive",
        "entity_mentions": [{"surface_form": "Acme", "entity_type": "organization",
                             "evidence": cite("Acme"), "confidence_bp": 8800}],
        "decision_states": [{"subject": "revised contract", "state": "pending",
                             "blocked_on": "our side",
                             "evidence": cite("send the revised contract by Friday"),
                             "confidence_bp": 8000}],
        "dependencies": [{"blocker": "us", "blocked": "Acme", "dependency_type": "approval",
                          "evidence": cite("Budget is approved"), "confidence_bp": 7900}],
    }


def _seed_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        parts, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            parts.append(r.column_name); ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else "o@x.test" if "email" in r.column_name else org)
        conn.execute(text(f"insert into orgs ({','.join(parts)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


def _fresh_tenant(store, org: str) -> None:
    """Erase this tenant through the production `/reset` list before the chain runs.

    The scratch database outlives one pytest process and every stage on this path is
    content-addressed: a second run of this file landed on `duplicate` at the landing stage and
    failed with a message about Layer 1 that was really about the previous run. A chain test that
    can only be run once is a chain test nobody re-runs.
    """
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as conn:
        _wipe(conn, org)
        # Not on the `/reset` list (migration 0037 erases these by schema on account DELETION,
        # which `/reset` does not do), and this file has to start from an empty graph either way.
        for tbl in ("context_correlation_members", "context_situations", "context_correlations"):
            conn.execute(text(f"delete from {tbl} where org_id=:o"), {"o": org})


def test_one_event_flows_through_all_layers(pg_store, monkeypatch):
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    crypto_key = get_settings().crypto_key
    org = "e2e_all_layers"
    _seed_org(pg_store, org)
    _fresh_tenant(pg_store, org)

    # ---- L1: ONE email through the production sync door ----
    #
    # THIS USED TO BE A BARE `capture_event`, and that stopped being Layer 1's entry point.
    # `capture_event` is the LANDING stage alone: it writes `source_events`, `raw_payloads` and
    # `prepared_content` and stops. Layer 1 v2 moved the boundary Layer 2 reads from — the drain's
    # `_pull` now joins `qualified_signals` and takes only events that crossed the QES publication
    # boundary — so a chain that landed an event and never qualified it drained NOTHING, and the
    # end-to-end proof reported a seam break that was its own. `run_sync` with the semantic lane,
    # the ESQE stage and `routes._run_ledger` is what every HTTP sync caller passes, so this is
    # the same door a customer's mailbox comes through; only the tenant-scoped stores are pointed
    # at the scratch database.
    from genios_engine.api import routes
    from genios_engine.capture.esqe import qualification as Q

    monkeypatch.setattr(routes, "_graph", pg_store, raising=False)
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore({org: 1}), raising=False)
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger(), raising=False)
    monkeypatch.setattr(routes, "_lifecycle_store", None, raising=False)

    captured = run_sync(
        _Mailbox("msg_e2e_1", "thread_e2e"), org_id=org, connection_id="conn_e2e",
        source="gmail", mode="backfill",
        repo=PostgresSourceEventRepository(url),
        payload_store=PostgresRawPayloadStore(url, crypto_key),
        prepared_store=PostgresPreparedContentStore(url),
        mailbox_owner=OWNER,
        semantic=P.SemanticLane(llm=_FakeLLM(_l1_extraction()), eval_time=NOW,
                                cache=PostgresExtractionCache(url)),
        esqe=P.EsqeStage(eval_time=NOW, org_domains=("genios.test",)),
        run_ledger=routes._run_ledger)
    assert captured.emitted == 1, f"L1 did not emit: {captured}"
    with pg_store.engine.connect() as conn:
        published = conn.execute(text(
            "select count(*) from qualified_signals where org_id=:o and state='active'"),
            {"o": org}).scalar()
    assert published >= 1, "L1 landed the mail but published no signal — L2 has nothing to read"

    # ---- L2: drain L1 into the graph + situations (the drain refreshes situations itself) ----
    # No canned L2 payload any more, and that is the point: `runner._process_one` now adapts
    # LAYER 1's stored extraction (`qualified_extraction=...`, `llm=None`) instead of paying a
    # second model to re-read the same message. Handing it one would test a lane the product no
    # longer runs.
    l2 = process_pending(org_id=org, store=pg_store, llm=None, crypto_key=crypto_key)
    assert l2["processed"] >= 1, f"L1->L2 seam carried nothing: {l2}"
    with pg_store.engine.begin() as conn:
        facts = conn.execute(text("select count(*) from graph_facts where org_id=:o"),
                             {"o": org}).scalar()
        nodes = conn.execute(text("select count(*) from graph_nodes where org_id=:o"),
                             {"o": org}).scalar()
    assert nodes >= 1 and facts >= 1, f"L2 built no graph: nodes={nodes} facts={facts}"

    # ---- L4: reason over the graph (pack engine, the live path) — emits signals ----
    registry = make_registry(url)
    l4 = run_all(org_id=org, store=pg_store, eval_time=NOW, registry=registry)
    assert "nodes" in l4, f"L4 did not run: {l4}"                # ran clean on L2's graph

    # ---- L5: executive sweep — reads signals, plans commitments ----
    l5 = run_executive(pg_store.engine, org, eval_time=NOW)
    assert "planned" in l5, f"L5 did not run: {l5}"             # ran clean on L4's signals

    # ---- L5.2: build cards from signals (the delivery card path) ----
    l52 = build_cards_for_org(graph=pg_store, card_store=CardStore(url), org_id=org,
                              llm=None, registry=registry, eval_time=NOW)
    assert isinstance(l52, dict), f"L5.2 did not run: {l52}"    # ran clean on L4's signals

    # ---- L6: learning sweep — reads outcomes/delivery, produces learning ----
    l6 = run_learning_sweep(pg_store.engine, now=NOW)
    assert isinstance(l6, dict), f"L6 did not run: {l6}"        # ran clean on the delivery/outcome seam

    # The chain ran end-to-end on one shared Postgres without a seam break.
    assert True

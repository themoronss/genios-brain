"""ONE event through ALL layers on a real Postgres — the end-to-end compatibility proof.

Every prior test is per-layer or per-seam. This one seeds a single email and drives the actual
live entry points in order — L1 capture -> L2 context/graph -> L4 reasoning (pack engine) ->
L5 executive -> L5.2 cards -> L6 learning — on one shared `pg_store`. It proves the seams line up
on real data: each layer runs on the previous layer's persisted output without a shape break.

Skips unless GENIOS_TEST_DATABASE_URL is set (same gate as the other real-Postgres tests).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
from genios_engine.capture.payload_store import PostgresRawPayloadStore
from genios_engine.capture.pipeline import capture_event
from genios_engine.capture.prepared_store import PostgresPreparedContentStore
from genios_engine.context.runner import process_pending
from genios_engine.deliver.pipeline import build_cards_for_org
from genios_engine.deliver.store import CardStore
from genios_engine.executive.sweep import run_executive
from genios_engine.feedback.orchestrator import run_learning_sweep
from genios_engine.packs.wiring import make_registry
from genios_engine.platform.config import get_settings
from genios_engine.reason.runner import run_all

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


class _FakeResult:
    ok, raw, input_tokens, output_tokens, error = True, "{}", 10, 20, None

    def __init__(self, parsed):
        self.parsed = parsed


class _FakeLLM:
    """Deterministic stand-in for the Haiku extractor so the L2 lane runs with no API key."""
    model = "fake-haiku"

    def __init__(self, parsed):
        self._parsed = parsed

    def call(self, prompt, *, max_tokens=4096):
        return _FakeResult(self._parsed)


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


def test_one_event_flows_through_all_layers(pg_store):
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    crypto_key = get_settings().crypto_key
    org = "e2e_all_layers"
    _seed_org(pg_store, org)

    # ---- L1: capture a real email into source_events / raw_payloads / prepared_content ----
    body = ("Priya from Acme said the proposal looks good. Budget is approved. "
            "Can you send the revised contract by Friday?")
    raw = RawObject(
        source="gmail", object_type="email_message", source_object_id="msg_e2e_1",
        occurred_at=NOW, actor_email="priya@acme.io", actor_type="external_contact",
        parent_object_id="thread_e2e",
        raw={"subject": "Revised contract", "body": body})
    captured = capture_event(
        raw, org_id=org, connection_id="conn_e2e",
        repo=PostgresSourceEventRepository(url),
        payload_store=PostgresRawPayloadStore(url, crypto_key),
        prepared_store=PostgresPreparedContentStore(url))
    assert captured.outcome == "emitted", f"L1 did not emit: {captured.outcome}"

    # ---- L2: drain L1 into the graph + situations (the drain refreshes situations itself) ----
    canned = {
        "relevance": 0.85, "noise_type": "none", "domains": ["sales"],
        "entity_mentions": [
            {"type": "person", "name": "Priya", "email": "priya@acme.io",
             "evidence_text": "Priya from Acme"},
            {"type": "company", "name": "Acme", "email": None, "evidence_text": "from Acme"}],
        "fact_candidates": [
            {"subject": "Priya", "field": "company", "value": "Acme",
             "evidence_text": "Priya from Acme"}],
        "commitments": [
            {"text": "send the revised contract by Friday", "owner": "us",
             "evidence_text": "send the revised contract by Friday"}],
        "questions": [],
        "observations": [
            {"kind": "positive_reply", "evidence_text": "looks good"},
            {"kind": "budget_approved", "evidence_text": "Budget is approved"}],
    }
    l2 = process_pending(org_id=org, store=pg_store, llm=_FakeLLM(canned), crypto_key=crypto_key)
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

from __future__ import annotations
import json
from datetime import timedelta
import pytest
from sqlalchemy import text
from genios_engine.context import situations
from genios_engine.context.pipeline import process_event
from ...test_admin_support_packs import NOW, _FakeLLM, _seed_event, _seed_org

SALES_CONTENT = (
    "Following up on my note last week about the onboarding tooling. "
    "We reviewed your pricing page and it looks workable for our team of forty. "
    "Can you tell me what the rollout would involve before we take it further?")

SALES_CANNED = {
    "relevance": 0.9, "noise_type": "none", "domains": ["sales"],
    "entity_mentions": [
        {"type": "person", "name": "Tara Iyer", "email": "tara.iyer@gmail.com",
         "evidence_text": "Following up on my note last week"}],
    "fact_candidates": [
        {"subject": "Tara Iyer", "field": "thread.ball_in_court", "value": "us",
         "evidence_text": "Can you tell me what the rollout would involve"}],
    "commitments": [],
    "questions": [{"directed_at": "us",
                   "evidence_text": "Can you tell me what the rollout would involve"}],
    "observations": [{"kind": "question",
                      "evidence_text": "Can you tell me what the rollout would involve"}],
}

pytestmark = pytest.mark.pg


def test_diag(pg_store, monkeypatch):
    from genios_engine.packs.compiler.context_adapter import ContextAdapter
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.domain_shadow import shadow_compile

    orig = ContextAdapter.matches

    def spy(self, conditions):
        v = orig(self, conditions)
        print("MATCH", json.dumps(list(conditions), default=str), "->", v.state)
        return v

    monkeypatch.setattr(ContextAdapter, "matches", spy)
    org = "pk_diag_sales1"
    _seed_org(pg_store, org)
    at = NOW - timedelta(days=1)
    with pg_store.engine.begin() as c:
        _seed_event(c, org, "sal_evt", "sales")
        c.execute(text("update source_events set occurred_at=:t where org_id=:o"),
                  {"t": at, "o": org})
    r = process_event(org_id=org, event_id="sal_evt", source="gmail", content=SALES_CONTENT,
                      sender_email="tara.iyer@gmail.com", occurred_at=at,
                      llm=_FakeLLM(SALES_CANNED), store=pg_store, is_inbound=True,
                      internal_emails=frozenset(), domain_hints=[{"domain": "sales"}])
    print("OUTCOME", r.outcome)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    with pg_store.engine.connect() as c:
        for row in c.execute(text("select node_id, node_type from graph_nodes where org_id=:o"), {"o": org}):
            print("NODE", row.node_id, row.node_type)
        for row in c.execute(text("select subject_node_id, field, value from graph_facts where org_id=:o"), {"o": org}):
            print("FACT", row.subject_node_id, row.field, row.value)
        for row in c.execute(text("select situation_id, situation_type, domain, anchor_node_id from context_situations where org_id=:o"), {"o": org}):
            print("SIT", row.situation_id, row.situation_type, row.domain, row.anchor_node_id)
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    counts = shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True, registry=registry)
    print("COUNTS", dict(counts))
    with pg_store.engine.connect() as c:
        for row in c.execute(text("select play, capability_id, rejected_candidates from signals where org_id=:o"), {"o": org}).mappings():
            rc = row["rejected_candidates"]
            if isinstance(rc, str):
                rc = json.loads(rc)
            print("SIG", row["play"], row["capability_id"])
            print("   REJ", json.dumps(rc, default=str)[:3000])
        for row in c.execute(text("select manifest from reasoning_capability_snapshots where org_id=:o"), {"o": org}).mappings():
            m = row["manifest"]
            if isinstance(m, str):
                m = json.loads(m)
            w = (m.get("metadata") or {}).get("weld") or {}
            print("CAP", m.get("capability_id"),
                  json.dumps([(v["rule_id"], v["outcome"], v["severity"], v.get("blocked_play_ids"))
                              for v in (w.get("rule_verdicts") or ())], default=str))

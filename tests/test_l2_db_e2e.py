"""Behavioural Layer 2 tests against a REAL Postgres (the pg_store fixture — skipped unless
GENIOS_TEST_DATABASE_URL is set). These exercise the SQL the hermetic suite can't reach: the doc's
biggest risk was 'written, tested, green, and does nothing' — code whose queries never ran. Here they
run for real, both lanes, plus the two live bug fixes end-to-end."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context import identity, situations
from genios_engine.context.health import compute_health
from genios_engine.context.pipeline import process_event
from genios_engine.context.structured import commit_structured

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _seed_org(store, org: str) -> None:
    """Insert the FK-parent org row, filling any NOT-NULL-no-default columns so the schema's
    referential integrity is satisfied (graph_nodes.org_id → orgs)."""
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


class _FakeResult:
    ok, raw, input_tokens, output_tokens, error = True, "{}", 10, 20, None

    def __init__(self, parsed):
        self.parsed = parsed


class _FakeLLM:
    """A deterministic stand-in for the Haiku extractor — lets the unstructured lane's grounding /
    resolution / graph-write / correlation SQL run without an API key."""
    model = "fake-haiku"

    def __init__(self, parsed):
        self._parsed = parsed

    def call(self, prompt, *, max_tokens=4096):
        return _FakeResult(self._parsed)


def test_structured_deal_reaches_a_situation(pg_store):
    org = "e2e_deal"
    _seed_org(pg_store, org)
    res = commit_structured(
        pg_store, org_id=org, event_id="d1", source="hubspot", source_object_id="deal_1",
        structured_fields={"deal.title": "Acme expansion", "deal.stage": "proposal"},
        node_type="deal", occurred_at=NOW, display_name="Acme expansion",
        domain_hints=[{"domain": "sales"}],
        relations=[{"node_type": "person", "canonical_key": "buyer@acme.io",
                    "edge_type": "involves", "direction": "in", "display_name": "Buyer"}])
    assert res.outcome == "committed_structured" and res.correlations >= 1
    assert situations.refresh_situations(pg_store, org, eval_time=NOW) >= 1
    with pg_store.engine.begin() as conn:
        assert len(situations.active_situations(conn, org_id=org)) >= 1


def test_subscription_now_reaches_a_situation(pg_store):
    # bug #2 end-to-end: before, subscription wasn't anchorable → reached NO situation
    org = "e2e_sub"
    _seed_org(pg_store, org)
    commit_structured(
        pg_store, org_id=org, event_id="s1", source="stripe", source_object_id="sub_1",
        structured_fields={"subscription.status": "active", "subscription.current_period_end": "2026-09-01"},
        node_type="subscription", occurred_at=NOW, display_name="Acme sub",
        domain_hints=[{"domain": "admin"}])
    assert situations.refresh_situations(pg_store, org, eval_time=NOW) >= 1
    with pg_store.engine.begin() as conn:
        assert len(situations.active_situations(conn, org_id=org)) >= 1


def test_person_name_resolves_to_the_anchored_node(pg_store):
    # bug #1 end-to-end: a bare-name mention reaches the person we already know by that name
    org = "e2e_person"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        nid = pg_store.find_or_create_node(conn, org_id=org, node_type="person",
                                           canonical_key="rohit@acme.io", display_name="Rohit Sharma",
                                           event_id=None)
        identity.observe_person_name(conn, org_id=org, node_id=nid, name="Rohit Sharma", event_id=None)
        assert identity.resolve_person_name(conn, org_id=org, name="Rohit Sharma") == nid
        assert identity.resolve_person_name(conn, org_id=org, name="Nobody Here") is None


def test_unstructured_lane_commits_facts_and_observations(pg_store):
    org = "e2e_unstr"
    _seed_org(pg_store, org)
    content = "Priya from Acme said the proposal looks good. Budget is approved. Can we meet Friday?"
    canned = {
        "relevance": 0.85, "noise_type": "none", "domains": ["sales"],
        "entity_mentions": [
            {"type": "person", "name": "Priya", "email": "priya@acme.io", "evidence_text": "Priya from Acme"},
            {"type": "company", "name": "Acme", "email": None, "evidence_text": "from Acme"}],
        "fact_candidates": [
            {"subject": "Priya", "field": "company", "value": "Acme", "evidence_text": "Priya from Acme"}],
        "commitments": [],
        "questions": [{"text": "meet Friday", "directed_at": "us", "evidence_text": "Can we meet Friday?"}],
        "observations": [
            {"kind": "positive_reply", "evidence_text": "looks good"},
            {"kind": "budget_approved", "evidence_text": "Budget is approved"}],
    }
    res = process_event(org_id=org, event_id="u1", source="gmail", content=content,
                        sender_email="priya@acme.io", occurred_at=NOW, llm=_FakeLLM(canned),
                        store=pg_store, is_inbound=True, internal_emails=frozenset(),
                        domain_hints=[{"domain": "sales"}])
    assert res.outcome == "committed"
    with pg_store.engine.begin() as conn:
        facts = conn.execute(text("select count(*) from graph_facts where org_id=:o"), {"o": org}).scalar()
        obs = conn.execute(text("select count(*) from graph_observations where org_id=:o"), {"o": org}).scalar()
    assert facts >= 1 and obs >= 1               # grounding kept the substring-backed items


def test_graph_health_scores_a_real_graph(pg_store):
    org = "e2e_health"
    _seed_org(pg_store, org)
    commit_structured(pg_store, org_id=org, event_id="h1", source="hubspot", source_object_id="deal_h",
                      structured_fields={"deal.stage": "won"}, node_type="deal", occurred_at=NOW,
                      display_name="Deal H", domain_hints=[{"domain": "sales"}])
    health = compute_health(pg_store, org)
    assert 0 <= health.overall <= 100
    assert health.dimensions and "integrity" in health.dimensions

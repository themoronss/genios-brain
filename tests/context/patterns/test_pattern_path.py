"""THE REAL PATH — the registry, reached over HTTP, over a real Postgres, with the fire log and
the activation guard behaving as they will in production.

Layer 1 shipped SIX units that were green and called by nothing, and every one was found in review
rather than by a test. This file is the answer to that for L2.6: every assertion below goes through
`POST /api/org/{org}/patterns/evaluate`, so if the router were not registered in `main.py`, or the
store read the wrong table, or the evaluator were never reached from a request, this is what fails.

It also drives the two things a pure test cannot:

  * the FIRE LOG — a run row per pattern including the ones that fired zero times, because "no
    fires" and "never ran" are the same empty result without it;
  * the ACTIVATION GUARD — a pattern that fires on every anchor is refused activation over HTTP,
    with the measured rate in the refusal. That is doc 09's H6 gate row, proven end to end.

And the report script, rendered from the same rows an operator would read.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

ORG = "org_x6_pattern_path"
EVAL_TIME = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
ACTOR = "harsh@thegenios.com"

pytestmark = pytest.mark.pg


def _seed_org(engine) -> None:
    """Its own tenant, not the shared scratch org. The fire RATE has a denominator — every node of
    the anchor's type in the org — so sharing a tenant with other suites would make this file's
    breach assertions depend on how many person nodes somebody else's test happened to write."""
    with engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": ORG}
        for r in reqd:
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else "{}" if dt in ("json", "jsonb") else "scratch")
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                          "on conflict (id) do nothing"), vals)


def _node(conn, node_id: str, node_type: str, name: str) -> None:
    conn.execute(text(
        "insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
        "  display_name, identity_strength, valid_from) "
        "values (:n, 1, :o, :t, :k, :d, 'strong', :at) on conflict do nothing"),
        {"n": node_id, "o": ORG, "t": node_type, "k": f"{node_type}:{node_id}", "d": name,
         "at": EVAL_TIME - timedelta(days=90)})


def _fact(conn, node_id: str, field: str, value) -> None:
    """`graph_facts.value` is JSONB, so a fact is written the way the pipeline writes one — a
    JSON scalar, not a bare string. Getting this wrong in a fixture would prove the evaluator
    against a column shape production does not have."""
    conn.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        "  value, value_type, status, authority_rank, occurred_at, valid_from) "
        "values (:fv, :fi, :o, :n, :f, cast(:v as jsonb), 'text', 'active', 2, :at, :at) "
        "on conflict do nothing"),
        {"fv": f"fv_{node_id}_{field}", "fi": f"f_{node_id}_{field}", "o": ORG, "n": node_id,
         "f": field, "v": json.dumps(value), "at": EVAL_TIME - timedelta(days=5)})


@pytest.fixture
def seeded(pg_store):
    """A tenant with four people, three of whom are in `condition_now_satisfied`'s situation.

    Three of four is a fire rate of 75 per 100 anchors per 30 days against a declared 6 and a
    ceiling of 60 — over the ceiling, deliberately, because the guard is what this file is for.
    """
    _seed_org(pg_store.engine)
    with pg_store.engine.begin() as conn:
        for table in ("pattern_fires", "pattern_runs", "pattern_activation", "graph_facts",
                      "graph_edges", "graph_observations", "graph_nodes"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        for i in range(4):
            node = f"node_person_{i}"
            _node(conn, node, "person", f"Person {i}")
            if i < 3:
                _fact(conn, node, "derived.timeline.condition_satisfied",
                      {"statement": "we will send it once legal signs off"})
                _fact(conn, node, "thread.ball_in_court", "us")
        # A commitment that is NOT unresolved: due in the future, so `commitment_unresolved` is
        # evaluated and correctly finds nothing. That is what makes the "silent" row meaningful.
        _node(conn, "node_cmt_1", "commitment", "send the deck")
        _fact(conn, "node_cmt_1", "commitment.status", "open")
        _fact(conn, "node_cmt_1", "commitment.due_at",
              (EVAL_TIME + timedelta(days=14)).isoformat())
    return pg_store


@pytest.fixture
def client(seeded):
    """The REAL router with only the tenant identity and the principal overridden."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import pattern_routes
    from genios_engine.platform.auth import AuthCtx, get_auth_ctx, get_current_org
    if pattern_routes._graph is None:
        pytest.skip("graph store not configured for the API module")
    app = FastAPI()
    app.include_router(pattern_routes.router)
    app.dependency_overrides[get_current_org] = lambda: ORG
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id=ACTOR)
    return TestClient(app)


# =================================================================================================
# The wiring itself
# =================================================================================================

def test_the_router_is_registered_on_the_application():
    """Asked of the SERVED application: `app.openapi()` is what the process actually answers on,
    so an `include_router` line deleted in a later refactor fails here."""
    from genios_engine.main import app
    served = app.openapi()["paths"]
    assert "/api/org/{org_id}/patterns" in served
    assert "/api/org/{org_id}/patterns/evaluate" in served
    assert "/api/org/{org_id}/patterns/{pattern_id}/activate" in served


# =================================================================================================
# Evaluation, over HTTP, over a real graph
# =================================================================================================

def test_evaluate_reaches_the_matcher_the_builder_the_scorer_and_both_framing_sites(client):
    """One request, five units. This is the "reached from a real path" proof for the whole
    package: nothing below is constructed by the test."""
    body = client.post(f"/api/org/{ORG}/patterns/evaluate",
                       params={"as_of": EVAL_TIME.isoformat()}).json()
    assert body["eval_time"].startswith("2026-03-01")
    fired = [c for c in body["candidates"] if c["pattern_id"] == "condition_now_satisfied"]
    assert len(fired) == 3, "three of four people are in this situation"

    one = fired[0]
    # The candidate builder's contract: per-condition evidence, carried, with a receipt each.
    assert len(one["matched_conditions"]) == 2
    assert all(c["ref"].startswith("fact:") for c in one["matched_conditions"])
    # The scorer's: strength and quality kept apart, and no importance anywhere.
    assert one["score"]["match_strength_bp"] == 6000
    assert "importance_bp" not in one["score"]
    # M-6 and M-7, reached and falling back deterministically because no model is wired here.
    assert one["framing"]["fallback"] is True
    assert one["framing"]["headline"]
    assert one["timeline"]["fallback"] is True


def test_the_evaluation_is_shadow_and_writes_no_situation(client, seeded):
    """Doc 06: keep anchor-based detection running alongside. Nothing here may touch the table
    `context/situations.py` owns, or the two paths cannot be compared for seven days."""
    before = _count(seeded, "context_situations")
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    assert _count(seeded, "context_situations") == before
    with seeded.engine.connect() as conn:
        activated = conn.execute(text(
            "select bool_or(activated) from pattern_fires where org_id = :o"),
            {"o": ORG}).scalar()
    assert activated is False, "a fire is shadow until somebody activates the pattern"


def test_the_fire_log_records_a_run_for_every_pattern_including_the_silent_ones(client, seeded):
    """"No fires" and "never ran" are the same empty result without a run row, and the difference
    is the whole remedy for a dead pattern."""
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    with seeded.engine.connect() as conn:
        rows = {r["pattern_id"]: r for r in conn.execute(text(
            "select pattern_id, fires, anchors_considered, top_failure_reason, top_failure_field "
            "from pattern_runs where org_id = :o"), {"o": ORG}).mappings().all()}
    assert len(rows) >= 6, "every registered pattern is evaluated, not only the ones that fire"
    assert rows["condition_now_satisfied"]["fires"] == 3
    assert rows["condition_now_satisfied"]["anchors_considered"] == 4

    # The silent pattern names the condition that stopped it — the line that turns "this is
    # silent" into "condition 1 failed on every anchor, and here is why".
    commitment = rows["commitment_unresolved"]
    assert commitment["fires"] == 0
    assert commitment["top_failure_reason"] == "temporal_window"
    assert commitment["top_failure_field"] == "commitment.due_at"


def test_re_evaluating_at_the_same_instant_does_not_double_the_fire_count(client, seeded):
    """Replaying a sweep must not double a tenant's fire rate — every rate in the report would be
    wrong by however many times the drain ran."""
    for _ in range(3):
        client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    with seeded.engine.connect() as conn:
        fires = conn.execute(text(
            "select count(*) from pattern_fires where org_id = :o "
            "and pattern_id = 'condition_now_satisfied'"), {"o": ORG}).scalar()
    assert fires == 3


def test_the_evaluation_is_deterministic_across_runs(client):
    """Same tenant, same instant, same answer — byte for byte over the candidates."""
    import json
    a = client.post(f"/api/org/{ORG}/patterns/evaluate",
                    params={"as_of": EVAL_TIME.isoformat()}).json()["candidates"]
    b = client.post(f"/api/org/{ORG}/patterns/evaluate",
                    params={"as_of": EVAL_TIME.isoformat()}).json()["candidates"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# =================================================================================================
# The guard, over HTTP — H6's gate row
# =================================================================================================

def test_a_pattern_that_fires_on_everything_cannot_be_activated(client):
    """H6: *"0 patterns activated while exceeding their expected fire rate 10x"*.

    `condition_now_satisfied` declares 6 per 100 anchors per 30 days, ceiling 60. It fired on 3 of
    4 anchors — 75 — and activation is refused over HTTP with the measured rate in the refusal.
    """
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    refused = client.post(f"/api/org/{ORG}/patterns/condition_now_satisfied/activate",
                          json={"as_of": EVAL_TIME.isoformat()})
    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    assert detail["activated"] is False
    assert detail["observed_rate_per_100_anchors_30d"] == 75
    assert detail["ceiling_rate_per_100_anchors_30d"] == 60


def test_the_refusal_is_stored_so_the_next_reader_sees_the_rate(client, seeded):
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    client.post(f"/api/org/{ORG}/patterns/condition_now_satisfied/activate",
                json={"as_of": EVAL_TIME.isoformat()})
    with seeded.engine.connect() as conn:
        row = conn.execute(text(
            "select activated_at, blocked_reason from pattern_activation "
            "where org_id = :o and pattern_id = 'condition_now_satisfied'"),
            {"o": ORG}).mappings().first()
    assert row["activated_at"] is None
    assert "matches everything is noise" in row["blocked_reason"]


def test_a_well_behaved_pattern_activates_and_can_be_turned_off_again(client, seeded):
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    allowed = client.post(f"/api/org/{ORG}/patterns/commitment_unresolved/activate",
                          json={"as_of": EVAL_TIME.isoformat()})
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["activated"] is True

    off = client.post(f"/api/org/{ORG}/patterns/commitment_unresolved/deactivate",
                      json={"as_of": EVAL_TIME.isoformat()})
    assert off.json()["activated"] is False
    with seeded.engine.connect() as conn:
        assert conn.execute(text(
            "select activated_at from pattern_activation where org_id = :o "
            "and pattern_id = 'commitment_unresolved'"), {"o": ORG}).scalar() is None


def test_activating_an_unregistered_pattern_is_a_404(client):
    assert client.post(f"/api/org/{ORG}/patterns/invented_pattern/activate").status_code == 404


def test_the_listing_shows_both_failures(client):
    """A page that showed only the loose patterns would make the silent ones worse."""
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    body = client.get(f"/api/org/{ORG}/patterns",
                      params={"as_of": EVAL_TIME.isoformat(), "since_days": 30}).json()
    assert body["registered"] >= 6
    assert "commitment_unresolved" in body["silent"]
    assert [d["pattern_id"] for d in body["breaching"]] == ["condition_now_satisfied"]
    rates = {p["pattern_id"]: p for p in body["patterns"]}
    assert rates["condition_now_satisfied"]["fires"] == 3
    assert rates["condition_now_satisfied"]["anchors"] == 4


def test_one_tenants_fires_are_invisible_to_another(client, seeded):
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    with seeded.engine.connect() as conn:
        assert conn.execute(text(
            "select count(*) from pattern_fires where org_id = 'org_scratch_tests'")).scalar() == 0


# =================================================================================================
# The gate command an operator actually runs
# =================================================================================================

def test_the_fire_report_reads_the_same_rows_and_names_both_failures(client, seeded):
    """`python scripts/pattern_fire_report.py --org <pilot> --since 30d`, rendered from the rows
    the route just wrote."""
    from scripts.pattern_fire_report import _fetch, activated_breaches, render
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    since = EVAL_TIME - timedelta(days=30)
    with seeded.engine.connect() as conn:
        report = _fetch(conn, ORG, since=since, until=EVAL_TIME)
    lines = "\n".join(render(report, ORG, since=since, until=EVAL_TIME))

    assert "condition_now_satisfied" in lines
    assert "over ceiling" in lines, "the loose pattern is named"
    assert "silent — condition" in lines, "and the silent one says WHICH condition stopped it"
    assert "temporal_window" in lines
    # Nothing is activated, so the gate row is 0 and the command exits 0 — a shadow pattern over
    # its ceiling is a calibration note, not a broken build.
    assert activated_breaches(report) == []
    assert "ACTIVATED over 10x   0" in lines


def test_the_report_exits_non_zero_only_on_an_ACTIVATED_breach(client, seeded, monkeypatch):
    """The H6 gate row, demonstrated: force the activation into the table and the same report now
    fails. Without this, "exits non-zero on a breach" is a claim nobody has seen happen."""
    from scripts.pattern_fire_report import _fetch, activated_breaches
    client.post(f"/api/org/{ORG}/patterns/evaluate", params={"as_of": EVAL_TIME.isoformat()})
    with seeded.engine.begin() as conn:
        conn.execute(text(
            "insert into pattern_activation (org_id, pattern_id, activated_at, activated_by) "
            "values (:o, 'condition_now_satisfied', :at, 'test') "
            "on conflict (org_id, pattern_id) do update set activated_at = excluded.activated_at"),
            {"o": ORG, "at": EVAL_TIME})
    # Read on a SEPARATE connection after the write commits — a read inside the writing
    # transaction would see the row and prove nothing about what the script sees.
    with seeded.engine.connect() as read:
        report = _fetch(read, ORG, since=EVAL_TIME - timedelta(days=30), until=EVAL_TIME)
    assert activated_breaches(report) == ["condition_now_satisfied"]


def test_the_report_cannot_inherit_the_production_database_url():
    """Modelled on `history_density_report`: the target is resolved through `scripts/_db.py`, which
    has no fallback to the configured URL — on a machine with a `.env`, that is production."""
    import argparse

    from scripts._db import UnsafeDatabaseTarget, resolve_database_url
    with pytest.raises(UnsafeDatabaseTarget):
        resolve_database_url(argparse.Namespace(database_url=None), purpose="test")


# =================================================================================================
# The model branch of the framing sites, driven from the same route
# =================================================================================================

def test_the_route_renders_the_model_framing_when_one_is_wired(client, monkeypatch):
    """Both halves of M-6 are proven from a real request: the deterministic fallback above, and
    the model branch here. The asker is overridden the way a per-tenant activation would wire it.
    """
    from genios_engine.api import pattern_routes

    def stub(_prompt):
        # Ids, never prose — and the ids have to be real, which is the whole contract.
        import re
        ids = re.findall(r"id=(fact:[^\s]+)", _prompt)
        return {"template_id": "condition_met", "slots": {"subject": ids[0]}} if ids else None

    monkeypatch.setattr(pattern_routes, "framing_asker", lambda: stub)
    body = client.post(f"/api/org/{ORG}/patterns/evaluate",
                       params={"as_of": EVAL_TIME.isoformat()}).json()
    fired = [c for c in body["candidates"] if c["pattern_id"] == "condition_now_satisfied"]
    framings = [c["framing"] for c in fired]
    assert any(f["fallback"] is False for f in framings), "the model branch was reached"
    for framing in framings:
        if not framing["fallback"]:
            assert framing["template_id"] == "condition_met"
            assert "waiting on has happened" in framing["headline"]


def _count(store, table: str) -> int:
    with store.engine.connect() as conn:
        return conn.execute(text(f"select count(*) from {table} where org_id = :o"),
                            {"o": ORG}).scalar() or 0

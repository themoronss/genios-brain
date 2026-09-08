"""Wave Z6 · gate K6 — the two outbound seams AS REQUEST PATHS, driven through the app.

    a corpus rule eliminates an AGENT'S proposed action via critique ......... POST, end to end
    BriefRanking produced daily with rank_components ......................... GET, end to end
    `advisory` still unfalsifiable .......................................... attacked, per path

WHY THIS FILE DRIVES HTTP AND NOT FUNCTIONS. This codebase has shipped thirteen unreached units
across three layers — Layer 1 six, Layer 2 five, Layer 3 two — and every one of them had a passing
unit test. A seam is not built until a credential can reach it, so the reachability half is asserted
structurally against the RUNNING application's OpenAPI schema (a router nobody includes is the same
defect one level up), and the behaviour half is driven through `TestClient` with the real
authorisation dependencies in place.

THE TENANT IS SEEDED THROUGH THE PRODUCTION LANE. `tests/reason/adapters/l3_pilot_seed.py` drives
real events through `context/pipeline.process_event`, the derived roll-ups in production order,
`refresh_situations`, the live compile and `deliver/pipeline.build_cards_for_org`. So the cards this
brief ranks are cards the product built, and the decisions the critique is scored against are
decisions the compiled lane made. Nothing here inserts a card, a signal or a reasoning row by hand.

Real Postgres. Without `GENIOS_TEST_DATABASE_URL` the DB half skips and the structural half — which
is the half that catches the defect above — still runs.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import l4_seam_routes as SEAM
from genios_engine.contracts.events import AGENT_API_SCOPES, INTELLIGENCE_API_SCOPES
from genios_engine.contracts.reasoning import ExecutionMode
from genios_engine.platform import l4_activation as ACT
from genios_engine.platform.auth import AuthCtx, get_auth_ctx
from genios_engine.reason import brief_ranking as B

from tests.reason.adapters.conftest import (CLOSING_PLAY, DEAL_FACTS, DEAL_OBSERVATIONS,
                                            URGENCY_RULE, compile_situation)

#: The agent's draft, and the doctrine it walks into. `urgency-must-belong-to-the-buyer` is doc 03's
#: named acceptance fixture and it is used here as itself.
AGENT_DRAFT = "Our quarter closes on Friday — can we get the paperwork signed before then?"

#: The target the deal situation is reasoned about. `reasoning_runs.root_node_id` is what the
#: critique seam resolves a `target_ref` against.
DEAL_NODE = "node_1"


# =================================================================================================
# the structural half — no database, and it is the half that catches an unreached seam
# =================================================================================================

def test_both_seams_are_registered_on_the_running_application():
    """Read off the OpenAPI schema of `genios_engine.main.app`, not off a router object: this
    FastAPI includes routers at import, and a router built but never included is exactly the
    "looked fine from a unit test" failure this layer keeps repeating."""
    from genios_engine.main import app

    paths = app.openapi()["paths"]
    assert "/v1/intelligence/critique" in paths, \
        "no request path lets an agent have its proposed action scored"
    assert "post" in paths["/v1/intelligence/critique"]
    assert "/v1/intelligence/brief" in paths, "no request path produces the book-level re-rank"
    assert "/v1/intelligence/brief/{date_key}" in paths, \
        "no request path answers 'what did the brief say on Tuesday'"


def test_the_critique_grant_is_one_an_owner_can_actually_mint():
    """doc 06 says the scope is agent-grantable, and BOTH minting paths validate against a fixed
    allow-list — so a scope missing from them is one no tenant can ever issue, leaving an endpoint
    reachable only by an owner session, which is not the seam.

    It is its OWN family rather than an addition to `AGENT_API_SCOPES`, and that is the point:
    adding it there would have widened every key a tenant has already issued — every credential
    carrying `signals.read` would silently have gained the right to submit proposals.
    """
    import inspect

    from genios_engine.api import routes as CORE
    from genios_engine.api.auth_routes import GRANTABLE

    assert SEAM.CRITIQUE_SCOPE == "intelligence.critique"
    assert SEAM.CRITIQUE_SCOPE in INTELLIGENCE_API_SCOPES
    assert SEAM.CRITIQUE_SCOPE not in AGENT_API_SCOPES
    assert SEAM.CRITIQUE_SCOPE in GRANTABLE, "an owner cannot mint a key carrying the grant"
    assert "INTELLIGENCE_API_SCOPES" in inspect.getsource(CORE.register_agent), \
        "/agents/register would refuse the grant doc 06 says is agent-grantable"


def test_the_brief_table_is_erased_with_the_account():
    """Everything in it is a statement about this tenant's own situations."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES

    assert "l4_brief_rankings" in _ORG_SCOPED_TABLES


def test_the_critique_route_is_scoped_and_the_brief_route_is_owner_only():
    """Read the dependencies structurally: a route that lost its guard in a refactor still returns
    200 to the test that only checks the happy path."""
    import inspect

    from fastapi.params import Depends as DependsMarker

    critique = inspect.signature(SEAM.critique_proposed_action).parameters["ctx"].default
    assert isinstance(critique, DependsMarker)
    assert "require_scope" in repr(critique.dependency) or callable(critique.dependency)
    brief = inspect.signature(SEAM.daily_brief).parameters["org_id"].default
    assert isinstance(brief, DependsMarker)
    from genios_engine.platform.auth import get_current_org
    assert brief.dependency is get_current_org


# =================================================================================================
# the real-Postgres half
# =================================================================================================

def _url() -> str:
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the Z6 request paths are not exercised")
    return url


@pytest.fixture(scope="module")
def seeded():
    """One tenant, seeded through the production lane, with both Z6 features switched on.

    The evaluation instant is the WALL CLOCK rather than a fixed past date, and that is deliberate
    rather than sloppy: a card expires seven days after it is built and a context payload is swept
    at 720 hours, so a tenant seeded at a frozen 2026-08-08 has an empty card queue and an
    unreplayable run by the time anybody runs this — the two seams would then be tested against a
    tenant with nothing in it and would pass by saying nothing. Every assertion below is about
    structure and arithmetic, never about a hash, so a moving instant costs nothing.
    """
    url = _url()
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.db import get_engine
    from tests.reason.adapters.l3_pilot_seed import seed_admin_pilot

    org = "org_z6_seams_out"
    engine = get_engine(url)
    store = GraphStore(url)
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
        conn.execute(text("insert into orgs (id, name) values (:o,:o)"), {"o": org})
    # BEFORE the seed: `domain_shadow` reads `ranking_v2` per tenant when it compiles, so switching
    # it on afterwards would leave every decision on the five-weight model — which the critique
    # seam refuses, correctly, and which would make this a test of the refusal.
    for feature in (ACT.FEATURE_RANKING_V2, ACT.FEATURE_CRITIQUE, ACT.FEATURE_BRIEF):
        ACT.activate(engine, org, feature=feature, by="tests")

    now = datetime.now(timezone.utc)
    counts = seed_admin_pilot(store, org, eval_time=now)
    assert counts["compile"]["emitted"] >= 2, counts
    assert counts["delivery"]["built"] >= 2, counts
    _persist_deal_run(engine, org, now)
    yield {"org": org, "engine": engine, "store": store, "url": url, "now": now}
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})


def _persist_deal_run(engine, org: str, now: datetime) -> None:
    """One compiled SALES situation, reasoned and audited, so the critique has doctrine to meet.

    The admin tenant above carries admin doctrine; the rule doc 03 names as the acceptance fixture
    is a sales closing rule, and it is the one this gate is written about. Compiled from the shipped
    corpus, reasoned by `reason_native_capability` — the same entry the live pass calls — and
    persisted through `persist_execution`, so what the endpoint later reads is a real audit bundle
    that has to verify before it can be used.
    """
    from genios_engine.reason.adapters.expertise import expertise_capability_manifest
    from genios_engine.reason.adapters.native import reason_native_capability
    from genios_engine.reason.audit import persist_execution
    from genios_engine.reason.engine import NodeContext
    from genios_engine.reason.store import ReasoningStore

    compiled = compile_situation(absent=("commitment.due_at",))
    manifest = expertise_capability_manifest(
        compiled.package, root_entity_type="company", situation=compiled.situation,
        context=compiled.context, ranking_v2=True)
    context = NodeContext(
        node_id=DEAL_NODE, node_type="company",
        facts={path: {"value": value, "confidence": 900, "authority_rank": 3}
               for path, value in DEAL_FACTS.items()},
        obs=[{"kind": kind, "occurred_at": now} for kind in DEAL_OBSERVATIONS])
    execution = reason_native_capability(
        org_id=org, context=context, capability=manifest, evaluation_time=now,
        graph_version=1, config_snapshot_id=None, mode=ExecutionMode.SHADOW)
    persist_execution(store=ReasoningStore(engine=engine), execution=execution)


def _client(ctx: AuthCtx) -> TestClient:
    """The real router with the real authorisation dependencies; only the credential is supplied.

    `get_auth_ctx` is the seam a credential arrives through, so overriding IT (rather than
    `require_scope` or `get_current_org`) keeps both guards under test — the 403 below is produced
    by the shipped dependency, not by a stand-in for it.
    """
    app = FastAPI()
    app.include_router(SEAM.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app, raise_server_exceptions=False)


def _agent(org: str, *, scopes=(SEAM.CRITIQUE_SCOPE,)) -> AuthCtx:
    return AuthCtx(org_id=org, agent_id="agent_hermes", actor_id="agent_hermes",
                   scopes=list(scopes), source="api_key")


def _owner(org: str) -> AuthCtx:
    return AuthCtx(org_id=org, actor_id="founder@tenant.test", scopes=None, source="jwt")


def _proposal(**overrides) -> dict:
    body = {"target_ref": DEAL_NODE, "proposal_id": "prop_agent_1", "agent_id": "agent_hermes",
            "proposed_action": {"kind": "email_draft", "draft": AGENT_DRAFT,
                                "params": {"impact_bp": 6_000, "effort_bp": 2_000}}}
    body.update(overrides)
    return body


# ── E1 · K6's row: authored doctrine binds an action GeniOS did not generate ─────────────────

@pytest.mark.pg
def test_a_corpus_rule_holds_an_agents_proposed_action_over_http(seeded):
    """THE GATE ROW. An external agent posts a draft; the response is `hold`, and the reason is a
    rule a human wrote in a YAML file, quoted back with the play it removed from our own field."""
    response = _client(_agent(seeded["org"])).post("/v1/intelligence/critique", json=_proposal())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "hold"
    assert body["failing_checks"] == [URGENCY_RULE]
    assert "A closing recommendation MUST rest on a date the BUYER owns" in body["rationale"]
    urgency = next(row for row in body["receipt"]["rules_consulted"]
                   if row["rule_id"] == URGENCY_RULE)
    assert urgency["severity"] == "blocking" and urgency["applies"] is True
    assert CLOSING_PLAY in urgency["scope_play_ids"]
    # ...and the answer names the run it was judged against, so an agent can ask for the same
    # decision's explanation rather than taking the verdict on trust.
    assert body["receipt"]["evidence"]["run_id"].startswith("rrun_")
    assert body["receipt"]["evidence"]["replay_mode"] == "payload_verified"


@pytest.mark.pg
def test_the_verdict_that_crosses_the_wire_is_advisory_and_no_request_can_change_that(seeded):
    """`advisory` is the safety property of the seam, attacked from the one place an attacker
    actually stands: the request body. `params` is the agent's own payload and reaches the scorer;
    nothing in it reaches the verdict's authority bit, which is True on every path."""
    client = _client(_agent(seeded["org"]))
    hostile = _proposal()
    hostile["proposed_action"]["params"] = {"impact_bp": 9_000, "advisory": False,
                                            "binding": True, "verdict": "proceed"}

    body = client.post("/v1/intelligence/critique", json=hostile).json()

    assert body["advisory"] is True
    assert body["verdict"] == "hold"


@pytest.mark.pg
def test_an_agent_cannot_declare_the_situations_urgency_through_the_endpoint(seeded):
    hostile = _proposal()
    hostile["proposed_action"]["params"] = {"urgency_bp": 10_000}

    response = _client(_agent(seeded["org"])).post("/v1/intelligence/critique", json=hostile)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "agent_declared_a_situation_component"


@pytest.mark.pg
def test_a_target_nothing_has_ever_been_reasoned_about_is_refused_not_answered(seeded):
    """A verdict with no situation behind it is an opinion wearing a receipt's clothes."""
    response = _client(_agent(seeded["org"])).post(
        "/v1/intelligence/critique", json=_proposal(target_ref="node_never_reasoned"))

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "no_reasoned_situation_for_target"


@pytest.mark.pg
def test_an_unknown_action_kind_is_refused_at_the_boundary(seeded):
    response = _client(_agent(seeded["org"])).post("/v1/intelligence/critique", json=_proposal(
        proposed_action={"kind": "launch_missile", "draft": "x", "params": {}}))

    assert response.status_code == 422
    assert "kind must be one of" in response.text


@pytest.mark.pg
def test_a_credential_without_the_grant_cannot_reach_the_critique_seam(seeded):
    response = _client(_agent(seeded["org"], scopes=("signals.read",))).post(
        "/v1/intelligence/critique", json=_proposal())

    assert response.status_code == 403
    assert SEAM.CRITIQUE_SCOPE in response.text


@pytest.mark.pg
def test_an_unactivated_tenant_has_no_critique_seam_at_all(seeded):
    """404 rather than 403: for this org the surface does not exist yet, and saying "you may not"
    would invite a retry with a better credential and describe another tenant's configuration."""
    engine, org = seeded["engine"], seeded["org"]
    ACT.deactivate(engine, org, feature=ACT.FEATURE_CRITIQUE, by="tests")
    try:
        response = _client(_agent(org)).post("/v1/intelligence/critique", json=_proposal())
        assert response.status_code == 404
        assert "critique" in response.text
    finally:
        ACT.activate(engine, org, feature=ACT.FEATURE_CRITIQUE, by="tests")


@pytest.mark.pg
def test_the_critique_writes_nothing_to_the_graph_signals_or_cards(seeded):
    """GeniOS scores; the agent executes. The seam is a READ of the decision record, and an
    endpoint that quietly emitted would be this layer taking an action on somebody's behalf."""
    engine, org = seeded["engine"], seeded["org"]
    counted = ("signals", "cards", "card_events", "delivery_outbox", "reasoning_runs",
               "graph_facts", "graph_observations")
    with engine.connect() as conn:
        before = {table: conn.execute(text(f"select count(*) from {table} where org_id=:o"),
                                      {"o": org}).scalar() for table in counted}

    _client(_agent(org)).post("/v1/intelligence/critique", json=_proposal())

    with engine.connect() as conn:
        after = {table: conn.execute(text(f"select count(*) from {table} where org_id=:o"),
                                     {"o": org}).scalar() for table in counted}
    assert before == after


# ── E3 · the book-level brief, produced daily with rank_components ───────────────────────────

@pytest.mark.pg
def test_the_brief_ranks_todays_decisions_against_each_other_with_components(seeded):
    """THE OTHER GATE ROW. Every entry carries the terms that put it where it is — "why #1 today"
    answered in data, from a pass that compared the day's decisions with one another."""
    response = _client(_owner(seeded["org"])).get("/v1/intelligence/brief")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["brief_date_key"] == B.brief_date_key(datetime.now(timezone.utc))
    assert body["model_version"] == B.BOOK_RANKING_VERSION
    assert len(body["entries"]) >= 2, body
    for entry in body["entries"]:
        components = entry["rank_components"]
        assert set(components) == {B.BASE_COMPONENT, B.CONCENTRATION_COMPONENT,
                                   B.STALENESS_COMPONENT, B.COVERAGE_COMPONENT,
                                   B.BOOK_SCORE_COMPONENT}
        assert entry["book_score_bp"] == components[B.BOOK_SCORE_COMPONENT]
        assert entry["card_id"] and entry["headline"], "an entry names the card it ranked"
    assert [entry["rank"] for entry in body["entries"]] == list(
        range(1, len(body["entries"]) + 1))


@pytest.mark.pg
def test_the_coverage_term_is_read_from_what_the_decision_itself_recorded(seeded):
    """`absence_count` is `reasoning_run_outputs.missing_data` — the decision's own uncertainty,
    not a number this pass invented. On a `ranking_v2` tenant with no measured importance, every
    decision records `importance_absent`, so the term is live rather than theoretical."""
    body = _client(_owner(seeded["org"])).get("/v1/intelligence/brief").json()
    entry = body["entries"][0]

    with seeded["engine"].connect() as conn:
        recorded = conn.execute(text(
            "select jsonb_array_length(missing_data) from reasoning_run_outputs "
            "where org_id=:o and run_id=:r"), {"o": seeded["org"], "r": entry["run_id"]}).scalar()

    assert entry["absence_count"] == recorded
    assert entry["rank_components"][B.COVERAGE_COMPONENT] == min(
        recorded * B.COVERAGE_STEP_BP, B.COVERAGE_CAP_BP)


@pytest.mark.pg
def test_the_brief_is_stored_for_the_day_and_a_re_read_does_not_rewrite_it(seeded):
    """A brief is a daily ARTIFACT. The row is what makes "was one produced" a query and "why was
    that first on Tuesday" answerable after the open set has moved on."""
    client = _client(_owner(seeded["org"]))
    first = client.get("/v1/intelligence/brief").json()
    second = client.get("/v1/intelligence/brief").json()

    assert second["ranking_hash"] == first["ranking_hash"]
    assert second["changed"] is False, "an unchanged brief must not rewrite its own row"
    stored = client.get(f"/v1/intelligence/brief/{first['brief_date_key']}")
    assert stored.status_code == 200
    body = stored.json()
    assert body["entry_count"] == len(first["entries"])
    assert body["ranking_hash"] == first["ranking_hash"]
    assert body["entries"][0]["rank_components"], "the stored artifact carries the components too"


@pytest.mark.pg
def test_a_day_with_no_brief_is_a_404_and_not_an_empty_one(seeded):
    response = _client(_owner(seeded["org"])).get("/v1/intelligence/brief/1999-01-01")
    assert response.status_code == 404


@pytest.mark.pg
def test_a_thrice_surfaced_card_decays_in_the_days_ranking(seeded):
    """doc 06's staleness row, on real rows: the surfacings are written by `CardStore.log_event` —
    the production writer — and the leading card steps down without its DECISION changing at all."""
    from genios_engine.deliver.store import CardStore

    client = _client(_owner(seeded["org"]))
    before = client.get("/v1/intelligence/brief").json()
    leader = before["entries"][0]
    runner_up = before["entries"][1]

    cards = CardStore(seeded["url"])
    for _ in range(3):
        cards.log_event(leader["card_id"], seeded["org"], "card.surfaced", cause="dashboard")

    after = client.get("/v1/intelligence/brief").json()
    decayed = next(entry for entry in after["entries"]
                   if entry["decision_id"] == leader["decision_id"])
    assert decayed["surfaced_count"] == 3
    assert decayed["rank_components"][B.STALENESS_COMPONENT] == 2 * B.STALENESS_STEP_BP
    assert decayed["book_score_bp"] < leader["book_score_bp"]
    assert after["changed"] is True
    if leader["book_score_bp"] - runner_up["book_score_bp"] < 2 * B.STALENESS_STEP_BP:
        # The decay was larger than the gap, so the brief now leads with the other card. This is
        # the whole point of the term: nothing about the decision changed, only the day.
        assert after["entries"][0]["decision_id"] == runner_up["decision_id"]


@pytest.mark.pg
def test_two_cards_on_one_account_compete_and_the_best_carries(seeded):
    """doc 06's concentration row, on a real `works_at` edge written by the graph store itself."""
    client = _client(_owner(seeded["org"]))
    before = client.get("/v1/intelligence/brief").json()
    assert all(entry["rank_components"][B.CONCENTRATION_COMPONENT] == 0 for entry in
               before["entries"]), "the fixture must start with the cards on separate accounts"

    from genios_engine.platform.ids import new_id
    store, org = seeded["store"], seeded["org"]
    with store.engine.begin() as conn:
        company = conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, valid_from) "
            "values (:n,:o,'company','One Account', now()) returning node_id"),
            {"n": new_id("node"), "o": org}).scalar()
        for entry in before["entries"]:
            store.write_edge(conn, org_id=org, edge_type="works_at",
                             from_node_id=entry["subject_node_id"], to_node_id=company,
                             confidence=0.9, occurred_at=datetime.now(timezone.utc),
                             event_id="test_concentration", evidence={}, source="test")

    after = client.get("/v1/intelligence/brief").json()
    penalties = [entry["rank_components"][B.CONCENTRATION_COMPONENT]
                 for entry in after["entries"]]
    assert all(entry["account_ref"] == company for entry in after["entries"])
    assert penalties[0] == 0, "the account's best card carries it"
    assert penalties[1] == B.CONCENTRATION_STEP_BP, "the second card on one account steps down"


@pytest.mark.pg
def test_an_unactivated_tenant_has_no_brief_seam(seeded):
    engine, org = seeded["engine"], seeded["org"]
    ACT.deactivate(engine, org, feature=ACT.FEATURE_BRIEF, by="tests")
    try:
        assert _client(_owner(org)).get("/v1/intelligence/brief").status_code == 404
    finally:
        ACT.activate(engine, org, feature=ACT.FEATURE_BRIEF, by="tests")


@pytest.mark.pg
def test_a_scoped_credential_cannot_read_the_brief(seeded):
    """The brief is the whole tenant's book. An agent key granted a critique scope reads its own
    lane, never the founder's morning."""
    response = _client(_agent(seeded["org"])).get("/v1/intelligence/brief")
    assert response.status_code == 403


@pytest.mark.pg
def test_the_stored_brief_is_erased_through_the_wipe_that_actually_runs():
    """Driven through `account_routes._wipe`, not through a DELETE this test writes: a table named
    in `_ORG_SCOPED_TABLES` and never exercised is a row that leaks on the day it matters.

    Its OWN tenant, because `_wipe` erases signals, cards and reasoning runs — sharing the seeded
    org would make this test destroy the fixture every other test in this file reads, and which of
    them noticed would depend on collection order.
    """
    from genios_engine.api.account_routes import _wipe
    from genios_engine.platform.db import get_engine

    engine = get_engine(_url())
    org = "org_z6_seams_erase"
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
        conn.execute(text("insert into orgs (id, name) values (:o,:o)"), {"o": org})
    now = datetime.now(timezone.utc)
    # The production writer, with a real ranking — the same call the request path makes.
    ranking = B.book_rank(org_id=org, eval_time=now, decisions=(
        B.OpenDecision(decision_id="decision_erase_me", account_ref="acct", base_utility_bp=5_000,
                       card_id="card_erase_me"),))
    assert B.store_ranking(engine, ranking, computed_at=now) is True

    try:
        with engine.connect() as conn:
            assert conn.execute(text("select count(*) from l4_brief_rankings where org_id=:o"),
                                {"o": org}).scalar() == 1
        with engine.begin() as conn:
            wiped = _wipe(conn, org)
        assert wiped["l4_brief_rankings"] == 1
        with engine.connect() as conn:
            assert conn.execute(text("select count(*) from l4_brief_rankings where org_id=:o"),
                                {"o": org}).scalar() == 0
    finally:
        with engine.begin() as conn:
            conn.execute(text("delete from orgs where id=:o"), {"o": org})

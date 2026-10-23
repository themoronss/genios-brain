"""GeniOS-011 S40.U2 · GET /feedback/precision shows what shadow calibration WOULD do, and precision by layer.

    pytest tests/api/test_precision_shows_shadow_calibration.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest … -q            # + the behavioural half

⛔ WHY THIS ROUTE (audit `l6-calibration-shadow-unread`). Calibration runs every week in SHADOW
(STEP-18 B1): it scores every rule and stores `would_mute` / `would_nudge` in
`calibration_runs.result`, and nobody reads them — so Rohit cannot see what arming
`calibration_apply` would do before he decides D13. ⛔ `would_mute` holds bare rule ids, so the
route REPLAYS the run's own measurement (`precision_28d` at the run's pack version, authority
revision and evaluation time; the judgments CTE is bounded by `:as_of`) to give each one its
precision and n.

⛔ AND THE LAST UNREAD LEDGER (audit `l6-unread-ledgers`). Every METRICS proposal lands in
`learning_metrics` and nothing selected it; its own declaration said *"MOVES WHEN a
precision-by-layer surface exists"*. This is that surface. ⛔ `actor_outcome_analysis` is
`Visibility(PRIVATE, principals=(assignee,))` and the table stores no visibility, while the route
admits any seat of the org — so its rows are never selected (and they would double-count L4, being
the same outcomes grouped by person).

⛔ READ ONLY. The route calls no calibration, reads no switch, and writes nothing; arming stays
behind `calibration_apply`, which is never default-on (memory calibration-fix-arms-auto-mute).
"""
from __future__ import annotations

import ast
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROUTES = Path(__file__).resolve().parents[2] / "genios_engine" / "api" / "routes.py"
_PG = pytest.mark.skipif(not os.environ.get("GENIOS_TEST_DATABASE_URL"),
                         reason="GENIOS_TEST_DATABASE_URL not set — real-Postgres tests skipped")


# =================================================================================================
# 1 · hermetic — the route is a read, and it cannot arm anything
# =================================================================================================
def _tree() -> ast.Module:
    return ast.parse(ROUTES.read_text(encoding="utf-8"))


def _function(name: str) -> ast.FunctionDef:
    found = [n for n in ast.walk(_tree()) if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(found) == 1, f"{name} is defined {len(found)} times in api/routes.py"
    return found[0]


def _constant(name: str) -> str:
    for node in _tree().body:
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name
                                                 for t in node.targets)):
            value = ast.literal_eval(node.value)
            assert isinstance(value, str), name
            return value
    raise AssertionError(f"{name} is not a module-level constant of api/routes.py")


_READERS = ("feedback_precision", "_last_shadow_calibration", "_precision_by_layer")
_SQL = ("_LAST_SHADOW_CALIBRATION_SQL", "_PRECISION_BY_LAYER_SQL")


def test_the_route_reads_the_shadow_run_and_the_metrics_ledger():
    names = {n.id for n in ast.walk(_function("feedback_precision")) if isinstance(n, ast.Name)}
    assert {"_last_shadow_calibration", "_precision_by_layer"} <= names, names


@pytest.mark.parametrize("fn", _READERS)
def test_the_route_calls_no_calibration_and_reads_no_switch(fn):
    """A call to `run_calibration` or `is_l4_activated`, or a name of the arming feature, inside
    the read path would make a GET one step from a mute."""
    tree = _function(fn)
    called = {getattr(n.func, "id", None) or getattr(n.func, "attr", None)
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not called & {"run_calibration", "is_l4_activated", "expire_cards"}, called
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "FEATURE_CALIBRATION_APPLY" not in names


@pytest.mark.parametrize("name", _SQL)
def test_each_statement_is_one_select(name):
    sql = " ".join(_constant(name).lower().split())
    assert sql.startswith("select "), sql
    for verb in ("insert ", "update ", "delete ", " for update"):
        assert verb not in sql, (name, verb)


def test_the_private_actor_metrics_are_never_selected():
    sql = _constant("_PRECISION_BY_LAYER_SQL")
    assert "actor_outcome_analysis" not in sql
    assert "unit in (" in " ".join(sql.split()), "the units must be an allow-list, not a deny-list"


def test_only_shadow_runs_are_read():
    assert "result->>'mode'='shadow'" in _constant("_LAST_SHADOW_CALIBRATION_SQL").replace(" ", "")


# =================================================================================================
# 2 · behavioural — on Postgres, through the production lanes
# =================================================================================================
def _route(monkeypatch, store):
    from genios_engine.api import routes
    monkeypatch.setattr(routes, "_graph", store)
    return routes.feedback_precision


def _harmful_rule(store, n_people: int) -> str:
    """`n_people` people we owe a reply → that many `unanswered_email` cards that prescribed → the
    founder presses `wrong: not relevant` on each → one shadow calibration run. 13 judgments at
    precision 0 is a would-mute; 10 is below the mute floor (12) and eligible (8), so a would-nudge."""
    from sqlalchemy import text

    from genios_engine.deliver.actions import ingest_action
    from genios_engine.deliver.pipeline import build_cards_for_org
    from genios_engine.deliver.store import CardStore
    from genios_engine.feedback.calibrate import run_calibration
    from genios_engine.packs.wiring import ensure_defaults
    from genios_engine.packs.wiring import make_registry
    from genios_engine.reason.runner import run_all
    from tests.feedback.test_calibration_runs_on_postgres import _org

    url = store.engine.url.render_as_string(hide_password=False)
    org = _org(store, n_people=n_people)
    registry = make_registry(url)
    ensure_defaults(registry, org)
    now = datetime.now(timezone.utc)
    run_all(org_id=org, store=store, eval_time=now, registry=registry)
    build_cards_for_org(graph=store, card_store=CardStore(url), org_id=org, llm=None,
                        registry=registry, eval_time=now)
    with store.engine.begin() as c:
        c.execute(text("update cards set level='prescriptive' where org_id=:o"), {"o": org})
        cards = c.execute(text(
            "select k.card_id from cards k join signals s on s.signal_id=k.signal_id "
            "and s.org_id=k.org_id where k.org_id=:o and s.rule_id='unanswered_email'"),
            {"o": org}).scalars().all()
    assert len(cards) == n_people, cards
    for card_id in cards:
        pressed = ingest_action(card_store=None, graph=store, org_id=org, card_id=card_id,
                                actor="founder", action="wrong", reason="not_relevant",
                                eval_time=datetime.now(timezone.utc))
        assert pressed.get("ok"), pressed
    result = run_calibration(store, org, pack_id="general", eval_time=datetime.now(timezone.utc))
    assert result["mode"] == "shadow" and result["applied"] is False, result
    return org


def _snapshot(store, org):
    from sqlalchemy import text
    with store.engine.connect() as c:
        return (
            c.execute(text("select count(*) from rule_mutes where org_id=:o"), {"o": org}).scalar(),
            tuple(c.execute(text("select authority_revision, lvl3_config from tenant_packs "
                                 "where org_id=:o and pack_id='general'"), {"o": org}).one()),
            c.execute(text("select count(*) from cards where org_id=:o and state in "
                           "('queued','surfaced','snoozed','claimed','delivered')"),
                      {"o": org}).scalar(),
            c.execute(text("select count(*) from calibration_runs where org_id=:o"),
                      {"o": org}).scalar(),
            c.execute(text("select count(*) from calibration_nudges where org_id=:o"),
                      {"o": org}).scalar())


@pytest.mark.pg
@_PG
def test_the_last_shadow_run_shows_its_would_mute_with_precision_and_n(pg_store, monkeypatch):
    from tests.feedback.test_calibration_runs_on_postgres import _drop
    org = _harmful_rule(pg_store, 13)
    try:
        before = _snapshot(pg_store, org)
        body = _route(monkeypatch, pg_store)(pack_id="general", org_id=org)
        assert _snapshot(pg_store, org) == before, "a GET changed a mute, the pack, a card or a run"

        shadow = body["shadow_calibration"]
        assert shadow is not None and shadow["mode"] == "shadow" and shadow["applied"] is False
        assert shadow["would_mute"] == [
            {"rule_id": "unanswered_email", "precision": 0.0, "n": 13}], shadow
        assert shadow["rules_scored"] >= 1 and shadow["run_id"].startswith("calrun")
        assert "rules" in body and body["pack_id"] == "general", "the existing payload is kept"
        json.dumps(body)                                  # the route's answer is JSON as returned
    finally:
        _drop(pg_store, org)


@pytest.mark.pg
@_PG
def test_the_last_shadow_run_shows_its_would_nudge_with_n(pg_store, monkeypatch):
    from tests.feedback.test_calibration_runs_on_postgres import _drop
    org = _harmful_rule(pg_store, 10)
    try:
        shadow = _route(monkeypatch, pg_store)(pack_id="general", org_id=org)["shadow_calibration"]
        assert shadow["would_mute"] == [], shadow
        nudges = [n for n in shadow["would_nudge"] if n["rule_id"] == "unanswered_email"]
        assert len(nudges) == 1, shadow
        assert nudges[0]["direction"] == "tighten" and nudges[0]["after"] > nudges[0]["before"]
        assert nudges[0]["precision"] == 0.0 and nudges[0]["n"] == 10, nudges
    finally:
        _drop(pg_store, org)


def _plain_org(store) -> str:
    from sqlalchemy import text
    org = f"s40u2_{uuid.uuid4().hex[:10]}"
    with store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": org})
    return org


def _metric(store, org, unit, subject, value, observed_at):
    from sqlalchemy import text
    with store.engine.begin() as c:
        c.execute(text(
            "insert into learning_metrics (org_id, metric_id, learning_id, unit, subject, value, "
            "observed_at) values (:o, :m, :l, :u, :s, cast(:v as jsonb), :at)"),
            {"o": org, "m": f"met_{uuid.uuid4().hex[:12]}", "l": f"lo_{uuid.uuid4().hex[:12]}",
             "u": unit, "s": subject, "v": json.dumps(value), "at": observed_at})


@pytest.mark.pg
@_PG
def test_precision_by_layer_reads_each_subjects_latest_metric(pg_store, monkeypatch):
    from tests.feedback.test_calibration_runs_on_postgres import _drop
    org, other = _plain_org(pg_store), _plain_org(pg_store)
    now = datetime.now(timezone.utc)
    try:
        # L2 — per rule. rule:a's OLDER measurement (0 of 5) is superseded by its latest (3 of 4).
        _metric(pg_store, org, "feedback_learning", "rule:a", {"acted": 0, "wrong": 5},
                now - timedelta(days=9))
        _metric(pg_store, org, "feedback_learning", "rule:a", {"acted": 3, "wrong": 1},
                now - timedelta(days=2))
        _metric(pg_store, org, "feedback_learning", "rule:b", {"acted": 1, "wrong": 0}, now)
        # L4 — per (capability, play). The private per-person rows must not reach it.
        _metric(pg_store, org, "outcome_analysis", "cap:play", {"succeeded": 2, "failed": 2}, now)
        _metric(pg_store, org, "actor_outcome_analysis", "actor:sam",
                {"succeeded": 9, "failed": 0}, now)
        # L5 — per channel: half of four delivered cards were engaged.
        _metric(pg_store, org, "performance_optimization", "channel:push",
                {"delivered": 4, "engagement_rate_bp": 5000}, now)
        # Another tenant's measurement is never this tenant's precision.
        _metric(pg_store, other, "feedback_learning", "rule:a", {"acted": 0, "wrong": 50}, now)

        body = _route(monkeypatch, pg_store)(pack_id="general", org_id=org)
        layers = {row["layer"]: row for row in body["precision_by_layer"]}
        assert [row["layer"] for row in body["precision_by_layer"]] == ["L2", "L4", "L5"]
        assert (layers["L2"]["n"], layers["L2"]["precision"], layers["L2"]["subjects"]) == (5, 0.8, 2)
        assert (layers["L4"]["n"], layers["L4"]["precision"], layers["L4"]["subjects"]) == (4, 0.5, 1)
        assert (layers["L5"]["n"], layers["L5"]["precision"], layers["L5"]["subjects"]) == (4, 0.5, 1)
        assert {row["unit"] for row in body["precision_by_layer"]} == {
            "feedback_learning", "outcome_analysis", "performance_optimization"}
        assert "actor" not in json.dumps(body["precision_by_layer"])
        assert body["shadow_calibration"] is None, "no run yet is None, not an invented one"
    finally:
        _drop(pg_store, org)
        _drop(pg_store, other)


@pytest.mark.pg
@_PG
def test_a_tenant_with_nothing_measured_says_so(pg_store, monkeypatch):
    from tests.feedback.test_calibration_runs_on_postgres import _drop
    org = _plain_org(pg_store)
    try:
        body = _route(monkeypatch, pg_store)(pack_id="general", org_id=org)
        assert body["shadow_calibration"] is None
        assert [(r["layer"], r["n"], r["precision"], r["subjects"])
                for r in body["precision_by_layer"]] == [
            ("L2", 0, None, 0), ("L4", 0, None, 0), ("L5", 0, None, 0)]
    finally:
        _drop(pg_store, org)

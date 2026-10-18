"""STEP-07 · the company brief is reviewed once a week, per tenant, for what it is missing.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_company_brief_review_is_weekly.py -q

Tree `yc2_w27_s07 · M25.C3.L-integration.V4.U04`. A brief written once goes stale. Once per ISO week,
for every tenant whose founder accepted at least one line, the drafter is asked again — with the brief
in force in its prompt — and what it returns is written as proposals by `weekly`. The week is claimed in
`company_brief_reviews`, so every replica may call it on every heavy tick and the week is reviewed once;
with no model it does nothing at all; one tenant's failure is recorded and the rest go on.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.llm.client import LLMResult
from genios_engine.platform import company_brief_store as store
from genios_engine.reason.brief_review import run_company_brief_reviews, week_key

pytestmark = pytest.mark.pg

ORGS = ("org_s07_review_a", "org_s07_review_b", "org_s07_review_none")
NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)          # a Wednesday, ISO week 41
PATTERNS = {"company": "Nimbus Labs", "founder": "Arjun Rao", "us": [], "window_days": 180,
            "items": [{"id": "p1", "kind": "domain", "domain": "hub71.com", "mail": 4, "archived": 1,
                       "senders": 2, "looks": None}]}


@pytest.fixture
def engine(live_db_url, monkeypatch):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    from genios_engine.reason import brief_patterns

    monkeypatch.setattr(brief_patterns, "patterns_for", lambda c, org, *, now: PATTERNS)
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = any(:o)"), {"o": list(ORGS)})
        for org, company in zip(ORGS, ("Alpha Labs", "Beta Labs", "Gamma Labs")):
            c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', :c)"),
                      {"o": org, "c": company})
        for org in ORGS[:2]:
            store.add(c, org_id=org, section="goals", words="raise the pre-seed round",
                      decided_by="founder", at=NOW - timedelta(days=9))
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = any(:o)"), {"o": list(ORGS)})


class _Model:
    model = "claude-sonnet-5"

    def __init__(self, *, fail_for: str | None = None):
        self.prompts, self.fail_for = [], fail_for

    def call(self, prompt, *, max_tokens=4096, **_kw):
        self.prompts.append(prompt)
        if self.fail_for and self.fail_for in prompt:
            raise RuntimeError("transport down")
        return LLMResult(parsed={"lines": [{"section": "watchlist", "text": "Hub71 — the program",
                                            "address": None, "domain": "hub71.com",
                                            "evidence": ["p1"]}]},
                         raw="", model=self.model, input_tokens=800, output_tokens=60)


def _ours(rows):
    return [r for r in rows if r.org_id in ORGS]


def _reviews(engine):
    with engine.connect() as c:
        return _ours(c.execute(text(
            "select org_id, week_key, outcome, proposed, finished_at from company_brief_reviews "
            " order by org_id")).fetchall())


def test_the_week_key_is_the_iso_week():
    assert week_key(NOW) == "2026-W41"
    assert week_key(datetime(2027, 1, 1, tzinfo=timezone.utc)) == "2026-W53"


def test_each_tenant_with_a_brief_is_reviewed_once_a_week(engine):
    model, costs = _Model(), []
    first = run_company_brief_reviews(engine, now=NOW, llm=model,
                                      cost_sink=lambda **row: costs.append(row))
    assert first["week"] == "2026-W41" and first["failed"] == 0
    assert [(r.org_id, r.outcome, r.proposed) for r in _reviews(engine)] == [
        ("org_s07_review_a", "proposed", 1), ("org_s07_review_b", "proposed", 1)]
    calls = len(model.prompts)
    again = run_company_brief_reviews(engine, now=NOW + timedelta(hours=6), llm=model)
    assert len(model.prompts) == calls and again["already_this_week"] >= 2
    assert {c["purpose"] for c in costs} == {"company_brief_draft"}


def test_the_review_asks_with_the_brief_in_force_and_proposes_as_weekly(engine):
    model = _Model()
    run_company_brief_reviews(engine, now=NOW, llm=model)
    prompt = next(p for p in model.prompts if "raise the pre-seed round" in p)
    assert "Propose only what is missing" in prompt and "COMPANY BRIEF cb-" in prompt
    with engine.connect() as c:
        pending = store.pending(c, "org_s07_review_a")
    assert [(p["section"], p["domain"], p["proposed_by"]) for p in pending] == [
        ("watchlist", "hub71.com", "weekly")]


def test_a_tenant_without_an_accepted_line_is_never_reviewed(engine):
    run_company_brief_reviews(engine, now=NOW, llm=_Model())
    assert "org_s07_review_none" not in {r.org_id for r in _reviews(engine)}


def test_no_model_claims_nothing(engine):
    assert run_company_brief_reviews(engine, now=NOW, llm=None)["skipped"] == "no_model"
    assert _reviews(engine) == []


def test_one_tenants_failure_is_recorded_and_the_rest_go_on(engine):
    out = run_company_brief_reviews(engine, now=NOW, llm=_Model(fail_for="Alpha Labs"))
    assert out["failed"] >= 1
    outcomes = {r.org_id: r.outcome for r in _reviews(engine)}
    assert outcomes == {"org_s07_review_a": "error:RuntimeError", "org_s07_review_b": "proposed"}
    assert all(r.finished_at is not None for r in _reviews(engine))


def test_the_heavy_tick_runs_the_review_in_its_own_block_after_learning():
    from genios_engine.api import routes

    tree = ast.parse(inspect.getsource(routes.run_maintenance_sweep))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", getattr(n.func, "attr", None)) in (
                 "run_learning_sweep", "run_company_brief_reviews")]
    names = [getattr(c.func, "id", getattr(c.func, "attr", None)) for c in calls]
    assert names.count("run_company_brief_reviews") == 1
    review = next(c for c in calls if getattr(c.func, "id", None) == "run_company_brief_reviews")
    learning = next(c for c in calls if getattr(c.func, "id", None) == "run_learning_sweep")
    assert review.lineno > learning.lineno
    kwargs = {k.arg for k in review.keywords}
    assert {"now", "llm", "cost_sink"} <= kwargs
    returned = next(n for n in ast.walk(tree) if isinstance(n, ast.Return)
                    and isinstance(n.value, ast.Dict))
    assert "company_brief_review" in {k.value for k in returned.value.keys
                                      if isinstance(k, ast.Constant)}

"""STEP-07 · an operator drafts a tenant's company brief — patterns, a dry run, then proposals.

    pytest tests/scripts/test_draft_company_brief.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_draft_company_brief.py -q

`scripts/draft_company_brief.py` (tree `yc2_w27_s07 · M25.C3.L-interface.V4.U03`). `--patterns` shows
what the drafter would read and calls no model; the dry run makes the one call and prints every
proposed line with the patterns it rests on, writing nothing; `--apply` writes the lines as proposals
and accepts none. The call is billed either way.
"""
from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genios_engine.context.llm.client import LLMResult

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "draft_company_brief.py"
ORG = "org_s07_draft_script"
US = "arjun@nimbus.test"


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("draft_company_brief", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_target_is_resolved_through_the_guard_with_no_fallback():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_database_url" in called and "get_settings" not in called


def test_the_org_is_required_and_the_modes_exclude_each_other():
    mod = _module()
    with pytest.raises(SystemExit):
        mod.parse_args([])
    with pytest.raises(SystemExit):
        mod.parse_args(["--org", "o", "--patterns", "--apply"])


class _Model:
    model = "claude-sonnet-5"

    def __init__(self):
        self.prompts = []

    def call(self, prompt, *, max_tokens=4096, **_kw):
        self.prompts.append(prompt)
        return LLMResult(parsed={"lines": [
            {"section": "watchlist", "text": "Startup India portal", "domain": "sampark.gov.in",
             "evidence": [_portal_pattern(prompt)]},
            {"section": "people", "text": "Silas at Fund Two", "address": "silas@invented.test",
             "evidence": [_portal_pattern(prompt)]}]},
            raw="", model=self.model, input_tokens=700, output_tokens=90)


def _portal_pattern(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("{") and '"domain": "sampark.gov.in"' in line:
            return json.loads(line)["id"]
    raise AssertionError("the portal's domain pattern is not in the prompt")


@pytest.fixture
def tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    engine = get_engine(url)

    def clean(c):
        c.execute(text("delete from llm_costs where org_id = :o"), {"o": ORG})
        c.execute(text("delete from source_events where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})

    with engine.begin() as c:
        clean(c)
        c.execute(text("insert into orgs (id, name, company, email) "
                       "values (:o, 'Arjun Rao', 'Nimbus Labs', :e)"), {"o": ORG, "e": US})
        for n in range(2):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                " source_object_id, dedup_key, actor, occurred_at, captured_at, sync_mode, "
                " schema_version, outcome, recipients, attention) values (:e, :o, 'conn_s07d', "
                " 'gmail', 'email_message', :k, :d, cast(:a as jsonb), :t, :t, 'backfill', 3, "
                " 'archived', :r, 'archive')"),
                {"e": f"evt_{ORG}_{n}", "o": ORG, "k": f"k{n}", "d": f"gmail:email_message:{ORG}:{n}",
                 "a": json.dumps({"email": "notice@sampark.gov.in"}), "r": [US],
                 "t": datetime.now(timezone.utc) - timedelta(days=3 + n)})
    yield url, engine
    with engine.begin() as c:
        clean(c)


def _state(engine):
    from sqlalchemy import text

    from genios_engine.platform import company_brief_store as store
    with engine.connect() as c:
        costs = c.execute(text("select purpose, success from llm_costs where org_id = :o"),
                          {"o": ORG}).fetchall()
        return store.pending(c, ORG), store.accepted(c, ORG), [tuple(r) for r in costs]


def test_patterns_mode_prints_what_the_drafter_reads_and_calls_no_model(tenant, capsys):
    url, engine = tenant
    model = _Model()
    assert _module().main(["--org", ORG, "--database-url", url, "--patterns"], llm=model) == 0
    out = capsys.readouterr().out
    assert '"domain": "sampark.gov.in"' in out and "company Nimbus Labs" in out
    assert model.prompts == [] and _state(engine) == ([], [], [])


def test_the_dry_run_prints_each_line_with_what_it_rests_on_and_writes_none(tenant, capsys):
    url, engine = tenant
    assert _module().main(["--org", ORG, "--database-url", url], llm=_Model()) == 0
    out = capsys.readouterr().out
    assert "[watchlist] Startup India portal <sampark.gov.in>" in out
    assert "rests on p" in out and '"looks": "government"' in out
    assert "address silas@invented.test is not in the patterns" in out
    assert "a dry run, nothing written" in out
    pending, accepted, costs = _state(engine)
    assert pending == [] and accepted == [] and costs == [("company_brief_draft", True)]


def test_apply_writes_proposals_and_accepts_nothing(tenant, capsys):
    url, engine = tenant
    assert _module().main(["--org", ORG, "--database-url", url, "--apply"], llm=_Model()) == 0
    assert "1 written as proposals" in capsys.readouterr().out
    pending, accepted, _ = _state(engine)
    assert [(p["section"], p["domain"], p["proposed_by"]) for p in pending] == [
        ("watchlist", "sampark.gov.in", "drafter")]
    assert pending[0]["evidence"][0]["domain"] == "sampark.gov.in" and accepted == []

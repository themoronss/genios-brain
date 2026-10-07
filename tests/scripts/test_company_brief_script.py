"""STEP-07 · an operator reads and decides a tenant's company brief, on the founder's word.

    pytest tests/scripts/test_company_brief_script.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_company_brief_script.py -q

`scripts/company_brief.py` (tree `yc2_w27_s07 · M25.C2.L-interface.V2.U02`). Until the dashboard has
the confirm screen, Harsh shows Rohit the proposals (`show`) and applies what Rohit says — accept (as
written or in his words), reject, remove, add — through the same writer the screen's routes use.
Accepting a watchlist domain promotes what the gate archived from it, as the screen does; `show`
prints the patterns a proposal rests on and never a message.
"""
from __future__ import annotations

import ast
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "company_brief.py"
WORDS = "Your DPIIT application has moved to the next stage"


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("company_brief_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_target_is_resolved_through_the_guard_with_no_fallback():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_database_url" in called and "get_settings" not in called


@pytest.mark.parametrize("argv, why", [
    (["--org", "o", "add", "goals"], "add takes SECTION and TEXT"),
    (["--org", "o", "accept"], "accept takes one or more line ids"),
    (["--org", "o", "reject", "cbl_1", "--text", "x"], "ONE line being accepted"),
    (["--org", "o", "accept", "cbl_1", "cbl_2", "--text", "x"], "ONE line being accepted"),
])
def test_an_ambiguous_command_is_refused_before_any_database(argv, why):
    with pytest.raises(SystemExit, match=why):
        _module().main(argv)                                   # no --database-url given


@pytest.fixture
def tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text

    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt

    org = f"org_s07_brief_cli_{uuid.uuid4().hex[:8]}"
    eng = create_engine(url)
    at = datetime.now(timezone.utc) - timedelta(days=2)
    event = f"evt_{uuid.uuid4().hex[:12]}"
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', 'Nimbus Labs')"),
                  {"o": org})
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, attention, "
            " attention_reason) values (:e, :o, 'con_x', 'gmail', 'email_message', :e, :dk, "
            " cast(:a as jsonb), :at, :at, 'archived', 'archive', 'N-03')"),
            {"e": event, "o": org, "at": at, "dk": f"gmail:email_message:{event}",
             "a": json.dumps({"email": "noreply@sampark.gov.in"})})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event}", "o": org, "e": event,
             "enc": encrypt(json.dumps({"subject": "DPIIT", "body": WORDS}), get_settings().crypto_key),
             "exp": at + timedelta(days=180)})
        watch = store.propose(c, org_id=org, section="watchlist", words="Startup India portal",
                              domain="sampark.gov.in", proposed_by="drafter", at=at,
                              evidence=[{"pattern": "p2", "kind": "domain", "domain": "sampark.gov.in",
                                         "mail": 1, "archived": 1}])
        goal = store.propose(c, org_id=org, section="goals", words="raise the pre-seed round",
                             proposed_by="drafter", at=at)
    yield url, eng, org, event, watch, goal
    with eng.begin() as c:
        for table in ("raw_payloads", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _outcome(eng, org, event):
    from sqlalchemy import text
    with eng.connect() as c:
        return c.execute(text("select outcome from source_events where org_id = :o and event_id = :e"),
                         {"o": org, "e": event}).scalar_one()


@pytest.mark.pg
def test_show_lists_the_proposals_with_what_they_rest_on_and_no_message(tenant, capsys):
    url, eng, org, event, watch, goal = tenant
    assert _module().main(["--org", org, "--database-url", url, "show"]) == 0
    out = capsys.readouterr().out
    assert "none yet — no line is accepted" in out
    assert f"{watch}  [watchlist] Startup India portal <sampark.gov.in>   — proposed by drafter" in out
    assert '"archived": 1' in out and WORDS not in out and goal in out


@pytest.mark.pg
def test_accepting_a_watchlist_domain_promotes_its_archive_and_the_brief_is_in_force(tenant, capsys):
    url, eng, org, event, watch, goal = tenant
    mod = _module()
    assert mod.main(["--org", org, "--database-url", url, "--by", "rohit", "accept", watch]) == 0
    assert f"accepted {watch}; promoted 1 archived mail(s)" in capsys.readouterr().out
    assert _outcome(eng, org, event) == "emitted"
    assert mod.main(["--org", org, "--database-url", url, "accept", goal,
                     "--text", "Raise the pre-seed round by December"]) == 0
    capsys.readouterr()
    assert mod.main(["--org", org, "--database-url", url, "show"]) == 0
    out = capsys.readouterr().out
    assert "COMPANY BRIEF cb-" in out and "Raise the pre-seed round by December" in out
    assert "proposals waiting for the founder (0)" in out


@pytest.mark.pg
def test_reject_remove_and_add_go_through_the_one_writer(tenant, capsys):
    url, eng, org, event, watch, goal = tenant
    mod = _module()
    assert mod.main(["--org", org, "--database-url", url, "reject", goal]) == 0
    assert mod.main(["--org", org, "--database-url", url, "add", "connectors",
                     "Introly introduces the founder to investors",
                     "--address", "hello@introly.test"]) == 0
    added = capsys.readouterr().out.splitlines()[-1].split()[1]
    assert mod.main(["--org", org, "--database-url", url, "remove", added]) == 0
    from genios_engine.platform import company_brief_store as store
    with eng.connect() as c:
        assert store.accepted(c, org) == [] and [p["line_id"] for p in store.pending(c, org)] == [watch]
    assert mod.main(["--org", org, "--database-url", url, "remove", goal]) == 1
    assert f"refused {goal}" in capsys.readouterr().out

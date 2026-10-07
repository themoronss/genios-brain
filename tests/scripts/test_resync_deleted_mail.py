"""STEP-08 · the operator brings back one tenant's deleted Gmail mail — a dry run first, then apply, then finish.

    pytest tests/scripts/test_resync_deleted_mail.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_resync_deleted_mail.py -q

`scripts/resync_deleted_mail.py` (tree `yc2_w27_s08 · M26.C3.L-interface.V1.U01`). Harsh runs it on
Rohit's window (D5 / D16): the dry run counts the deleted messages by the rule that deleted them, by
month and by sender domain, names the oldest and the window that reaches it, and what a given window
leaves out — never a subject or a body; `--apply --days N` frees their keys; `--finish`, after the
backfill drain, supersedes what came back and says why the rest did not.
"""
from __future__ import annotations

import ast
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "resync_deleted_mail.py"
WORDS = "Pankaj, meet Meera"
NOW = datetime.now(timezone.utc)


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("resync_deleted_mail", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── the command line, before any database ───────────────────────────────────────────────────────

def test_the_target_is_resolved_through_the_guard_with_no_fallback():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "resolve_database_url" in called and "get_settings" not in called


def test_the_org_is_required_and_apply_needs_rohits_window():
    mod = _module()
    with pytest.raises(SystemExit):
        mod.parse_args([])
    with pytest.raises(SystemExit):
        mod.parse_args(["--org", "o", "--apply"])                  # the window is never a default
    with pytest.raises(SystemExit):
        mod.parse_args(["--org", "o", "--apply", "--finish", "--days", "365"])
    with pytest.raises(SystemExit):
        mod.parse_args(["--org", "o", "--days", "0"])
    args = mod.parse_args(["--org", "o", "--apply", "--days", "365"])
    assert (args.apply, args.finish, args.days) == (True, False, 365)


def test_no_target_no_run():
    from scripts._db import UnsafeDatabaseTarget
    os.environ.pop("GENIOS_TARGET_DATABASE_URL", None)
    with pytest.raises(UnsafeDatabaseTarget):
        _module().main(["--org", "o"])


# ── on a real ledger ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from sqlalchemy import create_engine, text
    org = f"org_resync_cli_{uuid.uuid4().hex[:8]}"
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'resync cli')"), {"o": org})
        c.execute(text(
            "insert into connections (connection_id, org_id, source_type, status, capture_scope) "
            "values (:c, :o, 'gmail', 'connected', cast('{\"backfill_days\": 60}' as jsonb))"),
            {"c": f"con_{org}", "o": org})
    yield engine, org, url
    with engine.begin() as c:
        for table in ("event_trace", "raw_payloads", "source_events", "connections"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _row(engine, org, mid, *, sender="hello@boardy.ai", days=10, outcome="dropped", code="N-02",
         stage="S1", object_type="email_message", parent=None, body=False, key=None):
    from sqlalchemy import text

    from genios_engine.contracts.source_event import compute_dedup_key
    from genios_engine.platform.config import get_settings
    from genios_engine.platform.crypto import encrypt
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    at = NOW - timedelta(days=days)
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, parent_object_id, dedup_key, actor, occurred_at, captured_at, "
            " outcome) values (:e, :o, 'con_x', 'gmail', :ot, :mid, :parent, :dk, "
            " cast(:actor as jsonb), :at, :at, :out)"),
            {"e": event_id, "o": org, "ot": object_type, "mid": mid, "parent": parent,
             "dk": key or compute_dedup_key("gmail", object_type, mid),
             "actor": json.dumps({"type": "external_contact", "email": sender}), "at": at,
             "out": outcome})
        if code:
            action = {"dropped": "drop", "archived": "archive"}.get(outcome, "pass")
            c.execute(text("insert into event_trace (org_id, event_id, stage, action, reason_code) "
                           "values (:o, :e, :s, :a, :r)"),
                      {"o": org, "e": event_id, "s": stage, "a": action, "r": code})
        if body:
            c.execute(text(
                "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                " expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
                {"id": f"pay_{event_id}", "o": org, "e": event_id,
                 "enc": encrypt(json.dumps({"subject": "Intro", "body": WORDS}),
                                get_settings().crypto_key),
                 "exp": NOW + timedelta(days=60)})
    return event_id


@pytest.fixture
def mailbox(tenant):
    """Six deleted messages over four months, and what must never be counted as one."""
    engine, org, url = tenant
    ids = {
        "boardy1": _row(engine, org, "b1", days=10),
        "boardy2": _row(engine, org, "b2", days=40),
        "portal": _row(engine, org, "p1", sender="no-reply@startupsetu.gov.in", days=20,
                       code="N-03"),
        "junk": _row(engine, org, "j1", sender="deals@letters.test", days=70, code="llm_junk",
                     stage="S2"),
        "oldest": _row(engine, org, "o1", sender="news@sine.test", days=99.9, code="N-06"),
        "with_files": _row(engine, org, "f1", sender="cfo@kite.test", days=15, code="N-06"),
    }
    # never a deleted message the re-sync can take
    _row(engine, org, "s1", code="out_of_scope", stage="S0")
    _row(engine, org, "k1", code="llm_junk", stage="S2", body=True, days=5)   # it kept its body
    _row(engine, org, "a1", outcome="archived", body=True)
    # attachments: one deleted with its message, one that survived it
    _row(engine, org, "f1::att1", object_type="email_attachment", parent="f1", code="N-06")
    _row(engine, org, "f1::att2", object_type="email_attachment", parent="f1", outcome="emitted",
         code=None, body=True)
    return engine, org, url, ids


def _keys(engine, org):
    from sqlalchemy import text
    with engine.connect() as c:
        return {r.event_id: (r.outcome, r.dedup_key) for r in c.execute(
            text("select event_id, outcome, dedup_key from source_events where org_id = :o"),
            {"o": org})}


def _run(capsys, url, *argv) -> str:
    assert _module().main(["--database-url", url, *argv]) == 0
    return capsys.readouterr().out


def test_the_dry_run_counts_by_rule_month_and_domain_and_writes_nothing(mailbox, capsys):
    engine, org, url, ids = mailbox
    before = _keys(engine, org)
    out = _run(capsys, url, "--org", org)
    assert f"{org}: 6 Gmail message(s) the old gate deleted" in out
    assert "by rule:   N-02 2 · N-06 2 · N-03 1 · llm_junk 1" in out
    assert "boardy.ai 2" in out and "startupsetu.gov.in 1" in out
    oldest = (NOW - timedelta(days=99.9)).date().isoformat()
    assert f"oldest {oldest} — a window of 100 days reaches every one" in out
    assert "the Gmail connection's window today: 60 days" in out
    assert "1 deleted with their message" in out and "1 survived it" in out
    assert "1 message(s) with both" in out
    assert "nothing freed yet" in out and "DRY RUN — nothing written" in out
    assert WORDS not in out and "Intro" not in out, "a mail's words never leave the ledger"
    assert _keys(engine, org) == before


def test_a_window_says_what_it_reaches_and_what_it_leaves_out(mailbox, capsys):
    engine, org, url, ids = mailbox
    out = _run(capsys, url, "--org", org, "--days", "60")
    oldest = (NOW - timedelta(days=99.9)).date().isoformat()
    assert f"--days 60 reaches 4 and leaves out 2, the oldest {oldest}" in out
    out = _run(capsys, url, "--org", org, "--days", "365")
    assert "--days 365 reaches 6 and leaves out 0" in out
    assert "PATCH /connections/{gmail}/backfill-window to 365 before the drain" in out


def test_apply_frees_exactly_what_the_dry_run_said_the_window_reaches(mailbox, capsys):
    engine, org, url, ids = mailbox
    out = _run(capsys, url, "--org", org, "--apply", "--days", "60")
    assert "FREED 4 deleted Gmail message(s) from the last 60 days" in out
    keys = _keys(engine, org)
    freed = {e for e, (outcome, key) in keys.items() if "#resync:" in key}
    assert freed == {ids[k] for k in ("boardy1", "boardy2", "portal", "with_files")}
    assert all(keys[e][0] == "dropped" for e in freed)
    out = _run(capsys, url, "--org", org, "--apply", "--days", "60")
    assert "FREED 0" in out
    out = _run(capsys, url, "--org", org)
    assert "2 Gmail message(s) the old gate deleted" in out
    assert "freed, waiting for the drain 4" in out


def test_apply_warns_when_the_connection_will_not_list_that_far_back(mailbox, capsys):
    engine, org, url, ids = mailbox
    out = _run(capsys, url, "--org", org, "--apply", "--days", "365")
    assert "FREED 6" in out and "PATCH /connections/{gmail}/backfill-window to 365 first" in out


def test_finish_supersedes_what_came_back_and_reports_the_rest(mailbox, capsys):
    from genios_engine.contracts.source_event import compute_dedup_key
    engine, org, url, ids = mailbox
    _run(capsys, url, "--org", org, "--apply", "--days", "365")
    # the drain lands two of them again, under their own keys
    _row(engine, org, "b1", outcome="archived", body=True,
         key=compute_dedup_key("gmail", "email_message", "b1"))
    _row(engine, org, "p1", outcome="emitted", body=True, code=None,
         key=compute_dedup_key("gmail", "email_message", "p1"))
    out = _run(capsys, url, "--org", org, "--finish")
    assert "FINISHED: 2 came back and were superseded; 4 freed message(s) not listed" in out
    assert "(2 older than the connection's 60-day window" in out
    assert "4 reason(s) written now" in out
    keys = _keys(engine, org)
    assert keys[ids["boardy1"]][0] == keys[ids["portal"]][0] == "superseded"
    out = _run(capsys, url, "--org", org, "--finish")
    assert "FINISHED: 0 came back" in out and "0 reason(s) written now" in out
    out = _run(capsys, url, "--org", org)
    assert "came back 2 · not listed 4" in out

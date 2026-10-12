"""STEP-18 S18-X07 · `scripts/gmail_l1.py` deletes the fingerprints and the events in ONE transaction.

    GENIOS_TEST_DATABASE_URL=… pytest tests/scripts/test_the_gmail_wipe_is_one_transaction.py -q

`yc2_w27_s18` M48.C3.L-data.V1.U17 (L1 Signals, `capture/`, and its scripts).

⛔ WHAT WAS WRONG. B20's second half (M48.C3.L-data.V0.U11) put the fingerprint delete before the
event delete — but each statement ran in its own `with eng.begin()` and a failure printed `skip:`
and went on. A fingerprint delete that failed (a lock, a timeout, a database without 0144) still
let the events go, and a claim by an event with no row is honoured
(`capture/screen/fingerprint._without_set_aside_claims`), so the re-sync then skipped every message
as `seen_on_screen` — B20 again, by another road. The disconnect does both deletes in one
transaction (`api/routes.integration_disconnect`); now the script does too, and stops on a failure
before anything is re-synced.

The script is imported only after its top level is shown, from the AST, to run nothing — importing
it used to run the wipe.
"""
from __future__ import annotations

import ast
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gmail_l1.py"
ORG = "org_s18_gmail_wipe"
AT = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def test_importing_the_script_runs_nothing():
    """Its top level is imports, constants, functions and the `__main__` guard — nothing that
    reaches a database when a test (or anyone) imports it."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    loose = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue                                              # the docstring
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, (
                ast.Constant, ast.Tuple)) and all(isinstance(e, ast.Constant) for e in ast.walk(
                    node.value) if isinstance(e, ast.expr) and not isinstance(e, ast.Tuple)):
            continue                                              # a constant
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"):
            continue
        loose.append(f"line {node.lineno}: {ast.dump(node)[:80]}")
    assert not loose, loose


def _script():
    test_importing_the_script_runs_nothing()
    return importlib.import_module("scripts.gmail_l1")


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the wipe is Postgres's")
    from genios_engine.platform.db import get_engine

    eng = get_engine(live_db_url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
        for event, source in (("e_gmail", "gmail"), ("e_outlook", "outlook")):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at) values (:e, :o, 'conn', :s, "
                "'email_message', :e, :e, cast(:a as jsonb), :at)"),
                {"e": event, "o": ORG, "s": source, "a": json.dumps({"email": "p@acme.test"}),
                 "at": AT})
            c.execute(text("insert into message_fingerprints (org_id, fp, source, event_id) "
                           "values (:o, :fp, :s, :e)"), {"o": ORG, "fp": "fp_" + event, "s": source,
                                                         "e": event})
        c.execute(text("insert into sync_cursors (id, org_id, connection_id, source) values "
                       "('cur_s18', :o, 'conn', 'gmail')"), {"o": ORG})
        # Deleted BEFORE the fingerprints (`WIPE`'s order): the row that shows a wipe split into
        # transactions — it would be gone while the events stayed.
        c.execute(text("insert into event_trace (org_id, event_id, source, stage, action) values "
                       "(:o, 'e_gmail', 'gmail', 'gate', 'pass')"), {"o": ORG})
    yield eng
    _reset(eng)


def _reset(engine) -> None:
    with engine.begin() as c:
        for table in ("event_trace", "message_fingerprints", "sync_cursors", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _left(engine) -> dict[str, list[str]]:
    with engine.connect() as c:
        return {
            "events": sorted(r[0] for r in c.execute(text(
                "select event_id from source_events where org_id = :o"), {"o": ORG})),
            "prints": sorted(r[0] for r in c.execute(text(
                "select event_id from message_fingerprints where org_id = :o"), {"o": ORG})),
            "cursors": sorted(r[0] for r in c.execute(text(
                "select source from sync_cursors where org_id = :o"), {"o": ORG})),
            "trace": sorted(r[0] for r in c.execute(text(
                "select event_id from event_trace where org_id = :o"), {"o": ORG}))}


def _without_0144(script) -> tuple[str, ...]:
    """The script's own wipe, on a database where the fingerprint delete fails."""
    (prints,) = [s for s in script.WIPE if s.startswith("delete from message_fingerprints")]
    return tuple(s.replace("delete from message_fingerprints",
                           "delete from message_fingerprints_not_migrated") if s == prints else s
                 for s in script.WIPE)


def test_the_wipe_takes_the_gmail_events_and_their_fingerprints_and_nothing_else(engine):
    _script().clear_gmail(engine, ORG)
    assert _left(engine) == {"events": ["e_outlook"], "prints": ["e_outlook"], "cursors": [],
                             "trace": []}


def test_a_failed_fingerprint_delete_deletes_nothing(engine, monkeypatch):
    script = _script()
    monkeypatch.setattr(script, "WIPE", _without_0144(script))
    with pytest.raises(Exception):
        script.clear_gmail(engine, ORG)
    assert _left(engine) == {"events": ["e_gmail", "e_outlook"], "prints": ["e_gmail", "e_outlook"],
                             "cursors": ["gmail"], "trace": ["e_gmail"]}, (
        "the events went and their fingerprints stayed: the re-sync would skip every message")


def test_a_failed_wipe_stops_the_script_before_the_resync(engine, monkeypatch, capsys):
    script = _script()
    resynced: list[str] = []
    monkeypatch.setattr("genios_engine.platform.wiring.make_graph_store",
                        lambda: type("S", (), {"engine": engine})())
    monkeypatch.setattr(script, "_resync", lambda eng, org: resynced.append(org))
    monkeypatch.setattr(script, "WIPE", _without_0144(script))
    assert script.main(["gmail_l1.py", ORG]) == 1
    assert resynced == [] and "nothing deleted, nothing re-synced" in capsys.readouterr().err
    monkeypatch.undo()
    monkeypatch.setattr("genios_engine.platform.wiring.make_graph_store",
                        lambda: type("S", (), {"engine": engine})())
    monkeypatch.setattr(script, "_resync", lambda eng, org: resynced.append(org))
    assert script.main(["gmail_l1.py", ORG]) == 0 and resynced == [ORG]
    assert _left(engine)["events"] == ["e_outlook"]

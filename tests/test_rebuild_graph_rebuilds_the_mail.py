"""STEP-18 B12 · `scripts/rebuild_graph.py` rebuilds the mail, not only the calendar.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_rebuild_graph_rebuilds_the_mail.py -q

`yc2_w27_s18` M48.C2.L-integration.V1.U05 (L3 Context Graph, `context/`, and its operator script).

⛔ WHAT WAS WRONG. The script replays the ledger through the drain's own `_safe_process_one`, but
pulled its rows with a query of its own (`_pull_all`): `outcome = 'emitted'` only, and no cached
extraction, prepared text, recipients or thread. Every mail that had reached memory through a signal
arrived with `qes_output` missing and was held `held_missing_qes_extraction` — the rebuild restored
the calendar and none of the mail — and the archived and below-floor roads were never replayed.

It now replays `context/runner._rows_for_rebuild`, the drain's columns over the drain's roads.

`yc2_w27_s18` M48.C2.L-integration.V2.U16 (S18-X06): with the archived road in its rows, the
script's estimate — every unstructured row not cache-linked "may cost LLM" — counted every archived
mail, which takes the metadata road with no extraction and no model, and `--apply` refused unless
`--allow-llm`: an operator was pushed to permit spending on a run that spends nothing. No road calls
a model (`context/runner._process_one`), so the estimate, the refusal and the flag are gone. The dry
run is driven through `main()` here.
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import encrypt

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rebuild_graph.py"
ORG = "org_s18_rebuild_mail"
NOW = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
PRIYA = "priya@acme-logistics.test"
FIXTURE = json.loads((Path(__file__).resolve().parent / "context" / "fixtures"
                      / "screen_decline_extraction.json").read_text())


# ── the script reads through the drain's road, and holds no pull of its own ───────────────────

def _tree():
    return ast.parse(SCRIPT.read_text(encoding="utf-8"))


def test_the_script_holds_no_select_of_the_event_ledger_of_its_own():
    own = [node.value for node in ast.walk(_tree())
           if isinstance(node, ast.Constant) and isinstance(node.value, str)
           and "from source_events" in " ".join(node.value.lower().split())]
    assert own == [], "the rebuild pulls its rows through `context/runner._rows_for_rebuild`"


def test_the_script_replays_the_drains_rows():
    names = {alias.name for node in ast.walk(_tree()) if isinstance(node, ast.ImportFrom)
             and node.module == "genios_engine.context.runner" for alias in node.names}
    assert {"_rows_for_rebuild", "_safe_process_one"} <= names, names


# ── and on Postgres, a mail that had reached memory is rebuilt into it ────────────────────────

@pytest.fixture
def store(pg_store):
    _reset(pg_store)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, 'Rebuild', :e)"),
                  {"o": ORG, "e": "founder.rebuild@gmail.com"})
    yield pg_store
    _reset(pg_store)


def _reset(store) -> None:
    from genios_engine.api.account_routes import _wipe

    with store.engine.begin() as c:
        _wipe(c, ORG)
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _seed_a_mail_memory_holds(store) -> None:
    """A mail that crossed the floor: its event, payload, prepared text, cached extraction and
    active signal — and the run that says memory already holds it."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, recipients, occurred_at, outcome, "
            "parent_object_id) values ('e_mail', :o, 'conn_rb', 'gmail', 'email_message', "
            "'m_1', 'm_1', cast(:a as jsonb), :r, :at, 'emitted', 'thread_1')"),
            {"o": ORG, "a": json.dumps({"type": "external_contact", "email": PRIYA,
                                        "name": "Priya Shah"}),
             "r": ["founder.rebuild@gmail.com"], "at": NOW - timedelta(days=1)})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values ('pay_mail', :o, 'e_mail', 'application/json', :enc, :exp)"),
            {"o": ORG, "enc": encrypt(json.dumps({"subject": "Update", "body": FIXTURE["clean_text"],
                                                  "labelIds": ["INBOX"]}),
                                      get_settings().crypto_key),
             "exp": NOW + timedelta(days=180)})
        c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, "
                       "clean_text) values ('e_mail', :o, 'pc_mail', :t)"),
                  {"o": ORG, "t": FIXTURE["clean_text"]})
        c.execute(text(
            "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
            "profile_id, tier) values ('x_mail', :o, 'e_mail', cast(:out as jsonb), 'email', 'T2')"),
            {"o": ORG, "out": json.dumps(FIXTURE["output"])})
        c.execute(text(
            "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
            "importance_bp, importance_version, confidence_bp, visibility, extraction_ref, "
            "evidence_refs, state, occurred_at) values ('sig_mail', :o, 'e_mail', 'tr_mail', "
            "'approval_requested', 6000, 'alg17-v1', 8000, cast('{\"scope\": \"org\"}' as jsonb), "
            "'x_mail', cast('[\"ev\"]' as jsonb), 'active', :at)"), {"o": ORG, "at": NOW})
        c.execute(text("insert into l2_processing_runs (org_id, event_id, status, attempts) "
                       "values (:o, 'e_mail', 'done', 1)"), {"o": ORG})


def _people(store) -> set[str]:
    with store.engine.connect() as c:
        return {r[0] for r in c.execute(text(
            "select canonical_key from graph_nodes where org_id = :o and node_type = 'person' "
            "and valid_to is null"), {"o": ORG})}


def test_a_rebuild_replays_a_mail_memory_held_and_files_it_again(store):
    from scripts import rebuild_graph as RB

    _seed_a_mail_memory_holds(store)
    rows = RB._rows(store, ORG)
    assert [r.event_id for r in rows] == ["e_mail"]
    assert rows[0].qes_output is not None, "the replayed row carries its cached extraction"
    outcomes = RB._replay(rows, org=ORG, store=store, llm=None, crypto_key=get_settings().crypto_key,
                          workers=1)
    assert "held_missing_qes_extraction" not in outcomes, outcomes
    assert PRIYA in _people(store), "the sender of a rebuilt mail is in memory again"



def _seed_an_archived_mail(store) -> None:
    """A mail the gate archived: kept, read by no model, no extraction — the metadata road."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, recipients, occurred_at, outcome) values "
            "('e_archived', :o, 'conn_rb', 'gmail', 'email_message', 'm_2', 'm_2', cast(:a as jsonb), "
            ":r, :at, 'archived')"),
            {"o": ORG, "a": json.dumps({"type": "external_contact", "email": PRIYA,
                                        "name": "Priya Shah"}),
             "r": ["founder.rebuild@gmail.com"], "at": NOW - timedelta(days=2)})
        # and a calendar event — the structured road, no model either
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, outcome) values ('e_meeting', :o, "
            "'conn_cal', 'gcal', 'calendar_event', 'ev_1', 'ev_1', cast('{}' as jsonb), :at, "
            "'emitted')"), {"o": ORG, "at": NOW - timedelta(days=3)})


def _graph_rows(store) -> int:
    with store.engine.connect() as c:
        return c.execute(text("select (select count(*) from graph_nodes where org_id = :o) + "
                              "(select count(*) from graph_edges where org_id = :o)"),
                         {"o": ORG}).scalar()


def test_a_dry_run_of_main_names_the_archived_road_and_estimates_no_model(store, monkeypatch,
                                                                            capsys):
    """S18-X06: `main()` itself, dry, on a tenant with an archived mail, a mail memory holds and a
    calendar event."""
    from scripts import rebuild_graph as RB

    _seed_a_mail_memory_holds(store)
    _seed_an_archived_mail(store)
    monkeypatch.setattr(RB, "make_graph_store", lambda: store)
    monkeypatch.setattr(RB, "_bounded_engine", lambda url, pool: store.engine)
    before = _graph_rows(store)
    RB.main(["--org", ORG])
    out = capsys.readouterr().out
    assert "kept events with a road: 3 (structured=1, unstructured=2)" in out, out
    assert "LLM" not in out and "may cost" not in out, out
    assert "no road calls a model" in out and "DRY RUN" in out, out
    assert _graph_rows(store) == before, "a dry run writes nothing"


def test_the_script_has_no_model_flag_and_no_refusal():
    """No road calls a model: the script builds no model client, offers no `--allow-llm`, and has
    no refusal to wipe that a flag would lift."""
    from scripts import rebuild_graph as RB

    with pytest.raises(SystemExit):
        RB.main(["--org", ORG, "--allow-llm"])
    source = SCRIPT.read_text(encoding="utf-8")
    assert "make_llm_client" not in source and "REFUSING" not in source

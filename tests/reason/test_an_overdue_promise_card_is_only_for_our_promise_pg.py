"""G012 H-03 · `commitment_overdue` ("you owe this") fires on OUR promises, never on a counterparty's.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_an_overdue_promise_card_is_only_for_our_promise_pg.py -q

On the design partner's org, 23 Oct 2026, 7 of 7 overdue-promise cards were someone else's promise — a vendor's
delivery written as "You committed to…" — and 79 of the 81 dated promises in memory are theirs. The rule read only
`commitment.due_at`. It now also reads `commitment.ours`, which the runner computes once a pass by the morning
brief's definition (`context/promises_due`): the owner's address, else the node that `owns` it, else the sender of
the mail it was made in. The world: three promises, all two days past due, written the way `context/pipeline` writes
one — ours (an `owns` edge from our address), theirs (an `owns` edge from a vendor), and one with no owner at all,
made in a mail we sent.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason import runner

pytestmark = pytest.mark.pg

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
ORG = "g012h03_promises"
US, VENDOR = "founder@nimbus.test", "antonio@vendor.test"
OURS, THEIRS, SENT = "g012h03_c_ours", "g012h03_c_theirs", "g012h03_c_sent"


def _seed_org(conn) -> None:
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns where table_name='orgs' "
        "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
    cols, ph, vals = ["id"], [":id"], {"id": ORG}
    for r in reqd:
        cols.append(r.column_name)
        ph.append(f":{r.column_name}")
        dt = r.data_type
        vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                               else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                               else US if "email" in r.column_name else ORG)
    conn.execute(text(f"insert into orgs ({','.join(cols)}) values ({','.join(ph)}) on conflict do nothing"), vals)
    conn.execute(text("update orgs set email = :e where id = :o"), {"e": US, "o": ORG})


def _promise(conn, node: str, words: str, *, maker: str | None, event: str, sender: str) -> None:
    conn.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
        "dedup_key, actor, occurred_at, recipients) values (:e, :o, 'con_h03', 'gmail', 'email_message', :e, :e, "
        "cast(:a as jsonb), :at, '{}')"),
        {"e": event, "o": ORG, "a": json.dumps({"email": sender}), "at": NOW - timedelta(days=9)})
    conn.execute(text("insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
                      "values (:n, :o, 'commitment', :w, :k)"), {"n": node, "o": ORG, "w": words, "k": f"commitment:{node}"})
    for i, (field, value) in enumerate((("commitment.due_at", (NOW - timedelta(days=2)).isoformat()),
                                        ("commitment.text", words), ("commitment.status", "open"))):
        conn.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, value_type, "
            "status, occurred_at, created_by_event_id) values (:fv, :f, :o, :n, :field, cast(:v as jsonb), 'string', "
            "'active', :t, :e)"),
            {"fv": f"{node}_fv{i}", "f": f"{node}_f{i}", "o": ORG, "n": node, "field": field,
             "v": json.dumps(value), "t": NOW - timedelta(days=9), "e": event})
    if maker:
        conn.execute(text(
            "insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, to_node_id, "
            "created_by_event_id) values (:ev, :ei, :o, 'owns', :m, :n, :e)"),
            {"ev": f"{node}_ev", "ei": f"{node}_ei", "o": ORG, "m": maker, "n": node, "e": event})


@pytest.fixture
def world(pg_store):
    from genios_engine.api.account_routes import _wipe
    from genios_engine.packs.wiring import ensure_defaults, make_registry

    with pg_store.engine.begin() as conn:
        _seed_org(conn)
        _wipe(conn, ORG)
        for t in ("signals", "reasoning_publication_watermarks", "signal_suppression_log", "source_events"):
            conn.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) values "
            "('g012h03_us', :o, 'person', 'Founder', :us), ('g012h03_vendor', :o, 'person', 'Antonio', :v)"),
            {"o": ORG, "us": US, "v": VENDOR})
        _promise(conn, OURS, "send Antonio the signed order", maker="g012h03_us", event="evt_h03_ours", sender=US)
        _promise(conn, THEIRS, "ship the replacement unit", maker="g012h03_vendor", event="evt_h03_theirs",
                 sender=VENDOR)
        _promise(conn, SENT, "share the revised quote", maker=None, event="evt_h03_sent", sender=US)
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)
    try:
        yield pg_store, registry
    finally:
        with pg_store.engine.begin() as conn:
            _wipe(conn, ORG)
            conn.execute(text("delete from source_events where org_id = :o"), {"o": ORG})


@pytest.fixture
def verdicts(monkeypatch):
    """What the rule concluded on each promise the pass reasoned — `matched` is the conditions' answer, before
    any score or gate (a two-day-old promise with no deal behind it scores below the push band here)."""
    seen: dict[str, bool] = {}
    original = runner.reason_legacy_rule

    def _spy(**kw):
        reasoned = original(**kw)
        if kw["rule"].id == "commitment_overdue":
            seen[kw["context"].node_id] = reasoned.matched
        return reasoned
    monkeypatch.setattr(runner, "reason_legacy_rule", _spy)
    return seen


def test_whose_promise_is_answered_by_the_brief_s_own_definition(world):
    from genios_engine.context.promises_due import ours_by_promise
    store, _registry = world
    with store.engine.connect() as c:
        assert ours_by_promise(c, ORG) == {OURS: True, THEIRS: False, SENT: True}


def test_the_rule_fires_on_our_overdue_promise_and_not_on_a_vendors(world, verdicts):
    store, registry = world
    runner.run(org_id=ORG, store=store, eval_time=NOW, registry=registry, pack_id="general")
    assert verdicts.get(THEIRS) is False, f"a vendor's overdue delivery became 'You committed to…': {verdicts}"
    assert verdicts.get(OURS) is True and verdicts.get(SENT) is True, f"our overdue promises must fire: {verdicts}"

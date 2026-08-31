"""What the seven readings actually WRITE, and who can read it back.

`tests/test_support_situations.py` pins the seven decisions over an in-memory snapshot. This file
pins the other half: the situation rows land, they are idempotent, they close themselves when the
finding stops being true, and — the bug that made the whole mechanism half-invisible — the
`/situations` endpoint can see a situation that did not come from a correlation.

The full sweep needs a real Postgres (`GENIOS_TEST_DATABASE_URL`) because the write path uses
`jsonb` casts and array parameters. The `active_situations` join does not, and it is tested
against sqlite so the regression is caught on a fresh clone with no database at all.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytest.importorskip("sqlalchemy")

from genios_engine.context.domain_spec import domains_declaring, spec_for  # noqa: E402
from genios_engine.context.situations import active_situations  # noqa: E402
from genios_engine.context.support_situations import (  # noqa: E402
    ANCHOR_THREAD,
    READINGS,
    ResponsePolicy,
    gather,
    refresh_support_situations,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


# ── the join that hid every directly-written situation ───────────────────────────────────────

@pytest.fixture()
def lite():
    from sqlalchemy import create_engine
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("""
            create table context_situations (
                situation_id text primary key, org_id text not null,
                correlation_id text not null, anchor_node_id text not null,
                situation_type text not null, domain text not null,
                status text not null default 'active', resolved_by text, resolved_at timestamp,
                resolution_note text,
                confidence_overall int, confidence_evidence int, confidence_freshness int,
                confidence_consistency int, confidence_identity int,
                coverage int, missing text not null default '[]',
                inputs text not null default '{}',
                first_seen_at timestamp, last_seen_at timestamp, computed_at timestamp)"""))
        c.execute(text("""
            create table context_correlations (
                org_id text not null, correlation_id text not null, anchor_node_id text,
                anchor_type text, domain text, generation int, first_event_at timestamp,
                last_event_at timestamp, event_count int)"""))
        c.execute(text("""
            create table graph_nodes (
                node_id text, version int, org_id text, node_type text, canonical_key text,
                display_name text, valid_to timestamp)"""))
    with engine.begin() as c:
        yield c


def test_a_situation_with_no_correlation_row_is_still_visible_to_the_api(lite):
    """The bug: `active_situations` INNER JOINed `context_correlations`, so every situation this
    module and `periodic.py` write — synthetic correlation id, no correlation row, because the
    subject is a computed anchor rather than a group of events — was invisible to `/situations`
    while `reason/domain_shadow.py` compiled them happily. The API and the reasoner disagreed
    about what was live, and nothing errored.
    """
    lite.execute(text(
        "insert into graph_nodes values ('n1', 1, 'o', 'thread', 'thread:t1', 'Thread', null)"))
    lite.execute(text(
        "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
        "situation_type, domain, status, confidence_overall, coverage, missing, inputs) "
        "values ('s1','o','corr_firstreply_o_t1','n1','first_response_overdue','support',"
        "        'active', 70, 40, '[]', '{}')"))
    rows = active_situations(lite, org_id="o")
    assert [r["situation_id"] for r in rows] == ["s1"]
    # 0 is an absence of correlation, not a situation with no evidence — the evidence these rows
    # do have is already priced into confidence_evidence.
    assert rows[0]["event_count"] == 0
    assert rows[0]["anchor_type"] == "thread"


def test_a_correlated_situation_still_carries_its_event_count(lite):
    """Guard the fix: relaxing the join must not silently zero the count for the situations that
    DO come from a correlation, which is most of them."""
    lite.execute(text(
        "insert into graph_nodes values ('n2', 1, 'o', 'person', 'a@b.co', 'A', null)"))
    lite.execute(text(
        "insert into context_correlations values ('o','c2','n2','person','support',1,null,null,9)"))
    lite.execute(text(
        "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
        "situation_type, domain, status, confidence_overall, coverage, missing, inputs) "
        "values ('s2','o','c2','n2','support_contact','support','active',80,50,'[]','{}')"))
    assert active_situations(lite, org_id="o")[0]["event_count"] == 9


# ── the full sweep, against a real Postgres ──────────────────────────────────────────────────

def _us(org: str) -> str:
    """`orgs.email` is UNIQUE, so every test org needs its own address — and the address is also
    what `_internal_emails` reads to decide which messages are ours, so it cannot be a constant
    shared between orgs without one org's reply looking like another's."""
    return f"founder@{org}.io"


def _seed_org(store, org: str) -> None:
    """NOT-NULL columns are discovered rather than listed, so a later migration adding one does
    not turn this into a skip — same shape as `tests/test_period_situations.py`."""
    with store.engine.begin() as c:
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id", "email"], [":id", ":email"], {"id": org, "email": _us(org)}
        for r in reqd:
            if r.column_name in vals:
                continue
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else "{}" if dt in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                       "on conflict (id) do nothing"), vals)


def _seed_connection(c, org: str) -> None:
    """`composio_user_id` is supplied even though the column is nullable, and that is not padding.

    Every production writer sets it (`connections/store.py` binds it on every insert), but the
    pydantic `Connection` model types it `str` — so a row seeded without it loads fine here and
    then raises `ValidationError: composio_user_id Input should be a valid string` in ANY later
    test that enumerates connections off the same session-scoped scratch database. Measured: it
    took `test_reasoning_retention.py::test_scheduled_maintenance_purges_expired_reasoning_context
    _payloads` down whenever this file ran first, in the real-Postgres lane only.
    """
    c.execute(text(
        "insert into connections (connection_id, org_id, external_account_id, composio_user_id, "
        "  status) values (:cid, :o, :addr, :cu, 'connected') on conflict do nothing"),
        {"cid": f"conn_{org}", "o": org, "addr": _us(org), "cu": f"cu_{org}"})


def _seed_unanswered_request(store, org: str) -> None:
    """One inbound message, six days old, never replied to — the simplest of the seven findings,
    and the one that exercises every join in the gather: source_events, prepared_content, the
    thread node and the situation upsert."""
    with store.engine.begin() as c:
        _seed_connection(c, org)
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "  source_object_id, parent_object_id, dedup_key, actor, occurred_at, recipients) "
            "values (:e, :o, :cid, 'gmail', 'message', :soid, :thread, :e, "
            "  cast(:actor as jsonb), :at, cast(:rcpt as text[])) "
            "on conflict do nothing"),
            {"e": f"ev_{org}_1", "o": org, "cid": f"conn_{org}", "soid": f"m_{org}_1",
             "thread": f"th_{org}", "actor": '{"email": "customer@big.co"}',
             "at": NOW - timedelta(days=6), "rcpt": "{" + _us(org) + "}"})
        c.execute(text(
            "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
            "values (:e, :o, :p, 'the nightly export is broken, how do I download the file?') "
            "on conflict (event_id) do nothing"),
            {"e": f"ev_{org}_1", "o": org, "p": f"pc_{org}_1"})
        c.execute(text(
            "insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
            "  display_name) values (:n, 1, :o, 'thread', :k, 'Thread with customer@big.co') "
            # The scratch database persists for the whole session, so every seed here has to be
            # re-runnable or the second invocation of the file fails on its own leftovers.
            "on conflict (node_id, version) do nothing"),
            {"n": f"node_{org}_t", "o": org, "k": f"thread:th_{org}"})


def test_the_sweep_opens_a_situation_for_an_unanswered_request(pg_store):
    org = "desk_first_response"
    _seed_org(pg_store, org)
    _seed_unanswered_request(pg_store, org)
    assert refresh_support_situations(pg_store, org, now=NOW) > 0

    with pg_store.engine.connect() as c:
        rows = c.execute(text(
            "select situation_type, domain, status, coverage, missing, anchor_node_id "
            "from context_situations where org_id=:o"), {"o": org}).mappings().all()
    expected = {spec_for(d).type_for(ANCHOR_THREAD) for d in domains_declaring(ANCHOR_THREAD)}
    assert {r["situation_type"] for r in rows} == expected
    row = rows[0]
    assert row["status"] == "active"
    # Inferred, never recorded: the ceiling is on the reading, not on the row's own completeness.
    # PERCENT, the unit `situations.SCORE_MAX` names — 4000 here was basis points, which
    # `situation_bso._bp` re-multiplied into a saturated coverage_bp=10000 at the Layer 3 seam.
    assert 0 < row["coverage"] <= 40
    assert any("entitlement" in m for m in row["missing"]), row["missing"]


def test_the_sweep_is_idempotent_inside_one_window(pg_store):
    """Every fact overwrites its own deterministic version id and every situation conflicts on
    `(org_id, correlation_id)`, so a sweep that runs six times a day produces one row per finding
    rather than six — the same property `periodic.py` keeps and for the same reason."""
    org = "desk_idempotent"
    _seed_org(pg_store, org)
    _seed_unanswered_request(pg_store, org)
    refresh_support_situations(pg_store, org, now=NOW)
    refresh_support_situations(pg_store, org, now=NOW)
    with pg_store.engine.connect() as c:
        situations = c.execute(text(
            "select count(*) from context_situations where org_id=:o"), {"o": org}).scalar()
        facts = c.execute(text(
            "select count(*) from graph_facts where org_id=:o and field like 'response.%'"),
            {"o": org}).scalar()
    assert situations == len(domains_declaring(ANCHOR_THREAD))
    assert facts == 5          # opened_at, target_at, target_source, channel, overdue_hours


def test_a_finding_that_stops_being_true_resolves_itself_by_fact(pg_store):
    """RESOLVED BY FACT rather than by a human, so it un-resolves by itself if the finding
    returns — the system must not need somebody to undo a conclusion it drew from data that has
    since changed. This is what closes an aging item when its loop closes and a workaround when a
    fix email lands; here it is a reply arriving on the unanswered thread."""
    org = "desk_selfclosing"
    _seed_org(pg_store, org)
    _seed_unanswered_request(pg_store, org)
    refresh_support_situations(pg_store, org, now=NOW)

    with pg_store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "  source_object_id, parent_object_id, dedup_key, actor, occurred_at) "
            "values (:e, :o, :cid, 'gmail', 'message', :soid, :thread, :e, "
            "  cast(:actor as jsonb), :at) on conflict do nothing"),
            {"e": f"ev_{org}_2", "o": org, "cid": f"conn_{org}", "soid": f"m_{org}_2",
             "thread": f"th_{org}",
             "actor": json.dumps({"email": _us(org)}),
             "at": NOW - timedelta(days=5)})
    refresh_support_situations(pg_store, org, now=NOW)

    with pg_store.engine.connect() as c:
        row = c.execute(text(
            "select status, resolved_by from context_situations where org_id=:o"),
            {"o": org}).mappings().one()
    assert row["status"] == "resolved" and row["resolved_by"] == "fact"


def test_the_anchors_are_ordinary_nodes_so_the_compile_path_needs_no_new_concept(pg_store):
    """The whole design rests on this, exactly as the period situations do: if the anchors are
    ordinary graph nodes carrying ordinary facts, then `_load_context`, `_neighborhood`,
    `build_context_slice` and the compiler all work unchanged."""
    org = "desk_anchors"
    _seed_org(pg_store, org)
    _seed_unanswered_request(pg_store, org)
    refresh_support_situations(pg_store, org, now=NOW)
    with pg_store.engine.connect() as c:
        node_types = {r[0] for r in c.execute(text(
            "select distinct n.node_type from graph_nodes n join context_situations s "
            "  on s.org_id=n.org_id and s.anchor_node_id=n.node_id where n.org_id=:o"),
            {"o": org})}
    assert node_types <= {a for a, _ in READINGS}


def test_the_snapshot_comes_back_ordered_however_the_rows_were_written(pg_store):
    """The `order by` in `gather`'s message query, checked against the thing that actually breaks
    it: heap order.

    Postgres returns an unordered set, and for a small table a sequential scan returns rows in the
    order they were INSERTED. This seeds one thread newest-message-first, which is the order a
    backfill produces, and pins that the snapshot still reads oldest-first. Without the `order by`
    the two orders are the same thing and `Desk.by_thread()` — whose dict key order is insertion
    order — hands the seven readings a different mailbox on a different day, contradicting the
    module's claim that a re-sweep produces the same answers. `(occurred_at, event_id)` rather
    than `occurred_at` alone because a send and its own delivery record can share a second.
    """
    org = "desk_ordering"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as c:
        _seed_connection(c, org)
        # Written newest first, and the two oldest share a timestamp so the tie-break is exercised
        # rather than assumed.
        tied = NOW - timedelta(days=9)
        for suffix, at in (("c", NOW - timedelta(days=4)), ("b", tied), ("a", tied)):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "  source_object_id, parent_object_id, dedup_key, actor, occurred_at) "
                "values (:e, :o, :cid, 'gmail', 'message', :soid, :thread, :e, "
                "  cast(:actor as jsonb), :at) on conflict do nothing"),
                {"e": f"ev_{org}_{suffix}", "o": org, "cid": f"conn_{org}",
                 "soid": f"m_{org}_{suffix}", "thread": f"th_{org}",
                 "actor": json.dumps({"email": "customer@big.co"}), "at": at})

    desk = gather(pg_store, org, now=NOW, policy=ResponsePolicy())
    seen = [(m.at, m.event_id) for m in desk.messages]
    assert seen == sorted(seen), seen
    assert [m.event_id for m in desk.by_thread()[f"th_{org}"]] == [
        f"ev_{org}_a", f"ev_{org}_b", f"ev_{org}_c"]

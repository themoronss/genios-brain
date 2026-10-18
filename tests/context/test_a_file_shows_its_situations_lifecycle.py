"""STEP-12 · a file shows its situations' lifecycle — each one's status, when first and last seen, and its quiet window.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_file_shows_its_situations_lifecycle.py -q

`context/workstreams.lifecycle_for` (tree `yc2_w27_s12` M32.C2.L-data.V0.U07, added by `yc2_w27_align`
M34.C4). What the dossier's *expected vs actual* reads: each situation anchored on the file, its status,
first and last seen, how long it was seen and how long it has been quiet — and the window it is held to,
named by where it came from: the file's kind of work (`06` D33, the playbook's stop rule — in code since
M34.C2 U02, `context/correlation.file_quiet_days`), else its domain's declared clock, else the engine's
45 days. An open situation quiet past its window says so; one that ended is not "past" anything.
Bounded, newest first, the cut counted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context import correlation
from genios_engine.context import workstreams as W

pytestmark = pytest.mark.pg

ORG = "org_s12_lifecycle"
FILE = "node_lifecycle_fund"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(pg_store):
    eng = pg_store.engine
    _clean(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'lc@example.test')"),
                  {"o": ORG})
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key) "
                       "values (:n, :o, 'company', 'kestrelcap.test')"), {"n": FILE, "o": ORG})
    before = correlation._quiet_days_for_node
    yield eng
    correlation.use_quiet_days(before)
    _clean(eng)


def _clean(eng) -> None:
    with eng.begin() as c:
        for table in ("context_situations", "context_correlations", "graph_nodes"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _situation(c, sid: str, *, first: datetime, last: datetime, status: str = "active",
               domain: str = "founder_office", anchor: str = FILE) -> None:
    c.execute(text("insert into context_correlations (correlation_id, org_id, anchor_node_id, "
                   "domain, generation) values (:k, :o, :a, :d, (select coalesce(max(generation), "
                   "0) + 1 from context_correlations where org_id = :o and anchor_node_id = :a "
                   "and domain = :d))"),
              {"k": f"cor_{sid}", "o": ORG, "a": anchor, "d": domain})
    c.execute(text(
        "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
        "situation_type, domain, status, first_seen_at, last_seen_at) values (:s, :o, :k, :a, "
        "'investor_relationship', :d, :st, :f, :l)"),
        {"s": sid, "o": ORG, "k": f"cor_{sid}", "a": anchor, "d": domain, "st": status,
         "f": first, "l": last})


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def test_each_situation_with_its_window_from_the_files_kind(engine):
    correlation.use_quiet_days(lambda conn, org, node: 90 if node == FILE else None)
    with engine.begin() as c:
        _situation(c, "sit_quiet", first=_ago(130), last=_ago(100))          # 100 > 90: past
        _situation(c, "sit_live", first=_ago(20), last=_ago(3))
        _situation(c, "sit_done", first=_ago(200), last=_ago(150), status="resolved")
    with engine.connect() as c:
        life = W.lifecycle_for(c, ORG, FILE, now=NOW)
    by_id = {s.situation_id: s for s in life.situations}
    assert [s.situation_id for s in life.situations] == ["sit_live", "sit_quiet", "sit_done"]
    quiet = by_id["sit_quiet"]
    assert (quiet.status, quiet.quiet_window_days, quiet.window_from) == ("active", 90, "kind")
    assert (quiet.days_seen, quiet.days_since_seen, quiet.past_window) == (30.0, 100.0, True)
    assert (by_id["sit_live"].days_since_seen, by_id["sit_live"].past_window) == (3.0, False)
    assert by_id["sit_done"].past_window is None                         # it ended: past nothing
    assert life.cut == 0


def test_without_a_kind_the_domains_clock_then_the_engines(engine, monkeypatch):
    correlation.use_quiet_days(None)
    with engine.begin() as c:
        _situation(c, "sit_admin", first=_ago(60), last=_ago(50), domain="admin")
        _situation(c, "sit_fo", first=_ago(10), last=_ago(5))
    with engine.connect() as c:
        life = W.lifecycle_for(c, ORG, FILE, now=NOW)
    by_id = {s.situation_id: s for s in life.situations}
    assert (by_id["sit_admin"].quiet_window_days, by_id["sit_admin"].window_from) == (
        correlation.CORRELATION_WINDOW_DAYS, "engine")
    assert by_id["sit_admin"].past_window is True                         # 50 > 45

    real = correlation.spec_for

    class _Declared:
        correlation_window_days = 14

    monkeypatch.setattr(correlation, "spec_for",
                        lambda d: _Declared() if d == "admin" else real(d))
    with engine.connect() as c:
        life = W.lifecycle_for(c, ORG, FILE, now=NOW)
    admin = next(s for s in life.situations if s.situation_id == "sit_admin")
    assert (admin.quiet_window_days, admin.window_from) == (14, "domain")


def test_a_reader_that_fails_costs_its_answer_not_the_file(engine):
    def _broken(conn, org, node):
        raise RuntimeError("the brief could not be read")
    correlation.use_quiet_days(_broken)
    with engine.begin() as c:
        _situation(c, "sit_a", first=_ago(10), last=_ago(5))
    with engine.connect() as c:
        [life] = W.lifecycle_for(c, ORG, FILE, now=NOW).situations
    assert (life.quiet_window_days, life.window_from) == (correlation.CORRELATION_WINDOW_DAYS,
                                                          "engine")


def test_only_the_files_own_situations_bounded_and_the_cut_counted(engine):
    correlation.use_quiet_days(None)
    with engine.begin() as c:
        c.execute(text("insert into graph_nodes (node_id, org_id, node_type, canonical_key) "
                       "values ('node_other', :o, 'company', 'other.test')"), {"o": ORG})
        _situation(c, "sit_other", first=_ago(2), last=_ago(1), anchor="node_other")
        for n in range(W.LIFECYCLE_LIMIT + 3):
            _situation(c, f"sit_{n:02d}", first=_ago(40 - n), last=_ago(30 - n))
    with engine.connect() as c:
        life = W.lifecycle_for(c, ORG, FILE, now=NOW)
    ids = [s.situation_id for s in life.situations]
    assert "sit_other" not in ids and len(ids) == W.LIFECYCLE_LIMIT and life.cut == 3
    assert ids[0] == f"sit_{W.LIFECYCLE_LIMIT + 2:02d}"                    # the most recently seen


def test_the_lifecycle_reads_as_json(engine):
    import json
    correlation.use_quiet_days(lambda conn, org, node: 90)
    with engine.begin() as c:
        _situation(c, "sit_a", first=_ago(10), last=_ago(5))
    with engine.connect() as c:
        body = W.lifecycle_for(c, ORG, FILE, now=NOW).as_dict()
    assert json.loads(json.dumps(body)) == body
    assert body["situations"][0]["window_from"] == "kind" and body["cut"] == 0

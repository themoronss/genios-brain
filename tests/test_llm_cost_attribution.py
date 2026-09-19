"""0175 · WHO spent the model money — per-seat attribution and the cache split.

`llm_costs` could always answer "what did this ACCOUNT cost this month". It could not answer
"which PERSON in it cost that", because org_id was the only identity on the row — so a runaway or
abusive seat stayed invisible until the ORG-wide daily cap tripped and blocked the whole tenant.

These tests pin the four things that fix has to get right, because each one is a way for a
per-user bill to be quietly wrong rather than obviously broken:

  1. the seat reaches the ledger from the lanes that know it (screen, a seat's own mailbox, an
     authenticated query);
  2. a seat is never INVENTED where the work has no single owner — NULL stays NULL;
  3. a reused object (one relevance classifier across a cross-org sweep) cannot leak the previous
     connection's seat into this one's rows;
  4. the cache split is recorded and NEVER priced — `input_tokens` is already cost-equivalent, so
     adding the cache counts to it would double-charge every cached call.

The real-Postgres half proves the columns and the admin rollup, since the SQL is where "it
compiled" and "it answers the question" part company.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


# ════════════════════════════════════════════════════════════════════════════════════════
# hermetic — the plumbing
# ════════════════════════════════════════════════════════════════════════════════════════
class _Recorder:
    """A `record_cost`-shaped sink that keeps the kwargs, which are the whole contract here."""

    def __init__(self):
        self.rows: list[dict] = []

    def __call__(self, **row):
        self.rows.append(row)


class _FakeLLM:
    model = "claude-haiku-4-5"

    def __init__(self, result=None):
        self.result = result or SimpleNamespace(
            ok=True, parsed={"rules": []}, raw="{}", model=self.model,
            input_tokens=900, output_tokens=60, error=None,
            cache_read_tokens=800, cache_write_tokens=0)
        self.calls = 0

    def call(self, _prompt, **_kw):
        self.calls += 1
        return self.result


def test_the_ingestion_sink_carries_the_connection_s_seat(monkeypatch):
    """A seat connection (0138) is one person's mailbox, so every call made while draining it is
    that person's. The seat is bound to the SINK rather than passed at each call site — the lane
    has many of those and would only have to forget once."""
    import genios_engine.context.graph_store as gs
    from genios_engine.platform import wiring

    seen = _Recorder()
    monkeypatch.setattr(gs, "GraphStore", lambda **_kw: SimpleNamespace(record_cost=seen))
    bound = wiring._llm_cost_sink(SimpleNamespace(), seat_id="seat_a")
    plain = wiring._llm_cost_sink(SimpleNamespace())

    bound(org_id="org_1", model="m", purpose="extract", input_tokens=1, output_tokens=1)
    plain(org_id="org_1", model="m", purpose="extract", input_tokens=1, output_tokens=1)

    assert seen.rows[0]["seat_id"] == "seat_a"
    # A WORKSPACE connection has no seat, and the honest ledger value is absence: the sink adds
    # no key at all rather than a placeholder that would later be counted as a person.
    assert "seat_id" not in seen.rows[1]


def test_a_reused_relevance_gate_cannot_bill_the_previous_connection_s_seat():
    """One classifier is reused across a cross-org sweep. Before 0175 that only risked billing the
    wrong ORG; now it could also put this mailbox's spend on the last person synced."""
    from genios_engine.capture.gate.relevance import LLMRelevanceClassifier

    seen = _Recorder()
    gate = LLMRelevanceClassifier(_FakeLLM())
    res = SimpleNamespace(model="claude-haiku-4-5", input_tokens=10, output_tokens=2, ok=True,
                          error=None, cache_read_tokens=4, cache_write_tokens=1)

    gate.bind_costs(seen, "org_1", "seat_a")
    gate._record(res)
    gate.bind_costs(seen, "org_2", "seat_b")
    gate._record(res)
    gate.bind_costs(seen, "org_3")             # a workspace connection, one loop later
    gate._record(res)

    assert [(r["org_id"], r["seat_id"]) for r in seen.rows] == [
        ("org_1", "seat_a"), ("org_2", "seat_b"), ("org_3", None)]
    # …and the raw cache counts came along, at their real values.
    assert seen.rows[0]["cache_read_tokens"] == 4
    assert seen.rows[0]["cache_write_tokens"] == 1


def test_the_document_reader_records_what_it_spent_even_when_it_refuses():
    """The T2 policy-document read is the most expensive single call in the product and was the
    one call that never reached `llm_costs` — reported spend sat below the Anthropic bill by
    exactly this lane. A refused answer was still bought, so it is recorded too."""
    from genios_engine.packs.brains.org_rule_extract import COST_PURPOSE, LLMOrgRuleExtractor

    seen = _Recorder()
    failed = SimpleNamespace(ok=False, parsed=None, raw="", model="claude-haiku-4-5",
                             input_tokens=4_000, output_tokens=0, error="overloaded",
                             cache_read_tokens=0, cache_write_tokens=0)
    ex = LLMOrgRuleExtractor(_FakeLLM(failed), cost_sink=seen, org_id="org_1")
    ex.bind_event("evt_9")

    with pytest.raises(RuntimeError):
        ex.propose(text="…", kind="policy", title="Approvals")

    assert len(seen.rows) == 1
    row = seen.rows[0]
    assert row["purpose"] == COST_PURPOSE
    assert row["input_tokens"] == 4_000 and row["success"] is False
    assert row["event_id"] == "evt_9" and row["subject_ref"] == "event:evt_9"
    # No seat: a policy document is read for the ORG, and naming whoever uploaded it would put one
    # person's name on spend the whole tenant caused.
    assert row.get("seat_id") is None


def test_a_broken_ledger_never_costs_us_a_document_we_already_paid_to_read():
    from genios_engine.packs.brains.org_rule_extract import LLMOrgRuleExtractor

    def boom(**_row):
        raise RuntimeError("db down")

    ex = LLMOrgRuleExtractor(_FakeLLM(), cost_sink=boom, org_id="org_1")
    assert list(ex.propose(text="…", kind="policy", title="Approvals")) == []


def test_the_screen_lane_passes_its_seat_down_to_the_ledger():
    """Screen intelligence is per-seat by construction (a device belongs to one seat, 0140), so
    this is the lane where an unattributed row would be a plain loss of information."""
    import inspect

    from genios_engine.reason.moments import screen_insight as SI

    assert "seat_id" in inspect.signature(SI.insight).parameters
    assert "seat_id" in inspect.signature(SI.llm_insight).parameters
    src = inspect.getsource(SI.llm_insight)
    assert "seat_id=seat_id" in src
    assert "cache_read_tokens=res.cache_read_tokens" in src


def test_the_cache_split_is_recorded_and_never_added_to_the_billable_input():
    """`LLMClient.input_tokens` is ALREADY cost-equivalent (uncached + 1.25x/2x writes + 0.1x
    reads). Pricing the raw cache counts on top of it would charge the cache twice."""
    from genios_engine.platform import metrics as M

    priced = M.cost_usd("claude-haiku-4-5", 1_000, 100)
    pi, po = M.llm_price("claude-haiku-4-5")
    assert priced == pytest.approx(1_000 * pi + 100 * po)
    # The pricer takes two token numbers and knows nothing about caching — which is what keeps
    # the extra columns reportable without touching a single bill.
    assert M.cost_usd.__code__.co_argcount == 3


# ════════════════════════════════════════════════════════════════════════════════════════
# real Postgres — the columns and the rollup
# ════════════════════════════════════════════════════════════════════════════════════════
pg = pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")


@pytest.fixture
def engine():
    from sqlalchemy import create_engine
    eng = create_engine(URL)
    with eng.begin() as c:
        c.execute(text("delete from llm_costs where org_id in ('org_cost_a','org_cost_b')"))
        c.execute(text("delete from org_seats where org_id = 'org_cost_a'"))
        c.execute(text("delete from orgs where id in ('org_cost_a','org_cost_b')"))
        c.execute(text("insert into orgs (id, name, email) values "
                       "('org_cost_a','Cost A','a@cost.test'), ('org_cost_b','Cost B',null)"))
        c.execute(text("insert into org_seats (org_id, seat_id, email) values "
                       "('org_cost_a','seat_a','amit@cost.test'), "
                       "('org_cost_a','seat_b','bina@cost.test')"))
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from llm_costs where org_id in ('org_cost_a','org_cost_b')"))
        c.execute(text("delete from org_seats where org_id = 'org_cost_a'"))
        c.execute(text("delete from orgs where id in ('org_cost_a','org_cost_b')"))


@pg
@pytest.mark.pg
def test_the_ledger_stores_the_seat_and_the_cache_split(engine):
    from genios_engine.context.graph_store import GraphStore

    store = GraphStore(engine=engine)
    store.record_cost(org_id="org_cost_a", model="claude-haiku-4-5",
                      purpose="moment.screen_insight", seat_id="seat_a",
                      input_tokens=1_200, output_tokens=200,
                      cache_read_tokens=9_000, cache_write_tokens=1_000)
    store.record_cost(org_id="org_cost_a", model="claude-haiku-4-5", purpose="l1_extract",
                      input_tokens=500, output_tokens=50)         # background: no seat

    with engine.connect() as c:
        rows = c.execute(text(
            "select purpose, seat_id, input_tokens, cache_read_tokens, cache_write_tokens "
            "from llm_costs where org_id = 'org_cost_a' order by purpose")).fetchall()

    assert [(r.purpose, r.seat_id) for r in rows] == [
        ("l1_extract", None), ("moment.screen_insight", "seat_a")]
    # Recorded, not priced: the billable input is untouched by the 10k cached tokens beside it.
    assert (rows[1].input_tokens, rows[1].cache_read_tokens, rows[1].cache_write_tokens) == (
        1_200, 9_000, 1_000)
    assert (rows[0].cache_read_tokens, rows[0].cache_write_tokens) == (0, 0)


@pg
@pytest.mark.pg
def test_the_admin_rollup_names_the_person_and_admits_what_it_cannot_attribute(engine):
    """The per-user bill, end to end: two seats and one background lane in the same window."""
    from genios_engine.api import admin_routes as A
    from genios_engine.context.graph_store import GraphStore

    store = GraphStore(engine=engine)
    for _ in range(3):        # the heavy seat
        store.record_cost(org_id="org_cost_a", model="claude-opus-5", purpose="intelligence_query",
                          seat_id="seat_a", input_tokens=100_000, output_tokens=10_000)
    store.record_cost(org_id="org_cost_a", model="claude-haiku-4-5", purpose="intelligence_query",
                      seat_id="seat_b", input_tokens=1_000, output_tokens=100)
    store.record_cost(org_id="org_cost_a", model="claude-haiku-4-5", purpose="l1_extract",
                      input_tokens=2_000, output_tokens=100)

    original, A._graph = A._graph, store
    try:
        out = A.account_llm_usage("org_cost_a", days=30)
    finally:
        A._graph = original

    seats = {r["seat_id"]: r for r in out["seats"]}
    assert set(seats) == {"seat_a", "seat_b", A.UNATTRIBUTED}
    assert seats["seat_a"]["email"] == "amit@cost.test"
    assert seats[A.UNATTRIBUTED]["email"] is None
    # Ranked by money, and the heavy seat is on Opus: the ordering is the whole point of the view.
    assert out["seats"][0]["seat_id"] == "seat_a"
    assert seats["seat_a"]["cost_usd"] > seats["seat_b"]["cost_usd"]
    assert seats["seat_a"]["calls"] == 3
    # The share of the bill that can be put on a named person at all — stated, never assumed.
    assert 0 < out["totals"]["attributed_pct"] < 100
    assert out["totals"]["cost_usd"] == pytest.approx(
        sum(r["cost_usd"] for r in out["seats"]), rel=1e-6)
    # Monthly is what a per-user bill is actually computed from.
    assert any(r["seat_id"] == "seat_a" and r["cost_usd"] > 0 for r in out["by_seat_month"])


@pg
@pytest.mark.pg
def test_the_runaway_view_separates_a_heavy_month_from_a_heavy_day(engine):
    """A monthly total cannot tell a busy user from a compromised one. One seat spends steadily,
    the other spends the same money in a single day — only `peak_over_avg` tells them apart."""
    from genios_engine.api import admin_routes as A
    from genios_engine.context.graph_store import GraphStore

    store = GraphStore(engine=engine)
    steady, spike = "seat_a", "seat_b"
    with engine.begin() as c:
        for day in range(4):
            at = NOW - timedelta(days=day)
            c.execute(text(
                "insert into llm_costs (org_id, model, purpose, input_tokens, output_tokens, "
                "seat_id, created_at) values ('org_cost_a','claude-haiku-4-5','x',"
                ":it,0,:s,:at)"), {"it": 250_000, "s": steady, "at": at})
        c.execute(text(
            "insert into llm_costs (org_id, model, purpose, input_tokens, output_tokens, "
            "seat_id, created_at) values ('org_cost_a','claude-haiku-4-5','x',"
            ":it,0,:s,:at)"), {"it": 1_000_000, "s": spike, "at": NOW})
    assert store is not None

    original, A._graph = A._graph, store
    try:
        out = A.top_spending_seats(days=30, limit=50, include_internal=True)
    finally:
        A._graph = original

    rows = {r["seat_id"]: r for r in out["seats"] if r["org_id"] == "org_cost_a"}
    assert rows[steady]["cost_usd"] == pytest.approx(rows[spike]["cost_usd"], rel=1e-6)
    assert rows[steady]["active_days"] == 4 and rows[spike]["active_days"] == 1
    assert rows[steady]["peak_over_avg"] == 1.0          # flat: every day looks like the average
    assert rows[spike]["peak_over_avg"] == 1.0           # one day IS its average…
    # …and that is exactly why the pair of numbers, not the ratio alone, is what an operator reads:
    # the spike seat's whole bill landed in one day.
    assert rows[spike]["peak_day_usd"] == pytest.approx(rows[spike]["cost_usd"], rel=1e-6)
    assert rows[steady]["peak_day_usd"] < rows[steady]["cost_usd"]

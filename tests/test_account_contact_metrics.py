"""Account-level contact metrics — `derived.contact_frequency` + `contact_rate_per_account`.

The corpus asks for these in `Customer Support Expertise/objects/core/churn-risk.yaml`, and says
exactly why the per-person metrics already in `baselines.py` are not a substitute: every
executable going-quiet pattern "reads a THREAD and infers an ACCOUNT", and "an account can be
silent on one thread and busy on four others". Eleven Customer Support patterns are gated on
`derived.contact_frequency` alone — it was the single highest-unblocking ask in the whole
Customer Support backlog, and unlike the rest of that backlog it needs no new connector: the
events are already in `source_events` and the company edges already in `graph_edges`.

The pair is the point. A frequency without the account's own norm cannot answer the question the
patterns actually ask — the corpus puts it as "a hundred-seat account opening four tickets a week
is normal; a two-seat account doing the same is a churn signal" — so both keys are written
together or the metric is not evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.reason.baselines import (
    BASELINE_DAYS,
    RECENT_DAYS,
    _account_rows,
    _per_week,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Edge:
    def __init__(self, company: str, person: str):
        self.company, self.person = company, person


class _FakeConn:
    """Stands in for the live connection; `_account_rows` issues exactly one query."""

    def __init__(self, edges):
        self._edges = edges
        self.queries = 0

    def execute(self, *_args, **_kwargs):
        self.queries += 1
        return _FakeResult(self._edges)


# ── the rate itself ──────────────────────────────────────────────────────────────────────────
def test_frequency_is_contacts_per_week_over_its_window():
    """A rate over the WHOLE window, not over the days that happened to have traffic.

    One contact a day for the full fourteen days is seven a week. Seven contacts in the same
    window is half that — averaging over the window is what makes a fortnight of silence visible
    instead of being hidden by the busy days inside it.
    """
    assert _per_week([_ago(i) for i in range(RECENT_DAYS)], NOW, RECENT_DAYS) == 7.0
    assert _per_week([_ago(i) for i in range(7)], NOW, RECENT_DAYS) == 3.5


def test_events_outside_the_window_do_not_count_toward_it():
    """The recent window is 14 days; a contact 30 days ago is history, not current frequency."""
    times = [_ago(30), _ago(40), _ago(50)]
    assert _per_week(times, NOW, RECENT_DAYS) == 0.0
    # ...but they are exactly what the 56-day baseline is for.
    assert _per_week(times, NOW, BASELINE_DAYS) > 0.0


def test_silence_reads_as_zero_and_not_as_neutral():
    """The one behaviour that separates a RATE from the ratios beside it.

    `_engagement` and `_momentum` return a neutral 1.0 when there is no history, and that is
    right for them: a brand-new contact has not gone cold. For a rate it would be a lie — an
    account nobody has heard from contacts us zero times a week, and that zero IS the churn
    finding these patterns are looking for. Returning 1.0 here would make every silent account
    read as an averagely-chatty one.
    """
    assert _per_week([], NOW, RECENT_DAYS) == 0.0


# ── the account roll-up ──────────────────────────────────────────────────────────────────────
def test_a_company_sums_the_events_of_all_its_people():
    """The whole reason the metric exists: four people on one account are one contact stream."""
    conn = _FakeConn([_Edge("co_1", "p_1"), _Edge("co_1", "p_2")])
    rows = _account_rows(conn, "org_1", {"p_1": [_ago(1), _ago(2)], "p_2": [_ago(3)]}, NOW)

    freq = next(r for r in rows if r["k"] == "contact_frequency:co_1")
    assert freq["v"] == round(3 * 7.0 / RECENT_DAYS, 3)
    assert freq["n"] == 3


def test_both_keys_are_written_for_every_company():
    """A frequency without its baseline is not evidence, so neither ships alone."""
    conn = _FakeConn([_Edge("co_1", "p_1"), _Edge("co_2", "p_2")])
    rows = _account_rows(conn, "org_1", {"p_1": [_ago(1)], "p_2": [_ago(2)]}, NOW)

    keys = {r["k"] for r in rows}
    assert keys == {
        "contact_frequency:co_1", "contact_rate_per_account:co_1",
        "contact_frequency:co_2", "contact_rate_per_account:co_2",
    }


def test_an_account_busy_on_one_thread_is_not_read_as_quiet():
    """The corpus's own sentence, as a test.

    p_quiet has said nothing in the recent window and p_busy has said plenty. Per-person metrics
    report the first as cold. The account is not cold, and the account is what churn is about.
    """
    conn = _FakeConn([_Edge("co_1", "p_quiet"), _Edge("co_1", "p_busy")])
    rows = _account_rows(
        conn, "org_1",
        {"p_quiet": [_ago(40)], "p_busy": [_ago(1), _ago(2), _ago(3), _ago(4)]}, NOW)

    assert next(r for r in rows if r["k"] == "contact_frequency:co_1")["v"] > 0.0


def test_the_roll_up_costs_one_query_not_one_per_company():
    """Same constraint the per-person pass was rewritten for — this runs against a remote pooler."""
    conn = _FakeConn([_Edge(f"co_{i}", f"p_{i}") for i in range(50)])
    _account_rows(conn, "org_1", {f"p_{i}": [_ago(1)] for i in range(50)}, NOW)
    assert conn.queries == 1


def test_a_thin_account_is_flagged_cold_start():
    """Three contacts is not a norm. The consumer needs to know it is reading a guess."""
    conn = _FakeConn([_Edge("co_1", "p_1")])
    rows = _account_rows(conn, "org_1", {"p_1": [_ago(1)]}, NOW)
    assert all(r["c"] is True for r in rows)


# ── the readers ──────────────────────────────────────────────────────────────────────────────
def test_both_readers_route_the_new_metrics():
    """`baselines.load_node_metrics` and `runner._load_all_baselines` split the same key space.

    They are two copies of one mapping, and a metric added to one and not the other is written,
    stored, and then silently dropped on the way to the rules — which is the failure mode the
    whole file exists to avoid.
    """
    import inspect

    from genios_engine.reason import baselines, runner

    for src in (inspect.getsource(baselines.load_node_metrics),
                inspect.getsource(runner)):
        assert "contact_rate_per_account" in src, "the baseline half is not routed"
        assert "contact_frequency" in src, "the derived half is not routed"


def test_the_corpus_now_calls_these_substrate_rather_than_planned():
    """The vocabulary is a census, not a wish. Shipping the writer moves the entry."""
    import pathlib

    import yaml

    root = pathlib.Path(__file__).resolve().parents[1]
    v = yaml.safe_load((root / "Domain Expertise/_schema/vocabulary.yaml").read_text())

    assert "derived.contact_frequency" in v["substrate"]["fact_paths"]
    assert "derived.contact_frequency" not in v["planned_substrate"]["fact_paths"]
    assert "contact_rate_per_account" in v["substrate"]["baselines"]
    assert "contact_rate_per_account" not in v["planned_substrate"]["baselines"]

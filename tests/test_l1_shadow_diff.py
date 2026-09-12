"""G10 · the shadow diff, exercised against a SEEDED SCRATCH ORG.

There is no real pilot tenant. No org has a live `l1_semantic_activation` row on any deployment,
so `scripts/l1_shadow_diff.py` has never been run over seven days of a customer's mail, and this
file does not pretend otherwise. What it does instead is make the LOGIC run: two scratch orgs are
seeded with both extraction paths' records — events both paths processed, a signal only the new
path found, signals only the old path found in every explanation class the script can produce,
resolved and unresolved evidence spans, extraction rows and cost ledgers on both sides — and
every number the gate reads is asserted against data whose answer is known by construction.

Two orgs, because a gate has to be shown BOTH ways round: `_clean` passes every line of the build
order's table, `_messy` fails three of them for three different reasons. A report that has only
ever been seen passing is a report nobody has seen work.

THE DEFECTS THIS FILE FOUND, all of one root cause plus one join. `l1_extraction_results` is
written by BOTH lanes — migration 0080 states that the old L2 lane's rows carry a null
`profile_id` and the new lane's carry the profile it read under — and the script read that table
without the filter. So the old path's own extraction rows were counted as evidence that the NEW
path had read the event (coverage), priced into the new path's spend (cost), and taken as proof
that the new lane had read an event it never saw (the explanation attached to a miss). The first
of those made the gate's headline line PASS on a tenant where the semantic lane never ran, which
is the one failure mode a shadow diff exists to prevent. Separately, the founder-visible
regression query joined `cards` to `graph_facts` on nothing at all.

Needs GENIOS_TEST_DATABASE_URL; skips without it, like every other real-Postgres file here.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import l1_shadow_diff as SD          # noqa: E402
from scripts._db import UnsafeDatabaseTarget      # noqa: E402
from scripts._gate import read_only_connection    # noqa: E402

NOW = datetime.now(timezone.utc)
SINCE = NOW - timedelta(days=7)
IN_WINDOW = NOW - timedelta(days=2)
OUT_OF_WINDOW = NOW - timedelta(days=40)

CLEAN = "org_shadow_clean"
MESSY = "org_shadow_messy"
CARDS = "org_shadow_cards"

HAIKU = "claude-haiku-4-5"
#: `platform/metrics.LLM_PRICE`, as the whole nano-dollars the script prices with.
HAIKU_IN, HAIKU_OUT = 1_000, 5_000


# ── seeding ──────────────────────────────────────────────────────────────────────────────────

def _span(quote: str, *, offset: int, verified: bool, event_id: str = "e") -> dict:
    """One evidence span. `source_ref` carries the EVENT, which is the real shape
    (`EvidenceSpan.source_ref` is `prepared_content:<event_id>`) and also what keeps two
    different events' quotes from deduplicating into one span in the counters below."""
    return {"source_ref": f"prepared_content:{event_id}", "quote": quote,
            "start_offset": offset, "end_offset": offset + len(quote), "verified": verified}


def _org(conn, org_id: str) -> None:
    """An org row, with NOT-NULL columns discovered rather than listed — the same trick
    `tests/conftest.py::_seed_scratch_org` uses, so a later migration adding a column does not
    turn this file into an error."""
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns where table_name='orgs' "
        "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
    cols, ph, vals = ["id"], [":id"], {"id": org_id}
    for r in reqd:
        cols.append(r.column_name)
        ph.append(f":{r.column_name}")
        dt = r.data_type
        vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                               else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                               else False if dt == "boolean"
                               else "{}" if dt in ("json", "jsonb") else "scratch")
    conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                      "on conflict (id) do nothing"), vals)


def _event(conn, org: str, event_id: str, *, at: datetime) -> None:
    conn.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at, captured_at) "
        "values (:e,:o,'conn_1','gmail','message',:e,:e,'{}'::jsonb,:at,:at)"),
        {"e": event_id, "o": org, "at": at})


def _l2_run(conn, org: str, event_id: str, *, status: str = "done") -> None:
    """The old path's own record that it processed this event."""
    conn.execute(text(
        "insert into l2_processing_runs (org_id, event_id, status) values (:o,:e,:s) "
        "on conflict (org_id, event_id) do update set status = excluded.status"),
        {"o": org, "e": event_id, "s": status})


def _extraction(conn, org: str, event_id: str, *, profile: str | None, tin: int, tout: int,
                model: str = HAIKU) -> None:
    """One extraction cache row. `profile is None` is an OLD-lane row — migration 0080: "existing
    rows keep profile_id null because the L2 lane never had a profile"."""
    conn.execute(text(
        "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
        "input_tokens, output_tokens, model_snapshot, profile_id, tier) "
        "values (:k,:o,:e,'{}'::jsonb,:ti,:to,:m,:p,:t) on conflict do nothing"),
        {"k": f"{'new' if profile else 'old'}:{org}:{event_id}", "o": org, "e": event_id,
         "ti": tin, "to": tout, "m": model, "p": profile, "t": "T2" if profile else None})


def _llm_cost(conn, org: str, event_id: str, *, tin: int, tout: int, model: str = HAIKU,
              at: datetime | None = None) -> None:
    """The old path's spend ledger row (`context/pipeline.py:545`, purpose='extract')."""
    conn.execute(text(
        "insert into llm_costs (org_id, model, purpose, input_tokens, output_tokens, event_id, "
        "created_at) values (:o,:m,'extract',:ti,:to,:e,:at)"),
        {"o": org, "m": model, "ti": tin, "to": tout, "e": event_id, "at": at or IN_WINDOW})


def _fact(conn, org: str, event_id: str, *, field: str, subject: str = "node_1") -> None:
    """An old-path signal: an active graph fact drawn from this event."""
    conn.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
        "value, created_by_event_id, occurred_at) "
        "values (:v,:f,:o,:s,:fld,'\"x\"'::jsonb,:e,:at) on conflict do nothing"),
        {"v": f"fv:{org}:{event_id}:{field}", "f": f"f:{org}:{event_id}:{field}", "o": org,
         "s": subject, "fld": field, "e": event_id, "at": IN_WINDOW})


def _signal(conn, org: str, event_id: str, *, kind: str, spans: list[dict],
            at: datetime | None = None) -> None:
    conn.execute(text(
        "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
        "importance_bp, importance_version, confidence_bp, visibility, extraction_ref, "
        "evidence_refs, occurred_at) values (:s,:o,:e,:t,:k,7000,'ALG-17@1',8000,"
        "'{\"scope\":\"org\"}'::jsonb, :ref, cast(:sp as jsonb), :at)"),
        {"s": f"sig:{org}:{event_id}", "o": org, "e": event_id, "t": f"trace:{event_id}",
         "k": kind, "ref": f"new:{org}:{event_id}", "sp": json.dumps(spans),
         "at": at or IN_WINDOW})


def _park(conn, org: str, event_id: str, *, reason: str, stage: str) -> None:
    conn.execute(text(
        "insert into parked_events (event_id, org_id, reason_code, stage) values (:e,:o,:r,:s) "
        "on conflict (event_id) do nothing"),
        {"e": event_id, "o": org, "r": reason, "s": stage})


def _drop(conn, org: str, event_id: str, *, kind: str, importance: int, floor: int) -> None:
    conn.execute(text(
        "insert into qualification_drops (drop_id, org_id, signal_id, event_id, signal_type, "
        "predicate, subject_key, importance_bp, importance_version, floor_bp, evaluated_at, "
        "retain_until) values (:d,:o,:s,:e,:k,'p','subj',:imp,'ALG-17@1',:f, now(), "
        "now() + interval '30 days')"),
        {"d": f"drop:{org}:{event_id}", "o": org, "s": f"sig:{org}:{event_id}", "e": event_id,
         "k": kind, "imp": importance, "f": floor})


def _card(conn, org: str, card_id: str, *, signal_id: str, subject: str) -> None:
    """A founder-visible card, and the Layer 4 signal behind it."""
    conn.execute(text(
        "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
        "eval_time) values (:s,:o,'rule_1',:n,50,'because', now()) on conflict do nothing"),
        {"s": signal_id, "o": org, "n": subject})
    conn.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
        "situation, score, expires_at) values (:c,:s,:o,'prescriptive','today','h','s',50, "
        "now() + interval '7 days') on conflict do nothing"),
        {"c": card_id, "s": signal_id, "o": org})


_TABLES = ("cards", "signals", "qualification_drops", "parked_events", "qualified_signals",
           "graph_facts", "llm_costs", "l1_extraction_results", "l2_processing_runs",
           "source_events", "l1_semantic_activation")


def _wipe(conn, org: str) -> None:
    for table in _TABLES:
        conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})


def _activate(conn, org: str, *, at: datetime, off: datetime | None = None) -> None:
    conn.execute(text(
        "insert into l1_semantic_activation (org_id, enabled_at, enabled_by, notes, disabled_at) "
        "values (:o,:at,'harsh@genios.ai','design partner',:off)"),
        {"o": org, "at": at, "off": off})


def _seed_clean(conn) -> None:
    """A pilot week that passes every line of the gate: both paths processed all three events,
    they agree on two, the new path found a third signal the old one did not (reported, not
    failed), every span resolved, and the new path spent 1.5x the old — inside the 2x allowed."""
    _org(conn, CLEAN)
    _wipe(conn, CLEAN)
    _activate(conn, CLEAN, at=SINCE - timedelta(days=1))
    for event_id in ("clean_e1", "clean_e2", "clean_e3"):
        _event(conn, CLEAN, event_id, at=IN_WINDOW)
        _l2_run(conn, CLEAN, event_id)
        _extraction(conn, CLEAN, event_id, profile=None, tin=1000, tout=100)
        _llm_cost(conn, CLEAN, event_id, tin=1000, tout=100)
        _extraction(conn, CLEAN, event_id, profile="email", tin=1500, tout=150)
        _signal(conn, CLEAN, event_id, kind="commitment_made",
                spans=[_span("we will sign on Friday", offset=0, verified=True,
                             event_id=event_id)])
    for event_id in ("clean_e1", "clean_e2"):
        _fact(conn, CLEAN, event_id, field="commitment.action")

    # outside the window entirely — must not reach a single number
    _event(conn, CLEAN, "clean_old", at=OUT_OF_WINDOW)
    _l2_run(conn, CLEAN, "clean_old")
    _extraction(conn, CLEAN, "clean_old", profile=None, tin=999_999, tout=999_999)
    _llm_cost(conn, CLEAN, "clean_old", tin=999_999, tout=999_999, at=OUT_OF_WINDOW)
    _fact(conn, CLEAN, "clean_old", field="ancient")


#: One old-path-only event per explanation class the script produces. Table-driven so a new class
#: is a row here and a row in the assertion, not a fifth copy of the seeding code.
MESSY_MISSES = (
    # (event_id, fact field, expected reason, what to seed on the v2 side)
    ("messy_never", "commitment.action", "not_extracted", "nothing"),
    ("messy_park", "deadline.date", "parked", "park"),
    ("messy_floor", "intro.person", "below_floor", "drop"),
    ("messy_gate", "question.text", "no_signal_detected", "read_only"),
)


def _seed_messy(conn) -> None:
    """A week that fails three gates, each for its own reason: an event the new lane never read
    (coverage), two unresolved spans of three (span rate), and 4x the old path's spend (cost)."""
    _org(conn, MESSY)
    _wipe(conn, MESSY)
    _activate(conn, MESSY, at=SINCE + timedelta(days=1), off=NOW - timedelta(days=1))

    _event(conn, MESSY, "messy_match", at=IN_WINDOW)
    _l2_run(conn, MESSY, "messy_match")
    _extraction(conn, MESSY, "messy_match", profile=None, tin=1000, tout=0)
    _llm_cost(conn, MESSY, "messy_match", tin=1000, tout=0)
    _extraction(conn, MESSY, "messy_match", profile="email", tin=4000, tout=0)
    _fact(conn, MESSY, "messy_match", field="commitment.action")
    _signal(conn, MESSY, "messy_match", kind="commitment_made",
            spans=[_span("verbatim and checked", offset=0, verified=True,
                         event_id="messy_match"),
                   _span("the model said this", offset=100, verified=False,
                         event_id="messy_match"),
                   _span("and this too", offset=200, verified=False, event_id="messy_match")])

    for event_id, field, _expected, seed in MESSY_MISSES:
        _event(conn, MESSY, event_id, at=IN_WINDOW)
        _l2_run(conn, MESSY, event_id)
        _extraction(conn, MESSY, event_id, profile=None, tin=1000, tout=0)
        _llm_cost(conn, MESSY, event_id, tin=1000, tout=0)
        _fact(conn, MESSY, event_id, field=field)
        if seed == "nothing":
            continue                        # the new lane never read this one
        _extraction(conn, MESSY, event_id, profile="email", tin=4000, tout=0)
        if seed == "park":
            _park(conn, MESSY, event_id, reason="extraction_timeout", stage="s2")
        elif seed == "drop":
            _drop(conn, MESSY, event_id, kind="opportunity_signal", importance=1200, floor=3000)


def _seed_cards(conn) -> None:
    """A tenant with a founder-visible card and, separately, an event the new path produced no
    signal for. The two have NOTHING to do with each other: the card's own subject is not the
    subject of the un-signalled fact, so nothing a founder can see has regressed."""
    _org(conn, CARDS)
    _wipe(conn, CARDS)
    _activate(conn, CARDS, at=SINCE - timedelta(days=1))

    _event(conn, CARDS, "cards_shown", at=IN_WINDOW)
    _l2_run(conn, CARDS, "cards_shown")
    _extraction(conn, CARDS, "cards_shown", profile="email", tin=100, tout=10)
    _fact(conn, CARDS, "cards_shown", field="commitment.action", subject="node_card")
    _signal(conn, CARDS, "cards_shown", kind="commitment_made",
            spans=[_span("still here", offset=0, verified=True,
                         event_id="cards_shown")])
    _card(conn, CARDS, "card_1", signal_id="sig_card_1", subject="node_card")

    # an unrelated event, on a different subject, that L1 v2 produced nothing for
    _event(conn, CARDS, "cards_quiet", at=IN_WINDOW)
    _l2_run(conn, CARDS, "cards_quiet")
    _extraction(conn, CARDS, "cards_quiet", profile="email", tin=100, tout=10)
    _fact(conn, CARDS, "cards_quiet", field="chit.chat", subject="node_other")


@pytest.fixture(scope="module")
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the shadow diff is not exercised")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)
    with eng.begin() as conn:
        _seed_clean(conn)
        _seed_messy(conn)
        _seed_cards(conn)
    yield eng
    with eng.begin() as conn:
        for org in (CLEAN, MESSY, CARDS):
            _wipe(conn, org)


@pytest.fixture
def ro(engine):
    """The script's OWN read-only connection — every assertion is made through the same
    server-enforced transaction the CLI uses, not a permissive one."""
    conn = read_only_connection(engine)
    yield conn
    conn.close()


@pytest.fixture
def clean(ro):
    return SD.build_report(ro, org_id=CLEAN, since=SINCE, until=NOW)


@pytest.fixture
def messy(ro):
    return SD.build_report(ro, org_id=MESSY, since=SINCE, until=NOW)


# ── read-only, and the target it is allowed to open ─────────────────────────────────────────

def test_the_connection_the_report_runs_on_refuses_writes(ro):
    """Read-only at the SERVER, not by review. A gate report that could write is a gate report
    that can be blamed for the state it measured."""
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError) as exc:
        ro.execute(text("insert into l1_semantic_activation (org_id, enabled_by) "
                        "values ('org_x','x')"))
    assert "read-only" in str(exc.value).lower()


def test_the_script_will_not_choose_a_database_for_you(monkeypatch):
    """`scripts/_db.py` has no fallback to the application's settings, and this script must not
    add one: on a developer machine `.env` names the production tenant database."""
    monkeypatch.delenv("GENIOS_TARGET_DATABASE_URL", raising=False)
    with pytest.raises(UnsafeDatabaseTarget) as exc:
        SD.main(["--org", CLEAN])
    assert "--database-url" in str(exc.value)


# ── coverage: "events processed by both paths" ──────────────────────────────────────────────

def test_only_events_inside_the_window_are_counted(clean):
    """`clean_old` carries a million tokens and a fact, 40 days ago. A window that leaked it
    would report a cost figure nobody could reproduce."""
    assert clean.events_in_window == 3
    assert clean.v1_processed == 3 and clean.v2_processed == 3


def test_a_week_both_paths_read_in_full_is_100_percent(clean):
    assert clean.both_processed == 3 and clean.both_bp == 10_000
    assert dict((k, ok) for k, _, _, ok in clean.checks)["events_processed_by_both"] is True


def test_an_event_only_the_OLD_lane_extracted_is_not_coverage_for_the_new_one(messy):
    """THE DEFECT. `l1_extraction_results` is written by both lanes and told apart by
    `profile_id` (migration 0080). Reading it without that filter counted the OLD path's own
    extraction row as proof the NEW path had read the event — so `messy_never`, which the
    semantic lane never touched, was counted as processed by both and the gate's headline line
    PASSED on a tenant where the new lane never ran. That is the one failure a shadow diff
    exists to prevent."""
    assert messy.events_in_window == 5
    assert messy.v1_processed == 5
    assert messy.v2_processed == 4, "an old-lane extraction row is not new-lane coverage"
    assert messy.both_processed == 4
    assert messy.both_bp == 8_000
    assert dict((k, ok) for k, _, _, ok in messy.checks)["events_processed_by_both"] is False


# ── the two difference lists ────────────────────────────────────────────────────────────────

def test_a_signal_only_the_new_path_found_is_reported_not_failed(clean):
    assert clean.v2_only_events == ("clean_e3",)
    assert dict((k, ok) for k, _, _, ok in clean.checks)["v2_only"] is True


@pytest.mark.parametrize("event_id,field,reason", [(e, f, r) for e, f, r, _ in MESSY_MISSES],
                         ids=[r for _, _, r, _ in MESSY_MISSES])
def test_every_signal_the_old_path_found_and_the_new_missed_carries_its_reason(
        messy, event_id, field, reason):
    """The plan's hardest line: each one REVIEWED AND EXPLAINED. A count is not an explanation,
    so each miss is resolved against the ledger the stage that stopped it writes."""
    by_event = {m.event_id: m for m in messy.misses}
    assert set(by_event) == {e for e, _, _, _ in MESSY_MISSES}
    miss = by_event[event_id]
    assert (miss.field, miss.reason) == (field, reason)
    assert miss.explained is True and miss.detail


def test_an_event_the_new_lane_never_read_is_not_explained_as_one_it_read_and_ignored(messy):
    """The same defect seen from the other end, and this is the one that would send a reviewer
    to the wrong unit: `messy_never` has an OLD-lane extraction row, so the unfiltered read
    concluded "the v2 lane extracted this event and no ALG-15 predicate fired" about an event the
    v2 lane never saw."""
    by_event = {m.event_id: m for m in messy.misses}
    assert by_event["messy_never"].reason == "not_extracted"
    assert "never read" in by_event["messy_never"].detail


def test_the_explanations_carry_the_numbers_behind_them(messy):
    by_reason = {m.reason: m.detail for m in messy.misses}
    assert "extraction_timeout" in by_reason["parked"]
    assert "1200" in by_reason["below_floor"] and "3000" in by_reason["below_floor"]


def test_no_miss_is_left_unexplained_and_the_gate_says_so(messy):
    assert messy.unexplained == ()
    assert dict((k, ok) for k, _, _, ok in messy.checks)["v1_only_explained"] is True


def test_a_week_with_nothing_lost_explains_nothing(clean):
    assert clean.misses == () and clean.unexplained == ()


# ── the unverified span rate ────────────────────────────────────────────────────────────────

def test_a_week_of_resolved_quotes_has_a_zero_unverified_rate(clean):
    assert clean.span_counters.total_spans == 3
    assert clean.unverified_bp == 0
    assert dict((k, ok) for k, _, _, ok in clean.checks)["unverified_span_rate"] is True


def test_spans_are_counted_per_span_not_per_signal(messy):
    """One signal with one good quote and two bad ones is a third of a receipt. Counting per
    signal would report 0% here — the number the gate is trying to catch."""
    assert (messy.span_counters.total_spans, messy.span_counters.failed_spans) == (3, 2)
    assert messy.unverified_bp == 6_666
    assert dict((k, ok) for k, _, _, ok in messy.checks)["unverified_span_rate"] is False


def test_one_quote_cited_by_four_claims_moves_the_rate_once(ro, engine):
    """`SpanCounters`' own rule: claims read out of one sentence share one receipt, and counting
    it four times would let one popular quote move the rate the extractor is judged by."""
    org = "org_shadow_dupe"
    duplicate = _span("the same sentence", offset=0, verified=False)
    with engine.begin() as conn:
        _org(conn, org)
        _wipe(conn, org)
        _event(conn, org, "dupe_e1", at=IN_WINDOW)
        _signal(conn, org, "dupe_e1", kind="commitment_made",
                spans=[duplicate, dict(duplicate), dict(duplicate),
                       _span("a resolved one", offset=500, verified=True)])
    try:
        report = SD.build_report(ro, org_id=org, since=SINCE, until=NOW)
        assert report.span_counters.total_spans == 2
        assert report.span_counters.failed_spans == 1
        assert report.unverified_bp == 5_000
    finally:
        with engine.begin() as conn:
            _wipe(conn, org)


# ── money ───────────────────────────────────────────────────────────────────────────────────

def test_the_two_paths_are_priced_from_their_own_records(clean):
    """v1 from `llm_costs` (the ledger the deployed breaker reads), v2 from the extraction rows
    it actually wrote — the new lane files no `llm_costs` row at all, so a single-ledger read
    would report it as free, which is the most flattering possible wrong answer."""
    events = 3
    assert clean.v1_cost_nano_per_1k == (3000 * HAIKU_IN + 300 * HAIKU_OUT) * 1000 // events
    assert clean.v2_cost_nano_per_1k == (4500 * HAIKU_IN + 450 * HAIKU_OUT) * 1000 // events


def test_the_old_paths_extraction_rows_are_not_billed_to_the_new_path(clean):
    """THE DEFECT, on the money side. Pricing every `l1_extraction_results` row as v2 spend adds
    the OLD lane's own extractions to the NEW lane's bill — here 1000 in / 100 out per event of
    somebody else's tokens — and the gate that decides whether the new path is affordable would
    have been reading a number inflated by the path it is being compared against."""
    v2_only = (4500 * HAIKU_IN + 450 * HAIKU_OUT) * 1000 // 3
    both_lanes = (7500 * HAIKU_IN + 750 * HAIKU_OUT) * 1000 // 3
    assert clean.v2_cost_nano_per_1k == v2_only
    assert clean.v2_cost_nano_per_1k != both_lanes


def test_one_and_a_half_times_the_old_price_is_inside_the_gate(clean):
    assert clean.cost_within_2x is True
    assert dict((k, ok) for k, _, _, ok in clean.checks)["llm_cost_per_1000_events"] is True


def test_four_times_the_old_price_is_not(messy):
    assert messy.cost_within_2x is False
    assert dict((k, ok) for k, _, _, ok in messy.checks)["llm_cost_per_1000_events"] is False


def test_every_number_in_the_money_path_is_an_integer(clean):
    """Determinism, asserted rather than assumed: a gate that says PASS on the strength of a
    float comparison is a gate that changes its mind between two machines."""
    for value in (clean.v1_cost_nano_per_1k, clean.v2_cost_nano_per_1k, clean.both_bp,
                  clean.unverified_bp):
        assert isinstance(value, int) and not isinstance(value, bool)


@pytest.mark.parametrize("model,tin,tout,expected", [
    (HAIKU, 1000, 100, 1000 * 1000 + 100 * 5000),
    ("claude-sonnet-4-6", 10, 10, 10 * 3000 + 10 * 15000),
    ("claude-sonnet-5-20260101", 10, 10, 10 * 2000 + 10 * 10000),
    ("claude-opus-5", 1, 1, 5000 + 25000),
    ("some-model-nobody-priced", 100, 0, 100 * 1000),     # falls back to the CHEAPEST family
    ("", 0, 0, 0),
])
def test_nanodollar_pricing_matches_the_products_own_table(model, tin, tout, expected):
    assert SD.token_cost_nano(model, tin, tout) == expected


# ── founder-visible regressions ─────────────────────────────────────────────────────────────

def test_a_card_and_an_unrelated_quiet_event_are_not_a_regression(ro):
    """THE DEFECT. The regression query joined `cards` to `graph_facts` on
    `f.created_by_event_id is not null` — which relates a card to nothing at all — so EVERY card
    paired with EVERY un-signalled event in the window, and the gate's last line failed for any
    tenant that had both. A regression has to be a card whose own subject lost its evidence."""
    report = SD.build_report(ro, org_id=CARDS, since=SINCE, until=NOW)
    assert report.founder_visible_regressions == ()
    assert dict((k, ok) for k, _, _, ok in report.checks)["founder_visible_regressions"] is True


def test_a_card_whose_own_subject_lost_its_evidence_IS_a_regression(ro, engine):
    """The other half: the check must still catch the thing it is for. A founder is looking at a
    card built on a fact from an event L1 v2 produced no signal for — remove the old path and
    that card stops existing."""
    with engine.begin() as conn:
        _fact(conn, CARDS, "cards_quiet", field="commitment.action", subject="node_card")
    try:
        report = SD.build_report(ro, org_id=CARDS, since=SINCE, until=NOW)
        assert report.founder_visible_regressions == ("card_1",)
        assert dict((k, ok) for k, _, _, ok
                    in report.checks)["founder_visible_regressions"] is False
    finally:
        with engine.begin() as conn:
            conn.execute(text("delete from graph_facts where fact_version_id = :v"),
                         {"v": f"fv:{CARDS}:cards_quiet:commitment.action"})


# ── activation, reported as a precondition ──────────────────────────────────────────────────

def test_a_tenant_on_the_lane_for_the_whole_window_says_so(clean):
    assert clean.activation.live is True and clean.activation.notes == "design partner"


def test_a_pilot_switched_off_mid_window_is_not_live(messy):
    """The reason `deactivate_semantic` stamps the row instead of deleting it (migration 0090):
    without the stamp this report would present a partial window as a full shadow run."""
    assert messy.activation.live is False and messy.activation.disabled_at is not None


def test_an_org_with_no_activation_row_can_never_pass_the_gate(ro, engine):
    """The honest answer for every org on every deployment today. "Built but not enabled is not
    done" — an inactive tenant has not been measured, so its zeros are not a pass."""
    org = "org_shadow_never"
    with engine.begin() as conn:
        _org(conn, org)
        _wipe(conn, org)
    try:
        report = SD.build_report(ro, org_id=org, since=SINCE, until=NOW)
        assert report.activation.live is False
        assert report.passed is False
        assert "NO live row in l1_semantic_activation" in SD.render(report)
    finally:
        with engine.begin() as conn:
            _wipe(conn, org)


# ── the verdict, and the CLI that prints it ─────────────────────────────────────────────────

def test_a_clean_pilot_week_passes_every_line_of_the_gate(clean):
    assert [k for k, _, _, ok in clean.checks if not ok] == []
    assert clean.passed is True


def test_the_messy_week_fails_three_gates_for_three_different_reasons(messy):
    assert [k for k, _, _, ok in messy.checks if not ok] == [
        "events_processed_by_both", "unverified_span_rate", "llm_cost_per_1000_events"]
    assert messy.passed is False


def test_the_report_renders_the_misses_where_an_operator_will_read_them(messy):
    out = SD.render(messy)
    assert "signals v1 found that L1 v2 did not:" in out
    assert "below_floor" in out and "not_extracted" in out
    assert "VERDICT: FAIL" in out


def test_the_cli_exits_zero_only_when_the_gate_passes(capsys):
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    assert SD.main(["--org", CLEAN, "--days", "7", "--database-url", url]) == 0
    assert SD.main(["--org", MESSY, "--days", "7", "--database-url", url]) == 1
    assert "G10 shadow diff" in capsys.readouterr().out


def test_the_json_form_carries_every_number_the_text_form_shows(clean):
    payload = clean.as_dict()
    assert payload["v1_processed"] == clean.v1_processed
    assert payload["span_counters"]["total"] == clean.span_counters.total_spans
    assert len(payload["misses"]) == len(clean.misses)
    assert json.loads(json.dumps(payload))["passed"] is True

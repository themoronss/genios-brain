"""G2 · the acceptance report — its derivations, and its refusal to write.

    python scripts/l1_s1_report.py --org <pilot> --since 30d

The script cannot be run end-to-end against a pilot yet — none is wired at W2 — so what is
testable is everything except the pilot: the three metrics against seeded rows, the arithmetic
that decides whether a document is silently empty, the offset round-trip that decides whether an
evidence span can be trusted, and the two safety properties that matter more than any number the
report prints. A gate report is exactly the kind of "harmless" script that inherits `.env` and
opens production, so both are asserted here: the target must be NAMED, and the transaction is
declared `read only` at the server rather than by good intentions.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.documents.base import DocumentStatus
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.platform.db import get_engine
from scripts._db import TARGET_URL_ENV, UnsafeDatabaseTarget
from scripts.l1_s1_report import (build_report, document_body, main, offset_map_failures,
                                  parse_since, render, structural_token_failures,
                                  _read_only_connection)

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
ORG = "org_l1_s1_report_pg"
KEY = "sxpepd0Y2jFCXW0Vjbb-EK_dQ9Yv9keeVdOOoNTk0eE="
_TABLES = ("prepared_content", "document_jobs", "raw_payloads", "parked_events", "source_events")


# ── the window ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value, expected", [
    ("30d", timedelta(days=30)),
    ("1d", timedelta(days=1)),
    ("12h", timedelta(hours=12)),
    ("90m", timedelta(minutes=90)),
    ("  7D  ", timedelta(days=7)),
])
def test_the_window_accepts_whole_units(value, expected):
    assert parse_since(value) == expected


@pytest.mark.parametrize("value", ["30", "1.5d", "30 days", "d", "-3d", "", "30w"])
def test_the_window_refuses_anything_else(value):
    with pytest.raises(argparse.ArgumentTypeError, match="whole number"):
        parse_since(value)


# ── metric 2's derivation ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("clean_text, expected, why", [
    ("MSA-signed.pdf\n\nTotal $84,000.", "Total $84,000.", "the document's own text"),
    ("MSA-signed.pdf\n\n", "", "a filename with nothing after it IS an empty document"),
    ("MSA-signed.pdf\n\n   \n ", "   \n ", "whitespace is returned; the caller strips it"),
    ("MSA-signed.pdf", "", "no blank line at all — nothing but the filename survived"),
    ("", "", "no text at all"),
    ("deck.pdf\n\npage one\n\npage two", "page one\n\npage two",
     "only the FIRST blank line separates the prepended filename"),
])
def test_the_document_body_is_the_text_after_the_prepended_filename(clean_text, expected, why):
    assert document_body(clean_text) == expected, why


# ── metric 3's derivation ────────────────────────────────────────────────────────────────────

def _prepared(source: str):
    p = preprocess(source, event_id="evt_1")
    return p.clean_text, [s.model_dump() for s in p.offset_map], \
        [m.model_dump() for m in p.masked_spans]


def test_a_real_offset_map_round_trips():
    clean, offsets, masked = _prepared("Signed by ABCDE1234F on the 3rd. Total $84,000.")
    assert "[PAN]" in clean
    assert offset_map_failures(clean, offsets, masked) == []


def test_an_empty_document_needs_no_map():
    assert offset_map_failures("", [], []) == []


def test_a_missing_map_over_real_text_is_a_failure():
    assert offset_map_failures("hello", [], []) == ["no offset map for non-empty clean_text"]


@pytest.mark.parametrize("mutate, fragment", [
    (lambda segs: segs.__setitem__(0, {**segs[0], "prep_start": 1}), "is not tiled"),
    (lambda segs: segs.__setitem__(0, {**segs[0], "prep_end": segs[0]["prep_end"] - 1}),
     "length drift"),
    (lambda segs: segs.__setitem__(-1, {**segs[-1], "prep_end": 9_999}), "past the"),
    (lambda segs: segs.__setitem__(-1, {**segs[-1], "src_start": 0, "src_end": 1}),
     "go backwards"),
    (lambda segs: segs.pop(), "covers"),
])
def test_every_kind_of_offset_drift_is_reported(mutate, fragment):
    clean, offsets, masked = _prepared("Signed by ABCDE1234F today. Total $84,000 annually.")
    mutate(offsets)
    failures = offset_map_failures(clean, offsets, masked)
    assert any(fragment in f for f in failures), failures


def test_a_masked_token_that_no_longer_matches_the_text_is_caught():
    """The actual round-trip: the map says these characters are `[PAN]`; the text has to agree."""
    clean, offsets, masked = _prepared("Signed by ABCDE1234F today.")
    masked[0] = {**masked[0], "token": "[AADHAAR]"}
    failures = offset_map_failures(clean, offsets, masked)
    assert any("does not round-trip" in f for f in failures), failures


def test_a_masked_segment_with_no_recorded_token_is_caught():
    clean, offsets, masked = _prepared("Signed by ABCDE1234F today.")
    failures = offset_map_failures(clean, offsets, [])
    assert any("no recorded token" in f for f in failures), failures


class _Token:
    def __init__(self, raw, start, end):
        self.token_type, self.raw = "currency_token", raw
        self.start_offset, self.end_offset = start, end


class _Tokens:
    def __init__(self, tokens):
        self.tokens = tokens


def test_structural_tokens_from_the_real_scanner_round_trip():
    text_ = "Renewal on 12 March 2026 for $84,000 — invoice INV-2291, see https://acme.io/msa"
    assert structural_token_failures(text_) == []


def test_a_token_whose_offsets_point_elsewhere_is_reported():
    """A checker that has only ever seen a correct scanner is a checker nobody has seen fail."""
    text_ = "Total $84,000 due."
    drifted = structural_token_failures(text_, scan=lambda t: _Tokens([_Token("$84,000", 0, 7)]))
    assert len(drifted) == 1 and "token says '$84,000'" in drifted[0]


def test_a_scanner_that_finds_nothing_reports_nothing():
    assert structural_token_failures("hello", scan=lambda t: _Tokens([])) == []


# ── the safety properties ────────────────────────────────────────────────────────────────────

def test_the_report_refuses_to_run_without_a_named_database(monkeypatch):
    """No `--database-url`, no `GENIOS_TARGET_DATABASE_URL`, and deliberately no fallback to the
    configured database — which on a developer machine is the production tenant."""
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    with pytest.raises(UnsafeDatabaseTarget, match=TARGET_URL_ENV):
        main(["--org", "org_pilot"])


def test_the_script_never_names_the_configured_database():
    """The neighbouring guard (`tests/test_scripts_db_guard.py`) asserts this over every script;
    restated here so a change to THIS file fails in THIS file."""
    import pathlib
    source = (pathlib.Path(__file__).resolve().parents[3] / "scripts" / "l1_s1_report.py"
              ).read_text()
    assert "get_settings()" + ".database_url" not in source


def test_the_renderer_says_when_nothing_was_measured():
    """An empty org must not read as a pass. Zeros with no events are an absence of observation."""
    from scripts.l1_s1_report import GateMetric, S1Report
    empty = S1Report(org_id="org_pilot", since=NOW - timedelta(days=30), until=NOW,
                     events_in_window=0,
                     metrics=(GateMetric(key="k", title="t", observed=0),))
    out = render(empty)
    assert "absence of observation" in out and "PASS" in out


# ── against a real database ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres report tests skipped")
    eng = get_engine(live_db_url)
    _reset(eng)
    _seed_org(eng)
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    """Data first, then the org row itself.

    Leaving the org behind would be a slow-acting bug in somebody else's file: several fixtures in
    this suite start with `select id from orgs limit 1`, and an empty org that outlives its test is
    a plausible answer to that query — the next module then seeds nothing, asserts on nothing, and
    passes for a reason its author never wrote down."""
    with eng.begin() as c:
        for table in _TABLES:
            c.execute(text(f"delete from {table} where org_id=:o"), {"o": ORG})
        c.execute(text("delete from orgs where id=:o"), {"o": ORG})


def _seed_org(eng) -> None:
    with eng.begin() as c:
        if c.execute(text("select 1 from orgs where id=:o"), {"o": ORG}).scalar():
            return
        required = c.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": ORG}
        for row in required:
            cols.append(row.column_name)
            ph.append(f":{row.column_name}")
            kind = row.data_type
            vals[row.column_name] = ("2026-01-01T00:00:00Z" if ("time" in kind or "date" in kind)
                                     else 0 if ("int" in kind or "numeric" in kind)
                                     else False if kind == "boolean"
                                     else "{}" if kind in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                       "on conflict (id) do nothing"), vals)


def _document_event(eng, *, event_id: str, body: str, status: str, captured=None) -> None:
    """A document event with a prepared seam and a provenance row — the pair metric 2 reads.

    Seeded relative to the REAL clock, not to `NOW`: the CLI computes its own `datetime.now`, so a
    fixture pinned to a fixed date falls outside `--since 30d` the moment the calendar moves past
    it — and the report would then pass for the one reason a report must never pass, which is that
    it looked at nothing.
    """
    captured = captured or (datetime.now(timezone.utc) - timedelta(hours=1))
    prepared = preprocess(f"MSA-signed.pdf\n\n{body}" if body else "MSA-signed.pdf\n\n",
                          event_id=event_id)
    with eng.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
            "(:e, :o, 'conn_1', 'gmail', 'email_attachment', :soid, :d, cast('{}' as jsonb), "
            ":at, :at, 'emitted')"),
            {"e": event_id, "o": ORG, "soid": f"m1::{event_id}", "d": f"dedup_{event_id}",
             "at": captured})
        c.execute(text(
            "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text, "
            "language, masked_spans, protected_spans, offset_map, preprocessor_version, "
            "created_at) values (:e, :o, :pid, :txt, :lang, cast(:ms as jsonb), "
            "cast('[]' as jsonb), cast(:om as jsonb), 'prep-1', :at)"),
            {"e": event_id, "o": ORG, "pid": prepared.prepared_content_id,
             "txt": prepared.clean_text, "lang": prepared.language,
             "ms": json.dumps([m.model_dump() for m in prepared.masked_spans]),
             "om": json.dumps([s.model_dump() for s in prepared.offset_map]), "at": captured})
        c.execute(text(
            "insert into document_jobs (id, org_id, event_id, format, native_parse_used, "
            "ocr_pages, status, created_at) values (:id, :o, :e, 'application/pdf', true, 1, "
            ":s, :at)"),
            {"id": f"doc_{event_id}", "o": ORG, "e": event_id, "s": status, "at": captured})


@pytest.mark.pg
def test_the_three_metrics_against_seeded_rows(engine, live_db_url):
    now = datetime.now(timezone.utc)
    _document_event(engine, event_id="evt_good", body="Total $84,000 annually.",
                    status=DocumentStatus.ACCEPTED.value)
    _document_event(engine, event_id="evt_silent", body="",
                    status=DocumentStatus.ACCEPTED.value)          # empty AND unexplained
    _document_event(engine, event_id="evt_explained", body="",
                    status=DocumentStatus.OCR_FAILED.value)        # empty, but it says why
    with engine.begin() as c:
        c.execute(text(
            "insert into parked_events (event_id, org_id, source, reason_code, status, "
            "created_at) values ('evt_silent', :o, 'gmail', 'DOC-05', 'pending', :at)"),
            {"o": ORG, "at": now - timedelta(hours=9)})

    conn = _read_only_connection(engine)
    try:
        report = build_report(conn, org_id=ORG, since=now - timedelta(days=30), now=now)
    finally:
        conn.close()

    by_key = {m.key: m for m in report.metrics}
    assert report.events_in_window == 3
    assert by_key["attachments_stuck_in_needs_refetch"].observed == 1
    assert by_key["empty_documents_without_marker"].observed == 1
    assert "evt_silent" in by_key["empty_documents_without_marker"].sample[0]
    assert by_key["structural_offset_roundtrip_failures"].observed == 0
    assert by_key["structural_offset_roundtrip_failures"].scanned == 3
    assert report.passed is False


@pytest.mark.pg
def test_a_corrupted_offset_map_is_caught_by_the_round_trip(engine, live_db_url):
    _document_event(engine, event_id="evt_drift", body="Signed by ABCDE1234F for $84,000.",
                    status=DocumentStatus.ACCEPTED.value)
    drifted = json.dumps([{"prep_start": 0, "prep_end": 5, "src_start": 0, "src_end": 99,
                           "masked": False}])
    with engine.begin() as c:
        c.execute(text("update prepared_content set offset_map = cast(:om as jsonb) "
                       "where event_id='evt_drift'"), {"om": drifted})
    now = datetime.now(timezone.utc)
    conn = _read_only_connection(engine)
    try:
        report = build_report(conn, org_id=ORG, since=now - timedelta(days=30), now=now)
    finally:
        conn.close()
    metric = {m.key: m for m in report.metrics}["structural_offset_roundtrip_failures"]
    assert metric.observed == 1 and "evt_drift" in metric.sample[0]


@pytest.mark.pg
def test_a_clean_org_passes_every_metric(engine, live_db_url):
    _document_event(engine, event_id="evt_clean", body="Total $84,000 annually.",
                    status=DocumentStatus.ACCEPTED.value)
    now = datetime.now(timezone.utc)
    conn = _read_only_connection(engine)
    try:
        report = build_report(conn, org_id=ORG, since=now - timedelta(days=30), now=now)
    finally:
        conn.close()
    assert report.passed is True
    assert all(m.observed == 0 for m in report.metrics)


@pytest.mark.pg
def test_the_connection_the_report_runs_on_refuses_writes(engine, live_db_url):
    """`set transaction read only` is enforced by PostgreSQL, so a future metric that tried to
    write a scratch table would fail here rather than in production."""
    conn = _read_only_connection(engine)
    try:
        with pytest.raises(Exception, match="read-only"):
            conn.execute(text("insert into parked_events (event_id, org_id, reason_code) "
                              "values ('evt_nope', :o, 'DOC-05')"), {"o": ORG})
    finally:
        conn.close()


@pytest.mark.pg
def test_the_cli_reports_and_exits_on_the_verdict(engine, live_db_url, capsys, monkeypatch):
    _document_event(engine, event_id="evt_cli", body="", status=DocumentStatus.ACCEPTED.value)
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    code = main(["--org", ORG, "--since", "30d", "--database-url", live_db_url])
    out = capsys.readouterr().out
    assert code == 1, "a failing metric is a non-zero exit"
    assert "documents with empty text and no ocr_failed marker: 1" in out
    assert "VERDICT   FAIL" in out


@pytest.mark.pg
def test_an_empty_org_can_be_made_to_fail_loudly(engine, live_db_url, capsys, monkeypatch):
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    assert main(["--org", ORG, "--database-url", live_db_url]) == 0
    assert main(["--org", ORG, "--require-data", "--database-url", live_db_url]) == 2
    assert "nothing was measured" in capsys.readouterr().err


@pytest.mark.pg
def test_the_json_form_carries_every_metric(engine, live_db_url, capsys, monkeypatch):
    _document_event(engine, event_id="evt_json", body="Total $84,000.",
                    status=DocumentStatus.ACCEPTED.value)
    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    main(["--org", ORG, "--json", "--database-url", live_db_url])
    payload = json.loads(capsys.readouterr().out.split("\n", 2)[2])
    assert payload["passed"] is True
    # Metric 2 (`recapture_parks_stuck`) joined the report when the parked queue turned out to
    # have a THIRD drain class: `visibility_unknown` and `MUT-01` are held for reasons no payload
    # and no provider can answer, they were in no class at all, and this report — the G2 surface
    # — could not see them. The order is the order `build_report` assembles them in.
    assert [m["key"] for m in payload["metrics"]] == [
        "attachments_stuck_in_needs_refetch", "recapture_parks_stuck",
        "empty_documents_without_marker", "structural_offset_roundtrip_failures"]

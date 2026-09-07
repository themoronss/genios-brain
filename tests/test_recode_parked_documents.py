"""`scripts/recode_parked_documents.py` — correcting the parks the old skip mis-filed.

    pytest tests/test_recode_parked_documents.py -q      (needs GENIOS_TEST_DATABASE_URL)

The connector fix stops NEW screenshots being filed as terminally `unsupported`. It does nothing
for the rows already written, and those rows are the ones production is holding: a park is a
permanent record, and one that says *nothing can ever read this* about a scanned PO is a backlog
nobody will ever look at again.

Three behaviours, and the last two are what make the script safe to point at a live tenant:

* a file WITH pages moves `DOC-02` -> `DOC-06`, which `parked/drain.NEEDS_REFETCH` will pick up
  the day an OCR engine is wired;
* a file with no pages is left exactly as it is — the code was right about a .zip;
* a park whose payload has expired is COUNTED and left alone. An unreadable payload is not
  evidence that the file had no pages, and a script that guessed would be inventing the very fact
  it exists to correct.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform.crypto import encrypt, generate_key
from genios_engine.platform.db import get_engine
from scripts import recode_parked_documents as script

ORG = "org_recode"
KEY = generate_key()
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)

#: (event id, filename, mime) — one of each class the script has to tell apart.
SCAN = ("evt_recode_scan", "invoice-scan.png", "image/png")
PDF = ("evt_recode_pdf", "PO-8841.pdf", "application/octet-stream")   # pages by EXTENSION
ZIP = ("evt_recode_zip", "export.zip", "application/zip")
GONE = ("evt_recode_gone", "expired.png", "image/png")                # payload no longer retained


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the re-code script writes real rows")
    return live_db_url


@pytest.fixture
def seeded(pg_url):
    engine = get_engine(pg_url)

    def wipe(conn):
        for table in ("parked_events", "raw_payloads", "source_events"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})

    with engine.begin() as conn:
        wipe(conn)
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                          f"({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{n: "scratch" for n in names}})
        for event_id, filename, mime in (SCAN, PDF, ZIP, GONE):
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, 'con_recode', 'gmail', 'email_attachment', :e, :e, "
                "cast('{}' as jsonb), :at)"), {"e": event_id, "o": ORG, "at": NOW})
            conn.execute(text(
                "insert into parked_events (event_id, org_id, source, reason_code, stage, "
                "trace, status) values (:e, :o, 'gmail', 'DOC-02', 'S1', "
                "cast('[]' as jsonb), 'pending')"), {"e": event_id, "o": ORG})
            if event_id == GONE[0]:
                continue          # the TTL already took this one's body
            conn.execute(text(
                "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                "expires_at) values (:id, :o, :e, 'application/json', :enc, :exp)"),
                {"id": f"pay_{event_id}", "o": ORG, "e": event_id,
                 "enc": encrypt(json.dumps({"subject": filename, "mime": mime, "body": ""}), KEY),
                 "exp": NOW + timedelta(days=30)})
    yield engine, pg_url
    with engine.begin() as conn:
        wipe(conn)


def _run(pg_url: str, *extra: str) -> None:
    import sys
    argv = ["recode_parked_documents.py", "--database-url", pg_url, "--org", ORG,
            "--crypto-key", KEY, *extra]
    old = sys.argv
    sys.argv = argv
    try:
        assert script.main() == 0
    finally:
        sys.argv = old


def _codes(engine) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(text("select event_id, reason_code from parked_events "
                                 "where org_id = :o"), {"o": ORG}).fetchall()
    return {r.event_id: r.reason_code for r in rows}


def test_a_dry_run_writes_nothing(seeded):
    engine, pg_url = seeded
    _run(pg_url)
    assert set(_codes(engine).values()) == {"DOC-02"}, "the dry run wrote to the database"


def test_apply_moves_only_the_files_that_have_pages(seeded):
    engine, pg_url = seeded
    _run(pg_url, "--apply")
    codes = _codes(engine)
    assert codes[SCAN[0]] == "DOC-06", "a screenshot is readable in principle and stayed terminal"
    assert codes[PDF[0]] == "DOC-06", "a .pdf named by extension was judged by its mime alone"
    assert codes[ZIP[0]] == "DOC-02", "a .zip has no pages and the original code was right"
    assert codes[GONE[0]] == "DOC-02", "a row with no payload was re-coded on a guess"


def test_running_it_twice_changes_nothing_the_second_time(seeded):
    """Idempotent by its own `where reason_code = 'DOC-02'`: the second pass finds the moved rows
    already gone from its selection, so an operator can re-run it without thinking about it."""
    engine, pg_url = seeded
    _run(pg_url, "--apply")
    first = _codes(engine)
    _run(pg_url, "--apply")
    assert _codes(engine) == first


def test_a_park_a_human_already_acted_on_is_left_alone(seeded):
    """`status='pending'` only. A promoted or dead-lettered park is somebody's decision, and
    re-coding it would overwrite that decision with a guess about a code they never saw."""
    engine, pg_url = seeded
    with engine.begin() as conn:
        conn.execute(text("update parked_events set status = 'dead_letter' "
                          "where org_id = :o and event_id = :e"), {"o": ORG, "e": SCAN[0]})
    _run(pg_url, "--apply")
    assert _codes(engine)[SCAN[0]] == "DOC-02"


def test_the_moved_code_is_one_the_drain_will_actually_pick_up():
    """The whole point of the move: `DOC-06` is in `NEEDS_REFETCH`, so these rows re-enter the
    ladder the day OCR is wired. A code outside that set would be a tidier label on the same
    permanent backlog."""
    from genios_engine.capture.parked.drain import NEEDS_REFETCH
    assert script.TO_CODE in NEEDS_REFETCH

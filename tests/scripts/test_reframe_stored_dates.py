"""`03` F148's stored half · the dates a late read stored are re-framed to when the mail was written.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_reframe_stored_dates.py -q

`yc2_w27_align` M34.C2.L-interface.V1.U16. Until U13/U14 Layer 1 resolved a mail's relative dates
against the sync that read it; the fix makes new reads right, and `scripts/reframe_stored_dates.py`
re-frames what late reads already stored in `l1_extraction_results.output`: each date and each
promise's due framed more than a day after its mail, resolved again by ALG-09 against the mail's own
time, in the org's zone. A dry run counts by month and prints no words; `--apply` rewrites only those,
and a second run finds nothing.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg
WRITTEN = datetime(2026, 7, 16, 7, 10, tzinfo=timezone.utc)        # Thursday
READ_LATE = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
PHRASE = "by Friday"


def _module():
    import importlib
    return importlib.import_module("scripts.reframe_stored_dates")


def _date(frame: datetime) -> dict:
    from genios_engine.capture.validate.dates import resolve_date
    from genios_engine.contracts.evidence import EvidenceSpan
    span = EvidenceSpan(source_ref="prepared_content:pc_x", quote=PHRASE, start_offset=0,
                        end_offset=len(PHRASE))
    return resolve_date(PHRASE, eval_time=frame, tz="UTC", evidence=[span]).model_dump(mode="json")


@pytest.fixture
def tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    org = f"org_reframe_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name, timezone) values (:o, 'reframe', 'UTC')"), {"o": org})
    yield engine, org, url
    with engine.begin() as c:
        for table in ("l1_extraction_results", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _stored(engine, org, *, frame: datetime, profile: str | None = "email") -> str:
    """One mail written on WRITTEN, and its extraction framed at `frame`: a date and a promise."""
    from genios_engine.contracts.source_event import compute_dedup_key
    mid = uuid.uuid4().hex[:10]
    output = {"intent": "commit", "dates_mentioned": [_date(frame)],
              "commitments": [{"actor": "Arjun Rao", "action": "send the deck", "due": _date(frame),
                               "is_conditional": False}]}
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, outcome) values "
            " (:e, :o, 'con_x', 'gmail', 'email_message', :mid, :dk, cast(:a as jsonb), :at, :cap, "
            " 'emitted')"),
            {"e": f"evt_{mid}", "o": org, "mid": mid, "dk": compute_dedup_key("gmail", "email_message", mid),
             "a": json.dumps({"email": "nandini@vertexangels.test"}), "at": WRITTEN, "cap": frame})
        c.execute(text(
            "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
            " input_tokens, output_tokens, model_snapshot, profile_id, tier) values "
            " (:k, :o, :e, cast(:out as jsonb), 0, 0, 'm', :p, 'T2')"),
            {"k": f"pk_{mid}", "o": org, "e": f"evt_{mid}", "out": json.dumps(output), "p": profile})
    return f"evt_{mid}"


def _outputs(engine, org) -> dict:
    with engine.connect() as c:
        return {r.event_id: r.output for r in c.execute(
            text("select event_id, output from l1_extraction_results where org_id = :o"), {"o": org})}


def test_the_dry_run_counts_and_writes_nothing(tenant, capsys):
    engine, org, url = tenant
    _stored(engine, org, frame=READ_LATE)
    _stored(engine, org, frame=WRITTEN + timedelta(minutes=5))      # read as it arrived
    before = _outputs(engine, org)
    assert _module().main(["--database-url", url, "--org", org]) == 0
    out = capsys.readouterr().out
    assert f"{org}: 1 stored extraction(s)" in out and "1 date(s), 1 promise(s)" in out
    assert "2026-07 1" in out and "DRY RUN" in out
    assert PHRASE not in out, "a mail's words never leave the database"
    assert _outputs(engine, org) == before


def test_apply_reframes_a_late_read_to_the_day_its_mail_was_written(tenant, capsys):
    engine, org, url = tenant
    late = _stored(engine, org, frame=READ_LATE)
    on_time = _stored(engine, org, frame=WRITTEN + timedelta(minutes=5))
    legacy = _stored(engine, org, frame=READ_LATE, profile=None)    # L2's own cache row: not L1's
    before = _outputs(engine, org)
    assert _module().main(["--database-url", url, "--org", org, "--apply"]) == 0
    assert "REFRAMED 1 stored extraction(s)" in capsys.readouterr().out
    after = _outputs(engine, org)
    friday = _date(WRITTEN)
    assert after[late]["dates_mentioned"][0] == friday                   # Friday 17 Jul, not 2 Oct
    assert after[late]["commitments"][0]["due"] == friday
    assert after[late]["intent"] == "commit", "nothing else in the row moves"
    assert after[on_time] == before[on_time] and after[legacy] == before[legacy]
    assert _module().main(["--database-url", url, "--org", org, "--apply"]) == 0
    assert "REFRAMED 0" in capsys.readouterr().out, "a second run finds nothing"

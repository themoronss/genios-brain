"""STEP-17 §3.4 · the health gate says NO DATA when it judged nothing — never PASS.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q tests/scripts/test_pipeline_health_says_no_data.py

`yc2_w27_s17` M40.C3.L-contract.V0.U01. ⛔ `03` F24: the 24-hour ceiling check passed while the lane
it guards had made no call at all. Measured 2026-10-12 on a tenant with NO DATA AT ALL: **17 of the
gate's 19 checks printed PASS** — six of them saying *"not exercised"* or *"skipped"* in the same
breath. A pass over an empty table is not a pass.

A check now has three verdicts. `ok` still answers *"did it fail?"* — every existing reader of `.ok`
(the golden replays among them) keeps its meaning — and `no_data` answers *"did it judge anything?"*:
PASS, FAIL, or NO DATA. A FAIL exits 1; NO DATA is printed and counted apart, and is never a pass.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from scripts import pipeline_health as ph

EMPTY = "org_s17_health_empty"

#: The two checks a tenant with nothing fails, by design: no brief is a failure (no prompt carries
#: one), and memory that reaches back nowhere is short of any window.
FAIL_ON_NOTHING = {"the company brief exists and is current",
                   "memory reaches back as far as the Gmail connection's window"}


# ── the verdict: hermetic ──────────────────────────────────────────────────────────────────────

def _check(ok, no_data=False, name="n"):
    return ph.Check(name=name, ok=ok, measured="m", expected="e", fix="f", no_data=no_data)


def test_three_verdicts():
    assert _check(True).verdict == ph.PASS
    assert _check(False).verdict == ph.FAIL
    assert _check(True, no_data=True).verdict == ph.NO_DATA
    assert _check(False, no_data=True).verdict == ph.FAIL, "a failure is never hidden as no data"


def _main(monkeypatch, capsys, results, *argv):
    import genios_engine.platform.db as db
    monkeypatch.setattr(ph, "resolve_database_url", lambda *a, **k: "postgresql://scratch/x")
    monkeypatch.setattr(db, "get_engine", lambda url: SimpleNamespace())
    monkeypatch.setattr(ph, "read_only_connection", lambda engine: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(ph, "run", lambda *a, **k: list(results))
    monkeypatch.setattr(sys, "argv", ["pipeline_health.py", "--org", "o", *argv])
    code = ph.main()
    return code, capsys.readouterr().out


def test_no_data_is_printed_as_such_and_is_not_a_failure(monkeypatch, capsys):
    code, out = _main(monkeypatch, capsys,
                      [_check(True, name="a"), _check(True, no_data=True, name="b")])
    assert code == 0
    assert "PASS     a" in out and "NO DATA  b" in out
    assert "1/2 checks passed, 1 with no data, 0 failed" in out


def test_a_failure_still_exits_one(monkeypatch, capsys):
    code, out = _main(monkeypatch, capsys,
                      [_check(False, name="a"), _check(True, no_data=True, name="b")])
    assert code == 1
    assert "FAIL     a" in out and "0/2 checks passed, 1 with no data, 1 failed" in out


# ── every check on a tenant with nothing: real Postgres ────────────────────────────────────────

@pytest.fixture
def empty(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the checks read real tables")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": EMPTY})
        c.execute(text("insert into orgs (id, name) values (:o, 'Nothing Yet')"), {"o": EMPTY})
    with eng.connect() as c:
        yield c
        c.rollback()
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": EMPTY})


def test_a_tenant_with_nothing_passes_nothing(empty):
    """⛔ THE INVARIANT. On a tenant with no rows at all, no check may say PASS: each says NO DATA,
    or FAILS because having nothing is itself the defect. A check added later that passes on
    nothing fails here."""
    results = ph.run(empty, EMPTY, hours=24, ceiling_bp=2000)
    assert len(results) == len(ph.CHECKS) + 2
    verdicts = {c.name: c.verdict for c in results}
    passed = sorted(name for name, v in verdicts.items() if v == ph.PASS)
    assert not passed, f"PASS on a tenant with no data: {passed}"
    assert {n for n, v in verdicts.items() if v == ph.FAIL} == FAIL_ON_NOTHING, verdicts


def test_a_check_with_something_to_judge_still_passes(empty):
    """The negative control: NO DATA must not swallow a real pass. One emitted, routed event and
    the routing check judges it."""
    empty.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, source_object_id, "
        "object_type, dedup_key, actor, occurred_at, outcome, route) values ('ev_s17_routed', :o, "
        "'conn_s17', 'gmail', 'm1', 'email_message', 'k_s17_routed', '{}', now(), 'emitted', "
        "'needs_extraction')"), {"o": EMPTY})
    check = ph.check_every_emitted_event_is_routed(empty, EMPTY)
    assert check.verdict == ph.PASS, check.measured
    empty.execute(text("update source_events set route = null where event_id = 'ev_s17_routed'"))
    assert ph.check_every_emitted_event_is_routed(empty, EMPTY).verdict == ph.FAIL


def test_work_named_in_motion_with_no_mail_yet_is_no_data(pg_store):
    """The second way the work check judged nothing and said PASS: the brief names a piece of work
    in motion, memory holds no mail with it yet — *"0 piece(s) of work in motion have mail"*."""
    import uuid
    from datetime import timedelta

    from genios_engine.platform import company_brief, company_brief_store
    from tests.context.workstream_world import T0, reset, tenant

    org = f"org_s17_motion_{uuid.uuid4().hex[:8]}"
    tenant(pg_store, org)
    try:
        with pg_store.engine.begin() as c:
            company_brief_store.add(c, org_id=org, section="in_motion",
                                    words="Raise · Kestrel Capital — engaged",
                                    domain="kestrelcap.test", address=None, kind="investor",
                                    decided_by="the founder", at=T0 - timedelta(days=30))
        company_brief.invalidate(org)
        with pg_store.engine.connect() as c:
            check = ph.check_every_piece_of_work_has_one_file(c, org)
            c.rollback()
        assert check.measured.startswith("0 piece(s) of work in motion have mail"), check.measured
        assert check.verdict == ph.NO_DATA
    finally:
        reset(pg_store, org)

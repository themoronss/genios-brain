"""STEP-03 · every archived mail can still be read — the receipt that holds the gate to its promise.

    pytest tests/platform/test_an_archived_mail_is_reviewable.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_an_archived_mail_is_reviewable.py -q

`platform/receipts.py` (tree `yc2_w27_s03/M21.C4.L-logic.V4.U04`). The gate no longer deletes what a
noise rule or the AI filter calls noise: it ARCHIVES it, and the whole value of an archive is that
the mail can be read when it turns out to matter — Boardy's introduction, a government portal's
update. An archived row with no body is a delete that says it is not one. So the receipt asks of
EVERY archived mail, whichever rule or judgment stopped it, inside the archive's own window
(`pipeline.ARCHIVED_PAYLOAD_TTL_DAYS`): one archived mail with no body fails it.

The sibling receipt about judged DROPS stays, unchanged: rows the gate dropped before the deploy
keep their 90-day bodies and are still asked about until they age out.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.pipeline import ARCHIVED_PAYLOAD_TTL_DAYS
from genios_engine.platform.receipts import Receipt, receipts

ARCHIVED_READABLE = "every archived mail can still be read"
JUDGED_DROPS = "every drop we might be wrong about can still be reviewed"
ORG = "org_archived_receipt"


def _receipt(claim: str = ARCHIVED_READABLE, org: str | None = "org_x") -> Receipt:
    return next(r for r in receipts(org) if r.claim == claim)


def test_the_receipt_exists_once_and_belongs_to_capture():
    from genios_engine.platform.receipt_coverage import RECEIPT_PACKAGE

    assert sum(r.claim == ARCHIVED_READABLE for r in receipts("org_x")) == 1
    assert RECEIPT_PACKAGE[ARCHIVED_READABLE][0] == "capture"


def test_it_asks_every_archived_mail_whatever_stopped_it():
    """A rule's archive and a judgment's archive are both a promise to keep the body — the
    receipt must not narrow to the judged codes the way the drop receipt (rightly) does."""
    sql = _receipt().sql
    assert "outcome = 'archived'" in sql
    assert "raw_payloads" in sql
    for code in ("llm_junk", "low_relevance", "N-02", "N-06"):
        assert f"'{code}'" not in sql, f"the receipt narrowed to {code}"


def test_the_window_is_the_archives_own():
    assert f"'{ARCHIVED_PAYLOAD_TTL_DAYS} days'" in _receipt().sql
    assert "captured_at" in _receipt().sql


def test_one_archived_mail_with_no_body_is_enough_to_fail():
    r = _receipt()
    assert r.expect(0) is True and r.expect(1) is False


def test_it_is_scoped_to_the_tenant():
    assert ":org" in _receipt().sql and ":org" not in _receipt(org=None).sql


def test_the_judged_drop_receipt_still_asks_about_the_rows_before_the_deploy():
    sql = _receipt(JUDGED_DROPS).sql
    assert "se.outcome='dropped'" in sql and "t.action='drop'" in sql


# ── against Postgres ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the receipt needs real Postgres")
    from genios_engine.platform.db import get_engine

    eng = get_engine(live_db_url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'ar@example.test')"),
                  {"o": ORG})
    yield eng
    _reset(eng)


def _reset(eng) -> None:
    with eng.begin() as c:
        for table in ("raw_payloads", "source_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _archived(eng, key: str, *, captured_at: datetime, with_body: bool) -> None:
    with eng.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, captured_at, outcome, attention, "
            "attention_reason, payload_ref) values (:e, :o, 'conn_gmail', 'gmail', 'email_message', "
            ":k, :d, cast('{}' as jsonb), :t, :t, 'archived', 'archive', 'N-02', :p)"),
            {"e": f"evt_{key}", "o": ORG, "k": key, "d": f"gmail:email_message:{key}",
             "t": captured_at, "p": f"pay_{key}"})
        if with_body:
            c.execute(text(
                "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
                "expires_at) values (:p, :o, :e, 'application/json', 'x', :exp)"),
                {"p": f"pay_{key}", "o": ORG, "e": f"evt_{key}",
                 "exp": captured_at + timedelta(days=ARCHIVED_PAYLOAD_TTL_DAYS)})


def _count(eng) -> int:
    with eng.connect() as c:
        return int(c.execute(text(_receipt(org=ORG).sql), {"org": ORG}).scalar())


@pytest.mark.pg
def test_an_archive_with_its_body_passes(engine):
    _archived(engine, "kept", captured_at=datetime.now(timezone.utc), with_body=True)
    assert _count(engine) == 0


@pytest.mark.pg
def test_an_archive_that_lost_its_body_fails(engine):
    _archived(engine, "kept", captured_at=datetime.now(timezone.utc), with_body=True)
    _archived(engine, "lost", captured_at=datetime.now(timezone.utc), with_body=False)
    assert _count(engine) == 1


@pytest.mark.pg
def test_an_archive_past_its_window_is_expected_to_have_no_body(engine):
    old = datetime.now(timezone.utc) - timedelta(days=ARCHIVED_PAYLOAD_TTL_DAYS + 2)
    _archived(engine, "aged", captured_at=old, with_body=False)
    assert _count(engine) == 0

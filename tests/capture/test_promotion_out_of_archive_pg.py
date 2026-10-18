"""STEP-05 · promotion out of the archive — by a named rule, a dry run first, then the ladder reads it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_promotion_out_of_archive_pg.py -q

`capture/landing/promote.promote_archived` (tree `yc2_w27_s05 · M23.C4.L-logic.V2.U02`). Boardy's
introductions are archived on their unsubscribe header (N-02); since STEP-05 an archive enters memory as
names and dates only, and promotion is how its words get read: by the rule that archived it, optionally
one sender's domain, back in the ledger as KEPT — and then the re-read queue files it for the ladder,
which reads it as a re-read the gate does not archive again.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.landing import promote, unread
from genios_engine.contracts.source_event import compute_dedup_key
from genios_engine.platform.crypto import encrypt

pytestmark = pytest.mark.pg

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
WORDS = "Pankaj, meet Meera"


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    return get_engine(live_db_url)


@pytest.fixture
def org(engine):
    from genios_engine.platform.config import get_settings
    org_id = f"org_promote_{uuid.uuid4().hex[:8]}"
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'promotion')"), {"o": org_id})
        c.execute(text("insert into l1_semantic_activation (org_id, enabled_at, enabled_by) "
                       "values (:o, :at, 'test')"), {"o": org_id, "at": NOW - timedelta(days=30)})
    yield org_id, get_settings().crypto_key
    with engine.begin() as c:
        for table in ("parked_events", "l1_extraction_results", "l2_processing_runs",
                      "raw_payloads", "source_events", "l1_semantic_activation"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org_id})
        c.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _archived(engine, org, *, sender: str, code: str = "N-02", outcome: str = "archived",
              expires: datetime = NOW + timedelta(days=150), day: int = 1,
              read: bool = False) -> str:
    org_id, key = org
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    at = NOW - timedelta(days=day)
    with engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, dedup_key, actor, occurred_at, captured_at, recipients, outcome, "
            " attention, attention_reason) values (:e, :o, 'con_x', 'gmail', 'email_message', :e, "
            " :dk, cast(:actor as jsonb), :at, :at, :rcp, :out, :att, :code)"),
            {"e": event_id, "o": org_id, "dk": compute_dedup_key("gmail", "email_message",
                                                                 event_id, None),
             "actor": json.dumps({"type": "external_contact", "email": sender}), "at": at,
             "rcp": ["meera@kite.test", "pankaj@saka.test"], "out": outcome,
             "att": "archive" if outcome == "archived" else "deep", "code": code})
        c.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at) "
            "values (:id, :o, :e, 'application/json', :enc, :exp)"),
            {"id": f"pay_{event_id}", "o": org_id, "e": event_id, "exp": expires,
             "enc": encrypt(json.dumps({"subject": "Intro", "body": WORDS}), key)})
        if read:
            c.execute(text("insert into l1_extraction_results (processing_key, org_id, event_id, "
                           "output, profile_id, tier) values (:k, :o, :e, cast('{}' as jsonb), "
                           "'email', 'T2')"), {"k": f"x_{event_id}", "o": org_id, "e": event_id})
    return event_id


def _rows(engine, org) -> dict[str, tuple]:
    with engine.connect() as c:
        return {r.event_id: (r.outcome, r.attention, r.attention_reason, r.route) for r in c.execute(
            text("select event_id, outcome, attention, attention_reason, route from source_events "
                 "where org_id = :o"), {"o": org[0]})}


@pytest.fixture
def mailbox(engine, org):
    return {"intro": _archived(engine, org, sender="hello@boardy.test", day=1),
            "nudge": _archived(engine, org, sender="Hello@Boardy.test", day=2),
            "expired": _archived(engine, org, sender="hello@boardy.test", day=200,
                                 expires=NOW - timedelta(days=20)),
            "other_sender": _archived(engine, org, sender="news@letters.test"),
            "other_rule": _archived(engine, org, sender="hello@boardy.test", code="N-06"),
            "kept": _archived(engine, org, sender="hello@boardy.test", outcome="emitted",
                              code="passed", read=True)}


def test_a_dry_run_counts_and_changes_nothing(engine, org, mailbox):
    before = _rows(engine, org)
    report = promote.promote_archived(engine, org[0], rule="N-02", sender_domain="boardy.test",
                                      now=NOW)
    assert (report.archived, report.unreadable, report.promoted) == (2, 1, 0)
    assert {s[0] for s in report.sample} == {mailbox["intro"], mailbox["nudge"]}
    assert all(len(s) == 3 and WORDS not in json.dumps(s) for s in report.sample)
    assert _rows(engine, org) == before


def test_apply_puts_back_only_what_the_rule_and_the_sender_name(engine, org, mailbox):
    report = promote.promote_archived(engine, org[0], rule="N-02", sender_domain="boardy.test",
                                      apply=True, now=NOW)
    assert report.promoted == 2
    rows = _rows(engine, org)
    for name in ("intro", "nudge"):
        assert rows[mailbox[name]] == ("emitted", "deep", "promoted:N-02", "needs_extraction")
    for name in ("expired", "other_sender", "other_rule"):
        assert rows[mailbox[name]][0] == "archived", name
    assert promote.promote_archived(engine, org[0], rule="N-02", sender_domain="boardy.test",
                                    apply=True, now=NOW).promoted == 0


def test_the_ladder_then_reads_what_was_promoted(engine, org, mailbox):
    promote.promote_archived(engine, org[0], rule="N-02", sender_domain="boardy.test",
                             apply=True, now=NOW)
    assert unread.queue_unread(engine, org[0], now=NOW) == 2
    due = {r.event_id for r in unread.find_parked_extractions(engine, org[0], now=NOW)}
    assert due == {mailbox["intro"], mailbox["nudge"]}


def test_a_rule_the_gate_never_archives_with_is_refused(engine, org):
    for rule in ("N-05", "W-01", "low_relevance", ""):
        with pytest.raises(ValueError, match="archives with"):
            promote.promote_archived(engine, org[0], rule=rule, now=NOW)


# ── STEP-07 · a sender the company brief names (`promote_named_sender`) ─────────────────────────

def test_a_named_sender_gets_back_its_archive_under_every_rule(engine, org, mailbox):
    """The connector's address names its domain: the N-02 intro and nudge AND the N-06 mail come
    back; another sender's, and an archive past its keep window, stay archived."""
    assert promote.promote_named_sender(engine, org[0], address="hello@boardy.test", now=NOW) == 3
    rows = _rows(engine, org)
    assert {rows[mailbox[n]][2] for n in ("intro", "nudge", "other_rule")} == {
        "promoted:N-02", "promoted:N-06"}
    for name in ("expired", "other_sender"):
        assert rows[mailbox[name]][0] == "archived", name


def test_a_public_mail_host_is_never_promoted_by_domain(engine, org):
    _archived(engine, org, sender="someone@gmail.com")
    before = _rows(engine, org)
    assert promote.promote_named_sender(engine, org[0], address="friend@gmail.com", now=NOW) == 0
    assert promote.promote_named_sender(engine, org[0], domain="gmail.com", now=NOW) == 0
    assert promote.promote_named_sender(engine, org[0], now=NOW) == 0
    assert _rows(engine, org) == before

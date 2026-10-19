"""L2 rebuild A4 — the History Assembler reads every comparable case in two queries, and says the same thing.

Before: two reads per case (the file's latest situation, its latest valid review) — up to ten a subject. Now one
read of each for all the cases. Each case must still carry ITS OWN latest situation and review, never another
file's, never an older one.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/l2/test_history_reads_every_case_at_once_pg.py -q
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text

from genios_engine.reason.l2.history import history_for

pytestmark = pytest.mark.pg

ORG = "org_l2_history_batch"
T = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)


@dataclass
class _File:
    file_id: str
    counterparty: str
    work_kind: str = "fundraise"
    last_touch: datetime | None = None
    first_touch: datetime | None = None
    events: tuple = ("e1",)
    whose_move: str | None = None
    open_asks: tuple = field(default_factory=tuple)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'H', 'h@example.test')"), {"o": ORG})
        for fid, sits, revs in (
            ("node_a", [("closed", T), ("active", T - timedelta(days=9))], [("advise", "send the deck", T)]),
            ("node_b", [("resolved", T - timedelta(days=1))],
             [("wait", "give it a week", T - timedelta(days=5)), ("nudge", "nudge Kiran", T - timedelta(days=2))]),
        ):
            for n, (status, seen) in enumerate(sits):
                c.execute(text(
                    "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
                    " situation_type, domain, status, last_seen_at) values (:s, :o, :c, :a, 'fundraise', 'admin', "
                    " :st, :ls)"), {"s": f"sit_{fid}_{n}", "o": ORG, "c": f"cor_{fid}_{n}", "a": fid, "st": status,
                                     "ls": seen})
            for n, (mode, move, at) in enumerate(revs):
                c.execute(text(
                    "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, dossier_digest, "
                    " status, reviewed_at, review) values (:o, :f, :fp, 'm', 'p', 'd', 'valid', :at, "
                    " cast(:r as jsonb))"),
                    {"o": ORG, "f": fid, "fp": f"fp_{fid}_{n}", "at": at,
                     "r": json.dumps({"mode": mode, "next_move": {"what": move}})})
    yield eng
    with eng.begin() as c:
        for table in ("context_situations", "expert_reviews"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_each_case_carries_its_own_latest_situation_and_review_in_two_reads(engine):
    files = [_File("node_a", "Pinewood", last_touch=T), _File("node_b", "Kestrel", last_touch=T - timedelta(days=1)),
             _File("node_x", "Self", last_touch=T)]
    statements = []
    with engine.connect() as conn:
        event.listen(conn, "before_cursor_execute", lambda *a: statements.append(a[2]))
        history = history_for(conn, ORG, files=files, work_kind="fundraise", exclude="node_x")
    cases = {c.case_id: c for c in history.cases}
    assert list(cases) == ["case:node_a", "case:node_b"], "most recently touched first; the subject excluded"
    assert cases["case:node_a"].outcome == "fundraise closed", "node_a's LATEST situation, not its older one"
    assert "last advised (2026-10-01): advise — send the deck" in cases["case:node_a"].summary
    assert cases["case:node_b"].outcome == "fundraise resolved"
    assert "nudge — nudge Kiran" in cases["case:node_b"].summary and "give it a week" not in cases["case:node_b"].summary
    assert len(statements) == 2, statements


def test_no_comparable_work_reads_nothing(engine):
    statements = []
    with engine.connect() as conn:
        event.listen(conn, "before_cursor_execute", lambda *a: statements.append(a[2]))
        history = history_for(conn, ORG, files=[_File("node_a", "P", work_kind="hiring")], work_kind="fundraise",
                              exclude=None)
    assert history.cases == () and statements == []

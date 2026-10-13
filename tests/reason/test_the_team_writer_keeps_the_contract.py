"""STEP-14 · the second card writer keeps the card contract — a P4 team or verify card that says what no card may is
never written, nor its moment.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_the_team_writer_keeps_the_contract.py -q

Tree `yc2_w27_s14` M43.C4.L-integration.V1.U03 (`reason/team/emit.emit_situation`; STEP-14 §8.4 item 6, s14-F10). The P4
team and verify cards go straight into `cards` (`_write_card`) — no renderer, no validator: production's *"Which is
right? Maria Exconde: party.role"* was one. They now pass the same contract the pipeline's cards pass
(`contracts/card_contract`) before anything is written, over the words the card AND its moment show, against their
own evidence: refused, no card, no moment, no situation row — counted per rule (`counts`), logged. A clipped quote
("…") is still its words.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.reason.team import emit as E

pytestmark = pytest.mark.pg

ORG = "org_s14_team_contract"
NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    _clean(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'tc@example.test')"), {"o": ORG})
        c.execute(text("insert into org_seats (org_id, seat_id, email, role) values (:o, 'seat_owner', "
                       "'tc@example.test', 'admin')"), {"o": ORG})
    yield eng
    _clean(eng)


def _clean(eng):
    with eng.begin() as c:
        for table in ("team_situations", "moments", "card_events", "cards", "signals", "org_seats"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _emit(engine, counts=None, **over):
    kw = dict(kind="team", key="deadline_at_risk:c1", seat_id="seat_owner", subject_node_ids=["node_c1"],
              headline="Anisha is away 14–16 Sep — “Send the ISO pack to Kestrel …” due 15 Sep",
              body="Shalini can cover. Anisha owes Kestrel “Send the ISO pack to Kestrel …” by 15 Sep.",
              actions=[], ttl_seconds=900, digest="d1", now=NOW,
              evidence=[{"kind": "away", "start": "2026-09-14", "end": "2026-09-16"},
                        {"kind": "commitment", "text": "Send the ISO pack to Kestrel before the audit",
                         "due": "2026-09-15"}])
    kw.update(over)
    return E.emit_situation(engine, None, ORG, counts=counts, **kw)


def _written(engine):
    with engine.connect() as c:
        return tuple(c.execute(text(f"select count(*) from {t} where org_id = :o"), {"o": ORG}).scalar()
                     for t in ("cards", "moments", "team_situations"))


def test_a_true_team_card_is_written_with_its_moment(engine):
    assert _emit(engine) is not None and _written(engine) == (1, 1, 1)


@pytest.mark.parametrize("over, rule", [
    ({"headline": "Which is right? Maria Exconde: party.role", "kind": "verify", "key": "discrepancy:d1"},
     "internal"),
    ({"body": "Shalini can cover. A dated payment obligation is open."}, "money"),
    ({"body": "Shalini can cover — due 19 Sep."}, "number"),
    ({"body": "Anisha said “we will miss the audit”."}, "quote"),
])
def test_a_team_card_that_breaks_the_contract_is_never_written(engine, over, rule):
    counts: dict = {}
    assert _emit(engine, counts, **over) is None
    assert _written(engine) == (0, 0, 0), "no card, no moment, no situation row"
    assert counts == {f"refused_contract:{rule}": 1}
    with engine.connect() as c:          # STEP-14 M43.C4.L-integration.V2.U05: kept where the health check reads it
        kept = c.execute(text("select writer, ref, rule from card_refusals where org_id = :o"), {"o": ORG}).all()
    key = over.get("key", "deadline_at_risk:c1")
    assert [tuple(r) for r in kept] == [("team", f"{over.get('kind', 'team')}:{key}", rule)]


def test_a_refusal_that_cannot_be_kept_still_refuses(engine, monkeypatch):
    def _down(*_a, **_k):
        raise RuntimeError("card_refusals is not there")
    monkeypatch.setattr(E.card_refusals, "record", _down)
    counts: dict = {}
    assert _emit(engine, counts, body="Shalini can cover — due 19 Sep.") is None
    assert _written(engine) == (0, 0, 0)
    assert counts == {"refused_contract:number": 1, "refusals_unkept": 1}


def test_money_in_its_evidence_lets_a_card_say_money(engine):
    money = [{"kind": "invoice", "amount": "₹50,000", "due": "2026-09-15"}]
    assert _emit(engine, body="The ₹50,000 invoice is due 15 Sep.", evidence=money,
                 headline="Kestrel's invoice is due 15 Sep") is not None
    assert _written(engine) == (1, 1, 1)

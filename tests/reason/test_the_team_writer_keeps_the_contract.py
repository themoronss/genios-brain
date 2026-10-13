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


# ── STEP-14 M43.C4.L-integration.V1.U03 (fix, 13 Oct) · the words code composed are held by what it composed them from ──
#
# Found by the root guard (`tests/test_meetings_pg.py`): every meeting follow-up was refused — *"Follow-ups from ISO
# audit — 1 for you"*, *"send the ISO pack (due 20 Sep)"* — because a follow-up's evidence names its facts (node,
# field) and does not hold their values, and its count of yours is code's. A readiness card's *"1 away"* was held only
# when the milestone's id happened to carry the digit. The writer hands the contract what its words were composed from
# (`corpus=`): never the words themselves.

def _followup_refusals(out, *, corpus=True):
    evidence = [{"kind": "transcript", "transcript_id": "tr_iso", "source": "transcript"}, *out["evidence"]]
    return E.refusals(headline=out["headline"], body=out["body"], evidence=evidence,
                      corpus=out["corpus"] if corpus else ())


def test_a_meeting_followup_is_held_by_the_facts_it_was_composed_from():
    from genios_engine.reason.meetings import passes as MS
    from tests.test_meetings_unit import _items
    for viewer in ("a@x.test", "b@x.test"):
        out = MS.compose_followup(_items(), viewer=viewer, title="ISO audit", meeting_node_id="m")
        assert _followup_refusals(out) == (), viewer
    mine = MS.compose_followup(_items(), viewer="a@x.test", title="ISO audit", meeting_node_id="m")
    assert [r.rule for r in _followup_refusals(mine, corpus=False)] == ["number"], "the corpus is load-bearing"
    assert not any(c in mine["corpus"] for c in (mine["headline"], mine["body"])), "never its own words"
    # a title, a decision and an open decision carry their own numbers
    dated = MS.Items(nodes={}, facts=[], owners=[], decisions=[("made", "ship on 14 Oct", "org", None),
                                                               ("pending", "pick 2 vendors", "org", None)])
    out = MS.compose_followup(dated, viewer="a@x.test", title="Q3 board review", meeting_node_id=None)
    assert out["body"] == "Decided: ship on 14 Oct · Open decision: pick 2 vendors" and "Q3" in out["headline"]
    assert _followup_refusals(out) == ()
    for held in ("Q3 board review", "ship on 14 Oct", "pick 2 vendors"):
        assert [r.rule for r in _followup_refusals({**out, "corpus": [c for c in out["corpus"] if c != held]})] \
            == ["number"], held
    # yours, counted; a commitment's own number; its due date — node ids with no digit, so nothing holds them by luck
    org = (None, None)
    yours = MS.Items(nodes={"ca": [org], "cb": [org]},
                     facts=[("ca", "commitment.text", "file the 3 forms", "org", None),
                            ("ca", "commitment.due_at", "2026-09-24T00:00:00Z", "org", None),
                            ("cb", "commitment.text", "send the deck", "org", None)],
                     owners=[("ca", "pa", "Aarav Mehta", {"a@x.test"}, None, None),
                             ("cb", "pa", "Aarav Mehta", {"a@x.test"}, None, None)], decisions=[])
    out = MS.compose_followup(yours, viewer="a@x.test", title="Sync", meeting_node_id="m")
    assert out["headline"] == "Follow-ups from Sync — 2 for you", out["headline"]
    assert out["body"] == "You: file the 3 forms (due 24 Sep); send the deck", out["body"]
    assert _followup_refusals(out) == ()
    for held in ("2", "file the 3 forms", "2026-09-24T00:00:00Z"):
        assert [r.rule for r in _followup_refusals({**out, "corpus": [c for c in out["corpus"] if c != held]})] \
            == ["number"], held


def test_a_corpus_never_holds_what_it_does_not_say(engine):
    """The corpus is the facts', not a pass: a number nothing composed is still refused."""
    counts: dict = {}
    assert _emit(engine, counts, body="Shalini can cover — due 19 Sep.", corpus=("Shalini",)) is None
    assert counts == {"refused_contract:number": 1}


def test_the_writer_hands_its_corpus_to_the_contract(engine):
    head = "Follow-ups from ISO audit — 2 for you"
    assert _emit(engine, headline=head, body="You: send the ISO pack", evidence=[{"kind": "transcript"}]) is None
    assert _emit(engine, headline=head, body="You: send the ISO pack", evidence=[{"kind": "transcript"}],
                 corpus=("2", "send the ISO pack")) is not None
    assert _written(engine) == (1, 1, 1)


def test_a_readiness_card_holds_its_own_counts(monkeypatch):
    """*"Board pack on 17 Oct: 1 away, 3 pending"* — the away count is in the card's evidence, as done and pending are."""
    from datetime import date
    from types import SimpleNamespace
    from genios_engine.reason.team import readiness as R
    milestone = R.Milestone(milestone_id="ms_board", title="Board pack", due_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
                            owner_seat_id="seat_owner", scope_kind=None, scope_key=None, task_filter=None)
    away = (SimpleNamespace(label="Anisha", seat_id="seat_a"),
            SimpleNamespace(start=date(2026, 10, 14), end=date(2026, 10, 16), effective_end=date(2026, 10, 16)))
    monkeypatch.setattr(R, "load_milestones", lambda *_a, **_k: [milestone])
    monkeypatch.setattr(R, "counts", lambda *_a, **_k: {"done": 5, "pending": 3, "away": 1, "away_names": ["Anisha"],
                                                         "away_windows": [away], "tasks": 0})
    ctx = SimpleNamespace(org_id=ORG, today=date(2026, 10, 12), now=datetime(2026, 10, 12, tzinfo=timezone.utc),
                          directory=SimpleNamespace(for_seat=lambda _s: object()), links=None)
    (s,) = R.situations(None, ctx)
    assert "1 away" in s.headline and "3 pending" in s.headline, s.headline
    assert E.refusals(headline=s.headline, body=s.body, evidence=list(s.evidence)) == ()

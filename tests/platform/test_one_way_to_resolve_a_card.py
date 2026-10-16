"""STEP-16 · one way to resolve a card — and every resolution says why, and what proved it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_one_way_to_resolve_a_card.py -q

Tree `yc2_w27_s16` M47.C1.L-data.V0.U01 (`platform/card_lifecycle.resolve_cards`; `s16-F6`). The card lifecycle could
expire a card and never resolve one; the team lane set `resolved` with statements of its own. `resolve_cards` moves the
named cards still open to `resolved` (and `resolved_at`), one `card.resolved` event each naming its cause — `verified`
with the event that closed the ask, the loop and the basis, each required; the team lane's `situation_cleared` and
`superseded` — in the caller's transaction. A card already ended is neither moved nor given an event. The expiry
guard's twin: no other code sets a card `resolved` (by the AST, as `test_one_way_to_expire_a_card` reads `expired`).
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import card_lifecycle as L
from tests.platform.test_one_way_to_expire_a_card import ROOT, SCANNED, THE_WRITER, _outermost_strings

ORG = "org_s16_resolve"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
EVIDENCE = {"event_id": "evt_signed_nda", "loop_id": "loop_nda", "basis": "answered"}

_SETS_RESOLVED = re.compile(r"\bupdate\s+cards\b[^;]*?\bset\b[^;]*?\bstate\s*=\s*'resolved'",
                            re.IGNORECASE | re.DOTALL)

#: The team lane's two statements, as they stood at `9d469efb` — each must still be caught.
HISTORICAL = (
    "update cards set state = 'resolved', resolved_at = :now where card_id = :c "
    "and org_id = :o and state in ('built', 'queued', 'surfaced', 'snoozed') returning 1",
    "update cards set state = 'resolved', resolved_at = :now where card_id = :id "
    "and org_id = :o and state = 'snoozed' returning 1",
)


def _violations() -> list[str]:
    found = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == THE_WRITER or "/." in rel:
                continue
            for line, sql in _outermost_strings(ast.parse(path.read_text(encoding="utf-8"))):
                if _SETS_RESOLVED.search(sql):
                    found.append(f"{rel}:{line}")
    return found


def test_every_historical_shape_is_caught():
    for sql in HISTORICAL:
        assert _SETS_RESOLVED.search(sql), sql


def test_no_other_code_sets_a_card_resolved():
    assert _violations() == []


def test_the_writer_is_where_it_says():
    assert len(_SETS_RESOLVED.findall((ROOT / THE_WRITER).read_text(encoding="utf-8"))) == 1


def test_the_causes_are_closed_and_a_verified_one_names_what_proved_it():
    assert L.RESOLVE_CAUSES == {L.VERIFIED, L.SITUATION_CLEARED, L.SUPERSEDED}
    assert L.RESOLVED == "card.resolved" and L.RESOLVED not in L.KINDS


class _Unreachable:
    def execute(self, *_a, **_k):                                    # pragma: no cover - the point
        raise AssertionError("a refused resolution reached the database")


@pytest.mark.parametrize("cause, evidence", [
    ("done", EVIDENCE), (L.VERIFIED, None), (L.VERIFIED, {"event_id": "evt_1", "loop_id": "loop_1"}),
    (L.VERIFIED, {**EVIDENCE, "event_id": ""}),
])
def test_a_resolution_with_no_cause_or_no_proof_is_refused_before_anything_moves(cause, evidence):
    with pytest.raises(ValueError):
        L.resolve_cards(_Unreachable(), org_id=ORG, cause=cause, card_ids=["card_1"], evidence=evidence)


def test_nothing_named_moves_nothing():
    assert L.resolve_cards(_Unreachable(), org_id=ORG, cause=L.VERIFIED, evidence=EVIDENCE) == []


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the cards are Postgres's")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id in (:o, :x)"), {"o": ORG, "x": ORG + "_x"})
        for org in (ORG, ORG + "_x"):
            c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": org})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id in (:o, :x)"), {"o": ORG, "x": ORG + "_x"})


def _card(c, card_id, *, state="queued", org=ORG):
    c.execute(text("insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
                   "expires_at, state) values (:c, :s, :o, 'prescriptive', 'standard', 'h', 's', 10, :exp, :st)"),
              {"c": card_id, "s": f"sig_{card_id}", "o": org, "exp": AT + timedelta(days=7), "st": state})


@pytest.mark.pg
def test_a_verified_card_is_resolved_with_one_event_naming_what_closed_its_ask(engine):
    with engine.begin() as c:
        _card(c, "card_open")
        moved = L.resolve_cards(c, org_id=ORG, cause=L.VERIFIED, card_ids=["card_open"], evidence=EVIDENCE, at=AT)
        row = c.execute(text("select state, resolved_at from cards where card_id = 'card_open'")).one()
        [event] = c.execute(text("select kind, cause, detail, occurred_at from card_events where org_id = :o "
                                 "and card_id = 'card_open'"), {"o": ORG}).all()
    assert moved == ["card_open"] and tuple(row) == ("resolved", AT)
    assert (event.kind, event.cause, event.occurred_at) == (L.RESOLVED, L.VERIFIED, AT)
    assert event.detail == {**EVIDENCE, "signal_id": "sig_card_open"}


@pytest.mark.pg
@pytest.mark.parametrize("state", ["acted", "resolved", "expired"])
def test_a_card_already_ended_is_neither_moved_nor_given_an_event(engine, state):
    with engine.begin() as c:
        _card(c, "card_ended", state=state)
        assert L.resolve_cards(c, org_id=ORG, cause=L.VERIFIED, card_ids=["card_ended"], evidence=EVIDENCE) == []
        assert c.execute(text("select state from cards where card_id = 'card_ended'")).scalar() == state
        assert c.execute(text("select count(*) from card_events where card_id = 'card_ended'")).scalar() == 0


@pytest.mark.pg
def test_by_signal_another_tenants_card_never_moves(engine):
    with engine.begin() as c:
        _card(c, "card_mine")
        _card(c, "card_theirs", org=ORG + "_x")
        moved = L.resolve_cards(c, org_id=ORG, cause=L.VERIFIED, signal_ids=["sig_card_mine", "sig_card_theirs"],
                                evidence=EVIDENCE)
        theirs = c.execute(text("select state from cards where card_id = 'card_theirs'")).scalar()
    assert moved == ["card_mine"] and theirs == "queued"


@pytest.mark.pg
def test_the_states_it_may_move_are_the_callers_to_narrow(engine):
    with engine.begin() as c:
        _card(c, "card_queued")
        _card(c, "card_snoozed", state="snoozed")
        moved = L.resolve_cards(c, org_id=ORG, cause=L.SUPERSEDED, card_ids=["card_queued", "card_snoozed"],
                                evidence={"digest": "d1"}, states=("snoozed",))
    assert moved == ["card_snoozed"]

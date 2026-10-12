"""STEP-13 · a team or verify card carries the lane its signal was routed to — on its card, where the surface reads.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/test_a_team_card_carries_its_lane.py

Tree `yc2_w27_s13` M36.C1.L-data.V0.U07 (`reason/team/emit._write_card`; crosscheck X29). M36.C1.L-data.V0.U05 made
the team emitter route its signal's lane (a team situation is watched, a verify discrepancy is a conflict), but
its card insert and its in-place refresh carried no lane — and `0190` says it: "a lane that stops at `signals`
reached nobody". The card now carries the signal's lane and reason, written and refreshed alike.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.reason.test_every_writer_routes_its_lane import AT, ORG, _lane, _without_references, engine  # noqa: F401

pytestmark = pytest.mark.pg


def _write(kind, *, held=None, digest="d1"):
    from genios_engine.reason.team import emit as E
    with _without_references().begin() as c:
        return E._write_card(
            c, org_id=ORG, kind=kind, key=f"{kind}:k1", seat_id="seat_1", subjects=["node_1"],
            headline="Asha holds three overdue loops", body="Asha holds three overdue loops",
            actions=[], evidence=[], priority="high", capability=f"{kind}.situation", digest=digest,
            now=AT, expires_at=AT + timedelta(days=7), held_card_id=held)


def _card(engine, card_id):
    with engine.connect() as c:
        return c.execute(text("select signal_id, output_lane, lane_reason from cards where card_id = :c"),
                         {"c": card_id}).one()


@pytest.mark.parametrize("kind, lane", [("team", "monitor"), ("verify", "conflict")])
def test_the_card_carries_its_signals_lane(engine, kind, lane):
    card = _card(engine, _write(kind))
    assert (card.output_lane, card.lane_reason) == _lane(engine, card.signal_id)
    assert card.output_lane == lane and card.lane_reason.strip()


def test_a_card_refreshed_in_place_carries_it_too(engine):
    """A card written before the lane reached it is given the lane when the emitter refreshes it."""
    card_id = _write("verify")
    with engine.begin() as c:
        c.execute(text("update cards set output_lane = null, lane_reason = null where card_id = :c"),
                  {"c": card_id})
    assert _write("verify", held=card_id, digest="d2") == card_id
    card = _card(engine, card_id)
    assert (card.output_lane, card.lane_reason) == _lane(engine, card.signal_id)

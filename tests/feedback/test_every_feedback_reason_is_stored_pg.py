"""STEP-17 §3.3 · every reason the feedback route accepts is a reason the ledger can store.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q \
        tests/feedback/test_every_feedback_reason_is_stored_pg.py

`yc2_w27_s17` M40.C2.L-integration.V0.U01. ⛔ STEP-18 B3 (S17-F7): `POST /v1/intelligence/feedback`
accepts eleven *wrong* reasons (`api/intelligence_routes._FB_WRONG_REASONS`, the delivery lane's
`WRONG_REASONS`, held equal to `contracts/learning_attribution.ALL_REASONS`), and migration `0034`'s
CHECK on `card_feedback_verdicts` admits three. A founder who says *misread the source* gets a 500 and
their answer is lost — and every hermetic test is green, because none of them runs the INSERT.

This runs the route's OWN two statements — read out of the route by the statement census, so a
change to the route's columns is a change to this test — for every reason it accepts. ⛔ RESTATED by
STEP-16 (`yc2_w27_s16` M46.C2.L-data.V1.U02): the two statements moved byte for byte into the ledger's one
writer, `deliver/verdicts.record`, which both doors now call — so they are read from there. The three the
CHECK admits pass. The eight it refuses are STRICT expected failures naming the step that widens the
schema (`STEP-16` §3.1), so the day it does, each one XPASSes, fails, and its marker must come off.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.api.intelligence_routes import _FB_WRONG_REASONS
from genios_engine.contracts.learning_attribution import ALL_REASONS, LEGACY_REASONS
from genios_engine.platform import statement_plans as sp

ORG = "org_s17_feedback_reasons"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
#: ⛔ The ledger's one writer since STEP-16 M46.C2.L-data.V1.U02 — the route's two statements, moved there.
ROUTE = "genios_engine/deliver/verdicts.py"

#: STEP-18 B3 (`yc2_w27_s18` M48.C1.L-contract.V0.U01, migration 0210): 0034's CHECK admitted three reasons
#: while the route accepts eleven; 0210 admits every reason the route accepts, so each must now be stored —
#: the eight strict xfails that held B3 came off at the merge (crosscheck S17X-B2 / S18-X01).


def _route_statement(prefix: str) -> str:
    """The ledger's INSERT, as the census reads it from its one writer — exactly one."""
    found = [s for s in sp.statements() if s.path == ROUTE and s.sql.startswith(prefix)]
    assert len(found) == 1 and not found[0].holes, [(s.line, s.holes) for s in found]
    return found[0].sql


def test_the_route_accepts_exactly_the_eleven_reasons():
    """The premise: what this file parametrizes over is what a founder can send."""
    assert set(_FB_WRONG_REASONS) == set(ALL_REASONS) and len(ALL_REASONS) == 11
    assert LEGACY_REASONS < set(ALL_REASONS) and len(LEGACY_REASONS) == 3


@pytest.fixture
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the ledger's CHECK needs real Postgres")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    try:
        c.execute(text("insert into orgs (id, name) values (:o, 'Feedback Reasons') "
                       "on conflict (id) do nothing"), {"o": ORG})
        yield c
    finally:
        tx.rollback()
        c.close()


def _card(c, reason: str) -> str:
    card_id = f"card_s17_{reason}"
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
        "score, expires_at) values (:c, :s, :o, 'prescriptive', 'standard', 'h', 's', 10, :exp)"),
        {"c": card_id, "s": f"sig_s17_{reason}", "o": ORG, "exp": AT + timedelta(days=7)})
    return card_id


def _params():
    return [pytest.param(r, id=r) for r in sorted(ALL_REASONS)]


@pytest.mark.parametrize("reason", _params())
def test_a_wrong_verdict_with_this_reason_is_stored(conn, reason):
    card_id = _card(conn, reason)
    feedback_id = f"fb_s17_{reason}"
    stored = conn.execute(text(_route_statement("insert into card_feedback_verdicts")), {
        "id": feedback_id, "o": ORG, "card": card_id, "p": "admin", "pv": "1.0.0", "pr": 1,
        "cap": "admin.unanswered_email", "capv": "1.0.0", "r": "unanswered_email",
        "cause": "wrong", "reason": reason, "d": f'{{"reason": "{reason}"}}',
        "actor": "seat_founder", "as_of": AT}).first()
    assert stored is not None and stored.verdict_version == 1
    conn.execute(text(_route_statement("insert into card_feedback_revisions")), {
        "rid": f"fbrev_s17_{reason}", "fid": feedback_id, "o": ORG, "card": card_id, "v": 1,
        "cause": "wrong", "reason": reason, "d": f'{{"reason": "{reason}"}}',
        "actor": "seat_founder"})
    assert conn.execute(text(
        "select count(*) from card_feedback_revisions where org_id = :o and feedback_id = :f "
        "and reason = :r"), {"o": ORG, "f": feedback_id, "r": reason}).scalar() == 1

"""STEP-14 · the gold card has somewhere to put its lines — the move whole, its alternative, when to stop; and the
review keeps the lines code wrote for its card.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_the_gold_card_table.py

`migrations/0221_the_gold_card.sql` (tree `yc2_w27_s14` M43.C1.L-contract.V0.U01; STEP-14 §3.3, §8.4 item 5, s14-F6,
s14-F7). The gold card says the move WHOLE — who, what, for whom, by when, to whom — under *recommended*, where the
headline cut it at 60 characters and lost its date on 10 of 39 cards; its alternative; and when to wait or stop.
These sat in the audited play's metadata only (`reason/expert/decide._play`). `cards.recommended` (an object, its
`what` said), `cards.alternative` and `cards.wait_or_stop` carry them; the existing columns carry the rest (subject,
role, what remains, why now, done when, window, do-nothing, receipts, confidence). And `expert_reviews.card_lines`
keeps the lines code wrote for the card at review time (why now, what remains, subject, role, window) from the
dossier it was written against, so a decision and a replay read them without the dossier. Additive; rolled back
cleanly; `/reset` wipes both tables.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.pg

ORG = "gc0221_org"
AT = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0221_the_gold_card.sql"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        for table in ("cards", "expert_reviews"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'gc0221@example.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        for table in ("cards", "expert_reviews"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _card(c, card_id="c1", **over):
    row = {"c": card_id, "o": ORG, "exp": AT + timedelta(days=7), "rec": None, "alt": None, "stop": None}
    row.update(over)
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, state, "
        "expires_at, recommended, alternative, wait_or_stop) values (:c, :c, :o, 'prescriptive', 'high', 'h', 's', "
        "50, 'queued', :exp, cast(:rec as jsonb), :alt, :stop)"), row)


def _review(c, **over):
    row = {"o": ORG, "lines": None}
    row.update(over)
    c.execute(text(
        "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, dossier_digest, status, "
        "review, reviewed_at, card_lines) values (:o, 'node_f', 'ffp-1', 'claude-sonnet-5', 'expert-review.v3', "
        "'sha256:d', 'valid', cast('{\"mode\": \"act\"}' as jsonb), now(), cast(:lines as jsonb))"), row)


def test_the_gold_columns_are_there_and_nullable(engine):
    with engine.connect() as c:
        cols = {(r.table_name, r.column_name): (r.data_type, r.is_nullable) for r in c.execute(text(
            "select table_name, column_name, data_type, is_nullable from information_schema.columns "
            "where (table_name = 'cards' and column_name in ('recommended', 'alternative', 'wait_or_stop')) "
            "   or (table_name = 'expert_reviews' and column_name = 'card_lines')"))}
    assert cols == {("cards", "recommended"): ("jsonb", "YES"), ("cards", "alternative"): ("text", "YES"),
                    ("cards", "wait_or_stop"): ("text", "YES"), ("expert_reviews", "card_lines"): ("jsonb", "YES")}


def test_a_gold_card_keeps_its_move_whole_its_alternative_and_when_to_stop(engine):
    move = {"who": "you", "what": "Send Maria the deck", "for_whom": "Maria", "by_when": "2026-10-16",
            "to": "maria@alyst.test"}
    with engine.begin() as c:
        _card(c, rec=json.dumps(move), alt="Offer a short call instead", stop="If no reply by the 20th, ask once")
        _card(c, "c_plain")
        row = c.execute(text("select recommended, alternative, wait_or_stop from cards where card_id = 'c1'")).one()
        plain = c.execute(text("select recommended, alternative, wait_or_stop from cards where card_id = 'c_plain'")).one()
    assert tuple(row) == (move, "Offer a short call instead", "If no reply by the 20th, ask once")
    assert tuple(plain) == (None, None, None), "a card that carries none is as it was"


@pytest.mark.parametrize("rec", ['"Send Maria the deck"', '[]', '{"who": "you"}', '{"what": "  "}'])
def test_a_recommended_move_is_an_object_that_says_what(engine, rec):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _card(c, rec=rec)


def test_a_review_keeps_its_card_lines(engine):
    lines = {"why_now": "Maria replied on 11 Aug", "what_remains": [], "subject": "Maria Exconde", "role": None,
             "window": {"days": 3, "from": "move_date"}}
    with engine.begin() as c:
        _review(c, lines=json.dumps(lines))
        assert c.execute(text("select card_lines from expert_reviews where org_id = :o"), {"o": ORG}).scalar() == lines


@pytest.mark.parametrize("lines", ['"a line"', '[]'])
def test_card_lines_are_an_object(engine, lines):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _review(c, lines=lines)


def test_the_migration_is_additive_and_idempotent(engine):
    sql = MIGRATION.read_text(encoding="utf-8")
    body = " ".join(line for line in sql.splitlines() if not line.strip().startswith("--")).lower()
    assert "drop table" not in body and "drop column" not in body and " rename " not in body
    with engine.begin() as c:
        c.exec_driver_sql(sql)
        _card(c, rec=json.dumps({"what": "Send Maria the deck"}))

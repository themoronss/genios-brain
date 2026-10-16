"""STEP-15 · one brief per seat per local day, kept — and your mark on a line, the latest standing.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_the_morning_briefs_table.py

`migrations/0230_morning_briefs.sql` (tree `yc2_w27_s15` M44.C1.L-contract.V1.U02; STEP-15 §8.4 items 4-5). The
row is the CLAIM — a second composer of the same seat's day finds it — and the ARTIFACT: the brief's lines with
their sources and verdicts, the digest of the day's material, how it was written, the model, tier and cost, when.
`morning_brief_marks` keeps your mark on a line — useful, or not useful with your words — one per line per
person, a later one replacing it. The vocabularies are closed in the schema, the template spends nothing,
`/reset` erases both, the tenant's deletion cascades, a brief's deletion takes its marks, and the migration is
additive (`tests/platform/test_the_code_can_always_be_rolled_back.py`).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from genios_engine.api import account_routes

pytestmark = pytest.mark.pg

ORG = "mb0230_org"
AT = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)
DAY = date(2026, 9, 30)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'mb0230@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _brief(c, *, seat="seat_owner", day=DAY, **over):
    row = {"o": ORG, "s": seat, "d": day, "tz": "Asia/Kolkata", "as_of": AT, "one": "3 things need you.",
           "lines": json.dumps([{"line_id": "bl_1", "section": "today", "words": "Bluepeak."}]),
           "brief": json.dumps({"version": "morning_brief.v1"}), "digest": "abc", "by": "template",
           "why": "the template: no model armed", "model": None, "tier": None, "cost": 0}
    row.update(over)
    c.execute(text(
        "insert into morning_briefs (org_id, seat_id, local_date, timezone, as_of, one_line, lines, brief, "
        "material_digest, written_by, why, model, tier, cost_micro_usd) values (:o, :s, :d, :tz, :as_of, :one, "
        "cast(:lines as jsonb), cast(:brief as jsonb), :digest, :by, :why, :model, :tier, :cost)"), row)


def _mark(c, *, line="bl_1", by="seat_owner", mark="useful", words=None, seat="seat_owner", day=DAY):
    c.execute(text(
        "insert into morning_brief_marks (org_id, line_id, marked_by, seat_id, local_date, mark, words, "
        "marked_at) values (:o, :l, :b, :s, :d, :m, :w, :at)"),
        {"o": ORG, "l": line, "b": by, "s": seat, "d": day, "m": mark, "w": words, "at": AT})


def test_the_tables_hold_what_a_brief_and_a_mark_are(engine):
    with engine.connect() as c:
        def cols(t):
            return {r[0] for r in c.execute(text(
                "select column_name from information_schema.columns where table_name = :t"), {"t": t})}
        briefs, marks = cols("morning_briefs"), cols("morning_brief_marks")
    assert briefs == {"org_id", "seat_id", "local_date", "timezone", "as_of", "composed_at", "one_line", "lines",
                      "brief", "material_digest", "written_by", "why", "model", "tier", "cost_micro_usd"}
    assert marks == {"org_id", "line_id", "marked_by", "seat_id", "local_date", "mark", "words", "marked_at"}


def test_one_brief_per_seat_per_local_day(engine):
    with engine.begin() as c:
        _brief(c)
        _brief(c, day=date(2026, 10, 1))
        _brief(c, seat="seat_two")
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _brief(c)
    with engine.begin() as c:
        # The second composer of the same day: the claim is the row — it finds the first one's.
        found = c.execute(text(
            "insert into morning_briefs (org_id, seat_id, local_date, timezone, as_of, one_line, lines, brief, "
            "material_digest, written_by, why) values (:o, 'seat_owner', :d, 'UTC', :at, 'x', '[]', '{}', 'd', "
            "'template', 'w') on conflict (org_id, seat_id, local_date) do nothing returning seat_id"),
            {"o": ORG, "d": DAY, "at": AT}).first()
    assert found is None


@pytest.mark.parametrize("over", [
    {"by": "drafted"},                                                 # the ways a brief is written are closed
    {"cost": 9000},                                                    # the template spends nothing…
    {"model": "claude-haiku-4-5"}, {"tier": "T1"},                     # …and names no model
    {"by": "written", "tier": "T3"},                                   # never the strongest tier
    {"by": "written", "cost": -1, "model": "m", "tier": "T1"},          # a cost is never negative
    {"one": "  "}, {"why": ""},                                        # a brief says its line and why
    {"lines": json.dumps({"not": "a list"})},                          # its lines are a list
])
def test_the_schema_refuses_a_brief_that_is_not_one(engine, over):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _brief(c, **over)


def test_a_written_brief_names_its_model_tier_and_cost(engine):
    with engine.begin() as c:
        _brief(c, by="written", model="claude-haiku-4-5", tier="T1", cost=9000)
        _brief(c, seat="seat_two", by="escalated", model="claude-sonnet-5", tier="T2", cost=21000)
        rows = c.execute(text("select seat_id, written_by, tier, cost_micro_usd from morning_briefs "
                              "where org_id = :o order by seat_id"), {"o": ORG}).all()
    assert [tuple(r) for r in rows] == [("seat_owner", "written", "T1", 9000), ("seat_two", "escalated", "T2", 21000)]


def test_a_mark_is_one_per_line_per_person_and_says_why_not(engine):
    with engine.begin() as c:
        _brief(c)
        _mark(c)
        _mark(c, by="seat_two", mark="not_useful", words="I sent it yesterday")
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _mark(c)                                                    # the same person's second row
    for over in ({"mark": "meh"}, {"mark": "not_useful"}, {"mark": "not_useful", "words": " "},
                 {"mark": "useful", "words": "nice"}, {"day": date(2026, 9, 29)}):
        with pytest.raises(IntegrityError):
            with engine.begin() as c:
                _mark(c, by="seat_three", **over)


def test_deleting_the_tenant_cascades_reset_erases_and_a_brief_takes_its_marks(engine):
    assert account_routes._ORG_SCOPED_TABLES.index("morning_brief_marks") < \
        account_routes._ORG_SCOPED_TABLES.index("morning_briefs")
    with engine.begin() as c:
        _brief(c)
        _mark(c)
        wiped = account_routes._wipe(c, ORG)
        left = c.execute(text("select (select count(*) from morning_briefs where org_id = :o) + "
                              "(select count(*) from morning_brief_marks where org_id = :o)"), {"o": ORG}).scalar()
    assert wiped["morning_briefs"] == 1 and wiped["morning_brief_marks"] == 1 and left == 0
    with engine.begin() as c:
        _brief(c)
        _mark(c)
        c.execute(text("delete from morning_briefs where org_id = :o"), {"o": ORG})
        assert c.execute(text("select count(*) from morning_brief_marks where org_id = :o"),
                         {"o": ORG}).scalar() == 0
        _brief(c)
        _mark(c)
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        assert c.execute(text("select (select count(*) from morning_briefs where org_id = :o) + "
                              "(select count(*) from morning_brief_marks where org_id = :o)"),
                         {"o": ORG}).scalar() == 0

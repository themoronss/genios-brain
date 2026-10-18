"""STEP-18 B13 · a screen follow-up has a place to name the graph observation it became.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_migration_0211_a_followup_names_its_observation.py -q

`migrations/0211_a_followup_names_its_observation.sql` (`yc2_w27_s18` M48.C2.L-contract.V0.U12). A
follow-up whose words change is written to memory again, each time as a new observation, and nothing
on the row said which observation the last write had made — so no write could retire the one before
(`reason/moments/screen_memory`, M48.C2.L-data.V0.U06). One nullable column, additive, gone with the
follow-up row.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "org_s18_m0211"
MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "0211_a_followup_names_its_observation.sql"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_the_column_exists_and_is_optional(engine):
    with engine.connect() as c:
        row = c.execute(text(
            "select data_type, is_nullable from information_schema.columns "
            "where table_name = 'screen_followups' and column_name = 'observation_id'")).one()
    assert (row.data_type, row.is_nullable) == ("text", "YES")


def test_a_follow_up_written_before_names_nothing_and_one_written_after_names_its_observation(engine):
    with engine.begin() as c:
        c.execute(text(
            "insert into screen_followups (id, org_id, seat_id, kind, text, topic_key) values "
            "('fu_s18_a', :o, 'seat_s18', 'ask', 'Send the deck', 'deck'), "
            "('fu_s18_b', :o, 'seat_s18', 'ask', 'Book the call', 'call')"), {"o": ORG})
        c.execute(text("update screen_followups set observation_id = 'obs_s18' where id = 'fu_s18_b'"))
        named = dict(c.execute(text("select id, observation_id from screen_followups "
                                    "where org_id = :o"), {"o": ORG}).all())
    assert named == {"fu_s18_a": None, "fu_s18_b": "obs_s18"}


def test_the_migration_adds_one_column_and_nothing_else():
    sql = "\n".join(line for line in MIGRATION.read_text(encoding="utf-8").splitlines()
                    if not line.strip().startswith("--")).lower()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    assert statements[0] == ("alter table screen_followups add column if not exists "
                             "observation_id text")
    assert all(s.startswith(("alter table screen_followups add column if not exists",
                             "comment on column screen_followups.observation_id"))
               for s in statements), statements

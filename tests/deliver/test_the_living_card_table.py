"""STEP-14 · a file's card is ONE card: the file it carries, its version, and one open card per file.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_the_living_card_table.py

`migrations/0220_the_living_card.sql` (tree `yc2_w27_s14` M42.C1.L-contract.V0.U01; STEP-14 §8.4 item 1, `03`
F176). Until now a card was its signal's (`cards_one_per_signal`, 0008), so every new decision on a file was a
new card and the old one was expired REPLACED — 10 replacements over 9 golden cases. A card now names the FILE
whose decisions and questions it carries (`file_id`; NULL on a card that is no file's — the legacy and compiled
lanes, P4) and how many versions it has had (`version`, 1 at creation). The schema holds at most one OPEN card
per (org, file); a closed one is reopened by the file's next version (`platform/card_lifecycle.version_card`),
never doubled. `/reset` wipes them with the cards, the tenant's deletion cascades, and the migration is additive
(`tests/platform/test_the_code_can_always_be_rolled_back.py`).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from genios_engine.api import account_routes

pytestmark = pytest.mark.pg

ORG = "lc0220_org"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0220_the_living_card.sql"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        for table in ("card_events", "cards", "signals"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'lc0220@example.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        for table in ("card_events", "cards", "signals"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _card(c, card_id, *, file_id=None, state="queued", version=None):
    signal = f"sig_{card_id}"
    c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
                   "eval_time) values (:s, :o, 'file_review', 'node_file', 50, 'file_review', :t)"),
              {"s": signal, "o": ORG, "t": AT})
    cols = "card_id, signal_id, org_id, level, urgency_band, headline, situation, score, state, expires_at, file_id"
    vals = ":c, :s, :o, 'prescriptive', 'standard', 'h', 's', 50, :state, :exp, :f"
    if version is not None:
        cols, vals = cols + ", version", vals + ", :v"
    c.execute(text(f"insert into cards ({cols}) values ({vals})"),
              {"c": card_id, "s": signal, "o": ORG, "state": state, "exp": AT + timedelta(days=7),
               "f": file_id, "v": version})


def test_a_card_names_its_file_and_its_version(engine):
    with engine.connect() as c:
        cols = {r.column_name: r for r in c.execute(text(
            "select column_name, is_nullable, column_default, data_type from information_schema.columns "
            "where table_name = 'cards' and column_name in ('file_id', 'version')"))}
    assert set(cols) == {"file_id", "version"}
    assert (cols["file_id"].is_nullable, cols["file_id"].data_type) == ("YES", "text")
    assert (cols["version"].is_nullable, cols["version"].data_type) == ("NO", "integer")


def test_a_new_card_is_version_one_and_no_files_card_carries_no_file(engine):
    with engine.begin() as c:
        _card(c, "c_legacy")
        _card(c, "c_file", file_id="node_file")
        rows = dict(c.execute(text("select card_id, version from cards where org_id = :o"), {"o": ORG}).all())
        files = dict(c.execute(text("select card_id, file_id from cards where org_id = :o"), {"o": ORG}).all())
    assert rows == {"c_legacy": 1, "c_file": 1}
    assert files == {"c_legacy": None, "c_file": "node_file"}


def test_a_version_is_never_below_one(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _card(c, "c_zero", file_id="node_file", version=0)


@pytest.mark.parametrize("open_state", ["built", "queued", "surfaced", "snoozed", "claimed", "delivered"])
def test_a_file_has_one_open_card(engine, open_state):
    with engine.begin() as c:
        _card(c, "c_one", file_id="node_file", state=open_state)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _card(c, "c_two", file_id="node_file")


@pytest.mark.parametrize("closed_state", ["expired", "acted", "resolved"])
def test_a_closed_card_does_not_hold_the_files_place(engine, closed_state):
    """A card the founder decided stays decided (s14-D2) — the file's next card may stand beside it; one the
    clock or a replacement closed is REOPENED by the file's next version (`card_lifecycle.version_card`), which
    is the writer's rule, not the schema's."""
    with engine.begin() as c:
        _card(c, "c_closed", file_id="node_file", state=closed_state)
        _card(c, "c_next", file_id="node_file")
        n = c.execute(text("select count(*) from cards where org_id = :o and file_id = 'node_file'"),
                      {"o": ORG}).scalar()
    assert n == 2


def test_cards_of_no_file_and_of_other_files_never_collide(engine):
    with engine.begin() as c:
        _card(c, "c_a", file_id="node_a")
        _card(c, "c_b", file_id="node_b")
        _card(c, "c_none_1")
        _card(c, "c_none_2")
        n = c.execute(text("select count(*) from cards where org_id = :o"), {"o": ORG}).scalar()
    assert n == 4


def test_reset_wipes_a_files_card_and_the_tenants_deletion_cascades(engine):
    assert "cards" in account_routes._ORG_SCOPED_TABLES
    with engine.begin() as c:
        _card(c, "c_file", file_id="node_file")
        wiped = account_routes._wipe(c, ORG)
        left = c.execute(text("select count(*) from cards where org_id = :o"), {"o": ORG}).scalar()
    assert wiped["cards"] >= 1 and left == 0


def test_the_migration_is_additive_and_idempotent(engine):
    sql = MIGRATION.read_text(encoding="utf-8")
    body = " ".join(line for line in sql.splitlines() if not line.strip().startswith("--")).lower()
    assert "drop table" not in body and "drop column" not in body and " rename " not in body
    with engine.begin() as c:                       # applied again on a migrated database: nothing moves
        c.exec_driver_sql(sql)
        _card(c, "c_again", file_id="node_file")
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _card(c, "c_again_two", file_id="node_file")

"""STEP-07 · the company brief's table: one row per line, a closed vocabulary, nothing deleted.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_migration_0195_company_brief.py -q

`migrations/0195_company_brief.sql` (tree `yc2_w27_s07/M25.C1.L-contract.V0.U02`). A line is proposed,
then accepted, rejected or — once accepted — removed; its timestamps must agree with its status, so the
brief in force at any instant can be rebuilt from the rows. A connector names an address, a watchlist
line a domain. The schema refuses what the contract refuses, so a write that skips the store cannot
put a malformed line in front of a model.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

ORG = "cb0195_org"
AT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.pg


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'cb0195@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _line(c, **over):
    row = {"o": ORG, "l": "cbl_1", "section": "goals", "text": "raise the pre-seed round",
           "address": None, "domain": None, "status": "proposed", "by": "drafter",
           "at": AT, "decided_at": None, "accepted_at": None, "removed_at": None}
    row.update(over)
    c.execute(text(
        "insert into company_brief_lines (org_id, line_id, section, text, address, domain, status, "
        " proposed_by, proposed_at, decided_at, accepted_at, removed_at) values "
        "(:o, :l, :section, :text, :address, :domain, :status, :by, :at, :decided_at, "
        " :accepted_at, :removed_at)"), row)


def test_the_tables_have_the_columns_the_store_needs(engine):
    with engine.connect() as c:
        lines = {r.column_name for r in c.execute(text(
            "select column_name from information_schema.columns "
            "where table_name = 'company_brief_lines'"))}
        reviews = {r.column_name for r in c.execute(text(
            "select column_name from information_schema.columns "
            "where table_name = 'company_brief_reviews'"))}
    # ⛔ MOVED 2026-10-09 by yc2_w27_s11/M30.C4.L-contract.V0.U01: migration 0196 adds `kind`, the
    # kind of work an in-motion line names (`06` D31) — nullable, validated in code; its own test is
    # `tests/platform/test_a_brief_line_names_its_kind.py`.
    assert lines == {"org_id", "line_id", "section", "text", "address", "domain", "status",
                     "proposed_by", "proposed_text", "evidence", "proposed_at", "decided_by",
                     "decided_at", "accepted_at", "removed_at", "kind"}
    assert reviews == {"org_id", "week_key", "started_at", "finished_at", "outcome", "proposed"}


def test_a_proposed_and_an_accepted_line_are_written(engine):
    with engine.begin() as c:
        _line(c)
        _line(c, l="cbl_2", status="accepted", decided_at=AT, accepted_at=AT)
        _line(c, l="cbl_3", section="connectors", text="Introly — introduces people",
              address="hello@introly.test")
        _line(c, l="cbl_4", section="watchlist", text="StartupSetu", domain="startupsetu.gov.test")


@pytest.mark.parametrize("bad", [
    {"section": "us"}, {"section": "gossip"}, {"status": "pending"},
    {"text": ""}, {"text": "two\nlines"}, {"text": "x" * 201},
    {"section": "connectors", "address": None},
    {"section": "watchlist", "domain": None},
    {"address": "Hello@Introly.test"}, {"domain": "StartupSetu.gov.test"}, {"domain": "localhost"},
    {"status": "accepted"},                                   # accepted with no decision
    {"status": "proposed", "decided_at": AT},                 # proposed but decided
    {"status": "rejected", "decided_at": AT, "accepted_at": AT},
    {"status": "removed", "decided_at": AT, "accepted_at": AT},   # removed with no removed_at
])
def test_the_schema_refuses_what_the_contract_refuses(engine, bad):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _line(c, **bad)


def test_one_row_per_line(engine):
    with engine.begin() as c:
        _line(c)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _line(c)


def test_one_review_per_tenant_per_week(engine):
    with engine.begin() as c:
        c.execute(text("insert into company_brief_reviews (org_id, week_key, started_at) "
                       "values (:o, '2026-W41', :at)"), {"o": ORG, "at": AT})
        claimed = c.execute(text(
            "insert into company_brief_reviews (org_id, week_key, started_at) "
            "values (:o, '2026-W41', :at) on conflict do nothing returning week_key"),
            {"o": ORG, "at": AT}).first()
    assert claimed is None


def test_the_lines_go_with_their_org(engine):
    with engine.begin() as c:
        _line(c)
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        left = c.execute(text("select count(*) from company_brief_lines where org_id = :o"),
                         {"o": ORG}).scalar()
    assert left == 0


def test_the_reset_keeps_the_brief():
    """Authored, like `org_self_identities`: what the tenant told us about itself survives `/reset`."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    from tests.api.test_a_reset_leaves_no_tenant_conclusion_behind import SURVIVES_RESET

    for table in ("company_brief_lines", "company_brief_reviews"):
        assert table not in _ORG_SCOPED_TABLES
        assert table in SURVIVES_RESET

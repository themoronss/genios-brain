"""STEP-11 · a brief line can say what kind of work it is — one nullable column, and nothing else moves.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_a_brief_line_names_its_kind.py -q

`migrations/0196_company_brief_line_kind.sql` (tree `yc2_w27_s11 · M30.C4.L-contract.V0.U01`, `06` D31).
A founder's file knew only its ROLE — connector, watched, person, intro — so no file could say what kind
of WORK it is, and the next step's expert could not pick the playbook for it (`speedrun008/YC-II W27/`
STEP-11 §8.3 N1). An in-motion line of the brief now names its kind of work in `kind`; its counterparty
is the line's existing `address` or `domain`, which 0195 already holds and checks.

The closed list lives in code (`contracts/company_brief.WORK_KINDS`), not in a check constraint — a
seventh kind is an authoring event, not a schema event, as `l3_activation.domain` (0107) is. And the
column is additive: the previous image never names it, and every write it makes still lands.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from genios_engine.platform.migrate import _split_statements

ORG = "cb0196_org"
AT = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0196_company_brief_line_kind.sql"

pytestmark = pytest.mark.pg


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'cb0196@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    eng.dispose()


def _as_before(c, line_id: str, **over) -> None:
    """A line written the way the previous image writes one — 0195's columns, no `kind`."""
    row = {"o": ORG, "l": line_id, "section": "in_motion", "text": "Banyan Seed — first call held",
           "address": None, "domain": None, "status": "accepted", "by": "founder", "at": AT}
    row.update(over)
    c.execute(text(
        "insert into company_brief_lines (org_id, line_id, section, text, address, domain, status, "
        " proposed_by, proposed_at, decided_at, accepted_at) values "
        "(:o, :l, :section, :text, :address, :domain, :status, :by, :at, :at, :at)"), row)


def _kind(c, line_id: str):
    return c.execute(text("select kind from company_brief_lines where org_id = :o and line_id = :l"),
                     {"o": ORG, "l": line_id}).scalar_one()


def test_a_line_has_a_kind_and_may_name_none(engine):
    """Nullable, no default, text: a line written before 0196 named no kind, and most lines never
    will — a default would claim a kind nobody chose."""
    with engine.connect() as c:
        col = c.execute(text(
            "select data_type, is_nullable, column_default from information_schema.columns "
            " where table_name = 'company_brief_lines' and column_name = 'kind'")).first()
    assert col is not None, "company_brief_lines has no kind column"
    assert (col.data_type, col.is_nullable, col.column_default) == ("text", "YES", None)


def test_a_line_the_previous_image_writes_still_lands_and_names_no_kind(engine):
    with engine.begin() as c:
        _as_before(c, "cbl_before")
        assert _kind(c, "cbl_before") is None


def test_an_in_motion_line_keeps_its_kind_and_its_counterparty(engine):
    with engine.begin() as c:
        _as_before(c, "cbl_fund", domain="banyanseed.test")
        _as_before(c, "cbl_program", text="Lakshya — application under review",
                   address="programs@lakshya.test")
        c.execute(text("update company_brief_lines set kind = 'investor' "
                       " where org_id = :o and line_id = 'cbl_fund'"), {"o": ORG})
        c.execute(text("update company_brief_lines set kind = 'program' "
                       " where org_id = :o and line_id = 'cbl_program'"), {"o": ORG})
        rows = c.execute(text(
            "select line_id, kind, address, domain from company_brief_lines where org_id = :o "
            " order by line_id"), {"o": ORG}).fetchall()
    assert [tuple(r) for r in rows] == [("cbl_fund", "investor", None, "banyanseed.test"),
                                        ("cbl_program", "program", "programs@lakshya.test", None)]


def test_the_list_of_kinds_is_the_codes_not_the_schemas(engine):
    """No check constraint names `kind`, and the column says where its list lives — so the next
    reader of the schema finds the rule instead of a column that looks unchecked."""
    with engine.connect() as c:
        defs = [r.d for r in c.execute(text(
            "select pg_get_constraintdef(oid) as d from pg_constraint "
            " where conrelid = 'company_brief_lines'::regclass"))]
        comment = c.execute(text(
            "select col_description('company_brief_lines'::regclass, a.attnum) from pg_attribute a "
            " where a.attrelid = 'company_brief_lines'::regclass and a.attname = 'kind'")).scalar()
    assert defs and not [d for d in defs if "kind" in d], defs
    assert comment and "contracts/company_brief.WORK_KINDS" in comment, comment


def test_running_it_again_changes_nothing(engine):
    """A restore or a lost ledger row re-runs a file the ledger thought was done (`migrate.py`: one
    transaction per file) — every statement in it must be a no-op the second time."""
    statements = _split_statements(MIGRATION.read_text(encoding="utf-8"))
    with engine.connect() as c:
        tx = c.begin()
        try:
            for stmt in statements:
                c.execute(text(stmt))
            n = c.execute(text(
                "select count(*) from information_schema.columns "
                " where table_name = 'company_brief_lines' and column_name = 'kind'")).scalar_one()
        finally:
            tx.rollback()
    assert n == 1


def test_it_only_adds_the_column_and_says_what_it_is():
    """One `add column if not exists` and one comment: no backfill, no constraint, nothing dropped
    or renamed — the previous image keeps running (`test_the_code_can_always_be_rolled_back`)."""
    statements = [" ".join(s.lower().split())
                  for s in _split_statements(MIGRATION.read_text(encoding="utf-8"))]
    assert len(statements) == 2, statements
    assert statements[0] == "alter table company_brief_lines add column if not exists kind text"
    assert statements[1].startswith("comment on column company_brief_lines.kind is '")

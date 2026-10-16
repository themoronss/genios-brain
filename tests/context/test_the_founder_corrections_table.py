"""STEP-16 · your correction of a file is kept, in your words, with its scope — never deleted.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_the_founder_corrections_table.py

`migrations/0241_founder_corrections.sql` (tree `yc2_w27_s16` M46.C3.L-contract.V0.U01; STEP-16 §8.4 item 2,
S16-D1). A correction is your words (one line, required) on a file — its anchor, no foreign key, as
`founder_questions` — with its scope: `file`, `kind` (every file of this kind of work, the kind recorded) or
`company` (your preferences line of the brief, its line id kept); optionally the card, the verdict and the
verdict's reason (one of the eleven); who and when; standing or withdrawn (who, when). The vocabularies are
closed in the schema, each scope carries what makes it one, `/reset` erases the table, the tenant's deletion
cascades, and the migration is additive (`tests/platform/test_the_code_can_always_be_rolled_back.py`).
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from genios_engine.api import account_routes
from genios_engine.contracts.learning_attribution import ALL_REASONS

ORG = "fc0241_org"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "0241_founder_corrections.sql"
WORDS = "She asked for updates only with real news — don't push me."


def _sql() -> str:
    return "\n".join(line.split("--", 1)[0] for line in MIGRATION.read_text(encoding="utf-8").splitlines())


def test_the_reasons_are_the_eleven_the_verdict_ledger_admits():
    lists = [set(re.findall(r"'([a-z_]+)'", body))
             for body in re.findall(r"reason\s+in\s*\(([^)]*)\)", _sql(), re.I)]
    assert lists == [set(ALL_REASONS)], lists


def test_the_migration_is_one_new_table_and_its_indexes():
    sql = " ".join(_sql().lower().split())
    assert sql.count("create table if not exists founder_corrections") == 1
    assert "alter table" not in sql and "drop " not in sql and "references cards" not in sql


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'fc0241@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _correct(c, cid="fc_1", file="node_theresa", **over):
    row = {"o": ORG, "id": cid, "f": file, "card": None, "fb": None, "reason": None, "words": WORDS,
           "scope": "file", "kind": None, "line": None, "by": "user_rohit", "at": AT, "state": "standing",
           "wby": None, "wat": None}
    row.update(over)
    c.execute(text(
        "insert into founder_corrections (org_id, correction_id, file_id, card_id, feedback_id, reason, words, "
        "scope, kind, brief_line_id, corrected_by, corrected_at, state, withdrawn_by, withdrawn_at) values "
        "(:o, :id, :f, :card, :fb, :reason, :words, :scope, :kind, :line, :by, :at, :state, :wby, :wat)"), row)


@pytest.mark.pg
def test_the_table_holds_what_a_correction_is(engine):
    with engine.connect() as c:
        cols = {r[0] for r in c.execute(text(
            "select column_name from information_schema.columns where table_name = 'founder_corrections'"))}
    assert cols == {"org_id", "correction_id", "file_id", "card_id", "feedback_id", "reason", "words", "scope",
                    "kind", "brief_line_id", "corrected_by", "corrected_at", "state", "withdrawn_by",
                    "withdrawn_at"}


@pytest.mark.pg
def test_each_scope_and_a_withdrawal_are_kept(engine):
    with engine.begin() as c:
        _correct(c)
        _correct(c, cid="fc_2", card="card_9", fb="fb_9", reason="not_relevant")
        _correct(c, cid="fc_3", scope="kind", kind="investor",
                 words="Investors who asked for news only on milestones get nothing before one lands.")
        _correct(c, cid="fc_4", scope="company", line="cbl_pref_1", words="Never push a follow-up on a Friday.")
        _correct(c, cid="fc_5", state="withdrawn", wby="user_rohit", wat=AT)
        rows = dict(c.execute(text("select correction_id, scope || '/' || state from founder_corrections "
                                   "where org_id = :o"), {"o": ORG}).all())
    assert rows == {"fc_1": "file/standing", "fc_2": "file/standing", "fc_3": "kind/standing",
                    "fc_4": "company/standing", "fc_5": "file/withdrawn"}


@pytest.mark.pg
@pytest.mark.parametrize("over", [
    {"scope": "team"},                                                  # the scope is closed
    {"state": "deleted"},                                               # …and so is the state
    {"words": "  "}, {"words": "two\nlines"}, {"words": "x" * 501},     # your words: one line, said
    {"reason": "meh"},                                                  # one of the eleven, or none
    {"scope": "kind"}, {"scope": "kind", "kind": " "},                  # a kind correction names its kind
    {"kind": "investor"},                                               # …and only it does
    {"scope": "company"},                                               # a company correction keeps its line
    {"line": "cbl_1"},                                                  # …and only it does
    {"state": "withdrawn", "wby": "user_rohit"},                        # a withdrawal says who and when
    {"wat": AT}, {"wby": "user_rohit", "wat": AT},                      # …and only a withdrawn one has one
])
def test_the_schema_refuses_a_correction_that_is_not_one(engine, over):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _correct(c, **over)


@pytest.mark.pg
def test_every_reason_of_the_eleven_is_kept(engine):
    with engine.begin() as c:
        for i, reason in enumerate(sorted(ALL_REASONS)):
            _correct(c, cid=f"fc_r{i}", reason=reason)
        n = c.execute(text("select count(*) from founder_corrections where org_id = :o"), {"o": ORG}).scalar()
    assert n == 11


@pytest.mark.pg
def test_a_file_with_no_node_and_a_card_that_is_gone_are_still_what_you_said(engine):
    """No foreign key on the file, the card or the verdict: a merged node or an expired card leaves your
    correction standing."""
    with engine.begin() as c:
        _correct(c, file="node_merged_away", card="card_long_gone", fb="fb_long_gone", reason="wrong_person")
        assert c.execute(text("select count(*) from founder_corrections where org_id = :o"),
                         {"o": ORG}).scalar() == 1


@pytest.mark.pg
def test_deleting_the_tenant_cascades_and_reset_erases_it(engine):
    assert "founder_corrections" in account_routes._ORG_SCOPED_TABLES
    with engine.begin() as c:
        _correct(c)
        _correct(c, cid="fc_2", file="node_other")
        wiped = account_routes._wipe(c, ORG)
        left = c.execute(text("select count(*) from founder_corrections where org_id = :o"),
                         {"o": ORG}).scalar()
    assert wiped["founder_corrections"] == 2 and left == 0
    with engine.begin() as c:
        _correct(c, cid="fc_3")
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        assert c.execute(text("select count(*) from founder_corrections where org_id = :o"),
                         {"o": ORG}).scalar() == 0

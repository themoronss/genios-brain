"""STEP-13b · every rung's consult of a file is kept — and the rung whose review stands is named.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_expert_review_attempts_table.py

`migrations/0250_expert_review_attempts.sql` (tree `yc2_w27_s13b` M38.C1.L-contract.V0.U04; STEP-13b §8.4 item 5).
The expert's review goes up a ladder of models (Haiku → one repair with the check's verdicts → Sonnet →
Opus if allowed, s13b-D1); `expert_reviews` keeps the review that STANDS, and this table keeps every consult
that led to it — the file, the fingerprint, the rung, the model, whether it was the first ask or the repair,
its status, its check's fate, the reason it climbed (closed), its tokens and cost — so a scorecard can say
which rung answered and why the others did not. `expert_reviews.rung` is the rung whose review stands; null on
a row from before 0250, which reads as rung one. `/reset` erases the table; the tenant's deletion cascades; the
migration is additive (`tests/platform/test_the_code_can_always_be_rolled_back.py`).
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

ORG = "era0250_org"
AT = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)
MIGRATION = Path(__file__).resolve().parents[3] / "migrations" / "0250_expert_review_attempts.sql"
CLIMBS = ("malformed", "truncated", "nothing_stands", "uncited", "unknown_evidence", "unquoted", "misquoted",
          "unsupported", "wrong_number", "engine_is_no_fact", "headline_failed", "recipient_is_us",
          "recipient_is_connector")
STATUSES = ("valid", "refused", "truncated", "over_budget", "failed")
FATES = ("shown", "held", "suppressed", "refused")


def _sql() -> str:
    return "\n".join(line.split("--", 1)[0] for line in MIGRATION.read_text(encoding="utf-8").splitlines())


def test_the_migration_is_additive_and_closes_its_vocabularies():
    sql = _sql().lower()
    assert re.search(r"create table if not exists expert_review_attempts", sql)
    assert not re.search(r"\bdrop\s+(table|column)\b|\brename\b|\balter\s+column\b", sql)
    lists = [set(re.findall(r"'([a-z_]+)'", body)) for body in re.findall(r"in\s*\(([^)]*)\)", sql)]
    assert set(CLIMBS) in lists and set(STATUSES) in lists and set(FATES) in lists
    assert {"first", "repair"} in lists


def test_the_reset_erases_it_and_the_tenants_deletion_cascades():
    assert "expert_review_attempts" in account_routes._ORG_SCOPED_TABLES
    assert re.search(r"references\s+orgs\s*\(id\)\s+on\s+delete\s+cascade", _sql(), re.I)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the attempts are kept in Postgres")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'era0250@example.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _insert(c, **over):
    row = {"o": ORG, "file": "node_fund_neel", "fp": "fp_1", "n": 1, "rung": 1, "model": "claude-haiku-4-5",
           "consult": "first", "status": "valid", "fate": "held", "climbed": "misquoted", "tin": 5600,
           "tout": 2800, "cost": 20_000, "at": AT}
    row.update(over)
    c.execute(text(
        "insert into expert_review_attempts (org_id, file_id, fingerprint, attempt_no, rung, model, consult, "
        "status, fate, climbed_because, input_tokens, output_tokens, cost_micro_usd, attempted_at) "
        "values (:o, :file, :fp, :n, :rung, :model, :consult, :status, :fate, :climbed, :tin, :tout, :cost, :at)"),
        row)


@pytest.mark.pg
def test_the_table_has_the_columns_the_readers_need(engine):
    with engine.connect() as c:
        cols = {r.column_name: (r.data_type, r.is_nullable) for r in c.execute(text(
            "select column_name, data_type, is_nullable from information_schema.columns "
            "where table_name = 'expert_review_attempts'"))}
        rung = c.execute(text("select data_type, is_nullable from information_schema.columns "
                              "where table_name = 'expert_reviews' and column_name = 'rung'")).one()
    assert cols == {
        "org_id": ("text", "NO"), "file_id": ("text", "NO"), "fingerprint": ("text", "NO"),
        "attempt_no": ("integer", "NO"), "rung": ("integer", "NO"), "model": ("text", "NO"),
        "consult": ("text", "NO"), "status": ("text", "NO"), "fate": ("text", "YES"),
        "climbed_because": ("text", "YES"), "input_tokens": ("integer", "NO"),
        "output_tokens": ("integer", "NO"), "cost_micro_usd": ("bigint", "NO"),
        "attempted_at": ("timestamp with time zone", "NO")}
    assert tuple(rung) == ("integer", "YES"), "null on a row from before 0250: it reads as rung one"


@pytest.mark.pg
def test_a_consult_is_kept_with_its_rung_its_fate_and_why_it_climbed(engine):
    with engine.begin() as c:
        _insert(c)
        _insert(c, n=2, consult="repair", fate="held", climbed="misquoted")
        _insert(c, n=3, rung=2, model="claude-sonnet-5", fate="shown", climbed=None)
        rows = c.execute(text("select attempt_no, rung, consult, fate, climbed_because from "
                              "expert_review_attempts where org_id = :o order by attempt_no"), {"o": ORG}).all()
    assert [tuple(r) for r in rows] == [(1, 1, "first", "held", "misquoted"), (2, 1, "repair", "held", "misquoted"),
                                        (3, 2, "first", "shown", None)]


@pytest.mark.pg
@pytest.mark.parametrize("over", [
    {"status": "maybe"}, {"fate": "maybe"}, {"climbed": "rude"}, {"consult": "third"}, {"rung": 0}, {"n": 0},
    {"tin": -1}, {"cost": -1}, {"model": ""},
])
def test_the_vocabularies_are_closed_in_the_schema(engine, over):
    with pytest.raises(IntegrityError), engine.begin() as c:
        _insert(c, **over)


@pytest.mark.pg
def test_one_attempt_number_is_one_consult_of_a_fingerprint(engine):
    with pytest.raises(IntegrityError), engine.begin() as c:
        _insert(c)
        _insert(c)


@pytest.mark.pg
def test_a_review_row_names_the_rung_that_stands_and_a_deletion_of_the_tenant_takes_the_attempts(engine):
    with engine.begin() as c:
        _insert(c)
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        n = c.execute(text("select count(*) from expert_review_attempts where org_id = :o"), {"o": ORG}).scalar()
    assert n == 0

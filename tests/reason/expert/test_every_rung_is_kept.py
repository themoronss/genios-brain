"""STEP-13b · every rung's consult is kept, and the review that stands says which rung it is.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_every_rung_is_kept.py

Tree `yc2_w27_s13b` M38.C2.L-data.V1.U01 (`reason/expert/store`, over `expert_review_attempts`, 0250). `write_attempt`
keeps one consult of a file on a fingerprint — its rung, model, whether the first ask or the repair, status, the
check's fate, the closed reason it climbed, tokens and cost — numbered in the order asked; `attempts_for` reads them
back. The review row's model and rung are those of the review that stands; a row written before 0250 reads as rung one.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.reason.expert import store as R
from tests.reason.expert.test_the_review_store import FILE, INPUTS, REVIEW, TRIGGERS

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s13b_attempts", "org_s13b_attempts_other"
AT = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"), {"o": org, "e": f"{org}@example.test"})
    yield eng
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def _attempt(c, fp="fp_1", org=ORG, **over):
    row = dict(rung=1, model="claude-haiku-4-5", consult="first", status="valid", fate="held",
               climbed_because="misquoted", input_tokens=5600, output_tokens=2800, cost_micro_usd=20_000, at=AT)
    row.update(over)
    return R.write_attempt(c, org_id=org, file_id=FILE, fingerprint=fp, **row)


def test_an_attempt_is_numbered_in_the_order_it_was_asked(engine):
    with engine.begin() as c:
        assert [_attempt(c), _attempt(c, consult="repair"), _attempt(c, rung=2, model="claude-sonnet-5",
                                                                     fate="shown", climbed_because=None)] == [1, 2, 3]
        assert _attempt(c, fp="fp_2") == 1, "another fingerprint starts again"
        assert _attempt(c, org=OTHER) == 1, "another tenant too"


def test_the_attempts_of_a_file_read_back_in_order_with_what_each_cost(engine):
    with engine.begin() as c:
        _attempt(c)
        _attempt(c, consult="repair", output_tokens=2900)
        _attempt(c, rung=2, model="claude-sonnet-5", fate="shown", climbed_because=None, cost_micro_usd=70_000)
        got = R.attempts_for(c, ORG, FILE, "fp_1")
    assert [(a.attempt_no, a.rung, a.consult, a.fate, a.climbed_because) for a in got] == [
        (1, 1, "first", "held", "misquoted"), (2, 1, "repair", "held", "misquoted"), (3, 2, "first", "shown", None)]
    assert got[1].output_tokens == 2900 and got[2].model == "claude-sonnet-5" and got[2].cost_micro_usd == 70_000
    assert sum(a.cost_micro_usd for a in got) == 110_000
    assert all(a.attempted_at == AT for a in got)


def test_one_tenants_attempts_are_never_another_s(engine):
    with engine.begin() as c:
        _attempt(c)
        _attempt(c, org=OTHER, model="claude-sonnet-5")
        assert [a.model for a in R.attempts_for(c, ORG, FILE, "fp_1")] == ["claude-haiku-4-5"]
        assert R.attempts_for(c, ORG, FILE, "fp_none") == ()


@pytest.mark.parametrize("over", [{"status": "maybe"}, {"consult": "third"}, {"fate": "kept"},
                                  {"climbed_because": "rude"}, {"rung": 0}, {"model": " "},
                                  {"input_tokens": -1}, {"output_tokens": -1}, {"cost_micro_usd": -1}])
def test_an_attempt_the_table_would_not_hold_is_refused_before_it_is_sent(engine, over):
    with pytest.raises(ValueError), engine.begin() as c:
        _attempt(c, **over)


def test_a_review_row_names_the_rung_that_stands(engine):
    with engine.begin() as c:
        R.write_review(c, org_id=ORG, file_id=FILE, fingerprint="fp_1", model="claude-sonnet-5",
                       prompt_version="expert-review.v1", dossier_digest="sha256:d", status=R.VALID, reason=None,
                       review=REVIEW, input_tokens=9000, output_tokens=900, cost_micro_usd=26_100, at=AT,
                       inputs=INPUTS, triggers=[{"kind": k, "says": s} for k, s in TRIGGERS], rung=2)
        stored = R.read_review(c, ORG, FILE, "fp_1")
        assert stored.rung == 2 and R.latest_valid(c, ORG, FILE).rung == 2 and R.latest_standing(c, ORG, FILE).rung == 2
        assert R.current_judgments(c, ORG, now=AT)[FILE].stored.rung == 2


def test_a_row_written_before_0250_reads_as_rung_one(engine):
    with engine.begin() as c:
        R.write_review(c, org_id=ORG, file_id=FILE, fingerprint="fp_1", model="claude-sonnet-5",
                       prompt_version="expert-review.v1", dossier_digest="sha256:d", status=R.VALID, reason=None,
                       review=REVIEW, input_tokens=9000, output_tokens=900, cost_micro_usd=26_100, at=AT,
                       inputs=INPUTS, triggers=[{"kind": k, "says": s} for k, s in TRIGGERS])
        assert c.execute(text("select rung from expert_reviews where org_id = :o"), {"o": ORG}).scalar() is None
        assert R.read_review(c, ORG, FILE, "fp_1").rung == 1


def test_a_rung_below_one_is_refused_on_a_review_too(engine):
    with pytest.raises(ValueError, match="rung"), engine.begin() as c:
        R.write_review(c, org_id=ORG, file_id=FILE, fingerprint="fp_1", model="m", prompt_version="v",
                       dossier_digest="d", status=R.VALID, reason=None, review=REVIEW, input_tokens=1,
                       output_tokens=1, cost_micro_usd=1, at=AT, inputs=INPUTS, triggers=[], rung=0)

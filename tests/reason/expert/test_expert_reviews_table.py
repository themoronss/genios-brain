"""STEP-12 · the expert's review is kept: one row per file per fingerprint, and a refusal is a row.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_expert_reviews_table.py -q

`migrations/0197_expert_reviews.sql` (tree `yc2_w27_s12` M32.C1.L-contract.V0.U02). The expert judges a
FILE once each time its fingerprint moves (STEP-12 §8.4); to know it already did, and to replay the
judgment without the model, the review is kept with what it was shown (the dossier's digest), who wrote
it (model, prompt version), what it cost, and what came of it. The status vocabulary is closed in the
schema; a row that is not `valid` carries its reason, and a `valid` row carries its review. `/reset`
erases it; the tenant's deletion cascades.

`0198_expert_review_inputs.sql` (M32.C1.L-contract.V0.U07): a review keeps what the file WAS when it
was judged — its fingerprint's inputs, an object — so a later review says what moved by a diff. Null
only on a row from before 0198; the check holds its shape, never its presence (the previous image
writes none).

`0199_expert_review_triggers.sql` (M32.C1.L-contract.V0.U08): a review keeps what triggered it — a list
of each trigger's kind and what moved (`05` §5), null only on a row from before 0199.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from genios_engine.api import account_routes

ORG = "er0197_org"
AT = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
STATUSES = ("valid", "refused", "truncated", "over_budget", "failed")


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'er0197@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _insert(c, **over):
    row = {"o": ORG, "file": "node_fund_neel", "fp": "fp_1", "model": "claude-sonnet-5",
           "pv": "expert-review.v1", "digest": "sha256:d1", "status": "valid", "reason": None,
           "review": json.dumps({"mode": "act"}), "tin": 4200, "tout": 900, "cost": 26_100, "at": AT,
           "inputs": json.dumps({"events": ["evt_1"], "whose_move": "ours"}),
           "triggers": json.dumps([{"kind": "new_evidence", "says": "new since: evt_1"}])}
    row.update(over)
    c.execute(text(
        "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, "
        "dossier_digest, status, reason, review, input_tokens, output_tokens, cost_micro_usd, "
        "reviewed_at, inputs, triggers) values (:o, :file, :fp, :model, :pv, :digest, :status, "
        ":reason, cast(:review as jsonb), :tin, :tout, :cost, :at, cast(:inputs as jsonb), "
        "cast(:triggers as jsonb))"), row)


@pytest.mark.pg
def test_the_table_has_the_columns_the_readers_need(engine):
    with engine.connect() as c:
        cols = {r.column_name: (r.data_type, r.is_nullable) for r in c.execute(text(
            "select column_name, data_type, is_nullable from information_schema.columns "
            "where table_name = 'expert_reviews'"))}
    assert cols == {
        "org_id": ("text", "NO"), "file_id": ("text", "NO"), "fingerprint": ("text", "NO"),
        "model": ("text", "NO"), "prompt_version": ("text", "NO"), "dossier_digest": ("text", "NO"),
        "status": ("text", "NO"), "reason": ("text", "YES"), "review": ("jsonb", "YES"),
        "input_tokens": ("integer", "NO"), "output_tokens": ("integer", "NO"),
        "cost_micro_usd": ("bigint", "NO"),
        "reviewed_at": ("timestamp with time zone", "NO"),
        # ⛔ MOVED by M32.C1.L-contract.V0.U07 (0198), deliberately: what the file was when judged.
        "inputs": ("jsonb", "YES"),
        # ⛔ MOVED by M32.C1.L-contract.V0.U08 (0199), deliberately: what triggered the review.
        "triggers": ("jsonb", "YES"),
    }


@pytest.mark.pg
def test_a_review_keeps_what_triggered_it(engine):
    with engine.begin() as c:
        _insert(c)
        _insert(c, fp="fp_before_0199", triggers=None)
        _insert(c, fp="fp_first", triggers=json.dumps([]))           # an empty list is a list
        kept = dict(c.execute(text("select fingerprint, triggers from expert_reviews "
                                   "where org_id = :o"), {"o": ORG}).fetchall())
    assert kept == {"fp_1": [{"kind": "new_evidence", "says": "new since: evt_1"}],
                    "fp_before_0199": None, "fp_first": []}


@pytest.mark.pg
@pytest.mark.parametrize("triggers", ['{"kind": "new_evidence"}', '"new_evidence"', "1", "null"])
def test_triggers_that_are_not_a_list_are_refused(engine, triggers):
    with pytest.raises(IntegrityError, match="expert_reviews_triggers_check"):
        with engine.begin() as c:
            _insert(c, triggers=triggers)


@pytest.mark.pg
def test_a_review_keeps_what_the_file_was(engine):
    with engine.begin() as c:
        _insert(c)
        _insert(c, fp="fp_before_0198", inputs=None)            # a row from before 0198 reads as null
        kept = dict(c.execute(text("select fingerprint, inputs from expert_reviews where org_id = :o"),
                              {"o": ORG}).fetchall())
    assert kept == {"fp_1": {"events": ["evt_1"], "whose_move": "ours"}, "fp_before_0198": None}


@pytest.mark.pg
@pytest.mark.parametrize("inputs", ['["evt_1"]', '"evt_1"', "7", "null"])
def test_inputs_that_are_not_an_object_are_refused(engine, inputs):
    """A JSON null is not SQL null: what the file was is an object, or nothing at all."""
    with pytest.raises(IntegrityError, match="expert_reviews_inputs_check"):
        with engine.begin() as c:
            _insert(c, inputs=inputs)


@pytest.mark.pg
def test_one_review_per_file_per_fingerprint(engine):
    with engine.begin() as c:
        _insert(c)
        _insert(c, fp="fp_2")                                  # the file moved: a new review
        _insert(c, file="node_programme_iitd")                 # another file, the same fingerprint
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, status="refused", reason="unknown_evidence", review=None)


@pytest.mark.pg
@pytest.mark.parametrize("status", STATUSES)
def test_every_named_status_is_accepted(engine, status):
    with engine.begin() as c:
        _insert(c, status=status, reason=None if status == "valid" else f"why it was {status}")


@pytest.mark.pg
def test_an_unknown_status_is_refused(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, status="skipped", reason="nobody said")


@pytest.mark.pg
@pytest.mark.parametrize("status", [s for s in STATUSES if s != "valid"])
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_a_refusal_without_its_reason_is_refused(engine, status, reason):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, status=status, reason=reason, review=None)


@pytest.mark.pg
def test_a_valid_review_carries_the_review(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, review=None)


@pytest.mark.pg
def test_a_refused_review_may_keep_what_the_model_wrote(engine):
    with engine.begin() as c:
        _insert(c, status="refused", reason="number_not_in_dossier: 32")
        kept = c.execute(text("select review ->> 'mode' from expert_reviews where org_id = :o"),
                         {"o": ORG}).scalar()
    assert kept == "act"


@pytest.mark.pg
@pytest.mark.parametrize("column", ["tin", "tout", "cost"])
def test_a_negative_cost_is_refused(engine, column):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, **{column: -1})


@pytest.mark.pg
def test_the_latest_review_of_a_file_has_its_index(engine):
    with engine.connect() as c:
        defn = c.execute(text("select indexdef from pg_indexes where tablename = 'expert_reviews' "
                              "and indexname = 'expert_reviews_latest'")).scalar()
    assert defn is not None and "(org_id, file_id, reviewed_at DESC)" in defn


@pytest.mark.pg
def test_deleting_the_tenant_cascades(engine):
    with engine.begin() as c:
        _insert(c)
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        left = c.execute(text("select count(*) from expert_reviews where org_id = :o"),
                         {"o": ORG}).scalar()
    assert left == 0


def test_reset_names_the_table():
    assert "expert_reviews" in account_routes._ORG_SCOPED_TABLES


@pytest.mark.pg
def test_the_wipe_leaves_no_review_of_the_tenant(engine):
    with engine.begin() as c:
        _insert(c)
        _insert(c, fp="fp_2", status="over_budget", reason="the day's $2 was spent", review=None)
        wiped = account_routes._wipe(c, ORG)
        left = c.execute(text("select count(*) from expert_reviews where org_id = :o"),
                         {"o": ORG}).scalar()
    assert wiped["expert_reviews"] == 2 and left == 0

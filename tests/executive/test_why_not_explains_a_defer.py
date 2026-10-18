"""STEP-02 · "why didn't GeniOS tell me?" — for a DEFER, the answer is that it could not decide.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/executive/test_why_not_explains_a_defer.py -q

Tree `yc2_w27_s02/M20.C5.L-interface.V1.U02`. Until `M20.C5.L-logic.V0.U01` a DEFER was logged as
`shadow`, and `why_not` explained it as *"the pack is in shadow mode"* — false: the pack was live and
the decider could not decide. A `deferred` row now says what happened, and that the card the
founder already saw is still there.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.executive import explain

ORG = "whynot_defer_org"


def test_a_deferred_suppression_has_its_own_sentence():
    sentence = explain._REASON_HUMAN["deferred"]
    assert "could not decide" in sentence and "card" in sentence
    assert "shadow" not in sentence


@pytest.mark.pg
def test_why_not_reads_a_deferred_row_back_in_words(pg_store):
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("needs GENIOS_TEST_DATABASE_URL")
    at = datetime.now(timezone.utc)
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'whynot@example.test')"),
                  {"o": ORG})
        c.execute(text(
            "insert into signal_suppression_log (org_id, rule_id, subject_node_id, reason_code, "
            "detail, eval_time) values (:o, 'unanswered_email', 'n1', 'deferred', "
            "cast(:d as jsonb), :t)"),
            {"o": ORG, "d": json.dumps({"uncertainty": ["llm_decision_unavailable:no_client"]}),
             "t": at})
    try:
        rows = explain.why_not(pg_store, ORG)["suppressions"]
        assert [(r["reason_code"], r["reason"]) for r in rows] == [
            ("deferred", explain._REASON_HUMAN["deferred"])]
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from orgs where id = :o"), {"o": ORG})

"""STEP-10 · the health check: every reply time written as a normal says its n, and none rests on fewer than five.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_numbers.py -q

`scripts/pipeline_health.check_every_normal_says_its_n` (tree `yc2_w27_s10 · M29.C6.L-interface.V3.U03`). On
the golden set the only normals were "tenant normals" built from ONE reply counted twice, with no n anywhere
(`STEP-10` §8.1, F17 and F25). The waiting pass now writes a normal only at `NORMAL_AT` with its n beside it
(`06` D37); this check holds production to it: every `party.reply_cadence_*`, `party.our_reply_*` and
`derived.our_reply_*` written as current says its n, and none is below five. It names the file each failing
number is on — the counterparty the founder would see it beside, the same files `GET /v1/workstreams`
serves — and a tenant with no normal written measures nothing, and says so. Read only.
"""
from __future__ import annotations

import ast
import inspect
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.periodic import _ensure_tenant_node
from genios_engine.context.waiting import compute_waiting
from tests.context.workstream_world import FOUNDER, T0, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_health_numbers"
PRIYA = "priya@northwind.test"
KAVITHA = "kavitha@inboxmail.test"
NOW = T0 + timedelta(days=60)


def _health():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


def test_the_check_runs_in_every_audit():
    assert _health().check_every_normal_says_its_n in _health().CHECKS


def test_it_names_files_by_the_answer_the_file_list_serves():
    tree = ast.parse(inspect.getsource(_health().check_every_normal_says_its_n))
    called = {getattr(n.func, "id", getattr(n.func, "attr", None)) for n in ast.walk(tree)
              if isinstance(n, ast.Call)}
    assert "files_for" in called


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        _ensure_tenant_node(pg_store, c, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _check(store):
    from scripts._gate import read_only_connection
    conn = read_only_connection(store.engine)
    try:
        return _health().check_every_normal_says_its_n(conn, ORG)
    finally:
        conn.close()


def _five_replies(store):
    for i, gap in enumerate((1, 2, 2, 3, 9)):
        asked = T0 + timedelta(days=5 * i)
        process(store, ORG, event_id=f"evt_ask_{i}", sender=FOUNDER, recipients=(PRIYA,),
                thread=f"t_{i}", at=asked)
        process(store, ORG, event_id=f"evt_her_{i}", sender=PRIYA, thread=f"t_{i}",
                at=asked + timedelta(days=gap))
    compute_waiting(store, ORG, now=NOW)


def _fact(store, key: str, field: str, value: str, *, at=T0):
    subject = node(store, ORG, key).node_id
    with store.engine.begin() as c:
        c.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            " value, value_type, status, authority_rank, confidence, occurred_at, valid_from) "
            "values (:v, :f, :o, :n, :field, cast(:val as jsonb), 'number', 'active', 2, 0.9, "
            "        :at, :at)"),
            {"v": f"fv_t_{key}_{field}", "f": f"f_t_{key}_{field}", "o": ORG, "n": subject,
             "field": field, "val": value, "at": at})


def test_a_tenant_with_no_normal_measures_nothing_and_says_so(store):
    process(store, ORG, event_id="evt_hello", sender=PRIYA, thread="t_hello", at=T0)
    check = _check(store)
    assert check.ok and check.measured.startswith("not exercised")


def test_normals_written_with_their_n_pass(store):
    _five_replies(store)
    check = _check(store)
    assert check.ok, check.detail
    assert check.measured == "1 normal(s) written, each with its n and none below 5"


def test_a_normal_with_no_n_fails_and_names_its_file(store):
    """A cadence written before STEP-10 — the golden F25 shape: one reply, a tenant normal, no n."""
    process(store, ORG, event_id="evt_offer", sender=FOUNDER, recipients=(KAVITHA,),
            thread="t_offer", at=T0)
    process(store, ORG, event_id="evt_yes", sender=KAVITHA, thread="t_offer",
            at=T0 + timedelta(days=1.92))
    _fact(store, KAVITHA, "party.reply_cadence_days", "1.92")
    check = _check(store)
    assert not check.ok
    assert check.detail == ["inboxmail.test — kavitha@inboxmail.test: party.reply_cadence_days "
                            "1.92 has no n beside it"]


def test_a_normal_below_five_fails_and_names_its_file(store):
    """Four is one short: the boundary is five (`06` D37), not "a few"."""
    _five_replies(store)
    _fact(store, PRIYA, "party.our_reply_days", "1.0")
    _fact(store, PRIYA, "party.our_reply_n", "4")
    check = _check(store)
    assert not check.ok
    assert check.detail == ["northwind.test — priya@northwind.test: party.our_reply_days 1.0 "
                            "rests on 4, fewer than 5"]


def test_the_overall_normal_is_held_to_it_too(store):
    _five_replies(store)
    _fact(store, f"tenant:{ORG}", "derived.our_reply_days", "1.5")
    _fact(store, f"tenant:{ORG}", "derived.our_reply_n", "3")
    check = _check(store)
    assert not check.ok
    assert check.detail == [f"the tenant — tenant:{ORG}: derived.our_reply_days 1.5 rests on 3, "
                            "fewer than 5"]


def test_a_retired_normal_is_not_held_against_anyone(store):
    _five_replies(store)
    _fact(store, PRIYA, "party.our_reply_days", "1.0")
    with store.engine.begin() as c:
        c.execute(text("update graph_facts set valid_to = now(), status = 'superseded' "
                       " where org_id = :o and field = 'party.our_reply_days'"), {"o": ORG})
    assert _check(store).ok

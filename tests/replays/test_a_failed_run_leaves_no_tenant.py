"""STEP-10 · a golden run that fails leaves no tenant behind — even one asked to keep it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_a_failed_run_leaves_no_tenant.py -q

`tests/replays/engine_runner.run_case` (tree `yc2_w27_s10 · M29.C6.L-integration.V0.U06`). Found by STEP-10's
QA: F45's cassette miss failed its own test and then two more that have nothing to do with it —
`test_the_list_route_separates_the_live_from_the_switched_off`, in `test_l1_pilot_activation` and
`test_l2_pilot_activation`, which read every activation in the shared database and found `org_golden_f45`
still switched on. `keep=True` keeps a tenant for the reader of a run that FINISHED; a run that raised hands
nobody its tenant to remove, so the runner kept it for no one. Now a run that does not finish removes its
tenant whatever `keep` says, and one failure is one failure.
"""
from __future__ import annotations

import os

import pytest

from tests.replays.founder_case import load_cases

CASES = {c.case_id: c for c in load_cases()}
ORG = "org_golden_a_failed_run"


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _left(routes) -> dict:
    from sqlalchemy import text
    with routes._graph.engine.connect() as c:
        return {table: c.execute(text(f"select count(*) from {table} where {column} = :o"),
                                 {"o": ORG}).scalar()
                for table, column in (("orgs", "id"), ("l1_semantic_activation", "org_id"),
                                      ("l2_v2_activation", "org_id"), ("source_events", "org_id"))}


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("keep", [True, False])
def test_a_run_that_raises_removes_its_tenant(keep):
    _scratch_db()
    from genios_engine.api import routes
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import CassetteMiss, RecordedLLM

    with pytest.raises(CassetteMiss):
        run_case(CASES["F47"], RecordedLLM({}), org_id=ORG, keep=keep)
    assert not any(_left(routes).values()), _left(routes)
    assert ORG not in routes._LIVE_ORGS


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("keep", [True, False])
def test_a_run_that_finishes_keeps_its_tenant_only_when_asked(keep):
    """The other half of the contract: the reader of a finished run gets its tenant when it asks,
    and only then."""
    _scratch_db()
    from genios_engine.api import routes
    from tests.replays import cassettes
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    case = CASES["F47"]
    run = run_case(case, RecordedLLM(cassettes.load(case)), org_id=ORG, keep=keep)
    try:
        assert run.misses == () and _left(routes)["orgs"] == (1 if keep else 0)
    finally:
        if keep:
            remove_tenant(routes._graph.engine, ORG)

"""STEP-10 · a golden run starts with no memory of who the last run's tenant knew.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_a_case_starts_with_no_memory_of_its_senders.py -q

`tests/replays/engine_runner.cold_start` (tree `yc2_w27_s10 · M29.C6.L-integration.V0.U05`). Found by
STEP-10's QA: the whole suite missed F45's cassette at the relevance site twice, where the golden lane and
every run of the case alone replayed it exactly. `api/routes._SENDER_CACHE` holds each tenant's known
counterparties for five minutes of process memory (`_SENDER_TTL_S`), and the runner never emptied it — so
a run of F45 inside five minutes of another run of `org_golden_f45` that had already read Meera into the
graph found her KNOWN at its first sweep, judged her questions without the model, and asked the model a
page it never asked when it was recorded. F45 is the first case whose sender is first seen in one sweep
and still ambiguous in the next, which is why no earlier case showed it. Now `cold_start` empties that
cache with the model caches: every run starts as the recording did, in a process that knows nobody.
"""
from __future__ import annotations

import os
import time

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

CASES = {c.case_id: c for c in load_cases()}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def test_cold_start_forgets_every_tenants_known_senders():
    from genios_engine.api import routes
    from tests.replays.engine_runner import COLD_CACHES, cold_start

    assert ("genios_engine.api.routes", "_SENDER_CACHE") in COLD_CACHES
    routes._SENDER_CACHE["org_golden_somebody"] = (time.time(), frozenset({"a@b.test"}))
    cold_start()
    assert routes._SENDER_CACHE == {}


@pytest.mark.pg
@pytest.mark.golden
def test_a_case_replays_exactly_after_a_run_that_already_knew_its_sender():
    """The whole suite's shape, made certain: a moment ago this process ran F45 to its end and read
    Meera as known. Left as it was, the next run of F45 asks the relevance page `fea5a51d5ba5…` — the
    key the whole suite missed in `test_we_are_never_the_subject[F45]`.

    The other key it missed, `679dd0acaf92…` (`test_the_gate_deletes_nothing…[F45]`), is the same
    memory running out between the case's two sweeps — an entry an earlier run made five minutes
    before; measured by expiring it before the second sweep. No earlier entry survives `cold_start`,
    and a run's own entry would need five minutes between its sweeps to run out (they are seconds
    apart), so that one is not timed here: a test that waits on the wall clock is the flake it would
    be guarding against."""
    _scratch_db()
    from genios_engine.api import routes
    from tests.replays.engine_runner import ORG_PREFIX, run_case
    from tests.replays.harness import RecordedLLM

    case = CASES["F45"]
    routes._SENDER_CACHE[f"{ORG_PREFIX}f45"] = (time.time(), frozenset({"meera@bluepeak.test"}))
    llm = RecordedLLM(cassettes.load(case))
    run = run_case(case, llm)
    assert not llm.misses and run.misses == ()

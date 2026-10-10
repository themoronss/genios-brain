"""STEP-04 C5 · a case may name the product's own sending domains, and the runner runs it with them.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/replays/test_a_case_names_the_platforms_domain.py -q

`yc2_w27_align` M34.C1.L-data.V0.U03. The design partner's company domain is also the domain GeniOS
sends from (`settings.platform_domains`), and an address on a platform domain reads as the product's
own (`context/pipeline.is_platform_sender`). No golden case could show that shape: the default,
`thegenios.com`, is a real name a case may not carry. So a case names its platform domains
(`FounderCase.platform_domains`), and `engine_runner.production_switches` sets them for its run and
puts production's back after it.
"""
from __future__ import annotations

import ast
import inspect
import os

import pytest

from tests.replays import engine_runner


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def test_run_case_hands_the_runner_the_cases_own_domains():
    """The wiring, read off the code: `run_case` opens production's switches with the case's domains."""
    tree = ast.parse(inspect.getsource(engine_runner.run_case))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "production_switches"]
    assert calls, "run_case no longer opens production_switches"
    assert all(any(k.arg == "platform_domains" and ast.unparse(k.value) == "case.platform_domains"
                   for k in c.keywords) for c in calls), [ast.unparse(c) for c in calls]


@pytest.mark.pg
def test_the_runner_runs_with_the_cases_domains_and_puts_productions_back():
    _scratch_db()
    from genios_engine.context.pipeline import is_platform_sender
    from genios_engine.platform.config import get_settings

    before = get_settings().platform_domains
    with engine_runner.production_switches(object(), platform_domains=("relaygrid.test",)):
        assert get_settings().platform_domains == "relaygrid.test"
        assert is_platform_sender("alerts@relaygrid.test")
    assert get_settings().platform_domains == before
    with engine_runner.production_switches(object()):
        assert get_settings().platform_domains == before, "a case that names none keeps production's"

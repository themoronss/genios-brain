"""STEP-11 · the golden founder has the Founder Office switched on, as the pilot org will.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 \
        pytest tests/replays/test_the_golden_founder_has_the_founder_office.py -q

Tree `yc2_w27_s11 · M30.C1.L-integration.V2.U04`, `06` D2. The Founder Office corpus is `default_on:
false`: a tenant nobody configured never hears from it, and `scripts/activate_tenant.py --domains
admin,founder_office` switches it on for the pilot org alone. The golden runner does the same for
every golden tenant — `engine_runner.switch_on_founder_office`, right after the switch-on every tenant
gets — so the golden set measures what the founder will run: fundraising situations on the founder's
own live lane, refused as `unreviewed` until the founder's review admits the capability (D45).
"""
from __future__ import annotations

import ast
import inspect
import os

import pytest

from tests.replays import engine_runner as er
from tests.replays import founder_case as fc

needs_db = pytest.mark.skipif(not os.environ.get(er.SCRATCH_ENV),
                              reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def test_run_case_switches_it_on_right_after_every_tenant_s_switch_on():
    """The order is the claim: after `_ensure_tenant_live`, before the first sweep."""
    body = ast.parse(inspect.getsource(er.run_case))
    calls = [name for _, name in sorted(
        (node.lineno, node.func.attr if isinstance(node.func, ast.Attribute)
         else getattr(node.func, "id", ""))
        for node in ast.walk(body) if isinstance(node, ast.Call))]
    assert "switch_on_founder_office" in calls
    assert calls.index("_ensure_tenant_live") < calls.index("switch_on_founder_office")
    assert calls.index("switch_on_founder_office") < calls.index("_land")


def test_it_is_the_founder_office_and_nothing_else():
    assert er.FOUNDER_DOMAIN == "founder_office"
    from genios_engine.platform.l3_activation import L3_DOMAINS
    assert er.FOUNDER_DOMAIN in L3_DOMAINS


@needs_db
@pytest.mark.pg
def test_a_golden_tenant_runs_with_admin_and_the_founder_office(pg_store):
    from genios_engine.api import routes
    from genios_engine.platform.intelligence_onboarding import provision_intelligence
    from genios_engine.platform.l3_activation import activated_domains

    er.pin_scratch_database()
    case = fc.load_cases()[0]
    org = f"{er.ORG_PREFIX}founder_office_probe"
    try:
        er._fresh_tenant(pg_store.engine, org, case)
        provision_intelligence(pg_store.engine, org)
        routes._ensure_tenant_live(org)
        er.switch_on_founder_office(pg_store.engine, org)
        er.switch_on_founder_office(pg_store.engine, org)            # a re-run doubles nothing
        domains = set(activated_domains(pg_store.engine, org))
        assert {"admin", "founder_office"} <= domains
        assert "sales" not in domains, "Sales stays off (06 D2)"
    finally:
        er.remove_tenant(pg_store.engine, org)
    assert "founder_office" not in set(activated_domains(pg_store.engine, org))

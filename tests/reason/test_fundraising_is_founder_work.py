"""STEP-11 · fundraising is founder work — the L2 domain lands on the Founder Office, never on Sales.

    .venv/bin/python -m pytest tests/reason/test_fundraising_is_founder_work.py -q

Tree `yc2_w27_s11 · M30.C1.L-logic.V1.U02`, `06` D2. On the golden set all 23 fundraising situations
(18 of 47 cases) were DARK: `_L2_TO_L3_DOMAIN["fundraising"]` was None, and the only candidate route
pointed at the Sales copy of investor relations (STEP-11 §8.1). The doctrine now lives in the Founder
Office corpus (M30.C6.L-data.V1.U01), the domain maps there, the candidate route is retired with its
reason, and `DARK_DOMAINS` no longer lists it. The two safety properties stay: every type
`fundraising` mints lands on founder doctrine and nothing generic, and `live_lane` still needs the
tenant to have switched the corpus on — the pilot org alone.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def founder():
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
    return ExpertBrainCatalog(default_authoring_root()).domains["founder_office"]


def test_fundraising_maps_to_the_founder_office():
    from genios_engine.reason.domain_shadow import _L2_TO_L3_DOMAIN, l3_domain_for
    assert _L2_TO_L3_DOMAIN["fundraising"] == "founder_office"
    assert l3_domain_for("fundraising") == l3_domain_for(" Fundraising ") == "founder_office"


def test_it_is_dark_no_more():
    from genios_engine.context.domain_silence import DARK_DOMAINS, is_dark
    assert "fundraising" not in DARK_DOMAINS and not is_dark("fundraising")
    assert set(DARK_DOMAINS) == {"general"}


def test_the_candidate_route_is_retired_with_its_reason():
    from genios_engine.reason.domain_shadow import CANDIDATE_ROUTES, RETIRED_CANDIDATE_ROUTES
    assert "fundraising" not in CANDIDATE_ROUTES
    why = RETIRED_CANDIDATE_ROUTES["fundraising"]
    assert why.startswith("ENDED 2026-10-09") and "founder_office" in why


def test_every_type_fundraising_mints_lands_on_founder_doctrine_only(founder):
    """⛔ THE SAFETY PROPERTY the candidate route argued for, now held by the Founder Office: every
    situation type `fundraising` mints routes to investor-named founder situations and capabilities."""
    from genios_engine.context.domain_spec import spec_for
    types = set(spec_for("fundraising").situation_types.values())
    assert types, "fundraising mints no situation type"
    for situation_type in types:
        route = founder.routes.get(situation_type)
        assert route, f"the Founder Office routes no {situation_type}"
        assert route.get("situations") and all(
            s.startswith("founder_office.sit.") and "investor" in s for s in route["situations"])
        assert set(route.get("capabilities") or ()) == {"founder_office.fundraising.investor_relations"}


def test_the_lane_is_live_only_where_the_tenant_switched_it_on():
    from genios_engine.reason.domain_shadow import l3_domain_for, live_lane
    domain = l3_domain_for("fundraising")
    assert live_lane(forced=False, domain=domain, activated=frozenset({"admin"})) is False
    assert live_lane(forced=False, domain=domain, activated=frozenset({"admin", "founder_office"}))

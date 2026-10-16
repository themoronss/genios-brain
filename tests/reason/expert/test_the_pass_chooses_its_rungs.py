"""STEP-13b · the pass chooses the rungs it climbs — a lone client asks once, a ladder of clients climbs.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_pass_chooses_its_rungs.py

Tree `yc2_w27_s13b` M38.C2.L-integration.V12.U05 (`reason/expert/sweep._clients`). Production's pass asks the R-sites' door
for a client per rung (`llm_sites.make_site_client(tier)`): Haiku-class then Sonnet-class by default, an Opus-class
third only where the tenant allows it (s13b-D1); the ladder can start at T2 for a tenant by configuration (s13b-D2),
no code. No client for a rung is no model configured.
"""
from __future__ import annotations

import pytest

from genios_engine.reason import llm_sites
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.expert import sweep as P

pytestmark = pytest.mark.unit


class _C:
    def __init__(self, tier):
        self.tier = tier


@pytest.fixture
def door(monkeypatch):
    asked = []
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: asked.append(tier) or _C(tier))
    return asked


def test_a_lone_client_is_one_rung_on_the_sites_own_tier():
    client = object()
    assert P._clients(client, None, allow_opus=False) == [(S.tier_for(S.SITE_EXPERT), client)]


def test_production_asks_the_door_once_per_rung_cheapest_first(door):
    made = P._clients(None, None, allow_opus=False)
    assert [t for t, _c in made] == ["T1", "T2"] and door == ["T1", "T2"]
    assert [c.tier for _t, c in made] == ["T1", "T2"]


def test_the_ladder_can_start_at_the_stronger_rung_without_a_line_of_code(door):
    assert [t for t, _c in P._clients(None, ("T2",), allow_opus=False)] == ["T2"] and door == ["T2"]


def test_an_opus_rung_is_refused_until_the_tenant_allows_it(door):
    with pytest.raises(ValueError, match="Opus rung is off"):
        P._clients(None, ("T1", "T2", "T3"), allow_opus=False)
    assert door == [], "no client is built for a ladder that is refused"
    assert [t for t, _c in P._clients(None, ("T1", "T2", "T3"), allow_opus=True)] == ["T1", "T2", "T3"]


def test_a_mapping_of_clients_is_a_ladder_of_its_tiers_in_order():
    t1, t2 = object(), object()
    assert P._clients({"T2": t2, "T1": t1}, None, allow_opus=False) == [("T1", t1), ("T2", t2)]
    with pytest.raises(ValueError, match="Opus rung is off"):
        P._clients({"T1": t1, "T3": object()}, None, allow_opus=False)


def test_no_client_for_a_rung_is_no_model_configured(monkeypatch):
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: None if tier == "T2" else _C(tier))
    assert P._clients(None, None, allow_opus=False) is None
    assert P._clients({"T1": object(), "T2": None}, None, allow_opus=False) is None

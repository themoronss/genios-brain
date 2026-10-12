"""STEP-17 §3.3 · every feature the onboarding switches on is switched on — against a real database.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q \
        tests/platform/test_the_onboarding_switches_on_every_default_pg.py

`yc2_w27_s17` M40.C2.L-integration.V0.U02. `make_tenant_live` is what turns a new tenant's lane on —
measured 2026-09-13, a tenant with no `l1_semantic_activation` row got 14 facts from 1,665 events.
It is NEVER FATAL by design: a switch that raises is collected into `errors` and the tenant keeps the
rest. That is right for the tenant and means a write path that cannot write is invisible —
`tests/platform/test_every_tenant_is_switched_on.py` proves the ORDER with every table in memory, and
nothing proved the WRITES. Here they run on Postgres: no error collected, a row for every default
feature, none for a declared exclusion, and a second run that writes nothing.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.platform import l2_activation as l2
from genios_engine.platform import l4_activation as l4
from genios_engine.platform.intelligence_onboarding import (L4_DEFAULT_FEATURES, NOT_DEFAULT_ON,
                                                            make_tenant_live)

ORG = "org_s17_onboarding"


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the switches are written to real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, 'Onboarding')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _live_l4(eng) -> set[str]:
    with eng.connect() as c:
        return {r.feature for r in c.execute(text(
            "select feature from l4_activation where org_id = :o and enabled_at is not null "
            "and disabled_at is null"), {"o": ORG})}


def test_a_new_tenant_has_every_default_switched_on_and_nothing_collected_as_an_error(engine):
    result = make_tenant_live(engine, ORG)

    assert result.errors == (), result.errors
    assert result.provisioned is not None and result.provisioned.errors == (), (
        result.provisioned.errors)
    assert result.switched_on == (("l1.semantic",) + tuple(f"l2.{s}" for s in l2.SWITCHES)
                                  + tuple(f"l4.{f}" for f in L4_DEFAULT_FEATURES))
    # Read against the closed set itself, not the derived default list: every Layer 4 feature
    # nobody declared an exclusion for is live.
    assert _live_l4(engine) == set(l4.L4_FEATURES) - set(NOT_DEFAULT_ON)
    assert not _live_l4(engine) & set(NOT_DEFAULT_ON), "a declared exclusion was switched on"
    with engine.connect() as c:
        assert c.execute(text("select count(*) from l1_semantic_activation where org_id = :o"),
                         {"o": ORG}).scalar() == 1
        assert c.execute(text("select count(*) from tenant_packs where org_id = :o"),
                         {"o": ORG}).scalar() > 0, "the default packs were bound"


def test_a_second_run_writes_nothing(engine):
    make_tenant_live(engine, ORG)
    again = make_tenant_live(engine, ORG)
    assert again.errors == () and again.switched_on == ()
    assert again.provisioned is not None and again.provisioned.activated == ()

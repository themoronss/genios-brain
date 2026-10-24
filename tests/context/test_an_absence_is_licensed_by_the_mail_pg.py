"""G012 H-21 · "they have not replied" is licensed by the MAIL being covered, not by every system the domain could use.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_an_absence_is_licensed_by_the_mail_pg.py -q

The admin domain requires finance AND communication (`capture/coverage/model.PACK_REQUIREMENTS`). On the design
partner's org (local copy, 24 Oct) Gmail and Calendar were connected and fresh and no finance tool was, so 786 admin
signals carried `coverage_ready = False` and 74 situations claiming a silence were held `source_coverage_insufficient`
— among them the 11 Aug investor wave ("6 unanswered") and 24 cohorts that never replied.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context import situation_bso as B

ORG = "org_h21_absence_licence"


@pytest.mark.unit
@pytest.mark.parametrize("situation_type, domain_ready, freshness, held", [
    # the design partner's case: the domain says not ready (finance missing), the mail is fresh -> licensed
    ("awaiting_response", False, {"communication": "fresh", "calendar": "fresh"}, False),
    ("campaign_awaiting_reply", False, {"communication": "fresh"}, False),
    ("cohort_outreach_gap", False, {"communication": "fresh"}, False),
    ("condition_in_review", False, {"communication": "fresh"}, False),
    # the mail itself stale or never connected -> held, whatever the domain said
    ("awaiting_response", True, {"communication": "stale"}, True),
    ("organization_gone_quiet", None, {"communication": "not_connected"}, True),
    # a support reply may live in a helpdesk: the domain's verdict stands
    ("first_response_overdue", False, {"communication": "fresh"}, True),
    # no declaration on file -> the domain's verdict, as before; never assessed is not bad news
    ("awaiting_response", False, {}, True),
    ("awaiting_response", None, {}, False),
    # a situation that reports something PRESENT is never held for coverage
    ("account_admin", False, {"communication": "not_connected"}, False),
])
def test_an_absence_is_licensed_by_the_capability_it_rests_on(situation_type, domain_ready, freshness, held):
    l1 = SimpleNamespace(coverage_ready=domain_ready)
    assert B.absence_unlicensed(situation_type, l1, freshness) is held


@pytest.mark.unit
def test_every_absence_but_a_support_reply_rests_on_the_mail():
    assert set(B.ABSENCE_RESTS_ON) == B.ABSENCE_CLAIMING_TYPES - {"first_response_overdue"}
    assert set(B.ABSENCE_RESTS_ON.values()) == {"communication"}


@pytest.mark.unit
def test_the_builder_and_the_sweep_use_the_capability_licence():
    """The call sites: the builder sets the hold through `absence_unlicensed`, and the compiled sweep reads the
    tenant's freshness once and hands it to every situation it builds."""
    from genios_engine.reason import domain_shadow
    assert "absence_unlicensed(" in inspect.getsource(B.build_business_situation)
    source = inspect.getsource(domain_shadow.shadow_compile)
    assert "capability_freshness = read_capability_freshness(conn, org_id)" in source
    assert "capability_freshness=capability_freshness" in source


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)

    def _clean(c):
        c.execute(text("delete from source_coverage where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    with eng.begin() as c:
        _clean(c)
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        _clean(c)


@pytest.mark.pg
def test_the_freshness_is_the_tenants_latest_declaration(engine):
    with engine.begin() as c:
        assert B.read_capability_freshness(c, ORG) == {}, "never declared: the domain's verdict stands"
        for domain, at, mail in (("support", "2026-10-22T09:00:00+00:00", "stale"),
                                 ("admin", "2026-10-23T09:00:00+00:00", "fresh")):
            c.execute(text("insert into source_coverage (org_id, domain, required, connected, freshness, coverage_ready, "
                           "computed_at) values (:o, :d, '{finance,communication}', '{communication}', "
                           "cast(:f as jsonb), false, :at)"),
                      {"o": ORG, "d": domain, "f": f'{{"communication": "{mail}"}}', "at": at})
        assert B.read_capability_freshness(c, ORG) == {"communication": "fresh"}

"""STEP-07 · the golden founder has the company brief §4 would draft — accepted, and in force.

    pytest tests/replays/test_the_golden_founder_has_a_company_brief.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 \
        pytest tests/replays/test_the_golden_founder_has_a_company_brief.py -q

Tree `yc2_w27_s07 · M25.C7.L-integration.V4.U01`. The golden founder is Arjun Rao of Nimbus Labs; his
brief is `speedrun008/YC-II W27/` STEP-07 §4's first draft in the golden world's names
(`specs/founder/brief/company_brief.json`) — the recognition portal and the document locker, the intro
agent, the program he is in, the accelerators and incubators he applied to. `engine_runner._fresh_tenant`
seeds it as the founder's own accepted lines, so every case runs with it, the way a tenant does once
the founder has confirmed the draft. Nothing in it is real, and every sender it names writes in a case.
"""
from __future__ import annotations

import json
import os

import pytest

from tests.replays import engine_runner as er
from tests.replays import founder_case as fc

BRIEF = fc.FOUNDER_DIR / "brief" / "company_brief.json"


def _lines():
    from genios_engine.contracts.company_brief import CompanyBriefLine
    data = json.loads(BRIEF.read_text(encoding="utf-8"))
    return [CompanyBriefLine(line_id=f"golden_{n}", **line)
            for n, line in enumerate(data["lines"], 1)]


def test_every_line_is_a_line_the_brief_can_hold_and_it_fits_its_budget():
    from genios_engine.contracts.company_brief import compose
    lines = _lines()
    brief = compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao",
                    us=("arjun@nimbuslabs.test", "nimbuslabs.test"), lines=lines)
    assert brief.truncated == () and brief.version.startswith("cb-")
    sections = {ln.section for ln in lines}
    assert {"company", "goals", "in_motion", "connectors", "watchlist"} <= sections
    assert "us" not in sections                       # composed from STEP-04, never written


def test_no_real_name_and_every_named_sender_writes_in_a_case():
    assert fc.real_names_in(json.loads(BRIEF.read_text(encoding="utf-8"))) == []
    senders = {o.sender_email for case in fc.load_cases() for o in case.objects
               if getattr(o, "sender_email", None)}
    domains = {s.rsplit("@", 1)[1] for s in senders}
    for line in _lines():
        if line.address:
            assert line.address in senders, line.address
        if line.domain:
            assert line.domain in domains, line.domain


def test_the_brief_file_is_not_read_as_a_case():
    assert all(case.source.startswith("F") for case in fc.load_cases())


needs_db = pytest.mark.skipif(not os.environ.get(er.SCRATCH_ENV),
                              reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


@needs_db
@pytest.mark.pg
def test_a_fresh_golden_tenant_has_the_brief_in_force_and_names_its_senders(pg_store):
    from types import SimpleNamespace

    from genios_engine.api import routes
    from genios_engine.platform import company_brief

    er.pin_scratch_database()
    case = fc.load_cases()[0]
    org = f"{er.ORG_PREFIX}brief_probe"
    try:
        er._fresh_tenant(pg_store.engine, org, case)
        with pg_store.engine.connect() as c:
            first = company_brief.brief_for(c, org)
        er._fresh_tenant(pg_store.engine, org, case)                 # a re-run doubles nothing
        with pg_store.engine.connect() as c:
            again = company_brief.brief_for(c, org)
        assert first and first.version == again.version
        assert len(again.lines) == len(_lines())
        resolver = routes._sender_resolver_for(org)
        assert resolver(SimpleNamespace(actor_email="hello@introly.test"))
        assert resolver.named(SimpleNamespace(actor_email="hello@introly.test")) == \
            "connector:hello@introly.test"
        assert resolver.named(SimpleNamespace(actor_email="updates@startupsetu.gov.test")) == \
            "watchlist:startupsetu.gov.test"
        assert resolver.named(SimpleNamespace(actor_email="news@payflux.test")) is None
    finally:
        er.remove_tenant(pg_store.engine, org)


@needs_db
@pytest.mark.pg
def test_the_junk_filter_a_golden_run_builds_reads_the_brief_as_production_does(pg_store):
    from genios_engine.api import routes

    er.pin_scratch_database()
    with er.production_switches(llm=object()):
        gate = routes.make_relevance_classifier("org_golden_probe")
    assert getattr(gate, "_brief_source", None) is routes._graph

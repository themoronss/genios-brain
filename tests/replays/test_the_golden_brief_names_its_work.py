"""STEP-11 · the golden founder's work in motion names each kind of work and its counterparty.

    pytest tests/replays/test_the_golden_brief_names_its_work.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 \
        pytest tests/replays/test_the_golden_brief_names_its_work.py -q

Tree `yc2_w27_s11 · M30.C4.L-integration.V2.U05`, `06` D31. The golden brief's work in motion was five
grouped sentences — "Fundraising — five funds written to in one wave; Banyan Seed Fund, Northfield
Ventures, …" — so no line named a counterparty and no golden file could know its kind of work, nor
read the playbook for it. An in-motion line names ONE counterparty (`contracts/company_brief`): the
golden founder's work is now one line per fund, programme, portal, hire and partner, each with its
kind — the shape `reason/brief_drafter` v2 proposes — and `engine_runner.seed_company_brief` carries
the kind into the store. The kind word leads each line's text, because the kind itself is never shown
to a model.
"""
from __future__ import annotations

import json
import os

import pytest

from tests.replays import engine_runner as er
from tests.replays import founder_case as fc

BRIEF = fc.FOUNDER_DIR / "brief" / "company_brief.json"

#: Who the golden founder's work is with, by kind — every one a sender in some case.
EXPECTED = {
    "investor": {"banyanseed.test", "northfieldvc.test", "harborpoint.test", "tuskercap.test",
                 "fjordvp.test", "lumenvc.test"},
    "program": {"lakshya.test", "gulflaunchpad.test", "ditincubator.test", "techbridge.test",
                "awadhec.test", "unistartupcell.test", "statestartup.gov.test"},
    "compliance": {"startupsetu.gov.test", "digivault.gov.test"},
    "hiring": {"kavitha.nair@inboxmail.test"},
    "partner": {"orbitly.test", "cleanwave.test", "novacore.test", "memloop.test"},
}
WORD = {"investor": "Raise", "program": "Program", "compliance": "Compliance", "hiring": "Hiring",
        "partner": "Partner"}


def _motion() -> list[dict]:
    data = json.loads(BRIEF.read_text(encoding="utf-8"))
    return [line for line in data["lines"] if line["section"] == "in_motion"]


def test_every_in_motion_line_names_its_kind_and_one_counterparty():
    for line in _motion():
        assert line.get("kind"), line["text"]
        assert bool(line.get("address")) != bool(line.get("domain")), line["text"]


def test_the_work_is_who_the_founder_works_with():
    named: dict[str, set[str]] = {}
    for line in _motion():
        named.setdefault(line["kind"], set()).add(line.get("address") or line.get("domain"))
    assert named == EXPECTED


def test_each_line_says_its_kind_in_words_a_model_can_read():
    for line in _motion():
        assert line["text"].startswith(f"{WORD[line['kind']]} · "), line["text"]


def test_the_brief_still_fits_its_budget_whole():
    from genios_engine.contracts.company_brief import CompanyBriefLine, compose
    data = json.loads(BRIEF.read_text(encoding="utf-8"))
    lines = [CompanyBriefLine(line_id=f"golden_{n}", **line) for n, line in enumerate(data["lines"], 1)]
    brief = compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao",
                    us=("arjun@nimbuslabs.test",), lines=lines)
    assert brief.truncated == ()
    assert "Work in motion:" in brief.text and "[investor]" not in brief.text


needs_db = pytest.mark.skipif(not os.environ.get(er.SCRATCH_ENV),
                              reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


@needs_db
@pytest.mark.pg
def test_a_fresh_golden_tenant_keeps_each_line_s_kind(pg_store):
    from genios_engine.platform import company_brief

    er.pin_scratch_database()
    case = fc.load_cases()[0]
    org = f"{er.ORG_PREFIX}brief_kinds"
    try:
        er._fresh_tenant(pg_store.engine, org, case)
        with pg_store.engine.connect() as c:
            brief = company_brief.brief_for(c, org)
        kinds: dict[str, set[str]] = {}
        for line in brief.lines:
            if line.section == "in_motion":
                kinds.setdefault(line.kind, set()).add(line.address or line.domain)
        assert kinds == EXPECTED
    finally:
        er.remove_tenant(pg_store.engine, org)

"""STEP-13 · a resolution claim names the brief it was made under (`03` F83).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/lifecycle/test_a_claim_names_its_brief.py

Tree `yc2_w27_s13` M35.C5.L-data.V0.U01. Since STEP-07 every resolution prompt carries the tenant's company
brief, and its audit row (`l2_model_runs`) names it — `m4…+cb-…` — but the claim the judge made from the
answer kept the judge's own `PROMPT_VERSION`: *why did this situation close* was answerable from the claim,
*under which brief* only by matching the audit rows by time. The claim now carries the version its audit row
carries; a tenant with no accepted line records `PROMPT_VERSION` in both, as before.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.context.lifecycle import store as store_mod
from genios_engine.context.lifecycle.contract import PROMPT_VERSION
from genios_engine.context.lifecycle.resolution import detect_resolutions
from genios_engine.platform import company_brief as CB
from genios_engine.platform import company_brief_store as BS

from .conftest import AT, ScriptedModel, answer_for
from .test_resolution import RESOLUTION_TEXT, _drop, _ids, _seed

pytestmark = pytest.mark.pg

WITH_BRIEF, PLAIN = "org_s13_claim_brief", "org_s13_claim_plain"


def _clear(store, org: str) -> None:
    _drop(store, org)
    with store.engine.begin() as c:
        for table in ("l2_model_runs", "company_brief_lines"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
    CB.invalidate(org)


@pytest.fixture
def world(pg_store):
    for org in (WITH_BRIEF, PLAIN):
        _clear(pg_store, org)
        _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
    try:
        yield pg_store
    finally:
        for org in (WITH_BRIEF, PLAIN):
            _clear(pg_store, org)


def _resolving(org: str) -> ScriptedModel:
    return ScriptedModel(answers={_ids(org)["reply"]: answer_for(
        RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
        scope=[_ids(org)["commitment"]], quote="we signed yesterday")})


def _versions(store, org: str) -> tuple[list[str], set[str]]:
    with store.engine.connect() as c:
        claims = [r[0] for r in c.execute(text(
            "select prompt_version from situation_resolution_claims where org_id = :o"), {"o": org})]
        runs = {r[0] for r in c.execute(text(
            "select prompt_version from l2_model_runs where org_id = :o and site = 'resolution'"),
            {"o": org})}
    return claims, runs


def test_a_claim_made_under_a_brief_names_it_as_its_audit_row_does(world):
    with world.engine.begin() as c:
        BS.add(c, org_id=WITH_BRIEF, section="goals", words="raise the pre-seed round",
               decided_by="founder", at=AT)
    with world.engine.connect() as c:
        brief = CB.brief_for(c, WITH_BRIEF)
    assert brief.version
    out = detect_resolutions(world, WITH_BRIEF, llm=_resolving(WITH_BRIEF), eval_time=AT)
    assert out.claims_written == 1
    claims, runs = _versions(world, WITH_BRIEF)
    assert claims == [f"{PROMPT_VERSION}+{brief.version}"] and runs == set(claims)
    # Read back as the ledger reads it: the claim object carries it too.
    with world.engine.connect() as c:
        [[claim]] = store_mod.claims_for(c, WITH_BRIEF, [_ids(WITH_BRIEF)["situation"]]).values()
    assert claim.prompt_version == f"{PROMPT_VERSION}+{brief.version}"


def test_a_claim_made_with_no_brief_keeps_the_judges_version(world):
    out = detect_resolutions(world, PLAIN, llm=_resolving(PLAIN), eval_time=AT)
    assert out.claims_written == 1
    claims, runs = _versions(world, PLAIN)
    assert claims == [PROMPT_VERSION] and runs == {PROMPT_VERSION}

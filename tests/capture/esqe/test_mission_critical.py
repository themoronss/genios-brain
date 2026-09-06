"""L1.6.7 term 4 RUNG 1 — the mission-critical tag, from the route that writes it to the score.

`EntityStanding.MISSION_CRITICAL` is the top rung of a term worth 2000 of ALG-17's 10000 basis
points, and it shipped unreachable: `baseline_reader.load_org_baseline` took `mission_critical`
as a parameter with an empty default, its own docstring recorded that *"this build has no such
tag anywhere — no column, no writer, no route"*, and nothing ever passed one. Every tenant's most
important vendor could therefore rank no higher than TOP_DECILE, which is a statement about money
— so "our single-source payroll provider" and "our largest customer" were the same kind of
important, and the difference between them did not exist.

It is measurable, and doc 06 measures it: the plan's headline acceptance row is *"$84K renewal,
12 days out, CFO sender, MISSION-CRITICAL vendor, signed PDF, org p50 $45K -> [7500, 8500]"*.
With rung 1 unreachable that row scores 7425 on the production path — below its band by exactly
the 400 bp the rung is worth.

This file walks the whole chain and nothing in it constructs an `OrgBaseline`: the route writes,
the reader reads, the factory hands the baseline to capture, and the standing comes back on a
stored score.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.esqe import baseline_reader as BR
from genios_engine.capture.esqe.importance import EntityStanding
from genios_engine.platform.db import get_engine

NOW = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)
ORG = "org_mission_critical"


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres term-4 tests skipped")
    return live_db_url


@pytest.fixture
def org(pg_url):
    engine = get_engine(pg_url)
    with engine.begin() as conn:
        conn.execute(text("delete from org_mission_critical_entities where org_id=:o"),
                     {"o": ORG})
        conn.execute(text("delete from orgs where id=:o"), {"o": ORG})
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                          f"({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{n: "scratch" for n in names}})
    yield pg_url
    with engine.begin() as conn:
        conn.execute(text("delete from org_mission_critical_entities where org_id=:o"),
                     {"o": ORG})
        conn.execute(text("delete from orgs where id=:o"), {"o": ORG})


def _tag(name: str, note: str = "single-source provider"):
    from genios_engine.api.routes import MissionCriticalEntity, tag_mission_critical
    from genios_engine.platform.auth import AuthCtx
    return tag_mission_critical(MissionCriticalEntity(name=name, note=note),
                                ctx=AuthCtx(org_id=ORG, actor_id="founder@genios.test"))


# ── the reader ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.pg
def test_a_tenant_with_no_tags_reads_an_empty_set_rather_than_failing(org):
    """The state every tenant ships in. It has to be the quiet one — a reader that raised on an
    untagged tenant would take the whole sweep down for the absence of an optional judgement."""
    assert BR.mission_critical_entities(get_engine(org), ORG) == ()


def test_an_unreachable_database_reads_no_tags_and_does_not_raise():
    """The same contract every read in `baseline_reader` has: a broken database is a cold start,
    never a 500 on the ingestion path."""
    class _Broken:
        def connect(self):
            raise RuntimeError("no")
    assert BR.mission_critical_entities(_Broken(), ORG) == ()
    assert BR.mission_critical_entities(None, ORG) == ()


@pytest.mark.pg
@pytest.mark.parametrize("written", ["Northwind Ltd", "NORTHWIND LTD", "  Northwind Ltd  ",
                                     "Northwind", "northwind ltd."])
def test_every_spelling_of_one_vendor_stores_the_same_canonical_key(org, written):
    """L1.5.4's key, not a casefold. ALG-11 drops the legal-form token before a name reaches
    term 4, so "Northwind Ltd" is looked up as `northwind`; a tag stored as `northwind ltd`
    would never compare equal to it and the vendor would score `first_seen` with no error
    anywhere. Five spellings, one row."""
    from genios_engine.capture.esqe.importance import fold_entity_key

    _tag(written)
    assert BR.mission_critical_entities(get_engine(org), ORG) == (fold_entity_key("Northwind Ltd"),)


@pytest.mark.pg
def test_tagging_the_same_entity_twice_updates_it_rather_than_duplicating_it(org):
    _tag("Northwind Ltd", note="first reason")
    rows = _tag("Northwind Ltd", note="the reason it is actually critical")["entities"]
    assert len(rows) == 1
    assert rows[0]["note"] == "the reason it is actually critical"
    assert rows[0]["name"] == "Northwind Ltd", "the display form was lost to the fold"


@pytest.mark.pg
def test_the_tag_can_be_taken_away_again(org):
    """The OFF path is a route for the same reason the ON path is: a judgement that can only be
    added is a ranking that drifts upward for ever."""
    from genios_engine.api.routes import untag_mission_critical
    from genios_engine.platform.auth import AuthCtx

    _tag("Northwind Ltd")
    ctx = AuthCtx(org_id=ORG, actor_id="founder@genios.test")
    assert untag_mission_critical("Northwind", ctx=ctx)["removed"] == 1, (
        "a vendor tagged as 'Northwind Ltd' could not be untagged as 'Northwind'; the two "
        "spellings are one canonical key")
    assert untag_mission_critical("Northwind Ltd", ctx=ctx)["removed"] == 0
    assert BR.mission_critical_entities(get_engine(org), ORG) == ()


@pytest.mark.pg
def test_a_tag_names_who_answers_for_it(org):
    """Migration 0088's argument about the floor, applied to a judgement that outranks the org's
    largest contract: an unattributed one is a ranking change nobody owns."""
    row = _tag("Northwind Ltd")["entities"][0]
    assert row["owner"] == "founder@genios.test"
    assert row["note"]
    assert row["added_at"]


@pytest.mark.pg
def test_an_empty_name_is_refused_by_the_route(org):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _tag("   ")


@pytest.mark.pg
def test_one_tenants_tags_are_never_visible_to_another(org):
    """Term 4 is a per-ORG judgement. A tag leaking across tenants would rank one company's
    vendor at the top of another company's list."""
    _tag("Northwind Ltd")
    assert BR.mission_critical_entities(get_engine(org), "org_someone_else") == ()


# ── the rung, through the baseline the production factory builds ─────────────────────────────

@pytest.mark.pg
def test_the_tag_reaches_the_baseline_and_becomes_the_top_rung(org):
    """`load_org_baseline` reads the table by DEFAULT. That default is the whole fix: the
    parameter existed before this and every caller left it empty."""
    engine = get_engine(org)
    before = BR.load_org_baseline(engine, ORG, eval_time=NOW)
    assert before.standing_of("Northwind Ltd") is EntityStanding.FIRST_SEEN

    _tag("Northwind Ltd")
    after = BR.load_org_baseline(engine, ORG, eval_time=NOW)
    from genios_engine.capture.esqe.importance import fold_entity_key
    assert after.mission_critical == frozenset({fold_entity_key("Northwind Ltd")})
    assert after.standing_of("Northwind Ltd") is EntityStanding.MISSION_CRITICAL
    assert after.standing_of("NORTHWIND LTD") is EntityStanding.MISSION_CRITICAL


@pytest.mark.pg
def test_an_explicit_argument_still_overrides_the_read(org):
    """`None` means "read it", `()` means "this tenant has none" — two different statements, and
    a caller that already holds the answer must not be forced into a second query."""
    _tag("Northwind Ltd")
    engine = get_engine(org)
    assert BR.load_org_baseline(engine, ORG, eval_time=NOW,
                                mission_critical=()).mission_critical == frozenset()
    assert BR.load_org_baseline(
        engine, ORG, eval_time=NOW,
        mission_critical=["Someone Else"]).mission_critical == frozenset({"someone else"})


@pytest.mark.pg
def test_the_production_factory_carries_the_tag_into_the_sweeps_bundle(org):
    """**THE WIRING ASSERTION.** `api/routes._esqe_stage_for` -> `wiring.make_esqe_stage` ->
    `baseline_reader.load_org_baseline` is the chain every capture door in the API goes through,
    and it is the chain that has to carry this. Nothing here builds a baseline."""
    from genios_engine.api import routes

    if routes._graph is None:
        pytest.skip("routes has no graph store — the request path cannot reach a database")
    _tag("Northwind Ltd")
    stage = routes._esqe_stage_for(ORG)
    assert stage.org_baseline is not None, "the production factory built no baseline"
    assert stage.org_baseline.standing_of("Northwind Ltd") is EntityStanding.MISSION_CRITICAL, (
        "the tag was written and the sweep's own bundle does not carry it — term 4 rung 1 is "
        "unreachable again")


def test_the_table_is_erased_with_its_tenant():
    """Doc 07: a table that survives a tenant deletion is a compliance defect. This one holds the
    tenant's own vendor names and a free-text reason, so it is theirs to have erased."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    assert "org_mission_critical_entities" in _ORG_SCOPED_TABLES


@pytest.mark.pg
def test_deleting_the_tenant_takes_its_tags_with_it(org):
    """The FK cascade, executed rather than read off the migration text."""
    _tag("Northwind Ltd")
    engine = get_engine(org)
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": ORG})
        left = conn.execute(text(
            "select count(*) from org_mission_critical_entities where org_id=:o"),
            {"o": ORG}).scalar()
    assert left == 0


@pytest.mark.pg
def test_the_stored_key_must_be_folded_at_the_database_too(org):
    """The route folds; the COLUMN also refuses an unfolded key. A second writer that skipped the
    route would otherwise store a key `standing_of` can never match, silently."""
    from sqlalchemy.exc import IntegrityError
    engine = get_engine(org)
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(text(
                "insert into org_mission_critical_entities "
                "(org_id, entity_key, display_name, owner) values (:o,'Northwind','N','x')"),
                {"o": ORG})

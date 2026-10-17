"""STEP-13b · a file's dossier parts carry its engine read, its units' readings and the company's record.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/reason/expert/test_the_dossier_reads_the_engine.py

Tree `yc2_w27_s13b` M37.C2.L-integration.V3.U05 (`dossier.read_parts`, with `reason/expert/file_engine`). The route key
is every file's — cheap, no predicate, no unit — for its fingerprint. The engine itself is read once for a file DUE for
review: the Domain Expertise of its situations and kind with what the brains learned, the twelve units in shadow, the
company's own record. A read that cannot be made is "the engine could not be read for this file", never a failed review.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.company_record import CompanyRecord
from genios_engine.contracts import engine_read as E
from genios_engine.context.workstreams import SituationLife
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import file_engine as F

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
KUNAL = "kunal@meridianvc.test"
ORG = "org_s13b_dossier_engine"
INVESTOR_SIT = SituationLife(situation_id="sit_1", situation_type="investor_relationship", domain="fundraising",
                             status="active", first_seen_at=NOW, last_seen_at=NOW, days_seen=0.0,
                             days_since_seen=0.0, quiet_window_days=14, window_from="kind", past_window=False)


def _life(*situations):
    return dataclasses.make_dataclass("L", ["situations"])(tuple(situations))


def _work(**over):
    base = dict(file_id="node_f", counterparty_type="person", counterparty_key=KUNAL, work_kind=None, people=())
    base.update(over)
    return dataclasses.make_dataclass("W", list(base))(**base)


# ── pure: what a file hands the readers ───────────────────────────────────────────────────────

def test_a_files_situations_are_their_type_and_layer_two_domain():
    sits = F.situations_of(_life(INVESTOR_SIT))
    assert [(s.situation_type, s.domain, s.situation_id) for s in sits] == [
        ("investor_relationship", "fundraising", "sit_1")]
    assert F.situations_of(_life()) == ()


def test_the_route_key_is_every_files_and_moves_with_what_its_routes_reach():
    none = F.route_key_of(_work(), _life())
    investor = F.route_key_of(_work(work_kind="investor"), _life(INVESTOR_SIT))
    assert none == "none" and investor.startswith("route-")
    assert F.route_key_of(_work(work_kind="investor"), _life(INVESTOR_SIT), domains_on=frozenset()) != investor, (
        "a corpus switched off is a different engine")
    assert F.route_key_of(_work(work_kind="investor"), _life(INVESTOR_SIT)) == investor, "deterministic"


def test_a_route_key_that_cannot_be_computed_names_nothing(monkeypatch):
    monkeypatch.setattr(F.R, "route_key", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert F.route_key_of(_work(), _life()) == "none"


def test_the_learned_tokens_are_the_files_own_address():
    work = _work(counterparty_type="company", counterparty_key="meridianvc.test", people=("node_p1", "node_p2"))
    got = F.learned_tokens(work, ["admin.executive_support.commitment_tracking"])
    assert got == ("node:node_f", "person:node_p1", "person:node_p2", "company:node_f",
                   "capability:admin.executive_support.commitment_tracking")
    assert "email:kunal@meridianvc.test" in F.learned_tokens(_work(), ())
    assert F.learned_tokens(_work(file_id="bad:id"), ()) == (
        "email:kunal@meridianvc.test",), "a value the vocabulary refuses is left out, not raised"


def test_the_authored_read_and_what_the_brains_learned_are_one_read_in_the_one_order():
    cap = E.EngineLine(ref="cap:a.b.c#q", family=E.CAPABILITY, words="q", source="a.b.c", source_version="v",
                       reviewed=False)
    org = E.EngineLine(ref="org:organization:x:v1", family=E.ORGANIZATION, words="rule", source="x",
                       source_version="1", reviewed=True)
    pb = E.EngineLine(ref="pb:p", family=E.PLAYBOOK, words="pb", source="p", source_version="v", reviewed=False)
    authored = E.EngineRead(lines=(cap, pb), cut={E.PLAYBOOK: 2}, not_read=(
        E.NotRead(situation_type="t", domain="d", reason=E.NO_ROUTE),))
    learned = E.EngineRead(lines=(org,), cut={E.PLAYBOOK: 1, E.ORGANIZATION: 3})
    both = F._merged(authored, learned)
    assert [l.ref for l in both.lines] == ["cap:a.b.c#q", "pb:p", "org:organization:x:v1"]
    assert both.cut[E.PLAYBOOK] == 3 and both.cut[E.ORGANIZATION] == 3 and both.not_read == authored.not_read


def test_a_read_that_cannot_be_made_is_the_engine_could_not_be_read_never_a_raise(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("the graph is down")
    monkeypatch.setattr(F, "_load_context", _boom)
    got = F.read_file_engine(None, ORG, _work(work_kind="investor"), _life(INVESTOR_SIT), now=NOW)
    assert got.error == F.UNREAD == "the engine could not be read for this file"
    assert got.engine is None and got.units is None and got.route_key.startswith("route-"), (
        "the fingerprint still names the engine the file would read")


# ── on a real file ───────────────────────────────────────────────────────────────────────────

@pytest.fixture
def world(pg_store):
    from tests.context.workstream_world import FOUNDER, process, reset, tenant
    tenant(pg_store, ORG)
    process(pg_store, ORG, event_id="evt_e_in", sender=KUNAL, thread="t_e", at=NOW - timedelta(days=12))
    process(pg_store, ORG, event_id="evt_e_out", sender=FOUNDER, recipients=(KUNAL,), thread="t_e",
            at=NOW - timedelta(days=10))
    with pg_store.engine.connect() as c:
        file_id = c.execute(text(
            "select distinct k.anchor_node_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id and m.correlation_id = k.correlation_id "
            " where k.org_id = :o and m.event_id = 'evt_e_in'"), {"o": ORG}).scalar_one()
    yield pg_store, file_id
    reset(pg_store, ORG)


@pytest.mark.pg
def test_a_file_not_due_carries_its_route_key_and_nothing_else_of_the_engine(world):
    store, file_id = world
    with store.engine.connect() as c:
        parts = D.read_parts(c, ORG, file_id, now=NOW)
    assert parts.route_key == "none", "this file has no situation and no kind: its routes reach nothing"
    assert (parts.engine, parts.units, parts.engine_error, parts.company) == (None, None, None, None)


@pytest.mark.pg
def test_a_due_file_carries_the_units_readings_the_engine_and_the_companys_record(world):
    store, file_id = world
    with store.engine.connect() as c:
        parts = D.read_parts(c, ORG, file_id, now=NOW, engine=True)
    assert parts.engine_error is None and parts.engine is not None
    assert [l.ref for l in parts.units.lines][-1] == "ru:not_run" and len(parts.units.lines) == 13
    assert isinstance(parts.company, CompanyRecord) and parts.company.org_id == ORG
    assert parts.route_key == "none"


@pytest.mark.pg
def test_the_company_record_read_once_a_sweep_is_the_one_handed_in(world):
    store, file_id = world
    sentinel = CompanyRecord(org_id=ORG, as_of=NOW, lines=())
    with store.engine.connect() as c:
        parts = D.read_parts(c, ORG, file_id, now=NOW, engine=True, company_record=sentinel)
    assert parts.company is sentinel


@pytest.mark.pg
def test_a_files_situations_and_kind_reach_the_domain_expertise_and_a_corpus_off_is_named(world):
    store, file_id = world
    with store.engine.connect() as c:
        base = D.read_parts(c, ORG, file_id, now=NOW)
        work = dataclasses.replace(base.file, work_kind="investor")
        life = dataclasses.replace(base.lifecycle, situations=(INVESTOR_SIT,))
        on = F.read_file_engine(c, ORG, work, life, now=NOW, domains_on=frozenset({"founder_office"}))
        off = F.read_file_engine(c, ORG, work, life, now=NOW, domains_on=frozenset({"admin"}))
    assert on.error is None
    refs = set(on.engine.refs)
    assert "cap:founder_office.fundraising.investor_relations#q" in refs
    assert any(r.startswith("cap:founder_office.fundraising.investor_relations#f") for r in refs)
    assert "founder_office.fundraising.investor_relations" in on.capabilities
    assert on.route_key.startswith("route-")
    assert off.engine.not_read and off.engine.not_read[0].reason == E.SWITCHED_OFF
    assert on.route_key != off.route_key


def _admin_rule(store, file_id, *, anchor_says):
    """`no_chase_while_we_hold_the_ball` as read over a file whose person holds `due_at` and the ball."""
    with store.engine.begin() as c:
        person = store.find_or_create_node(c, org_id=ORG, node_type="person", canonical_key=KUNAL,
                                           display_name="Kunal", event_id="evt_e_in")
        store.write_fact(c, org_id=ORG, subject_node_id=person, field="commitment.due_at",
                         value="2026-10-01T00:00:00Z", value_type="string", confidence=0.9,
                         occurred_at=NOW - timedelta(days=11), event_id="evt_e_in", evidence={}, source="gmail")
        if anchor_says:
            store.write_fact(c, org_id=ORG, subject_node_id=file_id, field="thread.ball_in_court",
                             value=anchor_says, value_type="string", confidence=0.9,
                             occurred_at=NOW - timedelta(days=11), event_id="evt_e_in", evidence={}, source="gmail")
    with store.engine.connect() as c:
        base = D.read_parts(c, ORG, file_id, now=NOW)
        work = dataclasses.replace(base.file, people=(person,))
        life = dataclasses.replace(base.lifecycle, situations=(dataclasses.replace(
            INVESTOR_SIT, situation_type="account_admin", domain="admin"),))
        got = F.read_file_engine(c, ORG, work, life, now=NOW, domains_on=frozenset({"admin"}))
    return got.engine.by_ref["cons:admin.rule.commitment_tracking.no_chase_while_we_hold_the_ball"]


@pytest.mark.pg
def test_the_facts_of_a_files_people_fill_what_its_anchor_lacks(world):
    """`commitment.due_at` lives on the people and threads, not on a company anchor: the borrow fills the gap."""
    store, file_id = world
    with store.engine.begin() as c:
        person = store.find_or_create_node(c, org_id=ORG, node_type="person", canonical_key=KUNAL,
                                           display_name="Kunal", event_id="evt_e_in")
        store.write_fact(c, org_id=ORG, subject_node_id=person, field="commitment.due_at",
                         value="2026-10-01T00:00:00Z", value_type="string", confidence=0.9,
                         occurred_at=NOW - timedelta(days=11), event_id="evt_e_in", evidence={}, source="gmail")
    with store.engine.connect() as c:
        base = D.read_parts(c, ORG, file_id, now=NOW)
        node, borrowed, _ = F._anchor(c, ORG, dataclasses.replace(base.file, people=(person,)))
        alone = F._anchor(c, ORG, dataclasses.replace(base.file, people=()))[1]
    assert "commitment.due_at" not in node.facts and "commitment.due_at" in borrowed
    assert alone == {}, "no people, nothing borrowed"


@pytest.mark.pg
def test_the_borrowed_facts_reach_the_rule_and_the_anchors_own_fact_wins_over_a_persons(world):
    """The person's `ball_in_court` is `them` (the pipeline wrote it: we wrote last); the anchor says `us` and
    OUTRANKS it — root first — so with the borrowed `due_at` the rule's condition HOLDS; with the anchor's `them` it
    does not."""
    store, file_id = world
    assert _admin_rule(store, file_id, anchor_says="us").verdict == E.HOLDS
    assert _admin_rule(store, file_id, anchor_says="them").verdict == E.FAILS


@pytest.mark.pg
def test_what_the_brains_learned_for_the_file_is_in_its_engine(world):
    store, file_id = world
    with store.engine.begin() as c:
        c.execute(text(
            "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
            "visibility_scope, visibility, active, created_at) values (:o, 'organization', "
            "'orgrule:spend:threshold', 1, 'l1', cast(:v as jsonb), 'org', cast(:vis as jsonb), true, :at)"),
            {"o": ORG, "v": json.dumps({"statement": "A spend over a lakh needs two approvers."}),
             "vis": json.dumps({"scope": "org", "principals": []}), "at": NOW - timedelta(days=3)})
    with store.engine.connect() as c:
        base = D.read_parts(c, ORG, file_id, now=NOW)
        got = F.read_file_engine(c, ORG, base.file, base.lifecycle, now=NOW)
    assert any(line.family == E.ORGANIZATION and "two approvers" in line.words for line in got.engine.lines)


# ── what each reader is handed ───────────────────────────────────────────────────────────────

def test_a_files_kind_alone_reaches_its_capability_without_a_situation():
    assert F.route_key_of(_work(work_kind="investor"), _life()).startswith("route-")
    assert F.route_key_of(_work(), _life()) == "none"


def test_a_token_named_twice_is_one_token():
    assert F.learned_tokens(_work(people=("p1", "p1")), ["c.a", "c.a"]).count("person:p1") == 1
    assert F.learned_tokens(_work(people=("p1", "p1")), ["c.a", "c.a"]).count("capability:c.a") == 1


@pytest.mark.pg
def test_the_readers_are_handed_the_anchor_the_people_and_the_time(world, monkeypatch):
    store, file_id = world
    seen = {}
    real_engine_for, real_units = F.R.engine_for, F.units_for

    def _spy_engine(situations, **kw):
        seen["anchor"], seen["activated"], seen["kind"] = kw["anchor"], kw["activated"], kw["kind"]
        return real_engine_for(situations, **kw)

    def _spy_units(context):
        seen["context"] = context
        return real_units(context)
    monkeypatch.setattr(F.R, "engine_for", _spy_engine)
    monkeypatch.setattr(F, "units_for", _spy_units)
    with store.engine.begin() as c:
        for name in ("zed", "abe"):
            node = store.find_or_create_node(c, org_id=ORG, node_type="person", canonical_key=f"{name}@x.test",
                                             display_name=name, event_id="evt_e_in")
            store.write_fact(c, org_id=ORG, subject_node_id=node, field="deal.status", value=f"{name}-open",
                             value_type="string", confidence=0.9, occurred_at=NOW, event_id="evt_e_in",
                             evidence={}, source="gmail")
            seen.setdefault("nodes", []).append((name, node))
        store.write_fact(c, org_id=ORG, subject_node_id=file_id, field="deal.owner", value="anchor-owner",
                         value_type="string", confidence=0.9, occurred_at=NOW, event_id="evt_e_in", evidence={},
                         source="gmail")
    people = tuple(n for _, n in seen["nodes"])
    first = min(seen["nodes"], key=lambda kv: kv[1])[0]
    with store.engine.connect() as c:
        base = D.read_parts(c, ORG, file_id, now=NOW)
        F.read_file_engine(c, ORG, dataclasses.replace(base.file, people=people), base.lifecycle, now=NOW,
                           domains_on=frozenset({"admin"}))
    anchor, ctx = seen["anchor"], seen["context"]
    assert anchor.edge_count == 2 and anchor.evaluation_time == NOW
    assert seen["activated"] == frozenset({"admin"})
    assert anchor.neighbor_facts["deal.status"]["value"] == f"{first}-open", "the first person (by node id) wins"
    assert anchor.facts["deal.owner"]["value"] == "anchor-owner" and "deal.status" not in anchor.facts
    assert ctx.edge_count == 2 and ctx.evaluation_time == NOW and ctx.root_entity_id == file_id
    assert ctx.facts["deal.status"]["value"] == f"{first}-open" and ctx.facts["deal.owner"]["value"] == "anchor-owner"


@pytest.mark.pg
def test_the_units_see_the_anchors_own_fact_before_a_persons(world, monkeypatch):
    store, file_id = world
    seen = {}
    real_units = F.units_for
    monkeypatch.setattr(F, "units_for", lambda ctx: (seen.setdefault("c", ctx), real_units(ctx))[1])
    with store.engine.begin() as c:
        node = store.find_or_create_node(c, org_id=ORG, node_type="person", canonical_key="p@x.test",
                                         display_name="p", event_id="evt_e_in")
        for subject, value in ((node, "theirs"), (file_id, "mine")):
            store.write_fact(c, org_id=ORG, subject_node_id=subject, field="deal.owner", value=value,
                             value_type="string", confidence=0.9, occurred_at=NOW, event_id="evt_e_in",
                             evidence={}, source="gmail")
    with store.engine.connect() as c:
        base = D.read_parts(c, ORG, file_id, now=NOW)
        F.read_file_engine(c, ORG, dataclasses.replace(base.file, people=(node,)), base.lifecycle, now=NOW)
    assert seen["c"].facts["deal.owner"]["value"] == "mine"


@pytest.mark.pg
def test_a_brain_addressed_to_the_files_node_is_read_into_its_engine(world):
    store, file_id = world
    with store.engine.begin() as c:
        c.execute(text(
            "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
            "visibility_scope, visibility, active, created_at) values (:o, 'behavior', 'behavior:engagement:n1', "
            "1, 'l2', cast(:v as jsonb), 'org', cast(:vis as jsonb), true, :at)"),
            {"o": ORG, "v": json.dumps({"pattern_statement": "Replies within a day on most threads.",
                                        "address": {"tokens": [f"node:{file_id}"]}}),
             "vis": json.dumps({"scope": "org", "principals": []}), "at": NOW - timedelta(days=3)})
    with store.engine.connect() as c:
        base = D.read_parts(c, ORG, file_id, now=NOW)
        got = F.read_file_engine(c, ORG, base.file, base.lifecycle, now=NOW)
    assert any(l.family == E.BEHAVIOUR and "Replies within a day" in l.words for l in got.engine.lines)


@pytest.mark.pg
def test_a_due_file_whose_engine_cannot_be_read_is_still_a_dossier_that_says_so(world, monkeypatch):
    store, file_id = world
    monkeypatch.setattr(F.R, "engine_for", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("corpus unreadable")))
    with store.engine.connect() as c:
        parts = D.read_parts(c, ORG, file_id, now=NOW, engine=True)
    assert parts.engine_error == "the engine could not be read for this file"
    assert parts.engine is None and parts.units is None and parts.route_key == "none" and parts.company is not None
    assert D.build_dossier(parts).text, "the dossier is built on the data alone"

"""STEP-10 · a file in two domains keeps both pasts — each domain's history is its own fact on the
anchor, and nothing is left behind that passes one domain's past off as the other's.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_history_per_file_and_domain.py -q

`context/correlation_history.publish_histories` (tree `yc2_w27_s10 · M29.C2.L-logic.V0.U03`). The
history is computed per (anchor, domain) and was published per ANCHOR — the fact id is prefix + node
+ field (`analytic/publish.derived_fact_version_id`) — so an anchor in two domains kept the
last-sorted domain's past (`STEP-10` §8.1, golden F29). `graph_facts` holds one current value per
(org, subject, field), so each domain's past is now published under a domain-qualified field,
`derived.history.<fact>@<domain>`, on the anchor. The four declared paths stay the whole family
(`packs/substrate_demand.HISTORY_FIELDS`), and every open history row a sweep did not publish — the
old per-anchor rows among them — is closed, never deleted.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.analytic.publish import publish_derived_fact
from genios_engine.context.correlation import correlate_event
from genios_engine.context.correlation_history import (NO_PRIOR, UNKNOWN_OUTCOME, VERSION_PREFIX,
                                                       history_field, publish_histories)
from genios_engine.context.workstreams import files_for
from genios_engine.packs.substrate_demand import HISTORY_FIELDS

from .workstream_world import T0, ledger, later, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s10_history", "org_s10_history_other"
KESTREL, SURVIVOR = "node_s10_kestrel", "node_s10_survivor"
NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
TIMES, GAP, OUTCOME, VERDICT = HISTORY_FIELDS


@pytest.fixture
def store(pg_store):
    for org in (ORG, OTHER):
        tenant(pg_store, org)
    yield pg_store
    for org in (ORG, OTHER):
        reset(pg_store, org)


def _generation(store, anchor: str, domain: str, generation: int, *, first_days_ago: int,
                last_days_ago: int, org: str = ORG) -> None:
    with store.engine.begin() as c:
        c.execute(text(
            "insert into context_correlations (correlation_id, org_id, anchor_node_id, anchor_type,"
            " domain, generation, first_event_at, last_event_at) "
            "values (:id, :o, :n, 'company', :d, :g, :f, :l)"),
            {"id": f"corr_{org}_{anchor}_{domain}_{generation}", "o": org, "n": anchor,
             "d": domain, "g": generation, "f": NOW - timedelta(days=first_days_ago),
             "l": NOW - timedelta(days=last_days_ago)})


def _two_domains(store, anchor: str = KESTREL, org: str = ORG) -> None:
    """Kestrel's third time in fundraising — 85 days after the second ended — and its first in
    admin. The old writer published both onto the anchor's one row per fact, in sorted order, so
    it kept fundraising's past (sorted last) and lost admin's."""
    for generation, (first, last) in enumerate(((200, 190), (100, 90), (5, 0)), start=1):
        _generation(store, anchor, "fundraising", generation, first_days_ago=first,
                    last_days_ago=last, org=org)
    _generation(store, anchor, "admin", 1, first_days_ago=9, last_days_ago=0, org=org)


def _publish(store, org: str = ORG, at: datetime = NOW) -> int:
    with store.engine.begin() as c:
        return publish_histories(c, org, eval_time=at)


def _loaded(value):
    """A `jsonb` value as the driver hands it: decoded already, or its text."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _current(store, org: str = ORG) -> dict[tuple[str, str], object]:
    """Every open history fact, `(subject, field) → value`."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select subject_node_id, field, value from graph_facts "
            " where org_id = :o and field like 'derived.history.%' and valid_to is null "
            " order by subject_node_id, field"), {"o": org}).fetchall()
    return {(r.subject_node_id, r.field): _loaded(r.value) for r in rows}


def _of(current: dict, anchor: str) -> dict[str, object]:
    return {field: value for (subject, field), value in current.items() if subject == anchor}


def test_a_file_in_two_domains_keeps_both_pasts(store):
    _two_domains(store)
    _publish(store)
    assert _of(_current(store), KESTREL) == {
        history_field(TIMES, "fundraising"): 3, history_field(GAP, "fundraising"): 85,
        history_field(OUTCOME, "fundraising"): UNKNOWN_OUTCOME,
        history_field(VERDICT, "fundraising"): UNKNOWN_OUTCOME,
        history_field(TIMES, "admin"): 1, history_field(OUTCOME, "admin"): NO_PRIOR,
        history_field(VERDICT, "admin"): NO_PRIOR}


def test_a_first_visit_has_no_gap_rather_than_a_gap_of_zero(store):
    _two_domains(store)
    _publish(store)
    assert (KESTREL, history_field(GAP, "admin")) not in _current(store)


def test_the_name_is_the_declared_path_and_the_domain_it_was_measured_in(store):
    """The family is exactly the four the vocabulary declares — both directions — and each name
    says which domain's past it is."""
    assert history_field(TIMES, "admin") == "derived.history.times_seen@admin"
    _two_domains(store)
    _publish(store)
    fundraising = {field.partition("@")[0] for field in _of(_current(store), KESTREL)
                   if field.endswith("@fundraising")}
    assert fundraising == set(HISTORY_FIELDS)


def test_every_field_holds_one_current_value(store):
    _two_domains(store)
    _two_domains(store, anchor=SURVIVOR)
    _publish(store)
    with store.engine.connect() as c:
        doubled = c.execute(text(
            "select subject_node_id, field, count(*) from graph_facts "
            " where org_id = :o and left(fact_version_id, :pl) = :p and valid_to is null "
            " group by subject_node_id, field having count(*) > 1"),
            {"o": ORG, "pl": len(VERSION_PREFIX), "p": VERSION_PREFIX}).fetchall()
    assert doubled == [] and len(_current(store)) == 14


def test_a_sweep_that_agrees_writes_nothing_and_closes_nothing(store):
    _two_domains(store)
    assert _publish(store) == 7
    before = _current(store)
    assert _publish(store, at=NOW + timedelta(days=8)) == 0
    assert _current(store) == before


def test_the_old_per_anchor_rows_are_closed_never_deleted(store):
    """What the old writer left: ONE row per anchor holding whichever domain sorted last. Read by
    anyone, it says fundraising's third time is Kestrel's only past. The first sweep closes it."""
    _two_domains(store)
    with store.engine.begin() as c:
        old = publish_derived_fact(
            c, org_id=ORG, subject_node_id=KESTREL, field=TIMES, value=3,
            eval_time=NOW - timedelta(days=14), value_type="count", visibility_scope="org",
            version_prefix=VERSION_PREFIX).version_id
    assert _publish(store) == 7 + 1
    assert (KESTREL, TIMES) not in _current(store)
    with store.engine.connect() as c:
        row = c.execute(text("select valid_to, status from graph_facts "
                             " where org_id = :o and fact_version_id = :v"),
                        {"o": ORG, "v": old}).one()
    assert (row.valid_to, row.status) == (NOW, "superseded")


def test_a_past_the_chain_no_longer_holds_is_closed(store):
    """A merge repoints admin's chain to the surviving node: Kestrel no longer has an admin past,
    and the survivor does."""
    _two_domains(store)
    _publish(store)
    with store.engine.begin() as c:
        c.execute(text("update context_correlations set anchor_node_id = :s "
                       " where org_id = :o and anchor_node_id = :n and domain = 'admin'"),
                  {"s": SURVIVOR, "o": ORG, "n": KESTREL})
    assert _publish(store, at=NOW + timedelta(days=8)) == 3 + 3
    current = _current(store)
    assert not any(field.endswith("@admin") for field in _of(current, KESTREL))
    assert _of(current, SURVIVOR) == {history_field(TIMES, "admin"): 1,
                                      history_field(OUTCOME, "admin"): NO_PRIOR,
                                      history_field(VERDICT, "admin"): NO_PRIOR}
    assert len(_of(current, KESTREL)) == 4


def test_another_writers_facts_on_the_anchor_are_never_closed(store):
    """The close is this module's own: a timeline fact another writer derived on Kestrel stays."""
    _two_domains(store)
    with store.engine.begin() as c:
        theirs = publish_derived_fact(
            c, org_id=ORG, subject_node_id=KESTREL, field="derived.timeline.dormant_condition",
            value={"open": []}, eval_time=NOW, value_type="json", visibility_scope="org",
            version_prefix="fv_tl:").version_id
    _publish(store)
    with store.engine.connect() as c:
        assert c.execute(text("select valid_to from graph_facts where org_id = :o "
                              "   and fact_version_id = :v"), {"o": ORG, "v": theirs}).scalar() \
            is None


def test_another_tenants_history_is_never_closed(store):
    _two_domains(store, org=OTHER)
    _publish(store, org=OTHER)
    theirs = _current(store, OTHER)
    _two_domains(store)
    _publish(store)
    assert _current(store, OTHER) == theirs and len(theirs) == 7


def test_the_founders_file_keeps_both_its_pasts(store):
    """The file the founder reads: Northwind wrote once (no domain hint — `general`), and a sales
    thread came twice, 200 days apart. One file, two domains, two pasts on its anchor."""
    process(store, ORG, event_id="evt_priya", sender="priya@northwind.test", thread="t_priya",
            at=T0)
    northwind = node(store, ORG, "northwind.test").node_id
    for event_id, days in (("evt_sales_1", 8), ("evt_sales_2", 208)):
        ledger(store, ORG, event_id=event_id, sender="priya@northwind.test", thread=None,
               at=later(days))
        with store.engine.begin() as c:
            correlate_event(c, org_id=ORG, event_id=event_id, occurred_at=later(days),
                            thread_id=None, node_types={northwind: "company"},
                            domain_hints=[{"domain": "sales", "source": "test"}])
    with store.engine.connect() as c:
        [file] = [f for f in files_for(c, ORG, now=later(210)).files
                  if f.counterparty_key == "northwind.test"]
    assert file.domains == ("general", "sales")
    _publish(store, at=later(210))
    past = _of(_current(store), file.file_id)
    assert (past[history_field(TIMES, "general")], past[history_field(TIMES, "sales")],
            past[history_field(GAP, "sales")]) == (1, 2, 200)

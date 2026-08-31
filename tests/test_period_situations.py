"""The aggregate reads, which no anchor could carry.

Twenty-three authored capabilities across all three domains ask about a WINDOW rather than a
subject — coverage, backlog, turnaround, team health. Every one was unreachable, and not because
nobody wrote a situation: `context_situations` anchors on a graph node, and no node's facts are
"the whole queue this month". Three corpus files named the missing mechanism in identical words so
it would read as one build rather than three coincidences.

`context/periodic.py` mints a tenant node, writes the window's aggregates onto it as ordinary
facts, and opens one situation per domain anchored there — so `_load_context`, `_neighborhood`,
`build_context_slice` and the whole compile path work unchanged. These tests hold the two
properties that make that safe: it is idempotent inside a window, and the tenant node never
competes for a correlation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.domain_spec import spec_for
from genios_engine.context.periodic import (
    period_domains,
    WINDOW_DAYS,
    period_key,
    refresh_period_situations,
    tenant_key,
    tenant_node_id,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def _seed_org(store, org: str) -> None:
    with store.engine.begin() as c:
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            cols.append(r.column_name); ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else "{}" if dt in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                       "on conflict (id) do nothing"), vals)


def test_a_sweep_opens_one_situation_per_domain_anchored_on_the_tenant(pg_store):
    org = "period_basic"
    _seed_org(pg_store, org)
    refresh_period_situations(pg_store, org, now=NOW)

    with pg_store.engine.connect() as c:
        rows = c.execute(text(
            "select domain, situation_type, anchor_node_id, status from context_situations "
            "where org_id=:o order by domain"), {"o": org}).all()
        tid = tenant_node_id(c, org)
    assert {r.domain for r in rows} == set(period_domains())
    assert tid and all(r.anchor_node_id == tid for r in rows)
    assert all(r.status == "active" for r in rows)
    # The type must be the one `domain_spec` names, not a string repeated here — a copy would let
    # the two drift and produce a type no situation file claims, which is the `admin_person` fault.
    for r in rows:
        assert r.situation_type == spec_for(r.domain).type_for("tenant")


def test_the_aggregates_land_on_the_tenant_node_as_ordinary_facts(pg_store):
    """The whole design rests on this: if the aggregates are ordinary facts on an ordinary node,
    every downstream reader — context loader, neighbourhood, slice builder, compiler — needs no
    change at all."""
    org = "period_facts"
    _seed_org(pg_store, org)
    refresh_period_situations(pg_store, org, now=NOW)

    with pg_store.engine.connect() as c:
        tid = tenant_node_id(c, org)
        node_type = c.execute(text(
            "select node_type from graph_nodes where org_id=:o and node_id=:n and valid_to is null"),
            {"o": org, "n": tid}).scalar()
        fields = {r[0] for r in c.execute(text(
            "select field from graph_facts where org_id=:o and subject_node_id=:n "
            "and valid_to is null"), {"o": org, "n": tid})}
    assert node_type == "tenant"
    assert "period.open_deals" in fields
    # Every count is paired with its previous-window twin, because one number is not a finding.
    # "Eleven open deals" tells a reader nothing; "eleven, against seven" tells them what changed.
    assert {"period.events_this_window", "period.events_prev_window"} <= fields


def test_running_twice_in_a_window_updates_rather_than_accumulates(pg_store):
    """The property that makes this safe to put on the sync path. `process_pending` drains in
    chunks and runs this every drain, so a sweep that fires six times in a week must produce one
    situation per domain and seven facts — not six times either."""
    org = "period_idempotent"
    _seed_org(pg_store, org)
    for offset in (0, 1, 2):
        refresh_period_situations(pg_store, org, now=NOW + timedelta(hours=offset))

    with pg_store.engine.connect() as c:
        sits = c.execute(text("select count(*) from context_situations where org_id=:o"),
                         {"o": org}).scalar()
        facts = c.execute(text(
            "select count(*) from graph_facts where org_id=:o and subject_node_id=:n "
            "and valid_to is null and field like 'period.%'"),
            {"o": org, "n": tenant_node_id(c, org)}).scalar()
        nodes = c.execute(text(
            "select count(*) from graph_nodes where org_id=:o and node_type='tenant'"),
            {"o": org}).scalar()
    assert sits == len(period_domains()), f"three sweeps produced {sits} situations"
    assert facts == 7, f"three sweeps produced {facts} period facts"
    assert nodes == 1


def test_a_new_window_is_a_new_situation_not_an_overwrite(pg_store):
    """The other half of idempotence, and the one that would be easy to get backwards. A period
    read is ABOUT its window; silently overwriting last month's with this month's would destroy the
    only comparison that makes an aggregate actionable."""
    org = "period_window"
    _seed_org(pg_store, org)
    refresh_period_situations(pg_store, org, now=NOW)
    later = NOW + timedelta(days=14)
    assert period_key(later) != period_key(NOW), "fixture dates must fall in different ISO weeks"
    refresh_period_situations(pg_store, org, now=later)

    with pg_store.engine.connect() as c:
        n = c.execute(text("select count(*) from context_situations where org_id=:o"),
                      {"o": org}).scalar()
    assert n == 2 * len(period_domains())


def test_the_tenant_node_never_wins_a_correlation(pg_store):
    """The guard that keeps this from swallowing the product.

    `choose_anchors` returns only the strongest tier present, by design. A tenant node inside
    `ANCHOR_PRIORITY` would outrank person and company on every event in the org, fusing every
    unrelated conversation into one situation — the same failure the connector-exclusion rule
    exists to prevent, at maximum scale.
    """
    from genios_engine.context.correlation import ANCHOR_PRIORITY, choose_anchors

    assert "tenant" not in ANCHOR_PRIORITY
    anchors = choose_anchors(
        node_types={"node_tenant_x": "tenant", "node_person": "person"},
        domain="general")
    assert [a.node_type for a in anchors] == ["person"]


def test_the_aggregates_carry_no_target_and_no_verdict(pg_store):
    """A count is a fact; whether it is good is a judgement that needs a target nobody has stated.
    Inventing one would put a fabricated benchmark under every forecast this feeds, and the corpus
    files explicitly ask for the movement rather than a grade."""
    org = "period_no_verdict"
    _seed_org(pg_store, org)
    refresh_period_situations(pg_store, org, now=NOW)

    with pg_store.engine.connect() as c:
        fields = {r[0] for r in c.execute(text(
            "select field from graph_facts where org_id=:o and subject_node_id=:n "
            "and valid_to is null"), {"o": org, "n": tenant_node_id(c, org)})}
        missing = c.execute(text(
            "select missing from context_situations where org_id=:o limit 1"), {"o": org}).scalar()
    assert not any(w in f for f in fields for w in ("target", "score", "health", "grade", "rating"))
    # The absent inputs are declared on every situation rather than estimated.
    assert "targets" in (missing if isinstance(missing, list) else [])


def test_the_sync_path_refreshes_them():
    """A period read only refreshed by a separate schedule is a period read that is always stale,
    and 23 capabilities would be reachable in principle and empty in practice."""
    import inspect

    from genios_engine.context import runner
    source = inspect.getsource(runner.process_pending)
    assert "refresh_period_situations" in source, (
        "process_pending does not refresh the period situations")


def test_every_period_domain_declares_a_tenant_anchor():
    """Without the `domain_spec` entry, `type_for` falls to its generic `<domain>_tenant` default —
    a type no situation file claims and the registry cannot resolve. That is the exact fault that
    kept `admin_person` and `fundraising_deal` dark, and it fails silently."""
    for domain in period_domains():
        stype = spec_for(domain).type_for("tenant")
        assert stype and not stype.endswith("_tenant"), (
            f"{domain} has no tenant anchor; type_for fell to the generic default: {stype}")


def test_the_window_is_four_weeks_so_periods_are_comparable():
    """Calendar months are 28, 30 or 31 days and a count over one is not comparable with a count
    over another — which makes the movement, the only actionable part, an artefact of the calendar."""
    assert WINDOW_DAYS == 28

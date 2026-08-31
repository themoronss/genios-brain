"""The deal lane worked after a backfill and went to zero on the next sync.

WHAT WAS BROKEN

Two things write `deal.status` and only one of them normalised it.

  * `pipeline.py` extracts it from correspondence and collapses the model's free text onto the
    controlled `open | won | lost` via `_normalise_deal_status`, keeping the model's own word as
    `deal.stage`. Authority rank 2.
  * `derived.py::compute_deal_view` rolls thread-level observations up to the deal and wrote its
    OWN vocabulary — `new`, `engaged`, `evaluating`, `proposing` — straight into `deal.status`.
    Authority rank 100.

Rank 100 outranks rank 2, so every sync overwrote the canonical value the extraction path had
just produced. Six `sales_v1` rules and all three Sales `deal` situations gate on the literal
`open`, so the lane routed immediately after a backfill and un-routed on the next sync — on the
design partner's org, 20 of 20 deal situations `no_route_predicate`, with `deal.status` reading
`engaged` (23), `evaluating` and `new`.

These tests are behavioural against a real Postgres because every unit here was correct: the
normaliser worked, the roll-up worked, and the joint between them did not.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.derived import compute_deal_view
from genios_engine.context.pipeline import _normalise_deal_status

NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)

#: Every stage word the roll-up can produce, and the status a reader must see for it.
#: `lost` is the only terminal one; everything else describes a deal that is still open.
STAGE_TO_STATUS = {
    "new": "open", "engaged": "open", "evaluating": "open", "proposing": "open", "lost": "lost",
}


def test_every_stage_word_the_rollup_emits_normalises(): 
    """Pure check on the seam, so a new stage word cannot be added without a status for it.

    `_STAGE_RANK` in derived.py is the list of words the roll-up can emit. Each has to survive
    `_normalise_deal_status` into something the rules actually compare against."""
    from genios_engine.context.derived import _STAGE_RANK

    assert set(_STAGE_RANK) == set(STAGE_TO_STATUS), (
        "derived.py grew a stage word with no status mapping asserted here")
    for stage, expected in STAGE_TO_STATUS.items():
        status, raw = _normalise_deal_status(stage)
        assert status == expected, f"{stage!r} -> {status!r}, expected {expected!r}"
        assert raw == stage, "the model's own word must survive as the stage"


def test_the_rollup_uses_the_shared_normaliser_not_its_own_words():
    """Pinned at the source, because the failure was a second vocabulary rather than a bad one."""
    import inspect

    from genios_engine.context import derived

    src = inspect.getsource(derived.compute_deal_view)
    assert "_normalise_deal_status(stage)" in src, (
        "compute_deal_view writes deal.status without the shared normaliser again")


def _seed_org(store, org: str) -> None:
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        parts, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            parts.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else "o@x.test" if "email" in r.column_name else org)
        conn.execute(text(f"insert into orgs ({','.join(parts)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


def _seed_event(conn, org: str, event_id: str) -> None:
    """A minimal emitted `source_events` row. `graph_source_refs.event_id` is NOT NULL, so every
    edge and fact written through the store needs one to point at. Columns are discovered rather
    than listed so the next migration does not break a test about something else."""
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns "
        "where table_name='source_events' and is_nullable='NO' and column_default is null")).all()
    vals = {"event_id": event_id, "org_id": org, "source": "gmail", "object_type": "email",
            "outcome": "emitted", "occurred_at": NOW, "domain_hints": json.dumps([{"domain": "sales"}])}
    for r in reqd:
        if r.column_name in vals:
            continue
        vals[r.column_name] = (NOW if ("time" in r.data_type or "date" in r.data_type)
                               else 0 if ("int" in r.data_type or "numeric" in r.data_type)
                               else "{}" if "json" in r.data_type
                               else f"{r.column_name}_{event_id}")
    cols = ",".join(vals)
    conn.execute(text(f"insert into source_events ({cols}) "
                      f"values ({','.join(':' + c for c in vals)}) on conflict do nothing"), vals)


def _seed_relationship(store, org: str, obs_kind: str) -> str:
    """A company with a person under it carrying one stage-bearing observation.

    This is the shape `compute_deal_view` rolls up: it walks company -> person edges and reads the
    observations on the far end, which is why the observation goes on the PERSON.
    """
    ev = f"evt_{org}"
    with store.engine.begin() as conn:
        _seed_event(conn, org, ev)
        company = store.find_or_create_node(conn, org_id=org, node_type="company",
                                            canonical_key="acme.test",
                                            display_name="Acme", event_id=ev)
        person = store.find_or_create_node(conn, org_id=org, node_type="person",
                                           canonical_key="p@acme.test",
                                           display_name="P", event_id=ev)
        store.write_edge(conn, org_id=org, edge_type="works_at", from_node_id=company,
                         to_node_id=person, confidence=0.9, occurred_at=NOW, event_id=ev,
                         evidence={}, source=None, authority_rank=2)
        conn.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "status, confidence, occurred_at) values (:i,:o,:n,:k,'active',0.9,:t) "
            "on conflict do nothing"),
            {"i": f"obs_{obs_kind}", "o": org, "n": person, "k": obs_kind, "t": NOW})
    return company


def _status_and_stage(store, org: str, node: str) -> tuple[str | None, str | None]:
    with store.engine.connect() as conn:
        rows = dict(conn.execute(text(
            "select field, value #>> '{}' from graph_facts where org_id=:o and subject_node_id=:n "
            "and field in ('deal.status','deal.stage') and status='active' and valid_to is null"),
            {"o": org, "n": node}).all())
    return rows.get("deal.status"), rows.get("deal.stage")


@pytest.mark.parametrize("obs_kind,stage", [
    ("meeting_request", "engaged"),
    ("demo_requested", "evaluating"),
    ("introduction", "new"),
    ("proposal_sent", "proposing"),
])
def test_an_open_deal_stays_open_through_the_rollup(pg_store, obs_kind, stage):
    """The regression, per stage word. Before the fix each of these wrote its own word into
    `deal.status` and the Sales situations — which compare against the literal `open` — stopped
    matching on the very next sync."""
    org = f"deal_status_{stage}"
    _seed_org(pg_store, org)
    node = _seed_relationship(pg_store, org, obs_kind)

    compute_deal_view(pg_store, org, now=NOW)

    status, kept_stage = _status_and_stage(pg_store, org, node)
    assert status == "open", (
        f"{obs_kind!r} rolled up to deal.status={status!r}; every Sales deal situation and six "
        "sales_v1 rules gate on the literal 'open', so this un-routes the whole deal lane")
    assert kept_stage == stage, (
        "the roll-up's own word must survive as deal.stage — collapsing it to 'open' and "
        "discarding the detail trades one dead field for a duller one")


def test_a_lost_deal_is_still_lost(pg_store):
    """The normaliser must not turn everything into `open`. `closed_lost_mention` is the one
    observation that genuinely terminates the deal, and a rule that saw it as open would keep
    recommending action on a dead relationship."""
    org = "deal_status_lost"
    _seed_org(pg_store, org)
    node = _seed_relationship(pg_store, org, "closed_lost_mention")

    compute_deal_view(pg_store, org, now=NOW)

    status, kept_stage = _status_and_stage(pg_store, org, node)
    assert status == "lost"
    # `lost` is already canonical, so there is no distinct stage word to preserve.
    assert kept_stage is None


def test_the_rollup_does_not_undo_the_extraction_path(pg_store):
    """The actual failure mode, end to end: extraction writes the canonical value at rank 2 and
    the roll-up writes at rank 100, so the roll-up always wins. That is fine — as long as what it
    writes is also canonical. This is the test that would have caught the original bug."""
    org = "deal_status_precedence"
    _seed_org(pg_store, org)
    node = _seed_relationship(pg_store, org, "meeting_request")

    # what the extraction path produces for this deal, at its own authority rank
    with pg_store.engine.begin() as conn:
        pg_store.write_fact(conn, org_id=org, subject_node_id=node, field="deal.status",
                            value="open", value_type="string", confidence=0.8, relevance=0.8,
                            occurred_at=NOW, event_id=f"evt_{org}", evidence={}, source=None,
                            authority_rank=2)

    compute_deal_view(pg_store, org, now=NOW)

    status, _ = _status_and_stage(pg_store, org, node)
    assert status == "open", (
        "the rank-100 roll-up overwrote the extraction path's canonical value with a stage word")

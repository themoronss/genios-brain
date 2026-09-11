"""The refresh uses contributing event time; unavailable refinements preserve old scores."""
from contextlib import nullcontext
from types import SimpleNamespace

from sqlalchemy import text

from .test_derived_provenance import provenance_db
from .test_support_derived_provenance import NOW, _fact_schema
from .test_situation_evidence_neighborhood import neighborhood_db
from genios_engine.context import outreach_situations as outreach


def test_seven_campaign_messages_refresh_at_65_evidence_and_50_freshness(provenance_db, monkeypatch):
    c = provenance_db
    _fact_schema(c)
    c.execute(text("update source_events set source='gmail',occurred_at='2026-08-11T12:00:00+00:00' where org_id='o'"))
    for i in range(3, 8):
        c.execute(text("insert into source_events values ('o',:e,'gmail',:e,'2026-08-11T12:00:00+00:00')"), {"e": f"e{i}"})
    finding = outreach._Finding(anchor="campaign", canonical_key="campaign:seven", display_name="Campaign",
        correlation_id="campaign:seven", concerns_node="representative", facts=[("campaign.contacted", 7, "number")],
        missing=[], inputs={}, event_ids=tuple(f"e{i}" for i in range(1, 8)))
    store = SimpleNamespace(engine=SimpleNamespace(begin=lambda: nullcontext(c)),
        find_or_create_node=lambda *a, **kw: "anchor", write_edge=lambda *a, **kw: None)
    captured = []
    monkeypatch.setattr(outreach, "_gather", lambda *a, **kw: ({}, {}, {}))
    monkeypatch.setattr(outreach, "READINGS", (("campaign", lambda *a: [finding]),))
    monkeypatch.setattr(outreach, "domains_declaring", lambda _: ("admin",))
    monkeypatch.setattr(outreach, "_reconcile", lambda *a, **kw: 0)
    monkeypatch.setattr(outreach, "_upsert", lambda *a, **kw: captured.append(kw))
    outreach.refresh_state_situations(store, "o", now=NOW)
    assert len(captured) == 1
    assert (captured[0]["evidence"], captured[0]["freshness"]) == (65, 50)
    assert captured[0]["last_seen"].isoformat() == "2026-08-11T12:00:00+00:00"


def test_a_new_anchor_uses_its_neighbours_and_not_the_representatives_second_hop(neighborhood_db):
    c = neighborhood_db
    finding = outreach._Finding(concerns_node="p1", inputs={})
    stats = outreach._refined_stats(c, org_id="o", node_id="anchor", finding=finding,
        now=NOW, fallback=SimpleNamespace(events=999), group_receipts=None)
    assert (stats.events, stats.sources) == (6, 1)
    assert stats.last_at.isoformat() == "2026-08-11T12:00:00+00:00"


def test_a_failed_new_read_preserves_the_exact_previous_stats_object(provenance_db):
    original = SimpleNamespace(events=3, sources=1, last_at=NOW)
    actual = outreach._refined_stats(provenance_db, org_id="o", node_id="anchor",
        finding=outreach._Finding(inputs={}), now=NOW, fallback=original, group_receipts=None)
    assert actual is original
    assert provenance_db.execute(text("select 1")).scalar() == 1

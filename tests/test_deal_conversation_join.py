"""THE CROSS-TOOL JOIN — a deal's clock comes from the buyer's email, not the CRM.

The defect: `deal.last_inbound` drives stalled_deal (the corpus's highest-scoring rule),
timeline_slip and champion_quiet — and no writer for that field existed anywhere. HubSpot
writes deal.stage/amount/close_date; L2 writes thread.last_inbound on the PERSON node.
Both halves sat in the same graph, connected by a real edge, and nothing joined them, so
"this deal went quiet" could never fire no matter how the scoring was tuned.

These tests lock the join AND its limits: it must not out-rank a system of record, must
not invent a clock from undated facts, and must be order-independent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.reason.signals_derived import NEIGHBOR_DERIVED_PATHS, deal_activity_facts
from genios_engine.packs.sales_v1 import SALES_V1

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=12)
RECENT = NOW - timedelta(days=2)

# fact_idx record shape from runner._neighbor_index: (value, occurred_at, rank, confidence)
DEAL = "deal_1"


def _graph(*people):
    """people = (node_id, node_type, last_inbound_ts | None)"""
    adj = {DEAL: {p[0] for p in people}}
    node_types = {DEAL: "deal"}
    fact_idx: dict = {}
    for nid, ntype, ts in people:
        adj.setdefault(nid, set()).add(DEAL)
        node_types[nid] = ntype
        if ts is not None:
            fact_idx[nid] = {"thread.last_inbound": (ts.isoformat(), ts, 2, 0.85)}
    return adj, node_types, fact_idx


def test_deal_inherits_the_most_recent_buyer_reply():
    """Two contacts on one deal: the deal is as alive as its MOST recent conversation."""
    adj, nt, fi = _graph(("p_quiet", "person", OLD), ("p_active", "person", RECENT))
    out = deal_activity_facts(DEAL, adj, nt, fi)
    assert out["deal.last_inbound"]["occurred_at"] == RECENT
    assert out["deal.last_inbound"]["value"] == RECENT.isoformat()


def test_join_is_capped_at_rank_2_and_never_exceeds_its_source_confidence():
    """The timestamp is hard fact; 'this thread is about this deal' is an inference from
    an edge. It must never out-rank the CRM, and never claim more than the source did."""
    adj, nt, fi = _graph(("p1", "person", OLD))
    fi["p1"]["thread.last_inbound"] = (OLD.isoformat(), OLD, 4, 0.40)   # low-conf source
    fact = deal_activity_facts(DEAL, adj, nt, fi)["deal.last_inbound"]
    assert fact["authority_rank"] == 2, "a graph inference cannot claim system-of-record rank"
    assert fact["confidence"] <= 0.40, "the join cannot manufacture confidence"


def test_non_conversant_neighbours_contribute_no_clock():
    """A company or competitor node hanging off the deal is structure, not a conversation."""
    adj, nt, fi = _graph(("c1", "company", RECENT), ("x1", "competitor", RECENT))
    assert deal_activity_facts(DEAL, adj, nt, fi) == {}


def test_undated_inbound_is_not_a_clock():
    """An elapsed-time rule fed an undated fact would compute garbage urgency. Better to
    emit nothing than a fabricated timestamp."""
    adj, nt, fi = _graph(("p1", "person", None))
    fi["p1"] = {"thread.last_inbound": ("whenever", None, 2, 0.85)}
    assert deal_activity_facts(DEAL, adj, nt, fi) == {}


def test_isolated_deal_gets_nothing_rather_than_a_default():
    """A deal with no contacts (the CRM-island case) must stay silent — a defaulted clock
    would make every unconnected deal look stalled."""
    assert deal_activity_facts(DEAL, {}, {DEAL: "deal"}, {}) == {}


def test_equal_timestamps_resolve_deterministically():
    """Two contacts replying in the same instant must not depend on set iteration order."""
    adj, nt, fi = _graph(("p_b", "person", RECENT), ("p_a", "person", RECENT))
    first = deal_activity_facts(DEAL, adj, nt, fi)
    for _ in range(5):
        assert deal_activity_facts(DEAL, adj, nt, fi) == first


def test_every_neighbor_derived_path_is_actually_used_by_a_rule():
    """No stale entries: a path listed here forces the expensive neighbour index to be
    built. If no rule reads it, that cost buys nothing."""
    read = {r["urgency"].get("path") for r in SALES_V1["rules"]}
    read |= {c.get("path") for r in SALES_V1["rules"] for c in r.get("when", [])}
    unused = NEIGHBOR_DERIVED_PATHS - read
    assert not unused, f"NEIGHBOR_DERIVED_PATHS entries no rule reads: {sorted(unused)}"

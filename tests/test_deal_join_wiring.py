"""The WIRING half of the deal↔conversation join (see test_deal_conversation_join.py).

Split from the derivation tests on purpose: the derivation is a pure function and lands
independently, while this asserts the runner actually asks for the neighbour index. A
correct derivation that the runner never calls is still a silent product failure — that
is precisely the shape of the original bug, so it gets its own lock.
"""
from __future__ import annotations

from genios_engine.packs.general_v1 import GENERAL_V1
from genios_engine.packs.sales_v1 import SALES_V1
from genios_engine.reason.rules import rule_from_dict
from genios_engine.reason.runner import _rules_need_neighbors
from genios_engine.reason.signals_derived import NEIGHBOR_DERIVED_PATHS


def _rules_reading_derived_paths():
    for pack in (SALES_V1, GENERAL_V1):
        for r in pack["rules"]:
            paths = {r["urgency"].get("path")} | {c.get("path") for c in r.get("when", [])}
            if paths & NEIGHBOR_DERIVED_PATHS:
                yield pack["id"], r


def test_rules_clocking_off_a_derived_path_request_the_neighbour_index():
    """stalled_deal's `when` mentions no neighbour at all — the old edge_count/neighbor_fact
    detection could not see it. Without the index the derived fact is never computed and the
    rule silently never fires."""
    found = list(_rules_reading_derived_paths())
    assert found, "no rule reads a neighbour-derived path — has the join been orphaned?"
    for pack_id, rule_d in found:
        assert _rules_need_neighbors([rule_from_dict(rule_d)]), (
            f"{pack_id}/{rule_d['id']} reads a neighbour-derived path but the runner "
            f"would skip building the neighbour index")


def test_stalled_deal_specifically_is_covered():
    """Named explicitly: it is the highest-scoring rule in the corpus and the one the
    missing join killed."""
    ids = {r["id"] for _p, r in _rules_reading_derived_paths()}
    assert "stalled_deal" in ids

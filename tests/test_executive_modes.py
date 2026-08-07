"""The four modes — and preventive's arithmetic: warn INSIDE the window, never after
the flip (that's the reasoner's job) and never on rules whose static conditions fail."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.executive.modes import (WARN_FRACTION, mode_of_signal,
                                           preventive_findings)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)

STALLED = {"id": "stalled_deal",
           "when": [{"path": "deal.status", "op": "=", "value": "open"},
                    {"fn": "days_since", "path": "deal.last_inbound", "op": ">=", "value": 7}]}


def _facts(days_ago: float, status="open"):
    return {"deal.status": {"value": status},
            "deal.last_inbound": {"value": (NOW - timedelta(days=days_ago)).isoformat()}}


def test_mode_of_signal():
    assert mode_of_signal("prescriptive") == "proactive"
    assert mode_of_signal("predictive") == "predictive"
    assert mode_of_signal("prescriptive", triggered_by="query") == "reactive"


def test_warns_inside_the_window_with_exact_days_remaining():
    finds = preventive_findings([STALLED], {"n1": _facts(5.0)}, NOW)
    assert len(finds) == 1
    f = finds[0]
    assert f.rule_id == "stalled_deal" and f.days_remaining == 2.0
    assert WARN_FRACTION <= f.fraction < 1.0


def test_silent_before_the_window_and_after_the_flip():
    assert preventive_findings([STALLED], {"n1": _facts(2.0)}, NOW) == []   # too early
    assert preventive_findings([STALLED], {"n1": _facts(8.0)}, NOW) == []   # already fired — reasoner's job


def test_static_conditions_gate_the_warning():
    # a WON deal 6 days quiet is not "about to stall" — the deal is closed
    assert preventive_findings([STALLED], {"n1": _facts(6.0, status="won")}, NOW) == []


def test_has_obs_condition_and_fail_closed():
    rule = {"id": "objection_open",
            "when": [{"has_obs": "objection"},
                     {"fn": "days_since", "path": "thread.last_inbound", "op": ">=", "value": 1}]}
    facts = {"thread.last_inbound": {"value": (NOW - timedelta(hours=18)).isoformat()},
             "_obs_kinds": {"objection"}}
    assert len(preventive_findings([rule], {"n1": facts}, NOW)) == 1
    # unknown condition kinds fail CLOSED — a preventive false alarm costs trust too
    weird = {"id": "x", "when": [{"neighbor_has_obs": "competitor"},
                                 {"fn": "days_since", "path": "thread.last_inbound",
                                  "op": ">=", "value": 1}]}
    assert preventive_findings([weird], {"n1": facts}, NOW) == []


def test_deterministic_ordering():
    two = {"n1": _facts(5.0), "n2": _facts(6.5)}
    a = preventive_findings([STALLED], two, NOW)
    b = preventive_findings([STALLED], dict(reversed(list(two.items()))), NOW)
    assert [f.subject_node_id for f in a] == [f.subject_node_id for f in b] == ["n2", "n1"]

"""STEP-02 · the material fingerprint: what a decision depends on, with time taken out.

    pytest tests/reason/test_material_fingerprint.py -q

`reason/fingerprint.material_fingerprint` (tree `yc2_w27_s02/M20.C1.L-logic.V1.U03`), over a REAL
snapshot (`adapters/native.native_context_snapshot`) and a real manifest.

Two directions, both by mutation:

  * STABLE where only time and the writers' re-stamping moved — the evaluation instant 15 minutes
    on, `graph_version`, every fact's `occurred_at` and `fact_version_id` (and so every evidence
    id, and the evidence list's order), the capability's derived `version`. Those are exactly the
    leaves a probe of all 40 golden cases found moving on a sweep that brought nothing new;
  * CHANGED by everything the decision reads — a fact's value, a new observation, a clock crossing
    a rung (6 → 7 days waiting, a deadline coming inside 48 hours, an overdue crossing 48 hours), the
    capability's content, the pack config, the mode, the pack's revision, a human verdict.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (CapabilityManifest, ExecutionMode, Goal,
                                               PlayDefinition, ReasonerSpec)
from genios_engine.reason.adapters import native
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.fingerprint import MaterialInputs, material_fingerprint, verdict_key

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
FIELDS = ("thread.ball_in_court", "thread.last_inbound", "thread.days_waiting",
          "commitment.due_at", "response.overdue_hours")
CAP = CapabilityManifest(
    capability_id="test.wait", version="1.0.0", domain="test", root_entity_type="person",
    goal=Goal(goal_id="g", statement="Decide whether a reply is owed."),
    reasoners=(ReasonerSpec(reasoner_id="core.context", version="1.0.0"),),
    plays=(PlayDefinition(play_id="p", version="1.0.0", label="P", steps=("one",)),),
    required_fields=("thread.ball_in_court",), selection_fields=FIELDS[1:], policies=(),
    live_delivery_enabled=True)


def _record(value, *, source: str, fv: str, at: datetime) -> dict:
    return {"value": value, "source_ref_id": source, "fact_version_id": fv,
            "confidence_bp": 9_000, "authority_rank": 3, "occurred_at": at}


def _context(*, at: datetime = NOW, stamp: datetime | None = None, fv_suffix: str = "",
             obs: tuple = (), **values) -> NodeContext:
    """One person we may owe a reply: every fact re-stamped at `stamp` (the drain's instant)."""
    stamp = stamp or at
    base = {"thread.ball_in_court": "us",
            "thread.last_inbound": (NOW - timedelta(days=5, hours=2)).isoformat(),
            "thread.days_waiting": 6,
            "commitment.due_at": (NOW + timedelta(hours=60)).isoformat(),
            "response.overdue_hours": 10}
    base.update(values)
    return NodeContext(
        node_id="p1", node_type="person",
        facts={name: _record(value, source=f"src_{i}", fv=f"fv_{i}{fv_suffix}", at=stamp)
               for i, (name, value) in enumerate(base.items())},
        obs=list(obs), neighbor_facts={}, neighbor_obs=set(), edge_count=0, baselines={})


def _fp(context: NodeContext | None = None, *, at: datetime = NOW, graph_version: int = 1,
        cap: CapabilityManifest = CAP, config: str = "cfg_1",
        mode: ExecutionMode = ExecutionMode.LIVE, inputs: MaterialInputs = MaterialInputs()) -> str:
    snapshot = native.native_context_snapshot(
        org_id="org_fp", context=context or _context(at=at), capability=cap,
        evaluation_time=at, graph_version=graph_version)
    return material_fingerprint(cap, snapshot, config_snapshot_id=config, mode=mode, inputs=inputs)


BASE = None


def setup_module():
    global BASE
    BASE = _fp()


# ── stable: only time and re-stamping moved ─────────────────────────────────────────────────────
def test_it_is_a_named_hash():
    assert BASE.startswith("fp_") and len(BASE) == 3 + 64 and _fp() == BASE


def test_fifteen_minutes_later_with_every_fact_re_stamped_is_the_same_fingerprint():
    later = NOW + timedelta(minutes=15)
    assert _fp(_context(at=later, stamp=later), at=later, graph_version=2) == BASE


def test_a_new_fact_version_with_the_same_value_is_the_same_fingerprint():
    assert _fp(_context(fv_suffix="_rewritten")) == BASE


def test_the_capabilitys_derived_version_is_not_its_content():
    assert _fp(cap=replace(CAP, version="exp.f906d8e5889b.6642ec0c3a6e")) == BASE


def test_a_clock_inside_its_rung_is_the_same_fingerprint():
    """3 → 4 days is one rung (≥3); 10 → 20 overdue hours is one rung (<48); 60 → 59 hours to a
    deadline is one rung (≥48)."""
    assert _fp(_context(**{"thread.days_waiting": 3})) == _fp(_context(**{"thread.days_waiting": 4}))
    assert _fp(_context(**{"response.overdue_hours": 20})) == BASE
    one_hour = NOW + timedelta(hours=1)
    assert _fp(_context(at=one_hour), at=one_hour) == BASE


# ── changed: everything the decision reads ──────────────────────────────────────────────────────
@pytest.mark.parametrize("field, value", [
    ("thread.ball_in_court", "them"),                                  # a fact's value
    ("thread.days_waiting", 7),                                        # 6 → 7 days crosses a rung
    ("response.overdue_hours", 50),                                    # past 48 hours overdue
    ("thread.last_inbound", (NOW - timedelta(days=7, hours=1)).isoformat()),   # 5 → 7 days ago
])
def test_a_material_change_to_a_fact_changes_the_fingerprint(field, value):
    assert _fp(_context(**{field: value})) != BASE


def test_a_deadline_coming_inside_48_hours_changes_the_fingerprint():
    """The same `due_at`, read thirteen hours later: 60 → 47 hours left, ≥48 → <48."""
    later = NOW + timedelta(hours=13)
    assert _fp(_context(at=later), at=later) != BASE


def test_a_new_observation_changes_the_fingerprint():
    obs = ({"kind": "email_received", "occurred_at": NOW - timedelta(minutes=5)},)
    assert _fp(_context(obs=obs)) != BASE


def test_the_capabilitys_content_changes_the_fingerprint():
    assert _fp(cap=replace(CAP, live_delivery_enabled=False)) != BASE
    assert _fp(cap=replace(CAP, goal=Goal(goal_id="g", statement="Decide something else."))) != BASE


@pytest.mark.parametrize("change", [
    {"config": "cfg_2"},
    {"mode": ExecutionMode.SHADOW},
    {"inputs": MaterialInputs(authority_revision=2)},
    {"inputs": MaterialInputs(verdicts=(verdict_key("fb_1", 1),))},
    {"inputs": MaterialInputs(decider="llm:claude-haiku-4-5-20251001")},
    {"inputs": MaterialInputs(decider="formula+r1")},
])
def test_what_sits_beside_the_request_changes_the_fingerprint(change):
    assert _fp(**change) != BASE


def test_a_new_version_of_one_verdict_changes_the_fingerprint():
    one = MaterialInputs(verdicts=(verdict_key("fb_1", 1),))
    two = MaterialInputs(verdicts=(verdict_key("fb_1", 2),))
    assert _fp(inputs=one) != _fp(inputs=two)


def test_a_snapshot_carrying_a_decimal_is_fingerprinted_not_refused():
    """⛔ Found by this file's own mutation check: hashing the finished payload with
    `semantic_hash` canonicalized it a second time and refused every tagged scalar — and real
    snapshots carry decimals (`$decimal` evidence on the golden cases). Stable, and still moved by
    the value."""
    from decimal import Decimal
    one = _fp(_context(**{"thread.ball_in_court": Decimal("0.5")}))
    later = NOW + timedelta(minutes=15)
    assert one == _fp(_context(at=later, **{"thread.ball_in_court": Decimal("0.5")}), at=later)
    assert one != _fp(_context(**{"thread.ball_in_court": Decimal("0.6")}))


def test_a_source_fact_ageing_across_a_rung_changes_the_fingerprint():
    """A source fact keeps the instant the world said it. Read a day and a half later, a fact said six
    days ago is seven and a half days old — across the 7-day rung. A derived fact re-stamped at every
    sweep's instant never ages, which is why the 15-minute test above holds."""
    said = NOW - timedelta(days=6)
    later = NOW + timedelta(days=1, hours=12)
    assert _fp(_context(stamp=said)) != _fp(_context(at=later, stamp=said), at=later)
    a_little_later = NOW + timedelta(hours=6)
    assert _fp(_context(stamp=said)) == _fp(_context(at=a_little_later, stamp=said),
                                            at=a_little_later)

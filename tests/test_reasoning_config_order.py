"""A capability must reason identically after a round trip through the audit store.

This pins a bug that was live in the shipped `sales.deal_cooling` capability and that the existing
replay tests could not see.

The failure was subtle and worth stating plainly. `ReasonerSpec.config` is a mapping, and a mapping
preserves the order it was written in. The audit store serialises the manifest with
`sort_keys=True`, and real PostgreSQL `jsonb` re-orders object keys again by its own rule
(length, then bytewise). So the config a replayed run receives is the *same data in a different
order*. Any unit that iterated it unsorted emitted its adjustments in a different order, which
changed `ReasonerResult.semantic_hash` — while `capability_snapshot_id` and `request_id` stayed
byte-identical, because those are computed from canonical, already-sorted bytes.

The result: `replay_persisted()` reported every persisted run as non-reproducible, with nothing
upstream signalling that anything had changed. The decision itself was never wrong — adjustments
are summed per component, so a permutation cannot move a score — but the mechanism that *proves*
determinism was quietly broken, which for an audit trail is nearly as bad.

Two things made it invisible. The existing replay tests rebuild the manifest with `canonicalize()`,
a pure Python transform that *preserves* key order, rather than `canonical_dumps()`, the JSON
serialiser the store actually uses. And only capabilities that author per-play config are exposed
at all. These tests use the real serialiser against the real shipped capability, and the first test
below guards against the fixture quietly losing the config that makes the rest meaningful.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import ContextSnapshot, ReasoningRequest
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.platform.canonical import canonical_dumps
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.replay import capability_from_manifest, compare_executions

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)

#: Config keys whose iteration order once reached a result hash. Named so a future author adding a
#: per-play config block can see immediately that ordering is load-bearing here.
ORDER_SENSITIVE_KEYS = ("play_adjustments", "play_risk_reduction_bp")


def _context() -> ContextSnapshot:
    """A cooling deal, in the fact shape the shipped capability actually declares."""
    return ContextSnapshot(
        org_id="org_1",
        graph_version=21,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="deal_cooling.selector.v1",
        facts={
            "deal.status": {"value": "open", "confidence_bp": 9_500, "src_count": 2},
            "deal.value": {"value": 500_000, "confidence_bp": 9_500, "src_count": 2},
            "derived.engagement": {"value_bp": 4_000, "confidence_bp": 8_500, "src_count": 2},
            "thread.last_inbound": {
                "value": (NOW - timedelta(days=10)).isoformat(),
                "confidence_bp": 9_000, "src_count": 2,
            },
            "relationship.verified_stakeholder_count": {"value": 2},
        },
        neighbor_facts={"deal.status": "open", "contact.verified_recipient": True},
        edge_count=2,
    )


def _request(capability) -> ReasoningRequest:
    return ReasoningRequest(
        org_id="org_1", capability=capability, context=_context(), evaluation_time=NOW,
        trigger_kind="email.received", trigger_ref="event_1", config_snapshot_id="cfg_1")


def _store_serialised(capability):
    """Exactly what the audit store does: canonical JSON out (sort_keys=True), manifest back in."""
    return capability_from_manifest(json.loads(canonical_dumps(capability.to_semantic_dict())))


def _keys_reordered(capability):
    """A store returning object keys in an order neither insertion nor alphabetical.

    Real PostgreSQL `jsonb` orders by (length, bytewise). Reversing is a cheap stand-in that
    reproduces the same class of divergence without depending on a database.
    """
    def flip(value):
        if isinstance(value, dict):
            return {key: flip(value[key]) for key in reversed(list(value))}
        if isinstance(value, list):
            return [flip(item) for item in value]
        return value

    return capability_from_manifest(
        flip(json.loads(canonical_dumps(capability.to_semantic_dict()))))


REBUILDS = pytest.mark.parametrize(
    "rebuild", [_store_serialised, _keys_reordered], ids=["store_serialised", "keys_reordered"])


def test_the_fixture_still_exercises_order_sensitive_config():
    """Guards the guard.

    Every test below is vacuous unless the capability authors per-play config. If deal_cooling ever
    stops doing so, this fails loudly rather than letting the suite go green on nothing.
    """
    authored = {
        spec.reasoner_id: [key for key in ORDER_SENSITIVE_KEYS if key in spec.config]
        for spec in DEAL_COOLING_V1.reasoners
    }
    exercised = {unit: keys for unit, keys in authored.items() if keys}

    assert exercised, f"no unit authors any of {ORDER_SENSITIVE_KEYS}"
    assert any(len(dict(spec.config.get(key, {}))) > 1
               for spec in DEAL_COOLING_V1.reasoners for key in ORDER_SENSITIVE_KEYS), \
        "a single-entry mapping cannot be reordered, so it cannot detect the regression"


@REBUILDS
def test_a_capability_reasons_identically_after_a_store_round_trip(rebuild):
    orchestrator = ReasoningOrchestrator(default_registry())
    live = orchestrator.execute(_request(DEAL_COOLING_V1))
    restored = orchestrator.execute(_request(rebuild(DEAL_COOLING_V1)))

    comparison = compare_executions(live, restored)

    assert comparison.matches, f"replay diverged: {comparison.differences}"


@REBUILDS
def test_every_unit_hashes_identically_after_a_round_trip(rebuild):
    """Per-unit, so a future regression names the unit that drifted, not just 'replay broke'."""
    orchestrator = ReasoningOrchestrator(default_registry())
    live = orchestrator.execute(_request(DEAL_COOLING_V1))
    restored = orchestrator.execute(_request(rebuild(DEAL_COOLING_V1)))

    drifted = [item.reasoner_id
               for item, other in zip(live.ordered_results, restored.ordered_results)
               if item.semantic_hash != other.semantic_hash]

    assert not drifted, f"result hash depends on config key order: {drifted}"


@REBUILDS
def test_adjustment_order_is_a_function_of_content_not_arrival_order(rebuild):
    """The precise mechanism, asserted directly so the next reader sees what broke."""
    orchestrator = ReasoningOrchestrator(default_registry())
    live = orchestrator.execute(_request(DEAL_COOLING_V1))
    restored = orchestrator.execute(_request(rebuild(DEAL_COOLING_V1)))

    def adjustments(execution):
        return {result.reasoner_id: tuple((item.play_id, item.component, item.delta_bp)
                                          for item in result.adjustments)
                for result in execution.ordered_results if result.adjustments}

    live_adjustments = adjustments(live)

    assert live_adjustments, "the run produced no adjustments, so this proves nothing"
    assert live_adjustments == adjustments(restored)


def test_the_identifiers_that_hid_the_bug_stay_stable():
    """Why this needed its own test file: the inputs look identical by every id the system checks.

    A reordered manifest has the same content address and the same request id, so no upstream
    guard fires. Only the per-unit result hash moves — which is exactly what replay compares.
    """
    restored = _keys_reordered(DEAL_COOLING_V1)

    assert restored.capability_snapshot_id == DEAL_COOLING_V1.capability_snapshot_id
    assert restored.semantic_hash == DEAL_COOLING_V1.semantic_hash
    assert _request(restored).request_id == _request(DEAL_COOLING_V1).request_id

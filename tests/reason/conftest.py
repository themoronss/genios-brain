"""Shared scaffolding for running a single reasoning unit in isolation.

A unit is a pure function of (capability spec, frozen snapshot, prior results). These helpers
build the smallest legal instance of each so a test can exercise one unit's arithmetic without
standing up an orchestrator — and, just as importantly, without a capability that quietly supplies
defaults the unit is supposed to demand for itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    EvidenceRef,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def spec(reasoner_id: str, *, dependencies: tuple[str, ...] = (), **config: Any) -> ReasonerSpec:
    """One unit's place in a test capability.

    `dependencies` matters more than it looks: the orchestrator hands a unit ONLY the results of
    the units it declared, so a reader that does not declare its source is handed an empty prior
    map and falls back to its default — silently, and identically to the source never running.
    """
    return ReasonerSpec(reasoner_id=reasoner_id, version="1.0.0",
                        dependencies=dependencies, config=config)


def context(facts: dict[str, Any] | None = None, *, evaluation_time: datetime = NOW,
            evidence: tuple[EvidenceRef, ...] = (), edge_count: int = 0) -> ContextSnapshot:
    return ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="node_1", root_entity_type="entity",
        evaluation_time=evaluation_time, selector_version="test.selector.v1",
        facts=facts or {}, evidence=evidence, edge_count=edge_count)


def capability(*specs: ReasonerSpec) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="test.capability", version="1.0.0", domain="test",
        root_entity_type="entity",
        goal=Goal(goal_id="test.goal", statement="Prove one unit in isolation."),
        reasoners=specs,
        plays=(PlayDefinition(play_id="do_the_thing", version="1.0.0",
                              label="Do the thing", steps=("step one",)),),
        # No policies and no preconditions: a policy would oblige the manifest to schedule
        # `core.constraint` as REQUIRED, and these tests are about ONE unit at a time.
        policies=(),
        live_delivery_enabled=False)


def request(*specs: ReasonerSpec, facts: dict[str, Any] | None = None,
            evaluation_time: datetime = NOW, evidence: tuple[EvidenceRef, ...] = (),
            edge_count: int = 0) -> ReasoningRequest:
    return ReasoningRequest(
        org_id="org_1", capability=capability(*specs),
        context=context(facts, evaluation_time=evaluation_time, evidence=evidence,
                        edge_count=edge_count),
        evaluation_time=evaluation_time, trigger_kind="test.trigger",
        config_snapshot_id="cfg_1")


def completed(reasoner_id: str, **metrics: int) -> ReasonerResult:
    """A prior unit that ran and published these metrics."""
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1.0.0",
                          status=ResultStatus.COMPLETED, metrics=metrics)


def run(unit, *, config: dict[str, Any] | None = None, facts: dict[str, Any] | None = None,
        prior: dict[str, ReasonerResult] | None = None, evaluation_time: datetime = NOW,
        evidence: tuple[EvidenceRef, ...] = ()):
    """Evaluate one unit through the real template method — never a plugin in isolation."""
    own = spec(unit.unit_id, **(config or {}))
    others = tuple(spec(reasoner_id) for reasoner_id in sorted(prior or {}))
    req = request(own, *others, facts=facts, evaluation_time=evaluation_time, evidence=evidence)
    return unit.evaluate(req, dict(prior or {}))


@pytest.fixture
def now() -> datetime:
    return NOW

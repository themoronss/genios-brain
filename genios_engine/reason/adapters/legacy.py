"""Execute a legacy rule through the deterministic Layer 4 authority boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.reasoning import (CapabilityManifest, ExecutionMode, ReasoningRequest,
                                               ResultStatus)
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.orchestrator import ReasoningExecution, ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.rules import Rule

from .legacy_context import legacy_context_snapshot
from .legacy_pack import legacy_capability_manifest

_DEFAULT_ORCHESTRATOR = ReasoningOrchestrator(default_registry())


@dataclass(frozen=True, slots=True)
class LegacyReasoningExecution:
    execution: ReasoningExecution

    @property
    def legacy_result(self):
        return self.execution.result_by_id["legacy.rule"]

    @property
    def matched(self) -> bool:
        result = self.legacy_result
        return result.status == ResultStatus.COMPLETED and result.matched is True

    @property
    def score(self) -> int:
        return int(self.legacy_result.metrics.get("legacy_score", 0))

    @property
    def score_inputs(self) -> dict[str, int]:
        metrics = self.legacy_result.metrics
        return {
            "U": int(metrics.get("urgency_bp", 0)) // 100,
            "I": int(metrics.get("impact_bp", 0)) // 100,
            "R": int(metrics.get("recency_bp", 0)) // 100,
            "C": int(metrics.get("confidence_bp", 0)) // 100,
            "terms_bp": int(metrics.get("legacy_terms_bp", 0)),
        }


def reason_legacy_rule(*, org_id: str, context: NodeContext, rule: Rule,
                       evaluation_time: datetime, scoring: dict[str, Any],
                       config_snapshot_id: str | None = None,
                       pack_id: str = "legacy", pack_version: str = "1",
                       play_config: dict[str, Any] | None = None,
                       mode: ExecutionMode = ExecutionMode.LIVE,
                       orchestrator: ReasoningOrchestrator | None = None,
                       graph_version: int = 0,
                       capability: CapabilityManifest | None = None
                       ) -> LegacyReasoningExecution:
    capability = capability or legacy_capability_manifest(
        rule=rule, scoring=scoring, pack_id=pack_id, pack_version=pack_version,
        play_config=play_config, config_snapshot_id=config_snapshot_id)
    snapshot = legacy_context_snapshot(
        org_id=org_id,
        context=context,
        rule=rule,
        evaluation_time=evaluation_time,
        graph_version=graph_version,
    )
    request = ReasoningRequest(
        org_id=org_id,
        capability=capability,
        context=snapshot,
        evaluation_time=evaluation_time,
        trigger_kind="legacy.rule_scan",
        trigger_ref=rule.id,
        mode=mode,
        config_snapshot_id=config_snapshot_id,
    )
    execution = (orchestrator or _DEFAULT_ORCHESTRATOR).execute(request)
    return LegacyReasoningExecution(execution)


__all__ = ["LegacyReasoningExecution", "reason_legacy_rule"]

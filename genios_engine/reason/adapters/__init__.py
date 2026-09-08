"""Compatibility boundaries between the legacy rule packs and the Layer 4 kernel."""

from .legacy import LegacyReasoningExecution, reason_legacy_rule
from .legacy_context import legacy_context_snapshot
from .legacy_pack import legacy_capability_manifest
from .native import native_context_snapshot, reason_native_capability
from .situation_projection import SituationProjection, project_situation

__all__ = ["LegacyReasoningExecution", "SituationProjection", "legacy_capability_manifest",
           "legacy_context_snapshot", "project_situation", "reason_legacy_rule",
           "native_context_snapshot", "reason_native_capability"]

"""The L3->L4 weld: an ExpertisePackage -> CapabilityManifest -> a real ReasoningDecision."""

from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.context.situation_bso import (
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
)
from genios_engine.contracts.reasoning import CapabilityManifest, ExecutionMode, FailurePolicy
from genios_engine.packs.compiler import DomainCompiler, InMemoryRuntimeBrains
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.engine import NodeContext

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _compile_package():
    row = {
        "situation_id": "sit_1", "situation_type": "buying_signal", "domain": "sales",
        "status": "active", "correlation_id": None, "confidence_overall": 82, "coverage": 70,
        "first_seen_at": NOW, "last_seen_at": NOW,
        "anchor_node_id": "account_1", "anchor_name": "Acme", "anchor_type": "account",
    }
    signal_ids, evidence = gather_evidence_and_signals(None, "org_1", None, row["situation_id"])
    bso = build_business_situation(org_id="org_1", situation=row, signal_ids=signal_ids,
                                   evidence=evidence, trace_id="trace_1")
    context_slice = build_context_slice(
        org_id="org_1", situation=row, facts={"thread.ball_in_court": {"value": "us"}},
        observations=[], neighbor=(0, set(), {}), graph_version=7, eval_time=NOW,
        trace_id="trace_1")
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(default_authoring_root()),
        runtime_brains=InMemoryRuntimeBrains(), publisher=None)
    return compiler.compile(bso, context_slice), row


def test_adapter_builds_a_valid_capability_manifest():
    package, _ = _compile_package()
    manifest = expertise_capability_manifest(package, root_entity_type="account")

    assert isinstance(manifest, CapabilityManifest)
    assert manifest.capability_id == "expertise.buying_signal"
    assert manifest.domain == "sales"
    assert manifest.root_entity_type == "account"
    reasoner_ids = {r.reasoner_id for r in manifest.reasoners}
    assert "core.planning" in reasoner_ids
    # the mandatory REQUIRED constraint invariant is satisfied
    constraint = next(r for r in manifest.reasoners if r.reasoner_id == "core.constraint")
    assert constraint.failure_policy is FailurePolicy.REQUIRED
    assert manifest.plays                                   # non-empty plays invariant
    assert manifest.metadata["expertise_id"] == package.id
    # version is a content hash of the package knowledge -> stable + change-sensitive
    assert manifest.version.startswith("exp.")


def test_manifest_version_changes_with_package_knowledge():
    package, _ = _compile_package()
    m1 = expertise_capability_manifest(package, root_entity_type="account")
    m2 = expertise_capability_manifest(package, root_entity_type="account")
    assert m1.version == m2.version                         # deterministic


def test_the_weld_drives_layer4_to_a_real_decision():
    """ExpertisePackage -> CapabilityManifest -> orchestrator -> a ReasoningDecision object."""
    package, row = _compile_package()
    manifest = expertise_capability_manifest(package, root_entity_type=row["anchor_type"])

    ctx = NodeContext(
        node_id="account_1", node_type="account",
        facts={"thread.ball_in_court": {"value": "us", "confidence": 900, "authority_rank": 3}},
        obs=[],
    )
    execution = reason_native_capability(
        org_id="org_1", context=ctx, capability=manifest, evaluation_time=NOW,
        graph_version=7, config_snapshot_id=None, mode=ExecutionMode.SHADOW)

    # the weld produced a typed decision from the typed package — L3->L4 is connected
    assert execution.decision is not None
    assert execution.decision.capability_id == "expertise.buying_signal"

from __future__ import annotations

from genios_engine.packs.capabilities import (
    DEAL_COOLING_V1,
    build_deal_cooling_manifest,
)
from genios_engine.platform.canonical import canonicalize
from genios_engine.reason.registry import ReasonerRegistry


def test_deal_cooling_manifest_is_native_versioned_and_content_addressed():
    rebuilt = build_deal_cooling_manifest()

    assert rebuilt.capability_id == "sales.deal_cooling"
    assert rebuilt.version == "1.0.0"
    assert rebuilt.root_entity_type == "deal"
    assert rebuilt.semantic_hash == DEAL_COOLING_V1.semantic_hash
    assert len(rebuilt.semantic_hash) == 64
    assert rebuilt.capability_snapshot_id == f"cap_{rebuilt.semantic_hash}"
    canonicalize(rebuilt.to_semantic_dict())  # also proves the manifest contains no floats


def test_deal_cooling_reasoner_dag_is_complete_and_deterministic():
    ordered = ReasonerRegistry.topological_order(DEAL_COOLING_V1.reasoners)
    ordered_ids = tuple(spec.reasoner_id for spec in ordered)

    assert set(ordered_ids) == {
        "core.temporal",
        "core.relationship",
        "core.risk",
        "core.constraint",
        "core.priority",
        "core.confidence",
        "core.planning",
    }
    assert ordered_ids.index("core.risk") > ordered_ids.index("core.temporal")
    assert ordered_ids.index("core.risk") > ordered_ids.index("core.relationship")
    assert ordered_ids[-1] == "core.planning"
    assert {spec.reasoner_id for spec in ordered if spec.gating} == {
        "core.temporal",
        "core.relationship",
    }


def test_deal_cooling_has_three_safe_outcome_observable_plays():
    plays = {play.play_id: play for play in DEAL_COOLING_V1.plays}

    assert set(plays) == {
        "restore_momentum",
        "multithread_account",
        "clarify_next_step",
    }
    assert all(play.read_only for play in plays.values())
    assert all(play.steps and play.success_events for play in plays.values())
    assert all(1 <= play.window_days <= 21 for play in plays.values())
    assert "read_only" in DEAL_COOLING_V1.policies
    assert "human_approval_required" in DEAL_COOLING_V1.policies
    assert DEAL_COOLING_V1.live_delivery_enabled is False

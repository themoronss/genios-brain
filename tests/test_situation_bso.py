"""The L2 situation -> typed BSO/slice producer, and that its output compiles on the real corpus."""

from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.context.situation_bso import (
    DEFAULT_IMPORTANCE_BP,
    SELECTOR_VERSION,
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
)
from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)
from genios_engine.packs.compiler import DomainCompiler, InMemoryRuntimeBrains
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _situation_row(**overrides) -> dict:
    row = {
        "situation_id": "sit_test_1",
        "situation_type": "buying_signal",
        "domain": "sales",
        "status": "active",
        "correlation_id": None,
        "confidence_overall": 82,          # int 0-100 (percent scale)
        "coverage": 70,
        "missing": None,
        "first_seen_at": NOW,
        "last_seen_at": NOW,
        "anchor_node_id": "account_1",
        "anchor_name": "Acme",
        "anchor_type": "account",
    }
    row.update(overrides)
    return row


def test_producer_builds_valid_typed_contracts():
    row = _situation_row()
    # correlation_id is None -> gather uses no connection and returns non-empty fallbacks
    signal_ids, evidence = gather_evidence_and_signals(None, "org_1", None, row["situation_id"])
    assert signal_ids == ["sig:sit_test_1"]
    assert evidence and evidence[0]["reconstructed"] is True

    bso = build_business_situation(
        org_id="org_1", situation=row, signal_ids=signal_ids, evidence=evidence,
        trace_id="trace_1")
    assert isinstance(bso, BusinessSituationObject)
    assert bso.type == "buying_signal"
    assert bso.confidence_bp == 8_200                      # 82 percent -> basis points
    assert bso.importance_bp == DEFAULT_IMPORTANCE_BP      # L2 carries none -> neutral default
    assert bso.metadata["importance_source"] == "default"
    assert bso.domain_hints == ("sales",)
    assert bso.entities[0]["id"] == "account_1"
    assert bso.signal_ids == ("sig:sit_test_1",)

    context_slice = build_context_slice(
        org_id="org_1", situation=row,
        facts={"thread.ball_in_court": {"value": "us"}},
        observations=[{"kind": "reply", "occurred_at": NOW}],
        neighbor=(3, {"competitor_mention"}, {"account.tier": "enterprise"}),
        graph_version=11, eval_time=NOW, trace_id="trace_1")
    assert isinstance(context_slice, SituationContextSlice)
    assert context_slice.root_entity_ids == ("account_1",)
    assert context_slice.selector_version == SELECTOR_VERSION
    assert context_slice.graph_version == 11
    assert context_slice.edge_count == 3
    assert context_slice.neighbor_observations == ("competitor_mention",)


def test_produced_objects_compile_against_the_real_corpus():
    """The whole point: producer output routes + compiles into a real ExpertisePackage."""
    row = _situation_row()
    signal_ids, evidence = gather_evidence_and_signals(None, "org_1", None, row["situation_id"])
    bso = build_business_situation(
        org_id="org_1", situation=row, signal_ids=signal_ids, evidence=evidence,
        trace_id="trace_1")
    context_slice = build_context_slice(
        org_id="org_1", situation=row,
        facts={"thread.ball_in_court": {"value": "us"}},
        observations=[], neighbor=(0, set(), {}),
        graph_version=7, eval_time=NOW, trace_id="trace_1")

    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(default_authoring_root()),
        runtime_brains=InMemoryRuntimeBrains(),
        publisher=None,                                    # shadow: no persistence
    )
    package = compiler.compile(bso, context_slice)

    assert package.situation_id == "sit_test_1"
    assert package.metadata["domain_ids"] == ("sales",)
    assert len(package.capabilities) >= 1
    # confidence is capped by the situation's own confidence, never inflated by runtime knowledge
    assert package.confidence_bp <= bso.confidence_bp


def test_lower_confidence_rescales_and_low_coverage_survives():
    row = _situation_row(confidence_overall=40, coverage=10)
    bso = build_business_situation(
        org_id="org_1", situation=row, signal_ids=["sig:sit_test_1"],
        evidence=[{"event_id": "sig:sit_test_1", "source": "situation", "reconstructed": True}],
        trace_id="trace_1")
    assert bso.confidence_bp == 4_000
    assert bso.metadata["coverage_bp"] == 1_000

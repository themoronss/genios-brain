"""The L2 situation -> typed BSO/slice producer, and that its output compiles on the real corpus."""

from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.context import document_register, periodic, support_situations
from genios_engine.context.domain_spec import domains_declaring, spec_for
from genios_engine.context.situation_bso import (
    DEFAULT_IMPORTANCE_BP,
    SELECTOR_VERSION,
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
)
from genios_engine.context.situations import SCORE_MAX
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
        # Sourced from the registry, never hand-written: `buying_signal` is a PACK signal
        # reason_code that `context/situations.py` cannot emit, so a fixture using it tested a
        # shape the compiler never receives — which is how a 100% live route-miss stayed
        # invisible to a green suite.
        "situation_type": spec_for("sales").type_for("company"),
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
        "anchor_type": "company",
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
    # Assert against the registry, not a literal: the producer's type must stay a value Layer 2
    # can emit, and pinning it to a hand-written string is exactly how it drifted before.
    assert bso.type == spec_for("sales").type_for("company")
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
        # The real corpus is entirely DRAFT today (nothing has cleared admission), which is a
        # true statement about the corpus, not a compiler defect. This test proves the produced
        # BSOs COMPILE — a measurement question — so it runs in measurement mode, exactly as
        # the live shadow pass does.
        require_admission=False,
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


# ── the cap, checked where it was actually defeated ───────────────────────────────────────────

def _bso_for(coverage: int) -> BusinessSituationObject:
    row = _situation_row(coverage=coverage, confidence_overall=coverage)
    return build_business_situation(
        org_id="org_1", situation=row, signal_ids=["sig:sit_test_1"],
        evidence=[{"event_id": "sig:sit_test_1", "source": "situation", "reconstructed": True}],
        trace_id="trace_1")


def test_an_inferred_readings_coverage_cannot_reach_a_recorded_situations_across_the_seam():
    """The one property the eight inferred support/records readings rest on, checked at the layer
    where it was actually broken rather than at the layer where it was written.

    Each of those readings caps its own coverage — a mailbox is not a helpdesk, a file store is
    not a records system — and the caps were correct in the writers. But they were expressed in
    BASIS POINTS while `context_situations` stores an int percent, and `situation_bso._bp` turns a
    stored score into basis points by multiplying by 100 and clamping at 10000. Measured before
    the fix: knowledge_gap's honest 2500 arrived at Layer 3 as coverage_bp=10000, escalation's
    3000 as 10000, first_response's and document's 4000 as 10000, and the period situations'
    5000 as 10000 — the SAME number a fully-covered recorded situation produces. Confidence
    saturated identically, so `expertise_builder`'s `min(situation.confidence_bp,
    expert.coverage_bp)` had nothing left to cap.

    This fails if any cap goes back to basis points, because the clamp then lands it exactly on
    the recorded ceiling.
    """
    recorded = _bso_for(SCORE_MAX).metadata["coverage_bp"]
    assert recorded == 10_000, "a fully-covered recorded situation is the ceiling being defended"

    caps = {name: value for name, value in vars(support_situations).items()
            if name.startswith("_CAP_")}
    assert len(caps) == len(support_situations.READINGS) == 7, sorted(caps)
    caps["document_register.COVERAGE_CAP_PCT"] = document_register.COVERAGE_CAP_PCT
    caps["periodic.PERIOD_COVERAGE_PCT"] = periodic.PERIOD_COVERAGE_PCT

    for name, cap in caps.items():
        bso = _bso_for(cap)
        assert bso.metadata["coverage_bp"] == cap * 100, name
        assert bso.metadata["coverage_bp"] < recorded, (
            f"{name}={cap} reaches a recorded situation's coverage across the L2->L3 seam; "
            f"the cap is stored as a percent (0..{SCORE_MAX}), not basis points")


def test_a_capped_reading_stays_capped_even_when_every_expected_field_is_present():
    """The end-to-end of the same property: the cap is a ceiling on the READING, not a penalty for
    a thin row. Hand a support reading every field its registry entry expects — the best case any
    mailbox can produce — and the number it stores is still the cap, and the number that crosses
    the seam is still below a recorded situation's."""
    recorded = _bso_for(SCORE_MAX).metadata["coverage_bp"]
    checked = 0
    for anchor, _reader in support_situations.READINGS:
        for domain in domains_declaring(anchor):
            stype = spec_for(domain).type_for(anchor)
            expected = set(spec_for(domain).fields_for(stype))
            cap = max(v for n, v in vars(support_situations).items() if n.startswith("_CAP_"))
            coverage, _gaps = support_situations._coverage(domain, stype, expected, cap)
            assert coverage == cap, (domain, stype)
            assert _bso_for(coverage).metadata["coverage_bp"] < recorded, (domain, stype)
            checked += 1
    assert checked, "no domain declares any support reading — the assertions above ran on nothing"

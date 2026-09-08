from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.context.qes_adapter import adapt_qes_extraction
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (
    Commitment,
    DecisionState,
    EntityMention,
    ExtractionResult,
)
from genios_engine.contracts.units import DateCertainty, ResolvedDate


NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)
QUOTE = "Acme will send the renewal by Friday."
SPAN = EvidenceSpan(source_ref="prepared_content:evt_1", quote=QUOTE,
                    start_offset=0, end_offset=len(QUOTE), verified=True)


def extraction() -> ExtractionResult:
    due = ResolvedDate(as_written="Friday", earliest=NOW, latest=NOW,
                       certainty=DateCertainty.EXACT, resolved_against=NOW, evidence=[SPAN])
    return ExtractionResult(
        intent="commit", stance="cautious", topics=["renewal"],
        entity_mentions=[EntityMention(surface_form="Acme", entity_type="organization",
                                       canonical_hint="acme.example", evidence=[SPAN],
                                       confidence_bp=9000)],
        commitments=[Commitment(actor="Acme", action="send the renewal", due=due,
                                is_conditional=False, evidence=[SPAN], confidence_bp=8500)],
        decision_states=[DecisionState(subject="renewal", state="pending", owner="Acme",
                                       evidence=[SPAN], confidence_bp=8200)],
        questions=["Can we sign Friday?"], all_evidence=[SPAN],
        roles=[{"party": "Acme", "role": "counterparty", "evidence_text": QUOTE}],
        model_snapshot="model-2026", prompt_version="l1.email.v1", schema_version="3",
        extraction_profile="email", input_tokens=100, output_tokens=20)


def test_qes_projection_is_deterministic_and_model_free():
    one = adapt_qes_extraction(extraction(), confidence_bp=8000,
                               domain_hints=[{"domain": "sales"}],
                               signal_types=["contract_renewal"])
    two = adapt_qes_extraction(extraction().model_dump(mode="json"), confidence_bp=8000,
                               domain_hints=[{"domain": "sales"}],
                               signal_types=["contract_renewal"])
    assert one == two
    assert one.input_tokens == one.output_tokens == 0
    assert one.relevance == 0.8
    assert one.domains == ["sales"]
    assert one.entity_mentions[0]["evidence_text"] == QUOTE
    assert one.commitments[0]["due_text"] == NOW.isoformat()
    assert one.observations == [{"kind": "contract_renewal", "evidence_text": QUOTE}]


def test_qes_projection_keeps_decision_fields_and_roles():
    projected = adapt_qes_extraction(extraction(), confidence_bp=7000)
    fields = {item["field"]: item["value"] for item in projected.fact_candidates}
    assert fields == {"decision.status": "pending", "decision.owner": "Acme",
                      "decision.owner_basis": "inferred_from_qes"}
    assert projected.roles[0]["role"] == "counterparty"

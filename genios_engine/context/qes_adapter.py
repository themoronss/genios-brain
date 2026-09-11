"""The production L1 -> L2 seam: a QES extraction becomes graph candidates without another LLM.

Layer 1 owns semantic interpretation.  Layer 2 owns identity, correlation and the temporal graph.
The legacy context extractor blurred that boundary by asking a second model to read the same
message.  This module is the deliberately boring bridge between the two contracts: it projects
the typed, cached :class:`ExtractionResult` embedded by a QualifiedEnterpriseSignal into the
candidate shape the existing graph committer already validates and stores.

No database, clock or model is read here.  A replay of the same QES bytes produces the same
candidate bytes.  Unsupported L1 fields are retained as typed observations rather than guessed
into a graph field whose meaning they may not have.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.context.extract.extractor import Extraction
from genios_engine.contracts.extraction import ExtractionResult


def _span_quote(spans: Sequence[Any]) -> str:
    """The first verbatim receipt, or the honest empty value when there is none."""
    for span in spans:
        quote = str(getattr(span, "quote", "") or "")
        if quote.strip():
            return quote
    return ""


def _domains(values: Sequence[Any]) -> list[str]:
    out: set[str] = set()
    for value in values:
        raw = value.get("domain") if isinstance(value, Mapping) else getattr(value, "domain", value)
        name = str(raw or "").strip().lower()
        if name:
            out.add(name)
    return sorted(out)


def _relevance(confidence_bp: int) -> float:
    if isinstance(confidence_bp, bool) or not isinstance(confidence_bp, int):
        raise TypeError("QES confidence_bp must be an integer")
    if not 0 <= confidence_bp <= 10_000:
        raise ValueError("QES confidence_bp must be between 0 and 10000")
    return confidence_bp / 10_000


def adapt_qes_extraction(
    payload: Mapping[str, Any] | ExtractionResult,
    *,
    confidence_bp: int,
    domain_hints: Sequence[Any] = (),
    signal_types: Sequence[str] = (),
) -> Extraction:
    """Project Layer 1's cached extraction into the existing deterministic graph committer.

    This is intentionally not a semantic translation.  Each emitted candidate is copied from a
    typed L1 claim and carries that claim's exact quote.  In particular, role and relationship
    open lanes pass through as data, commitments keep their resolved due bound, and a signal type
    becomes an observation rather than a fabricated fact.
    """
    result = (payload if isinstance(payload, ExtractionResult)
              else ExtractionResult.model_validate(dict(payload)))

    entities = [{
        "type": item.entity_type,
        "name": item.surface_form,
        "email": (item.canonical_hint if item.canonical_hint and "@" in item.canonical_hint
                  else None),
        "evidence_text": _span_quote(item.evidence),
    } for item in result.entity_mentions]

    facts: list[dict[str, Any]] = []
    # The active QES route previously discarded all nine business nouns. Preserve their
    # standing and actual ALG-08 receipts, never promote a model's unverified citation to R2.
    for item in result.business_facts:
        spans = [span for span in item.evidence if span.verified]
        if not spans:
            continue
        facts.append({"subject": item.subject, "field": item.field,
                      "value": item.value if isinstance(item.value, str) else item.value.model_dump(),
                      "standing": item.standing, "business_fact": True,
                      "evidence_text": spans[0].quote,
                      "evidence_spans": [span.model_dump(mode="json") for span in spans]})
    for item in result.decision_states:
        quote = _span_quote(item.evidence)
        facts.append({"subject": item.subject, "field": "decision.status",
                      "value": item.state, "evidence_text": quote})
        if item.blocked_on:
            facts.append({"subject": item.subject, "field": "decision.blocked_on",
                          "value": item.blocked_on, "evidence_text": quote})
        if item.owner:
            facts.append({"subject": item.subject, "field": "decision.owner",
                          "value": item.owner, "evidence_text": quote})
            facts.append({"subject": item.subject, "field": "decision.owner_basis",
                          "value": "inferred_from_qes", "evidence_text": quote})
    for amount in result.amounts:
        # Money is already normalised once in L1.  Keep integer minor units and currency together;
        # a bare number here would undo the Money contract at the first upper-layer boundary.
        facts.append({"subject": "", "field": "financial.amount",
                      "value": {"minor_units": amount.minor_units,
                                "currency": amount.currency,
                                "as_written": amount.as_written},
                      "evidence_text": amount.as_written})

    commitments = []
    for item in result.commitments:
        due_text = None
        if item.due is not None and item.due.earliest is not None:
            due_text = item.due.earliest.isoformat()
        commitments.append({
            "actor": item.actor,
            "action": item.action,
            "due_text": due_text,
            "is_conditional": item.is_conditional,
            "condition_text": item.condition_text,
            "evidence_text": _span_quote(item.evidence),
        })

    observations: list[dict[str, Any]] = []
    default_quote = _span_quote(result.all_evidence)
    for kind in sorted({str(value).strip() for value in signal_types if str(value).strip()}):
        observations.append({"kind": kind, "evidence_text": default_quote})
    for item in result.unclassified_observations:
        observations.append({"kind": item.proposed_kind,
                             "evidence_text": _span_quote(item.evidence),
                             "description": item.description})

    questions = [{"text": question, "directed_at": "us", "evidence_text": question}
                 for question in result.questions]

    return Extraction(
        relevance=_relevance(confidence_bp),
        # Junk/noise was already decided by L1's publication floor.  A QES is, by definition,
        # what crossed that floor; inventing another noise judgement here is double interpretation.
        noise_type="none",
        domains=_domains(domain_hints),
        entity_mentions=entities,
        fact_candidates=facts,
        commitments=commitments,
        questions=questions,
        observations=observations,
        roles=[dict(value) for value in result.roles],
        relationships=[dict(value) for value in result.relationships],
        scheduling_proposals=[dict(value) for value in result.scheduling_proposals],
        objective={},
        input_tokens=0,
        output_tokens=0,
        ok=True,
        raw="",
    )


__all__ = ["adapt_qes_extraction"]

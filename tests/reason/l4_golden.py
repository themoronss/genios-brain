"""Expand `tests/golden/l4/bundle_review.json` into REAL contract objects.

Nothing here is a mock. Each fixture's `situation` becomes a genuine `ReasoningDecision` with real
`DecisionCandidate`s, real `CandidateCheck`-free constraint applications, real `Finding`s and a real
`ReasoningRequest` — so what the golden set grades is the code that will run in production, not a
convenient shape of it. The one thing that is not real is the model: `model_answer` is a recorded
generation, which is the point of a replay lane.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    CapabilityManifest,
    ContextSnapshot,
    DecisionCandidate,
    DecisionOutcome,
    EvidenceRef,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningDecision,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.contracts.domain_expertise import citation_statement_hash

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "l4" / "bundle_review.json"
NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def load_golden() -> dict:
    return json.loads(GOLDEN.read_text())


def _statement_hash(statement: str) -> str:
    """L3's receipt, computed by L3's OWN function — `require_citation` re-checks it byte for byte.

    `citation_statement_hash`, not a local hash: a golden set that computed the receipt its own way
    would prove the fixtures agree with themselves and nothing about the corpus.
    """
    return citation_statement_hash(statement)


def citation(record: dict) -> dict:
    return {"artifact_id": record["artifact_id"], "artifact_class": record["artifact_class"],
            "statement": record["statement"],
            "statement_hash": _statement_hash(record["statement"]),
            "source_ref": record["source_ref"]}


def build(situation: dict, *, eval_time: datetime = NOW):
    """(decision, results, request) for one golden situation."""
    plays = tuple(
        PlayDefinition(play_id=item["play_id"], version="1.0.0", label=item["label"],
                       steps=tuple(item.get("steps") or ("act",)))
        for item in situation["candidates"])
    specs = tuple(ReasonerSpec(reasoner_id=unit["unit"], version="1.0.0")
                  for unit in situation["units"]) or (
        ReasonerSpec(reasoner_id="core.context", version="1.0.0"),)
    capability = CapabilityManifest(
        capability_id=situation["capability_id"], version="1.0.0", domain=situation["domain"],
        root_entity_type=situation["subject_type"],
        goal=Goal(goal_id="golden.goal", statement="Decide what should happen next here."),
        reasoners=specs, plays=plays, policies=(), live_delivery_enabled=False)
    # Every EvidenceRef points at a fact that EXISTS and whose value MATCHES — the contract
    # checks both, which is what makes these snapshots real rather than convenient.
    facts = {key: {"value": value} for key, value in situation["facts"].items()}
    for item in situation["evidence_ids"]:
        facts[f"evidence.{item}"] = {"value": item}
    context = ContextSnapshot(
        org_id="org_golden", graph_version=1, root_entity_id="node_golden",
        root_entity_type=situation["subject_type"], evaluation_time=eval_time,
        selector_version="golden.selector.v1", facts=facts,
        evidence=tuple(EvidenceRef(evidence_id=item, field=f"evidence.{item}", value=item)
                       for item in situation["evidence_ids"]))
    request = ReasoningRequest(
        org_id="org_golden", capability=capability, context=context, evaluation_time=eval_time,
        trigger_kind="golden.trigger", config_snapshot_id="cfg_golden")

    results = tuple(
        ReasonerResult(
            reasoner_id=unit["unit"], reasoner_version="1.0.0", status=ResultStatus.COMPLETED,
            matched=True, metrics=dict(unit.get("metrics") or {}),
            findings=tuple(
                Finding(finding_id=f"{unit['unit']}:{found['kind']}", kind=found["kind"],
                        matched=True, metrics=dict(found.get("metrics") or {}),
                        evidence_ids=tuple(found.get("evidence_ids") or ()),
                        reason_codes=tuple(found.get("reason_codes") or ()),
                        value_bp=found.get("value_bp"))
                for found in unit.get("findings") or ()),
            evidence_ids=tuple(situation["evidence_ids"]))
        for unit in situation["units"])

    candidates = []
    for item in situation["candidates"]:
        eliminated = bool(item.get("eliminated"))
        components = dict(item.get("components") or {})
        components["formula_utility"] = item.get("formula_utility_bp", item["utility_bp"])
        candidates.append(DecisionCandidate(
            play_id=item["play_id"], play_version="1.0.0",
            disposition=(CandidateDisposition.ELIMINATED if eliminated
                         else CandidateDisposition.ELIGIBLE),
            utility_bp=item["utility_bp"], confidence_bp=situation["confidence_bp"],
            score_components=components,
            rank_position=None if eliminated else item["rank"],
            evidence_ids=tuple(situation["evidence_ids"][:1])))
    by_play = {candidate.play_id: candidate for candidate in candidates}

    constraints = tuple(
        {"rule_id": rule["rule_id"], "severity": rule["severity"],
         "statement": rule["statement"], "statement_hash": _statement_hash(rule["statement"]),
         "source_ref": "golden_corpus", "outcome": "fired",
         "eliminated_candidate_ids": (by_play[rule["eliminates"]].candidate_id,)}
        for rule in situation.get("constraints") or ())

    selected = next(item for item in candidates if item.rank_position == 1)
    do_nothing = dict(situation["do_nothing"])
    horizon_days = do_nothing.pop("horizon_days", None)
    do_nothing["horizon"] = (eval_time + timedelta(days=horizon_days)
                             if horizon_days is not None else None)

    decision = ReasoningDecision(
        outcome=DecisionOutcome.DECISION, capability_id=situation["capability_id"],
        capability_version="1.0.0", context_snapshot_id=context.context_snapshot_id,
        candidates=tuple(candidates), selected_candidate_id=selected.candidate_id,
        confidence_bp=situation["confidence_bp"], uncertainty=(),
        do_nothing_consequence=situation["do_nothing"].get(
            "statement", "Nothing changes if this is left alone."),
        expires_at=eval_time + timedelta(days=situation["expires_in_days"]),
        outcome_window_days=situation["outcome_window_days"],
        citations=tuple(citation(item) for item in situation.get("citations") or ()),
        constraints_applied=constraints,
        confidence_vector=dict(situation["confidence_vector"]),
        do_nothing=do_nothing)
    return decision, results, request


__all__ = ["GOLDEN", "NOW", "build", "citation", "load_golden"]

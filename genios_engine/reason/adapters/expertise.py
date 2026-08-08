"""Adapt a Layer 3 ExpertisePackage into a Layer 4 CapabilityManifest.

This is the L3->L4 weld. The DomainCompiler emits knowledge (authored capabilities + objects +
four-brain rules); Layer 4's orchestrator reasons only over a `CapabilityManifest` — a DAG of
reasoning units plus plays. The authored corpus deliberately carries NO reasoner DAG (a capability
declares outcomes/failure-modes/KPIs, an object declares inference patterns), so this adapter
supplies a conservative default DAG and derives the load-bearing `required_fields` from the objects'
executable inference patterns. Package knowledge is content-hashed into the manifest version so an
overlay change yields new immutable bytes (same discipline as `legacy_capability_manifest`).

Knowledge-in, DAG-supplied. It never decides — it only shapes what Layer 4 will reason over.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genios_engine.contracts.domain_expertise import ExpertisePackage
from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerSpec,
)
from genios_engine.platform.canonical import semantic_hash

ADAPTER_ID = "expertise_to_capability"
ADAPTER_VERSION = "1.0.0"
_REQUIRED = FailurePolicy.REQUIRED


def _executable_required_fields(package: ExpertisePackage) -> tuple[str, ...]:
    """The graph fact paths Layer 4 must pull, taken only from EXECUTABLE inference patterns.

    `needs_signal` / `requires_signals` patterns name inputs that do not exist yet, so their
    fields are skipped — pulling them would fail the native context selector for no benefit.
    """
    fields: set[str] = set()
    for obj in package.objects:
        definition = obj.get("definition") if isinstance(obj, Mapping) else None
        patterns = (definition or {}).get("inference_patterns") or {}
        if not isinstance(patterns, Mapping):
            continue
        for group in ("deterministic", "heuristic"):
            for pattern in patterns.get(group, []) or []:
                if not isinstance(pattern, Mapping) or pattern.get("status") != "executable":
                    continue
                for field in pattern.get("evidence_fields", []) or []:
                    fields.add(str(field))
                for cond in pattern.get("when", []) or []:
                    if isinstance(cond, Mapping) and cond.get("path"):
                        fields.add(str(cond["path"]))
    return tuple(sorted(fields))


def _default_dag(required_fields: tuple[str, ...]) -> tuple[ReasonerSpec, ...]:
    """A conservative, situation-agnostic reasoning DAG that always terminates in a decision.

    understand (context) -> evaluate (risk) -> the mandatory REQUIRED constraint -> rank/score
    (priority + confidence, both sourced from risk) -> plan. No situation-specific gating unit, so
    a thin situation degrades confidence instead of being blocked out of reasoning entirely.
    """
    context = ReasonerSpec(
        "core.context", "1.0.0",
        required_fields=required_fields,
        failure_policy=_REQUIRED,
    )
    risk = ReasonerSpec(
        "core.risk", "1.0.0",
        dependencies=("core.context",),
        failure_policy=_REQUIRED,
    )
    constraint = ReasonerSpec(
        "core.constraint", "1.0.0",
        dependencies=("core.context",),
        input_kind="candidate_plays",
        output_kind="candidate_checks",
        failure_policy=_REQUIRED,
    )
    priority = ReasonerSpec(
        "core.priority", "1.0.0",
        dependencies=("core.risk", "core.constraint"),
        config={"source_reasoner": "core.risk"},
        failure_policy=_REQUIRED,
    )
    confidence = ReasonerSpec(
        "core.confidence", "1.0.0",
        dependencies=("core.risk",),
        config={"source_reasoner": "core.risk"},
        failure_policy=_REQUIRED,
    )
    planning = ReasonerSpec(
        "core.planning", "1.0.0",
        dependencies=("core.constraint", "core.priority", "core.confidence"),
        input_kind="ranked_candidates",
        output_kind="planning_checks",
        failure_policy=_REQUIRED,
    )
    return (context, risk, constraint, priority, confidence, planning)


def _plays(package: ExpertisePackage) -> tuple[PlayDefinition, ...]:
    """Playbook `expert_rules` (definitions carrying steps) become read-only review plays.

    Everything Layer 3 supplies is advisory knowledge, so every play is read_only and leaves any
    outreach to explicit human approval. A safe review play is always provided so the manifest's
    non-empty-plays invariant holds even when the package authored no playbook.
    """
    plays: list[PlayDefinition] = []
    seen: set[str] = set()
    for rule in package.expert_rules:
        if not isinstance(rule, Mapping):
            continue
        definition = rule.get("definition") or {}
        raw_steps = definition.get("steps") if isinstance(definition, Mapping) else None
        if not raw_steps:
            continue
        steps = tuple(
            str(step.get("description") or step.get("name")) if isinstance(step, Mapping)
            else str(step)
            for step in raw_steps
        )
        steps = tuple(s for s in steps if s and s != "None")
        if not steps:
            continue
        play_id = str(rule.get("id") or f"play_{len(plays)}").replace(" ", "_")[:120]
        if play_id in seen:
            continue
        seen.add(play_id)
        plays.append(PlayDefinition(
            play_id, "1.0.0", str(definition.get("name") or play_id)[:200],
            steps=steps,
            read_only=True,
            tags=("human_approval", "playbook"),
            metadata={"source": "expert_playbook", "external_recipient_required": False},
        ))
        if len(plays) >= 4:
            break
    if not plays:
        plays.append(PlayDefinition(
            "review_situation", "1.0.0", "Review the compiled expertise",
            steps=(
                "Review the compiled expert, organization, behavior and adaptive knowledge.",
                "Choose the safest next step with the owner.",
                "Leave any outreach or system change for explicit human approval.",
            ),
            read_only=True,
            tags=("human_approval", "review"),
            metadata={"source": "adapter_default", "external_recipient_required": False},
        ))
    return tuple(plays)


def _goal(package: ExpertisePackage, situation_type: str) -> Goal:
    statement = f"Resolve the {situation_type} situation using the compiled expertise."
    for capability in package.capabilities:
        definition = capability.get("definition") if isinstance(capability, Mapping) else None
        question = (definition or {}).get("question")
        if question:
            statement = str(question)
            break
    return Goal(
        f"expertise.{situation_type}",
        statement,
        constraints=("Never send or mutate an external system autonomously.",),
    )


def expertise_capability_manifest(
    package: ExpertisePackage, *, root_entity_type: str,
) -> CapabilityManifest:
    """One ExpertisePackage -> one CapabilityManifest driving Layer 4's reasoning."""
    situation_type = str(package.metadata.get("situation_type") or "situation")
    domain_ids = package.metadata.get("domain_ids") or ()
    domain = str(domain_ids[0]) if domain_ids else "general"
    required_fields = _executable_required_fields(package)

    knowledge_hash = semantic_hash({
        "capabilities": package.capabilities,
        "objects": package.objects,
        "expert_rules": package.expert_rules,
        "organization_rules": package.organization_rules,
        "behavior_patterns": package.behavior_patterns,
        "adaptive_preferences": package.adaptive_preferences,
        "brain_snapshot_id": package.brain_snapshot_id,
    })

    return CapabilityManifest(
        capability_id=f"expertise.{situation_type}",
        version=f"exp.{knowledge_hash[:16]}",
        domain=domain,
        root_entity_type=str(root_entity_type or "entity"),
        goal=_goal(package, situation_type),
        reasoners=_default_dag(required_fields),
        plays=_plays(package),
        required_fields=required_fields,
        policies=("read_only", "human_approval_required", "evidence_required"),
        live_delivery_enabled=False,          # typed L3->L4 path stays advisory until cutover
        do_nothing_consequence=(
            f"The {situation_type} situation is left unaddressed while its evidence compounds."
        ),
        metadata={
            "adapter": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "situation_type": situation_type,
            "expertise_id": package.id,
            "brain_snapshot_id": package.brain_snapshot_id,
            "object_coverage_bp": package.metadata.get("object_coverage_bp"),
            "knowledge_hash": knowledge_hash,
            "schema": "capability.v1",
        },
    )


__all__ = ["expertise_capability_manifest", "ADAPTER_ID", "ADAPTER_VERSION"]

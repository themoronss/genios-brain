"""Artifact builder — combines trace + narrator output + counterfactuals into a final brief/report.

Per MD g-i-6 §6.1.2:
- conclusion from Decision (engine)
- WHY = narrated derivation chain (grounded)
- counterfactuals = from g-i-2 symbolic what-if ONLY (never LLM-invented)
- recommendation = from Decision.recommend
- confidence = from external scorer
- uncertainty = flagged low-trust / below-N_min / gap-fill items

Template = Jinja2 (per g-i-6 blocker pick). Module-supplied template files
(modules/sales/artifacts/*.yaml) describe the brief shape.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from jinja2 import StrictUndefined, Template

from core.artifacts.narrator import NarratorResult
from core.artifacts.trace import Trace
from core.foundations.telemetry import get_logger
from core.reasoning.what_if import PremortemResult, WhatIfResult

log = get_logger(__name__)


class ArtifactKind(StrEnum):
    BRIEF = "brief"
    RISK_REPORT = "risk_report"
    MEMO = "memo"


@dataclass(frozen=True)
class Artifact:
    """A finalized artifact ready to ship. JSON-serializable for g-i-7 envelope."""

    id: str
    org_id: str
    decision_id: str
    kind: ArtifactKind
    title: str
    body: str  # the rendered text
    trace: Trace  # the audit-ready trace
    counterfactuals: list[dict[str, Any]]  # from symbolic what-if, never LLM
    uncertainty_summary: str  # human-readable summary of trace.uncertainty
    generated_at: datetime


def build_artifact(
    *,
    org_id: str,
    decision_id: str,
    kind: ArtifactKind,
    trace: Trace,
    narrator_result: NarratorResult,
    template_str: str,
    title: str,
    counterfactuals: Iterable[WhatIfResult | PremortemResult] = (),
) -> Artifact:
    """Render the artifact.

    counterfactuals MUST come from core.reasoning.what_if (WhatIfResult or
    PremortemResult dataclasses). The disclaimer ("bounded by asserted model")
    is embedded in those dataclasses and propagates into the artifact body.

    The template (Jinja2) receives a strict environment — unknown variables raise.
    Caller ensures the template only references fields available in the context.
    """
    counterfactual_payloads = [_render_counterfactual(c) for c in counterfactuals]
    uncertainty_summary = _summarize_uncertainty(trace)

    context = {
        "title": title,
        "narrative": narrator_result.prose,
        "confidence": trace.confidence.overall,
        "confidence_breakdown": trace.confidence.breakdown,
        "source_facts": [_fact_to_dict(f) for f in trace.source_facts],
        "rules_fired": [_rule_to_dict(r) for r in trace.rules_fired],
        "graph_path": [_edge_to_dict(e) for e in trace.graph_path],
        "counterfactuals": counterfactual_payloads,
        "uncertainty_flags": [_flag_to_dict(u) for u in trace.uncertainty],
        "uncertainty_summary": uncertainty_summary,
        "as_of_version": trace.as_of.graph_version,
        "as_of_timestamp": trace.as_of.timestamp.isoformat(),
    }

    template = Template(template_str, undefined=StrictUndefined, autoescape=False)
    body = template.render(**context)

    return Artifact(
        id=str(uuid.uuid4()),
        org_id=org_id,
        decision_id=decision_id,
        kind=kind,
        title=title,
        body=body,
        trace=trace,
        counterfactuals=counterfactual_payloads,
        uncertainty_summary=uncertainty_summary,
        generated_at=datetime.now(UTC),
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _render_counterfactual(c: WhatIfResult | PremortemResult) -> dict[str, Any]:
    """Convert a symbolic-only counterfactual into the artifact payload."""
    if isinstance(c, WhatIfResult):
        return {
            "kind": "what_if",
            "baseline_conclusion": c.baseline_conclusion,
            "intervention": c.intervention,
            "counterfactual_conclusion": c.counterfactual_conclusion,
            "delta": c.delta,
            "disclaimer": c.disclaimer,
        }
    return {
        "kind": "premortem",
        "goal": c.goal,
        "failure_interventions": c.failure_interventions,
        "load_bearing_assumptions": c.load_bearing_assumptions,
        "disclaimer": c.disclaimer,
    }


def _summarize_uncertainty(trace: Trace) -> str:
    """Human-readable summary of uncertainty flags. NEVER empty if flags exist."""
    if not trace.uncertainty:
        return "No uncertainty flags."
    lines = [f"{len(trace.uncertainty)} uncertainty flag(s):"]
    for u in trace.uncertainty:
        lines.append(f"  - [{u.kind.value}/{u.severity}] {u.detail}")
    return "\n".join(lines)


def _fact_to_dict(f: Any) -> dict[str, Any]:
    return {
        "id": f.id,
        "subject": f.subject,
        "predicate": f.predicate,
        "object": f.object,
        "source_item_id": f.source_item_id,
    }


def _rule_to_dict(r: Any) -> dict[str, Any]:
    return {
        "id": r.id,
        "priority": r.priority,
        "conclusion": r.conclusion,
    }


def _edge_to_dict(e: Any) -> dict[str, Any]:
    return {
        "id": e.id,
        "from": e.from_node,
        "to": e.to_node,
        "type": e.edge_type,
        "weight": e.weight,
        "weight_source": e.weight_source,
        "trust": e.trust,
        "asserted_by_type": e.asserted_by_type,
    }


def _flag_to_dict(u: Any) -> dict[str, Any]:
    return {
        "kind": u.kind.value,
        "target": u.target,
        "severity": u.severity,
        "detail": u.detail,
    }

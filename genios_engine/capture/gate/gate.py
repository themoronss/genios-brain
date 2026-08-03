from __future__ import annotations

from genios_engine.capture.structured.registry import has_mapping
from genios_engine.contracts.trace import EventTrace

from .context import GateContext, GateResult
from .relevance import RelevanceClassifier
from .rules import hard_rule, whitelist


def run_gate(ctx: GateContext, trace: EventTrace,
             relevance: RelevanceClassifier | None = None) -> GateResult:
    """Deterministic gate + optional S2 relevance classifier. Records each stage into
    the trace. Terminal: drop / park / short_circuit(structured) / route(needs_extraction)."""

    # S0 — scope
    if not ctx.in_scope:
        trace.record("S0", "drop", reason_code="out_of_scope")
        return GateResult(action="drop", reason_code="out_of_scope")
    trace.record("S0", "pass")

    # S1.5 — structured short-circuit (already typed; skips email N-codes)
    if ctx.is_structured:
        if has_mapping(ctx.event.source, ctx.event.object_type):
            trace.record("S1.5", "short_circuit", reason_code="structured_mapped")
            return GateResult(action="short_circuit", route="structured")
        trace.record("S1.5", "park", reason_code="mapping_missing")
        return GateResult(action="park", reason_code="mapping_missing")

    # S1 — unstructured: whitelist first, then destructive hard rules
    wl = whitelist(ctx)
    if wl:
        trace.record("S1", "pass", whitelist=wl)
    else:
        hit = hard_rule(ctx)
        if hit:
            code, action = hit
            trace.record("S1", action, reason_code=code)
            return GateResult(action=action, reason_code=code)
        trace.record("S1", "pass")

    # S2 — optional relevance classifier (defense-in-depth; deterministic now,
    # LLM-swappable later). Low relevance parks for review (never a hard drop).
    if relevance is not None:
        v = relevance.classify(ctx, ctx.prepared)
        if not v.relevant:
            trace.record("S2", "park", reason_code="low_relevance", relevance=v.relevance)
            return GateResult(action="park", reason_code="low_relevance", whitelist_code=wl)
        trace.record("S2", "pass", relevance=v.relevance, reason=v.reason)
        return GateResult(action="route", route="needs_extraction", whitelist_code=wl)

    # S2 default — route unstructured candidate to L2's combined relevance+extraction call
    trace.record("S2", "pass", route="needs_extraction")
    return GateResult(action="route", route="needs_extraction", whitelist_code=wl)

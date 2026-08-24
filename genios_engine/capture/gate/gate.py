from __future__ import annotations

from genios_engine.capture.structured.registry import has_mapping
from genios_engine.contracts.trace import EventTrace

from .context import GateContext, GateResult
from .relevance import DROP_BELOW_RELEVANCE, RelevanceClassifier
from .rules import content_integrity_rule, noise_rule, whitelist


def run_gate(ctx: GateContext, trace: EventTrace,
             relevance: RelevanceClassifier | None = None) -> GateResult:
    """Deterministic gate + optional S2 relevance classifier. Records each stage into
    the trace. Terminal: drop / park / short_circuit(structured) / route(needs_extraction)."""

    # S0 — scope
    if not ctx.in_scope:
        trace.record("S0", "drop", reason_code="out_of_scope")
        return GateResult(action="drop", reason_code="out_of_scope")
    trace.record("S0", "pass")

    # S0.5 — VERSIONABILITY, before anything can short-circuit past it.
    #
    # This has to precede the structured branch, not follow it: every source the check exists for
    # — calendar, HubSpot, the client's own database — is structured, so running it after S1.5
    # meant it could never fire for any of them. The rule was correct and unreachable, which is
    # the same as absent but harder to notice.
    #
    # A changing object with no version is undedupable: the ledger says "already seen" on every
    # later sync and the object freezes at whatever state it was in the first time.
    integrity = content_integrity_rule(ctx)
    if integrity and integrity[0] == "MUT-01":
        trace.record("S0.5", "park", reason_code="MUT-01")
        return GateResult(action="park", reason_code="MUT-01")

    # S0.6 — PROVENANCE, also before the structured short-circuit for the same reason as S0.5.
    #
    # An event whose audience no derivation rule can name must not publish under a guessed one:
    # "the audience of a derived insight can never be wider than the audience of the evidence",
    # and by Layer 2 the recipient list is gone, so this is the last gate that can still refuse.
    #
    # The question is "does any rule name this audience?" — NOT "did the caller remember to
    # attach one?". The normalize seam derives it with the mailbox owner and its answer wins;
    # an event built elsewhere (a legacy path, a test double) is re-derived here from the same
    # shared rules rather than parked for a constructor omission. Only a source genuinely
    # outside the rules parks — and adding its rule to capture/visibility_rules.py re-admits
    # the whole class on the next drain.
    if ctx.event.visibility is None:
        from genios_engine.capture.visibility_rules import derive_visibility
        derived = derive_visibility(
            source=ctx.event.source, actor_email=ctx.event.actor.email,
            recipients=getattr(ctx.event, "recipients", ()),
            internal_kind=ctx.event.internal_kind)
        if derived is None:
            trace.record("S0.6", "park", reason_code="visibility_unknown")
            return GateResult(action="park", reason_code="visibility_unknown")
        ctx.event.visibility = derived

    # S1.5 — structured short-circuit (already typed; skips email N-codes)
    if ctx.is_structured:
        if has_mapping(ctx.event.source, ctx.event.object_type):
            trace.record("S1.5", "short_circuit", reason_code="structured_mapped")
            return GateResult(action="short_circuit", route="structured")
        trace.record("S1.5", "park", reason_code="mapping_missing")
        return GateResult(action="park", reason_code="mapping_missing")

    # S1a — the rest of content integrity, evaluated for EVERYONE. "Can we read this?" is not a
    # question a whitelist can answer: a whitelist says the sender matters, which is a reason to
    # review an unreadable attachment more carefully, never to wave it through with an empty body.
    if integrity:
        code, action = integrity
        trace.record("S1", action, reason_code=code)
        return GateResult(action=action, reason_code=code)

    # S1b — unstructured noise: whitelist first, then the destructive N-codes
    wl = whitelist(ctx)
    if wl:
        trace.record("S1", "pass", whitelist=wl)
    else:
        hit = noise_rule(ctx)
        if hit:
            code, action = hit
            trace.record("S1", action, reason_code=code)
            return GateResult(action=action, reason_code=code)
        trace.record("S1", "pass")

    # S2 — relevance classifier. The LLM junk-gate is the ONE filter allowed to DROP on
    # judgment (keeps noise out of the graph); the deterministic classifier only parks.
    # `disposition` decides: "drop" (LLM-confident junk), "park" (low relevance, recoverable),
    # else route to extraction. Empty disposition falls back to the legacy relevant→route rule.
    if relevance is not None:
        v = relevance.classify(ctx, ctx.prepared)
        disp = v.disposition or ("keep" if v.relevant else "park")
        if disp == "drop":
            # A "drop" verdict is a proposal, not an authorisation. Deleting is irreversible —
            # the body is never stored — so the model's own confidence has to clear a named
            # threshold. Above it we still remove the mail from the working set, but as a PARK,
            # which keeps a payload and can be re-adjudicated when the gate improves.
            if v.relevance is not None and v.relevance >= DROP_BELOW_RELEVANCE:
                trace.record("S2", "park", reason_code="llm_junk_unconfident",
                             relevance=v.relevance, reason=v.reason)
                return GateResult(action="park", reason_code="llm_junk_unconfident",
                                  whitelist_code=wl)
            trace.record("S2", "drop", reason_code="llm_junk", relevance=v.relevance, reason=v.reason)
            return GateResult(action="drop", reason_code="llm_junk", whitelist_code=wl)
        if disp == "park":
            trace.record("S2", "park", reason_code="low_relevance", relevance=v.relevance)
            return GateResult(action="park", reason_code="low_relevance", whitelist_code=wl)
        trace.record("S2", "pass", relevance=v.relevance, reason=v.reason)
        return GateResult(action="route", route="needs_extraction", whitelist_code=wl)

    # S2 default — route unstructured candidate to L2's combined relevance+extraction call
    trace.record("S2", "pass", route="needs_extraction")
    return GateResult(action="route", route="needs_extraction", whitelist_code=wl)

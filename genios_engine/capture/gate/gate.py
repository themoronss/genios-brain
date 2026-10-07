from __future__ import annotations

from genios_engine.capture.structured.mapper import route_structured
from genios_engine.contracts.trace import EventTrace

from .context import GateContext, GateResult
from .relevance import DROP_BELOW_RELEVANCE, RelevanceClassifier
from .rules import availability_marker, content_integrity_rule, noise_rule, whitelist

#: What the gate does with a mail a rule or the model would have DELETED (STEP-03, the gate keeps
#: everything). Every noise rule (N-01 … N-10) and the model's confident junk (`llm_junk`) was a
#: drop, and a drop kept no body: on the golden set 33 of 86 mails — Boardy's introductions, the
#: government portal's updates, a bounce report — were gone for good, and in production 258 of 395
#: (`speedrun008/YC-II W27/` STEP-03 §8.1). The Atlas, RULE 04: uncertainty routes, it never
#: deletes. The rule's verdict is unchanged — it still says "noise", with its code — and the gate
#: is the one place that turns that verdict into what happens to the mail: kept, encrypted, and
#: read by no model (`capture/attention.ARCHIVE`).
ARCHIVE = "archive"


def _never_delete(action: str) -> str:
    """A rule's `drop` is the gate's `archive`; every other verdict (`park`) stands."""
    return ARCHIVE if action == "drop" else action


def run_gate(ctx: GateContext, trace: EventTrace,
             relevance: RelevanceClassifier | None = None) -> GateResult:
    """Deterministic gate + optional S2 relevance classifier. Records each stage into
    the trace. Terminal: archive / park / short_circuit(structured) / route(needs_extraction),
    and drop for S0 alone — a scope exclusion, not a judgment about the mail."""

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
        route = route_structured(ctx.event.source, ctx.event.object_type)
        if route.mapped:
            trace.record("S1.5", "short_circuit", reason_code="structured_mapped",
                         mapping_id=route.mapping.mapping_id)
            return GateResult(action="short_circuit", route="structured")
        # DIVERGENCE FROM DOC 03 L1.3.9, deliberate and narrower than the doc.
        #
        # The doc's failure table says an unregistered structured source "falls to
        # `needs_extraction`, model runs on JSON — acceptable fallback, but counted". This gate
        # PARKS instead, and keeps doing so: parking is recoverable and free, and
        # `parked/drain.py` re-drains `mapping_missing` the moment a mapping is registered, so
        # the object flows through the bypass it was always entitled to rather than through a
        # model reading raw JSON at model confidence. Running the model is the strictly worse
        # half of the doc's own sentence and is the one thing the component exists to avoid.
        #
        # The METRIC is the half worth keeping, and it is kept: `unmapped_structured` rides the
        # trace, so "how many objects paid for a mapping nobody wrote?" is countable from stored
        # traces instead of being a number nothing emits.
        trace.record("S1.5", "park", reason_code="mapping_missing",
                     unmapped_structured=route.unmapped_structured)
        return GateResult(action="park", reason_code="mapping_missing")

    # S1a — the rest of content integrity, evaluated for EVERYONE. "Can we read this?" is not a
    # question a whitelist can answer: a whitelist says the sender matters, which is a reason to
    # review an unreadable attachment more carefully, never to wave it through with an empty body.
    if integrity:
        code, action = integrity
        action = _never_delete(action)           # N-10, the empty mail: archived, not deleted
        trace.record("S1", action, reason_code=code)
        return GateResult(action=action, reason_code=code)

    # S1b — unstructured noise: whitelist first, then the N-codes, each ARCHIVED with its code
    wl = whitelist(ctx)
    if wl:
        # A re-read (W-06) names why it is read again, so the trace says which recovery it was;
        # a sender the company brief names (W-07) names why the founder named it (STEP-07).
        trace.record("S1", "pass", whitelist=wl,
                     **({"rereading": ctx.rereading} if ctx.rereading else {}),
                     **({"named_in_brief": ctx.named_in_brief}
                        if wl == "W-07" else {}))
    else:
        hit = noise_rule(ctx)
        if hit:
            code, action = hit
            action = _never_delete(action)
            trace.record("S1", action, reason_code=code)
            return GateResult(action=action, reason_code=code)
        trace.record("S1", "pass")

    # S1c — AVAILABILITY NOTICE (N-05). An out-of-office / leave / auto-reply message used to be
    # dropped on its subject; it is now routed to extraction, marked, WITHOUT the S2 junk gate —
    # a vacation responder is exactly what that gate is built to call "automated, drop", and it is
    # the one automated message whose content (who is away, until when, who covers) is the point.
    marker = availability_marker(ctx.raw)
    if marker:
        trace.record("S2", "pass", reason_code="N-05", route="needs_extraction",
                     availability=marker)
        return GateResult(action="route", route="needs_extraction", whitelist_code=wl,
                          availability=marker)

    # S2 — relevance classifier. The LLM junk-gate is the ONE filter allowed to take a mail out
    # of the working set on judgment (keeps noise out of the graph); the deterministic classifier
    # only parks. `disposition` decides: "drop" (LLM-confident junk — ARCHIVED, STEP-03), "park"
    # (low relevance, recoverable), else route to extraction. Empty disposition falls back to the
    # legacy relevant→route rule.
    # NOT FOR A RE-READ (STEP-05). The classifier's question — keep this mail or not — was
    # answered when the mail was kept: a park re-admitted for `low_relevance` met the very
    # classifier that parked it, and was parked again. A re-read is routed to be read.
    # NOR FOR A SENDER THE COMPANY BRIEF NAMES (STEP-07, W-07): the founder said this sender's mail
    # matters — the portal of a live application, the agent that introduces them — and the
    # classifier's question, "is a specific human writing?", is the one that got it wrong.
    if relevance is not None and not ctx.rereading and wl != "W-07":
        v = relevance.classify(ctx, ctx.prepared)
        disp = v.disposition or ("keep" if v.relevant else "park")
        if disp == "drop":
            # A "drop" verdict is a proposal, not an authorisation, so the model's own
            # confidence has to clear a named threshold. Above it the mail is PARKED, which
            # keeps a payload and can be re-adjudicated when the gate improves. Below it the mail
            # is ARCHIVED — kept and unread, never deleted — and the parked drain re-admits an
            # archived `llm_junk` mail exactly as it re-admitted a dropped one (03 F55).
            if v.relevance is not None and v.relevance >= DROP_BELOW_RELEVANCE:
                trace.record("S2", "park", reason_code="llm_junk_unconfident",
                             relevance=v.relevance, reason=v.reason)
                return GateResult(action="park", reason_code="llm_junk_unconfident",
                                  whitelist_code=wl)
            trace.record("S2", ARCHIVE, reason_code="llm_junk", relevance=v.relevance,
                         reason=v.reason)
            return GateResult(action=ARCHIVE, reason_code="llm_junk", whitelist_code=wl)
        if disp == "park":
            trace.record("S2", "park", reason_code="low_relevance", relevance=v.relevance)
            return GateResult(action="park", reason_code="low_relevance", whitelist_code=wl)
        trace.record("S2", "pass", relevance=v.relevance, reason=v.reason)
        return GateResult(action="route", route="needs_extraction", whitelist_code=wl)

    # S2 default — route unstructured candidate to L2's combined relevance+extraction call
    trace.record("S2", "pass", route="needs_extraction")
    return GateResult(action="route", route="needs_extraction", whitelist_code=wl)

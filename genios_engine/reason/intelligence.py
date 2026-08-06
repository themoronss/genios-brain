"""Grounding-first intelligence query compatibility adapter.

Layer 4 owns the decision. The strongest deterministic signal selects the play and graph-derived
confidence; an LLM may only phrase an optional explanation of that already-fixed decision. It can
never replace the action, rank candidates, manufacture confidence, or select an autonomous route.
The public Envelope shape stays backward compatible while the reasoning kernel is introduced.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.reason.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    authority_time,
)

def normalize_question(q: str) -> str:
    return " ".join((q or "").lower().split())


def _route(conf: float) -> str:
    # GeniOS v1 is read-only. Confidence can change attention, never execution authority.
    return "notify" if conf >= 0.5 else "flag"


def _envelope(org_id: str, gv: int, *, recommendation: dict, confidence: float,
              derivation: list, uncertainty: list, route: str,
              evaluation_time: datetime, decision_key: str,
              triggered_by: str = "query", foresight: dict | None = None,
              explanation: str | None = None) -> dict:
    when = evaluation_time if evaluation_time.tzinfo else evaluation_time.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    env = {
        "recommendation": recommendation,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "derivation": derivation,
        "uncertainty": uncertainty,
        "route": route,
        "triggered_by": triggered_by,
        "as_of": {"graph_version": int(gv),
                  "timestamp": when.isoformat()},
        "org_id": org_id,
    }
    if foresight is not None:        # C4 — additive; predicts deal outcome from base rate + signals
        env["foresight"] = foresight
    if explanation:
        env["explanation"] = explanation
    # The identifier binds the complete semantic envelope (including the rendered explanation and
    # explicit timestamp) plus the normalized query/input key.  A persistence conflict can therefore
    # never silently make one returned envelope explain another.
    semantic = json.dumps({"decision_key": decision_key, "envelope": env}, sort_keys=True,
                          separators=(",", ":"), default=str, allow_nan=False)
    env["decision_id"] = "dec_" + hashlib.sha256(semantic.encode("utf-8")).hexdigest()
    return env


def current_graph_version(store, org_id: str) -> int:
    with store.engine.connect() as c:
        return int(c.execute(text("select coalesce(max(graph_version),0) from graph_versions "
                                  "where org_id=:o"), {"o": org_id}).scalar() or 0)


def _neighborhood(c, org_id: str, node_id: str) -> set:
    """1-hop edge neighbors (both directions) of a node, plus itself — the deal→account→contacts
    →champion cluster. This is the multi-hop substrate the flat rule engine never reads."""
    rows = c.execute(text(
        "select case when from_node_id=:n then to_node_id else from_node_id end as nid "
        "from graph_edges where org_id=:o and valid_to is null "
        "and (from_node_id=:n or to_node_id=:n) "
        "order by case when from_node_id=:n then to_node_id else from_node_id end asc, "
        "edge_version_id asc limit 40"), {"o": org_id, "n": node_id}).fetchall()
    return {node_id} | {r.nid for r in rows}


def _retrieve(store, org_id: str, question: str, evaluation_time: datetime | None = None):
    """Grounding = the fired signals + facts for the NEIGHBOURHOOD of the entity the question is
    about (multi-hop over graph_edges), not the org-wide top-12. General questions (no entity match)
    fall back to org-wide top signals. Returns (signals, facts, focus_name)."""
    ql = normalize_question(question)
    as_of = authority_time(evaluation_time)
    first_word = ql.split()[0] if ql.split() else ""
    with store.engine.connect() as c:
        ents = c.execute(text(
            "select node_id, display_name, node_type from graph_nodes where org_id=:o "
            "and valid_to is null and length(display_name) > 2 and ("
            "  :q ilike '%' || lower(display_name) || '%' "
            "  or lower(display_name) ilike '%' || :w || '%') "
            "order by length(display_name) asc, lower(display_name) asc, node_id asc limit 4"),
            {"o": org_id, "q": ql, "w": first_word}).fetchall()

        scope: set = set()
        for e in ents:
            scope |= _neighborhood(c, org_id, e.node_id)     # multi-hop: entity + its edge-neighbours

        if scope:
            scope_ids = sorted(scope)
            signals = c.execute(text(
                "select rr.capability_id as rule_id, " + AUTHORITATIVE_REASON_CODE_SQL +
                " as reason_code, " + AUTHORITATIVE_SCORE_SQL + " as score, "
                "selected_rc.play_id as play, "
                "coalesce(authority_payload.payload->'evidence', selected_rc.evidence_refs) "
                "as evidence, "
                "s.reasoning_run_id, n.display_name "
                "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
                "left join reasoning_context_payloads authority_payload "
                "on authority_payload.org_id=authority_ctx.org_id and "
                "authority_payload.context_snapshot_id=authority_ctx.context_snapshot_id "
                "left join graph_nodes n on n.node_id=s.subject_node_id "
                "and n.org_id=s.org_id and n.valid_to is null "
                "where s.org_id=:o and s.status='open' and " +
                AUTHORITATIVE_SIGNAL_PREDICATE + " "
                "and s.subject_node_id = any(:ids) "
                "order by selected_rc.final_utility_bp desc, rr.capability_id asc, "
                "s.subject_node_id asc, "
                "s.signal_id asc limit 15"),
                {"o": org_id, "ids": scope_ids, "authority_time": as_of}).fetchall()
            facts = []
            for nid in scope_ids[:8]:
                node = c.execute(text("select display_name, node_type from graph_nodes where "
                                      "org_id=:o and node_id=:n and valid_to is null "
                                      "order by version desc limit 1"),
                                 {"o": org_id, "n": nid}).first()
                if node is None:
                    continue
                fr = c.execute(text(
                    "select field, value from graph_facts where org_id=:o and subject_node_id=:n "
                    "and valid_to is null and status='active' order by occurred_at desc nulls last "
                    ", field asc, fact_version_id asc limit 12"),
                    {"o": org_id, "n": nid}).fetchall()
                # qualitative signals extracted from comms (objection / competitor / budget_approved /
                # pricing_discussed / buying_intent…) — already produced by B3, never used in reasoning.
                obs = [r.kind for r in c.execute(text(
                    "select kind from graph_observations where org_id=:o and subject_node_id=:n "
                    "and status='active' order by occurred_at desc nulls last, kind asc, "
                    "observation_id asc limit 10"),
                    {"o": org_id, "n": nid})]
                if fr or obs:
                    fact_values = {}
                    for fact in fr:
                        # The current-fact invariant should yield one row per field.  If legacy data
                        # violates it, retain the newest row instead of allowing iteration order to
                        # overwrite it with an older value.
                        fact_values.setdefault(fact.field, str(fact.value).strip('"'))
                    facts.append({"entity": node.display_name, "type": node.node_type,
                                  "facts": fact_values,
                                  "observations": obs})
        else:
            signals = c.execute(text(
                "select rr.capability_id as rule_id, " + AUTHORITATIVE_REASON_CODE_SQL +
                " as reason_code, " + AUTHORITATIVE_SCORE_SQL + " as score, "
                "selected_rc.play_id as play, "
                "coalesce(authority_payload.payload->'evidence', selected_rc.evidence_refs) "
                "as evidence, "
                "s.reasoning_run_id, n.display_name "
                "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
                "left join reasoning_context_payloads authority_payload "
                "on authority_payload.org_id=authority_ctx.org_id and "
                "authority_payload.context_snapshot_id=authority_ctx.context_snapshot_id "
                "left join graph_nodes n on n.node_id=s.subject_node_id "
                "and n.org_id=s.org_id and n.valid_to is null "
                "where s.org_id=:o and s.status='open' and " +
                AUTHORITATIVE_SIGNAL_PREDICATE + " "
                "order by selected_rc.final_utility_bp desc, rr.capability_id asc, "
                "s.subject_node_id asc, "
                "s.signal_id asc limit 12"),
                {"o": org_id, "authority_time": as_of}).fetchall()
            facts = []
    return signals, facts, (ents[0].display_name if ents else None)


def _grounding_strength(signals, facts) -> float:
    """How much the graph actually supports an answer (0-1): breadth of fired signals + facts, plus
    the average signal strength. Used to TEMPER the LLM's self-reported confidence."""
    n_sig = len(signals)
    n_facts = sum(len(f["facts"]) + len(f.get("observations", [])) for f in facts)
    avg = (sum(float(s.score or 0) for s in signals) / n_sig / 100.0) if n_sig else 0.0  # score is 0-100
    breadth = min(1.0, (min(n_sig, 4) / 4.0) * 0.5 + (min(n_facts, 12) / 12.0) * 0.5)
    return round(min(1.0, 0.5 * breadth + 0.5 * avg), 3)


def _derivation(signals) -> list:
    return [{"rule_id": s.rule_id, "conclusion": s.reason_code,
             "matched_facts": (s.evidence if isinstance(s.evidence, (dict, list, tuple)) else {}),
             "about": s.display_name,
             "score": float(s.score) if s.score is not None else None,
             "reasoning_run_id": getattr(s, "reasoning_run_id", None)}
            for s in signals]


def _prompt(question: str, module_id: str, signals, facts, fixed: dict, extra: dict,
            focus: str | None) -> str:
    sig = "\n".join(
        f"- [{s.rule_id}] {s.reason_code} — about {s.display_name or 'unknown'} (score {s.score})"
        for s in signals) or "(no fired signals)"
    # Cross-signal synthesis is already reflected in `fixed`; the renderer may only explain it.
    synth = ""
    if focus and len(signals) >= 2:
        synth = (f"\nThese {len(signals)} signals concern {focus}'s deal/account. Explain their "
                 f"combined support for the fixed decision without adding another action.\n")
    return (
        f"You are the explanation renderer for GeniOS. The deterministic engine has ALREADY fixed "
        f"the action below. Explain it in one concise sentence using ONLY the supplied signals/facts. "
        f"Do not choose, modify, rank, or add an action. Do not output confidence. Never invent data."
        f"\n{synth}\n"
        f"QUESTION: {question}\n\n"
        f"FIXED DECISION (immutable):\n{json.dumps(fixed, default=str)}\n\n"
        f"FIRED SIGNALS (deterministic pack-rule firings on the live graph):\n{sig}\n\n"
        f"ENTITY FACTS + OBSERVATIONS (observations = objections/competitors/buying-signals/"
        f"pricing extracted from their comms — weigh these):\n{json.dumps(facts, default=str)[:2800]}\n\n"
        f"USER-SUPPLIED FACTS: {json.dumps(extra or {}, default=str)[:500]}\n\n"
        f'Return STRICT JSON only: {{"explanation": "<one grounded sentence>"}}'
    )


def _fixed_recommendation(signals, focus: str | None) -> dict:
    """Select the action without language-model authority. Retrieval has a stable total order."""
    signals = [signal for signal in signals if getattr(signal, "reasoning_run_id", None)]
    top = signals[0] if signals else None
    if top is None:
        return {"headline": "No audited recommendation yet", "action": "no_action",
                "reasoning": "No open signal with a complete Layer 4 reasoning trace matched."}
    codes = []
    for signal in signals:
        if signal.reason_code not in codes:
            codes.append(signal.reason_code)
    if focus and len(codes) >= 2:
        headline = f"Review {focus}: " + " + ".join(c.replace("_", " ") for c in codes[:3])
        reasoning = "Open deterministic signals: " + ", ".join(codes[:3]) + "."
    else:
        headline = str(top.reason_code).replace("_", " ").title()
        reasoning = f"Strongest open signal: {top.reason_code}."
    return {"headline": headline, "action": top.play or "review_linked_entity",
            "reasoning": reasoning}


_DIRECTIVE_RE = re.compile(
    r"(?:\b(?:you|we)\s+(?:should|must|need\s+to|have\s+to)\b|"
    r"\b(?:next\s+step|take\s+action|instead|autonomous(?:ly)?)\b|"
    r"(?:^|[.;:!?]\s*|\b(?:and|then)\s+)(?:send|email|call|schedule|execute|delete|update|"
    r"contact|message|offer|approve|"
    r"close|follow\s+up|re-engage|reach\s+out|invite|draft|create|cancel)\b)",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:%|[A-Za-z]+)?")
_ADDRESS_RE = re.compile(r"(?:https?://\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b)", re.IGNORECASE)
_EXPLANATION_GLUE = {
    "about", "after", "also", "because", "before", "between", "context", "currently",
    "deal", "evidence", "fact", "facts", "from", "grounded", "has", "have", "indicate",
    "indicates", "into", "open", "relationship", "remains", "signal", "signals", "since",
    "strongest", "suggest", "suggests", "support", "supports", "that", "their", "there",
    "this", "through", "while", "with", "within",
}


def _validated_explanation(raw: object, *, fixed: dict, signals, facts: list,
                           extra: dict, focus: str | None) -> tuple[str | None, str | None]:
    """Accept renderer prose only when it remains explanatory and grounded.

    This is intentionally conservative.  The prose is non-authoritative, so a rejected rendering
    simply falls back to the deterministic reasoning already present in ``fixed``.
    """
    explanation = " ".join(str(raw or "").split())
    if not explanation:
        return None, "empty"
    if (len(explanation) > 500 or "\n" in str(raw or "")
            or len(re.findall(r"[.!?]+", explanation)) > 1):
        return None, "shape"
    if _DIRECTIVE_RE.search(explanation):
        return None, "action_language"

    grounding = json.dumps({
        "fixed": fixed,
        "signals": [{
            "rule_id": getattr(signal, "rule_id", None),
            "reason_code": getattr(signal, "reason_code", None),
            "score": getattr(signal, "score", None),
            "evidence": getattr(signal, "evidence", None),
            "about": getattr(signal, "display_name", None),
        } for signal in signals],
        "facts": facts,
        "extra": extra or {},
        "focus": focus,
    }, sort_keys=True, default=str)
    allowed_numbers = {token.lower() for token in _NUMBER_RE.findall(grounding)}
    if any(token.lower() not in allowed_numbers for token in _NUMBER_RE.findall(explanation)):
        return None, "invented_number"
    allowed_addresses = {token.lower() for token in _ADDRESS_RE.findall(grounding)}
    if any(token.lower() not in allowed_addresses for token in _ADDRESS_RE.findall(explanation)):
        return None, "invented_address"

    grounding_words = {word.casefold() for word in re.findall(r"\b[A-Za-z]+\b", grounding)}
    explanation_words = {word.casefold() for word in re.findall(r"\b[A-Za-z]+\b", explanation)}
    if ({"no", "not", "never", "without"} & explanation_words) - grounding_words:
        return None, "unsupported_negation"

    # New proper names and acronyms are a high-signal invention boundary.  Ignore only the first
    # ordinary capitalized word because sentence casing makes it capitalized by construction.
    allowed_words = {
        word.casefold()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9]*", grounding.replace("_", " "))
    }
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]*\b", explanation)
    for index, word in enumerate(words):
        looks_named = (word.isupper() and len(word) > 1) or (index > 0 and word[0].isupper())
        if looks_named and word.casefold() not in allowed_words:
            return None, "invented_entity"

    for word in re.findall(r"\b[A-Za-z][A-Za-z0-9]*\b", explanation):
        normalized = word.casefold()
        if len(normalized) >= 4 and normalized not in allowed_words and normalized not in _EXPLANATION_GLUE:
            return None, "ungrounded_term"

    grounding_terms = {
        word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", grounding)
        if word.casefold() not in {"fixed", "signals", "facts", "extra", "focus", "none", "null"}
    }
    explanation_terms = {word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", explanation)}
    if not grounding_terms.intersection(explanation_terms):
        return None, "no_grounded_term"
    return explanation, None


def run_query(*, org_id: str, module_id: str, question: str, extra_facts: dict,
              store, llm, registry, graph_version: int,
              eval_time: datetime | None = None, triggered_by: str = "query"):
    """Returns (envelope, llm_result_or_None). llm_result is returned so the caller can record cost."""
    module_id = module_id or "sales"
    eval_time = eval_time or datetime.now(timezone.utc)
    extra_semantic = json.dumps(extra_facts or {}, sort_keys=True, separators=(",", ":"),
                                default=str, allow_nan=False)
    extra_hash = hashlib.sha256(extra_semantic.encode("utf-8")).hexdigest()
    decision_key = f"{module_id}:{normalize_question(question)}:{extra_hash}"
    signals, facts, focus = _retrieve(store, org_id, question, eval_time)
    ground = _grounding_strength(signals, facts)

    # No grounding at all → honest low-confidence, and we DON'T spend an LLM call.
    if not signals and not any(f["facts"] or f.get("observations") for f in facts):
        env = _envelope(org_id, graph_version,
                        recommendation={"headline": "Not enough context yet",
                                        "action": "no_action",
                                        "reasoning": "No audited signal or matched graph fact can "
                                                     "support a recommendation yet."},
                        confidence=0.15, derivation=[],
                        uncertainty=[{"kind": "no_grounding",
                                      "detail": "no signals or facts matched the question"}],
                        route="flag", evaluation_time=eval_time,
                        decision_key=decision_key, triggered_by=triggered_by)
        return env, None

    # Facts and legacy/unlinked signals may ground a factual answer, but they cannot authorize a
    # recommendation.  Until a trace-linked signal exists, fail closed without an LLM call.
    if not signals:
        rec = _fixed_recommendation([], focus)
        env = _envelope(
            org_id, graph_version, recommendation=rec, confidence=ground, derivation=[],
            uncertainty=[{"kind": "no_audited_signal",
                          "detail": "matched facts have no open Layer 4 trace-linked signal"}],
            route="flag", evaluation_time=eval_time, decision_key=decision_key,
            triggered_by=triggered_by,
        )
        return env, None

    derivation = _derivation(signals)
    pack = None
    if registry is not None:
        pack, _ = registry.effective(org_id, module_id)
    # Resolve for provenance/compatibility, but never hand play selection to the renderer.
    _plays = (pack or {}).get("plays", {})
    rec = _fixed_recommendation(signals, focus)
    conf = ground
    foresight = _foresight(store, org_id, signals, focus)

    res = llm.call(_prompt(question, module_id, signals, facts, rec, extra_facts, focus),
                   max_tokens=700) if llm is not None else None
    unc = []
    explanation = None
    if res is None or not res.ok or not res.parsed:
        if res is not None:
            unc.append({"kind": "llm_unavailable"})
    else:
        parsed = res.parsed if isinstance(res.parsed, dict) else {}
        if set(parsed) != {"explanation"}:
            reject_reason = "unexpected_output_fields"
        else:
            explanation, reject_reason = _validated_explanation(
                parsed.get("explanation"), fixed=rec, signals=signals, facts=facts,
                extra=extra_facts, focus=focus)
        if reject_reason:
            explanation = rec["reasoning"]
            unc.append({"kind": "llm_explanation_rejected", "detail": reject_reason})
    if conf < 0.5:
        unc.append({"kind": "low_confidence", "detail": "thin or conflicting grounding"})
    if ground < 0.35:
        unc.append({"kind": "thin_grounding", "detail": f"only {len(signals)} signal(s) support this"})
    if focus and len(signals) >= 2:
        unc.append({"kind": "composed", "detail": f"deal-health verdict across {len(signals)} signals on {focus}"})
    return _envelope(org_id, graph_version, recommendation=rec, confidence=conf,
                     derivation=derivation, uncertainty=unc, route=_route(conf),
                     evaluation_time=eval_time, decision_key=decision_key,
                     triggered_by=triggered_by, foresight=foresight,
                     explanation=explanation), res


def _foresight(store, org_id: str, signals, focus) -> dict | None:
    """C4 — predict THIS deal's outcome from the tenant's won/lost base rate ± the open signals.
    Only when the question is about a specific entity/deal (`focus`), so we don't blend unrelated
    deals into one number; None otherwise. DISTINCT reason codes (a code counts once, not per signal)."""
    if not focus or not signals:
        return None
    from genios_engine.reason.foresight import deal_close_probability, tenant_close_base_rate
    codes = []
    for s in signals:                    # distinct, first-seen — never double-count a concern
        if s.reason_code not in codes:
            codes.append(s.reason_code)
    base = tenant_close_base_rate(store, org_id)
    fc = deal_close_probability(base["rate"], codes)
    return {"close_probability": fc["probability"], "slip_risk": fc["slip_risk"],
            "base_rate": base["rate"], "base_rate_confidence": base["confidence"],
            "closed_deals": base["n"], "focus": focus, "drivers": fc["drivers"]}

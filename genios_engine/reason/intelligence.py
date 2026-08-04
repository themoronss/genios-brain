"""Intelligence query — the /v1/intelligence/query brain, grounding-first.

The answer is mostly deterministic: L3 signals (pack rules already fired on the live graph) + the
L2 facts of the entities the question is about. The LLM (Haiku, temp 0) is used ONLY to phrase the
final recommendation + a confidence — no raw-data dump, so it's cheap and every recommendation
carries its derivation (the fired signals). Returns a canonical Envelope dict.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id


def normalize_question(q: str) -> str:
    return " ".join((q or "").lower().split())


def _route(conf: float) -> str:
    return "autonomous" if conf >= 0.8 else ("notify" if conf >= 0.5 else "flag")


def _envelope(org_id: str, gv: int, *, recommendation: dict, confidence: float,
              derivation: list, uncertainty: list, route: str,
              triggered_by: str = "query", foresight: dict | None = None) -> dict:
    env = {
        "recommendation": recommendation,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "derivation": derivation,
        "uncertainty": uncertainty,
        "route": route,
        "triggered_by": triggered_by,
        "as_of": {"graph_version": int(gv),
                  "timestamp": datetime.now(timezone.utc).isoformat()},
        "decision_id": new_id("dec"),
        "org_id": org_id,
    }
    if foresight is not None:        # C4 — additive; predicts deal outcome from base rate + signals
        env["foresight"] = foresight
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
        "and (from_node_id=:n or to_node_id=:n) limit 40"), {"o": org_id, "n": node_id}).fetchall()
    return {node_id} | {r.nid for r in rows}


def _retrieve(store, org_id: str, question: str):
    """Grounding = the fired signals + facts for the NEIGHBOURHOOD of the entity the question is
    about (multi-hop over graph_edges), not the org-wide top-12. General questions (no entity match)
    fall back to org-wide top signals. Returns (signals, facts, focus_name)."""
    ql = normalize_question(question)
    first_word = ql.split()[0] if ql.split() else ""
    with store.engine.connect() as c:
        ents = c.execute(text(
            "select node_id, display_name, node_type from graph_nodes where org_id=:o "
            "and valid_to is null and length(display_name) > 2 and ("
            "  :q ilike '%' || lower(display_name) || '%' "
            "  or lower(display_name) ilike '%' || :w || '%') "
            "order by length(display_name) asc limit 4"),
            {"o": org_id, "q": ql, "w": first_word}).fetchall()

        scope: set = set()
        for e in ents:
            scope |= _neighborhood(c, org_id, e.node_id)     # multi-hop: entity + its edge-neighbours

        if scope:
            scope_ids = list(scope)
            signals = c.execute(text(
                "select s.rule_id, s.reason_code, s.score, s.play, s.evidence, n.display_name "
                "from signals s left join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=s.org_id "
                "where s.org_id=:o and s.status='open' and s.subject_node_id = any(:ids) "
                "order by s.score desc limit 15"), {"o": org_id, "ids": scope_ids}).fetchall()
            facts = []
            for nid in scope_ids[:8]:
                node = c.execute(text("select display_name, node_type from graph_nodes where "
                                      "org_id=:o and node_id=:n and valid_to is null"),
                                 {"o": org_id, "n": nid}).first()
                if node is None:
                    continue
                fr = c.execute(text(
                    "select field, value from graph_facts where org_id=:o and subject_node_id=:n "
                    "and valid_to is null and status='active' order by occurred_at desc nulls last "
                    "limit 12"), {"o": org_id, "n": nid}).fetchall()
                # qualitative signals extracted from comms (objection / competitor / budget_approved /
                # pricing_discussed / buying_intent…) — already produced by B3, never used in reasoning.
                obs = [r.kind for r in c.execute(text(
                    "select kind from graph_observations where org_id=:o and subject_node_id=:n "
                    "and status='active' order by occurred_at desc nulls last limit 10"),
                    {"o": org_id, "n": nid})]
                if fr or obs:
                    facts.append({"entity": node.display_name, "type": node.node_type,
                                  "facts": {f.field: str(f.value).strip('"') for f in fr},
                                  "observations": obs})
        else:
            signals = c.execute(text(
                "select s.rule_id, s.reason_code, s.score, s.play, s.evidence, n.display_name "
                "from signals s left join graph_nodes n on n.node_id=s.subject_node_id and n.org_id=s.org_id "
                "where s.org_id=:o and s.status='open' order by s.score desc limit 12"),
                {"o": org_id}).fetchall()
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
             "matched_facts": (s.evidence if isinstance(s.evidence, dict) else {}),
             "about": s.display_name,
             "score": float(s.score) if s.score is not None else None}
            for s in signals]


def _prompt(question: str, module_id: str, signals, facts, plays: dict, extra: dict,
            focus: str | None) -> str:
    sig = "\n".join(
        f"- [{s.rule_id}] {s.reason_code} — about {s.display_name or 'unknown'} (score {s.score})"
        for s in signals) or "(no fired signals)"
    # cross-signal synthesis: when several signals concern the same entity/deal, force ONE composed
    # verdict ("at risk: X + Y + Z") instead of listing disconnected alerts.
    synth = ""
    if focus and len(signals) >= 2:
        synth = (f"\nThese {len(signals)} signals all concern {focus}'s deal/account — COMPOSE them into "
                 f"ONE deal-health verdict (e.g. \"{focus} at risk: <signal A> + <signal B> + <signal C>\"), "
                 f"then give the single next-best-action that addresses the biggest driver. Do not list "
                 f"them as separate points.\n")
    return (
        f"You are GeniOS, a decision copilot. Answer the user's question with ONE concrete "
        f"next-best-action, grounded ONLY in the fired signals + facts below. Never invent data; if the "
        f"grounding is thin, say so and lower the confidence.\n{synth}\n"
        f"QUESTION: {question}\n\n"
        f"FIRED SIGNALS (deterministic pack-rule firings on the live graph):\n{sig}\n\n"
        f"ENTITY FACTS + OBSERVATIONS (observations = objections/competitors/buying-signals/"
        f"pricing extracted from their comms — weigh these):\n{json.dumps(facts, default=str)[:2800]}\n\n"
        f"USER-SUPPLIED FACTS: {json.dumps(extra or {}, default=str)[:500]}\n\n"
        f'Return STRICT JSON only: {{"headline": "<short imperative recommendation>", '
        f'"action": "<the concrete step to take>", "reasoning": "<1-2 sentences citing the signal/fact>", '
        f'"confidence": <0..1 by how much grounding supports it>}}'
    )


def run_query(*, org_id: str, module_id: str, question: str, extra_facts: dict,
              store, llm, registry, graph_version: int):
    """Returns (envelope, llm_result_or_None). llm_result is returned so the caller can record cost."""
    module_id = module_id or "sales"
    signals, facts, focus = _retrieve(store, org_id, question)
    ground = _grounding_strength(signals, facts)

    # No grounding at all → honest low-confidence, and we DON'T spend an LLM call.
    if not signals and not any(f["facts"] for f in facts):
        env = _envelope(org_id, graph_version,
                        recommendation={"headline": "Not enough context yet",
                                        "action": "Connect more sources and sync so the graph has "
                                                  "facts to reason over, then ask again.",
                                        "reasoning": "No signals fired and no facts matched this question."},
                        confidence=0.15, derivation=[],
                        uncertainty=[{"kind": "no_grounding",
                                      "detail": "no signals or facts matched the question"}],
                        route="flag")
        return env, None

    derivation = _derivation(signals)
    pack = None
    if registry is not None:
        pack, _ = registry.effective(org_id, module_id)
    plays = (pack or {}).get("plays", {})

    res = llm.call(_prompt(question, module_id, signals, facts, plays, extra_facts, focus),
                   max_tokens=700) if llm is not None else None

    if res is None or not res.ok or not res.parsed:
        # Deterministic fallback from the strongest signal — still grounded, no fabrication.
        top = signals[0] if signals else None
        conf = ((float(top.score) / 100.0 if top.score and float(top.score) > 1 else float(top.score or 0))
                if top else 0.4)
        rec = {"headline": (top.reason_code.replace("_", " ").title() if top else "Review your context"),
               "action": (top.play or "Review the linked entity and follow up.")
                         if top else "No urgent action right now.",
               "reasoning": f"Strongest open signal: {top.reason_code}." if top else ""}
        unc = [{"kind": "llm_unavailable"}] if res is not None else []
        return _envelope(org_id, graph_version, recommendation=rec, confidence=conf,
                         derivation=derivation, uncertainty=unc, route=_route(conf)), res

    out = res.parsed
    llm_conf = max(0.0, min(1.0, float(out.get("confidence", 0.6) or 0.6)))
    # Confidence is DERIVED, not the LLM's self-report alone: temper it by how much the graph
    # actually grounds the answer (fired-signal breadth + fact coverage + signal strength).
    conf = round(0.5 * llm_conf + 0.5 * ground, 3)
    rec = {"headline": out.get("headline") or out.get("recommendation") or "Recommendation",
           "action": out.get("action") or out.get("next_step") or "",
           "reasoning": out.get("reasoning") or ""}
    unc = []
    if conf < 0.5:
        unc.append({"kind": "low_confidence", "detail": "thin or conflicting grounding"})
    if ground < 0.35:
        unc.append({"kind": "thin_grounding", "detail": f"only {len(signals)} signal(s) support this"})
    if focus and len(signals) >= 2:
        unc.append({"kind": "composed", "detail": f"deal-health verdict across {len(signals)} signals on {focus}"})
    return _envelope(org_id, graph_version, recommendation=rec, confidence=conf,
                     derivation=derivation, uncertainty=unc, route=_route(conf),
                     foresight=_foresight(store, org_id, signals, focus)), res


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

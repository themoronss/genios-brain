from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import text

from .bands import band
from .router import resolve_assignee
from .slots import compute_slots

# E0 · Card Builder (§5.10). Compose the card.v1 draft deterministically from a signal + play +
# template — NO LLM here (that is E1). Attaches band (E2), owner (E3), the evidence chain (≥2,
# Law 2), on-device context_tags, the four actions, and +7d expiry. Returns a draft the renderer
# fills and the store persists.

EXPIRY_DAYS = 7

# field prefix → the surface that produced it (for the evidence chain's `source`)
_SOURCE = {"deal": "crm", "thread": "gmail", "commitment": "gmail", "meeting": "calendar"}
_APP = {"deal": "app:hubspot", "thread": "app:gmail", "commitment": "app:gmail",
        "meeting": "app:googlecalendar"}


def load_node(store, org_id: str, node_id: str) -> tuple[str, str, dict, dict]:
    """(display_name, node_type, attributes, facts{field:{value,confidence,authority_rank}})."""
    with store.engine.connect() as c:
        nd = c.execute(text("select node_type, display_name, attributes from graph_nodes "
                            "where org_id=:o and node_id=:n and valid_to is null limit 1"),
                       {"o": org_id, "n": node_id}).first()
        facts: dict = {}
        for r in c.execute(text(
                "select field, value, confidence, authority_rank from graph_facts "
                "where org_id=:o and subject_node_id=:n and valid_to is null and status='active'"),
                {"o": org_id, "n": node_id}):
            v = r.value
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (ValueError, TypeError):
                    pass
            facts[r.field] = {"value": v, "confidence": float(r.confidence),
                              "authority_rank": r.authority_rank}
    if nd is None:
        return "this account", "unknown", {}, facts
    attrs = nd.attributes if isinstance(nd.attributes, dict) else json.loads(nd.attributes or "{}")
    return (nd.display_name or "this account"), nd.node_type, attrs, facts


def _why(evidence: list, facts: dict) -> list[dict]:
    """Evidence chain: field + value + source. ≥2 inline (Law 2 · no naked cards). Pads from
    the node's other active facts if the rule carried fewer than two."""
    out = []
    for e in (evidence or []):
        field = e.get("field", "")
        out.append({"field": field, "value": e.get("value"),
                    "source": _SOURCE.get(field.split(".")[0], "graph")})
    if len(out) < 2:
        for field, f in facts.items():
            if field not in {e["field"] for e in out}:
                out.append({"field": field, "value": f.get("value"),
                            "source": _SOURCE.get(field.split(".")[0], "graph")})
            if len(out) >= 2:
                break
    return out


def _context_tags(node_type: str, attrs: dict, facts: dict) -> list[str]:
    """On-device matcher whitelist (§5.14). Built ONLY from the signal's source refs — app tags
    + a work-tool url_domain/tool path when the fact set carries one. No intelligence, by design."""
    tags: set[str] = set()
    for field in facts:
        app = _APP.get(field.split(".")[0])
        if app:
            tags.add(app)
    domain = (attrs or {}).get("company_domain") or \
        (facts.get("deal.company_domain") or {}).get("value") or \
        (facts.get("company.domain") or {}).get("value")
    if domain:
        tags.add(f"url_domain:{domain}")
    deal_key = (attrs or {}).get("crm_deal_id") or (facts.get("deal.id") or {}).get("value")
    if deal_key:
        tags.add(f"hs:deal:{deal_key}")
    return sorted(tags)


def build_draft(store, org_id: str, signal: dict, effective: dict, eval_time) -> dict:
    """E0 output — a complete card.v1 minus the rendered copy (E1) and persisted state."""
    node_id = signal["subject_node_id"]
    name, node_type, attrs, facts = load_node(store, org_id, node_id)
    reason_code = signal["reason_code"]

    scoring = effective.get("scoring", {})
    urgency_band = band(int(signal["score"]), scoring.get("bands"))
    assignee, rule = resolve_assignee(store, org_id, facts, attrs)
    slots = compute_slots(reason_code, name, facts, eval_time)

    # composite deal-health (C3): the member concerns live in the signal's evidence (field='signal').
    # Surface them as a `concerns` slot + a grounded fact so the renderer can COMPOSE them into one
    # verdict ("X at risk: quiet + objection + competitor") — and the invention guard allows the words.
    if reason_code == "deal_health":
        codes = [e.get("value") for e in (signal.get("evidence") or [])
                 if isinstance(e, dict) and e.get("field") == "signal"]
        if codes:
            concerns = ", ".join(str(c).replace("_", " ") for c in codes)
            slots["concerns"] = concerns
            facts = {**facts, "deal.concerns": {"value": concerns, "confidence": 1.0,
                                                "authority_rank": 3}}
    template = (effective.get("templates", {}) or {}).get(reason_code, {})
    play_id = (effective.get("plays", {}).get(signal.get("play") or "", {}) and signal.get("play"))

    actions = [
        {"type": "run_play", "play_id": signal.get("play"),
         "label": f"Draft {template.get('artifact_kind', 'response').replace('draft_', '')}",
         "artifact_ready": True},
        {"type": "do_it_myself"},
        {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
        {"type": "wrong", "reasons": ["not_relevant", "bad_timing", "wrong_facts"]},
    ]
    score_inputs = signal.get("score_inputs") or {}
    return {
        "signal_id": signal["signal_id"], "org_id": org_id, "subject_node_id": node_id,
        "domain": effective.get("pack_id", "sales"), "level": signal.get("level", "prescriptive"),
        "urgency_band": urgency_band, "assignee": assignee, "resolved_rule": rule,
        "score": int(signal["score"]),
        "score_block": {"S": int(signal["score"]), **{k: score_inputs.get(k) for k in
                        ("U", "I", "R", "C")}, "inputs": score_inputs},
        "actions": actions, "why": _why(signal.get("evidence"), facts),
        "context_tags": _context_tags(node_type, attrs, facts),
        "config_snapshot_id": signal.get("config_snapshot_id"),
        "template_version": (effective.get("templates", {}) or {}).get("_version"),
        "expires_at": eval_time + timedelta(days=EXPIRY_DAYS),
        # carried forward to E1 (not persisted as-is)
        "_reason_code": reason_code, "_template": template, "_facts": facts, "_slots": slots,
    }

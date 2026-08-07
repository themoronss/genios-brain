from __future__ import annotations

from typing import Any

from genios_engine.capture.source_registry import PROVIDER_CAPABILITY as _REGISTRY_CAPABILITY

# Coverage / context-readiness. Absence of data must never be read as negative
# evidence — downstream layers get explicit readiness predicates instead.
# Packs declare CAPABILITIES (not vendor names); providers satisfy capabilities.

PACK_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "sales":   {"required": ["communication", "crm"],
                "recommended": ["calendar", "product_usage", "document_store"]},
    "support": {"required": ["support_desk", "communication"],
                "recommended": ["product_usage", "incident"]},
    "admin":   {"required": ["finance", "communication"],
                "recommended": ["document_store"]},
}

# Derived from the source registry, not hand-listed: this list drifting from the family
# taxonomy is why `stripe` had a capability but no family. Alias ids resolve too, so a
# connection stored as source_type='google_calendar' now counts toward `calendar`
# coverage — hand-listing only the canonical id silently under-reported it.
PROVIDER_CAPABILITY: dict[str, str] = _REGISTRY_CAPABILITY

# Which readiness predicate each capability unlocks (absence ≠ negative fact).
_READINESS = {
    "communication": ["can_evaluate_no_reply"],
    "calendar": ["can_evaluate_no_meeting"],
    "finance": ["can_evaluate_payment_state"],
    "product_usage": ["can_evaluate_usage_drop"],
}


def compute_coverage(domain: str, connected: dict[str, str],
                     company_knowledge_count: int = 0) -> dict[str, Any]:
    """connected = {capability: status}, status ∈ fresh|stale|not_connected.
    Returns capability status, missing lists, coverage_ready, readiness predicates.

    `company_knowledge_count` is NON-APP evidence — the policies/pricing/SOPs the company WROTE
    (source='internal'), not a connected app. It never satisfies a live-signal capability (writing a
    policy yields no email data), so it does NOT change coverage_ready; but it is real context, so it
    is surfaced as its own dimension instead of being invisible — the dashboard used to show
    'not connected' no matter how much knowledge was written (see LAYER1_CAPTURE_FIXES #10)."""
    reqs = PACK_REQUIREMENTS.get(domain, {"required": [], "recommended": []})

    def status_of(cap: str) -> str:
        return connected.get(cap, "not_connected")

    missing_required = [c for c in reqs["required"] if status_of(c) != "fresh"]
    missing_recommended = [c for c in reqs["recommended"] if status_of(c) != "fresh"]

    readiness: dict[str, bool] = {}
    for cap, preds in _READINESS.items():
        fresh = status_of(cap) == "fresh"
        for p in preds:
            readiness[p] = fresh
    readiness["has_company_canon"] = company_knowledge_count > 0

    return {
        "domain": domain,
        "capabilities": {c: status_of(c) for c in set(reqs["required"] + reqs["recommended"])},
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "coverage_ready": len(missing_required) == 0,
        "readiness": readiness,
        "company_knowledge": {"present": company_knowledge_count > 0,
                              "count": company_knowledge_count},
    }


def capability_of(source: str) -> str | None:
    return PROVIDER_CAPABILITY.get(source)

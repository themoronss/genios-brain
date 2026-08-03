from __future__ import annotations

from typing import Any

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

PROVIDER_CAPABILITY: dict[str, str] = {
    "gmail": "communication", "outlook": "communication", "slack": "communication",
    "gcal": "calendar", "mscal": "calendar",
    "hubspot": "crm", "salesforce": "crm",
    "zendesk": "support_desk", "intercom": "support_desk",
    "stripe": "finance", "razorpay": "finance",
    "gdrive": "document_store", "notion": "document_store",
    "postgres": "product_usage", "mixpanel": "product_usage",
}

# Which readiness predicate each capability unlocks (absence ≠ negative fact).
_READINESS = {
    "communication": ["can_evaluate_no_reply"],
    "calendar": ["can_evaluate_no_meeting"],
    "finance": ["can_evaluate_payment_state"],
    "product_usage": ["can_evaluate_usage_drop"],
}


def compute_coverage(domain: str, connected: dict[str, str]) -> dict[str, Any]:
    """connected = {capability: status}, status ∈ fresh|stale|not_connected.
    Returns capability status, missing lists, coverage_ready, readiness predicates."""
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

    return {
        "domain": domain,
        "capabilities": {c: status_of(c) for c in set(reqs["required"] + reqs["recommended"])},
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "coverage_ready": len(missing_required) == 0,
        "readiness": readiness,
    }


def capability_of(source: str) -> str | None:
    return PROVIDER_CAPABILITY.get(source)

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
    # A founder raising money has no CRM and does not need one — the pipeline lives in the
    # inbox and the calendar. Requiring `crm` here (as `sales` does) would report a correctly
    # connected fundraising tenant as permanently incomplete, which is the same failure as
    # reporting an unassessed one as ready, pointed the other way.
    "fundraising": {"required": ["communication"],
                    "recommended": ["calendar", "document_store"]},
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
    # An UNREGISTERED domain has no requirements, and "no requirements" satisfied the readiness
    # test trivially: ask for coverage on `fundraising` — this org's actual domain — and the
    # answer was "ready" with nothing connected. Every negative inference downstream ("they did
    # not reply", "no meeting was booked") then looks licensed, when in truth we had never
    # established what a complete picture for that domain even is.
    #
    # Fail closed and say why, rather than inventing a readiness nobody assessed.
    if domain not in PACK_REQUIREMENTS:
        return {
            "domain": domain,
            "capabilities": {},
            "missing_required": [],
            "missing_recommended": [],
            "coverage_ready": False,
            "coverage_state": "unknown_domain",
            "reason": (f"no capability requirements registered for domain {domain!r} — "
                       "coverage cannot be assessed, so no negative inference is licensed"),
            # Every readiness predicate false: an unassessed domain grants no permissions.
            "readiness": {p: False for preds in _READINESS.values() for p in preds}
                         | {"has_company_canon": company_knowledge_count > 0},
            "company_knowledge": {"present": company_knowledge_count > 0,
                                  "count": company_knowledge_count},
        }
    reqs = PACK_REQUIREMENTS[domain]

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
        "coverage_state": "assessed",
        "readiness": readiness,
        "company_knowledge": {"present": company_knowledge_count > 0,
                              "count": company_knowledge_count},
    }


def capability_of(source: str) -> str | None:
    return PROVIDER_CAPABILITY.get(source)

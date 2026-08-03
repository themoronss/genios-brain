from __future__ import annotations

import re

from genios_engine.contracts.gated_event import DomainHint

# Deterministic domain HINTS only (no LLM). L2's combined call decides the real domain;
# these narrow the search and seed schema loading. Source prior + keyword evidence.

_SOURCE_PRIOR: dict[str, str] = {
    "hubspot": "sales", "salesforce": "sales",
    "zendesk": "support", "intercom": "support",
    "stripe": "admin", "razorpay": "admin",
}

_KEYWORDS: dict[str, re.Pattern[str]] = {
    "sales": re.compile(r"\b(deal|pricing|proposal|contract|quote|demo|budget|renewal)\b", re.I),
    "support": re.compile(r"\b(issue|error|broken|ticket|down|outage|bug|not working)\b", re.I),
    "admin": re.compile(r"\b(invoice|payment|overdue|gst|compliance|legal|tds|filing)\b", re.I),
}


def domain_hints(source: str, text: str | None) -> list[DomainHint]:
    hints: list[DomainHint] = []
    prior = _SOURCE_PRIOR.get(source)
    if prior:
        hints.append(DomainHint(domain=prior, source="scope"))
    if text:
        for domain, pat in _KEYWORDS.items():
            if pat.search(text) and not any(h.domain == domain for h in hints):
                hints.append(DomainHint(domain=domain, source="keyword"))
    return hints

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

#: Ordered: the FIRST match wins in `resolve_domain`, so the more specific vocabulary has to be
#: tested first. `fundraising` before `sales` is the whole point — an investor thread says
#: "deck", "round" and "diligence" and also says "budget" and "contract", and letting the generic
#: sales words claim it is how six VCs and three accelerator programmes became sales
#: opportunities in this org's graph. Not one of its sixteen sales situations was a customer.
_KEYWORDS: dict[str, re.Pattern[str]] = {
    "fundraising": re.compile(
        r"\b(term ?sheet|cap ?table|safe note|pre-?seed|seed round|series [a-d]\b|"
        r"raise|raising|fundrais\w*|investor|investors|\bvc\b|venture|"
        r"pitch ?deck|\bdeck\b|diligence|due ?diligence|allocation|cheque|check size|"
        r"\bLP\b|limited partner|valuation|dilution|runway|"
        r"accelerator|incubator|cohort|residency|programme|program application|"
        r"application (?:status|outcome|deadline)|portfolio)\b", re.I),
    # `budget` and `contract` are deliberately NOT unique to sales — they appear in investor and
    # admin threads too — so they can only classify a thread the more specific patterns declined.
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

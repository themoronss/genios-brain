from __future__ import annotations

import re
from collections.abc import Sequence

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
    # ADMIN IS THE COLLECTOR, DELIBERATELY AND TEMPORARILY. Measured 2026-09-11: of 889
    # captured events, 815 matched NO domain at all — four narrow regexes covered 8% of a real
    # mailbox, so 92% reached Layer 2 with nothing to select a corpus by, and the one corpus a
    # tenant has activated never got to speak.
    #
    # Rather than invent five half-written domains, everything a business OPERATES on is filed
    # under admin while it is the activated corpus: money, people, scheduling, procurement,
    # legal, facilities, and the invitations and interviews that go with them. Fundraising,
    # sales and support keep their own patterns and are tested FIRST (see `_SHIPPED_RANK`), so
    # widening admin cannot steal a thread that names a term sheet or a deal.
    #
    # This is a staging decision, not a taxonomy. When a second corpus is activated its terms
    # move out of this pattern and into its own file — which is a corpus edit, not a deploy.
    "admin": re.compile(
        r"\b("
        # money in and out
        r"invoice|invoices|payment|payments|paid|refund|receipt|billing|billed|subscription|"
        r"overdue|outstanding|reimburse\w*|expense|expenses|payroll|salary|payout|"
        r"gst|tds|tax|taxes|vat|purchase ?order|\bPO\b|quotation|vendor|supplier|procurement|"
        # obligation and governance
        r"compliance|complian\w*|legal|filing|filings|statutory|audit|auditor|policy|"
        r"agreement|\bNDA\b|msa|sow|terms|clause|signature|sign-?off|approval|approve\w*|"
        # people
        r"hiring|hire|recruit\w*|candidate|applicant|resume|\bcv\b|interview|interviews|"
        r"shortlist|offer letter|onboard\w*|offboard\w*|appraisal|leave|attendance|"
        r"\bHR\b|human resources|employment|joining|notice period|"
        # time and access
        r"invite|invitation|invited|calendar|reschedul\w*|availability|slot|slots|agenda|"
        r"meeting|meet|call|sync|standup|review|rsvp|"
        r"access|credential|permission|licence|license|seat|account setup|"
        # place and thing
        r"office|facility|facilities|asset|assets|inventory|shipment|delivery|logistics"
        r")\b", re.I),
}

#: WHERE A BUSINESS MESSAGE GOES WHEN NO PATTERN CLAIMS IT.
#:
#: A keyword table can only recognise language somebody thought to write down. A real mailbox is
#: mostly ordinary sentences — "can you send that across", "are we still on for Thursday" — and
#: those matched nothing at all, so 92% of events arrived with no domain.
#:
#: This is used ONLY for a message the caller has already established is business, and it is
#: stamped `source="fallback"` so no reader can mistake it for evidence. `tag_domains` records
#: it exactly like any other hint; what it must never do is look like a keyword match.
FALLBACK_DOMAIN = "admin"

#: HOW SURE EACH KIND OF EVIDENCE IS, in integer basis points. Added 2026-09-24 (step 6).
#:
#: Three different claims, and flattening them to one number is how the failure this module
#: already records stayed invisible until somebody read a card:
#:
#:   scope     9000  the CONNECTION is that domain. The strongest thing L1 knows without reading
#:                   a word — an object in a Zendesk account is support because of where it came
#:                   from, not because of what it says. Not 10000: a source prior is a claim
#:                   about whose account this is, and `hints.py` already records a tenant shape
#:                   for which the shipped `stripe -> admin` prior is exactly backwards.
#:   keyword   6000  this message USED that vocabulary. Real evidence and weaker than the
#:                   account: "deck" appears in investor threads and in design threads.
#:   fallback  1000  nothing matched and the caller said "this is business". The weakest possible
#:                   statement — deliberately far below keyword so no ranking, filter or report
#:                   can ever let a placeholder sit beside evidence. It is NOT zero, because zero
#:                   reads as "we are certain this is wrong" and the honest reading is "we have
#:                   no idea, and this is where unmatched business mail is parked".
#:
#: THE ORDER IS THE CONTRACT, not the literals. `test_the_three_deterministic_sources_are_not_
#: equally_sure` asserts the ordering so a recalibration is free and an inversion is loud.
CONFIDENCE_BP: dict[str, int] = {
    "scope": 9000,
    "keyword": 6000,
    "history": 5000,
    "fallback": 1000,
}


#: WHAT AN AUTHORED CORPUS MAY ADD TO THE TWO TABLES ABOVE.
#:
#: The four names above were the ONLY business domains this system could recognise, and they are
#: a Python literal. A footwear exporter's core domain is production-and-shipping: "container
#: held at Nhava Sheva, BIS certificate pending, L/C expires Friday" matches none of the four
#: patterns, so `domain_hints` returns [] and the signal is tagged with nothing. Worse than
#: nothing for a law firm — the single word that DOES match, `legal`, types every matter email
#: as back-office admin.
#:
#: A corpus may now declare its own, in its `domain.yaml`:
#:
#:     hints:
#:       rank: 15                       # lower is tested first; see the ordering note below
#:       keywords: ['\b(container|bill of lading|L/?C|customs|HS ?code)\b']
#:       source_priors: [cargowise]
#:
#: RANK IS AN INTEGER, NOT DICT ORDER. The ordering rule that matters — fundraising before sales,
#: because an investor thread says "deck" AND "budget" and letting the generic sales words claim
#: it turned six VCs into sales opportunities — used to be carried by the insertion order of a
#: Python dict. That is invisible to an author and lost by any reordering. It is now a number
#: the shipped table states and an authored domain competes on.
#:
#: THE SHIPPED FOUR ARE THE DEFAULT AND CANNOT BE OVERWRITTEN by a corpus of the same name: their
#: patterns are calibrated against a live graph and an authored file has no evidence behind it.
#: A corpus with a name already here is skipped rather than merged, and the skip is silent
#: because it is the correct outcome, not an error.
_SHIPPED_RANK: dict[str, int] = {"fundraising": 10, "sales": 20, "support": 30, "admin": 40}


def _authored_hints() -> tuple[dict[str, tuple[int, "re.Pattern[str]"]], dict[str, str]]:
    """`{domain: (rank, pattern)}` and `{source: domain}` from every authored corpus.

    FAILS SOFT, for the reason `l3_activation._authored_domain_ids` records: a corpus that
    cannot be read is a deployment problem, and it must not stop the shipped four recognising
    anything. A corpus with a malformed regex is skipped by itself rather than taking the rest
    of the catalog with it — one bad file must not blind capture.
    """
    keywords: dict[str, tuple[int, re.Pattern[str]]] = {}
    priors: dict[str, str] = {}
    # `platform.corpus`, NOT `packs.compiler.authoring`. This module is layer 1 and `packs` is
    # layer 3; `tests/test_layer_topology.py` refused the upward import the moment it was
    # written, which is exactly what that ratchet is for. `platform` is CROSS_CUTTING — "the
    # composition root, may import anything" — so it may read the corpus and capture may read
    # it, and neither direction is upward.
    from genios_engine.platform.corpus import authored_domains

    for domain_id, data in authored_domains():
        try:
            block = (data.get("hints") or {}) if isinstance(data, dict) else {}
            if domain_id in _SHIPPED_RANK or not block:
                continue
            patterns = [str(k) for k in (block.get("keywords") or []) if str(k).strip()]
            if patterns:
                keywords[domain_id] = (
                    int(block.get("rank") or 100),
                    re.compile("|".join(f"(?:{p})" for p in patterns), re.I))
            for source in (block.get("source_priors") or []):
                priors.setdefault(str(source).strip().lower(), domain_id)
        except Exception:      # noqa: BLE001 — one bad corpus must not blind capture
            continue
    return keywords, priors


def _ordered_keywords() -> tuple[tuple[str, "re.Pattern[str]"], ...]:
    """The shipped patterns and the authored ones, in rank order.

    Recomputed per call rather than cached: `domain_hints` runs once per event and the corpus is
    a handful of small files, but more importantly a cache here would mean an authored domain
    only takes effect after a restart — which is the deploy this change exists to remove.
    """
    authored, _ = _authored_hints()
    ranked = [(_SHIPPED_RANK[name], name, pattern) for name, pattern in _KEYWORDS.items()]
    ranked += [(rank, name, pattern) for name, (rank, pattern) in authored.items()]
    # Rank, then NAME, so two domains that declare the same rank order deterministically instead
    # of by whichever the filesystem listed first.
    return tuple((name, pattern) for _rank, name, pattern in sorted(ranked, key=lambda r: (r[0], r[1])))


def domain_hints(source: str, text: str | None,
                 *, fallback: str | None = None) -> list[DomainHint]:
    """Every domain this message could belong to, in rank order.

    `fallback` is the domain to use when NOTHING else matched. It defaults to `None` — no
    caller that has not thought about it gets a guess — and a caller passes it only for a
    message it has already established is business. The resulting hint carries
    `source="fallback"`, which is the whole safety property: a reader can tell a pattern that
    fired from a pattern that did not.
    """
    hints: list[DomainHint] = []
    _, authored_priors = _authored_hints()
    # THE AUTHORED PRIOR WINS, and this reverses what I wrote in the commit that added authored
    # hints. The reasoning there was that a shipped table calibrated against a live graph beats
    # an authored file with no evidence behind it — which is right for KEYWORDS and wrong for
    # SOURCE PRIORS, and the difference matters.
    #
    # A keyword prior is a claim about LANGUAGE: "term sheet" means fundraising in every
    # business, and a corpus asserting otherwise is probably mistaken. A source prior is a claim
    # about WHOSE ACCOUNT THIS IS, and the engine cannot know that. `stripe -> admin` assumes
    # the tenant is a BUYER paying for things. For a SaaS founder whose Stripe account holds
    # their CUSTOMERS' subscriptions it is exactly backwards: every object in it is revenue, and
    # the shipped prior filed all of it under back-office, ahead of any pattern, for every
    # tenant of that shape. The tenant knows whose account it is. We are guessing.
    #
    # The shipped table stays as the DEFAULT for every tenant that has not said otherwise, which
    # is all of them today.
    prior = authored_priors.get((source or "").strip().lower()) or _SOURCE_PRIOR.get(source)
    if prior:
        hints.append(DomainHint(domain=prior, source="scope",
                                confidence_bp=CONFIDENCE_BP["scope"]))
    if text:
        for domain, pat in _ordered_keywords():
            if pat.search(text) and not any(h.domain == domain for h in hints):
                hints.append(DomainHint(domain=domain, source="keyword",
                                        confidence_bp=CONFIDENCE_BP["keyword"]))
    if not hints and fallback:
        hints.append(DomainHint(domain=str(fallback), source="fallback",
                                confidence_bp=CONFIDENCE_BP["fallback"]))
    return hints


def merge_proposals(hints: list[DomainHint], accepted: "Sequence[str]") -> list[DomainHint]:
    """L1.6.6-U7 · fold the proposer's accepted domains into the deterministic hints.

    **BOTH SIDES SURVIVE (E8), and that is the whole design.** When the keyword table says `sales`
    and the proposer says `fundraising`, the answer is BOTH — with their sources intact — not a
    winner. This module already records what picking a winner silently costs: the generic sales
    vocabulary claimed investor threads and *"six VCs and three accelerator programmes became
    sales opportunities. Not one of its sixteen sales situations was a customer."* A merge that
    resolved the disagreement would recreate that failure with a model's authority behind it.

    **A DOMAIN ALREADY DETERMINISTICALLY TAGGED IS NOT DOWNGRADED (E9).** If a keyword already
    produced `sales` at 6000 bp, a proposal agreeing costs nothing and must not replace it with
    the proposer's lower 4500 — agreement is corroboration, never doubt. The existing hint stands
    exactly as it was.

    **THE FALLBACK IS REPLACED, NOT JOINED.** A `fallback` hint means *"nothing matched and the
    caller says this is business"*. The moment anything real matches, the placeholder is no longer
    true and leaving it beside a genuine domain would count the event in both columns of metric 4.

    Pure: no clock, no I/O, no model. It is handed the names the proposer already had validated.
    """
    names = [n for n in (str(a).strip().lower() for a in accepted) if n]
    if not names:
        return hints
    from genios_engine.capture.domain.proposer import PROPOSAL_CONFIDENCE_BP

    merged = [h for h in hints if h.source != "fallback"]
    for name in names:
        if any(h.domain == name for h in merged):
            continue                           # already tagged by evidence — leave it alone
        merged.append(DomainHint(domain=name, source="proposed",
                                 confidence_bp=PROPOSAL_CONFIDENCE_BP))
    return merged

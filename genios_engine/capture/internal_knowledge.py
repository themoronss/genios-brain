"""Internal knowledge — what the company DELIBERATELY asserts about itself.

Layer 1's Internal Sources family: policies, SOPs, pricing, product facts, goals, KPIs,
org structure, employee profiles, projects, tasks, assets, wiki pages. Two doors reach
it — a person writing directly (`POST /api/org/{org}/knowledge`) and an upload tagged
with one of these kinds — and both land through the same `capture_event` pipeline as a
connector sync.

WHY THIS EXISTS — the authority gap
------------------------------------
Before this, everything unstructured landed at authority_rank=2. So an uploaded pricing
sheet carried EXACTLY the authority of a stranger's email mentioning a price, and since
system-of-record facts land at rank 3, a Stripe row would BEAT the company's own written
policy. `contracts.events` already described a human correction as "the strongest
correction signal" — that was aspirational; FACT_CONF_BY_RANK already had a rank-4 tier
that nothing ever wrote to.

Company canon enters at rank 4, above system-of-record, because:

  * The two rarely describe the same FIELD. Canon says list price and refund window;
    Stripe says what a specific customer was charged. Different facts, no contest.
  * When they DO collide on one field, a deliberate written statement by the org should
    win over a third party's inference — and the loss is not silent: graph_store records
    a discrepancy, so the conflict stays visible instead of being resolved by luck.
  * It makes an explicit human correction finally outrank the connector it corrects.

Freshness still comes first: `fact_write_action` decides recency BEFORE authority, so a
rank-4 statement from last year does not pin a field against this morning's rank-3 fact.
Canon is authoritative, not immortal. Re-asserting a kind supersedes the old assertion
through `content_version` (same door, new version → the fact re-lands).

The kind vocabulary is the doc's Internal Sources subparts, with Company Memory
deliberately EXCLUDED: memory is derived from what the graph has already seen, so
re-ingesting it as a source would launder yesterday's inference into today's evidence.
Memory belongs to Layer 2.
"""
from __future__ import annotations

# The thirteen things a company can assert about itself. Declared, never derived —
# `capture.source_registry` publishes these as the `internal` source's object types.
INTERNAL_KINDS: frozenset[str] = frozenset({
    "policy",            # rules the company binds itself to (refunds, leave, security)
    "sop",               # how a process is run, step by step
    "product",           # what we sell and what it does
    "pricing",           # list price, tiers, discount rules
    # WHO WE SELL TO. The thirteenth, and it belongs here for exactly the reason the others do:
    # it is a statement a company makes about itself, not a thing that can be inferred from its
    # mail. Two authored Sales situations — `inbound_fit_check` and `out_of_profile_deal` — are
    # about fit against this profile, and until it had somewhere to live they were asking the
    # reader to judge against a definition the product could not see.
    #
    # Deliberately DECLARED and not derived from closed-won accounts. A profile inferred from
    # who happened to buy is a description of past luck, and using it to reject new accounts is
    # how a pipeline narrows onto its own history.
    "icp",               # who we sell to: segment, size, geography, what disqualifies
    "goal",              # a target the company has set itself
    "kpi",               # a metric the company measures itself by
    "org_structure",     # teams, reporting lines, ownership
    "employee_profile",  # who someone is, what they own
    "project",           # a named body of work
    "task",              # a unit of work with an owner
    "asset",             # a resource the company holds (tools, licences, accounts)
    "wiki",              # internal reference prose that is none of the above
})

# Kinds that describe WORK IN FLIGHT, and can therefore anchor a business situation:
# other signals (a Slack thread, a commit, a meeting) legitimately group under them.
#
# Everything else is REFERENCE — knowledge to be consulted, not a situation to act on.
# A refund policy is true continuously; it is not something happening. Letting every
# policy, price list and wiki page open its own situation would bury the handful that
# need attention under a filing cabinet, which is the opposite of the point.
#
# `task` is deliberately NOT here yet. A task per situation would be one situation per
# to-do item, and nothing downstream is ready to rank at that granularity — it would
# swamp the same list. Add it when something consumes it.
ANCHORING_KINDS: frozenset[str] = frozenset({"project"})

# Deliberate company statement — outranks system-of-record (3) and extraction (2).
CANON_AUTHORITY_RANK: int = 4
# Everything else unstructured: grounded in an event we observed, not asserted by the org.
OBSERVED_AUTHORITY_RANK: int = 2

# Tolerant input → canonical kind. The upload `tag` field has always been free text, so
# these keep existing tags meaningful instead of silently demoting them to non-canon.
_ALIASES: dict[str, str] = {
    "policies": "policy", "sops": "sop", "process": "sop", "procedure": "sop",
    "runbook": "sop", "playbook": "sop",
    "products": "product", "product_info": "product", "productinfo": "product",
    "price": "pricing", "prices": "pricing", "pricelist": "pricing",
    "price_list": "pricing", "rate_card": "pricing",
    "goals": "goal", "okr": "goal", "okrs": "goal", "objective": "goal",
    "kpis": "kpi", "metric": "kpi", "metrics": "kpi",
    "org": "org_structure", "org_chart": "org_structure", "orgchart": "org_structure",
    "team": "org_structure", "teams": "org_structure", "structure": "org_structure",
    "employee": "employee_profile", "employees": "employee_profile",
    "people": "employee_profile", "profile": "employee_profile",
    "projects": "project", "tasks": "task",
    "assets": "asset", "resource": "asset", "resources": "asset",
    "wiki_page": "wiki", "handbook": "wiki", "docs": "wiki", "documentation": "wiki",
}


def normalize_kind(value: str | None) -> str | None:
    """Free text → a declared kind, or None when it is not company canon.

    None is the honest answer for an unrecognised tag: it stays an ordinary tagged
    document at observed authority. Guessing here would hand rank 4 to a typo.
    """
    if not value:
        return None
    key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if key in INTERNAL_KINDS:
        return key
    return _ALIASES.get(key)


def is_canon(kind: str | None) -> bool:
    """True when this event is the company deliberately stating something about itself."""
    return normalize_kind(kind) is not None


def authority_rank_for(kind: str | None) -> int:
    """The authority an event carries into the graph. L1 owns this: authority is a
    property of PROVENANCE, and provenance is what capture knows. L2 honours it rather
    than re-deriving it from the source name."""
    return CANON_AUTHORITY_RANK if is_canon(kind) else OBSERVED_AUTHORITY_RANK


def is_anchoring(kind: str | None) -> bool:
    """Can this kind of company knowledge be the SUBJECT of a business situation?

    True for work in flight (a project), false for standing reference (a policy). The
    distinction is not about importance — a pricing policy may matter more than any one
    project — it is about whether other signals should GROUP under it. Emails cluster
    around a project; they do not cluster around a refund policy.
    """
    return normalize_kind(kind) in ANCHORING_KINDS

"""L2 · Domain specs — the seam where Layer 3 will plug its expertise in.

WHY THIS EXISTS: a leak in Step 3 that had to be closed before domains multiply.

`situations.py` shipped with tables keyed on ("company", "sales") → "opportunity", and on
"deal" → {which fields a deal should have}. That is DOMAIN EXPERTISE, and it was sitting
in the Context layer. The architecture is explicit that the context layer holds what is
true and never what a domain means — and the practical cost is worse than the principle:
with the knowledge inlined, every new domain would require editing Layer 2, so adding
"engineering" or "legal" would mean touching the layer that must stay stable.

So the knowledge moves behind a registry, and Layer 2 stops knowing any domain by name.

THE PROPERTY THAT MATTERS: OPEN BY DEFAULT

An unregistered domain is not an error, not a gap, and not a special case. It gets a
generic spec and everything downstream works:

    situation type   → "<domain>_<anchor>" — visibly unmapped, never mislabelled as
                       something it is not
    expected fields  → none, so coverage is 100% ("we expect nothing, so nothing is
                       missing"), never 0% ("we know nothing")

That second one is the trap. A registry that returns "no expectations" as "nothing known"
would report every situation in a new domain as completely uncovered — absence read as
negative evidence, which this codebase refuses everywhere else. It would make every new
domain look broken on the day it was added.

The three domains registered below are the ones the shipped packs already assume. They
live here as DATA, not logic: Layer 3 will own them properly, and `register()` is how it
will take over without Layer 2 changing at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class DomainSpec:
    """Everything Layer 2 needs to know about one domain — which is deliberately little.

    No thresholds, no rules, no priorities. Those are decisions, and a decision made here
    would be a decision made twice, since Layer 4 already makes them.
    """

    domain: str
    display_name: str = ""
    # (anchor node type) → what an executive calls a situation about it. A missing entry
    # falls back to "<domain>_<anchor>", which stays visibly unmapped rather than being
    # filed as something it is not.
    situation_types: dict[str, str] = field(default_factory=dict)
    # situation type → {fact field: plain-language name of the gap}. Only fields something
    # in the system actually produces belong here; checking for fields nothing writes
    # yields a report that is always right and never useful.
    expected_fields: dict[str, dict[str, str]] = field(default_factory=dict)

    def type_for(self, anchor_type: str) -> str:
        return self.situation_types.get(anchor_type) or f"{self.domain}_{anchor_type}"

    def fields_for(self, situation_type: str) -> dict[str, str]:
        return self.expected_fields.get(situation_type, {})


def generic_spec(domain: str) -> DomainSpec:
    """The spec for a domain nobody has described yet. Fully functional, not degraded."""
    return DomainSpec(domain=domain, display_name=domain.replace("_", " ").title())


# Registered specs. A plain dict rather than a frozen constant precisely so Layer 3 can
# take ownership at import time without Layer 2 being edited.
_SPECS: dict[str, DomainSpec] = {}


def register(spec: DomainSpec, *, replace_existing: bool = True) -> DomainSpec:
    """Declare (or take over) a domain.

    Layer 3 calls this. Overwriting is allowed and is the point: the built-in specs below
    are placeholders that real domain expertise should replace, and a registry that
    refused would force Layer 2 to be edited to remove them first.
    """
    if not spec.domain:
        raise ValueError("a domain spec needs a domain name")
    if not replace_existing and spec.domain in _SPECS:
        return _SPECS[spec.domain]
    _SPECS[spec.domain] = spec
    return spec


def extend(domain: str, **changes) -> DomainSpec:
    """Adjust one registered domain without restating it. Convenience for L3."""
    return register(replace(spec_for(domain), **changes))


def spec_for(domain: str | None) -> DomainSpec:
    """The spec for a domain. NEVER raises and never returns None — an unknown domain is
    an ordinary case, and making callers handle a missing spec would push domain
    awareness back into every call site."""
    name = (domain or "").strip().lower() or "general"
    return _SPECS.get(name) or generic_spec(name)


def spec_version() -> str:
    """Content hash of the whole registry.

    `situation_type`, `coverage` and `missing` are all DERIVED from these specs and then
    PERSISTED to context_situations. So a registry change silently rewrites stored values
    on the next refresh, with nothing recording that the definition moved rather than the
    data. Two workers with different import order could even write different types for
    the same situation.

    Stamping this into each situation's `inputs` makes a re-typing attributable: the row
    says which registry produced it, and a diff in this hash explains a change that would
    otherwise look like the world changed. Same idea as the pack registry's effective
    snapshot, which every signal already carries.
    """
    from dataclasses import asdict

    from genios_engine.platform.canonical import stable_id
    return stable_id("dspec", {name: asdict(spec)
                               for name, spec in sorted(_SPECS.items())})


def registered_domains() -> tuple[str, ...]:
    """Domains someone has described. NOT the list of domains that exist — data can carry
    a domain nobody registered, and Layer 2 must keep working when it does."""
    return tuple(sorted(_SPECS))


def is_registered(domain: str | None) -> bool:
    return (domain or "").strip().lower() in _SPECS


# ── the specs the shipped packs already assume ───────────────────────────────────
#
# Data, not logic. Every field here is a statement about what a domain MEANS, which is
# Layer 3's business — these exist so behaviour is unchanged the day this file lands, and
# they are meant to be replaced by `register()` rather than edited.

register(DomainSpec(
    domain="sales",
    display_name="Sales",
    situation_types={"deal": "deal", "company": "opportunity",
                     "person": "prospect_relationship"},
    expected_fields={
        "deal": {"deal.stage": "pipeline stage", "deal.amount": "deal value",
                 "deal.close_date": "expected close date",
                 "commitment.due_at": "agreed next step"},
        "opportunity": {"thread.ball_in_court": "whose turn it is",
                        "commitment.due_at": "agreed next step"},
        "prospect_relationship": {"thread.ball_in_court": "whose turn it is"},
    }))

register(DomainSpec(
    domain="support",
    display_name="Customer Support",
    situation_types={"company": "support_case", "person": "support_contact"},
    expected_fields={
        "support_case": {"thread.ball_in_court": "whose turn it is"},
        "support_contact": {"thread.ball_in_court": "whose turn it is"},
    }))

register(DomainSpec(
    domain="admin",
    display_name="Admin & Finance",
    situation_types={"company": "account_admin"},
    expected_fields={
        "account_admin": {"subscription.current_period_end": "renewal date"},
    }))

register(DomainSpec(
    domain="fundraising",
    display_name="Fundraising & Investors",
    # An investor relationship is not a sales pipeline wearing different words. The counterparty
    # is not buying, there is no deal to close, and "rejected" is frequently reversible — an
    # accelerator that passes this cohort invites a re-application to the next one. Typing them
    # as `opportunity` made every one of this org's sixteen sales-domain situations a
    # non-customer: six VCs, three accelerator programmes, an introduction bot and the product's
    # own address. Zero were a customer, and the rules acting on them were written for buyers.
    situation_types={"company": "investor_relationship", "person": "investor_contact"},
    expected_fields={
        "investor_relationship": {
            "funding.round": "which round this is",
            "application_status": "where the application stands",
            "thread.ball_in_court": "whose turn it is",
        },
        "investor_contact": {
            "party.role": "what they are to us",
            "thread.ball_in_court": "whose turn it is",
        },
    }))

register(DomainSpec(
    domain="general",
    display_name="General",
    situation_types={"company": "relationship", "person": "relationship"},
    expected_fields={
        # A relationship is NOT context-complete because we know who sent the last email.
        #
        # This spec asked for one trivially-satisfied field — `thread.ball_in_court`, which
        # `pipeline.py` writes mechanically on every inbound message — so 34 of this org's 73
        # situations reported `missing=[]` and 100% coverage on the strength of knowing whose
        # turn it was. Nearly half the graph declared itself fully understood, and any acceptance
        # gate reading "no actionable output when required context is unknown" read green.
        #
        # The two fields below are the minimum that make a relationship reasonable about: WHO
        # they are to us, and WHAT is open. Neither is written mechanically, so `missing` starts
        # telling the truth.
        "relationship": {
            "thread.ball_in_court": "whose turn it is",
            "party.role": "what they are to us",
            "commitment.last_due_at": "what is open with them",
        },
    }))

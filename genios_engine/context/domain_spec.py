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


#: Two names for one domain. The LEFT side is a word a producer actually emits; the right is the
#: registered spec it denotes.
#:
#: `investor` is the model's own word — `_RELATIONSHIP_NATURES` in the L2 pipeline offers it, and
#: the model reasonably answers with it when a message is about a fund. The registry calls the
#: same domain `fundraising`. Nothing was wrong with either name; what was wrong is that they did
#: not meet. An unregistered domain gets the generic spec, which types a company-anchored
#: situation `<domain>_<anchor>` — so one of the design partner's situations was `investor_company`
#: rather than `investor_relationship`, and the authored investor-relations route could not see
#: it. Not a mislabel and not a gap: two vocabularies for one thing, which is exactly what an
#: alias is for. (Layer 3 has the mirror of this table in `capability_resolver.DOMAIN_ALIASES`,
#: mapping a corpus folder name to an L2 domain id.)
#:
#: An alias is deliberately NOT the same as `register()`ing the name: the canonical name is what
#: gets stored, so the correlation key, the situation type and the L3 domain hint all agree, and
#: a diff in `spec_version()` records the day they started agreeing.
_ALIASES: dict[str, str] = {
    "investor": "fundraising",
}


def canonical_domain(domain: str | None) -> str:
    """The registered name for a domain someone referred to by another of its names."""
    name = (domain or "").strip().lower() or "general"
    return _ALIASES.get(name, name)


def spec_for(domain: str | None) -> DomainSpec:
    """The spec for a domain. NEVER raises and never returns None — an unknown domain is
    an ordinary case, and making callers handle a missing spec would push domain
    awareness back into every call site."""
    name = canonical_domain(domain)
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
    return stable_id("dspec", {"specs": {name: asdict(spec)
                                        for name, spec in sorted(_SPECS.items())},
                               # An alias decides which spec a domain resolves to, so it changes
                               # the derived `situation_type` exactly as a spec edit does. Leaving
                               # it out of the hash would make a re-typing unattributable — the
                               # one thing this stamp exists to prevent.
                               "aliases": dict(sorted(_ALIASES.items()))})


def registered_domains() -> tuple[str, ...]:
    """Domains someone has described. NOT the list of domains that exist — data can carry
    a domain nobody registered, and Layer 2 must keep working when it does."""
    return tuple(sorted(_SPECS))


def domains_declaring(anchor_type: str) -> tuple[str, ...]:
    """Every registered domain that names a situation type for this anchor.

    THE OPT-IN SHAPE for any Layer 2 sweep that mints its own anchor node. `context/periodic.py`
    needed it first and listed its domains inline; `test_domain_names_appear_in_exactly_one_file_
    in_the_context_layer` rejected that, correctly — a domain named in Layer 2 means adding a
    domain requires editing Layer 2, and this registry exists precisely so it does not. Declaring
    the anchor here is now the whole opt-in, for the tenant period read and for the seven
    correspondence-derived support readings alike.

    Domains WITHOUT the anchor are skipped rather than defaulted. `type_for` would otherwise
    return its generic `<domain>_<anchor>`, which no situation file claims and the registry cannot
    resolve — the exact fault that kept `admin_person` and `fundraising_deal` dark, and it fails
    silently.
    """
    return tuple(sorted(d for d, spec in _SPECS.items()
                        if spec.situation_types.get(anchor_type)))


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
    # `tenant` is the PERIOD anchor. Twenty-two authored capabilities across the three domains ask
    # about a WINDOW rather than a subject — coverage, backlog, turnaround, team health — and none
    # could ever route, because `context_situations` anchors on a graph node and no node's facts are
    # "the whole queue this month". `context/periodic.py` mints a tenant node, writes the aggregates
    # onto it as ordinary facts, and anchors one situation per domain there, so the compile path
    # needs no new concept.
    #
    # The tenant node is deliberately NOT in `ANCHOR_PRIORITY`: `choose_anchors` returns only the
    # strongest tier present, so a tenant node reachable from correspondence would swallow every
    # conversation in the org into one situation.
    situation_types={"deal": "deal", "company": "opportunity",
                     "person": "prospect_relationship",
                     "tenant": "pipeline_period_review"},
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
    # `tenant` is the PERIOD anchor. Twenty-two authored capabilities across the three domains ask
    # about a WINDOW rather than a subject — coverage, backlog, turnaround, team health — and none
    # could ever route, because `context_situations` anchors on a graph node and no node's facts are
    # "the whole queue this month". `context/periodic.py` mints a tenant node, writes the aggregates
    # onto it as ordinary facts, and anchors one situation per domain there, so the compile path
    # needs no new concept.
    #
    # The tenant node is deliberately NOT in `ANCHOR_PRIORITY`: `choose_anchors` returns only the
    # strongest tier present, so a tenant node reachable from correspondence would swallow every
    # conversation in the org into one situation.
    #
    # THE SEVEN CORRESPONDENCE READINGS, minted by `context/support_situations.py`. Each gets its
    # OWN anchor node type because `type_for` is a map from anchor to type and two readings
    # sharing an anchor could not both be named. That constraint turned out to be the right
    # design: `queue-overloaded.yaml` asks for per-item aging with "the item as a first-class
    # subject", and `repeat-contact.yaml` says the finding "belongs to an INTENT" and that
    # person-scope "finds the evidence; it does not describe the finding". So a `backlog_item` is
    # one unmet ask, a `contact_intent` is one person and one topic, a `topic` is the topic
    # itself, and a `mailbox` is one connected mailbox — never called a queue, because there is
    # no queue object, no assignee and no rota anywhere in this system.
    #
    # None of these anchors is in `correlation.ANCHOR_PRIORITY`, for the same reason `tenant` is
    # not: `choose_anchors` returns only the strongest tier present, so a synthetic anchor
    # reachable from correspondence would swallow every conversation that touched it into one
    # situation. `thread` in particular must stay out — correlation is already thread-first, and a
    # thread tier would re-anchor every live sales and general correlation onto its own thread.
    situation_types={"company": "support_case", "person": "support_contact",
                     "tenant": "support_period_review",
                     "thread": "first_response_overdue",
                     "backlog_item": "ticket_aging",
                     "escalation": "escalation_requested",
                     "contact_intent": "repeat_contact",
                     "topic": "knowledge_gap",
                     "mailbox": "queue_overloaded",
                     "workaround": "workaround_only"},
    expected_fields={
        "support_case": {"thread.ball_in_court": "whose turn it is"},
        "support_contact": {"thread.ball_in_court": "whose turn it is"},
        # Every block below carries at least one field NOTHING writes, deliberately. A situation
        # whose `missing` empties out the moment its mechanical facts land is how 34 of one org's
        # 73 situations came to report full coverage on the strength of knowing whose turn it
        # was — and these seven are approximations over mail, so the gap between what they show
        # and what a helpdesk would show has to stay visible on every single row.
        "first_response_overdue": {
            "response.opened_at": "when the request arrived",
            "response.target_at": "the deadline your stated policy implies",
            # Absent by construction while this situation is open — that IS the situation — and
            # absent for a different reason once it closes.
            "response.first_reply_at": "when we actually replied",
            # No per-customer target exists anywhere in this system. Never satisfied, so the card
            # can never quietly become an SLA claim.
            "entitlement.plan": "what this customer is actually entitled to",
        },
        "ticket_aging": {
            "backlog.opened_at": "when the request first arrived",
            "backlog.waiting_on": "whose turn it is",
            "backlog.days_since_customer": "how long since they last wrote",
            # There is no queue and no assignee. Never satisfied.
            "backlog.queue": "which queue this belongs to and who owns it",
        },
        "escalation_requested": {
            "escalation.origin": "who raised it",
            # The two the corpus calls the act itself. Written only when a new internal name
            # appears on the thread, which is an inference and not an acceptance.
            "escalation.receiver_node_id": "who is taking it",
            "escalation.accepted_at": "when a named person accepted",
        },
        "repeat_contact": {
            "repeat.intent": "what they keep coming back about",
            "repeat.ordinal": "how many times",
            "repeat.prior_answered": "whether the earlier contact was answered",
            # Needs help-centre telemetry nobody has connected. Never satisfied.
            "repeat.self_service_seen": "whether they tried to find the answer themselves",
        },
        "knowledge_gap": {
            "knowledge.distinct_askers": "how many different people asked",
            "knowledge.answer_reuse_bp": "whether we already have a settled answer",
            # The corpus's actual discriminator — write the article, or fix findability. Never
            # satisfied, and commissioning a duplicate is the harm it warns about.
            "knowledge.published_answer_seen": "whether a published answer already exists",
        },
        "queue_overloaded": {
            "mailbox.flow_ratio": "arrivals against closures",
            "mailbox.backlog_oldest_days": "how long the oldest open item has waited",
            "mailbox.backlog_age_p90_days": "the shape of the wait at the tail",
            # An alert nobody owns is a dashboard. Never satisfied.
            "mailbox.owner": "who owns this workload",
        },
        "workaround_only": {
            "workaround.provided_at": "when we handed them the workaround",
            "workaround.cost": "what it costs them to keep doing it",
            # Needs an engineering tracker. Never satisfied, which is why the best card this can
            # produce is "say something", not "you can stop now".
            "workaround.fix_state": "whether the underlying fault is fixed",
        },
    }))

register(DomainSpec(
    domain="admin",
    display_name="Admin & Finance",
    # `person` maps to `admin_contact`, and it did not before.
    #
    # Only `company` was described, so a person-anchored admin situation fell through to
    # `type_for`'s `<domain>_<anchor>` default and became `admin_person` — a name no situation
    # file claims, that `_schema/vocabulary.yaml` does not list, and that the registry therefore
    # cannot resolve. It is the same fault the `general_deal` fix closed: the generic fallback is
    # for domains NOBODY has described, and describing a domain half way leaves half its
    # situations in a lane with no door. The design partner carries one of these today.
    #
    # `admin_contact`, not `admin_person`, deliberately: it is the same word the two other
    # person-anchored lanes already use (`support_contact`, `investor_contact`), and consistency
    # in this name is not cosmetic — it is what a corpus author reads to know the lane exists.
    # `tenant` is the PERIOD anchor. Twenty-two authored capabilities across the three domains ask
    # about a WINDOW rather than a subject — coverage, backlog, turnaround, team health — and none
    # could ever route, because `context_situations` anchors on a graph node and no node's facts are
    # "the whole queue this month". `context/periodic.py` mints a tenant node, writes the aggregates
    # onto it as ordinary facts, and anchors one situation per domain there, so the compile path
    # needs no new concept.
    #
    # The tenant node is deliberately NOT in `ANCHOR_PRIORITY`: `choose_anchors` returns only the
    # strongest tier present, so a tenant node reachable from correspondence would swallow every
    # conversation in the org into one situation.
    #
    # `document` is the RECORDS anchor, minted by `context/document_register.py` from the file
    # metadata `capture/connectors/drive.py` already fetched and used to discard. Five authored
    # capabilities — document_control, filing_and_retrieval, version_control,
    # retention_and_archival, knowledge_base_maintenance — were complete knowledge with no
    # trigger, because no node in the graph was a document.
    #
    # It is NOT in `ANCHOR_PRIORITY` and its title is not a canon alias, which are the same
    # refusal twice: `choose_anchors` returns only the strongest tier present, so a document
    # reachable from correspondence would take an email that merely mentions "Security Policy"
    # and anchor it on the policy instead of on the customer who wrote it.
    situation_types={"company": "account_admin", "person": "admin_contact",
                     "tenant": "admin_period_review",
                     "document": "document_under_control"},
    expected_fields={
        "account_admin": {"subscription.current_period_end": "renewal date"},
        # An administrative counterparty is read through what we owe them and whose turn it is,
        # not through a pipeline stage. Both fields have real writers.
        "admin_contact": {"thread.ball_in_court": "whose turn it is",
                          "commitment.due_at": "what we owe them, and when"},
        # TWO OF THESE FOUR HAVE NO WRITER AND ARE NOT MEANT TO GET ONE.
        #
        # `document.approved_at` is not a file-store concept: Drive keeps revisions, comments and
        # suggestion-accepts, and inferring an approval from a modification history is the exact
        # fabrication the corpus file forbids. `document.retention_until` needs a retention
        # schedule this tenant has never stated anywhere, so there is no clock and none can be
        # derived. Leaving them here is what keeps `missing` truthful on every single row — an
        # artefact renders as "approval state unknown", never as "unapproved", which would be a
        # finding the system invented. Records coverage claimed and absent is worse than absent,
        # because it is what somebody relies on in an audit.
        "document_under_control": {
            "document.owner_email": "who owns it",
            "document.version": "which revision the file store is on",
            "document.approved_at": "approval state",
            "document.retention_until": "when it must be destroyed",
        },
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
    # `deal` maps to `investor_relationship`, and it is NOT the same concession as typing an
    # investor as an `opportunity` — which is what the paragraph above is about.
    #
    # A `deal` node exists only because `deal.*` facts were extracted, and an investor thread
    # produces them freely: the extractor reads a VC pass as a lost deal. So a deal-anchored
    # fundraising correlation is real, and without a mapping it fell to `type_for`'s generic
    # `<domain>_<anchor>` default and became `fundraising_deal` — a name no situation file claims
    # and the registry cannot resolve. Four of the design partner's situations sat there.
    #
    # It resolves to `investor_relationship` rather than to `deal` deliberately. Both readings are
    # of the same fundraising conversation, so it stays in the investor lane where the corpus
    # knows nobody is buying — mapping it to `deal` would hand it to Sales situations that gate on
    # `deal.status = open` and reason about pipeline stages, which is the exact error this spec
    # was written to stop.
    situation_types={"company": "investor_relationship", "person": "investor_contact",
                     "deal": "investor_relationship"},
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
    # `deal` maps to `deal`, not to `general_deal`.
    #
    # `general` does not mean "a domain called general". It means no hint fired — which on real
    # correspondence is most of it: 23 of one tenant's 30 deal-anchored correlations. A deal node
    # exists only because `deal.*` facts were extracted from the message, so the anchor is a deal
    # whether or not the word "pipeline" appeared in the text. Falling through to `type_for`'s
    # `<domain>_<anchor>` default named it `general_deal`, which no situation file claims and the
    # registry cannot resolve — the entire deal lane unroutable on any tenant whose mail happens
    # not to trip a keyword.
    #
    # Company and person stay `relationship` deliberately. Those readings genuinely differ by
    # domain — an unclassified account is not an opportunity — but a deal is a deal.
    situation_types={"company": "relationship", "person": "relationship", "deal": "deal"},
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

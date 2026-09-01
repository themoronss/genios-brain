"""The Layer 2 → Layer 3 routing contract: can the corpus be reached at all?

Layer 3's route index is keyed on `situation.type`, and `capability_resolver.py:63` looks it up
with `domain.routes.get(situation.type)`. That value does not come from anywhere in the corpus —
it comes from `context/situations.py::situation_type()`, which can only ever emit one of the
seven strings registered in `context/domain_spec.py`. If the two vocabularies do not intersect,
every situation abstains and NO amount of authoring changes it.

For months they did not intersect. The corpus was keyed on Layer 3 PACK SIGNAL REASON CODES
(`buying_signal`, `stalled_deal`, `champion_quiet`, …) which Layer 2 never produces, so a live run
against the design partner's 73 situations returned 73/73 `NoExpertiseRoute` — a 100% miss, in a
subsystem every dashboard reported as healthy.

Nobody caught it because of two blind spots, both closed here:

  * the corpus validator sourced its "L2 census" from `_schema/vocabulary.yaml`, whose own comment
    said it was the *"union of both packs' schema.signal_vocab"* — so `0 errors` certified nothing
    about routability. That list is now generated from `context/domain_spec.py` instead;
  * every compiler test hand-built `type="buying_signal"`, a value production cannot emit, so
    green CI actively certified the bug. Those fixtures now source their type from the registry.

This module is the standing oracle. It passes today (live routing is 72/73), and its job from
here is to fail the moment either side of the contract drifts again.
"""
from __future__ import annotations

import pytest

from genios_engine.context.domain_spec import registered_domains, spec_for
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root


def producible_situation_types() -> set[str]:
    """Every value `context/situations.py` can put on a BusinessSituationObject.

    This is the whole universe Layer 3 may key its routes on. It is small on purpose: a closed
    vocabulary is what makes routing decidable instead of a string-matching accident.
    """
    out: set[str] = set()
    for domain in registered_domains():
        out.update(spec_for(domain).situation_types.values())
    return out


def _catalog() -> ExpertBrainCatalog:
    root = default_authoring_root()
    if not root.is_dir():
        pytest.skip(f"authored corpus not present at {root}")
    return ExpertBrainCatalog(root)


def test_producible_vocabulary_is_small_and_closed():
    """Guard the oracle itself: if this set silently grew, the contract below means less."""
    types = producible_situation_types()
    assert types == {
        "deal", "opportunity", "prospect_relationship",
        "support_case", "support_contact",
        # `admin_contact` joined `account_admin`: only the company anchor was described, so a
        # person-anchored admin situation fell to `type_for`'s generic `<domain>_<anchor>` default
        # and became `admin_person` — a value this set never contained, that no situation file
        # claims, and that therefore routed nothing. Growing this set is exactly the event the
        # test exists to force someone to look at; it is checked against the corpus by
        # `test_every_producible_type_someone_authored_for` below.
        "account_admin", "admin_contact",
        "investor_relationship", "investor_contact",     # fundraising (L2-05)
        "relationship",
        # The one NON-MAIL channel the graph records rather than infers: a calendar meeting with an
        # external counterparty, minted per meeting by `context/meeting_touch.py`. It is a third of
        # its authored type on purpose — `demo` is a meeting and is now reachable, while
        # `cold_calling` and `linkedin_outreach` are not, because a dialled number and a LinkedIn
        # message appear in no calendar. Every row says so in `missing` and `inputs.not_served`,
        # which is what keeps a partial view from being read as a whole one.
        "channel_touch",
        # The three PERIOD types, and they are a different SHAPE from everything above rather than
        # three more subjects. Every other value here names a thing a situation is about — a deal,
        # a person, an account. These name a WINDOW, anchored on the tenant node
        # `context/periodic.py` mints, carrying counts and their previous-window twins.
        #
        # Twenty-three authored capabilities asked about a window and none could route, because
        # `context_situations` anchors on a graph node and no node's facts are "the whole queue
        # this month". Writing the aggregates onto a tenant node as ordinary facts is what let the
        # existing compile path read them without learning a second situation shape.
        #
        # A domain opts in by declaring `"tenant": "<domain>_period_review"` in `domain_spec`; the
        # set below therefore grows by one per opting-in domain and is still closed.
        "pipeline_period_review", "admin_period_review", "support_period_review",
        # The seven CORRESPONDENCE readings, minted by `context/support_situations.py`. A third
        # shape again: the period types name a window and the rest name a subject, while these
        # name an APPROXIMATION — a service-desk reading of a mailbox on a tenant that has no
        # helpdesk, no ticket table, no queue, no assignee and no SLA clock.
        #
        # That is why they are listed with their anchors rather than as seven more strings. Each
        # declares its OWN anchor node type, because `type_for` maps one anchor to one type and
        # two readings sharing an anchor could not both be named — and the constraint matched
        # what the corpus already wanted: per-item aging "needs the item to be a first-class
        # subject", and a content gap "belongs to an INTENT" rather than to whoever reported it.
        #
        # If this set grows again, the thing to check is not the count. It is that every new type
        # caps its `coverage` and names what it cannot see in `missing` on every row — because
        # the failure these seven were built against is a card labelled "SLA Breach Imminent" on
        # an org with no SLAs, which is worse than a gap since it reports coverage that does not
        # exist.
        "first_response_overdue",    # anchored on the thread a request arrived in
        "ticket_aging",              # anchored on one unmet ask (`backlog_item`)
        "escalation_requested",      # anchored on the raise (`escalation`)
        "repeat_contact",            # anchored on one person and one topic (`contact_intent`)
        "knowledge_gap",             # anchored on the topic itself (`topic`)
        "queue_overloaded",          # anchored on one connected mailbox (`mailbox`)
        "workaround_only",           # anchored on the workaround a customer lives on
        # The RECORDS reading, minted by `context/document_register.py` on a `document` node.
        # A fourth shape: not a subject, not a window, not a service-desk approximation, but a
        # CONTROL GAP on one file — and the distinction is the whole design. It opens a situation
        # only where an owner is unverified, two copies are live, a governance artefact has gone a
        # year without an edit, or nobody is attached to it at all. One per file would be a Drive
        # listing wearing a situation's clothes, which the situation file rules out in five words:
        # "the headline is the gap, not the document."
        #
        # The same test applies as to the seven above, and it applies harder here because records
        # is the domain where claimed-and-absent coverage is what somebody relies on in an audit:
        # two of the four failures this type exists to catch — missing approval and past its
        # retention date — cannot be read from a file store at all, so they stay in `missing` on
        # every row and are never inferred from a modification history.
        "document_under_control",    # admin, anchored on one file (`document`)
        # A FIFTH SHAPE, and the first that names what is HAPPENING rather than what it is about.
        # Everything above answers WHO or WHICH WINDOW; a capability written for "we wrote and
        # nobody answered" had nothing to bind to, so it fell to a person-shaped lane whose only
        # available predicate was `thread.ball_in_court` — which is why every waiting relationship
        # in an org reached the same route and produced the same card.
        #
        # All three are minted from evidence that already existed. `context/waiting.py` derives
        # the durations, the follow-up count and the counterparty's own reply cadence — the first
        # facts in this system computed from what did NOT happen, since no source system emits
        # "they have not replied". `context/outreach_situations.py` gives two of them a name;
        # `meeting_follow_through` is a second reading of the `meeting` anchor sales already reads
        # as `channel_touch`, which `type_for` allows because it maps an anchor PER DOMAIN.
        #
        # If this set grows again the check is the same one the seven support readings answer to:
        # every new type must declare in `expected_fields` the thing it cannot see, so `missing`
        # stays truthful on every row. All three do — `outreach.objective` (nothing knows what an
        # outbound was FOR), `commitment.delivered_at` (nothing reports a promise was kept), and
        # `meeting.recap_sent` (an outbound after a meeting is not evidence it recapped it).
        "awaiting_response",         # admin, anchored on the `outreach` node
        "commitment_overdue",        # admin, anchored on the `commitment` node
        "meeting_follow_through",    # admin, a second reading of the `meeting` anchor
        # A SIXTH SHAPE, and the first whose subject is a GROUP rather than a thing. Every value
        # above names one person, one promise, one meeting, one file or one window; this names
        # everyone contacted with the same stated OBJECTIVE, which is the only shape that can
        # answer "of everyone I wrote to about the raise, who has gone quiet?".
        #
        # Keyed on the objective and NOT the organisation, deliberately: two partners at two
        # firms are one raise, while a fundraising thread and a vendor thread with the same firm
        # are two things needing opposite answers. It could not have existed before
        # `thread.objective` had a writer.
        #
        # Same check as the readings above — it declares what it cannot see. `cohort.target` (how
        # many we MEANT to reach) has no writer and probably never will, so the reply rate is
        # reported and never graded.
        "cohort_outreach_gap",       # admin, anchored on the `cohort` node
    }, "the L2 situation vocabulary changed — re-check every corpus route against it"


def test_every_corpus_route_is_reachable_from_layer_2():
    """No route may be keyed on a `situation.type` Layer 2 cannot emit.

    A route the producer can never satisfy is not a gap in coverage — it is a capability that is
    invisible to the system that owns it, and it reports as healthy in every count.
    """
    producible = producible_situation_types()
    unreachable: list[str] = []
    for domain_id, record in _catalog().domains.items():
        for route_key in getattr(record, "routes", {}) or {}:
            if route_key not in producible:
                unreachable.append(f"{domain_id}/{route_key}")

    assert not unreachable, (
        f"{len(unreachable)} corpus route(s) keyed on a situation type Layer 2 cannot emit:\n  "
        + "\n  ".join(sorted(unreachable))
        + f"\nProducible types are: {sorted(producible)}")


def test_corpus_domain_ids_match_registered_l2_domains():
    """The domain NAME must match too, or the route lookup never even begins.

    Layer 2 resolves `general` for 53 of the design partner's 73 situations and `support` for
    most of the rest; the catalog knows `sales`, `customer_support` and `admin`. 56 of 73 die on
    the domain string alone, before any situation type is compared.
    """
    from genios_engine.packs.compiler.capability_resolver import (
        DOMAIN_ALIASES, UNCLASSIFIED_DOMAINS)

    corpus_domains = set(_catalog().domains)
    # Resolve L2's ids the way the resolver does: through the alias table, and ignoring the
    # ids that mean 'unclassified' rather than naming a domain.
    l2_domains = {DOMAIN_ALIASES.get(d, d) for d in registered_domains()
                  if d not in UNCLASSIFIED_DOMAINS}
    unmatched = sorted(corpus_domains - l2_domains)
    assert not unmatched, (
        f"corpus domain(s) with no registered L2 domain: {unmatched}. "
        f"L2 emits one of {sorted(l2_domains)}; a compile keyed on any other name cannot resolve.")

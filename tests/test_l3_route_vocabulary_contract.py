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
        "account_admin",
        "investor_relationship", "investor_contact",     # fundraising (L2-05)
        "relationship",
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

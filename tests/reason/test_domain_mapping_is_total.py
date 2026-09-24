"""L2-4-U2 · every Layer 2 domain has a row, and a row may be `None` only with a reason.

⛔ **THE GUARD THAT WOULD HAVE CAUGHT `support` → `customer_support` BEFORE 33 SITUATIONS DIED.**
`domain_shadow`'s own comment:

    `variants_by_domain` is built from `live_domains`, which are corpus ids (`customer_support`);
    `row["domain"]` is Layer 2's (`support`). … it silently returned `()` for every support
    situation on the tenant — 33 of them — so that corpus could never receive an overlay however
    it was declared. `admin` and `sales` spell the same on both sides, WHICH IS WHY THE MISS WAS
    INVISIBLE.

⛔ **AND THREE PLACES NOW STATE ONE FACT, WITH NOTHING BINDING THEM.** Measured 2026-09-24:

    context/domain_spec.registered_domains()   admin · fundraising · general · sales · support
    reason/domain_shadow._L2_TO_L3_DOMAIN      admin · sales · support · customer_support
    context/domain_silence.DARK_DOMAINS        fundraising · general          (added by L2-0)

`fundraising` and `general` are dark in all three readings **and they agree by coincidence**.
Nothing fails if one of them changes. That is the drift this repository has caught five times, and
this file is what ends it here: **the map's silence must BE `DARK_DOMAINS`, not merely match it.**
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_every_registered_l2_domain_has_a_row():
    """⛔ ABSENT AND DECLARED-DARK ARE DIFFERENT FACTS. `.get()` answers `None` for both, so a
    domain somebody forgot and a domain somebody decided about are indistinguishable at the call
    site — which is exactly how `support` went missing."""
    from genios_engine.context.domain_spec import registered_domains
    from genios_engine.reason.domain_shadow import _L2_TO_L3_DOMAIN

    missing = set(registered_domains()) - set(_L2_TO_L3_DOMAIN)
    assert not missing, (
        f"{sorted(missing)} are registered Layer 2 domains with no row in _L2_TO_L3_DOMAIN. "
        f"Give each one a row — `None` is a valid answer and an absent key is not.")


def test_the_maps_silence_is_exactly_the_declared_darkness():
    """⛔ Three places said one fact and agreed by coincidence. Now one binds the others."""
    from genios_engine.context.domain_silence import DARK_DOMAINS
    from genios_engine.context.domain_spec import registered_domains
    from genios_engine.reason.domain_shadow import _L2_TO_L3_DOMAIN

    unrouted = {d for d in registered_domains() if _L2_TO_L3_DOMAIN.get(d) is None}
    assert unrouted == set(DARK_DOMAINS), (
        f"the routing map says {sorted(unrouted)} is dark and `DARK_DOMAINS` says "
        f"{sorted(DARK_DOMAINS)}. Two answers to one question")


def test_a_row_that_is_not_an_l2_domain_is_declared_as_an_alias():
    """`customer_support` is a KEY in the map and is not a registered Layer 2 domain — it is the
    corpus id, accepted defensively so a caller that already translated is not punished. Real, and
    it must be stated rather than noticed."""
    from genios_engine.context.domain_spec import registered_domains
    from genios_engine.reason.domain_shadow import CORPUS_ID_ALIASES, _L2_TO_L3_DOMAIN

    strangers = set(_L2_TO_L3_DOMAIN) - set(registered_domains())
    assert strangers == set(CORPUS_ID_ALIASES), (
        f"{sorted(strangers - set(CORPUS_ID_ALIASES))} are keys that are not Layer 2 domains and "
        f"are not declared aliases")
    for alias, why in CORPUS_ID_ALIASES.items():
        assert why, f"{alias} is accepted as a key and nothing says why"


def test_every_dark_domain_says_what_would_end_it():
    """A dark domain with no mover is a dark domain forever. L2-0 built the declaration; this
    binds the routing map to it."""
    from genios_engine.context.domain_silence import DARK_DOMAINS, reason_for

    for domain in DARK_DOMAINS:
        assert "ENDS WHEN" in (reason_for(domain) or ""), domain


def test_a_mapped_domain_points_at_a_corpus_that_exists():
    """⛔ The OTHER direction of the 33-situation defect: a row that points at a corpus id nobody
    authored would route to a package that can never be built, and `admin`/`sales` spelling the
    same on both sides is precisely why nobody would notice."""
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
    from genios_engine.reason.domain_shadow import _L2_TO_L3_DOMAIN

    authored = set(ExpertBrainCatalog("Domain Expertise").domains)
    pointed = {corpus for corpus in _L2_TO_L3_DOMAIN.values() if corpus is not None}
    assert pointed <= authored, (
        f"{sorted(pointed - authored)} is routed to and no corpus by that id is authored")

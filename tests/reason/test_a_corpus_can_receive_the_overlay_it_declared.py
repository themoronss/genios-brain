"""One corpus could never receive a variant overlay, and the miss spelled itself invisible.

    pytest tests/reason/test_a_corpus_can_receive_the_overlay_it_declared.py -q

`domain_shadow` builds its overlay table from the tenant's ACTIVATED corpora:

    variants_by_domain = {d: declared_variants(engine, org, d) for d in live_domains}

`live_domains` are corpus ids — `admin`, `customer_support`, `sales`. It then looked one up with
`row["domain"]`, which is LAYER 2's domain — `admin`, `support`, `sales`, `fundraising`. Two of
the three spell the same on both sides, so the lookup worked for `admin` and `sales` and returned
`()` for every `support` situation on the tenant — 33 of them — whatever that corpus declared.

This is the seam `l3_domain_for` exists to bridge, and it was already computed six lines above the
lookup that did not use it. A `.get(..., ())` cannot fail loudly: an overlay nobody receives looks
exactly like an overlay nobody declared.

WHY IT MATTERS BEYOND THE COUNT. The variant axes are how one corpus becomes many — `models/`
(go-to-market motion), `verticals/` (industry), `offerings/`. They are the mechanism by which an
AI agency and a SaaS company stop reading identical doctrine. A corpus that cannot receive one is
a corpus permanently stuck on the canonical text.
"""
from __future__ import annotations

import pytest

from genios_engine.platform.l3_activation import L3_DOMAINS
from genios_engine.reason.domain_shadow import l3_domain_for

pytestmark = pytest.mark.unit


def test_layer_twos_name_for_support_is_not_the_corpus_name() -> None:
    """The fact that made the miss possible, pinned so nobody 'simplifies' the bridge away."""
    assert l3_domain_for("support") == "customer_support"
    assert "support" not in L3_DOMAINS
    assert "customer_support" in L3_DOMAINS


def test_the_two_that_spell_the_same_are_why_it_stayed_invisible() -> None:
    """`admin` and `sales` round-trip, so two thirds of the lookups worked and nothing failed."""
    assert l3_domain_for("admin") == "admin"
    assert l3_domain_for("sales") == "sales"


@pytest.mark.parametrize("l2_domain", ["admin", "support", "sales"])
def test_every_activated_corpus_can_be_looked_up_from_a_layer_two_domain(l2_domain: str) -> None:
    """The property the fix restores: a table keyed by corpus id must be reachable from the
    situation's own domain, for EVERY activated corpus and not only the ones that spell alike."""
    table = {d: (f"{d}.variant.example",) for d in L3_DOMAINS}
    assert table.get(l3_domain_for(l2_domain) or "", ()) != (), (
        f"{l2_domain!r} cannot reach its corpus's overlay table")


def test_an_unactivatable_domain_still_gets_nothing() -> None:
    """The direction that must not change. `fundraising` maps to no corpus, so it has no overlay
    to receive — and the lookup must return empty rather than raise or borrow another's."""
    table = {d: (f"{d}.variant.example",) for d in L3_DOMAINS}
    assert l3_domain_for("fundraising") is None
    assert table.get(l3_domain_for("fundraising") or "", ()) == ()


def test_the_lookup_in_the_pass_uses_the_bridged_name() -> None:
    """Read from the source, so a future edit that re-introduces `row["domain"]` fails here."""
    import inspect

    from genios_engine.reason import domain_shadow
    source = inspect.getsource(domain_shadow.shadow_compile)
    assert "variant_ids=variants_by_domain.get(row_domain" in source, (
        "the overlay lookup is not keyed by the corpus domain")

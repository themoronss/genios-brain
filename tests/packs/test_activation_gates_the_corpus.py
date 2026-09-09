"""M3.C1 · a tenant compiles expertise only from corpora it switched on.

    pytest tests/packs/test_activation_gates_the_corpus.py -q

`l3_activation(org_id, domain)` is the table an operator uses to say which expertise a tenant
runs. The publisher honoured it. The admission gate honoured it. `domain_shadow` even carries a
comment saying "a single compiler cannot serve a tenant that has Admin activated and Sales not."

THE CAPABILITY ROUTE DID NOT. With no domain hint the resolver considered
`self.catalog.domains.keys()` — everything authored — and with hints it took them whole.

MEASURED ON THE PILOT, whose only activated domain is `admin`:

  * `relationship` situations routed to `["admin", "customer_support", "sales"]`
  * the four capabilities compiled into the most packages were ALL `customer_support`
    (150, 144, 144, 144 packages), on a founder's inbox with no support desk
  * then eight `sales.post_sale_and_growth.*` at 79 each — upsell, cross-sell, churn prevention,
    renewal, onboarding, expansion — on a fundraising inbox with no customers
  * only two `admin.*` capabilities appeared at all

And that is where Layer 4's ballot came from: 270 of 512 candidates were sales plays holding the
top of the utility table, because L4's plays come from the capabilities compiled here.

`None` MEANS UNFILTERED, and the last block below is why that matters: the measurement compiler
has to keep reporting what a tenant WOULD get from a corpus it has not switched on, or route
coverage becomes unmeasurable for exactly the domains an operator is deciding about.
"""

from __future__ import annotations

import pytest

from genios_engine.packs.compiler.capability_resolver import CapabilityResolver, NoExpertiseRoute

pytestmark = pytest.mark.unit


class Situation:
    """The fields the route resolver and its context adapter actually read. A real
    `BusinessSituationObject` would work too; this keeps the fixture to the surface under test."""

    org_id = "org_pilot"
    visibility = {"scope": "org"}
    metadata: dict = {}

    def __init__(self, situation_id: str, type_: str, hints: tuple[str, ...] = ()) -> None:
        self.id = situation_id
        self.type = type_
        self.domain_hints = hints


def resolver_for(catalog, activated=None) -> CapabilityResolver:
    return CapabilityResolver(catalog, require_admission=False, activated_domains=activated)


# =============================================================================================
# The constructor argument, and the shape it borrows.
# =============================================================================================
def test_the_default_is_unfiltered():
    """A resolver built the old way behaves the old way. Every offline caller — the corpus
    tests, the authoring checks — keeps working untouched."""
    from genios_engine.packs.domain_wiring import expert_catalog

    assert CapabilityResolver(expert_catalog()).activated_domains is None


def test_activation_is_a_constructor_argument_not_a_per_call_flag():
    """It follows `require_admission`'s shape deliberately: nothing may quietly widen ONE
    situation's reach, because a compiler serves a tenant and a tenant has one answer."""
    from genios_engine.packs.domain_wiring import expert_catalog

    r = CapabilityResolver(expert_catalog(), activated_domains=frozenset({"admin"}))

    assert r.activated_domains == frozenset({"admin"})
    assert "activated_domains" not in CapabilityResolver.resolve.__code__.co_varnames


# =============================================================================================
# The narrowing, against the real authored catalog.
# =============================================================================================
@pytest.fixture(scope="module")
def catalog():
    from genios_engine.packs.domain_wiring import expert_catalog

    return expert_catalog()


def test_the_pilots_activation_is_a_real_subset_of_what_is_authored(catalog):
    """The premise, stated as a fact about the tree rather than an assumption: there is more
    authored than `admin`, so the filter has something to do."""
    authored = set(catalog.domains)

    assert "admin" in authored
    assert authored - {"admin"}, "nothing to narrow means this unit would be decorative"
    assert {"sales", "customer_support"} & authored


def test_an_unactivated_domain_is_refused_with_a_message_that_names_the_table(catalog):
    """The operator has to be able to tell "nobody authored a route for this" from "this tenant
    has not switched that corpus on" — they are fixed in different places."""

    situation = Situation("sit_x", "no_such_situation_type_anywhere", ("sales",))

    with pytest.raises(NoExpertiseRoute) as caught:
        resolver_for(catalog, frozenset({"admin"})).resolve(situation)

    message = str(caught.value)
    assert "activated" in message
    assert "l3_activation" in message


def test_an_empty_activation_set_refuses_everything(catalog):
    """`frozenset()` is a tenant that has switched nothing on, and it is NOT the same as `None`.
    Collapsing the two would make "activated nothing" mean "activated everything", which is the
    failure direction that matters."""

    with pytest.raises(NoExpertiseRoute):
        resolver_for(catalog, frozenset()).resolve(Situation("sit_y", "awaiting_response"))


def test_none_still_considers_the_whole_catalog(catalog):
    """THE MEASUREMENT LANE. `domain_shadow` builds two compilers and only the LIVE one is
    filtered — the shadow one must keep reporting what a tenant would get from a corpus it has
    not activated, or route coverage is unmeasurable for the domains an operator is deciding
    about. This asserts the unfiltered path reaches a different answer from the filtered one."""

    situation = Situation("sit_z", "no_such_situation_type_anywhere", ("sales",))

    with pytest.raises(NoExpertiseRoute) as loose:
        resolver_for(catalog, None).resolve(situation)
    with pytest.raises(NoExpertiseRoute) as tight:
        resolver_for(catalog, frozenset({"admin"})).resolve(situation)

    assert "activated" not in str(loose.value), "the unfiltered lane never mentions activation"
    assert "activated" in str(tight.value)


# =============================================================================================
# Wiring.
# =============================================================================================
def test_the_domain_compiler_passes_it_down():
    from genios_engine.packs.compiler.domain_compiler import DomainCompiler
    from genios_engine.packs.domain_wiring import expert_catalog

    class _NoBrains:
        def snapshot(self, **_):
            raise AssertionError("not reached")

    compiler = DomainCompiler(catalog=expert_catalog(), runtime_brains=_NoBrains(),
                              activated_domains=frozenset({"admin"}))

    assert compiler.capability_resolver.activated_domains == frozenset({"admin"})


def test_an_explicit_resolver_is_never_overridden():
    """A caller who built their own resolver chose its policy. The compiler must not second-guess
    it, or a measurement resolver handed to a live compiler would silently become fail-closed."""
    from genios_engine.packs.compiler.domain_compiler import DomainCompiler
    from genios_engine.packs.domain_wiring import expert_catalog

    class _NoBrains:
        def snapshot(self, **_):
            raise AssertionError("not reached")

    mine = CapabilityResolver(expert_catalog(), activated_domains=None)
    compiler = DomainCompiler(catalog=expert_catalog(), runtime_brains=_NoBrains(),
                              capability_resolver=mine,
                              activated_domains=frozenset({"admin"}))

    assert compiler.capability_resolver is mine
    assert compiler.capability_resolver.activated_domains is None

"""L2-4 · ⛔ the fundraising doctrine EXISTS, authored and approved, and nothing can reach it.

**THE STEP FILE'S PREMISE IS OUT OF DATE, AND SO IS THE COMMENT IT QUOTES.**

    step-04 §1:  "they die one layer later because no fundraising corpus exists — `Domain
                  Expertise/` holds Admin, Sales and Customer Support and nothing else"
    the map:     "`fundraising` and `general` map to NOTHING and that is not an oversight: NO
                  CORPUS WAS AUTHORED FOR THEM"

Measured 2026-09-24 against the catalog:

    sales.sit.live_investor_relationship     status=stable  review=approved
        "An ongoing relationship with a party that might fund us, read at the ACCOUNT level:
         the fund, the accelerator, the syndicate"
    sales.sit.live_investor_contact          status=stable  review=approved
    sales.investor_relations.investor_relations
        "Reading and running the relationships with the people who might fund the company:
         funds, accelerators, angels and the operators who introduce them."

**The investor doctrine was authored — inside the Sales corpus — and `_L2_TO_L3_DOMAIN` sends
`fundraising` to `None`, so the pilot tenant's dominant domain can never reach it.**

⛔ **AND THE OBJECTION THE COMMENT RAISES DOES NOT APPLY TO `sales`.** *"Mapping them onto `admin`
to get some coverage would put Admin doctrine on a fundraising situation"* — true, and routing is
**per situation type**, not a domain blanket. Every type `fundraising` can mint lands on
investor-named doctrine and nothing else. This file proves that, and keeps proving it.

⛔ **`general` IS A DIFFERENT PROBLEM WITH THE SAME WORDS.** Its `relationship` type is claimed by
**all three** corpora, so a route is a CHOICE nobody has made. `general` is dark from ambiguity;
`fundraising` is dark from a stale sentence. One code comment said "no corpus was authored" for
both.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def catalog():
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog

    return ExpertBrainCatalog("Domain Expertise")


def test_the_investor_doctrine_exists_and_is_admitted(catalog):
    """If this ever goes red, the candidate route below must go with it."""
    from genios_engine.packs.compiler.capability_resolver import situation_admission_reason

    sales = catalog.domains["sales"]
    for sid in ("sales.sit.live_investor_relationship", "sales.sit.live_investor_contact"):
        doc = sales.situations.get(sid)
        assert doc is not None, f"{sid} is gone; the fundraising candidate route rests on it"
        assert situation_admission_reason(doc.content) is None, (
            f"{sid} is no longer admissible, so a card built from it could not instruct")


def test_every_fundraising_type_would_land_on_investor_doctrine_only(catalog):
    """⛔ **THE SAFETY PROPERTY, AND THE WHOLE ARGUMENT.** The map's objection is that borrowing a
    corpus puts the wrong doctrine on a situation. It cannot happen here, and this is why."""
    from genios_engine.context.domain_spec import spec_for
    from genios_engine.reason.domain_shadow import CANDIDATE_ROUTES

    sales = catalog.domains["sales"]
    for situation_type in set(spec_for("fundraising").situation_types.values()):
        route = sales.routes.get(situation_type)
        assert route, f"sales claims no route for {situation_type}"
        situations = tuple(route.get("situations") or ())
        assert situations, f"{situation_type} routes to no situation"
        assert all("investor" in s for s in situations), (
            f"{situation_type} would reach {situations} — generic sales doctrine on a "
            f"fundraising situation is the defect that made six VCs into sales opportunities")
    assert CANDIDATE_ROUTES["fundraising"].corpus == "sales"


def test_the_candidate_route_carries_its_evidence_and_is_not_armed():
    """⛔ DECLARED, COUNTED, AND ONE LINE FROM LIVE — the same shape as L2-2's OBSERVE laws.

    Arming it makes every fundraising situation activatable at once, and nobody has counted them
    on the pilot. A route that flips itself on a measurement nobody took is how a cutover looks
    like a breakage.
    """
    from genios_engine.reason.domain_shadow import CANDIDATE_ROUTES, _L2_TO_L3_DOMAIN

    candidate = CANDIDATE_ROUTES["fundraising"]
    assert candidate.evidence, "a candidate route with no evidence is a guess"
    assert "ENDS WHEN" in candidate.evidence
    assert _L2_TO_L3_DOMAIN["fundraising"] is None, (
        "the candidate route was armed without the pilot count — see the findings")


def test_general_is_dark_for_ambiguity_and_says_so(catalog):
    """⛔ Two domains, one sentence, two different problems. `general:relationship` is claimed by
    all three corpora, so routing it is a CHOICE — not a missing corpus and not a stale comment."""
    from genios_engine.context.domain_silence import reason_for
    from genios_engine.context.domain_spec import spec_for
    from genios_engine.reason.domain_shadow import CANDIDATE_ROUTES

    claimants = {d for d, rec in catalog.domains.items()
                 if "relationship" in rec.routes}
    assert len(claimants) > 1, "general stopped being ambiguous; its declaration needs rewriting"
    assert "general" not in CANDIDATE_ROUTES, (
        "a candidate route for `general` would be picking one of three corpora by hand")
    why = reason_for("general") or ""
    assert "ambiguous" in why.lower() or "three" in why.lower(), (
        "`general`'s declaration still reads as 'no corpus exists', which is the fundraising "
        "sentence and is not this domain's problem")


def test_a_candidate_route_must_name_a_corpus_that_exists(catalog):
    from genios_engine.reason.domain_shadow import CANDIDATE_ROUTES

    for domain, candidate in CANDIDATE_ROUTES.items():
        assert candidate.corpus in catalog.domains, (
            f"{domain} proposes {candidate.corpus}, which is not an authored corpus")

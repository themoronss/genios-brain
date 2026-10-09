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

⛔ **2026-10-09 — THE FUNDRAISING HALF ENDED** (STEP-11, `06` D2, M30.C1.L-logic.V1.U02). The doctrine
moved out of Sales into the Founder Office corpus, `_L2_TO_L3_DOMAIN` maps `fundraising` there, and
the candidate route is retired with its reason. Its three tests here — the Sales doctrine is admitted,
every fundraising type would land on it, the route is not armed — were about a route that no longer
exists, and are replaced by `tests/reason/test_fundraising_is_founder_work.py`, which holds the same
safety property against the Founder Office. `general` is still dark, for its own reason, below.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def catalog():
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog

    return ExpertBrainCatalog("Domain Expertise")


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

"""L1.6.6-U1 · domain tagging — the never-filter rule, and the ordering rule inside `hints.py`.

    pytest tests/capture/esqe/test_domain.py -q

The plan's acceptance is two sentences and both are about what is NOT lost:

* a signal in an uncovered domain is published with a degraded flag, **not dropped**;
* a multi-domain signal **retains every tag**.

The unit is marked "exists, one rule to preserve", so the tests below are written against a
resolver this file must not have rewritten. Two rules are under guard here and they are
different rules:

1. **The plan's rule — never filter.** Dropping a signal whose domain is not yet covered breaks
   cross-domain correlation *permanently*: there is no backfill for a signal that was never
   stored, so the correlation is lost even after the domain becomes covered.
2. **The rule that lives inside `capture/domain/hints.py` — `fundraising` is tested before
   `sales`.** Its own comment records the cost of losing it: an investor thread says "deck",
   "round" and "diligence" and also says "budget" and "contract", and letting the generic sales
   vocabulary claim it is how six VCs and three accelerator programmes became sales
   opportunities in one org's graph — not one of its sixteen sales situations was a customer.
   `context/correlation.resolve_domain` reads the tag list POSITIONALLY, so a sort, a set or a
   reordering dedup anywhere in this unit would hand that thread back to the sales pack.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.domain.hints import domain_hints
from genios_engine.capture.esqe import domain as D
from genios_engine.context.correlation import resolve_domain

INVESTOR_THREAD = ("Sharing our pitch deck ahead of the round — happy to walk through the "
                   "budget and the draft contract once diligence starts.")
AWS_RENEWAL = ("Our AWS renewal invoice is due next month; engineering flagged an outage risk "
               "on the old plan and legal wants the contract reviewed.")


def covered(*domains: str):
    """A `coverage_fn` that reports the named domains ready and everything else assessed-but-not.

    Shaped exactly like `capture/coverage/model.compute_coverage`'s return value, because a
    double that invented its own keys would prove this unit reads a dict nobody produces.
    """
    ready = set(domains)

    def _fn(domain: str) -> dict:
        return {"domain": domain, "coverage_ready": domain in ready,
                "coverage_state": "assessed",
                "missing_required": [] if domain in ready else ["communication"]}
    return _fn


def unknown_domain_fn(domain: str) -> dict:
    """The real model's answer for a domain with no registered requirements — `fundraising`."""
    return {"domain": domain, "coverage_ready": False, "coverage_state": "unknown_domain",
            "missing_required": []}


# =============================================================================================
# The plan's rule: never filter.
# =============================================================================================
def test_an_uncovered_domain_is_flagged_and_carded_never_dropped():
    """The acceptance sentence, as one assertion per clause."""
    tagging = D.tag_domains("gmail", AWS_RENEWAL, coverage_fn=covered("admin"))

    assert "sales" in tagging.domains, "the uncovered domain is still tagged"
    assert tagging.degraded_compile is True
    assert "sales" in tagging.uncovered and "admin" in tagging.covered
    carded = {o.domain for o in tagging.observations}
    assert "sales" in carded and "admin" not in carded
    assert tagging.observations[0].reason == D.REASON_UNCOVERED


def test_coverage_changes_the_flag_and_nothing_else():
    """The strongest form of never-filter: the tag list is byte-identical whether the tenant has
    full coverage, no coverage, or no coverage function at all."""
    everything = D.tag_domains("gmail", AWS_RENEWAL, coverage_fn=covered("admin", "sales",
                                                                        "support"))
    nothing = D.tag_domains("gmail", AWS_RENEWAL, coverage_fn=covered())
    unwired = D.tag_domains("gmail", AWS_RENEWAL)

    assert everything.domains == nothing.domains == unwired.domains
    assert everything.degraded_compile is False
    assert nothing.degraded_compile is True and unwired.degraded_compile is True


def test_the_tag_list_is_exactly_what_the_existing_resolver_produced():
    """This unit must not have rewritten `hints.py`. Same source, same text, same answer — the
    only way to prove a wrapper is a wrapper."""
    for source, text in (("gmail", INVESTOR_THREAD), ("hubspot", AWS_RENEWAL),
                         ("gmail", None), ("stripe", "")):
        tagging = D.tag_domains(source, text, coverage_fn=covered())
        assert list(tagging.hints) == domain_hints(source, text), (source, text)


@pytest.mark.parametrize("state, reason", [
    ("assessed", D.REASON_UNCOVERED),
    ("unknown_domain", D.REASON_UNCOVERED),
])
def test_an_assessed_miss_and_an_unregistered_domain_both_produce_a_card(state, reason):
    tagging = D.tag_domains("gmail", "Invoice overdue, please confirm payment.",
                            coverage_fn=lambda d: {"coverage_ready": False,
                                                   "coverage_state": state,
                                                   "missing_required": ["finance"]})
    assert tagging.observations and tagging.observations[0].reason == reason
    assert tagging.observations[0].coverage_state == state
    assert tagging.observations[0].missing_required == ("finance",)
    assert "finance" in tagging.observations[0].message


def test_an_unassessable_domain_is_carded_rather_than_assumed_covered():
    """No `coverage_fn`, and a `coverage_fn` that raises, are both 'nobody asked'. Neither may
    read as 'covered' — that is the direction in which a wrong answer licenses a false negative
    inference downstream ('they did not reply')."""
    def explodes(domain: str):
        raise RuntimeError("connection registry is down")

    for fn in (None, explodes, lambda d: "not a mapping"):
        tagging = D.tag_domains("gmail", AWS_RENEWAL, coverage_fn=fn)
        assert tagging.covered == ()
        assert tagging.degraded_compile is True
        assert all(o.reason == D.REASON_UNASSESSABLE for o in tagging.observations)


def test_a_coverage_lookup_that_raises_never_fails_the_capture():
    def explodes(domain: str):
        raise RuntimeError("boom")

    tagging = D.tag_domains("gmail", AWS_RENEWAL, coverage_fn=explodes)
    assert tagging.domains, "the tags survived the failure"


# =============================================================================================
# A signal may carry several domains, and L2 depends on all of them.
# =============================================================================================
def test_a_multi_domain_signal_retains_every_tag():
    """An AWS renewal is admin AND sales-vocabulary AND a support risk. The plan is explicit
    that L2's cross-domain correlator depends on all of them being present."""
    tagging = D.tag_domains("gmail", AWS_RENEWAL, coverage_fn=covered("admin"))

    assert set(tagging.domains) >= {"sales", "support", "admin"}
    assert len(tagging.covered) + len(tagging.uncovered) == len(tagging.domains)


def test_a_source_prior_and_a_keyword_both_survive():
    """`hubspot` carries a scope prior; the body carries keywords. Neither displaces the other."""
    tagging = D.tag_domains("hubspot", AWS_RENEWAL, coverage_fn=covered())

    origins = {(h.domain, h.source) for h in tagging.hints}
    assert ("sales", "scope") in origins
    assert any(origin == "keyword" for _, origin in origins)


def test_an_event_with_no_domain_at_all_is_not_degraded():
    """Nothing to be uncovered about. A blanket `degraded_compile=True` on every unclassified
    event would make the flag meaningless the day it mattered."""
    tagging = D.tag_domains("gmail", "thanks, talk soon", coverage_fn=covered())

    assert tagging.domains == () and tagging.hints == ()
    assert tagging.degraded_compile is False and tagging.observations == ()


# =============================================================================================
# The rule inside hints.py: fundraising before sales, and order preserved end to end.
# =============================================================================================
def test_an_investor_thread_stays_fundraising_despite_its_sales_vocabulary():
    """The rule `hints.py` names in its own comment. This thread says deck, round and diligence
    AND budget and contract; the generic sales words must not claim it."""
    tagging = D.tag_domains("gmail", INVESTOR_THREAD, coverage_fn=covered())

    assert tagging.domains[0] == "fundraising"
    assert "sales" in tagging.domains, "sales is still tagged — never filtered, only outranked"


def test_the_tag_order_survives_into_the_domain_a_downstream_reader_resolves():
    """`resolve_domain` reads the list positionally. This is the assertion that catches a sort
    or a set introduced anywhere between the resolver and the seam."""
    tagging = D.tag_domains("gmail", INVESTOR_THREAD, coverage_fn=covered())

    assert resolve_domain(list(tagging.hints)) == "fundraising"
    assert resolve_domain(tagging.as_dicts) == "fundraising"


def test_duplicate_domains_collapse_without_reordering():
    """`domains` dedups first-occurrence-wins. A `set()` here would be non-deterministic across
    runs and would put the ordering rule at the mercy of hash seeding."""
    tagging = D.tag_domains("hubspot", "deal pricing proposal contract quote demo",
                            coverage_fn=covered())

    assert tagging.domains == tuple(dict.fromkeys(h.domain for h in tagging.hints))
    assert len(tagging.domains) == len(set(tagging.domains))


def test_the_wire_shape_keeps_the_order_and_the_origin():
    tagging = D.tag_domains("hubspot", INVESTOR_THREAD, coverage_fn=covered())

    assert tagging.as_dicts == [{"domain": h.domain, "source": h.source} for h in tagging.hints]
    assert all(set(d) == {"domain", "source"} for d in tagging.as_dicts)

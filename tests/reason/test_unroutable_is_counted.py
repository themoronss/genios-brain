"""L2-4-U0/U1 · an unroutable situation is counted WITH ITS DOMAIN, not absorbed into a total.

⛔ **THE COUNT EXISTS AND THROWS AWAY THE ONE THING THAT MAKES IT ACTIONABLE.** `domain_shadow`
already tallies `counts["unactivatable_domain"]`, added after this exact silence was found:

    A situation whose L2 domain no corpus claims compiles in measurement mode, publishes no
    package and emits no signal — on EVERY tenant configuration… There was no count for it, so
    "shadow_situations" absorbed it alongside rows a tenant could switch on tomorrow, and the two
    are not the same fact.

**It is a scalar.** `unactivatable_domain: 69` cannot tell anybody whether to author `fundraising`
first or `general` first — and the same comment says the answer is not close:

    `general:relationship` is the most-authored type in the corpus (15 situations across the three
    domains) and the largest on the pilot (55 rows); `fundraising:investor_relationship` and
    `investor_contact` are the other two.

**55 of the pilot's 159 active situations are one dark type.** L1 wrote the rule this step applies:
*"DROP ≠ DELETE — you log why dropped, which rule, which threshold, which evidence."* A routing
miss is a drop, and a drop with no name is a delete.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_the_scalar_tally_still_exists():
    """This step refines a count; it does not remove one. A dashboard reading the old key must
    keep reading it."""
    from genios_engine.reason.unroutable import tally_unroutable

    counts: dict = {}
    tally_unroutable(counts, l2_domain="fundraising", situation_type="investor_relationship")
    assert counts["unactivatable_domain"] == 1


def test_the_domain_is_named_and_not_absorbed():
    from genios_engine.reason.unroutable import tally_unroutable

    counts: dict = {}
    for domain, stype in (("general", "relationship"), ("general", "relationship"),
                          ("fundraising", "investor_contact")):
        tally_unroutable(counts, l2_domain=domain, situation_type=stype)

    assert counts["unactivatable_domain"] == 3
    assert counts["unroutable:general"] == 2
    assert counts["unroutable:fundraising"] == 1


def test_the_situation_type_is_named_too_because_that_is_what_gets_authored():
    """⛔ A corpus is authored PER SITUATION TYPE, not per domain. `unroutable:general` = 55 says
    write a general corpus; `unroutable:general:relationship` = 55 says which situation it must
    describe first."""
    from genios_engine.reason.unroutable import tally_unroutable

    counts: dict = {}
    tally_unroutable(counts, l2_domain="general", situation_type="relationship")
    assert counts["unroutable:general:relationship"] == 1


def test_a_missing_type_is_recorded_as_unknown_rather_than_dropped():
    """A row with no `situation_type` is still a row that produced nothing."""
    from genios_engine.reason.unroutable import tally_unroutable

    counts: dict = {}
    tally_unroutable(counts, l2_domain="general", situation_type=None)
    assert counts["unroutable:general"] == 1
    assert counts["unroutable:general:unknown"] == 1


def test_an_undeclared_dark_domain_is_still_counted_and_flagged():
    """⛔ A domain that routes nowhere and is not in `DARK_DOMAINS` is the `support` defect
    returning. It is counted — never dropped — and marked so the tally itself says it is a
    surprise."""
    from genios_engine.reason.unroutable import tally_unroutable

    counts: dict = {}
    tally_unroutable(counts, l2_domain="logistics", situation_type="shipment")
    assert counts["unroutable:logistics"] == 1
    assert counts["unroutable_undeclared"] == 1


def test_a_declared_dark_domain_is_not_flagged_as_a_surprise():
    """Sensitivity — the flag must distinguish, or it flags everything."""
    from genios_engine.reason.unroutable import tally_unroutable

    counts: dict = {}
    tally_unroutable(counts, l2_domain="fundraising", situation_type="investor_contact")
    assert "unroutable_undeclared" not in counts


def test_the_sweep_calls_it_rather_than_incrementing_by_hand():
    """⛔ **THE WIRING CHECK.** A tally nobody calls is the defect this project keeps finding —
    *"a unit built, tested, green, and called by nothing on a real request path."*"""
    import inspect

    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow)
    assert "tally_unroutable(" in src, "the sweep does not use the tally"
    assert 'counts["unactivatable_domain"] = counts.get(' not in src, (
        "the sweep still increments the scalar by hand, so the two paths can disagree")

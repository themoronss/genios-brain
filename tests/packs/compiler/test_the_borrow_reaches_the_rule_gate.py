"""RO-05 / RO-08 — the two halves of one rule disagreed about what the slice contains.

    pytest tests/packs/compiler/test_the_borrow_reaches_the_rule_gate.py -q

`ContextAdapter._typed_absence` and `._derived` both consult the 1-hop neighbourhood. `_fact` did
not — so `exists`, `absent` and `path`, the three forms that decide almost every authored rule,
saw the ANCHOR'S OWN facts and nothing else.

On a COMPANY anchor that is close to nothing. `reason/domain_shadow` measured it and says so in
its own comment: *"Every situation here anchors on a `company`, and a company node holds no facts
of its own — 15 of 18 had literally zero. Everything a capability asks for
(thread.ball_in_court, deal.status, commitment.due_at) is extracted correctly by L2 and stored on
the PEOPLE and THREADS that constitute the relationship."*

AND THE OTHER HALF MADE IT SILENT. `situation_bso._missing_paths` counts a neighbour-held field as
HELD, so such a path never entered `missing_fields` either — which is what turned the answer into
a confident FALSE instead of an honest UNKNOWN. Two halves of one rule, disagreeing.

WHY FALSE IS THE DANGEROUS ANSWER. `matches()` short-circuits on the first FALSE term, and for a
doctrine rule FALSE reads as *satisfied* — "this situation does not violate this doctrine". An
audit of the compiled corpus found 23 of 31 rules, NINE OF THEM BLOCKING, reporting satisfied on
slices they had not read. Only seven abstained honestly.
"""

from __future__ import annotations

import pytest

from genios_engine.packs.compiler.context_adapter import ContextAdapter, PredicateState

pytestmark = pytest.mark.unit


class _Situation:
    metadata: dict = {}
    entities: tuple = ()
    type = "account_admin"


def adapter(*, facts: dict | None = None, neighbor: dict | None = None,
            missing: frozenset[str] = frozenset(),
            unknowable: frozenset[str] = frozenset(),
            absent: frozenset[str] = frozenset()) -> ContextAdapter:
    """A bare adapter over a chosen slice. Constructed directly rather than through a fixture
    corpus so the ONE variable under test is where the fact sits."""
    a = ContextAdapter.__new__(ContextAdapter)
    a.situation = _Situation()
    a.context = None
    a.facts = facts or {}
    a.neighbor_facts = neighbor or {}
    a.observations = set()
    a.neighbor_obs = set()
    a.missing_fields = missing
    a.unknowable_fields = unknowable
    a.absent_fields = absent
    return a


def state(a: ContextAdapter, condition: dict) -> str:
    return a.evaluate(condition).state.name


# =============================================================================================
# A company anchor whose facts live one hop down.
# =============================================================================================
def test_exists_finds_a_fact_held_by_the_neighbourhood():
    """The live shape: the company node is empty and `deal.status` is on the people beneath it."""
    a = adapter(facts={}, neighbor={"deal.status": "open"})

    assert state(a, {"exists": "deal.status"}) == "TRUE"


def test_absent_stops_claiming_there_is_no_deal():
    """The same gap read the other way, and this is the direction that INVENTS something. Before
    the borrow, `{absent: deal.status}` on a company with an open deal one hop away answered
    TRUE — the system asserting there is no deal while looking straight at one."""
    a = adapter(facts={}, neighbor={"deal.status": "open"})

    assert state(a, {"absent": "deal.status"}) == "FALSE"


def test_a_threshold_can_be_compared_against_a_borrowed_value():
    a = adapter(facts={}, neighbor={"deal.status": "open"})

    assert state(a, {"path": "deal.status", "op": "=", "value": "open"}) == "TRUE"


def test_a_fact_nobody_holds_is_still_not_there():
    """The borrow must not become "everything exists". A path held by neither the anchor nor its
    neighbourhood is genuinely not in the slice."""
    a = adapter(facts={}, neighbor={"deal.status": "open"})

    assert state(a, {"exists": "deal.nothing"}) == "FALSE"
    assert state(a, {"absent": "deal.nothing"}) == "TRUE"


# =============================================================================================
# What the borrow must not change.
# =============================================================================================
def test_the_anchors_own_fact_outranks_a_borrowed_one():
    """A fact ON the subject is the subject's own answer. The borrow fills a gap; it never
    overrides — otherwise a neighbour's stale copy could speak for the anchor."""
    a = adapter(facts={"deal.status": "won"}, neighbor={"deal.status": "open"})

    assert state(a, {"path": "deal.status", "op": "=", "value": "won"}) == "TRUE"
    assert state(a, {"path": "deal.status", "op": "=", "value": "open"}) == "FALSE"


def test_neighbor_fact_still_reads_the_neighbourhood_only():
    """An author writing `{neighbor_fact: X}` is asking about the neighbourhood specifically. A
    root value would answer a different question, so that form is deliberately not widened."""
    a = adapter(facts={"deal.status": "won"}, neighbor={})

    assert state(a, {"neighbor_fact": "deal.status", "op": "=", "value": "won"}) == "UNKNOWN"


def test_a_declared_gap_still_abstains():
    """`missing_fields` outranks everything: a field the expectation map says should be here and
    is not is UNKNOWN, whether or not a neighbour happens to hold something by that name."""
    a = adapter(facts={}, neighbor={"deal.status": "open"},
                missing=frozenset({"deal.status"}))

    assert state(a, {"exists": "deal.status"}) == "UNKNOWN"


def test_an_unknowable_field_still_abstains():
    """No connected source could have carried it. A borrowed value cannot change that — and
    `absent:` must never conclude anything from it."""
    a = adapter(facts={}, neighbor={},
                unknowable=frozenset({"contract.amendment"}))

    assert state(a, {"exists": "contract.amendment"}) == "UNKNOWN"
    assert state(a, {"absent": "contract.amendment"}) == "UNKNOWN"


def test_a_typed_genuine_absence_is_still_the_finding():
    """The one case where an absence is TRUE rather than an abstention — a source could have
    carried it, everything visible was checked, and none did. The borrow must not mask it."""
    a = adapter(facts={}, neighbor={}, absent=frozenset({"thread.last_inbound"}))

    assert state(a, {"absent": "thread.last_inbound"}) == "TRUE"


# =============================================================================================
# The consequence at the rule gate.
# =============================================================================================
def test_a_rule_over_a_company_anchor_no_longer_reads_as_satisfied():
    """RO-08, in one assertion. `matches()` short-circuits on the first FALSE, and for a doctrine
    rule FALSE reads as *satisfied* — so a blocking rule over a company whose facts live one hop
    down silently passed."""
    a = adapter(facts={}, neighbor={"deal.status": "open", "thread.ball_in_court": "us"})

    verdict = a.matches([{"exists": "deal.status"},
                         {"path": "thread.ball_in_court", "op": "=", "value": "us"}])

    assert verdict.state is PredicateState.TRUE


def test_a_rule_that_genuinely_does_not_match_still_says_so():
    """The guard may not become "every rule matches"."""
    a = adapter(facts={}, neighbor={"deal.status": "open"})

    verdict = a.matches([{"exists": "deal.status"}, {"exists": "deal.nothing"}])

    assert verdict.state is PredicateState.FALSE


def test_a_rule_whose_terms_are_all_undecidable_abstains():
    a = adapter(facts={}, neighbor={}, missing=frozenset({"deal.status"}))

    verdict = a.matches([{"exists": "deal.status"}])

    assert verdict.state is PredicateState.UNKNOWN
    assert "deal.status" in verdict.missing

"""The seams a correlator's own tests cannot see.

    pytest tests/context/test_the_correlators_are_actually_consumed.py -q

Every gap here has the same shape and none of them would fail a single existing test:

  * `read_organization_silence` and `read_campaign_silence` build `held["_organizations"]` and
    `held["_campaigns"]` BY HAND in their own tests, and the READINGS-membership tests only prove
    the reader is dispatched. Delete `outreach_situations._gather`'s two stamping lines and both
    readings return zero findings forever — with the whole branch still green.
  * `correlation_domain` is tested; the DECISION it feeds is not. Nothing asserted that a
    situation carrying `contradicted_by` is HELD, that `domain_shadow` populates it, or that an
    unresolved contradiction holds BOTH sides while a settled one holds only the loser. Dropping
    the kwarg at the call site would have been invisible.
  * The Dependency correlator had no two-tenant isolation test, unlike the other three. CC-40 is
    the catalogue's consultant-across-clients case and nothing pinned that one org's blocking
    claim cannot resolve an endpoint into another org's node.

`tests/test_nothing_is_written_and_never_read.py` asks whether a module is imported at all. This
file asks the narrower question that survives an import: is the VALUE it produces actually used
at the seam that needs it.
"""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# The two stampings in `_gather` — delete either and two readings go silent.
# =============================================================================================
def _gather_source() -> str:
    from genios_engine.context import outreach_situations

    return inspect.getsource(outreach_situations._gather)


@pytest.mark.parametrize(("key", "producer"), [
    ("_organizations", "find_organizations"),
    ("_campaigns", "find_campaigns"),
])
def test_gather_stamps_the_correlator_answer_the_reading_expects(key, producer):
    """The reserved-key route `_conditions` established. A reading that unpacks a key nobody
    stamps is a reading that returns `[]` on every tenant, forever."""
    source = _gather_source()

    assert f'held["{key}"]' in source, f"_gather no longer stamps {key}"
    assert producer in source, f"_gather no longer calls {producer}"


@pytest.mark.parametrize(("reading", "key"), [
    ("read_organization_silence", "_organizations"),
    ("read_campaign_silence", "_campaigns"),
])
def test_the_reading_unpacks_exactly_that_key(reading, key):
    """Both halves of the weld, so a rename on either side fails rather than going quiet."""
    from genios_engine.context import outreach_situations

    source = inspect.getsource(getattr(outreach_situations, reading))

    assert f'rows.get("{key}")' in source


def test_the_campaign_window_comes_from_the_sweep_clock():
    """`_gather` took no `now` and built the window from `datetime.now()`, so a replay at a past
    eval_time looked back ninety days from TODAY and found campaigns the sweep it is replaying
    could not have seen."""
    source = _gather_source()

    assert "now: datetime | None = None" in source
    assert "(now or datetime.now(timezone.utc))" in source


def test_both_group_readings_are_dispatched_from_readings():
    from genios_engine.context.outreach_situations import (
        ANCHOR_CAMPAIGN,
        ANCHOR_ORGANIZATION,
        READINGS,
    )

    anchors = {anchor for anchor, _reader in READINGS}

    assert {ANCHOR_ORGANIZATION, ANCHOR_CAMPAIGN} <= anchors


# =============================================================================================
# Cross Domain — the correlator is tested, the decision it feeds was not.
# =============================================================================================
def test_the_shadow_pass_reads_the_contradictions():
    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow.shadow_compile)

    assert "read_contradictions" in source
    assert "contradicted_by=" in source


def test_an_unresolved_contradiction_holds_both_sides():
    """A coin toss between two domains is worse than telling a reviewer the system cannot tell,
    so when no arbiter settles it NEITHER claim may travel as settled."""
    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow.shadow_compile)

    assert "if not finding.resolved" in source
    assert "for _key, sid in finding.sides" in source


def test_a_settled_contradiction_holds_only_the_loser():
    """The winner is the claim the shared evidence supports. Holding it too would suppress the
    correct reading to punish the incorrect one."""
    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow.shadow_compile)

    assert "if key == finding.loser" in source


def test_the_builder_carries_it_onto_the_candidate():
    from genios_engine.context import situation_bso

    signature = inspect.signature(situation_bso.build_business_situation)

    assert "contradicted_by" in signature.parameters


def _candidate(**metadata):
    """A candidate that clears every OTHER hold, so the one under test is the only variable.

    `_preflight` reads `old.evidence` through `_receipts`, so a bare namespace is not enough —
    a receipt has to be there or `verified_evidence_required` fires and the assertion below
    would pass for the wrong reason.
    """
    quote = "they have not replied since 12 August"

    class Candidate:
        id = "sit_x"
        # A MAPPING, because `_receipt` calls `.get` on each item and validates it into an
        # `EvidenceSpan` itself — handing it a constructed span raises on `.get`.
        evidence = ({"source_ref": "evt_1", "quote": quote,
                     "start_offset": 0, "end_offset": len(quote), "verified": True},)

    Candidate.metadata = {"importance_source": "l1_qualified_signals",
                          "evidence_verified_spans": 1, **metadata}
    return Candidate()


def test_the_gate_holds_a_contradicted_candidate():
    """`HoldReason.CONFLICT_OPEN` is the same shape one layer down — Layer 1 preserving two
    incompatible FACTS — and its comment states the principle: publishing as settled while the
    disagreement stands erases it by omission."""
    from genios_engine.context.situation_publisher import HoldReason, _preflight

    reasons = _preflight(
        _candidate(contradicted_by=["admin:awaiting_response|support:first_response_overdue"]),
        l1_scoring_active=True)

    assert HoldReason.CROSS_DOMAIN_CONTRADICTION.value in reasons


def test_an_uncontradicted_candidate_is_not_held_for_it():
    """The guard may not become a reason every card is held."""
    from genios_engine.context.situation_publisher import HoldReason, _preflight

    reasons = _preflight(_candidate(contradicted_by=[]), l1_scoring_active=True)

    assert HoldReason.CROSS_DOMAIN_CONTRADICTION.value not in reasons


def test_it_holds_rather_than_rejects():
    """Recoverable in the ordinary way: the arbiter fact moves, or the losing situation resolves
    itself on the next sweep. `decide_publication`'s own docstring sets that test — "a permanent
    hold is a REJECT wearing HOLD's name"."""
    from genios_engine.context.situation_publisher import HoldReason

    assert HoldReason.CROSS_DOMAIN_CONTRADICTION.value == "cross_domain_contradiction"


# =============================================================================================
# CC-40 — the Dependency correlator's missing tenancy pin.
# =============================================================================================
def test_the_dependency_correlator_scopes_every_join_to_one_org():
    """The other three correlators each have an explicit `another org` test; this one had none.
    A consultant working for two clients exists in both graphs, and one client's blocking claim
    must never resolve an endpoint into the other's node."""
    from genios_engine.context import correlation_dependency

    source = inspect.getsource(correlation_dependency)
    claims = source[source.index("_CLAIMS_SQL"):source.index("_CLAIMS_SQL") + 1400]

    assert "x.org_id = :org" in claims
    assert "e.org_id = x.org_id" in claims


def test_every_correlator_is_inside_the_ranking_gates():
    """Four of the eight — conversation, domain, organization, resource — were outside all three
    correlator gates. None violated them; the gate that is supposed to catch the next one simply
    was not looking."""
    from tests.context import test_dependency_correlation as gate

    names = {m.__name__.rsplit(".", 1)[-1] for m in gate.CORRELATORS}

    assert names == {
        "correlation", "correlation_conversation", "correlation_dependency",
        "correlation_domain", "correlation_organization", "correlation_resource",
        "correlation_timeline",
    }, sorted(names)

"""S2 · a unit that RAN on fewer inputs than it declared says so.

    pytest tests/reason/test_a_kept_unit_says_what_it_lost.py -q

⛔ THE GAP IS ASSERTED, IN THE POSITIVE, BY A PASSING TEST IN THIS REPOSITORY.
`test_selector_and_registration.py:86` says:

    assert "core.tension" in plan.reasoner_plan                            # KEPT
    assert [step.reasoner_id for step in plan.skipped] == ["core.money"]   # only core.money

`core.tension` was kept, lost `core.money`, and nothing recorded it.

⛔ AND THE MOST IMPORTANT TEST IN THIS FILE IS THE ONE THAT ASSERTS NOTHING CHANGED.
`_select` keeps a partially-fed unit on purpose — `plan.py:229` records that the stricter rule cost
*"six units lost to one absent fact"*. This is a receipt, never a refusal, and it has to be provably
additive.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (CapabilityManifest, ContextSnapshot, FailurePolicy,
                                               Goal, PlayDefinition, ReasonerSpec, ReasoningRequest)
from genios_engine.reason.plan import CONTEXT_AWARE_SELECTION_KEY, DegradedStep, ReasoningPlanner

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _capability(specs, metadata=None) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="test.degraded", version="1.0.0", domain="test", root_entity_type="deal",
        goal=Goal("test.goal", "Decide something", constraints=("none",)),
        reasoners=tuple(specs),
        plays=(PlayDefinition("play_a", "1.0.0", "A play", steps=("do the thing",)),),
        policies=(), metadata=metadata or {})


def _request(capability, facts) -> ReasoningRequest:
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="selector.v1", facts=facts)
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received")


#: Three feeders and one dependent that reads all three. The dependent is REQUIRED so it survives
#: whatever happens to its sources, which is what makes the degradation observable.
_THREE_SOURCE_DEPENDENT = (
    ReasonerSpec("core.clock", "1", required_fields=("deal.last_inbound",),
                 failure_policy=FailurePolicy.OPTIONAL),
    ReasonerSpec("core.money", "1", required_fields=("deal.value",),
                 failure_policy=FailurePolicy.OPTIONAL),
    ReasonerSpec("core.people", "1", required_fields=("deal.owner",),
                 failure_policy=FailurePolicy.OPTIONAL),
    ReasonerSpec("core.tension", "1",
                 dependencies=("core.clock", "core.money", "core.people"),
                 failure_policy=FailurePolicy.REQUIRED),
)

_OPT_IN = {CONTEXT_AWARE_SELECTION_KEY: True}


def _plan(facts, specs=_THREE_SOURCE_DEPENDENT):
    capability = _capability(specs, metadata=_OPT_IN)
    return ReasoningPlanner().plan(capability, _request(capability, facts))


# =================================================================================================
# 1 · ⛔ THE RECEIPT CHANGES NOTHING ABOUT WHAT RUNS
# =================================================================================================
@pytest.mark.parametrize("facts", [
    {},
    {"deal.last_inbound": "2026-08-01T00:00:00+00:00"},
    {"deal.value": 10, "deal.owner": "a"},
    {"deal.last_inbound": "2026-08-01T00:00:00+00:00", "deal.value": 10, "deal.owner": "a"},
])
def test_the_receipt_changes_nothing_about_what_is_kept_or_dropped(facts):
    """⛔ THE MOST IMPORTANT TEST HERE. `_select`'s starvation rule is correct and was arrived at by
    measurement — `plan.py:229`: under the stricter rule *"six units lost to one absent fact"*. This
    unit must be provably additive, so the expectations below are the pre-existing behaviour."""
    plan = _plan(facts)
    fed = {"core.clock": "deal.last_inbound", "core.money": "deal.value",
           "core.people": "deal.owner"}
    expected_kept = {u for u, field in fed.items() if field in facts} | {"core.tension"}
    assert set(plan.reasoner_plan) == expected_kept
    assert {s.reasoner_id for s in plan.skipped} == set(fed) - expected_kept


def test_a_unit_that_lost_one_of_three_sources_still_runs():
    plan = _plan({"deal.value": 10, "deal.owner": "a"})
    assert "core.tension" in plan.reasoner_plan


def test_selection_that_dropped_nothing_records_nothing():
    plan = _plan({"deal.last_inbound": "2026-08-01T00:00:00+00:00", "deal.value": 10,
                  "deal.owner": "a"})
    assert plan.skipped == ()
    assert plan.degraded == ()


def test_a_capability_that_did_not_opt_in_records_nothing():
    """Not "we did not look" — there was nothing to look at, and the empty tuple says so for both."""
    capability = _capability(_THREE_SOURCE_DEPENDENT)
    plan = ReasoningPlanner().plan(capability, _request(capability, {}))
    assert plan.skipped == () and plan.degraded == ()


# =================================================================================================
# 2 · what the receipt says
# =================================================================================================
def test_the_kept_unit_names_the_source_it_lost():
    plan = _plan({"deal.value": 10, "deal.owner": "a"})          # core.clock is unfed
    degraded = {d.reasoner_id: d for d in plan.degraded}
    assert degraded["core.tension"].lost_sources == ("core.clock",)


def test_it_names_what_it_KEPT_not_only_what_it_lost():
    """⛔ *"lost core.clock"* does not say whether two sources remained or none. The first is a reading;
    the second cannot happen, because a unit with nothing left to read is SKIPPED."""
    plan = _plan({"deal.value": 10, "deal.owner": "a"})
    d = {x.reasoner_id: x for x in plan.degraded}["core.tension"]
    assert d.available_sources == ("core.money", "core.people")
    assert d.declared_sources == ("core.clock", "core.money", "core.people")


def test_losing_two_of_three_is_still_a_reading_and_still_receipted():
    plan = _plan({"deal.value": 10})
    d = {x.reasoner_id: x for x in plan.degraded}["core.tension"]
    assert d.lost_sources == ("core.clock", "core.people")
    assert d.available_sources == ("core.money",)
    assert "core.tension" in plan.reasoner_plan


def test_the_receipt_is_sorted_so_two_runs_agree():
    """An unsorted receipt would make the plan hash depend on dict iteration order."""
    plan = _plan({"deal.value": 10})
    d = plan.degraded[0]
    for field in (d.declared_sources, d.available_sources, d.lost_sources):
        assert list(field) == sorted(field)


def test_the_share_lost_is_integer_basis_points():
    plan = _plan({"deal.value": 10, "deal.owner": "a"})
    assert plan.degraded[0].share_lost_bp == 3333


def test_the_explanation_says_both_halves():
    plan = _plan({"deal.value": 10, "deal.owner": "a"})
    line = plan.degraded[0].explain()
    assert "2 of 3" in line
    assert "core.clock" in line


# =================================================================================================
# 3 · ⛔ degraded is not skipped
# =================================================================================================
def test_a_degraded_unit_is_never_in_the_skipped_list():
    """⛔ A skipped unit produced NOTHING; a degraded one produced a reading. Folding them into one
    list would make "how many units ran?" unanswerable, and a consumer counting `skipped` would start
    counting units that did run."""
    plan = _plan({"deal.value": 10, "deal.owner": "a"})
    assert {s.reasoner_id for s in plan.skipped} == {"core.clock"}
    assert {d.reasoner_id for d in plan.degraded} == {"core.tension"}
    assert not ({s.reasoner_id for s in plan.skipped}
                & {d.reasoner_id for d in plan.degraded})


def test_every_degraded_unit_actually_ran():
    plan = _plan({"deal.value": 10})
    for d in plan.degraded:
        assert d.reasoner_id in plan.reasoner_plan


def test_a_unit_whose_every_source_went_is_skipped_and_never_degraded():
    """⛔ THE STARVATION RULE, FROM THE RECEIPT'S SIDE. Nothing left to read is a drop, not a
    degradation, and a `DegradedStep` claiming otherwise would contradict the selector."""
    specs = (
        ReasonerSpec("core.money", "1", required_fields=("deal.value",),
                     failure_policy=FailurePolicy.OPTIONAL),
        ReasonerSpec("core.clock", "1", required_fields=("deal.last_inbound",),
                     failure_policy=FailurePolicy.OPTIONAL),
        ReasonerSpec("core.tension", "1", dependencies=("core.money", "core.clock"),
                     failure_policy=FailurePolicy.OPTIONAL),
    )
    plan = _plan({"deal.status": "open"}, specs)
    assert plan.reasoner_plan == ()
    assert "core.tension" in {s.reasoner_id for s in plan.skipped}
    assert plan.degraded == ()


# =================================================================================================
# 4 · ⛔ the contract refuses an incoherent receipt
# =================================================================================================
def test_a_receipt_for_a_unit_that_lost_nothing_is_refused():
    """It would make "how many units ran on full input?" unanswerable."""
    with pytest.raises(ValueError, match="lost nothing"):
        DegradedStep("u", "1", ("a",), ("a",), ())


def test_a_receipt_with_nothing_left_to_read_is_ACCEPTED_and_flagged_starved():
    """⛔ MY FIRST VERSION REFUSED THIS, AND IT WAS THE WORST POSSIBLE THING TO REFUSE.

    The starvation rule applies to OPTIONAL units only — `_select`: *"a required unit's missing input is
    a fact the decision must confront, not one the schedule may hide."* So a REQUIRED unit whose every
    source went is KEPT and runs on nothing, and that is the loudest thing this receipt exists to
    record. The pre-existing `test_a_required_dependent_survives_the_loss_of_every_source` failed and
    proved it."""
    d = DegradedStep("u", "1", ("a",), (), ("a",))
    assert d.starved is True
    assert "NONE of its 1 declared sources" in d.explain()


def test_a_required_unit_that_lost_everything_is_kept_and_receipted_as_starved():
    """The end-to-end version of the case above, through the real planner."""
    specs = (
        ReasonerSpec("core.money", "1", required_fields=("deal.value",),
                     failure_policy=FailurePolicy.OPTIONAL),
        ReasonerSpec("core.risk", "1", dependencies=("core.money",)),     # REQUIRED by default
    )
    plan = _plan({"deal.status": "open"}, specs)

    assert plan.reasoner_plan == ("core.risk",), "a required unit must not vanish"
    d = {x.reasoner_id: x for x in plan.degraded}["core.risk"]
    assert d.starved is True
    assert d.available_sources == ()
    assert d.share_lost_bp == 10_000


def test_starved_is_distinct_from_ordinary_degradation():
    """⛔ *"ran on 2 of 3"* is a reading over less; *"ran on 0 of 1"* is a unit asserting something with
    none of the input it said it needed. A consumer treating them alike would rank them the same."""
    partial = DegradedStep("u", "1", ("a", "b", "c"), ("a", "b"), ("c",))
    starved = DegradedStep("u", "1", ("a",), (), ("a",))
    assert partial.starved is False and starved.starved is True
    assert "NONE" not in partial.explain() and "NONE" in starved.explain()


def test_the_persisted_receipt_carries_starved_rather_than_making_a_reader_derive_it():
    d = DegradedStep("u", "1", ("a",), (), ("a",))
    assert d.to_semantic_dict()["starved"] is True


def test_kept_plus_lost_must_account_for_every_declared_source():
    """Otherwise the receipt describes a plan that was not made."""
    with pytest.raises(ValueError, match="every declared source"):
        DegradedStep("u", "1", ("a", "b"), ("a",), ("z",))


def test_the_receipt_is_frozen():
    d = DegradedStep("u", "1", ("a", "b"), ("a",), ("b",))
    with pytest.raises(Exception):
        d.lost_sources = ()


# =================================================================================================
# 5 · ⛔ it reaches the plan hash — but only when it happened
# =================================================================================================
def test_a_degraded_plan_is_a_different_plan():
    """A unit running on 2 of 3 inputs is a materially different execution, so it belongs in the
    identity of the plan."""
    intact = _plan({"deal.last_inbound": "2026-08-01T00:00:00+00:00", "deal.value": 10,
                    "deal.owner": "a"})
    degraded = _plan({"deal.value": 10, "deal.owner": "a"})
    assert "degraded" in degraded.to_semantic_dict()
    assert intact.plan_hash != degraded.plan_hash


def test_an_intact_plan_carries_no_degraded_key_at_all():
    """⛔ Adding `"degraded": ()` to every plan would change `plan_hash` for every plan ever computed,
    breaking replay verification and audit continuity for runs where nothing degraded. An absent key
    and an empty tuple mean the same thing; only one of them costs the trail."""
    intact = _plan({"deal.last_inbound": "2026-08-01T00:00:00+00:00", "deal.value": 10,
                    "deal.owner": "a"})
    assert "degraded" not in intact.to_semantic_dict()


def test_two_identical_degraded_plans_hash_the_same():
    a = _plan({"deal.value": 10, "deal.owner": "a"})
    b = _plan({"deal.value": 10, "deal.owner": "a"})
    assert a.plan_hash == b.plan_hash


def test_losing_a_different_source_is_a_different_hash():
    a = _plan({"deal.value": 10, "deal.owner": "a"})           # lost core.clock
    b = _plan({"deal.last_inbound": "2026-08-01T00:00:00+00:00", "deal.owner": "a"})
    assert a.plan_hash != b.plan_hash

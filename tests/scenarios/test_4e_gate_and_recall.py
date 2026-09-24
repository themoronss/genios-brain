"""§4e · S29–S34 — the gate, and recall.

    pytest tests/scenarios/test_4e_gate_and_recall.py -q

Two failure classes pull in opposite directions here and **they are not equally expensive**:

    F13  qualification FALSE NEGATIVE — a real signal refused
    F14  qualification FALSE POSITIVE — noise admitted

A false positive costs a founder ten seconds. A false negative costs them the thing they needed to
know, **and they never find out it happened.** That asymmetry is why four of these six rows are
about NOT filtering, and why two of them are GUARDs on paths that already refuse to.

*"Never block on a missing score"* and *"an absence of judgement is never a judgement of absence"*
are the same rule stated at two seams.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


# =================================================================================================
# S29 · CORPUS — low confidence, HIGH importance
# =================================================================================================
def test_s29_a_refusal_near_its_achievable_ceiling_is_a_review_candidate():
    """⛔ **THE STEP THAT GATED ITSELF.** Step 10 built 10-U0 — the measurement — and **shipped
    nothing else**, because `PublicationOutcome` must stay closed at three until a real count says
    a fourth is worth existing.

    The logic is provable now. *Whether the population is non-empty* is Harsh's, and it decides
    whether the rest of step 10 should exist at all.

    **Near the CEILING, not the floor.** 400 of an achievable 10000 is a weak signal on a scale it
    could have used, and nothing about it says a person should look.
    """
    from genios_engine.capture.esqe.review_candidates import is_review_candidate

    assert is_review_candidate(
        {"importance_bp": 4800, "floor_bp": 5000, "achievable_ceiling_bp": 5200}) is True
    assert is_review_candidate(
        {"importance_bp": 400, "floor_bp": 5000, "achievable_ceiling_bp": 10_000}) is False


def test_s29_a_signal_that_cleared_its_floor_is_not_up_for_review():
    """E2, and the reason a review queue does not become a second inbox. Counting published rows
    would inflate the population with things nobody needs to look at."""
    from genios_engine.capture.esqe.review_candidates import is_review_candidate

    assert is_review_candidate(
        {"importance_bp": 6000, "floor_bp": 5000, "achievable_ceiling_bp": 6200}) is False


def test_s29_a_refusal_with_no_knowable_ceiling_is_not_counted():
    """⛔ **THE HARNESS BUG STEP 11 CAUGHT IN ITSELF.** A row whose ceiling cannot be computed is
    not "near" anything, and counting it would let an unmeasurable population look like a
    measured one."""
    from genios_engine.capture.esqe.review_candidates import is_review_candidate

    assert is_review_candidate({"importance_bp": 4800, "floor_bp": 5000}) is False


# =================================================================================================
# S30 · F14 — low confidence, LOW importance
# =================================================================================================
def test_s30_a_refusal_carries_the_rule_that_refused_it():
    """A drop with no reason is unauditable — nobody can tell a correct refusal from a bug, and
    the ledger is what makes the floor arguable rather than magic."""
    from genios_engine.capture.esqe.relevance import _REFUSING_RULES, is_kept

    assert _REFUSING_RULES, "nothing refuses anything — the floor has no teeth"
    for rule in _REFUSING_RULES:
        assert is_kept(rule) is False, f"{rule} is listed as refusing and still keeps its events"


# =================================================================================================
# S31 · GUARD — a conflict travels regardless of score
# =================================================================================================
def test_s31_every_fail_open_path_keeps_its_event():
    """*"A rule added without a row here keeps its events — which is the safe direction to be
    wrong in."*

    This is the GUARD that catches the dangerous edit: adding a refusing rule and forgetting the
    row is safe; adding one and getting the polarity wrong is not.
    """
    from genios_engine.capture.esqe.relevance import (RULE_COST_REFUSED, RULE_LLM_UNAVAILABLE,
                                                      UNJUDGED_FOR_BUDGET, is_kept)

    for rule in (RULE_LLM_UNAVAILABLE, RULE_COST_REFUSED, UNJUDGED_FOR_BUDGET):
        assert is_kept(rule) is True, f"{rule} means NOBODY DECIDED and must never refuse"


def test_s31_an_unknown_rule_keeps_its_event():
    """The open-world half. A rule nobody wrote a row for keeps its events, so a future rule cannot
    silently start filtering by being forgotten."""
    from genios_engine.capture.esqe.relevance import is_kept

    assert is_kept("a_rule_invented_next_quarter") is True


# =================================================================================================
# S32 · GUARD — an unscored signal travels
# =================================================================================================
def test_s32_the_budget_allocator_defers_rather_than_refuses():
    """⛔ **STEP 8's WHOLE ARGUMENT, and the number behind it: 69 of 225 events, 31%, never
    assessed.**

    The old guard was all-or-nothing: over the ambiguous share it alerted and judged NOTHING, so on
    a young tenant — where almost every sender is unknown, so the guard always tripped — the
    component that could have said *"this is a mass programme announcement"* never ran once.

    *"Do not raise the budget to make the problem go away — ALLOCATE it."*
    """
    from genios_engine.capture.esqe.relevance import UNJUDGED_FOR_BUDGET, allocate_budget, is_kept

    judged, deferred = allocate_budget(list(range(10)), budget=4)

    assert (len(judged), len(deferred)) == (4, 6)
    assert is_kept(UNJUDGED_FOR_BUDGET) is True, "the tail we could not reach must still travel"


def test_s32_a_non_positive_budget_defers_everything_rather_than_slicing_from_the_end():
    """The bug this branch exists to prevent. `ranked[:budget]` with a **negative** budget slices
    from the END — judging everything except the last item, silently inverting the unit while
    looking like it worked."""
    from genios_engine.capture.esqe.relevance import allocate_budget

    assert allocate_budget([1, 2, 3], budget=0) == ((), (1, 2, 3))
    assert allocate_budget([1, 2, 3], budget=-1) == ((), (1, 2, 3))


def test_s32_the_allocator_never_reorders():
    """E2 — importance is computed **after** relevance, so this cannot sort by the thing it would
    most like to sort by. *"An allocator that sorted by a proxy of its own would bury that choice
    where no report could see it."*"""
    from genios_engine.capture.esqe.relevance import allocate_budget

    judged, deferred = allocate_budget(["c", "a", "b"], budget=2)

    assert judged == ("c", "a") and deferred == ("b",)


# =================================================================================================
# S33 · CORPUS — the 68 pilot refusals
# =================================================================================================
def test_s33_the_population_measurement_reports_a_count_rather_than_a_verdict():
    """§4e wants *"a REVIEW count that is **neither 0 nor 68**"* over the pilot's real refusals.

    **0** would mean the floor is refusing nothing worth a look, and REVIEW should not exist.
    **68** would mean the floor is refusing everything worth a look, and the floor is wrong.

    Literally those 68 rows — Harsh item 15. The measurement is built and counts what it is given.
    """
    from genios_engine.capture.esqe.review_candidates import measure_review_population

    rows = ([{"importance_bp": 4800, "floor_bp": 5000, "achievable_ceiling_bp": 5200}] * 3
            + [{"importance_bp": 200, "floor_bp": 5000, "achievable_ceiling_bp": 10_000}] * 5)

    population = measure_review_population(rows)

    assert population.candidates == 3, "the measurement must count, not decide"


# =================================================================================================
# S34 · F14 — a newsletter drops WITH a ledger row
# =================================================================================================
def test_s34_a_newsletter_drops_and_names_the_code_that_dropped_it():
    """The F14 direction, which is the cheap one — **and it still owes a reason.** A drop with no
    N-code is indistinguishable from a bug, and §1's table is full of things that looked fine."""
    from genios_engine.capture.gate.context import GateContext
    from genios_engine.capture.gate.rules import noise_rule
    from genios_engine.contracts.source_event import SourceEvent

    event = SourceEvent(event_id="e1", org_id="o", connection_id="c", source="gmail",
                        object_type="email_message", source_object_id="m1",
                        dedup_key="gmail:email_message:m1", occurred_at=NOW,
                        actor={"email": "noreply@newsletter.test", "type": "external_contact"})
    verdict = noise_rule(GateContext(event=event, raw={
        "subject": "This week in AI", "headers": {"List-Unsubscribe": "<https://x.test/u>"}}))

    assert verdict is not None
    code, action = verdict
    assert action == "drop" and code.startswith("N-"), "dropped with no code is dropped blind"

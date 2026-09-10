"""The sentence that had no addressee, and the privacy rule that keeps it sayable.

    pytest tests/feedback/test_a_person_can_learn_about_themselves.py -q

Every learning object this layer produced was ORG-scoped. Harsh's plays close 80% of the time
and Sneha's 20%; `run_calibration` mutes or loosens the rule for BOTH on the pooled average, and
neither is ever told one thing about their own pattern. So "Rohit, the way you did that was not
working" had no addressee in this system — there was no per-person denominator anywhere.

`execution_outcomes.assignee` has existed since `0041_l5_execution.sql:241` and no unit had ever
read it. Everything downstream was already built: `subject_principal`, the contract's cap to
`Visibility(PRIVATE, principals=(subject,))`, the `actor` address token, the tenant's floors.
Only the number was missing.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.learning import LearningPolicy, VisibilityScope
from genios_engine.feedback.store import LearningBatch
from genios_engine.feedback.units import unit_actor_outcome_analysis

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


def outcome(assignee, label, **kw):
    return {"assignee": assignee, "label": label, "capability_id": "cap", "play_id": "play",
            "closed_at": NOW, "reminders_sent": 0, "escalations_fired": 0, **kw}


def run(outcomes):
    batch = LearningBatch(org_id="org1", since=NOW, outcomes=tuple(outcomes))
    return unit_actor_outcome_analysis(batch, LearningPolicy(org_id="org1", revision=1), NOW)


def by_subject(objects):
    return {o.subject: o for o in objects}


# =============================================================================================
# Two people on one tenant stop being one average.
# =============================================================================================
def test_two_people_get_two_numbers():
    """THE WHOLE POINT. Pooled, these are five successes in ten — a number that describes
    neither of them."""
    objects = run([outcome("harsh", "succeeded") for _ in range(4)]
                  + [outcome("harsh", "cancelled_by_human")]
                  + [outcome("sneha", "succeeded")]
                  + [outcome("sneha", "cancelled_by_human") for _ in range(4)])

    got = by_subject(objects)
    assert len(got) == 2
    rates = {s: o.proposed_value["success_rate_bp"] for s, o in got.items()}
    assert max(rates.values()) == 8000
    assert min(rates.values()) == 2000


# =============================================================================================
# It measures endings, not people.
# =============================================================================================
def test_a_tooling_failure_is_counted_and_not_charged():
    """A person whose outcomes are mostly mechanical failures has a TOOLING problem. A number
    that called that their failure would be a lie with a decimal point on it."""
    objects = run([outcome("harsh", "succeeded")]
                  + [outcome("harsh", "cancelled_by_system") for _ in range(9)])

    value = objects[0].proposed_value
    assert value["succeeded"] == 1
    assert value["failed"] == 0
    assert value["mechanical_failures"] == 9
    assert value["success_rate_bp"] == 10000, "graded denominator excludes the machinery"


def test_the_world_moving_is_not_charged_either():
    objects = run([outcome("harsh", "succeeded"),
                   outcome("harsh", "cancelled_by_world")])

    assert objects[0].proposed_value["failed"] == 0


def test_confidence_falls_when_most_endings_prove_nothing():
    """Ten outcomes of which one is graded is not ten observations' worth of evidence."""
    objects = run([outcome("harsh", "succeeded")]
                  + [outcome("harsh", "completed_unproven") for _ in range(9)])

    assert objects[0].evidence.observations == 10
    assert objects[0].evidence.confidence_bp == 1000


# =============================================================================================
# The privacy rule, which the contract also enforces.
# =============================================================================================
def test_a_persons_rate_is_private_to_that_person():
    """A rate one person can read about another is a performance judgment the evidence cannot
    support. It is visible to its subject and to nobody else — including their manager."""
    objects = run([outcome("harsh", "succeeded"), outcome("sneha", "cancelled_by_human")])

    for o in objects:
        assert o.visibility.scope is VisibilityScope.PRIVATE
        assert tuple(o.visibility.principals) == (o.subject_principal,)
        assert len(o.visibility.principals) == 1


def test_harshs_number_does_not_name_sneha():
    objects = by_subject(run([outcome("harsh", "succeeded"),
                              outcome("sneha", "succeeded")]))

    harsh = next(o for s, o in objects.items() if "harsh" in s)
    assert "sneha" not in str(harsh.proposed_value)
    assert "sneha" not in str(tuple(harsh.visibility.principals))


def test_an_id_needing_sanitising_still_produces_a_valid_object():
    """The contract requires principals to EQUAL `subject_principal`. Passing the raw string as
    one and the sanitised key as the other would raise on precisely the ids that needed
    sanitising — the worst possible time to fail."""
    objects = run([outcome("rohit@genios.ai", "succeeded")])

    assert len(objects) == 1
    assert tuple(objects[0].visibility.principals) == (objects[0].subject_principal,)


# =============================================================================================
# What it refuses to do.
# =============================================================================================
def test_an_unassigned_outcome_is_skipped_not_bucketed():
    """A person-less outcome is not evidence about any person. An "unknown" bucket would be a
    private learning object addressed to nobody."""
    assert run([outcome(None, "succeeded"), outcome("", "succeeded"),
                outcome("   ", "succeeded")]) == []


def test_no_outcomes_means_no_claims():
    assert run([]) == []


def test_the_store_actually_reads_the_column():
    """The unit is worth nothing if `assignee` never arrives — which was the state for the whole
    life of the column."""
    import inspect

    from genios_engine.feedback import store

    assert '"assignee, "' in inspect.getsource(store._load_outcomes)


def test_it_shares_the_label_rules_with_the_play_scoped_unit():
    """Two spellings of "this ending is evidence the recommendation was wrong" is how they come
    to disagree the day a sixth label is minted."""
    import inspect

    from genios_engine.feedback import units

    source = inspect.getsource(units.unit_actor_outcome_analysis)

    assert "label_class(o.get(\"label\"))" in source
    assert "counts_against_the_play(o.get(\"label\"))" in source

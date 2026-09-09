"""LRN-01 and LRN-07 — what an ending says about the RECOMMENDATION.

    pytest tests/feedback/test_label_class.py -q

`executive/collect.py` records HOW an execution ended. Whether that ending is evidence about the
recommendation is a second, different question, and every consumer answered it by hand with
`else: failed`.

THE COST, and it is in the one unit that changes behaviour. `unit_recommendation_learning` writes
to `LearningTarget.ADAPTIVE` — not METRICS — and counted `negative = n - succeeded`. So a play was
charged for:

    completed_unproven    it worked and no connected source can prove it        ← LRN-01
    expired_in_progress   somebody was actively working on it
    cancelled_by_world    the situation resolved itself underneath a correct card
    cancelled_by_system   OUR OWN tooling cancelled it                          ← LRN-07

Meanwhile `unit_outcome_analysis` used a different rule — a `_NEUTRAL` set of two — so the two
units disagreed about `cancelled_by_world` and about `completed_unproven`. One called an ending
neutral while the other charged the play for it.

`label_class` is now the single table both read. Four classes, not three: `mechanical` is separate
from `neutral` because both must stay out of the score and only one of them means something is
BROKEN — folding them would hide a play whose tooling fails every time behind a shrug.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.executive.collect import (
    LABEL_CANCELLED_BY_HUMAN,
    LABEL_CANCELLED_BY_SYSTEM,
    LABEL_CANCELLED_BY_WORLD,
    LABEL_COMPLETED_UNPROVEN,
    LABEL_EXPIRED_IN_PROGRESS,
    LABEL_EXPIRED_UNTOUCHED,
    LABEL_MECHANICAL,
    LABEL_NEGATIVE,
    LABEL_NEUTRAL,
    LABEL_POSITIVE,
    LABEL_SUCCEEDED,
    counts_against_the_play,
    label_class,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


# =============================================================================================
# The table.
# =============================================================================================
@pytest.mark.parametrize("label,expected", [
    (LABEL_SUCCEEDED, "positive"),
    (LABEL_EXPIRED_UNTOUCHED, "negative"),
    (LABEL_CANCELLED_BY_HUMAN, "negative"),
    (LABEL_COMPLETED_UNPROVEN, "neutral"),
    (LABEL_EXPIRED_IN_PROGRESS, "neutral"),
    (LABEL_CANCELLED_BY_WORLD, "neutral"),
    (LABEL_CANCELLED_BY_SYSTEM, "mechanical"),
])
def test_each_ending_is_classified(label, expected):
    assert label_class(label) == expected


def test_lrn_01_work_that_cannot_be_proven_is_not_a_failure():
    """"The user completed the work, but GeniOS does not observe it." Charging the play for that
    teaches the system to stop recommending the thing that worked."""
    assert not counts_against_the_play(LABEL_COMPLETED_UNPROVEN)


def test_lrn_07_our_own_tooling_failing_is_not_a_bad_recommendation():
    """"A failed action is learned as a bad recommendation." Separate recommendation quality from
    tool-execution failure."""
    assert not counts_against_the_play(LABEL_CANCELLED_BY_SYSTEM)
    assert label_class(LABEL_CANCELLED_BY_SYSTEM) == "mechanical"


def test_the_world_moving_is_not_the_cards_fault():
    """COR-07: a commitment completed between detection and delivery. The recommendation was
    correct when it was made."""
    assert not counts_against_the_play(LABEL_CANCELLED_BY_WORLD)


def test_what_genuinely_counts_against_a_play():
    """Two endings, and both are the reader telling us something: nobody touched it before it
    expired, or a human looked at it and cancelled it."""
    assert counts_against_the_play(LABEL_EXPIRED_UNTOUCHED)
    assert counts_against_the_play(LABEL_CANCELLED_BY_HUMAN)


def test_an_unknown_label_never_penalises_a_play():
    """THE DIRECTION THAT MATTERS. A label this table has not been taught must not silently charge
    a play — the old `else: failed` did exactly that for four different endings."""
    assert label_class("some_future_label") == "unknown"
    assert not counts_against_the_play("some_future_label")
    assert not counts_against_the_play(None)
    assert not counts_against_the_play("")


# =============================================================================================
# The drift guard.
# =============================================================================================
def test_every_label_the_collector_can_emit_is_classified():
    """A new `LABEL_*` constant that nobody classifies falls to `unknown`, which is safe but
    silent. This fails instead."""
    import genios_engine.executive.collect as collect

    emitted = {v for k, v in vars(collect).items()
               if k.startswith("LABEL_") and isinstance(v, str)}
    classified = LABEL_POSITIVE | LABEL_NEGATIVE | LABEL_NEUTRAL | LABEL_MECHANICAL

    assert emitted == classified, f"unclassified endings: {sorted(emitted - classified)}"


def test_the_four_classes_do_not_overlap():
    """An ending in two classes would make `label_class` order-dependent."""
    classes = (LABEL_POSITIVE, LABEL_NEGATIVE, LABEL_NEUTRAL, LABEL_MECHANICAL)
    for i, a in enumerate(classes):
        for b in classes[i + 1:]:
            assert not (a & b), f"overlap: {sorted(a & b)}"


# =============================================================================================
# The units that read it.
# =============================================================================================
def _outcome(label: str, play: str = "deliver_commitment") -> dict:
    return {"capability_id": "cap", "play_id": play, "label": label,
            "reminders_sent": 0, "escalations_fired": 0, "closed_at": NOW}


def _batch(*outcomes):
    from genios_engine.feedback.store import LearningBatch

    return LearningBatch(org_id="org_pilot", since=NOW, outcomes=tuple(outcomes))


def _policy(min_observations: int = 1):
    from genios_engine.contracts.learning import LearningPolicy

    return LearningPolicy(org_id="org_pilot", revision=1, min_observations=min_observations)


def test_the_adaptive_unit_no_longer_charges_a_play_for_a_tool_failure():
    """THE REGRESSION, stated where it did damage. Unit 8's target is ADAPTIVE — it changes the
    brain — and every non-success used to be `negative`."""
    from genios_engine.feedback.units import unit_recommendation_learning

    batch = _batch(_outcome(LABEL_SUCCEEDED), _outcome(LABEL_CANCELLED_BY_SYSTEM),
                   _outcome(LABEL_COMPLETED_UNPROVEN))

    [obj] = unit_recommendation_learning(batch, _policy(), NOW)

    assert obj.evidence.negative == 0, "a tool failure and an unprovable success are not negatives"
    assert obj.evidence.positive == 1
    assert obj.proposed_value["graded_endings"] == 1
    assert obj.proposed_value["ungraded_endings"] == 2
    assert obj.proposed_value["success_rate_bp"] == 10_000


def test_a_play_with_no_graded_ending_teaches_nothing():
    """A play that ran twenty times and was cancelled by the world every time has twenty
    observations and nothing to learn from. Admitting it would let an unmeasured play rewrite the
    brain."""
    from genios_engine.feedback.units import unit_recommendation_learning

    batch = _batch(*[_outcome(LABEL_CANCELLED_BY_WORLD) for _ in range(20)])

    assert unit_recommendation_learning(batch, _policy(), NOW) == []


def test_a_genuine_dismissal_still_counts_against_the_play():
    """The guard must not become a way for a play to never be wrong."""
    from genios_engine.feedback.units import unit_recommendation_learning

    batch = _batch(_outcome(LABEL_SUCCEEDED), _outcome(LABEL_CANCELLED_BY_HUMAN))

    [obj] = unit_recommendation_learning(batch, _policy(), NOW)

    assert obj.evidence.negative == 1
    assert obj.proposed_value["success_rate_bp"] == 5_000


def test_the_metrics_unit_counts_mechanical_failures_separately():
    """Counted, never charged. A play whose tooling fails every time is a real defect and must
    stay visible — it is simply a defect in the machinery."""
    from genios_engine.feedback.units import unit_outcome_analysis

    batch = _batch(_outcome(LABEL_CANCELLED_BY_SYSTEM), _outcome(LABEL_SUCCEEDED))

    [obj] = unit_outcome_analysis(batch, _policy(), NOW)

    assert obj.proposed_value["mechanical_failures"] == 1
    assert obj.proposed_value["failed"] == 0


def test_the_two_units_now_agree_about_every_ending():
    """They disagreed about `cancelled_by_world` and `completed_unproven`: one called an ending
    neutral while the other charged the play for it."""
    from genios_engine.feedback.units import unit_outcome_analysis, unit_recommendation_learning

    for label in sorted(LABEL_POSITIVE | LABEL_NEGATIVE | LABEL_NEUTRAL | LABEL_MECHANICAL):
        batch = _batch(_outcome(label))
        [metrics] = unit_outcome_analysis(batch, _policy(), NOW)
        adaptive = unit_recommendation_learning(batch, _policy(), NOW)

        charged_by_metrics = metrics.proposed_value["failed"] > 0
        charged_by_adaptive = bool(adaptive) and adaptive[0].evidence.negative > 0

        assert charged_by_metrics == charged_by_adaptive == counts_against_the_play(label), label

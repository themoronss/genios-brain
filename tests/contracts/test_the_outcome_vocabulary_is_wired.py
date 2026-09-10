"""DM · the canonical outcome, from the vocabulary that named it to the seam that folds it.

    pytest tests/contracts/test_the_outcome_vocabulary_is_wired.py -q

`contracts/outcomes` was written to be "the one place that names what happened to a situation",
and an audit found it with ELEVEN outcomes, forty-two tests and ZERO importers in the engine. The
first wave gave it one consumer — the card push gate — and left four defects behind, all of which
this file pins:

  * THE FOLD NEVER HAPPENED. `resolve()` exists so "what happened" has ONE answer, and nothing
    called it. `deliver/outbox.py` — the drain, the only seam where the card's abstention level,
    the gate's `DeliveryVerdict` and the lifecycle are all in hand at once — imported
    `contracts/delivery` and not `contracts/outcomes`, so the question kept three answers in
    three modules.
  * THE PUBLISHER GATE WAS INVISIBLE TO THE MAP. `PublicationOutcome` is the single biggest real
    producer of the canonical HOLD — 504 held against 28 admitted on the pilot — and it was
    absent from `PROJECTION`, so `unreachable()` returned `()` and `UNEXPRESSED_BY` reported no
    gap for HOLD. A coverage map is at its most wrong when it reads clean about a layer it has
    never been shown.
  * `__all__` NAMED THE DEAD HALF. It exported five names no engine module reads and omitted
    `interrupts` and `INTERRUPTS`, the two that are actually wired.
  * FEEDBACK WAS BLIND TO THE CARD'S LEVEL. Dismissing an `ask_decision` card — one the system
    put in front of a person precisely because only they could answer it — was graded exactly
    like rejecting a bad prescription, and `calibrate.TAXONOMY` put it in the precision
    DENOMINATOR. Answering the system's own question became evidence the system was wrong.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.context.situation_publisher import PublicationOutcome
from genios_engine.contracts.abstention import ACTIONABLE, Level
from genios_engine.contracts.outcomes import (
    INTERRUPTS,
    PROJECTION,
    Outcome,
    disagreements,
    project,
    resolve,
    unreachable,
)

pytestmark = pytest.mark.unit


# =============================================================================================
# The fold, at the seam that has every input.
# =============================================================================================
def test_the_drain_folds_the_layers_into_one_outcome():
    from genios_engine.deliver import outbox

    source = inspect.getsource(outbox)

    assert "from genios_engine.contracts.outcomes import resolve" in source
    assert "canonical = resolve(" in source


def test_the_drain_reads_the_card_level_the_fold_needs():
    """`delivery_outbox` carries no level, so the fold would have seen `None` on every row and
    resolved from the verdict alone — a fold that cannot see half its inputs is not one."""
    from genios_engine.deliver import outbox

    source = inspect.getsource(outbox._drain_claimed)

    assert "select card_id, level from cards" in source
    assert 'levels.get(str(r.get("card_id") or ""))' in source


def test_the_level_read_never_stops_a_send():
    """It feeds a COUNTER. A card that cannot be read must still be delivered — the alternative
    is a metric deciding whether somebody gets their message."""
    from genios_engine.deliver import outbox

    source = inspect.getsource(outbox._drain_claimed)

    assert "except Exception:      # noqa: BLE001 — a counter's input, never a reason not to send" \
        in source


def test_the_fold_states_what_the_branches_mean_without_changing_them():
    """`resolve` is read-only here. If it started deciding, two things would decide delivery and
    the older one would win silently on the day they disagreed."""
    from genios_engine.deliver import outbox

    source = inspect.getsource(outbox)
    fold = source.index("canonical = resolve(")
    after = source[fold:fold + 600]

    assert "out[key] = out.get(key, 0) + 1" in after
    assert "if decision.verdict is DeliveryVerdict.SUPPRESS:" in after


@pytest.mark.parametrize(("level", "verdict", "expected"), [
    ("prescriptive", "send", Outcome.EMIT_ACTION),
    ("review", "send", Outcome.ASK_DECISION),
    ("observation", "send", Outcome.EMIT_OBSERVATION),
    ("prescriptive", "defer", Outcome.DEFER),
    ("prescriptive", "suppress", Outcome.SUPPRESS),
])
def test_the_precedence_the_drain_relies_on(level, verdict, expected):
    """What the two inputs together mean, by the documented rank. A suppressed prescription is
    SUPPRESSED, not emitted — the delivery decision outranks the card's ambition."""
    assert resolve(**{"abstention.Level": level,
                      "delivery.DeliveryVerdict": verdict}) is expected


def test_a_row_with_neither_input_resolves_to_nothing():
    """`None` is not an outcome and must not be counted as one."""
    assert resolve(**{"abstention.Level": None, "delivery.DeliveryVerdict": None}) is None


def test_a_disagreement_is_recoverable_rather_than_lost():
    """A suppressed decision request is a real event — the question was asked and refused — and
    `disagreements` is what lets a reader see the discarded half."""
    dropped = disagreements(**{"abstention.Level": "review",
                               "delivery.DeliveryVerdict": "suppress"})

    assert Outcome.ASK_DECISION in dropped


# =============================================================================================
# The layer the map had never been shown.
# =============================================================================================
def test_the_publisher_gate_is_projected():
    assert "context.PublicationOutcome" in PROJECTION


@pytest.mark.parametrize("value", [o.value for o in PublicationOutcome])
def test_every_verdict_that_gate_can_produce_is_projected(value):
    assert project("context.PublicationOutcome", value) is not None


def test_the_publisher_hold_is_the_canonical_hold():
    """504 held against 28 admitted on the pilot. That is what `Outcome.HOLD` was written for,
    and it had no source at all until this vocabulary was added."""
    assert project("context.PublicationOutcome", "hold") is Outcome.HOLD


def test_a_reject_is_not_a_hold():
    """`decide_publication` draws the line and the projection must keep it: a hold "preserves
    recoverable incompleteness and may be retried after the next sweep", a reject is a contract
    failure no sweep repairs."""
    assert project("context.PublicationOutcome", "reject") is not Outcome.HOLD


def test_hold_is_no_longer_unreachable():
    """`unreachable()` returned `()` while HOLD had no source — the map reading clean about a
    layer it could not see is the failure this closes."""
    assert Outcome.HOLD not in unreachable()


# =============================================================================================
# The public surface.
# =============================================================================================
def test_the_names_that_are_wired_are_exported():
    from genios_engine.contracts import outcomes

    for name in ("interrupts", "INTERRUPTS", "resolve"):
        assert name in outcomes.__all__, name


def test_everything_exported_exists():
    from genios_engine.contracts import outcomes

    for name in outcomes.__all__:
        assert hasattr(outcomes, name), name


# =============================================================================================
# Feedback stopped grading a question like an instruction.
# =============================================================================================
def test_only_a_prescribing_card_can_be_graded_as_wrong():
    from genios_engine.feedback.units import _PRESCRIBING_LEVELS

    assert _PRESCRIBING_LEVELS == frozenset(ACTIONABLE)
    assert Level.REVIEW not in _PRESCRIBING_LEVELS
    assert Level.OBSERVATION not in _PRESCRIBING_LEVELS


def test_the_level_travels_with_the_verdict():
    from genios_engine.feedback import store

    source = inspect.getsource(store)

    assert "_attach_card_level" in source
    assert "join cards c on c.org_id = v.org_id and c.card_id = v.card_id" in source


def test_a_verdict_whose_card_is_gone_is_ungradeable_not_negative():
    """Defaulting a missing level to "instruction" is exactly how the old behaviour returns."""
    from genios_engine.feedback import units

    source = inspect.getsource(units.unit_feedback_learning)

    assert 'level = str(v.get("card_level") or "").strip().lower()' in source
    assert "graded = level in _PRESCRIBING_LEVELS" in source


def test_the_precision_denominator_counts_prescriptions_only():
    """`calibrate` put `wrong:not_relevant` on any card into the precision denominator. A card at
    `review` never made a recommendation, so it cannot have made a wrong one."""
    from genios_engine.feedback import calibrate

    source = inspect.getsource(calibrate)

    assert "and card_level in ('prescriptive','predictive')) as rel_wrong" in source


def test_the_card_level_reaches_the_judgment_cte():
    """The filter above is worth nothing if the column never arrives."""
    from genios_engine.reason import authority

    assert "k.level as card_level" in authority.AUDITED_CARD_JUDGMENTS_CTES
    assert authority.AUDITED_CARD_JUDGMENTS_CTES.count("ac.card_level") >= 2


# =============================================================================================
# One question, one answer.
# =============================================================================================
def test_the_named_escalation_predicate_is_the_one_that_answers():
    """Three places answered "is this rung an escalation" and the named predicate was the dead
    one. The bridge owns the ladder; the channel asks it."""
    from genios_engine.deliver.channels import slack

    source = inspect.getsource(slack.format_reminder_message)

    assert "is_escalation(payload.get(\"reason_code\"))" in source


def test_counts_against_the_play_has_callers():
    """Built, tested five ways, called by nothing — while two sites asked the same question by
    spelling the label out."""
    from genios_engine.feedback import units

    source = inspect.getsource(units)

    assert source.count("counts_against_the_play(") >= 2


def test_asking_and_instructing_stay_different_questions():
    """`INSTRUCTING` says the system is telling somebody what to do; `INTERRUPTS` says it may
    take their attention. A decision request is the second and not the first, and folding them
    would either silence the question or turn it into an order."""
    from genios_engine.contracts.outcomes import INSTRUCTING

    assert Outcome.ASK_DECISION in INTERRUPTS
    assert Outcome.ASK_DECISION not in INSTRUCTING
    assert INSTRUCTING <= INTERRUPTS

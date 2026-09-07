"""M-7 · the timeline narrative — every row in `L2.7.2-U2`'s ACCEPTANCE list.

The load-bearing property is that **the model cannot reorder anything**. A timeline whose order
came from a model is a timeline that tells the story differently on the second run, and doc 09's
H8 gate diffs situations across runs. Order is computed; the model selects from an ordered set and
names a shape from a closed vocabulary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.context.framing.timeline import (FALLBACK_EMPTY_SELECTION,
                                                    FALLBACK_MODEL_ERROR, FALLBACK_NO_MODEL,
                                                    FALLBACK_UNKNOWN_EVENT,
                                                    FALLBACK_UNKNOWN_SHAPE, SHAPES,
                                                    TimelineEvent, build_prompt, chronology,
                                                    narrate, render)
from genios_engine.contracts.visibility import PARTICIPANTS, PRIVATE, Visibility

EVAL_TIME = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
READER = "rohit@antler.co"
SECRET = "Blackthorn-acquisition"


def _events() -> list[TimelineEvent]:
    """Three events, deliberately built OUT of order so a caller that forgot to sort is visible."""
    seen = Visibility(scope=PARTICIPANTS, principals=[READER])
    return [
        TimelineEvent("evt_c", EVAL_TIME - timedelta(days=10), "they went quiet", seen),
        TimelineEvent("evt_a", EVAL_TIME - timedelta(days=90), "promise made", seen),
        TimelineEvent("evt_b", EVAL_TIME - timedelta(days=45), "reminder sent", seen),
    ]


def _private_event() -> TimelineEvent:
    return TimelineEvent("evt_secret", EVAL_TIME - timedelta(days=30), SECRET,
                         Visibility(scope=PRIVATE, principals=["board@antler.co"]))


def _ask(**response):
    return lambda _prompt: response


# =================================================================================================
# The order is computed, never asked for
# =================================================================================================

def test_the_chronology_is_identical_with_and_without_the_model():
    """The model cannot reorder. A model-ordered timeline cannot be replayed."""
    plain = [e.event_id for e in chronology(_events(), viewer_email=READER)]
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       ask=_ask(event_ids=["evt_c", "evt_a"], shape="stalled"),
                       viewer_email=READER)
    assert plain == ["evt_a", "evt_b", "evt_c"]
    assert [e.event_id for e in narrated.chronology] == plain
    assert [e.event_id for e in narrated.selected] == ["evt_a", "evt_c"], (
        "selected events come back in CHRONOLOGICAL order, not in the order the model listed them")


def test_the_full_chronology_stays_available_even_when_selection_drops_events():
    """Doc 12 case 13: selection is the model's, and the complete story stays available so a card
    can expand to it. A narrative that replaced the timeline would make an omission unrecoverable.
    """
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       ask=_ask(event_ids=["evt_c"], shape="silent_since"), viewer_email=READER)
    assert len(narrated.selected) == 1
    assert len(narrated.chronology) == 3


def test_two_events_at_the_same_instant_order_deterministically():
    same = [TimelineEvent("evt_z", EVAL_TIME, "z"), TimelineEvent("evt_a", EVAL_TIME, "a")]
    assert [e.event_id for e in chronology(same)] == ["evt_a", "evt_z"]


# =================================================================================================
# Validation: an event outside the supplied set, and a shape outside the vocabulary
# =================================================================================================

def test_an_event_id_outside_the_supplied_set_rejects_the_whole_narrative():
    """A fabricated event on a card. The narrative is rejected entirely rather than repaired —
    a model that invented one event has not earned the benefit of the doubt on the others."""
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       ask=_ask(event_ids=["evt_a", "evt_imagined"], shape="stalled"),
                       viewer_email=READER)
    assert narrated.fallback is True
    assert narrated.fallback_reason == FALLBACK_UNKNOWN_EVENT
    assert narrated.sentence == ""


def test_a_filtered_event_cannot_be_named_back_in():
    """The visibility row. `evt_secret` was dropped before the prompt, so naming it is
    indistinguishable from inventing it — and lands on the same refusal."""
    events = _events() + [_private_event()]
    prompt = build_prompt(chronology(events, viewer_email=READER),
                          situation_type="commitment_unresolved")
    assert SECRET not in prompt and "evt_secret" not in prompt

    narrated = narrate(events, situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       ask=_ask(event_ids=["evt_secret"], shape="stalled"), viewer_email=READER)
    assert narrated.fallback_reason == FALLBACK_UNKNOWN_EVENT
    assert SECRET not in narrated.sentence
    assert SECRET not in str(narrated.as_record())


def test_a_shape_outside_the_closed_set_is_rejected():
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       ask=_ask(event_ids=["evt_a"], shape="catastrophic"), viewer_email=READER)
    assert narrated.fallback_reason == FALLBACK_UNKNOWN_SHAPE


def test_the_shape_vocabulary_is_closed_and_small():
    assert set(SHAPES) == {"steady", "stalled", "accelerating", "silent_since",
                           "deadline_approaching"}


# =================================================================================================
# Every interval is computed, never generated
# =================================================================================================

def test_every_interval_equals_the_computed_difference_between_the_selected_dates():
    """"about three months" is a number nobody can check. The card's numbers are arithmetic over
    the events' own dates."""
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       ask=_ask(event_ids=["evt_a", "evt_c"], shape="stalled"),
                       viewer_email=READER)
    assert narrated.sentence == "promise made, then nothing for 10 days"
    silent_days = (EVAL_TIME - narrated.selected[-1].occurred_at).days
    assert str(silent_days) in narrated.sentence


def test_the_rendered_sentence_is_the_same_for_the_same_inputs():
    selected = chronology(_events(), viewer_email=READER)
    assert render("silent_since", selected, eval_time=EVAL_TIME) == render(
        "silent_since", selected, eval_time=EVAL_TIME)


def test_no_shape_sentence_contains_a_digit():
    """Same rule as the headline templates: a literal number in a template is a number no event
    backs."""
    from genios_engine.context.framing.timeline import _SENTENCES
    for shape, sentence in _SENTENCES.items():
        assert not any(c.isdigit() for c in sentence), shape


# =================================================================================================
# The anchor's own events survive selection
# =================================================================================================

def test_the_anchors_own_events_are_kept_even_when_the_model_omits_them():
    """A narrative that drops the event the situation is about is a story about something else,
    and the model has no way of knowing which event that is."""
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       anchor_event_ids=["evt_a"],
                       ask=_ask(event_ids=["evt_c"], shape="silent_since"), viewer_email=READER)
    assert [e.event_id for e in narrated.selected] == ["evt_a", "evt_c"]


def test_an_empty_selection_falls_back_rather_than_rendering_nothing():
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       ask=_ask(event_ids=[], shape="steady"), viewer_email=READER)
    assert narrated.fallback_reason == FALLBACK_EMPTY_SELECTION


# =================================================================================================
# The fallback is a real path, logged
# =================================================================================================

def test_no_model_publishes_the_unnarrated_chronology():
    narrated = narrate(_events(), situation_type="commitment_unresolved", eval_time=EVAL_TIME,
                       viewer_email=READER)
    assert narrated.fallback is True
    assert narrated.fallback_reason == FALLBACK_NO_MODEL
    assert [e.event_id for e in narrated.chronology] == ["evt_a", "evt_b", "evt_c"]
    assert narrated.sentence == "", "a plainer card, not a wrong one"


def test_a_model_that_raises_falls_back_and_is_logged(caplog):
    import logging

    def explodes(_prompt):
        raise RuntimeError("budget exhausted")
    with caplog.at_level(logging.INFO, logger="genios.context.framing.timeline"):
        narrated = narrate(_events(), situation_type="commitment_unresolved",
                           eval_time=EVAL_TIME, ask=explodes, viewer_email=READER)
    assert narrated.fallback_reason == FALLBACK_MODEL_ERROR
    assert FALLBACK_MODEL_ERROR in caplog.text


def test_an_empty_timeline_is_representable(caplog):
    narrated = narrate([], situation_type="commitment_unresolved", eval_time=EVAL_TIME)
    assert narrated.chronology == ()
    assert narrated.fallback is True


def test_the_module_reads_no_clock():
    from pathlib import Path

    import genios_engine.context.framing.timeline as module
    source = Path(module.__file__).read_text()
    assert "datetime.now(" not in source and "utcnow(" not in source

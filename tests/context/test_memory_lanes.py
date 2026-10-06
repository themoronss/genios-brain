"""STEP-05 · which road a kept event takes into memory.

    pytest tests/context/test_memory_lanes.py -q

Tree `yc2_w27_s05 · M23.C1.L-contract.V0.U01`. One pure function decides it, so the pull, the drain and
the checks cannot disagree about which kept event belongs in memory and how.
"""
from __future__ import annotations

import pytest

from genios_engine.context.memory_lanes import KEPT_OUTCOMES, SCREEN_SOURCE, Lane, lane_for


def _lane(outcome="emitted", source="gmail", structured=False, has_signal=False,
          has_extraction=False):
    return lane_for(outcome=outcome, source=source, structured=structured,
                    has_signal=has_signal, has_extraction=has_extraction)


def test_a_mail_with_a_signal_enters_as_before():
    assert _lane(has_signal=True, has_extraction=True) is Lane.SIGNAL


def test_a_mail_the_floor_did_not_publish_enters_with_its_words():
    """Read by L1, no signal: its extraction is the road (06 D20)."""
    assert _lane(has_extraction=True) is Lane.BELOW_FLOOR


def test_a_mail_not_yet_read_waits_for_the_re_read():
    assert _lane() is None


def test_an_archived_mail_enters_as_metadata_whatever_it_has():
    for has_signal in (False, True):
        for has_extraction in (False, True):
            assert _lane(outcome="archived", has_signal=has_signal,
                         has_extraction=has_extraction) is Lane.METADATA


def test_a_calendar_event_is_always_a_meeting():
    """Signal or not — a meeting is not a deadline that expires."""
    for has_signal in (False, True):
        assert _lane(source="gcal", structured=True, has_signal=has_signal) is Lane.CALENDAR


def test_a_screen_session_enters_only_through_its_signal():
    """A screen never creates memory of a person on its own (06 D22)."""
    assert _lane(source=SCREEN_SOURCE, has_extraction=True) is None
    assert _lane(source=SCREEN_SOURCE, outcome="archived") is None
    assert _lane(source=SCREEN_SOURCE, has_signal=True) is Lane.SIGNAL


@pytest.mark.parametrize("outcome", ["parked", "dropped", "superseded", "duplicate", None])
def test_what_is_not_kept_takes_no_road(outcome):
    assert _lane(outcome=outcome, has_signal=True, has_extraction=True) is None
    assert outcome not in KEPT_OUTCOMES


def test_the_screen_source_is_the_one_the_screen_writes():
    from genios_engine.capture.screen.render import SOURCE as RENDERED
    from genios_engine.platform.screen_promoter import SOURCE as PROMOTED

    assert SCREEN_SOURCE == RENDERED == PROMOTED

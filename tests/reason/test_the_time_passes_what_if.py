"""STEP-12 · the time-passes what-if — what doing nothing for N days does to a file.

    pytest tests/reason/test_the_time_passes_what_if.py -q

`reason/simulation.time_passes` (tree `yc2_w27_s12` M32.C2.L-logic.V1.U08, `06` D39 — added by
`yc2_w27_align` M34.C4). `simulate` answers a counterfactual in the formula's utilities and needs a
finished decision to start from, so it could not say the one scenario every file has: nothing happens.
This does, from the file's own numbers — no model, no I/O: after N days of nothing the file has been
quiet so long; against its playbook's stop rule (a prior, cited) it is or is not dormant, and how many
days of nothing are left before it is; whether the next date passes; which open situations go past the
window their kind holds them to; and the playbook's own words for what doing nothing costs, labelled a
prior. Every number it says comes from what it was handed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.workstreams import Lifecycle, SituationLife
from genios_engine.reason.simulation import TIME_STEPS, TimePasses, time_passes, what_if_nothing

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
CONSEQUENCE = "The fund moves on to the next deal in the pipeline."


def _situation(sid: str, *, quiet: float, window: int = 45, status: str = "active") -> SituationLife:
    return SituationLife(situation_id=sid, situation_type="investor_relationship",
                         domain="founder_office", status=status, first_seen_at=None,
                         last_seen_at=NOW - timedelta(days=quiet), days_seen=None,
                         days_since_seen=quiet, quiet_window_days=window, window_from="kind",
                         past_window=quiet > window if status == "active" else None)


def _life(*situations: SituationLife) -> Lifecycle:
    return Lifecycle(file_id="node_fund", situations=situations)


def _ask(days: int, **over) -> TimePasses:
    kw = dict(days=days, now=NOW, quiet_days=10.0, stop_after_days=90,
              stop_cited="practitioner judgement — 90 days", do_nothing=CONSEQUENCE,
              lifecycle=_life(), next_date=None)
    kw.update(over)
    return time_passes(**kw)


def test_n_days_of_nothing_against_the_stop_rule():
    """⛔ MOVED 2026-10-11, deliberately: the days left before dormant are counted AFTER the N days of
    nothing — the scenario's own state. Counted from today they were the same number at 3, 7 and 14
    days (80 each here), which is what this test pinned until the golden authoring read it."""
    w = _ask(7)
    assert (w.quiet_days_then, w.dormant_then, w.days_to_dormant) == (17.0, False, 73.0)
    late = _ask(7, quiet_days=85.0)
    assert (late.quiet_days_then, late.dormant_then, late.days_to_dormant) == (92.0, True, 0.0)
    gone = _ask(3, quiet_days=120.0)
    assert (gone.dormant_then, gone.days_to_dormant) == (True, 0.0)
    steps = [_ask(n).days_to_dormant for n in (3, 7, 14)]
    assert steps == [77.0, 73.0, 66.0], "each step says what is left after it"
    assert "73 more days of nothing before it is" in w.says


def test_without_a_stop_rule_or_a_touch_nothing_is_claimed():
    no_rule = _ask(7, stop_after_days=None, stop_cited=None)
    assert (no_rule.dormant_then, no_rule.days_to_dormant) == (None, None)
    assert "no stop rule" in no_rule.says
    untouched = _ask(7, quiet_days=None)
    assert (untouched.quiet_days_then, untouched.dormant_then) == (None, None)


def test_whether_the_next_date_passes():
    in_five = NOW + timedelta(days=5)
    assert _ask(7, next_date=in_five).passes_next_date is True
    assert _ask(3, next_date=in_five).passes_next_date is False
    assert _ask(7).passes_next_date is None


def test_which_open_situations_go_past_their_window():
    life = _life(_situation("sit_close", quiet=40.0), _situation("sit_fresh", quiet=2.0),
                 _situation("sit_already", quiet=50.0),
                 _situation("sit_done", quiet=200.0, status="resolved"))
    w = _ask(7, lifecycle=life)
    assert w.situations_past_window == ("sit_already", "sit_close")


def test_the_playbooks_words_for_doing_nothing_are_carried_as_its_prior():
    w = _ask(7)
    assert w.do_nothing == CONSEQUENCE and w.stop_cited == "practitioner judgement — 90 days"
    assert "a prior" in w.says
    assert _ask(7, do_nothing=None).do_nothing is None


def test_every_number_said_is_one_it_was_handed_or_computed_from_them():
    import re
    w = _ask(7, quiet_days=85.0, next_date=NOW + timedelta(days=5))
    allowed = {"7", "85", "92", "90", "5"}
    assert set(re.findall(r"\d+", w.says)) <= allowed, w.says


def test_the_steps_are_the_dossiers():
    steps = what_if_nothing(now=NOW, quiet_days=10.0, stop_after_days=90, stop_cited="cited",
                            do_nothing=None, lifecycle=_life(), next_date=None)
    assert [w.days for w in steps] == list(TIME_STEPS) and TIME_STEPS == (3, 7, 14)


@pytest.mark.parametrize("days", [0, -1, 1.5, True])
def test_n_is_a_positive_whole_number_of_days(days):
    with pytest.raises(ValueError, match="days"):
        _ask(days)


def test_the_what_if_is_plain_data():
    import json
    body = _ask(7, next_date=NOW + timedelta(days=5)).as_dict()
    assert json.loads(json.dumps(body)) == body
    assert body["next_date"] == (NOW + timedelta(days=5)).isoformat()

"""STEP-02 · what a fingerprint is made of, beyond the decision's own request.

    pytest tests/reason/test_material_inputs_contract.py -q

`reason/fingerprint.MaterialInputs` and the clock ladders (tree `yc2_w27_s02/M20.C1.L-contract.V0.U01`).

The request a lane hands the decider already carries what the decision reads — measured: on all 40
golden cases, a request repeated on a sweep that brought nothing new is identical once time is taken
out (`speedrun008/YC-II W27/` STEP-02 §8). Two things can change the right answer without touching
that request, and they are carried beside it: the pack's `authority_revision` (a calibration or a
pack change), and the human verdicts on the subject's cards.

A clock is compared by its rung, never its value: deadline hours on Layer 4's own urgency ladder
(`timeline_unit.URGENCY_LADDER`, one source), elapsed days on the days ladder — so 6 → 7 days
waiting re-decides, and 15 minutes never does.
"""
from __future__ import annotations

import dataclasses

import pytest

from genios_engine.reason import fingerprint as fp
from genios_engine.reason.reasoners.timeline_unit import URGENCY_LADDER


def test_the_hour_ladder_is_layer_4s_urgency_ladder():
    assert fp.HOUR_LADDER == tuple(hours for hours, _ in URGENCY_LADDER)


@pytest.mark.parametrize("ladder", [fp.HOUR_LADDER, fp.DAY_LADDER])
def test_a_ladder_starts_at_zero_and_only_climbs(ladder):
    assert ladder[0] == 0 and list(ladder) == sorted(set(ladder))


def test_seven_days_is_a_rung_and_six_is_not():
    """STEP-02 §4: *"Theresa's wait crosses from 6 to 7 days"* must re-decide."""
    assert 7 in fp.DAY_LADDER and 6 not in fp.DAY_LADDER


def test_material_inputs_are_frozen_and_hold_their_verdicts_in_one_order():
    inputs = fp.MaterialInputs(authority_revision=3, verdicts=("fb_2:1", "fb_1:2", "fb_2:1"))
    assert inputs.verdicts == ("fb_1:2", "fb_2:1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        inputs.authority_revision = 4          # type: ignore[misc]


def test_no_inputs_is_a_value_too():
    assert fp.MaterialInputs() == fp.MaterialInputs(authority_revision=None, verdicts=(),
                                                    decider="formula")


def test_a_verdict_key_is_a_feedback_id_and_its_version():
    assert fp.verdict_key("fb_9", 2) == "fb_9:2"
    with pytest.raises(ValueError):
        fp.verdict_key("", 1)

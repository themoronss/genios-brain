"""STEP-11 · a playbook's stages become stage priors — a duration with its source, never a habit.

    .venv/bin/python -m pytest tests/packs/test_a_stage_prior_is_never_a_habit.py -q

Tree `yc2_w27_s11 · M30.C2.L-logic.V1.U03`, `06` D37. A stage's typical duration is a profession's
usual value, not a measurement of this founder: it travels as a `Measured` whose source is
`playbook_prior`, resting on no observation here (n = 0), never `normal`, and saying so in its own
words; and its citation travels beside it.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.measured import PLAYBOOK_PRIOR
from genios_engine.packs.compiler.stage_priors import stage_priors

PLAYBOOK = {
    "identity": {"id": "founder_office.pb.program_applications.follow_an_application"},
    "stages": [
        {"name": "applied", "label": "Applied", "typical_duration_days": 21,
         "quiet_means": "Nothing — programmes review in batches.",
         "leaves_when": "An interview invitation or a decision arrives.",
         "source": "https://www.ycombinator.com/apply"},
        {"name": "under_review", "typical_duration_days": 14, "source": "a named reference"},
        {"name": "onboarding", "typical_duration_days": 0, "source": "terminal stage"},
    ],
}


def test_the_stages_come_back_in_the_playbook_s_order_with_their_words():
    stages = stage_priors(PLAYBOOK)
    assert [s.name for s in stages] == ["applied", "under_review", "onboarding"]
    first = stages[0]
    assert (first.label, first.quiet_means, first.leaves_when, first.cited) == (
        "Applied", "Nothing — programmes review in batches.",
        "An interview invitation or a decision arrives.", "https://www.ycombinator.com/apply")


def test_a_duration_is_a_prior_resting_on_nothing_measured_here():
    for stage in stage_priors(PLAYBOOK):
        assert stage.typical.source == PLAYBOOK_PRIOR
        assert stage.typical.n == 0
        assert stage.typical.unit == "days"
        assert stage.typical.normal is False
        assert stage.typical.basis == ("playbook founder_office.pb.program_applications."
                                       "follow_an_application")
    assert stage_priors(PLAYBOOK)[0].typical.value == 21


def test_its_words_never_call_it_usual():
    words = [s.typical.says() for s in stage_priors(PLAYBOOK)]
    assert words[0] == "21 days — a playbook's prior, not measured here"
    assert not any("usually" in w or "normal" in w for w in words)


def test_an_unlabelled_stage_is_read_by_its_name():
    assert stage_priors(PLAYBOOK)[1].label == "under review"
    assert stage_priors(PLAYBOOK)[1].quiet_means is None


def test_a_playbook_without_stages_has_none():
    assert stage_priors({"identity": {"id": "x.pb.y.z"}}) == ()


@pytest.mark.parametrize("broken", [
    {"name": "applied", "typical_duration_days": 21},                        # no source
    {"name": "applied", "typical_duration_days": 21, "source": "   "},       # a blank source
    {"typical_duration_days": 21, "source": "s"},                             # no name
    {"name": "applied", "source": "s"},                                       # no duration
    {"name": "applied", "typical_duration_days": 2.5, "source": "s"},         # not whole days
    {"name": "applied", "typical_duration_days": -1, "source": "s"},          # negative
    {"name": "applied", "typical_duration_days": True, "source": "s"},        # a bool is no number
])
def test_a_stage_without_its_prior_or_its_source_is_refused(broken):
    with pytest.raises(ValueError):
        stage_priors({"identity": {"id": "x.pb.y.z"}, "stages": [broken]})


def test_a_stage_declared_twice_is_refused():
    twice = {"name": "applied", "typical_duration_days": 1, "source": "s"}
    with pytest.raises(ValueError, match="twice"):
        stage_priors({"identity": {"id": "x.pb.y.z"}, "stages": [twice, dict(twice)]})


def test_the_read_model_shape_carries_the_prior_s_own_words():
    as_dict = stage_priors(PLAYBOOK)[0].as_dict()
    assert as_dict["typical"]["says"] == "21 days — a playbook's prior, not measured here"
    assert as_dict["typical"]["source"] == PLAYBOOK_PRIOR
    assert as_dict["cited"] == "https://www.ycombinator.com/apply"

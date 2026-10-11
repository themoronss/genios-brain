"""STEP-12 · the stage's dwell — the stage is the expert's, the dwell code's, against its playbook's prior.

    pytest tests/reason/expert/test_the_stage_dwell.py -q

`reason/expert/stage_dwell.py` (tree `yc2_w27_s12` M32.C3.L-logic.V2.U07, `06` D39, STEP-11 §4). Once a review
names the file's stage, code measures how long the file has been there: from the earliest touch of the file
the review cites for a fact, to the dossier's as-of, in days — set against the playbook's typical duration
for that stage, which is a PRIOR and says so, never "normal" (D37). No stage, no playbook, a stage the
playbook does not have, or no cited touch: no dwell, and why.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import stage_dwell as SD
from tests.reason.expert.test_the_dossier import NOW, _parts, _review

pytestmark = pytest.mark.unit


def _with(review: ExpertReview, **eva) -> ExpertReview:
    return dataclasses.replace(review, expected_vs_actual=dataclasses.replace(
        review.expected_vs_actual, **eva))


def _citing(*evidence: str) -> ExpertReview:
    review = _review(evidence[0], "Hi Kunal, booking it now.")
    facts = tuple(dataclasses.replace(review.facts[0], evidence=(e,)) for e in evidence)
    return dataclasses.replace(review, facts=facts)


def test_the_dwell_counts_from_the_stages_first_cited_touch():
    """`_parts`' touches are evt_000, evt_003 and evt_005 — 60 days before NOW, plus 0, 3, 5 hours."""
    dwell = SD.stage_dwell(_citing("evt_005", "evt_003"), _parts())
    assert (dwell.stage, dwell.label, dwell.since_event) == ("first_call", "First call", "evt_003")
    assert dwell.since == NOW - timedelta(days=60) + timedelta(hours=3)
    assert dwell.days == round((NOW - dwell.since).total_seconds() / 86400, 2) == 59.88


def test_against_its_playbooks_prior_which_says_it_is_one():
    dwell = SD.stage_dwell(_citing("evt_000"), _parts())
    assert dwell.prior.value == 21 and dwell.beyond_prior is True
    assert dwell.says() == ("First call: 60 days since evt_000 — the playbook's prior for it: "
                            "21 days — a playbook's prior, not measured here")
    assert "normal" not in dwell.says()


def test_within_its_prior_is_not_beyond_it():
    parts = _parts()
    early = dataclasses.replace(parts, as_of=parts.timeline.touches[0].at + timedelta(days=4))
    assert SD.stage_dwell(_citing("evt_000"), early).beyond_prior is False


def test_what_is_not_a_touch_of_the_file_is_never_the_start():
    """A loop, a number or a playbook line may be cited for a fact; only a touch has a date here."""
    dwell = SD.stage_dwell(_citing("num:replied", "evt_005", "pb:founder_office.pb.investor.move_0"),
                           _parts())
    assert dwell.since_event == "evt_005"


@pytest.mark.parametrize("review, parts, why", [
    (_with(_citing("evt_005"), stage=None), _parts(), "names no stage"),
    (_citing("evt_005"), _parts(playbook=dataclasses.replace(
        _parts().playbook, playbook=None, reason="no_kind")), "has no playbook"),
    (_with(_citing("evt_005"), stage="term_sheet"), _parts(), "not a stage of its playbook"),
    (_citing("num:replied"), _parts(), "cites no touch of the file"),
])
def test_no_dwell_says_why(review, parts, why):
    assert SD.stage_dwell(review, parts) is None
    assert why in SD.why_no_dwell(review, parts)

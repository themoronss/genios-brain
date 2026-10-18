"""STEP-11 · a playbook may declare its stages, each with a sourced prior; and what success and doing nothing are.

    .venv/bin/python -m pytest tests/corpus/test_a_playbook_declares_its_stages.py -q

Tree `yc2_w27_s11 · M30.C2.L-contract.V0.U01`. STEP-11 §8.2 measured three runtime values the corpus could
not state: the consequence of doing nothing was a template sentence, the outcome window a 7-day default,
the success signal NULL; and no stage existed anywhere, so STEP-10's stage dwell had nothing to count
against. The schema now lets a PLAYBOOK declare its stages — each with a typical duration that is a
prior and names its source, what quiet means at that stage, and the event that ends it — its
`success_signal` and its `outcome_window_days`; and a SITUATION its `do_nothing_consequence`. Validated
by the corpus's own validators (`_tools/validate.build_validators`), so the authoring tool and this test
cannot disagree. A playbook may also say what doing nothing costs: a capability no Layer 2 type routes
(a programme, an introduction, a hire) has no situation to say it, and `playbook_for` reads it there.
The four fields are a playbook's alone, and none of them may be an empty sentence.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "Domain Expertise" / "_tools"

PLAYBOOK = {
    "identity": {"id": "founder_office.pb.program_applications.follow_an_application",
                 "name": "Follow an application", "kind": "playbook", "domain": "founder_office",
                 "scope": "capability",
                 "owner_capability": "founder_office.programs_and_applications.program_applications",
                 "version": "0.1.0", "status": "draft"},
    "purpose": {"statement": "Carry an application from submission to a decision."},
    "when_to_use": {"signals": ["An application was submitted."]},
    "steps": [{"order": 1, "name": "Note the decision date", "done_when": "The date is on file."}],
    "stages": [
        {"name": "submitted", "label": "Submitted", "typical_duration_days": 21,
         "quiet_means": "Nothing — programmes review in batches.",
         "leaves_when": "An interview invitation or a decision arrives.",
         "source": "https://www.ycombinator.com/apply"},
        {"name": "interview", "typical_duration_days": 7, "source": "a named reference"},
    ],
    "success_signal": "The programme's decision mail arrives.",
    "outcome_window_days": 30,
    "do_nothing_consequence": "The cohort fills and the next intake is six months away.",
    "metadata": {"owner": "Founder Office", "last_updated": "2026-10-09",
                 "review_status": "unreviewed"},
}


@pytest.fixture(scope="module")
def validators():
    sys.path.insert(0, str(TOOLS))
    try:
        import validate
        return validate.build_validators()
    finally:
        sys.path.remove(str(TOOLS))


def _errors(validator, doc) -> list[str]:
    return [e.message for e in validator.iter_errors(doc)]


def test_a_playbook_declares_its_stages_success_and_window(validators):
    assert _errors(validators["artifact"], PLAYBOOK) == []


@pytest.mark.parametrize("field", ["typical_duration_days", "source", "name"])
def test_a_stage_without_its_prior_or_its_source_is_refused(validators, field):
    doc = copy.deepcopy(PLAYBOOK)
    del doc["stages"][0][field]
    assert _errors(validators["artifact"], doc), f"a stage with no {field} was accepted"


def test_an_empty_source_is_no_source(validators):
    doc = copy.deepcopy(PLAYBOOK)
    doc["stages"][1]["source"] = ""
    assert _errors(validators["artifact"], doc), "a prior with an empty source was accepted"


def test_a_stage_name_is_an_id_and_a_duration_is_whole_days(validators):
    doc = copy.deepcopy(PLAYBOOK)
    doc["stages"][0]["name"] = "Under Review"
    doc["stages"][1]["typical_duration_days"] = 2.5
    assert len(_errors(validators["artifact"], doc)) == 2


def test_a_window_is_at_least_a_day_and_a_stage_list_is_never_empty(validators):
    doc = copy.deepcopy(PLAYBOOK)
    doc["outcome_window_days"] = 0
    doc["stages"] = []
    assert len(_errors(validators["artifact"], doc)) == 2


def test_an_unknown_stage_field_is_refused(validators):
    doc = copy.deepcopy(PLAYBOOK)
    doc["stages"][0]["normal_days"] = 21
    assert _errors(validators["artifact"], doc)


@pytest.mark.parametrize("field", ["success_signal", "do_nothing_consequence"])
def test_an_empty_sentence_is_no_sentence(validators, field):
    doc = copy.deepcopy(PLAYBOOK)
    doc[field] = ""
    assert _errors(validators["artifact"], doc), f"an empty {field} was accepted"


@pytest.mark.parametrize("field", ["stages", "success_signal", "outcome_window_days",
                                   "do_nothing_consequence"])
def test_only_a_playbook_carries_them(validators, field):
    """A heuristic is a claim, not a procedure: it has no stages and no outcome to wait for."""
    heuristic = {
        "identity": {"id": "founder_office.heu.program_applications.batches_decide_late",
                     "name": "Batches decide late", "kind": "heuristic", "domain": "founder_office",
                     "scope": "capability",
                     "owner_capability": "founder_office.programs_and_applications.program_applications",
                     "version": "0.1.0", "status": "draft"},
        "purpose": {"statement": "Why a programme's silence in review is not a no."},
        "heuristic": {"statement": "A programme that reviews in batches is silent until the batch decides.",
                      "why": "Reviewers read a cohort's applications together, not one by one."},
        "metadata": {"owner": "Founder Office", "last_updated": "2026-10-09",
                     "review_status": "unreviewed"},
    }
    assert _errors(validators["artifact"], heuristic) == [], "the heuristic itself must be valid"
    heuristic[field] = copy.deepcopy(PLAYBOOK[field])
    assert _errors(validators["artifact"], heuristic), f"a heuristic carrying {field} was accepted"


def test_a_situation_states_what_doing_nothing_costs(validators):
    situation = {
        "identity": {"id": "founder_office.sit.application_in_flight", "name": "Application in flight",
                     "domain": "founder_office",
                     "owner_capability": "founder_office.programs_and_applications.program_applications",
                     "version": "0.1.0", "status": "draft"},
        "description": "An application waits on a programme's decision.",
        "matches": {"l2_situation_types": ["condition_in_review"]},
        "objects": {"load": []},
        "do_nothing_consequence": "The cohort fills and the next intake is six months away.",
        "metadata": {"owner": "Founder Office", "last_updated": "2026-10-09",
                     "review_status": "unreviewed"},
    }
    def about_it():
        """Only the errors AT the field — the fixture's other gaps are not this test's business."""
        return [e.message for e in validators["situation"].iter_errors(situation)
                if "do_nothing_consequence" in e.absolute_path
                or "do_nothing_consequence" in e.message]

    assert about_it() == []
    situation["do_nothing_consequence"] = ""
    assert about_it(), "a situation's empty do-nothing sentence was accepted"

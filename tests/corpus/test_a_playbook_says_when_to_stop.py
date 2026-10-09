"""STEP-11 · a playbook says when its kind of work is dormant — a prior with its source (`06` D33).

    .venv/bin/python -m pytest tests/corpus/test_a_playbook_says_when_to_stop.py -q

Tree `yc2_w27_s11 · M30.C2.L-contract.V0.U05`. Every file went dormant after 45 quiet days (STEP-09),
whatever its kind of work: an investor between cycles and an introduction nobody followed up read the
same. D33 moved the number into the playbooks — *"each playbook's stop rule, authored as a labelled
prior"* — and the playbook contract of 9 Oct (M30.C2.L-contract.V0.U01) had no field to say it in.
A playbook may now declare `stop`: `dormant_after_days`, the `source` of that number, and `then`, what
a professional does with a dormant file. Validated by the corpus's own validators.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "Domain Expertise" / "_tools"

PLAYBOOK = {
    "identity": {"id": "founder_office.pb.investor_relations.follow_a_round",
                 "name": "Follow a round", "kind": "playbook", "domain": "founder_office",
                 "scope": "capability",
                 "owner_capability": "founder_office.fundraising.investor_relations",
                 "version": "0.1.0", "status": "draft"},
    "purpose": {"statement": "Carry an investor conversation from first contact to a decision."},
    "when_to_use": {"signals": ["An investor replied."]},
    "steps": [{"order": 1, "name": "Name the next step", "done_when": "It is on file."}],
    "stop": {"dormant_after_days": 90,
             "source": "practitioner judgement — unverified; for the founder's review",
             "then": "Let it rest; re-approach at the next fund cycle or a real milestone."},
    "metadata": {"owner": "Founder Office", "last_updated": "2026-10-09",
                 "review_status": "unreviewed"},
}


@pytest.fixture(scope="module")
def validator():
    sys.path.insert(0, str(TOOLS))
    try:
        import validate
        return validate.build_validators()["artifact"]
    finally:
        sys.path.remove(str(TOOLS))


def _errors(validator, doc) -> list[str]:
    return [e.message for e in validator.iter_errors(doc)]


def test_a_playbook_says_when_its_work_is_dormant(validator):
    assert _errors(validator, PLAYBOOK) == []


@pytest.mark.parametrize("field", ["dormant_after_days", "source"])
def test_a_stop_rule_without_its_number_or_its_source_is_refused(validator, field):
    doc = copy.deepcopy(PLAYBOOK)
    del doc["stop"][field]
    assert _errors(validator, doc), f"a stop rule with no {field} was accepted"


@pytest.mark.parametrize("field, value", [("dormant_after_days", 0), ("dormant_after_days", 4.5),
                                          ("source", ""), ("then", "")])
def test_a_stop_rule_s_values_are_real(validator, field, value):
    doc = copy.deepcopy(PLAYBOOK)
    doc["stop"][field] = value
    assert _errors(validator, doc), f"stop.{field} = {value!r} was accepted"


def test_an_unknown_stop_field_is_refused(validator):
    doc = copy.deepcopy(PLAYBOOK)
    doc["stop"]["normal_days"] = 45
    assert _errors(validator, doc)


def test_only_a_playbook_says_when_to_stop(validator):
    heuristic = {
        "identity": {"id": "founder_office.heu.investor_relations.investors_do_not_chase",
                     "name": "Investors do not chase", "kind": "heuristic",
                     "domain": "founder_office", "scope": "capability",
                     "owner_capability": "founder_office.fundraising.investor_relations",
                     "version": "0.1.0", "status": "draft"},
        "purpose": {"statement": "Why a quiet investor thread is evidence about us, not about them."},
        "heuristic": {"statement": "When the turn is ours, the clock is running against us.",
                      "why": "A fund loses nothing by dropping one company."},
        "metadata": {"owner": "Founder Office", "last_updated": "2026-10-09",
                     "review_status": "unreviewed"},
    }
    assert _errors(validator, heuristic) == []
    heuristic["stop"] = copy.deepcopy(PLAYBOOK["stop"])
    assert _errors(validator, heuristic), "a heuristic carrying a stop rule was accepted"

"""STEP-12 · every file a case's sweeps review has the expert's answer, authored for it by Claude (`06` D49).

    pytest tests/replays/test_every_changed_file_has_an_expert_answer.py -q [-k board_cases]

Tree `yc2_w27_s12` M32.C5.L-data.V1.U02 (`board_cases`: every must-detect case the board fails today and every
must-abstain case) and V1.U03 (every other case). Which files a case's sweeps review is MEASURED, not guessed:
`tests/replays/expert_files.json`, written by a run of every case with the expert switched on — its other model
sites answered from their cassettes, the expert's own prompts by the ideal reader from these very answers, as the
recording will answer them — for each file, the ids its first dossier offered to cite, the stages its playbook
lists, and how many prompts the run asked. Each case's `model.expert` answers exactly those files, or declares why it does not, and each
answer is one the review contract parses, marked `claude`, naming its file as its dossier does (`<key>`), citing
only what that first dossier offered, naming only a listed stage, and writing no digit at all — so it can
never be refused for a number its dossier does not hold. What the ideal reader then serves, and what the
review run makes of it, the golden lane and M32.C5.L-integration.V3.U05 measure on the real chain.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from genios_engine.contracts.expert_review import ExpertReview, number_tokens
from tests.replays.founder_case import load_cases

pytestmark = pytest.mark.unit

FILES = json.loads((Path(__file__).parent / "expert_files.json").read_text())
CASES = {case.case_id: case for case in load_cases()}

#: The board's state on 10 Oct (`03` §F.1): the must-detect cases it fails — at the gate, in reasoning,
#: with no stage to read — and the must-abstain one it fails. With every must-abstain case, V1.U02's set.
FAILING_MUST_DETECT = ("F01", "F02", "F07", "F09", "F11", "F15", "F16", "F17", "F19", "F24", "F27", "F29",
                       "F47", "F48", "F49", "F50", "F51", "F52", "F54", "F56", "F57")
BOARD_CASES = tuple(sorted(set(FAILING_MUST_DETECT) | {c for c, case in CASES.items()
                                                       if case.kind == "must_abstain"}))
OTHER_CASES = tuple(sorted(set(CASES) - set(BOARD_CASES)))
_KEY = re.compile(r"^<([^<>\s]+)>$")


def _entries(case_id: str) -> list[dict]:
    return list((CASES[case_id].model or {}).get("expert") or ())


def _check(case_id: str) -> None:
    files = FILES[case_id]
    entries = _entries(case_id)
    declared = dict((CASES[case_id].model or {}).get("expert_declared") or {})
    answered, general = set(), []
    for entry in entries:
        assert entry.get("by") == "claude", f"{case_id}: an expert answer is marked claude (D49)"
        keys = [m.group(1) for t in entry.get("when") or () if (m := _KEY.match(str(t)))]
        assert len(keys) == 1, f"{case_id}: an expert answer names its file once, as <key>: {entry['when']}"
        key = keys[0]
        assert key in files, f"{case_id}: <{key}> is no file its sweeps review: {sorted(files)}"
        answered.add(key)
        review = ExpertReview.from_mapping(entry["answer"])            # the contract parses it
        if len(entry["when"]) == 1:
            # The general entry answers the file's FIRST review: it cites only what that dossier
            # offered. A narrower one answers a later dossier only, and is held to it on the chain.
            general.append(key)
            offered = set(files[key]["evidence"])
            cited = {e for f in review.facts for e in f.evidence}
            cited |= {e for i in (*review.inferences, *review.patterns) for e in i.based_on
                      if not e.startswith("fact:")}
            if review.proposed_kind is not None:
                cited |= set(review.proposed_kind.evidence)
            assert cited <= offered, f"{case_id} <{key}>: cites what its first dossier never " \
                                     f"offered: {sorted(cited - offered)}"
        stage = review.expected_vs_actual.stage
        assert stage is None or stage in files[key]["stages"], f"{case_id} <{key}>: stage {stage!r}"
        digits = sorted(set().union(*(number_tokens(t) for t in review.texts())))
        assert not digits, f"{case_id} <{key}>: writes numbers {digits} — write none"
    assert sorted(general) == sorted(set(general)) and set(general) == answered, \
        f"{case_id}: every answered file has exactly one general entry: {sorted(general)}"
    missing = set(files) - answered - set(declared)
    assert not missing, f"{case_id}: files its sweeps review with no expert answer: {sorted(missing)}"
    for key, why in declared.items():
        assert key in files and len(str(why).split()) >= 5, f"{case_id}: <{key}> is declared with a reason"


def test_every_case_is_measured():
    assert set(FILES) == set(CASES)


@pytest.mark.parametrize("case_id", BOARD_CASES)
def test_board_cases(case_id):
    _check(case_id)


@pytest.mark.parametrize("case_id", OTHER_CASES)
def test_other_cases(case_id):
    _check(case_id)

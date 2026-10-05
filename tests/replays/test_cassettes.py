"""STEP-01 · a case's cassette: written once, replayed exactly, never carrying a real name.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/replays/test_cassettes.py -q

One JSON file per founder case beside the specs. It holds the model's answers keyed by the
prompt's hash, and says what wrote them (the ideal reader, or a named live model) and at which
commit — so a reader of the board knows whether a number came from authored answers or from the
model, which is the difference `D12c` asks about.
"""
from __future__ import annotations

import copy
import json
import os

import pytest

from tests.replays import cassettes
from tests.replays import founder_case as fc
from tests.replays.test_engine_runner import CASE

needs_db = pytest.mark.skipif(not os.environ.get("GENIOS_TEST_DATABASE_URL"),
                              reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _case() -> fc.FounderCase:
    return fc.parse_case(copy.deepcopy(CASE), source="test.json")


ANSWER = {"site": "relevance", "parsed": {"verdicts": []}, "raw": "{}", "input_tokens": 3,
          "output_tokens": 1, "model": "claude-haiku-4-5-20251001"}


def test_a_cassette_round_trips_with_what_wrote_it(tmp_path):
    case = _case()
    path = cassettes.save(case, {"ab" * 32: ANSWER}, source=cassettes.IDEAL_READER,
                          folder=tmp_path)
    assert path == tmp_path / "F97.json"
    stored = json.loads(path.read_text())
    assert stored["case_id"] == "F97" and stored["source"] == cassettes.IDEAL_READER
    assert stored["recorded_at"] and len(stored["answers"]) == 1
    assert cassettes.load(case, folder=tmp_path) == {"ab" * 32: ANSWER}
    assert cassettes.source_of(case, folder=tmp_path) == cassettes.IDEAL_READER


def test_a_missing_cassette_names_the_case_and_how_to_record_it(tmp_path):
    with pytest.raises(AssertionError, match="F97.*golden_eval.py --record"):
        cassettes.load(_case(), folder=tmp_path)


def test_a_real_name_in_an_answer_is_refused(tmp_path):
    leaked = dict(ANSWER, parsed={"headline": "Reply to Khushi"})
    with pytest.raises(fc.CaseError, match="Khushi"):
        cassettes.save(_case(), {"cd" * 32: leaked}, source=cassettes.IDEAL_READER,
                       folder=tmp_path)


def test_a_source_is_the_ideal_reader_or_a_named_live_model(tmp_path):
    with pytest.raises(ValueError, match="source"):
        cassettes.save(_case(), {}, source="vibes", folder=tmp_path)
    cassettes.save(_case(), {}, source="live:claude-haiku-4-5-20251001", folder=tmp_path)


@pytest.mark.pg
@needs_db
def test_a_recorded_case_replays_with_no_miss(tmp_path):
    case = _case()
    run, answers = cassettes.record(case)
    assert answers and not run.misses
    cassettes.save(case, answers, source=cassettes.IDEAL_READER, folder=tmp_path)
    replayed = cassettes.replay(case, folder=tmp_path)
    assert replayed.misses == () and replayed.chain_ok == run.chain_ok
    assert sorted(replayed.model_calls) == sorted(run.model_calls)

"""G4 · the golden corpus — Wave W4, the graded half.

    python scripts/extract_golden.py --set tests/golden/l1/          # the gate command
    pytest tests/golden/l1 -q                                        # this file, hermetic

    expected commitments detected                        >= 90%
    emitted evidence spans that verify                   >= 95%
    fabricated amounts (Money not literally in source)   0 — HARD FAIL
    the doc-04 worked example                            passes exactly as specified
    cache hit on an unchanged re-run                     100%, zero model calls

**THE CORPUS IS PARTIAL, AND THIS FILE ASSERTS THAT IT SAYS SO.** Doc 04 specifies thirty
hand-labelled REAL messages — 15 email, 10 documents, 5 CRM notes — pulled from live connectors.
This repository has no such data, and thirty invented messages labelled by their inventor would
grade the labeller. What ships is the RUNNER plus every fixture derivable from the specification
itself: doc 04's worked example verbatim, and one message per behaviour the doc names in prose
(the polite commitment, the injection as reported speech, the MSA obligations, the CRM shorthand,
a `chat` and a `transcript` fixture the doc explicitly excludes from the gate). One test below
pins the shortfall so nobody can read a passing run as the doc's thirty-message gate.

This file runs the REPLAY lane, and the distinction is the whole reason it can live in CI: each
fixture carries the model answer it was labelled against, so what is graded here is the
EXTRACTOR — the binding, the vocabulary refusals, the date cascade, the fabrication detector, the
cache — and not any model's quality on a given afternoon. The live lane is
`scripts/extract_golden.py --live --model <snapshot>`; it costs money, needs a key, and is a
command rather than a test, because a pytest that silently skips without an API key is a gate
that reports green for the wrong reason. "A skip is not a pass" is the plan's own rule, so
nothing here skips.

The fabrication threshold is the one with no tolerance, and one fixture is a NEGATIVE CONTROL
built to prove the metric is not vacuous: its recorded answer invents `$120,000`, the extractor
deliberately does not filter it (ALG-08 does, one unit later — a filter at the extraction seam
would report zero fabrications for every prompt ever written), and the runner is required to
CATCH it. The tests below check both directions: an undeclared fabrication fails the run, and a
declared one that goes unnoticed fails it too.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.extract_golden import (
    MIN_COMMITMENT_DETECTION_BP, MIN_SPAN_VERIFICATION_BP, SPECIFIED_CORPUS_SIZE,
    GoldenCorpusError, ReplayClient, load_set, main, render, run_set)

WAVE = "W4"
GATE = "G4"

CORPUS = Path(__file__).resolve().parent


def _replay(fixture):
    return ReplayClient(fixture)


@pytest.fixture(scope="module")
def report():
    """One replay of the whole shipped corpus, reused by every threshold assertion."""
    return run_set(load_set(CORPUS), client_factory=_replay)


@pytest.fixture
def corpus_copy(tmp_path: Path) -> Path:
    """A writable copy of the corpus, for tests that must break a fixture to prove a metric."""
    target = tmp_path / "l1"
    target.mkdir()
    for path in CORPUS.glob("*.json"):
        shutil.copy(path, target / path.name)
    return target


def _edit(directory: Path, fixture_id: str, mutate) -> None:
    path = directory / f"{fixture_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# The gate itself.
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
def test_golden_corpus_meets_every_extraction_threshold(report):
    """>=90% commitments, >=95% verifying spans, zero fabricated amounts, zero calls on replay."""
    assert report.commitment_detection_bp >= MIN_COMMITMENT_DETECTION_BP, report.failures
    assert report.span_verification_bp >= MIN_SPAN_VERIFICATION_BP, report.failures
    assert report.fabricated_amounts == [], report.failures
    assert report.detector_failures == [], report.failures
    assert report.replay_calls_on_rerun == 0, report.failures
    assert report.passed, report.failures


@pytest.mark.gate
def test_the_worked_example_is_in_the_corpus_and_passes_exactly(report):
    """Doc 04 L1.4.3-U2 is a corpus member, not only a unit fixture — the same table graded by
    the same runner that grades everything else."""
    scores = {score.fixture_id: score for score in report.scores}
    worked = scores["worked_example"]
    assert worked.passed, worked.mismatches
    assert worked.commitments_detected == worked.commitments_expected == 1
    assert worked.spans_emitted == worked.spans_verifying > 0


@pytest.mark.gate
def test_every_fixture_extracted_rather_than_parking(report):
    """A parked fixture contributes no spans and no commitments, so a corpus of parks would
    report every rate as met. The extraction has to actually happen."""
    parked = [score.fixture_id for score in report.scores if not score.extracted]
    assert parked == [], f"parked: {parked}"


def test_the_report_states_that_the_corpus_is_partial(report):
    """The one number a reader must not be able to miss: this is 8 of 30, not the doc's gate."""
    assert len(report.scores) < SPECIFIED_CORPUS_SIZE
    text = render(report)
    assert "PARTIAL" in text
    assert f"{SPECIFIED_CORPUS_SIZE} hand-labelled real messages" in text
    assert f"this set holds {len(report.scores)}" in text


def test_chat_and_transcript_run_but_are_not_graded(report):
    """Doc 04: neither profile has a live connector, and gating a wave on a corpus that cannot
    be assembled blocks it on unrelated work. They still have to RUN."""
    ungraded = {score.fixture_id for score in report.scores if not score.gate}
    assert ungraded == {"chat_reschedule", "transcript_renewal_call"}
    for score in report.scores:
        assert score.extracted, score.fixture_id
    assert all(score.gate for score in report.gated)


def test_the_profiles_the_doc_gates_on_are_all_represented(report):
    """email, document and crm_note are the three with a live source. All three are graded."""
    graded = {score.profile_id for score in report.gated}
    assert {"email", "document", "crm_note"} <= graded


# ---------------------------------------------------------------------------------------------
# Fixture hygiene — a corpus is only as honest as its labels.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", load_set(CORPUS), ids=lambda f: f.fixture_id)
def test_every_recorded_citation_quotes_the_fixtures_own_content(fixture):
    """A recorded answer citing text its content does not contain is a fabricated LABEL, and it
    would inflate the span-verification rate it is supposed to measure."""
    recorded = fixture.recorded_model_output
    assert recorded is not None, "every fixture must be replayable"

    def _walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "evidence" and isinstance(value, list):
                    for span in value:
                        quote = span.get("quote", "")
                        assert quote in fixture.content, (
                            f"{fixture.fixture_id}: cited {quote!r}, which is not in the content")
                        assert fixture.content[span["start_offset"]:span["end_offset"]] == quote
                else:
                    _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(recorded)


@pytest.mark.parametrize("fixture", load_set(CORPUS), ids=lambda f: f.fixture_id)
def test_every_declared_fabrication_really_is_absent_from_the_content(fixture):
    """A "fabrication" the content actually contains is a mislabelled control that would let a
    real fabrication through under its name."""
    for literal in fixture.expected.get("fabricated_amounts", []):
        assert literal not in fixture.content, fixture.fixture_id


@pytest.mark.parametrize("fixture", load_set(CORPUS), ids=lambda f: f.fixture_id)
def test_every_fixture_records_where_its_label_came_from(fixture):
    """Provenance is what separates a derived fixture from an invented one, and this corpus is
    derived. A fixture that cannot say which line of doc 04 it comes from does not belong."""
    raw = json.loads((fixture.path).read_text(encoding="utf-8"))
    assert raw.get("provenance", "").strip(), fixture.fixture_id


# ---------------------------------------------------------------------------------------------
# The runner is not vacuous: each threshold is shown to fail when it should.
# ---------------------------------------------------------------------------------------------


def test_an_undeclared_fabricated_amount_fails_the_run(corpus_copy):
    """The hard fail, in the direction that matters: an invented number nobody labelled."""
    _edit(corpus_copy, "email_fabricated_amount_control",
          lambda data: data["expected"].pop("fabricated_amounts"))
    report = run_set(load_set(corpus_copy), client_factory=_replay)
    assert not report.passed
    assert report.fabricated_amounts == ["$120,000"]
    assert any("HARD FAIL" in failure for failure in report.failures)


def test_a_declared_fabrication_that_goes_undetected_also_fails(corpus_copy):
    """The other direction. A negative control that passes means the DETECTOR is broken, which
    is a worse result than a dirty corpus and must not read as a clean one."""
    def _drop_the_invention(data):
        recorded = data["recorded_model_output"]
        recorded["amounts"] = [a for a in recorded["amounts"] if a["as_written"] != "$120,000"]

    _edit(corpus_copy, "email_fabricated_amount_control", _drop_the_invention)
    report = run_set(load_set(corpus_copy), client_factory=_replay)
    assert not report.passed
    assert report.detector_failures == ["$120,000"]


def test_a_missed_commitment_drops_the_detection_rate_below_the_threshold(corpus_copy):
    _edit(corpus_copy, "worked_example",
          lambda data: data["recorded_model_output"].update({"commitments": []}))
    report = run_set(load_set(corpus_copy), client_factory=_replay)
    assert not report.passed
    assert report.commitment_detection_bp < MIN_COMMITMENT_DETECTION_BP


def test_an_unverifiable_span_drops_the_verification_rate(corpus_copy):
    """A quote the source does not contain is the failure the span rate exists to find."""
    def _fabricate_a_quote(data):
        entry = data["recorded_model_output"]["entity_mentions"][0]
        entry["evidence"] = [{"quote": "the merger with Contoso closes in March",
                              "start_offset": 0, "end_offset": 39}]
        entry["surface_form"] = "Contoso"

    _edit(corpus_copy, "crm_note_blocked_deal", _fabricate_a_quote)
    report = run_set(load_set(corpus_copy), client_factory=_replay)
    assert not report.passed


def test_a_stale_cache_cannot_hide_a_prompt_change(corpus_copy):
    """The re-run threshold measures CALLS, not a hit-rate log written by the code being graded.
    Two fixtures with the same content under different profiles must not share a row."""
    source = json.loads((corpus_copy / "worked_example.json").read_text(encoding="utf-8"))
    twin = dict(source, fixture_id="worked_example_as_document", profile_id="document",
                tier="T3", worked_example=False)
    twin["expected"] = {"commitments": source["expected"]["commitments"]}
    (corpus_copy / "worked_example_as_document.json").write_text(json.dumps(twin, indent=2),
                                                                 encoding="utf-8")
    report = run_set(load_set(corpus_copy), client_factory=_replay)
    calls = {score.fixture_id: score.model_calls for score in report.scores}
    assert calls["worked_example"] == 1
    assert calls["worked_example_as_document"] == 1, "the profile is part of the cache key"
    assert report.replay_calls_on_rerun == 0


# ---------------------------------------------------------------------------------------------
# The runner refuses what it cannot grade.
# ---------------------------------------------------------------------------------------------


def test_an_empty_corpus_is_an_error_not_a_pass(tmp_path):
    """Every rate over zero fixtures is 100%, which is the one result this gate must not print."""
    (tmp_path / "empty").mkdir()
    with pytest.raises(GoldenCorpusError, match="no fixtures"):
        load_set(tmp_path / "empty")


def test_a_directory_that_is_not_one_is_refused(tmp_path):
    with pytest.raises(GoldenCorpusError, match="not a directory"):
        load_set(tmp_path / "nope")


def test_two_fixtures_with_one_id_are_refused(corpus_copy):
    """Duplicate ids would silently overwrite each other in any per-fixture report."""
    data = json.loads((corpus_copy / "worked_example.json").read_text(encoding="utf-8"))
    (corpus_copy / "copy.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GoldenCorpusError, match="duplicate fixture_id"):
        load_set(corpus_copy)


def test_a_malformed_fixture_raises_rather_than_being_skipped(corpus_copy):
    """A corpus that drops the fixture it could not read reports a pass over the ones it
    understood."""
    (corpus_copy / "broken.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(GoldenCorpusError, match="not valid JSON"):
        load_set(corpus_copy)


def test_a_fixture_with_no_recorded_answer_cannot_be_replayed(corpus_copy):
    _edit(corpus_copy, "crm_note_blocked_deal",
          lambda data: data.pop("recorded_model_output"))
    fixture = next(f for f in load_set(corpus_copy) if f.fixture_id == "crm_note_blocked_deal")
    with pytest.raises(GoldenCorpusError, match="no recorded_model_output"):
        ReplayClient(fixture)


def test_live_mode_refuses_to_run_without_an_exact_model_snapshot(capsys):
    """"claude-3-5-haiku" is not reproducible; a dated snapshot is, and the difference is whether
    a replay months later re-derives the same extraction."""
    assert main(["--set", str(CORPUS), "--live"]) == 2
    assert "--model" in capsys.readouterr().err


# ---------------------------------------------------------------------------------------------
# The command's own exit codes — the gate is a command before it is a test.
# ---------------------------------------------------------------------------------------------


def test_the_command_exits_zero_on_the_shipped_corpus(capsys):
    assert main(["--set", str(CORPUS)]) == 0
    assert "RESULT: PASS" in capsys.readouterr().out


def test_the_command_exits_two_when_the_full_corpus_is_required(capsys):
    """For the day the thirty real messages land: until then, --require-full-corpus is red."""
    assert main(["--set", str(CORPUS), "--require-full-corpus"]) == 2
    assert f"of the {SPECIFIED_CORPUS_SIZE} messages" in capsys.readouterr().err


def test_the_command_emits_machine_readable_json(capsys):
    assert main(["--set", str(CORPUS), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lane"] == "replay"
    assert payload["specified_corpus_size"] == SPECIFIED_CORPUS_SIZE
    assert payload["messages"] == len(list(CORPUS.glob("*.json")))
    assert payload["passed"] is True


def test_the_command_exits_one_when_a_threshold_is_missed(corpus_copy, capsys):
    _edit(corpus_copy, "worked_example",
          lambda data: data["recorded_model_output"].update({"commitments": []}))
    assert main(["--set", str(corpus_copy)]) == 1
    assert "RESULT: FAIL" in capsys.readouterr().out

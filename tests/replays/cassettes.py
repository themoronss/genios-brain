"""A founder case's cassette — the model's answers for that case, recorded once, replayed exactly.

One JSON file per case in `specs/founder/cassettes/`:

    {"case_id": "F03", "source": "ideal_reader" | "live:<model>", "recorded_at": "<commit>",
     "answers": {"<cassette key>": {"site", "parsed", "raw", "input_tokens", "output_tokens",
                                    "model"}}}

`source` says what wrote the answers, because the board's numbers mean different things in the
two cases: answers the ideal reader wrote from the case (`ideal_reader.py`, decision D12c's
default — no model spend) judge the ENGINE given a faithful reader; answers a live model gave
judge the engine AND the model. A reader of the board must be able to tell which.

A cassette is synthetic like its case: a real name from the founder's mailbox in any answer is
refused at save (`founder_case.REAL_NAMES`).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from tests.replays.founder_case import (CASSETTE_DIR, CaseError, CaseRun, FounderCase,
                                        real_names_in)

IDEAL_READER = "ideal_reader"
LIVE_PREFIX = "live:"
_REPO = Path(__file__).resolve().parents[2]


def path_for(case: FounderCase, folder: Path = CASSETTE_DIR) -> Path:
    return folder / f"{case.case_id}.json"


def save(case: FounderCase, answers: dict[str, dict[str, Any]], *, source: str,
         folder: Path = CASSETTE_DIR) -> Path:
    """Write a case's cassette. Refuses an unnamed source and any real name in an answer."""
    if source != IDEAL_READER and not (source.startswith(LIVE_PREFIX)
                                       and len(source) > len(LIVE_PREFIX)):
        raise ValueError(f"cassette source {source!r}: {IDEAL_READER!r} or 'live:<model>'")
    leaked = real_names_in(answers)
    if leaked:
        raise CaseError(f"{case.case_id}: the cassette carries real name(s) {sorted(set(leaked))}")
    folder.mkdir(parents=True, exist_ok=True)
    path = path_for(case, folder)
    body = {"case_id": case.case_id, "source": source, "recorded_at": _commit(),
            "answers": {k: answers[k] for k in sorted(answers)}}
    path.write_text(json.dumps(body, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                    encoding="utf-8")
    return path


def load(case: FounderCase, folder: Path = CASSETTE_DIR) -> dict[str, dict[str, Any]]:
    path = path_for(case, folder)
    if not path.is_file():
        raise AssertionError(f"{case.case_id} has no cassette at {path} — record it with "
                             f"`scripts/golden_eval.py --record {case.case_id}`")
    stored = json.loads(path.read_text(encoding="utf-8"))
    if stored.get("case_id") != case.case_id:
        raise AssertionError(f"{path} belongs to {stored.get('case_id')!r}, not {case.case_id}")
    return dict(stored.get("answers") or {})


def source_of(case: FounderCase, folder: Path = CASSETTE_DIR) -> str:
    return str(json.loads(path_for(case, folder).read_text(encoding="utf-8")).get("source"))


def record(case: FounderCase, model: Any = None) -> tuple[CaseRun, dict[str, dict[str, Any]]]:
    """Run the case through the real chain with `model` (default: the ideal reader) and keep
    every answer it gave, keyed by the prompt's hash."""
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader
    recorder = CassetteRecorder(model if model is not None else IdealReader(case))
    run = run_case(case, recorder)
    return run, dict(recorder.cassette)


def replay(case: FounderCase, folder: Path = CASSETTE_DIR) -> CaseRun:
    """Run the case with its recorded answers. A miss raises (`harness.CassetteMiss`)."""
    from tests.replays.engine_runner import run_case
    from tests.replays.harness import RecordedLLM
    return run_case(case, RecordedLLM(load(case, folder)))


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"

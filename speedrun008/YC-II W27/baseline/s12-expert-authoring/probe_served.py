"""Probe: run golden cases with the expert switched on, the recorded answers for every other site, and
capture each expert prompt (the dossier the expert would be shown) — answering none of them.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python <this> OUT_DIR [F01 F02 …]

Writes OUT_DIR/<case>.json: [{"sweep": i, "key": counterparty key, "prompt": …}], one per distinct prompt.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]          # the repository root
sys.path.insert(0, str(REPO))

from sqlalchemy import text  # noqa: E402

from tests.replays import cassettes, engine_runner  # noqa: E402
from tests.replays.founder_case import load_cases  # noqa: E402
from tests.replays.harness import RecordedLLM, identify_site  # noqa: E402
from tests.replays.ideal_reader import IdealReader, IdealReaderError  # noqa: E402

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
wanted = set(sys.argv[2:])

_KEY = re.compile(r"^Counterparty: .*? <([^>]+)> \(", re.M)


class Probe:
    """The expert's prompts are answered by the ideal reader from the case's authored blocks — as the
    recording will answer them — and captured with what came of each."""

    def __init__(self, recorded, sink, case):
        self._recorded = recorded
        self._sink = sink
        self._reader = IdealReader(case)
        self.model = recorded.model
        self.calls = recorded.calls
        self.misses = recorded.misses

    @staticmethod
    def content_hash(material: str) -> str:
        return RecordedLLM.content_hash(material)

    def call(self, prompt, **kw):
        if identify_site(prompt) == "expert":
            m = _KEY.search(prompt)
            row = {"key": m.group(1) if m else None, "prompt": prompt}
            self._sink.append(row)
            try:
                result = self._reader.call(prompt, **kw)
            except IdealReaderError as exc:
                row["refused_by_reader"] = str(exc)[:300]
                raise RuntimeError(f"the ideal reader refused: {exc}") from None
            row["served"] = True
            return result
        return self._recorded.call(prompt, **kw)


_switch = engine_runner.switch_on_founder_office


def switch_on_with_the_expert(engine, org):
    _switch(engine, org)
    with engine.begin() as c:
        c.execute(text("insert into l4_activation (org_id, feature, enabled_by) values (:o, 'expert_review', "
                       "'probe') on conflict do nothing"), {"o": org})


engine_runner.switch_on_founder_office = switch_on_with_the_expert

for case in load_cases():
    if wanted and case.case_id not in wanted:
        continue
    sink: list[dict] = []
    llm = Probe(RecordedLLM(cassettes.load(case)), sink, case)
    rows_db = []
    try:
        report = engine_runner.run_case(case, llm, keep=True)
        from genios_engine.api import routes
        engine = routes._graph.engine
        with engine.connect() as c:
            rows_db = [tuple(r) for r in c.execute(text(
                "select file_id, status, coalesce(reason, ''), reviewed_at from expert_reviews "
                " where org_id = :o order by reviewed_at, file_id"), {"o": report.org_id})]
        engine_runner.remove_tenant(engine, report.org_id)
        status = "ok"
    except BaseException as exc:  # noqa: BLE001 — report and go on
        status = f"{type(exc).__name__}: {str(exc)[:200]}"
    seen, rows = set(), []
    for row in sink:
        if row["prompt"] in seen:
            continue
        seen.add(row["prompt"])
        rows.append(row)
    (out / f"{case.case_id}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    keys = sorted({r["key"] for r in rows if r["key"]})
    refused = [r["refused_by_reader"][:120] for r in rows if r.get("refused_by_reader")]
    statuses = [f"{s}{(':' + why[:90]) if s != 'valid' else ''}" for _f, s, why, _at in rows_db]
    print(f"{case.case_id} {status} prompts={len(rows)} files={keys} reviews={statuses} "
          f"reader_refused={refused}", flush=True)

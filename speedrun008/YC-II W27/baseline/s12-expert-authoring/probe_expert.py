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

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
wanted = set(sys.argv[2:])

_KEY = re.compile(r"^Counterparty: .*? <([^>]+)> \(", re.M)


class Probe:
    def __init__(self, recorded, sink):
        self._recorded = recorded
        self._sink = sink
        self.model = recorded.model
        self.calls = recorded.calls
        self.misses = recorded.misses

    @staticmethod
    def content_hash(material: str) -> str:
        return RecordedLLM.content_hash(material)

    def call(self, prompt, **kw):
        if identify_site(prompt) == "expert":
            m = _KEY.search(prompt)
            self._sink.append({"key": m.group(1) if m else None, "prompt": prompt})
            raise RuntimeError("the probe answers no expert prompt")
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
    llm = Probe(RecordedLLM(cassettes.load(case)), sink)
    try:
        engine_runner.run_case(case, llm)
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
    print(f"{case.case_id} {status} prompts={len(rows)} files={keys}", flush=True)

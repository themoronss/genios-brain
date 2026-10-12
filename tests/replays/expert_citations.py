"""Where each authored expert citation points — so the ideal reader cites what the dossier in front of it shows.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… python -m tests.replays.expert_citations --write

STEP-12, tree `yc2_w27_s12` M33.C2.L-data.V0.U03. An authored review (`06` D49, `model.expert`) cites the ids of
the dossier it was written against — `[evt_…]`, `[loop:…]`, `[sit:…]`, `[card:…]`. The golden runner mints ids from
a per-case sequence (`engine_runner.pinned_world`), so a door that mints a different number of ids before a mail
lands shows the same mail under another id: the first-connect door's second drain call does exactly that. The
authored answer, served there, cites an id its dossier never showed, the contract refuses it, the file is not
decided — and the founder who presses Sync is told something other than what the sweep tells him (12 Oct: 12 of
58 cases, `03` F177). A faithful reader cites what it is shown. So each authored citation is kept with the
dossier LINES it named — each line with every id blanked, and which of its ids it was, every way the sweep
door's dossiers print it as time passes (a situation's quiet days, a card's events) (`CITATIONS`, written by
`--write`) — and the ideal reader, serving an answer to a dossier that does not show a cited id, cites the id
that dossier gives one of those lines (`translate`). A line the dossier does not hold exactly once is never
guessed: the citation stays as authored, and the contract refuses it, visibly.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Any

from pathlib import Path

#: Beside `expert_files.json`, never among the cases (`founder_case.load_cases` reads every file there).
CITATIONS = Path(__file__).parent / "expert_citations.json"
#: An id as a dossier prints it: in brackets, no spaces (`reason/expert/dossier`).
_ID = re.compile(r"\[([^\[\]\s]+)\]")


def dossier(prompt: str) -> str:
    """The dossier an expert prompt carries — the text between its tags, or the prompt itself."""
    if "<dossier>\n" not in prompt:
        return prompt
    return prompt.split("<dossier>\n", 1)[1].split("\n</dossier>", 1)[0]


def shape(line: str) -> str:
    """A dossier line with every id blanked — what the line says, whatever the ids were minted as."""
    return _ID.sub("[#]", line).strip()


def where(text: str) -> dict[str, tuple[str, int]]:
    """Each id a dossier shows → the first line that shows it (its shape) and which of the line's ids it is."""
    out: dict[str, tuple[str, int]] = {}
    for line in text.splitlines():
        for index, found in enumerate(_ID.findall(line)):
            out.setdefault(found, (shape(line), index))
    return out


def cited(answer: Mapping[str, Any]) -> set[str]:
    """Every id an authored review cites: its facts' evidence, what its inferences and patterns rest on
    (but the facts they name by number), and its proposed kind's evidence."""
    out = {str(e) for f in answer.get("facts") or () for e in f.get("evidence") or ()}
    for part in ("inferences", "patterns"):
        out |= {str(e) for i in answer.get(part) or () for e in i.get("based_on") or ()
                if not str(e).startswith("fact:")}
    kind = answer.get("proposed_kind") or {}
    out |= {str(e) for e in kind.get("evidence") or ()}
    return out


def translate(answer: Mapping[str, Any], prompt: str,
              spots: Mapping[str, Iterable[Any]]) -> Mapping[str, Any]:
    """`answer`, its citations of ids this prompt's dossier does not show replaced by the ids it gives the
    same line (`spots`: cited id → its lines, each [shape, index], as the answer's own dossiers printed it).
    Unchanged — the same object — when nothing needs it or nothing can be matched exactly once."""
    text = dossier(prompt)
    shown = set(_ID.findall(text))
    by_shape: dict[str, list[list[str]]] = defaultdict(list)
    for line in text.splitlines():
        ids = _ID.findall(line)
        if ids:
            by_shape[shape(line)].append(ids)
    moved: dict[str, str] = {}
    for cid in sorted(cited(answer) - shown):
        for line_shape, index in spots.get(cid) or ():
            candidates = by_shape.get(str(line_shape)) or []
            if len(candidates) == 1 and len(candidates[0]) > int(index):
                moved[cid] = candidates[0][int(index)]
                break
    if not moved:
        return answer
    raw = json.dumps(answer, ensure_ascii=False)
    for old, new in moved.items():
        raw = raw.replace(json.dumps(old), json.dumps(new))
    return json.loads(raw)


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, list[Any]]]:
    return json.loads(CITATIONS.read_text()) if CITATIONS.is_file() else {}


def spots_for(case_id: str) -> Mapping[str, Iterable[Any]]:
    """Where `case_id`'s authored citations point, as `--write` measured them."""
    return _table().get(case_id, {})


def measure(cases=None) -> dict[str, dict[str, list[Any]]]:
    """Each case's sweep door replayed from its cassette, every expert prompt kept: for every id its authored
    answers cite, every distinct line that shows it, in the order the dossiers printed them. An id no dossier
    shows is left out — and named."""
    from tests.replays import cassettes
    from tests.replays.engine_runner import run_case
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM, identify_site

    class _Keeping(RecordedLLM):
        def __init__(self, cassette):
            super().__init__(cassette)
            self.dossiers: list[str] = []

        def call(self, prompt: str, **kw: Any):
            if identify_site(prompt) == "expert":
                self.dossiers.append(dossier(prompt))
            return super().call(prompt, **kw)

    out: dict[str, dict[str, list[Any]]] = {}
    for case in cases or load_cases():
        want = set().union(*(cited(e["answer"]) for e in (case.model or {}).get("expert") or ()))
        if not want:
            continue
        llm = _Keeping(cassettes.load(case))
        run_case(case, llm)
        found: dict[str, list[Any]] = {}
        for text in llm.dossiers:
            for cid, (line_shape, index) in where(text).items():
                if cid in want and [line_shape, index] not in found.setdefault(cid, []):
                    found[cid].append([line_shape, index])
        missing = sorted(want - set(found))
        if missing:
            print(f"{case.case_id}: cited and shown in no dossier — {missing}")
        out[case.case_id] = dict(sorted(found.items()))
    return out


def write() -> None:
    from tests.replays.engine_runner import pin_scratch_database
    pin_scratch_database()
    table = measure()
    CITATIONS.write_text(json.dumps(table, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(f"{sum(len(v) for v in table.values())} citations over {len(table)} cases → {CITATIONS}")


if __name__ == "__main__":       # pragma: no cover - the recording entry point
    import sys
    if sys.argv[1:] != ["--write"]:
        raise SystemExit("usage: python -m tests.replays.expert_citations --write")
    write()

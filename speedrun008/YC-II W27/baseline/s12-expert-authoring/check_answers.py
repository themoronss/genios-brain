"""Check authored expert answers before they are merged into the case files.

    cd <repo> && .venv/bin/python <this> PROBE_DIR ANSWERS_DIR F01 F02 …   (no case ids: every file in ANSWERS_DIR)

PROBE_DIR is `probe_served.py`'s output (or `probe_expert.py`'s); the files each case reviews are read from
`tests/replays/expert_files.json` (`build_expert_files.py` writes it from the same probe).

ANSWERS_DIR/<case>.json is {"expert": [{"when": ["<key>"], "by": "claude", "answer": {…}}],
"expert_declared": {"key": "why, in a sentence"}}. Each answer must: parse into the review contract;
name its file once as <key>, a file the case's sweeps review; cite only ids its first dossier offered;
name only a listed stage (or null); write no digit in any text; and every reviewed file is answered or
declared. It also validates each answer against EVERY captured dossier of its file (the catalogue rebuilt
from the dossier's own text, as build_dossier builds it), so an answer served to a later review holds too.
Exit 0 when every case is clean.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]          # the repository root
sys.path.insert(0, str(REPO))

from genios_engine.contracts.expert_review import (DossierCatalogue, ExpertReview,  # noqa: E402
                                                   number_tokens, validate)
from tests.replays.ideal_reader import without_company_brief  # noqa: E402

_ID = re.compile(r"\[([^\[\]\s]+)\]")
_STAGES = re.compile(r"Stages — the file's current stage is named from these only:\n((?:- .*\n)+)")
_STAGE = re.compile(r"^- (\S+) \(", re.M)
_KEY = re.compile(r"^<([^<>\s]+)>$")

probe, answers_dir = Path(sys.argv[1]), Path(sys.argv[2])
files = json.loads((REPO / "tests" / "replays" / "expert_files.json").read_text())
wanted = sys.argv[3:] or sorted(p.stem for p in answers_dir.glob("F*.json"))
bad = 0
for case_id in wanted:
    problems = []
    path = answers_dir / f"{case_id}.json"
    if not path.exists():
        print(f"{case_id}: NO ANSWERS FILE")
        bad += 1
        continue
    data = json.loads(path.read_text())
    entries, declared = data.get("expert") or [], data.get("expert_declared") or {}
    reviewed = files.get(case_id, {})
    prompts = []                     # (the prompt as the ideal reader matches it, its catalogue)
    for row in json.loads((probe / f"{case_id}.json").read_text()):
        if row["key"]:
            d = row["prompt"].split("<dossier>\n", 1)[1].split("\n</dossier>", 1)[0]
            st = _STAGES.search(d)
            prompts.append((without_company_brief(row["prompt"]).lower(), DossierCatalogue(
                evidence_ids=frozenset(_ID.findall(d)), numbers=number_tokens(d),
                stages=tuple(_STAGE.findall(st.group(1))) if st else ())))
    answered = set()
    for n, entry in enumerate(entries):
        where = f"{case_id} entry {n}"
        if entry.get("by") != "claude":
            problems.append(f"{where}: not marked by claude")
        keys = [m.group(1) for t in entry.get("when") or () if (m := _KEY.match(str(t)))]
        if len(keys) != 1:
            problems.append(f"{where}: names its file once as <key>: {entry.get('when')}")
            continue
        key = keys[0]
        if key not in reviewed:
            problems.append(f"{where}: <{key}> is not a file this case reviews: {sorted(reviewed)}")
            continue
        answered.add(key)
        try:
            review = ExpertReview.from_mapping(entry["answer"])
        except ValueError as exc:
            problems.append(f"{where} <{key}>: does not parse: {exc}")
            continue
        digits = sorted(set().union(*(number_tokens(t) for t in review.texts())))
        if digits:
            problems.append(f"{where} <{key}>: writes numbers {digits}")
        first = reviewed[key]
        cited = {e for f in review.facts for e in f.evidence}
        cited |= {e for i in (*review.inferences, *review.patterns) for e in i.based_on
                  if not e.startswith("fact:")}
        if review.proposed_kind is not None:
            cited |= set(review.proposed_kind.evidence)
        narrower = [t for t in entry.get("when") or () if not _KEY.match(str(t))]
        if not narrower and not cited <= set(first["evidence"]):
            # The general entry answers the file's FIRST review, so it cites only what that dossier
            # offered. A narrower entry (more `when` terms) answers later prompts only, and is held to
            # each prompt it serves by the per-prompt validation below.
            problems.append(f"{where} <{key}>: cites ids its first dossier never offered: "
                            f"{sorted(cited - set(first['evidence']))}")
        stage = review.expected_vs_actual.stage
        if stage is not None and stage not in first["stages"]:
            problems.append(f"{where} <{key}>: stage {stage!r} not in {first['stages']}")
    # Every captured prompt is answered by the FIRST entry whose `when` terms all appear in it (the
    # ideal reader's rule), and that answer must validate against that prompt's own dossier.
    for i, (seen, catalogue) in enumerate(prompts):
        entry = next((e for e in entries if e.get("when") and
                      all(str(t).lower() in seen for t in e["when"])), None)
        if entry is None:
            problems.append(f"{case_id}: prompt {i} is served by no entry")
            continue
        try:
            v = validate(ExpertReview.from_mapping(entry["answer"]), catalogue)
        except ValueError:
            continue                                   # reported above
        if not v.ok:
            problems.append(f"{case_id}: prompt {i} ({entry['when']}) is refused: {list(v.problems)[:4]}")
    for key in sorted(set(reviewed) - answered - set(declared)):
        problems.append(f"{case_id}: <{key}> is reviewed and has no answer (nor a declared reason)")
    for p in problems:
        print(p)
    print(f"{case_id}: {'OK' if not problems else f'{len(problems)} problem(s)'} — "
          f"{len(answered)} of {len(reviewed)} files answered, {len(declared)} declared")
    bad += bool(problems)
sys.exit(1 if bad else 0)

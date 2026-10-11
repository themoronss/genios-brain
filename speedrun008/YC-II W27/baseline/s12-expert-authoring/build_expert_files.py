"""From the probe's captured expert prompts, the files each case's sweeps review — and, per file, what its
FIRST dossier offered to cite (bracketed ids) and the stages its playbook lists.

    python <this> PROBE_DIR OUT_JSON
"""
import json
import re
import sys
from pathlib import Path

probe, out = Path(sys.argv[1]), Path(sys.argv[2])
_ID = re.compile(r"\[([^\[\]\s]+)\]")
_STAGES = re.compile(r"Stages — the file's current stage is named from these only:\n((?:- .*\n)+)")
_STAGE = re.compile(r"^- (\S+) \(", re.M)
files: dict = {}
for path in sorted(probe.glob("F*.json")):
    rows = json.loads(path.read_text())
    per: dict = {}
    for row in rows:                       # in the order the chain asked: the first is the first dossier
        key = row["key"]
        if not key or key in per:
            continue
        dossier = row["prompt"].split("<dossier>\n", 1)[1].split("\n</dossier>", 1)[0]
        stages = _STAGES.search(dossier)
        per[key] = {"evidence": sorted(set(_ID.findall(dossier))),
                    "stages": _STAGE.findall(stages.group(1)) if stages else [],
                    "prompts": sum(1 for r in rows if r["key"] == key)}
    files[path.stem] = per
out.write_text(json.dumps(files, indent=1, sort_keys=True) + "\n")
print(sum(len(v) for v in files.values()), "files over", len(files), "cases")

"""STEP-12 check §8.1 · what the golden set's model was asked, read from the cassettes alone — no
database, no spend. Prints the answers per site, the decider's outcomes per case, and for each case the
board fails (`baseline/yc2w27-s11-build/record_verdicts.txt`) whether the decider was ever asked.

    python3 "speedrun008/YC-II W27/baseline/yc2w27-s12-check/cassette_sites.py"
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CASSETTES = ROOT / "tests/replays/specs/founder/cassettes"
VERDICTS = ROOT / "speedrun008/YC-II W27/baseline/yc2w27-s11-build/record_verdicts.txt"

total, decider = Counter(), {}
for f in sorted(CASSETTES.glob("F*.json")):
    answers = [v for v in json.loads(f.read_text())["answers"].values() if isinstance(v, dict)]
    total.update(v.get("site") for v in answers)
    decider[f.stem] = Counter((v.get("parsed") or {}).get("outcome") for v in answers
                              if v.get("site") == "decider")
print("answers:", sum(total.values()), dict(total.most_common()))
asked = {k: v for k, v in decider.items() if v}
print("decider asked in", len(asked), "cases:", dict(sum(asked.values(), Counter())))
print("\ncases the board fails:")
for line in VERDICTS.read_text().splitlines():
    parts = line.split(None, 2)
    if len(parts) > 1 and parts[1] == "fail":
        case = parts[0]
        print(f"  {case}  decider {dict(decider.get(case, {})) or 'never asked'}  —  "
              f"{line.split('answers', 1)[-1].strip()[:90]}")

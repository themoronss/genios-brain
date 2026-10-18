"""Compare each case's cassette before and after a re-record, by what was ANSWERED, not by key.

    python diff_cassettes.py <git-rev-before> [cases…]

A cassette's keys move whenever its prompts move, so a key diff says nothing. What matters is whether
the ideal reader answered the same things: per model site, the multiset of parsed answers. A case
whose answers are equal per site moved only its prompts; any other difference is printed for reading.
"""
import json, subprocess, sys
from collections import Counter
from pathlib import Path

REPO = Path("/Users/rohitswerashi/Downloads/Artifacts/Product/genios-brain (yc)/genios-brain")
DIR = "tests/replays/specs/founder/cassettes"
rev = sys.argv[1]
only = set(sys.argv[2:])


def load_rev(path):
    try:
        out = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:{path}"], capture_output=True,
                             text=True, check=True).stdout
        return json.loads(out)
    except subprocess.CalledProcessError:
        return None


def per_site(cassette):
    sites = {}
    for _key, entry in (cassette or {}).get("answers", {}).items():
        sites.setdefault(entry.get("site"), Counter())[json.dumps(entry.get("parsed"), sort_keys=True)] += 1
    return sites


same = moved = 0
for path in sorted((REPO / DIR).glob("F*.json")):
    case = path.stem
    if only and case not in only:
        continue
    before = per_site(load_rev(f"{DIR}/{path.name}"))
    after = per_site(json.loads(path.read_text()))
    if before == after:
        same += 1
        continue
    moved += 1
    print(f"== {case}")
    for site in sorted(set(before) | set(after), key=str):
        b, a = before.get(site, Counter()), after.get(site, Counter())
        if b == a:
            continue
        print(f"   site {site}: {sum(b.values())} → {sum(a.values())} answers")
        for k in sorted(set(b) | set(a)):
            if b[k] != a[k]:
                print(f"      {b[k]} → {a[k]}  {k[:240]}")
print(f"\n{same} cases answered the same per site; {moved} differ (printed above)")

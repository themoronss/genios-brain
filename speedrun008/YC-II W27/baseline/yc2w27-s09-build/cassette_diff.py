"""Per re-recorded cassette: answers removed and added, by site, and whether an answer's CONTENT
changed (same parsed answer under a new key = the prompt moved, the reading did not)."""
import json, subprocess, sys
from collections import Counter
def load_head(path):
    r = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True)
    return json.loads(r.stdout)["answers"] if r.returncode == 0 else {}
def canon(a):
    return json.dumps(a["parsed"], sort_keys=True, ensure_ascii=False)
for case in sys.argv[1:]:
    path = f"tests/replays/specs/founder/cassettes/{case}.json"
    old, new = load_head(path), json.load(open(path))["answers"]
    removed = {k: v for k, v in old.items() if k not in new}
    added = {k: v for k, v in new.items() if k not in old}
    old_content = Counter((v["site"], canon(v)) for v in removed.values())
    new_content = Counter((v["site"], canon(v)) for v in added.values())
    same = old_content & new_content
    gone = old_content - same
    fresh = new_content - same
    print(f"=== {case}: kept {len(old) - len(removed)} · removed {len(removed)} · added {len(added)} · "
          f"same answer under a moved prompt {sum(same.values())}")
    for (site, c), n in sorted(gone.items()):
        print(f"   - {site} x{n}: {c[:260]}")
    for (site, c), n in sorted(fresh.items()):
        print(f"   + {site} x{n}: {c[:260]}")

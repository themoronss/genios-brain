"""Sum the compiled lane's per-sweep counters (its one log line) across a golden run's log."""
import ast
import re
import sys
from collections import Counter

LINE = re.compile(r"domain-compiler \S+ org=(\S+) domains=\[[^\]]*\] (\{.*\})\s*$")
total, sweeps, by_reason, by_type = Counter(), 0, Counter(), Counter()
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    m = LINE.search(line)
    if not m:
        continue
    sweeps += 1
    d = ast.literal_eval(m.group(2))
    for k, v in d.items():
        if isinstance(v, dict):
            target = by_reason if k == "no_route_by_reason" else by_type if k == "no_route_by_type" else None
            if target is not None:
                target.update(v)
        elif isinstance(v, (int, float)):
            total[k] += v
print("sweeps", sweeps)
for k in sorted(total):
    print(f"  {k:40s} {total[k]}")
print("no_route_by_reason", dict(by_reason))
print("no_route_by_type", dict(by_type))

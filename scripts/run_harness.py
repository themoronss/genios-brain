"""Run the Sprint-1 harness. Exits 1 if any test fails."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.harness import (
    t01_entity_extraction,
    t03_resolution,
    t05_noise_stability,
    t06_pull_latency,
    t07_ingest_latency,
    t17_pii_leak,
)

_TESTS = [
    t01_entity_extraction, t03_resolution, t05_noise_stability,
    t06_pull_latency, t07_ingest_latency, t17_pii_leak,
]


def main() -> int:
    results = [t.run() for t in _TESTS]
    failed = [r for r in results if not r.get("passed", False) and not r.get("skipped")]
    print(f"\n── Harness results ──")
    for r in results:
        status = "SKIP" if r.get("skipped") else ("PASS" if r.get("passed") else "FAIL")
        print(f"  {status}  {r.get('test')}  {r.get('metric', '')}={r.get('value', '-')}  thr={r.get('threshold', '-')}")
    if failed:
        print(f"\n{len(failed)} test(s) failed.")
        return 1
    print("\nAll tests passed or skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

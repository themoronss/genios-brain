"""Sprint-1 test harness (Phase 4.8).

6 smoke tests that run against a live DB + API. Each test is importable and
returns a pass/fail dict. `scripts/run_harness.py` drives the batch and prints
a summary.

Thresholds per plan:
  T-01 entity F1 >= 0.94
  T-03 resolution accuracy >= 0.98
  T-05 top-5 churn under noise <= 1
  T-06 pull p95 < 400ms
  T-07 ingest p95 < 90s
  T-17 RLS cross-tenant query = 100% blocked
"""

from typing import Protocol


class HarnessTest(Protocol):
    def run(self) -> dict: ...

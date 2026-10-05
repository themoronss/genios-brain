# STEP-17 · TO BUILD · real tests — the suite stops being green while production is broken

**Owner:** Claude · Harsh for CI infrastructure. **Runs alongside every step.** **Moves:** the
database suite's failures **50 → 0** (measured 2026-10-05, `STEP-00` §4.2); pg-gated test files
that never run in CI **150 → 0**; every SQL statement in the engine is planned by Postgres on every
push.

---

## 1 · What is true now

| | Evidence |
|---|---|
| CI runs only the hermetic suite | `[CODE]` `.github/workflows/ci.yml` — `pip install -e ".[dev]"` then `pytest -q`, no database |
| The real-Postgres seam exists, and skips | `[CODE]` `tests/conftest.py:79-138` — `GENIOS_TEST_DATABASE_URL`; without it every pg test skips |
| Green while broken | `[CODE]` `5ebfef8e`'s own words: *"14,624 passed, 0 failed"* while production carried 4,076 rejected calls, 19 truncations, 160 unrouted events, 85 unreadable parks, 9 refused claims; the calibration SQL has errored weekly since 10 Sep with every test green |
| A production gate exists | `[CODE]` `scripts/pipeline_health.py` on `harsh/mvp`, seven read-only checks, exit 1 on failure |
| The database suite, run once by hand | `[TEST]` 2026-10-05, on the merged branch: **16,683 passed · 50 failed · 0 errors** · 4 skipped · 152 xfailed, in 20 minutes. None is caused by the merge, and 27 are one bug (`STEP-18` B2). Grouped by cause in `STEP-00` §4.2; every test in `baseline/2026-10-05/suite_with_database.txt` |
| A gate can pass on no data | `[PROD]` `pipeline_health`'s 24 h ceiling check passed while the lane it guards made no call at all (`03-FINDINGS.md` F24 · re-measured) |

## 2 · Why

Every step in this plan claims a number moved on production. That claim is only trustworthy if the
SQL it rests on was run, not just written.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.0 | **the database suite green — first** | the failing files of `STEP-00` §4.2 | `STEP-18` B2 first (27 tests); then each group, by cause. Each failure is classified before it is touched. A defect in the code is fixed in the code. A test whose premise the code has legitimately outgrown is redrawn, and the reason is written in `03-FINDINGS.md`. Never a skip, never a loosened assertion |
| 3.1 | Postgres in CI | `.github/workflows/ci.yml` | a `postgres` service and `GENIOS_TEST_DATABASE_URL` — **delivered in `STEP-01`** so the golden set runs from day one |
| 3.2 | every statement explained | new `tests/platform/test_every_statement_plans.py` | each SQL statement known to `platform/table_coverage` is `EXPLAIN`ed against the migrated scratch database — a column that does not exist (the `card_level` bug) fails the build |
| 3.3 | write paths that cannot write | new tests | every edge type any writer emits is in `context/graph_store.EDGE_TYPES`; every feedback reason inserts; every L4 feature the onboarding switches on exists |
| 3.4 | the health gate in deploy | `scripts/pipeline_health.py` | run after each deploy; a failure blocks the next. A check whose lane made no call reports *no data*, not *pass* |
| 3.5 | the plan's own checks | `tests/test_programme_step_status_is_consistent.py` | extended to this folder, so a step's file name and title cannot disagree here either |

## 4 · Expected

- the database suite: 0 failed, 0 errors — locally first, then in CI;
- 0 pg-gated files skipped in CI;
- 0 statements that fail `EXPLAIN`;
- the health gate runs on every deploy and its output is kept.

## 5 · Verify

```
# locally — the scratch database of STEP-00 §4.2. Use postgresql+psycopg://, as the repo does:
# tests/test_llm_cost_attribution.py:179 builds its engine from the raw URL.
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test \
  .venv/bin/python -m pytest -q -rfE        # 0 failed, 0 errors

# in CI, with the service:
pytest -q                                  # 0 skipped for want of a database
pytest tests/platform/test_every_statement_plans.py -q
```

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
| Tests that expire | `[TEST]` three found on 2026-10-05: `tests/reason/adapters/test_roster_reaches_the_audit.py` (red since 4 Oct), `tests/context/test_situation_publisher.py` (since 22 Sep), `tests/test_screen_followups_pg.py` (every Monday). The pattern — a fixed seed date beside a wall-clock evaluation — has not been swept for (`03-FINDINGS.md` F34) |
| Three Python versions | `[CODE]` production runs 3.11 (`Dockerfile:33`), CI 3.12 (`.github/workflows/ci.yml:17`), the local venv 3.13 — and one guard gave a different answer on 3.13 (`03-FINDINGS.md` F35) |

## 2 · Why

Every step in this plan claims a number moved on production. That claim is only trustworthy if the
SQL it rests on was run, not just written.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.0 | **the database suite green — first** · tree `yc2_w27/M16` (16 units) | the 16 failing files | Root-caused 2026-10-05, each on its own scratch database: **27** are `STEP-18` B2 (M16.C1 — the guard first, then the vocabulary); **5** a script that `int()`s the dict-valued counts `shadow_compile` returns since `22d598b1` (M16.C2); **6** tests on three clocks that expire — seeded on a fixed date, evaluated at the wall clock, dormant after 45 days, or a weekly window that fails on Mondays (M16.C3); **9** tests whose fixtures the code outgrew — a wipe that misses `message_fingerprints` (4 tests), an out-of-contract model stub, a CRM-closed situation now resolved by fact, a second situation writer, an approver that needs a seat, a decision fake that ignores R-1 (M16.C4); **2** guards that read text — a comment, and a docstring Python 3.13 dedents (M16.C5); and the H0 gate passes once its sub-run does. **No engine change is needed outside B2.** Never a skip, never a loosened assertion: each redrawn test keeps its point and names the commit that moved its premise |
| 3.1 | Postgres in CI | `.github/workflows/ci.yml` | a `postgres` service and `GENIOS_TEST_DATABASE_URL` — **delivered in `STEP-01`** (tree `yc2_w27/M19.C5.L-integration.V5.U03`, a separate `golden-pg` job) so the golden set runs from day one; the full database suite joins it once 3.0 is green. Run CI on production's Python, 3.11 |
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

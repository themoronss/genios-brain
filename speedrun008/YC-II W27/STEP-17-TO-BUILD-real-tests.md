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

---

## 8 · The check of 2026-10-12 — what the 5 Oct plan got right, and wrong

Re-checked claim by claim against `speedrun008` @ `c97155cd` by reading the code and running it: a
fresh scratch database migrated from zero (`0001`–`0199`, 195 tables), every SQL string the engine
holds prepared and explained against it, every Python file parsed on 3.11, and the lead's QA runs at
the same commit read for the suite's numbers. Since 5 Oct, `yc2_w27/M16` made the database suite
green (§3.0), STEP-01 put the golden set on Postgres in CI (§3.1, first half), and M34.C3 put this
folder under a guard (§3.5, mostly). What does not exist yet: the full database suite in CI, any
check that the engine's SQL is valid, a health gate that can say "no data", and a CI on production's
Python.

### 8.1 · Measured

| | |
|---|---|
| the database suite, today | **20,569 passed · 0 failed · 4 skipped · 86 xfailed**, 54 min — the lead's STEP-12 QA at `c97155cd`. None of the 4 skips is for want of a database (a missing `docx` locally, an empty parameter set, a declared rollback exception, an internal-auth harness) |
| CI's `test` job (the hermetic command) | **17,390 passed · 1,900 skipped** — 10 Oct at `3e2dba8d`. 1,896 of the skips are for want of a database, in **307 files**; 6 of those are `tests/replays`, which `golden-pg` runs. So **301 database-gated files never run in CI** — the plan said 150; it doubled as every step since added real-Postgres tests |
| the SQL the engine holds | `platform/table_coverage` counts **3,064** statements. **745** of them are pieces of a larger statement (the left side of a `+`, the text of an f-string) and **21** are docstrings that start with *Select* or *Update*. Of the **2,298** whole expressions: **2,040** prepare and plan on Postgres 17; **41** are not SQL (a bare `'update'` in a vocabulary set, a regex, a help text); **217** are assembled at run time from a helper or a local (`where {clause}`) and cannot be planned from the source; **1 is broken** (`scripts/slice_weight.py`, S17-F1) |
| the `card_level` bug, as a test would see it | the calibration statement is three modules of fragments (`"with " + AUDITED_CARD_JUDGMENTS_CTES + …`). Read as text, it is a statement with holes and nothing plans it. Read with each module's constants resolved, it plans — so the test must resolve them, or B1 comes back unseen |
| Python 3.11 | all **1,965** Python files of `genios_engine/`, `scripts/` and `tests/` parse on 3.11.17 (`python:3.11-slim-bookworm`, the Dockerfile's base). The suite has never run on 3.11 |
| the health gate | 19 checks. **Six already know they had nothing to judge** — they say *"not exercised"* or *"skipped"* in their measured line — **and print PASS**. The two LLM checks pass when a lane made no call (F24's shape) |
| the plan folder's guard | reads a step's Verify only when it is `## 6 · Verify` — STEP-01 (§7) and STEP-08 (§5) are never read, nor this file (§5) |
| clocks in tests | **22** test modules read the wall clock at import (`NOW = datetime.now(...)` at module level) — `03` F142's shape. Among them `tests/capture/test_unread_reread_pg.py`, three of F115's four |

### 8.2 · The claims

| # | Claim (§1) | Now | Evidence |
|---|---|---|---|
| 1 | CI runs only the hermetic suite | **partly** — `golden-pg` runs `tests/replays` on a Postgres 17 service since STEP-01; the rest of the database suite still skips | `.github/workflows/ci.yml:19-38` (`test`), `:40-76` (`golden-pg`) |
| 2 | the real-Postgres seam exists, and skips | **true** — and it is the only thing between 301 files and CI | `tests/conftest.py:61-67, 78-89, 103-138` |
| 3 | green while broken | **true in kind** — no test plans a statement it does not run; S17-F1 is a script that has never run | `scripts/slice_weight.py:31-37` |
| 4 | a production gate exists, seven checks, on `harsh/mvp` | **true, grown** — on this branch, 19 checks, exit 1 on a failure | `scripts/pipeline_health.py:859-918` |
| 5 | the database suite: 50 failed | **fixed** — 0 failed since `yc2_w27/M16` (5–6 Oct); 20,569 passed today | the lead's QA, `c97155cd` |
| 6 | a gate can pass on no data | **true** — six checks say so in words and still print PASS; an LLM lane with no call passes | `scripts/pipeline_health.py:155, 232, 624, 688, 784, 827`; `:79-125` |
| 7 | tests that expire; the pattern not swept | **partly** — the three were fixed (M16.C3); the import-time clock is in 22 modules | the census in 8.1; `tests/test_device_api.py:42` |
| 8 | three Python versions | **true** — production 3.11, CI 3.12, local 3.13 | `Dockerfile:33`; `ci.yml:25, 62` |

| # | Unit (§3) | Now | Evidence |
|---|---|---|---|
| 3.0 | the database suite green | **done** | `yc2_w27/M16`; 0 failed today |
| 3.1 | Postgres in CI, on 3.11 | **half** — the golden set only, on 3.12 | `ci.yml:40-76` |
| 3.2 | every statement explained | **not built** — and the plan's wording is not enough: "each statement known to `table_coverage`" counts pieces and docstrings, and leaves B1 as a statement with holes | 8.1 |
| 3.3 | write paths that cannot write | **a third done** — edge types: a guard reads every writer's AST (`tests/context/test_the_edge_vocabulary_is_closed.py`, M16.C1) and `write_edge` raises; no script writes an edge. Feedback reasons: **not guarded, and still broken** (S17-F7). L4 features: the defaults are derived (`tests/test_the_cutover_switch_can_be_flipped.py:175`), but nothing switches them on against a real database | `context/graph_store.py:178-205`; `migrations/0034_l4_learning_authority.sql:166-168`; `platform/intelligence_onboarding.py:189` |
| 3.4 | the health gate in deploy; no data is not a pass | **not built** — no deploy hook in the repo; no third verdict | `scripts/pipeline_health.py:42-50` |
| 3.5 | the plan's own checks, here | **mostly done** — `tests/test_the_plan_folder_is_consistent.py` (M34.C3, 10 Oct) holds names, titles, owners, decisions, open findings and Verify paths; it misses a Verify not numbered 6 (S17-F5) | `:146-159` |

### 8.3 · New — not in the plan

- **S17-F1 · A script that has never run.** `scripts/slice_weight.py` — L2-3's cost check —
  selects `anchor_type` from `context_situations`; the column lives on `context_correlations`. Every
  run raises `UndefinedColumn` on its first statement, since `aa6ab06e` (24 Sep). The sweep it
  claims to copy reads `n.node_type as anchor_type` from `graph_nodes`.
- **S17-F2 · The statement count counts pieces.** `table_coverage._statements` visits every string
  node, so `"select … from " + T` is two statements, and a docstring that starts *"Select only …"*
  is one. 745 + 21 of 3,064. Its table attribution needs the pieces (a whole expression with a call
  in it renders as nothing), so it is not changed; the planner counts whole expressions only.
- **S17-F3 · Six checks know they judged nothing and say PASS** (8.1). The line says *"not
  exercised"*; the verdict says the opposite.
- **S17-F4 · 301 database-gated files never run in CI** (8.1), not 150.
- **S17-F5 · The folder guard reads only a §6 Verify** (8.1).
- **S17-F6 · 22 test modules read the clock at import** (8.1). A long run — a sleeping laptop, a
  slow runner — moves the wall clock past their `NOW`. F142 is one of them; F115's three may be.
- **S17-F7 · B3 is still live in the schema.** Migration `0034`'s CHECK admits three reasons
  (`not_relevant`, `wrong_facts`, `bad_timing`); the route accepts all eleven
  (`api/intelligence_routes.py:956`, `= deliver/actions.WRONG_REASONS`). Eight would be a 500.
- **S17-F8 · `owns` is written with three meanings, declared with one** (F30, re-measured):
  company → deal (`context/pipeline.py:1689`, `backfill.py:329`), person → document
  (`context/documents.py:263`), person → commitment (`context/pipeline.py:2213`). The vocabulary says
  *company → deal*; `reason/moments/slice.py:267` and `reason/meetings/prep.py:255` read the third.

### 8.4 · What changes in the design

1. **"Every statement" means every whole expression, with its constants resolved.** The census
   takes the outermost string expression only, drops docstrings and single words, and resolves each
   `{NAME}` through the module's own value at run time (engine modules are imported; scripts are read
   from their AST, never run). That is what makes the `card_level` statement plannable — and a
   mutation that drops `card_level` from `canonical_judgments` must fail the test.
2. **A statement is planned the way Postgres will see it.** SQLAlchemy's own bind parsing (so
   `:x::int`, which it does not bind, fails as it would in production), an expanding `in :ids` as a
   list, `PREPARE` then `EXPLAIN EXECUTE` inside a transaction that is rolled back. A bind Postgres
   cannot type is typed by a search that accepts only a typing that plans — so the claim is *"some
   typing of the free binds plans it"*, said as such.
3. **What cannot be planned is counted, not hidden.** 217 statements are assembled at run time; a
   ceiling holds the number, so a new one fails the build until it is made static or the ceiling is
   raised in the same diff. Strings that look like SQL and are not are declared one by one, checked
   both ways.
4. **The health gate has three verdicts: pass, fail, no data.** A failure exits 1; no data is
   printed and counted apart and exits 0, unless the run asks for data (`--require-data`, exit 2). An
   LLM lane that called this week and not in the window is *no data* for that lane. The verdicts can
   be written as JSON, so a deploy can keep them.
5. **CI runs the whole suite on Postgres, on production's Python.** A `database` job beside the two
   that exist, and every job on the Dockerfile's Python, read from the Dockerfile by a test. A test
   that skips for want of a database fails that job.
6. **Not here:** F30's meaning split (S17-D4), determinism (F38, F41), L2's fixpoint (F45), the
   rebuild's lost company (F98), the decider's replay (F139) — engine changes, each its own step. And
   F143, F167, F168 live in `tests/replays/`, STEP-13's files today.

### 8.5 · What will be built — tree block `yc2_w27_s17` (M40, M41), proposed

Written to `baseline/yc2w27-s17/tree_s17.yaml` — not yet in `tree.yaml`, which the lead owns.

**M40 — the suite fails when production would** (12 units): C1 every statement planned — the census,
the planner, S17-F1's fix, the test over the whole tree · C2 write paths that cannot write — every
feedback reason stored (eight strict expected failures, STEP-16's), every default feature switched on
against Postgres · C3 the health gate says *no data* — the verdict, the LLM lanes, the kept output ·
C4 CI — the database-skip scan, the `database` job on 3.11 · C5 a Verify read whatever its number.

**M41 — tests that tell the truth** (4 units): the clock at import (F142, then the guard over the 22),
a timing guard that takes the best of three (F156), a test that claims its own rows (F67, F136).
F130 does not reproduce at `c97155cd` — `pytest tests/packs/*.py tests/packs/compiler/test_pattern_routing.py`:
380 passed, 13 skipped, 0 errors — so it has no unit; F115's three may be the clock at import (S17-F6)
and are re-measured after M41.C1.

**16 units, critical path 5** (M40.C1 U01 → U02 → U03 → U04 → M40.C4 U02).

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| S17-D1 | CI: a third job for the database suite, or the hermetic job given a database? | a third job — the hermetic job is the proof that a fresh clone with no database passes; the new one is the proof the SQL runs. About 50 runner-minutes more per push | a third job |
| S17-D2 | Does a *no data* check block a deploy? | no — it prints NO DATA and exits 0; the run a day after a deploy passes `--require-data` (exit 2), when every lane should have run | exit 0 |
| S17-D3 | Who runs the health gate after a deploy, and where is its output kept? | Harsh, as the last step of `08`'s deploy list, with `--json` into the release record; a red run is read before the next deploy. A CI job would need a read-only production role as a GitHub secret — your call, not built here | by hand, per `08` |
| S17-D4 | `owns` means three things (S17-F8) — split it? | declare the three meanings now, in the vocabulary's own words; split only when a reader is shown to confuse them | F30 stays open |

### 8.7 · Risks

- **A statement assembled at run time is invisible to the planner.** 217 of them; the database
  suite is their only check. The ceiling stops the number growing in silence, not the gap.
- **"Some typing plans it" is weaker than "the runtime's typing plans it."** A statement that needs
  a cast at run time could pass. It applies only to type errors; a missing column or table is never
  retried.
- **The ceiling will go red in someone else's diff.** The day STEP-13 adds a `where {clause}`, this
  test fails until the ceiling is raised in the same diff. That is the point; it will still be a
  surprise.
- **The suite has never run on 3.11.** It parses; the full run is the database job's own verify,
  in Docker on `python:3.11-slim-bookworm`, before the push.
- **A longer CI.** The database job is the slowest of the three (about 55 minutes here).

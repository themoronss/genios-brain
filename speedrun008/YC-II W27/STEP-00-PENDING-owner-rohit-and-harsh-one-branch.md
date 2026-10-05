# STEP-00 · PENDING — owner: Rohit (push, batched) and Harsh (deploy) · one branch, one baseline

**Depends on:** nothing. **Blocks:** every code step from `STEP-02` on. **Moves:**
`origin/harsh/mvp` vs this branch, **13 / 28 → 0 / N**. It also leaves a measured baseline,
committed together with the SQL that produced it.

✅ **Everything that is Claude's is done** — on 2026-10-05, then redone the same day (§4):

- one branch;
- the hermetic suite green;
- the database suite run for the first time, every failure attributed;
- a production baseline, committed with its statements.

⏳ **Two actions remain, both deliberately later.** Rohit pushes the whole batch at once, when the
steps are done (`06` D10). Harsh deploys after that.

---

## 1 · What was true before, measured 2026-10-05 `[CODE]`

```
git rev-list --left-right --count origin/harsh/mvp...speedrun008      →   13   28   (before)
                                                                       →    0   31   (at the merge)
```

| Branch | Ahead | What it holds |
|---|---:|---|
| `origin/harsh/mvp` — **what production runs** | 13 | Harsh's fixes of 2–4 Oct: park-queue routing (`adb04093`), the known-sender set read from the sent folder (`48768ca7`), readable attachment errors (`d4e035bb`), truncation detection (`2caf88aa`), the read-only pipeline-health gate and the narrator's token cap (`5ebfef8e`), expired cards rebuilt (`c22d0f00`, `2c42722d`), the slice row-order fix (`3f8d51e0`), the card drawer crash (`2f595277`), lapsed tenants stopped spending (`7075014c`), the no-data receipt (`7e19a1c9`), the tenant reset (`50c50073`), the five funnel numbers and object pruning (`9a51d0ea`) |
| `speedrun008` — **this branch** | 28 | the YCW27 programme since 1 Oct: receipts with witnesses, the SQL resolver, Atlas L1/L2 settled, the capture "where did it stop" tests |

### Every other remote branch

Each was dry-run merged (`git merge-tree`) against this branch.

| Branch | Commits this branch lacks | What a merge would change | Decision |
|---|---:|---|---|
| `origin/main` | 3 — two merges of `harsh/mvp`, one March README edit | **nothing** — the merged tree is identical | contained |
| `origin/rohit-yc-brain` | 19 (22 Aug – 9 Sep) | 88 files, **no code**. It moves 81 files from `Rohit_Updates/` into `Rohit_Updates (Version 2)/Version 1 Updates/`, and adds one failure-analysis document, `qa-contract.yaml` and `tree.yaml`. **3 conflicts**: `tree.yaml`, plus two `00-CORRECTIONS-2026-10-01.md` files this branch added inside the folder that branch renamed | **not merged** — a documents reorganisation, Rohit's call (`03-FINDINGS.md` E8) |
| `origin/antler-inception` | 6 (7–8 Aug) | 1,128 files, 171 of them code; **449 conflicts** — an older parallel build | not merged |
| `mvp`, `supabase`, `y-combinator-w27`, `speedrun008`, `claude/notion-…` | 0 | nothing | contained |

## 2 · Why this is step zero

The plan's steps touch the files Harsh has been fixing — `capture/parked/`, `reason/runner.py`,
`deliver/card_builder.py`, `api/routes.py`. Building on either branch alone guarantees one of two
failures: re-fixing what Harsh already fixed, or a merge in the middle of a step whose tests were
green on a base that no longer exists.

## 3 · How — and what happened

| # | Who | Action | Status |
|---|---|---|---|
| 1 | Claude, on Rohit's instruction | merge `origin/harsh/mvp` into `speedrun008` | ✅ `568a245d` — **no conflicts**. The branches overlapped only in `api/routes.py` and `deliver/card_builder.py`, in disjoint hunks |
| 2 | Claude | the hermetic suite, before and after the merge | ✅ before: **15,519 passed, 0 failed**. After: **15,669 passed, 0 failed** (§4.1) |
| 3 | Claude | the database suite — the 1,068 tests that skip without Postgres | ✅ run for the first time on this branch: **16,683 passed, 50 failed, 0 errors, 4 skipped**. **None of the failures is caused by the merge** (§4.2) |
| 4 | Claude | the production baseline, read-only, with its statements committed | ✅ `baseline/production_state.sql` → `baseline/2026-10-05/` (§4.3) |
| 5 | Claude | the per-workstream probe as a script | ✅ `scripts/workstream_funnel.py`, `f7784a9f` — 15 tests, **6 of 6 mutations rejected** |
| 6 | **Rohit** | push — **batched**: everything at once, when the steps are done | ⏳ his decision, 2026-10-05 |
| 7 | **Harsh** | deploy the pushed branch, with a **writable** database. No migration is needed today — production and this branch are both at `0190`; a later step that adds one says so | ⏳ after the push |

## 4 · The evidence

### 4.1 · The hermetic suite (no database)

| Run | Result | File |
|---|---|---|
| before the merge, `2dc61dac` | 15,519 passed · 0 failed · 1,067 skipped · 152 xfailed | `baseline/2026-10-05/suite_before_merge.txt` |
| after the merge, first run | **2 failed** — two pinned counts the merge moved | `suite_after_merge_first_run.txt` |
| after the merge, re-pinned | **15,669 passed · 0 failed** · 1,068 skipped · 152 xfailed | `suite_after_merge.txt` |

Both pinned counts were measured file by file, once on a pre-merge archive and once on the merge.
Each was then moved deliberately, as both tests ask, *"in a diff that names the SQL"*:

- **statements, 2,888 → 2,902:**
  - `api/routes.py` +2 (`48768ca7`);
  - `platform/warm_lane.py` +1 (`7075014c`);
  - `scripts/pipeline_health.py` +11 (`5ebfef8e`).
- **statements, 2,902 → 2,908:** `scripts/workstream_funnel.py`, six SELECTs.
- **tables, 186 → 187:** `signal_bundles`, first referenced by the reset's delete list (`50c50073`).

The merge commit's own tree was also checked in isolation: 2,902 statements, 187 tables, both
pinned files green.

### 4.2 · The database suite — the tests that had never run

**The database** is a scratch Postgres 17.11 in Docker; production runs 17.6. Migrations
`0001`…`0190` applied from zero without an error.

```
docker run -d --name genios-yc2w27-pg -e POSTGRES_PASSWORD=scratch -e POSTGRES_DB=genios_test \
  -p 127.0.0.1:55432:5432 postgres:17
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test \
  .venv/bin/python -m pytest -q -rfE
```

⚠️ **Use the `postgresql+psycopg://` scheme**, as the rest of the repo does. With a bare
`postgresql://`, `tests/test_llm_cost_attribution.py:179` builds its engine from the raw URL.
SQLAlchemy then picks `psycopg2`, which is not installed, and three setup errors appear that are
not defects.

**The result:** **16,683 passed · 50 failed · 0 errors** · 4 skipped · 152 xfailed, in 20
minutes. The 1,068 skipped tests became 4.

**Attribution.** Each failing file was run on three trees, each against a fresh database:

| Tree | Result |
|---|---|
| pre-merge `2dc61dac` | 50 failed |
| `harsh/mvp` `2c42722d` | 49 failed |
| merged `8a472b81` | 50 failed |

- **Failing only on the merge: none.**
- One test passes on `harsh/mvp` and fails on both others:
  `test_nothing_outside_the_publisher_writes_a_brain_entry`. It scans source **text**, and this
  branch's `feedback/target_policy.py` (`32a5c3a4`) mentions the statement in two comments
  (`:474, 512`). There is no second writer: a text guard was tripped by prose.

**The 50, by cause.** The full list is in `baseline/2026-10-05/suite_with_database.txt`.

| # | Cause | Where |
|---:|---|---|
| **27** | **the closed edge vocabulary** — `unknown edge_type 'involves'` (23) and `'edited'` (4), and the whole event rolls back | `context/graph_store.py` → `STEP-18` B2 |
| 5 | `int()` of a dict | `scripts/unit_reachability_report.py` |
| 4 | roster-to-audit expectations | `tests/reason/adapters/test_roster_reaches_the_audit.py` |
| 4 | the L1 G7 / G8 / G10 acceptance gates have nothing to measure — the replay scores 0 signals from 321 events | `tests/capture/test_g7_g8_g10_gates.py` |
| 2 | a text-scan guard tripped by two comments (above); an approver that resolves to `None` | `tests/packs/brains/test_org_discovery.py` |
| 8 | one each: CRM-closed resolution, L2 shadow diff, the publisher's coverage axis, the H0 placeholder gate, LLM-decision replay, out-of-office → availability, the per-tenant seam gate, the screen weekly claim | see the file |

⛔ **The edge-vocabulary bug is latent in production today, and it becomes live at `STEP-05`.**
Production has run L2 30 times since 3 Oct, with 0 edge errors (`@l2_processing_runs`). That is
because memory is gated on a signal (`01-CROSSCHECK.md` §3), so almost nothing reaches the
writers that raise. Once `STEP-05` sends every kept item into memory, every deal-shaped fact and
every document edit would roll its whole event back. **It must be fixed before `STEP-05`.**

### 4.3 · The production baseline — read-only, 2026-10-05, 13:51 UTC

**The statements are committed:** `baseline/production_state.sql`, run verbatim. Next to them,
`scripts/pipeline_health.py` and `scripts/workstream_funnel.py`.

| File in `baseline/2026-10-05/` | What it holds |
|---|---|
| `pipeline_health.txt` | **7 / 7 pass** — 0 unrouted emitted events · 29 known counterparties · no lane mostly failing in 24 h |
| `workstream_funnel.txt` | 365 inbound mails: 15 reached reasoning · 18 read, no signal · 67 junked · 258 deleted · 7 kept unread. Calendar: 35 events → 3 meeting nodes. Screen: 151 follow-ups, 140 open. Cards: 18 queued, 3 surfaced, 1 expired. Model calls in 3 days: `l4_llm_decision` 2,159 · `l4_llm_r1` 1,264 · `relevance_gate` 753. Every expert-context table 0 |
| `production_state.txt` | the funnel per sweep and per stage; L2 runs; the park queue and why attachments fail; the decider's calls per day (718 · 477 · 1,204 · 306); the narrator's ceiling; L3 `admin` only; L4 brief, bundle, critique, ranking_v2, roster_v2; migrations at `0190`; Gmail and Calendar connected since 21 Aug; Postgres 17.6 |

**How it was read.** `scripts/pipeline_health.py`'s own CLI goes through
`scripts/_db.resolve_database_url`. For a Supabase host, that resolver also demands
`GENIOS_ALLOW_PROD_WRITE=1`, and Claude does not set a write flag in order to read. Instead, one
connection was opened from `scripts/_gate.read_only_connection`, whose first statement is
`set transaction read only`. The scripts' own functions and the committed statements all ran
through it. Harsh can reproduce the same results with the CLI, or with
`PGOPTIONS='-c default_transaction_read_only=on' psql "$URL" -f baseline/production_state.sql`.

### 4.4 · What the baseline says

**What is live.** A 7 / 7 pass says production's data is healthy on seven checks. It does not say
which commit runs:

- `d4e035bb` is **visibly live**: the refetch errors written on 5 Oct carry their reason.
- `5ebfef8e`'s narrator cap **cannot show yet**. Every narrator failure of 4 Oct stopped at exactly
  1,400 tokens, the last at 11:30 UTC, before the fix was committed. No narrator call has run
  since, so the 24 h ceiling check passed on no data for that lane (`03-FINDINGS.md` F24).

**What does not move.** None of Harsh's fixes moves the numbers this plan is about:

- the deleted, junked and unreached mail is where `01-CROSSCHECK.md` left it;
- since 3 Oct the funnel has run 64 sweeps; `decision_emitted` was written in 3 of them, and
  `card_delivered` was 0 in the last 7 that wrote it.

That is the floor `STEP-02` onward is measured from.

**Three live bugs nobody had seen.** The re-do found them, and each now has a row in `STEP-18`:

| | What | The measurement |
|---|---|---|
| **B17** | the funnel never records a zero decision — the runner counts into a `Counter`, and the relay turns a missing key into *"nobody looked"* | `decision_emitted`: 3 rows in 64 sweeps, values 1–4, never 0 — while `capability_resolved` was written in 59 |
| **B18** | a mail whose extraction did not parse waits forever: the extractor's four park codes are in no drain set | 2 mails pending since 3 Oct 11:17 UTC, 0 attempts. The funnel counts them as *kept unread* |
| **B19** | **no Gmail attachment is read**: Composio refuses every fetch — *"Missing required fields: file_name"* | 88 of 88 stored errors are this one; 50 dead-lettered, 38 pending, 0 ever recovered. Khushi's two attachments and NSRCEL's 22 are among them |

## 5 · Expected

- one branch — ✅ `0 / N`;
- the hermetic suite green — ✅;
- the database suite run, every failure attributed — ✅. Making it green is its own work (§7);
- the baseline committed with its statements — ✅;
- pushed and deployed — ⏳ batched, by Rohit's decision.

## 6 · Verify

```
git fetch origin && git rev-list --left-right --count origin/harsh/mvp...speedrun008    # 0 N
.venv/bin/python -m pytest -q                                                          # 0 failed
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test \
  .venv/bin/python -m pytest -q                                                        # today: 50 failed, 0 errors
```

## 7 · What comes out of this step

1. **Recommended next, before `STEP-01`: make the database suite green** — `STEP-17` §3.0.
   Every later step's *verify* runs against Postgres. Inside it, `STEP-18` B2 goes first: it
   accounts for 27 of the 50 failures, and `STEP-05` would make it live.
2. **B17, B18 and B19.** Each is small and certain, and each has a production probe in
   `baseline/production_state.sql`.
3. Then `STEP-01`. Its engine-driving runner uses the same scratch database.
4. Nothing is pushed until Rohit pushes the batch.

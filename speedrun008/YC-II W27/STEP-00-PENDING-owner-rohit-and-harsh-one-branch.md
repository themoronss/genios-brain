# STEP-00 · PENDING — owner: Rohit (push) and Harsh (deploy) · one branch, one baseline

**Depends on:** nothing. **Blocks:** every code step from `STEP-02` on. **Moves:**
`origin/harsh/mvp` vs this branch, **13 / 28 → 0 / 31**, and a deployed baseline written
down. ✅ Merged, tested and baselined on 2026-10-05; the push and the deploy remain (§8).

---

## 1 · What was true, measured 2026-10-05 `[CODE]`

```
git rev-list --left-right --count origin/harsh/mvp...speedrun008      →   13   28   (before)
                                                                       →    0   31   (after, §8)
```

| Branch | Ahead | What it holds | Pushed? |
|---|---:|---|---|
| `origin/harsh/mvp` — **what production runs** | 13 | Harsh's production fixes of 2–4 Oct: park-queue routing (`adb04093`), the known-sender set read from the sent folder (`48768ca7`), readable attachment errors (`d4e035bb`), truncation detection (`2caf88aa`), the read-only pipeline-health gate and the narrator's token cap (`5ebfef8e`), expired cards rebuilt (`c22d0f00`, `2c42722d`), the slice row-order fix (`3f8d51e0`), the card drawer crash (`2f595277`), lapsed tenants stopped spending (`7075014c`), the no-data receipt (`7e19a1c9`), the tenant reset (`50c50073`), the five funnel numbers and object pruning (`9a51d0ea`) | yes |
| `speedrun008` — **this branch** | 28 | the YCW27 programme since 1 Oct: receipts with witnesses, the SQL resolver, Atlas L1/L2 settled, the capture "where did it stop" tests | **no** — `git push` is refused for Claude by the auto-mode classifier, and Claude does not retry or work around it |

## 2 · Why this is step zero

The plan's steps touch the files Harsh has been fixing — `capture/parked/`, `reason/runner.py`,
`deliver/card_builder.py`, `api/routes.py`. Building on either branch alone guarantees one of two
failures: re-fixing what Harsh already fixed, or a merge in the middle of a step whose tests were
green on a base that no longer exists. *(Measured at the merge: the two branches overlapped in only
two files, in disjoint hunks — no conflicts.)*

## 3 · How

| # | Who | Action | Status |
|---|---|---|---|
| 1 | Claude, on Rohit's instruction | merge `origin/harsh/mvp` into `speedrun008` | ✅ |
| 2 | Claude | the full suite before and after the merge — **no skip counted as a pass** | ✅ |
| 3 | Claude | the production baseline, read-only, kept in `baseline/2026-10-05/` | ✅ |
| 4 | **Rohit** | `git push origin speedrun008` | ⏳ |
| 5 | **Harsh** | deploy the pushed branch — with a **writable** database (a read-only database crash-loops every deploy, `9a51d0ea` / `7e19a1c9`) | ⏳ |

## 4 · What will happen

Nothing you can see. This is the floor every later number is measured from.

## 5 · Expected

- one branch: `git rev-list --left-right --count origin/harsh/mvp...speedrun008` → `0 N`;
- the full suite green on it;
- production running it;
- `baseline/<date>/pipeline_health.txt` and `baseline/<date>/workstream_funnel.txt` committed here.

## 6 · Verify

```
git fetch origin
git rev-list --left-right --count origin/harsh/mvp...speedrun008           # 0 N — nothing left out
.venv/bin/python -m pytest -q                                               # 0 failed
GENIOS_TARGET_DATABASE_URL=<url> GENIOS_ALLOW_PROD_WRITE=1 \
  .venv/bin/python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a; echo "exit=$?"
# ⛔ scripts/_db refuses any Supabase host without GENIOS_ALLOW_PROD_WRITE=1, even for this
#    read-only gate. That is Harsh's flag to set. Claude does not set a write flag to read —
#    see §8 for how the baseline was read instead.
```

## 7 · If this does not happen

`STEP-01` still runs — it only adds new files under `tests/replays/specs/founder/` and
`scripts/`. **No other step starts.**

---

## 8 · Progress — 2026-10-05

On Rohit's instruction — *"Harsh MVP se pull le lo, Step 00 karo"* — Claude did the merge and the
baseline. Two actions are left, and neither is Claude's.

| # | Action | Who | Status | Evidence |
|---|---|---|---|---|
| 1 | merge `origin/harsh/mvp` into `speedrun008` | Claude | ✅ **done**, no conflicts — the branches overlapped only in `api/routes.py` and `deliver/card_builder.py`, in disjoint hunks | merge commit `568a245d`; `git rev-list --left-right --count origin/harsh/mvp...speedrun008` → `0 31` |
| 2 | the full suite, before and after | Claude | ✅ **before:** 15,519 passed · 0 failed · 1,067 skipped · 152 xfailed. **After:** **15,669 passed · 0 failed** · 1,068 skipped · 152 xfailed. The first run after the merge failed two pinned counts (statements 2,888 → 2,908, tables 186 → 187); each was traced per file to its source and moved deliberately, as both tests ask | `baseline/2026-10-05/suite_before_merge.txt`, `suite_after_merge.txt` |
| 3 | the production baseline | Claude | ✅ `pipeline_health` **7 / 7 pass**; the workstream funnel written | `baseline/2026-10-05/pipeline_health.txt`, `workstream_funnel.txt` |
| 4 | the funnel probe as a script | Claude | ✅ `scripts/workstream_funnel.py` + `tests/scripts/test_workstream_funnel.py` — 15 tests; **6 of 6 mutations rejected** (a write, a dropped org filter, a reordered fate, unmatched mail swallowed, a statement passed by name, a non-read-only connection) | the test file |
| 5 | **push** | **Rohit** | ⏳ | `git push origin speedrun008` |
| 6 | **deploy** the pushed branch | **Harsh** | ⏳ | production already runs `harsh/mvp`'s fixes (7 / 7); the deploy adds `speedrun008`'s 28 commits |

### How the production baseline was read

`scripts/pipeline_health.py`'s own CLI goes through `scripts/_db.resolve_database_url`. For a
Supabase host that resolver also demands `GENIOS_ALLOW_PROD_WRITE=1`. Claude does not set a write
flag for a read. Instead the scripts' own functions — `pipeline_health.run`,
`workstream_funnel.inbound_mail`, `tally`, `beyond_mail` — were called through one connection from
`scripts/_gate.read_only_connection`, whose first statement is `set transaction read only`, so the
server refuses any write. Harsh can reproduce it with the CLI, which takes the flag.

### What the baseline says

```
pipeline_health   7 / 7 pass — 0 unrouted emitted events · 29 known counterparties ·
                  no model lane failing or truncating in 24 h
inbound mail      365 = 15 reached reasoning · 18 read but no signal · 67 junked ·
                  258 deleted · 7 kept unread
calendar          35 events → 3 meeting nodes
screen            142 follow-ups, 133 open
model calls       3 days: l4_llm_decision 2,447 · l4_llm_r1 1,464 · relevance_gate 751 · l1_extract 209
context           every expert-context table 0 · 118 unclassified observations, 0 reviewed
```

Harsh's fixes are live and passing. **None of them moves the numbers this plan is about.** The
deleted, junked and unreached mail is exactly where `01-CROSSCHECK.md` left it. That is the floor
`STEP-02` onward is measured from.

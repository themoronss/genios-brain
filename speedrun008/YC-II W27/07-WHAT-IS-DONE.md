# 07 · What is done — each finished step, its proof, and what is still owed

**Written for:** Rohit, Harsh, and whoever picks this folder up next. **As of:** 2026-10-06,
after Rohit's push. A step is listed here once everything that is Claude's in it is done. It
becomes **DONE** only when its number moves on production (`00-START-HERE.md`, "How we work
through it" §3), and this page says, step by step, what is still owed before that.

---

## 1 · Where this work lives

Everything in this programme — the nineteen steps, the decisions, the findings, the golden set's
records — is in **`speedrun008/YC-II W27/`**, this folder. It sits beside `speedrun008/YCW27/`,
an earlier programme (the six layers and their receipts), which it does not replace: `YCW27` is
the record of what was built; `YC-II W27` is the plan to make it reason like an expert. The code
is one branch, `speedrun008`, and the units are block `yc2_w27` of `tree.yaml`.

## 2 · The push — 2026-10-06

| | |
|---|---|
| pushed by | Rohit — the batch (`06` D10) |
| `origin/speedrun008` | `77aba10e` — the same as the local branch: 0 behind, 0 ahead (`git fetch origin`, 2026-10-06) |
| in this push | 88 commits since `3e36951b` (1 Oct) |
| against production's branch | `origin/harsh/mvp` is still `2c42722d` (4 Oct) — **75 commits behind `speedrun008`, 0 ahead**: the deploy is a fast-forward, with no conflict |
| migrations | none in the push — the newest is still `0190`, which production already has |
| CI on the push | run `37407196202` — see §7 |

## 3 · The nineteen steps

| Phase | Steps | Status |
|---|---|---|
| 0 · Ground truth | `STEP-00` one branch · `STEP-01` the golden set | both **PENDING — Harsh** (deploy). Claude's part done, pushed |
| 1 · Remember everything | `STEP-02` change gate · `03` the gate keeps everything · `04` who is us · `05` every item enters memory · `06` nothing lost silently | TO BUILD |
| 2 · The expert's desk | `STEP-07` company brief · `08` the re-sync · `09` workstreams · `10` history, patterns, analytics | `08` **PENDING — Harsh** (after 03–07 are live); the rest TO BUILD |
| 3 · Expertise | `STEP-11` founder playbooks | TO BUILD |
| 4 · The expert thinks | `STEP-12` the expert pass · `13` check every claim | TO BUILD |
| 5 · What you see | `STEP-14` the card · `15` the morning brief | TO BUILD |
| 6 · Learning from you | `STEP-16` | TO BUILD |
| Across all phases | `STEP-17` real tests · `18` known bugs | TO BUILD — six of `STEP-18`'s bugs are fixed in code and pushed (§5) |

**19 steps: 2 finished by Claude and pushed (`00`, `01`), 1 waiting on Harsh from the start (`08`),
16 to build.** The next is `STEP-02`.

## 4 · STEP-00 · one branch, one baseline

**What was done** (`STEP-00-PENDING-owner-harsh-one-branch.md`):

- `origin/harsh/mvp` merged into `speedrun008`, no conflicts (`568a245d`) — 13 / 28 → 0 / N;
- the hermetic suite before and after the merge: 15,519 → 15,669 passed, 0 failed;
- the database suite run on this branch for the first time: 16,683 passed, 50 failed — every
  failure attributed, none caused by the merge — and then made green by `yc2_w27/M16`: **16,736
  passed, 0 failed** (`e151a7db`, `baseline/m16-green/`);
- a production baseline, read-only, committed with every statement that produced it
  (`baseline/production_state.sql` → `baseline/2026-10-05/`);
- `scripts/workstream_funnel.py` — where each piece of work's mail went (`f7784a9f`).

**Still owed:** Harsh deploys `speedrun008` — production then runs one branch. The step's own
number (the branch gap) is already 0 / N; DONE is the deploy.

## 5 · The bugs fixed on the way — `STEP-18`, tree `yc2_w27/M16–M18`

All six are fixed in code with a test that fails without the fix, and pushed. **None is deployed,
so none is DONE**: each is closed only when its production probe is re-run after the deploy.

| Bug | What it was | Fixed in | The probe after the deploy (read-only) |
|---|---|---|---|
| B2 | four writers emitted edge types the closed vocabulary refused — the whole event rolled back | `d8c83cb4` | `baseline/production_state.sql` `@l2_processing_runs` — no edge errors |
| B17 | the funnel never wrote a zero decision, and counted one lane of three | `94a93d9f` | `@funnel_per_stage` — `decision_emitted` in every sweep, zeros included |
| B18 | a mail whose extraction failed waited forever | `9bfd911e`, `5c892922`, `2e76cf4a` | `@park_queue` — the two `extraction_parse_failed` mails get attempts |
| B19 | no Gmail attachment was ever read — `file_name` missing | `681a85e3`, `8ca130a3` | `@attachment_refetch_errors` — new errors are not the `file_name` refusal |
| B20 | a disconnect-with-wipe, then a reconnect, extracted nothing | `36567231`, `ba0577e3` | after a reconnect, no `seen_on_screen` against an event that is gone |
| B1 | calibration failed every run since 10 Sep — and the one-line fix alone armed auto-muting | `184269a0` (shadow first, then the column) | `select max(evaluation_time), count(*) from calibration_runs` — runs again, applies nothing |

⛔ **One unit is blocked:** `M17.C3.L-integration.V2.U04`, pinning the Composio toolkit versions.
It needs the SDK the production image runs — Harsh.

## 6 · STEP-01 · the golden set

**What was built** (`STEP-01-PENDING-owner-harsh-the-golden-set.md` §10):

- 40 synthetic founder cases, one per row of `golden-labels.md`, each with a cassette of
  recorded model answers, replayed through the real chain on Postgres — the production sync door,
  the floor, `_run_l2_chain` at the case's own instants;
- the Atlas replays 01–07 judged on the engine's output, not on their own strings;
- the board (`scripts/golden_score.py`), the live evaluation (`scripts/golden_eval.py` — not run:
  no model spend, `06` D12c, ≈ $0.63 a pass), a `golden-pg` CI job;
- three engine fixes the set found: the narrator was shown one situation two ways (`e730720d`,
  `64110e92`), and a statement could be pinned on the founder as the counterparty of the founder's
  own mail (`9e5cede8`).

**The before-score** — every later step is measured against it (`03-FINDINGS.md` §F.1):

```
founder golden set   must-detect  4/30 (8 not expressible)   must-abstain  5/10 (2 not exercised)   forbidden outputs  4
atlas replays 01–07  passing  0/80   blocked  7/80   not expressible  73
must-detect cases lost at:  gate 5  memory 9  reasoning 3
```

The biggest loss is the qualification floor: 9 of the 18 failing must-detect cases never reach
memory (`03` F44 → `STEP-03`, `04`, `05`).

**QA before the push** — `baseline/yc2w27-qa/qa_record.txt`, at `83dd87f3` on an empty scratch
database: every unit's own verify **55 pass / 1 fail / 0 skip** (the fail is the blocked unit
above); the whole suite with and without the database exit 0; the golden lane 357 passed, 100
xfailed, 0 skipped; the board matches §F.1; the hermetic job 16,018 passed.

**On GitHub, after the push:** see §7.

**Still owed:** the deploy (the three engine fixes); the labels are mine until Rohit corrects
them (`06` D12a — optional, nothing waits on it).

## 7 · CI on the push

| Job | Run `37407196202`, on `77aba10e` |
|---|---|
| `golden-pg` — the golden set on Postgres 17, Python 3.12 | ✅ **passed**, 03:03–03:10 UTC — its first run anywhere but the scratch database |
| `test` — the hermetic suite | ⛔ **red on its old install.** It installed `.[dev]` alone; reproduced exactly (that install, Python 3.12), seven tests die at an import of a package `requirements.txt` ships — the six of `tests/test_office_extraction.py` (`openpyxl`, `python-pptx`, since 10 Sep) and the golden runner's door test (`anthropic`). Every CI run listed since 27 Sep, on both branches, failed |

**Fixed in `2e7aea5b`** — the `test` job installs `requirements.txt` first, as `golden-pg` already
did (`yc2_w27/M19.C5.L-integration.V5.U05`). Run the way the new job runs — a git checkout of the commit, Python 3.12, `requirements.txt`
then `.[dev]`, `pytest -q -m "not golden"` — it gives **16,020 passed, 0 failed** (the 1,093
skipped are the database tests, which `golden-pg` and the database suite run). ⏳ It reaches GitHub
with Rohit's next push.

## 8 · Harsh's list — after the deploy, in this order

The full notes, with commands, expected outputs and what not to do: **`08-FOR-HARSH-deploy-and-after.md`**.

1. Deploy `speedrun008` @ `77aba10e` or later. No migration.
2. Re-queue the attachments the `file_name` refusal dead-lettered — dry run, then `--apply`.
3. Read the first `refetch_last_error` that comes back — it now names the response's shape.
4. Pin the Composio toolkits — `yc2_w27/M17.C3.L-integration.V2.U04`.
5. Re-run the probes and send the outputs; each bug is closed on its own probe.

## 9 · Decisions still open — none blocks the next step

| | Question | What holds until you answer |
|---|---|---|
| `06` D12a | label the 40 golden items yourself? | my labels, every row marked `claude` |
| `06` D12c | spend on a live evaluation of the golden set? | no spend; ≈ $0.63 a pass on Haiku 4.5 |
| `06` D13 | may calibration mute or nudge on your account? | shadow — it records, applies nothing; arming not before `STEP-18` B22–B24 |
| — | is `GENIOS_L4_LLM_DECISION_MAKER` on in production? | the golden set assumes on; one look at the deploy's environment |

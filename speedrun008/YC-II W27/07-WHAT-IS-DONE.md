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
| 1 · Remember everything | `STEP-02` change gate · `03` the gate keeps everything · `04` who is us · `05` every item enters memory · `06` nothing lost silently | `02`–`06` **PENDING — Rohit (push), Harsh (deploy)**: built, QA green (§6b–§6f) |
| 2 · The expert's desk | `STEP-07` company brief · `08` the re-sync · `09` workstreams · `10` history, patterns, analytics | `07` **PENDING — Rohit (push; accept the brief), Harsh (deploy, migration `0195`; draft it)**: built, QA green (§6g) · `08` **PENDING — Rohit (push; the window, D5/D16), Harsh (the run, after the brief — `06` D26)**: built, QA green (§6h) · `09` TO BUILD — checked and planned (`STEP-09` §8, tree `yc2_w27_s09`) · `10` TO BUILD |
| 3 · Expertise | `STEP-11` founder playbooks | TO BUILD |
| 4 · The expert thinks | `STEP-12` the expert pass · `13` check every claim | TO BUILD |
| 5 · What you see | `STEP-14` the card · `15` the morning brief | TO BUILD |
| 6 · Learning from you | `STEP-16` | TO BUILD |
| Across all phases | `STEP-17` real tests · `18` known bugs | TO BUILD — six of `STEP-18`'s bugs are fixed in code and pushed (§5) |

**19 steps: 9 finished by Claude (`00`, `01` pushed; `02`–`08` waiting for the push — `08`'s run is
Harsh's), 10 to build.** The next is `STEP-09` (workstreams): checked and planned (§8, tree
`yc2_w27_s09`, 10 units); the build starts on Rohit's go and `06` D2 / D30.

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

## 6b · STEP-02 · the change gate

**What was built** (`STEP-02-PENDING-owner-rohit-and-harsh-the-change-gate.md` §9): before the
decider and R-1 are asked, each lane fingerprints the request it is about to send — its own
capability and context, with time taken out — and skips a subject whose fingerprint is the one its
last decision was made on, while the card that decision left still has its authority. A DEFER keeps
the card it found. Every skip is counted, and a health check fails when the gate saves nothing.

**Measured:** on all 40 founder cases, a sweep that brings nothing new makes **0 decider and 0 R-1
calls** (before: F13 2 … F29 12), the cards are the same, and the board did not move. QA green at
`aaca7e67` (`baseline/yc2w27-s02-qa/qa_record.txt`).

**Still owed:** the push; Harsh's deploy, which applies migration `0191` at boot; then production's
`@model_calls_by_day` before and after — 760–1,890 a day today, under 100 the target.

## 6c · STEP-03 · the gate keeps everything

**What was built** (`STEP-03-PENDING-owner-rohit-and-harsh-the-gate-keeps-everything.md` §9): the
gate no longer deletes a mail. What a noise rule or the AI filter's confident junk verdict used to
drop is **archived** — its encrypted payload kept 180 days (`06` D4), read by no model — with the
rule as its reason; every mail carries an attention tier (`deep` · `skim` · `archive`). Every reader
of `dropped` learned `archived`: the sync summary, the run ledger, the drain, a new receipt, the
funnel, the golden marking, and a health check.

**Measured:** on the golden set, the same replay before and after — 33 of 86 mails dropped with their
content gone → **0**; the same 33 archived with the same code; every one of the 40 cases marked
exactly as before; the board matches. Found while building: an archive with prepared text is read by
the resolution model (F37) — so an archive keeps its payload only; and the pipeline emitted any gate
verb it did not know.

**QA:** green at `81857ce2` (`baseline/yc2w27-s03-qa/qa_record.txt`) — the units 21 / 0 / 0; the database suite
17,434 passed, 0 failed; the golden lane 442 passed, 0 skipped; the board matches; the hermetic job
16,166 passed. Run 1 (`ef011cb0`) was red on one database-only test that still expected a drop.

**Still owed:** the push; Harsh's deploy, which applies migration `0192` (with `0191`) at boot; then
the production number — new mail with its content deleted at the gate, 258 of 395 → 0, read by
`scripts/pipeline_health.py`.

## 6d · STEP-04 · who is us

**What was built** (`STEP-04-PENDING-owner-rohit-and-harsh-who-is-us.md` §9): one answer to *"is this
address, person or company one of us?"* — `platform/self_identity.identity_for`: the active seats,
`orgs.email`, the connected accounts, and what the tenant **declared** (new table, migration `0193`).
Twenty places used to decide it on their own; every one asks it now, and a guard fails the build if a
module builds its own set again. A card whose subject is one of us is refused and counted; a thread
is named after its other side; a Gmail founder no longer makes every Gmail sender a colleague. Two
scripts: declare the tenant's addresses and domain; repair what was built before (dry run first).

**Measured:** across all 44 golden cases — 0 cards about us, 0 cards naming us as a party, 0
situations anchored on us, 0 threads named after us; three planted defects each turn that check red.
The board: must-detect 5/32, must-abstain 5/12 — the forty cases did not move; four production-shaped
cases were added (F42 passes; F41, F43, F44 wait on `STEP-05`).

**QA:** `baseline/yc2w27-s04-qa/qa_record.txt` — run 1 at `c0e24f00`, a database created for every check: the units 48 / 0 / 0; the whole database suite 17,696 passed, 0 failed (the same four optional skips); the golden lane 520 passed, 103 xfailed, 0 skipped; the board matches; 0 golden tenants left; the hermetic job **red on one line** — the H0 gate read four new context tests' skip message as a placeholder (fixed in `78d7b4fd`). Run 2, the hermetic tier whole at `78d7b4fd`: 16259 passed, 1286 skipped, 184 deselected, 72 xfailed, 1595 warnings in 730.67s (0:12:10).

**Still owed:** the push; Harsh's deploy with migration `0193`; the declaration of `ceo@thegenios.com`
and `thegenios.com` (D6); the repair's dry run, **read by Rohit (D14)**, then `--apply`; the production
number — open cards about the founder → 0, threads named after him → 0
(`08-FOR-HARSH` §3.4, §4.2).

## 6e · STEP-05 · every kept item enters memory

**What was built** (`STEP-05-PENDING-owner-rohit-and-harsh-every-item-enters-memory.md` §9): every kept
event takes one road into memory, decided in one place — a signal (as before); **below the floor**, its
own L1 extraction, every claim ranked low, no model call (D20); an **archive** as names and dates only —
who wrote to whom, their companies, the thread — from the ledger's columns, never decrypted, not billed
(D21); every **calendar** event a meeting, keeping its organizer, its newest edit winning. Every
recovery — a re-admitted park, a refetch, a recapture, a promotion — is read again by the B18 ladder,
and the gate never judges a re-read out. Promotion out of the archive by a named rule, dry run first.
A receipt and a health check hold it.

**Measured:** on the golden set, lost before memory 10 → 0; must-detect 5/32 → 11/32 (F04, F05, F06,
F10, F26, F44 pass; F07, F11, F19, F24 now lost in reasoning); must-abstain 5/12 → 11/12, nothing
unexercised; Atlas replays 0 → 4 passing. The acceptance on every case: every kept event in memory,
every calendar event a meeting, no archive's words readable — a planted miss of each kind named.

**QA:** `baseline/yc2w27-s05-qa/qa_record.txt` — run 1 at `4909f718`, green on every tier, a database created for every check: the units 23 / 0 / 0 (4 tree checks + 19 units); the whole database suite 17,843 passed, 0 failed (the same four optional skips, re-listed with their reasons); the golden lane 584 passed, 87 xfailed, 0 skipped; the board matches (must-detect 11/32, must-abstain 11/12, Atlas 4/80); 0 golden tenants left; the hermetic job 16,300 passed, 1,328 skipped (the database tests, run in tier 2), 232 deselected, 72 xfailed in 721.47s (0:12:01).

**Still owed:** the push; Harsh's deploy (no migration); the first pass's numbers (`08` §3.5, §4.3);
Boardy's introductions promoted only after Rohit reads the dry run (D23).

## 6f · STEP-06 · nothing is lost silently

**What was built** (`STEP-06-PENDING-owner-rohit-and-harsh-nothing-lost-silently.md` §9): one writer of a
card's `expired` state, `platform/card_lifecycle`, called by all twelve places that used to set it (nine
wrote nothing), each with its cause — and History shows it. The compiled lane records what came of every
admitted live situation (migration `0194`): `decided`, or the stop and its reason. One reader names every
active situation's end, the journey every event's. The parked drain and the re-read ladder no longer
starve. Two receipts and a health check hold it.

**Measured:** on the golden set, active situations with no record of how they ended 126 of 227 → 0; card
expiry sites that write nothing 9 → 0; the board unchanged — STEP-06 changes no decision.

**QA:** `baseline/yc2w27-s06-qa/qa_record.txt` — run 1 at `d2146f4f`, green on every tier, a database created for every check: the units 28 / 0 / 0 (4 tree checks + 24 units; 1 retired); the whole database suite 17,989 passed, 0 failed (the same four optional skips, re-listed with their reasons); the golden lane 631 passed, 87 xfailed, 0 skipped; the board matches, unchanged (must-detect 11/32, must-abstain 11/12, Atlas 4/80); 0 golden tenants left; the hermetic job 16,339 passed, 1,388 skipped (the database tests, run in tier 2), 279 deselected, 72 xfailed in 763.88s (0:12:43).

**Still owed:** the push; Harsh's deploy with migration `0194`; the two production numbers (`08` §4.4).

## 6g · STEP-07 · the company brief

**What was built** (`STEP-07-PENDING-owner-rohit-and-harsh-the-company-brief.md` §9): the company brief in
its own table (migration `0195`), one writer, one composer; routes and a script for the founder to accept,
edit, reject, remove (the owner only, D27); a Sonnet-class drafter that proposes from memory patterns —
never a message — and proposes again weekly; the gate keeps and reads every sender the brief names
(**W-07**); the brief in every model call that judges or reads — twelve sites, held by a guard — and its
version in the change gate's fingerprint and every cache key; a health check.

**Measured:** on the golden set, every judging and reading prompt carries the brief (321 of 373, from 0),
no writing prompt does (52, byte for byte); 21 of the 33 objects the gate archived are now kept and read;
the board unchanged — four cases moved from lost at the gate to lost in reasoning (F01, F02, F03, F09).

**QA:** `baseline/yc2w27-s07-qa/qa_record.txt` (§9.4).

**Still owed:** the push; Harsh's deploy with `0195`; the first draft; Rohit's acceptance (`08` §3.6).

## 6h · STEP-08 · the mail the old gate deleted comes back

**What was built** (`STEP-08-PENDING-owner-harsh-the-resync.md` §9): `capture/landing/resync` frees the key of
every Gmail message the old gate deleted inside Rohit's window — the row stays `dropped`, so the orphan
recovery can never forge it into an emitted row with no body — and, after the existing backfill drain
has landed it again through today's gate, supersedes it, naming the event that replaced it, or says
why it did not come back; `scripts/resync_deleted_mail.py` (a read-only dry run by default; `--apply
--days N`; `--finish`); an attachment comes back once; the walk names the replacement both ways; a
health check. Found and fixed on the way: the re-read ladder could never read an attachment (`03` F87).

**Measured:** on the golden set the thirteen mails STEP-08's check rewrote to production's deleted shape
come back 13 of 13 with their body — the brief's ten read (W-07), three archived under their old rule —
and are superseded; a mail Gmail no longer lists is reported, not superseded; the health check goes
from red to green; a second run changes nothing; an attachment that survived its message is not
landed twice.

**QA:** `baseline/yc2w27-s08-qa/qa_record.txt` (§9.4).

**Still owed:** the push; the deploy; the brief accepted (D26); Rohit's window (D5 / D16 — 365
recommended); Harsh's run (`08` §3.7, §4.6).

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

1. Deploy `speedrun008` @ `77aba10e` or later. ⛔ The next push carries migrations `0191` (STEP-02)
   and `0192` (STEP-03); the boot applies them.
2. Re-queue the attachments the `file_name` refusal dead-lettered — dry run, then `--apply`.
3. Read the first `refetch_last_error` that comes back — it now names the response's shape.
4. Pin the Composio toolkits — `yc2_w27/M17.C3.L-integration.V2.U04`.
5. Re-run the probes and send the outputs; each bug is closed on its own probe.
6. ⛔ STEP-04: the next push also carries migration `0193`. Then declare the design partner's
   identity, run the repair DRY, send its list to Rohit, and `--apply` only after he reads it (D14);
   the health check must read 0 and 0 (`08` §3.4, §4.2).
7. ⛔ STEP-05: no migration. Watch the first chain pass (heavy, model-free) and read the two numbers a
   day later; the promotion of Boardy's introductions — dry run, Rohit reads it (D23), then `--apply`
   (`08` §3.5, §4.3).
8. ⛔ STEP-06: migration `0194_situation_outcomes` — the boot log must name it. Nothing to run after;
   read the two numbers before and a day after (`08` §1.8, §4.4).
9. ⛔ STEP-07: migration `0195_company_brief`. Then draft the company brief — patterns, the dry run to
   Rohit, `--apply` — and Rohit accepts it line by line; the health check must pass (`08` §1.9, §3.6, §4.5).
10. ⛔ STEP-08, only after 9: the dry run to Rohit, his window (D5 / D16), `PATCH …/backfill-window`,
    `--apply --days N`, `POST /connections/{gmail}/backfill`, `--finish`; the health check must read 0
    (`08` §3.7, §4.6).

## 9 · Decisions still open — none blocks the next step

| | Question | What holds until you answer |
|---|---|---|
| `06` D12a | label the 40 golden items yourself? | my labels, every row marked `claude` |
| `06` D12c | spend on a live evaluation of the golden set? | no spend; ≈ $0.63 a pass on Haiku 4.5 |
| `06` D13 | may calibration mute or nudge on your account? | shadow — it records, applies nothing; arming not before `STEP-18` B22–B24 |
| — | is `GENIOS_L4_LLM_DECISION_MAKER` on in production? | the golden set assumes on; one look at the deploy's environment |
| `06` D5 / D16 | how far back does STEP-08 re-read? | nothing runs: `--apply` refuses without a number; 365 recommended |
| `06` D2, D30 | STEP-09's scope, and may a connector's intro create the people it introduces? | M27 is drawn for A + yes; the build waits for your go |

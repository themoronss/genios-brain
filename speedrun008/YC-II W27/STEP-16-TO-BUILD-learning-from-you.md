# STEP-16 · TO BUILD · learning from you — your feedback and real outcomes change the next judgment

**Owner:** Claude. **Depends on:** `STEP-14`, `STEP-15`. **Moves:** a correction you make changes the
next decision on that file — and the change can be replayed and audited.

---

## 1 · What is true now

| | Evidence |
|---|---|
| Most feedback reasons cannot be saved | `[CODE]` 8 of 11 *"wrong because"* reasons return 500 — `migrations/0034:168, 189` allows only 3 |
| No feedback exists | `[PROD]` `card_feedback_verdicts` 0, `human_events` 0 |
| A learned preference has nowhere to go | `[CODE]` `user_model_proposals` has no writer; `user_models` has no reader in reasoning |
| Outcomes are not watched for founder plays | `[CODE]` an execution is monitored only when `success_events` is non-empty (`executive/execution.py:136-138`); compiled plays set none `[inference]` |
| The open lane waits for a person who is never asked | `[CODE]` review and promotion are on demand only (`capture/semantic/open_lane.py:36-39`, `api/admin_routes.py:792`); `[PROD]` 118 waiting |
| Calibration cannot run | `[CODE]` `feedback/calibrate.py:109` filters `card_level`, which `reason/authority.py:329` never projects — every weekly run errors (since 10 Sep) |
| Learning governance has three known stops | `[ATLAS]` Organization approval does not publish (`approved_unpublished`); a policy reload drops its block lists; an Adaptive proposal cannot carry an expiry — the Secret War audit's `RC-7` |

## 2 · Why

A 30-year expert is not born; she learns *your* company. Every correction should make the next
morning better — and nothing should be learned from a single click or a silence.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | every reason can be saved — ✅ **built by STEP-18, `0210`** (`61d679ed`; `yc2_w27_s18` M48.C1.L-contract.V0.U01) | `migrations/0210_every_wrong_reason_is_kept.sql` | the `0034` CHECK widened to all 11 reasons: two NAMED checks (`card_feedback_verdicts_reason_vocabulary`, `card_feedback_revisions_reason_vocabulary`). ⛔ This step writes no `0240` — a second migration on these constraints would be a second writer of one rule (the STEP-17/18 crosscheck S18-X10); `M46.C2.L-contract.V0.U01` is marked built, and M46.C2 keeps its one-writer unit (U02) and the dashboard's door (U03) |
| 3.2 | feedback becomes a proposal, never a rule | `feedback/`; `user_model_proposals` | *"not useful — I never want Boardy's newsletters"* → a brief proposal; *"wrong — this is not an investor"* → a workstream correction. You accept; then it applies. One click is never enough to learn a pattern |
| 3.3 | outcomes close loops | `executive/collect.py`; `STEP-09` | a reply arrives, a meeting is booked, an application advances → the file's stage moves, the exact ask closes, the card resolves **with the outcome recorded** |
| 3.4 | patterns update | `STEP-10` | your reply time, Boardy's conversion, a program's typical stage time — recomputed from outcomes, in the behaviour brain, **observe-only** (Atlas V.3) |
| 3.5 | the open lane is reviewed weekly | the learning sweep (`api/routes.py:1310`) | recurring unclassified kinds are proposed to you as new stages or kinds; accepted ones flow into `STEP-11`'s playbooks |
| 3.6 | calibration repaired, in shadow — **moved ahead into tree `yc2_w27/M18`** (Rohit's "B1", 2026-10-05) | `reason/authority.py:329-332`; `feedback/calibrate.py`; `platform/l4_activation.py`; `api/routes.py` | the shadow switch lands before the column: `run_calibration(apply=False)` records `would_mute` / `would_recover` / `would_nudge` and writes nothing else; `calibration_apply` is fail-closed and not default-on. **Arming stays here**, after `STEP-18` B22–B24 (a muted rule's cards vanish unexplained; a mute never lifts; any applied mute or nudge hides every open card of the pack) and `06` D13 |

## 4 · What will happen

You mark *"not useful — Theresa asked for updates only with real news; don't push me"*. That
becomes one proposal: *Antler / Theresa: send only on a material milestone.* You accept it. From
then on her file is Monitor until a milestone lands in your mail — and the next brief says so
under *Watching*, not under *Needs you*.

## 5 · Expected

- every feedback reason saves (0 × 500);
- an accepted correction changes the next judgment on that file, provably (replay shows the delta);
- a resolved file records its real outcome;
- the open lane is reviewed every week.

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/feedback -q      # the 27 tests that have never run, run
.venv/bin/python -m pytest tests/feedback/test_a_correction_changes_the_next_decision.py -q
```

---

## 8 · The check of 2026-10-12 — what the 5 Oct plan got right, and wrong

Re-checked claim by claim against `yc2w27-s13` @ `fbd0aeaa` (STEP-13 nearly built) by a read-only worker:
the code read; `tests/feedback` run file by file, without a database and on a fresh scratch database
(pg2); the eleven reasons inserted into the verdict ledger on a second fresh one; the golden set's 94
authored expert answers read. Production was not read. Since 5 Oct calibration runs in shadow
(`yc2_w27/M18`), STEP-12 made the expert's review each covered file's one decision, and STEP-13 made your
answer the first correction to reach the next judgment: it is printed in the file's dossier
(`[answer:<id>]`), the file's fingerprint names it, and it brings the file back to the expert. Nothing
else you say does. The *wrong because* you press on a card lands in a ledger the expert reads without its
reason and that moves nothing; a verdict moves a file's fingerprint and triggers no review; there is no
place to say a correction in your own words; nothing L6 learns reaches the expert; a founder play's
success is a sentence no monitor can see; and a file decision that ends records nothing of what closed it.

### 8.1 · Measured

| | |
|---|---|
| the doors your feedback comes in by | **two for a card** — the dashboard's button (`POST /cards/{id}/action` → `deliver/actions.ingest_action`) and the extension's (`POST /v1/intelligence/feedback`) — and a third for a screen reminder (`moment_feedback` → L6's inbox, loaded every week and consumed by no unit: `inbox_unconsumed`) |
| the eleven reasons, on a fresh scratch database (`0001`–`0201`) | the verdict ledger stores **3** (`not_relevant`, `wrong_facts`, `bad_timing`) and refuses **8** with an `IntegrityError` — the extension's 500. The dashboard's door stores all 11 — in `card_events` only |
| who reads which ledger | calibration reads both. **Eight** read only the extension's: the expert's dossier (a dashboard verdict shows there as `human.card_action (wrong)`, its reason dropped) and its file fingerprint, the change gate's inputs, the learning batch, the adaptive lease, a file's history facts, the counterfactual ledger, the receipt *"a human verdict has reached the loop"* |
| what brings a file back to the expert | a new mail or booking, a meeting held, your answer (STEP-13), a date a rung closer, a reply overdue, a number past the file's normal. A verdict moves the fingerprint and **triggers nothing**; *"the founder asked"* exists and is never passed |
| what the expert reads of L6 | **nothing** — no learned brain, no lease: 0 mentions in `reason/expert/` |
| the 94 authored expert answers (58 cases) | modes act 58 · wait 20 · find out 8 · nothing 8; **all 94** `done_when` are sentences, **0** an observation kind the monitor matches; 72 moves, **28** name the ask they answer (`answers`, a `loop:` id) |
| the rules calibration can score, per shipped pack | admin **0** · customer support **0** · general **5** · sales **20**; the expert's rule, `file_review`, is in none |
| `tests/feedback` | 17 files. Without a database **30 tests skip** (in 4 files), not 27; on a fresh scratch database all 30 pass, in about 4½ minutes. CI still skips them (`STEP-17` S17-F4) |
| the golden set | `outcome` is declared not expressible in **1** case, F57 — *"no card's end records the evidence that closed it"* |

### 8.2 · The claims

| # | Claim (§1) | Now | Evidence |
|---|---|---|---|
| 1 | 8 of 11 *wrong because* reasons return 500; `0034` allows 3 | **partly** — the extension's door 500s on 8 (measured: 3 stored, 8 refused). The dashboard's button stores all eleven, but in `card_events`, which eight of the nine verdict readers never read (N1) | `migrations/0034_l4_learning_authority.sql:166-168, 186-189`; `api/intelligence_routes.py:956, 976, 1071`; `deliver/actions.py:42, 67, 136-146`; `api/routes.py:5489-5507` |
| 2 | no feedback exists (`card_feedback_verdicts` 0, `human_events` 0) | **not re-measured** — production not read. The code writes both, by different doors: `human_events` and `card_events` by the dashboard, the verdict ledger by the extension; `human_events` has no reader | `deliver/actions.py:136-146`; `api/intelligence_routes.py:1071-1125`; `platform/table_coverage.py:155-161` |
| 3 | a learned preference has nowhere to go: `user_model_proposals` has no writer, `user_models` no reader in reasoning | **true** — and it is the wrong home: STEP-07 found the same table unwritten and built the brief, which has a *preferences* section and its own propose, accept and reject; and L6 left two units empty for want of exactly this — a surface where you say what you want (N7) | `api/usermodel_routes.py:53, 146-184` (no insert); `migrations/0195_company_brief.sql:6-8`; `feedback/units.py:182-233` |
| 4 | an execution is monitored only with `success_events`; compiled plays set none | **partly** — every founder play now names a success, the expert's `done_when` and the corpus's `success_signal`, but as a sentence; the monitor matches observation kinds, and no sentence is one. A founder play is watched and can never be seen to succeed (N5) | `executive/execution.py:137`; `reason/expert/decide.py:236, 245`; `reason/adapters/expertise.py:1056-1061`; `executive/execution_store.py:247-253`; `executive/monitor.py:102-105` |
| 5 | the open lane waits for a person never asked; 118 waiting | **true** in code (the 118 not re-measured) — the report and the promotion are admin calls, the heartbeat only purges the lane, and nothing under `reason/` or `packs/` may read it (its own fence) | `capture/semantic/open_lane.py:36-49`; `api/admin_routes.py:780, 838`; `api/routes.py:1213-1220` |
| 6 | calibration cannot run: `card_level` is never projected | **false in code** — the column is projected since `184269a0` (M18), and calibration is shadow unless a tenant's `calibration_apply` is armed, which is never by default (D13); on a fresh scratch database `test_calibration_runs_on_postgres` 2 passed, `test_calibration_is_shadow_until_armed` 5 passed. Production keeps erroring weekly until the deploy | `reason/authority.py:332-335`; `feedback/calibrate.py:110, 239-240`; `api/routes.py:1511-1518` |
| 7 | learning governance has three stops (`RC-7`) | **partly** — an approval publishes in the same transaction, and a policy loads both block lists with their state; an Adaptive proposal still cannot carry an expiry, by design: temporary guidance is a Runtime lease, and whether that stands is ADR-10, yours, unratified | `api/learning_routes.py:150-160`; `feedback/orchestrator.py:100-113`; `contracts/learning.py:222-227`; `docs/plans/ADR_RATIFICATION.md:95-104` |

The units of §3, against what exists:

| | Unit | Now |
|---|---|---|
| 3.1 | every reason can be saved | **not built** — and widening the CHECK alone leaves the dashboard's verdicts outside the ledger every learner reads |
| 3.2 | feedback becomes a proposal, never a rule | **not built** — no surface; the named home, `user_model_proposals`, is the wrong one (N7); the roads that exist are the brief's propose and accept (STEP-07) and your answers on a file (STEP-13) |
| 3.3 | outcomes close loops | **partly** — an ask closes on our reply, with what closed it and whether it answered (`open_loops`, `0167`), and STEP-13 suppresses an answered ask; nothing resolves the card with what closed it (N6), and the commitment can never succeed (N5) |
| 3.4 | patterns update, observe-only | **partly, the STEP-10 way** — reply times, waves and a connector's rate are computed on every dossier read, with their n; your own stage times and closes per kind of work exist nowhere; the behaviour brain is the compiled lane's, never the expert's (N3) |
| 3.5 | the open lane reviewed weekly | **not built** (claim 5) |
| 3.6 | calibration repaired, in shadow | **✅ built** (`yc2_w27/M18`, not deployed); arming stays `06` D13; `STEP-18` B22–B24 still open (`reason/runner.py:1360-1362` skips a muted rule and writes no suppression row) — and calibration never sees an expert card (N4) |

And §5 and §6: **0 × 500** holds on the dashboard's door and not on the extension's; **a correction changes the
next judgment** — not built: no correction surface, and a verdict is no trigger (N2); **a resolved file
records its outcome** — not built (N6); **the open lane weekly** — not built. §6's first command runs 17 files
and its 30 database tests pass on Postgres; its second names a file that does not exist yet.

### 8.3 · New — not in the plan

- **N1 · Two doors, two ledgers** (`s16-F1`). The dashboard's verdict and the extension's land in
  different tables, and every reader but calibration reads the extension's. So the reason you give on a
  card never reaches the expert, its fingerprint, the learning batch or the lease. Widening `0034` (§3.1)
  fixes the extension and leaves this.
- **N2 · A verdict is no trigger, and "you ask about it" has no door** (`s16-F2`). `05` §5 lists *you ask
  about it* among the five things that make the expert think; `triggers.FOUNDER_ASKED` exists and the
  sweep never passes it, and a verdict *"rides along with the next trigger"* — so a correction changes
  nothing until the file moves for another reason (`reason/expert/triggers.py:21-25, 155-170`;
  `reason/expert/sweep.py:181`).
- **N3 · Nothing L6 learns reaches a covered file** (`s16-F3`). The learned brains — Organization,
  Behaviour, the Adaptive leases — are read by the compiled lane's package compile only
  (`reason/domain_shadow.py:1534, 1544` → `packs/compiler/runtime_brains.py`); the expert reads none, and
  since M33 the compiled lane stands down on every file a review explains (`reason/runner.py:1363-1371`).
- **N4 · Calibration never sees an expert card** (`s16-F4`). The expert's rule is `file_review`, which
  no pack manifest names (`reason/expert/decide.py:130-132`), and calibration scores manifest rules only
  (`feedback/calibrate.py:300-305`). Arming it would judge the general pack's five rules and Sales' twenty
  on your org — not the files the expert decides.
- **N5 · A founder play's success is a sentence** (`s16-F5`) — measured in 8.1. Of the 72 authored
  moves, 28 name the ask they answer; that ask's closure is the one success code can see.
- **N6 · A file decision that ends says nothing of what closed it** (`s16-F6`). When a review names no
  move, the file's card is expired `rule_cleared` (`reason/domain_shadow.py:599-608`); the card lifecycle
  has no way to resolve a card (`platform/card_lifecycle.py:43-53`); and the evidence exists — an ask's
  closing event and whether it answered (`open_loops.closed_by_event`, `closed_basis`) — written since
  `0167` and declared *read by nothing* (`tests/test_nothing_is_written_and_never_read.py:188-199`).
- **N7 · The plan's home for a preference is the wrong table** (`s16-F10`). `user_model_proposals` is
  per-person persona JSON (`0023`) that nothing writes. `feedback/units.unit_preference_learning` and
  `unit_temporary_memory` return nothing because *"the gap is a `kind`, not a table: a SURFACE where a
  founder states a preference"* — the surface this step builds.
- **N8 · What L6 computes and nobody reads**: `learning_metrics`, `card_feedback_revisions`,
  `human_events` (`platform/table_coverage.UNREAD_WRITES`) and the per-layer debit of a *wrong because*
  (`feedback/attribution.route` — called by tests only) (`s16-F12`).
- **N9 · The public acted rate measures delivery** (`s16-F8`, widens `03` F76): acted is `claimed` plus
  `delivered`; the card's own `acted` and `resolved` states are not counted; `dismissed` is no card
  state; and every expiry, a replaced card's too, counts as ignored (`api/benchmarks_routes.py:72-85`).
- **N10 · A comment that already says eleven** (`s16-F7`): `context/correlation_history.py:208-211`
  says a `wrong` reason is *"one of the ELEVEN"*; the CHECK admits three (measured).
- **N11 · A question card cannot be called wrong** (`s16-F13`). STEP-13's question card offers *answer*
  and *snooze* only; *wrong* was left for this step on purpose (`deliver/pipeline.QUESTION_ACTIONS`, as
  the lead reports it — not yet in any branch at `fbd0aeaa`, so unverified here). Without it, *"don't
  ask me this"* has no button: a question you find pointless stays open until you answer it or the
  file's review stops asking — and the verdict ledger could not hold it anyway, because a question
  signal passes its own authority (`reason/authority.QUESTION_SIGNAL_PREDICATE`), not the decision's
  the verdict writer reads.
- **N12 · The receipt *"a human verdict has reached the loop"* reads the extension's ledger only**
  (`s16-F9`) — a founder who uses only the dashboard keeps it red whatever they press
  (`platform/receipts.py:1796-1799`).
- **N13 · `tests/feedback` has 30 database tests, not 27** (`s16-F11`) — measured in 8.1; they pass on
  Postgres and skip in CI, which is STEP-17's database job (M40.C4), not this step's.

Provisional ids `s16-F1`…`s16-F13` for `03`, each with its evidence above: F1 N1 · F2 N2 · F3 N3 · F4 N4 ·
F5 N5 · F6 N6 · F7 N10 · F8 N9 · F9 N12 · F10 N7 · F11 N13 · F12 N8 · F13 N11.

Owned here already, and where each lands: `03` F126 and F157 (the brief keeps what you corrected —
M46.C5); F152 (the verified close — M47.C1); F76 (M47.C3); F82 (S16-D9); `03` C16 (the wrong home — N7);
`STEP-18` B3 (M46.C2); B22–B24 (they leave this step — S16-D5); STEP-13's question card's *wrong* (N11 —
M46.C3, S16-D10).

### 8.4 · What changes in the design

Rohit, 12 Oct: the expert reasons from the data, the engine and its own expertise at once; your
corrections reach it **as data and as engine expertise — a corrected playbook prior — and never
silently**; and the result must hold on Haiku and Sonnet, Opus only when needed.

1. **One ledger for your verdict.** Both doors write `card_feedback_verdicts` through one writer, and the
   ledger admits the eleven reasons (`0240`). What you press on a card reaches every reader the
   extension's verdict reaches.
2. **A correction is your word on a file, and it stands as you wrote it** (S16-D1). `founder_corrections`
   (`0241`) keeps your words and their scope — this file; every file of this kind of work; the company,
   which is your own *preferences* line of the brief (STEP-07's `add`, accepted as written). A bare click
   stays a verdict on its own file and generalises nothing. Nothing here proposes a pattern from clicks
   (S16-D8), and nothing writes a learned brain.
3. **As data.** The dossier prints the file's corrections, each with its id (*WHAT YOU CORRECTED*, after
   *WHAT YOU TOLD US*); the fingerprint names them; and a correction is a trigger, `founder_corrected` —
   *you ask about it* given its door — so the next sweep reviews the file with your words in front of the
   expert. A verdict on the file's card brings it back too (S16-D2). **Learning reads a question card's
   *wrong* the same way** (S16-D10): it is a verdict on the file, bound to the question's own authority;
   it retires the question (`called_wrong`), and the file never asks it again in those words; with your
   words it is a correction of the file — *"saka.vc is no fund; stop asking"* is an answer by another
   name. Calibration never reads it: its rule, `founder_question`, is no pack rule.
4. **As engine expertise — the corrected playbook prior.** A correction for a kind of work prints in
   *WHAT A PROFESSIONAL KNOWS ABOUT THIS WORK*, beside the profession's prior, as yours; every file of that
   kind is reviewed with it (S16-D3). The shared corpus is never edited. And the prior meets your own
   numbers (M47): beside a stage's typical duration, your measured time for it with its n — *a prior* and
   *yours* told apart, normal only at n ≥ 5 (D37), observe-only (Atlas V.3). The behaviour brain is not
   involved: the expert reads numbers computed on the read, as STEP-10 built them.
5. **Never silently.** The prompt says what a correction is (`expert-review.v4`); the check holds a move
   made over a correction the review does not cite — the file asks ONE question, *"you said … on 12 Oct;
   does it still hold?"* — and a move repeating, in its words, a card you called wrong without citing
   your verdict. **This is what makes it model-agnostic**: a weaker model costs you a question, never an
   ignored correction. No new model site — your words are read by the expert already running
   (Sonnet-class, D7); no Haiku-class parser is needed, because the typed parts (reason, scope, file) come
   from buttons and the words are read whole; Opus nowhere.
6. **Replayed and audited.** The review before a correction and the one after are stored with their
   inputs (`0198`) and triggers (`0199`); both decisions replay with no model (STEP-12); `correction_delta`
   names what changed, and the weekly scorecard is its reader.
7. **The brief learns from your corrections of it.** Accepting a proposal with another kind keeps the
   drafter's (F126); the expert may propose correcting an accepted kind as a proposal that replaces the
   line, accepted in one act (F157) — and *"this is not an investor"* reaches the kind that way.
8. **A file decision that ends says how.** Its card is RESOLVED `verified`, naming the event that closed
   the ask its move answered, when that ask closed *answered*; otherwise cleared as today, the closing
   event in its detail. How each decision of a file ended — verified, only replied, taken by you, called
   wrong and why, lapsed, replaced — is read from what is already written (card ends, verdicts, ask
   closures): no new table. The executive commitment is left as it is (S16-D6).
9. **The week, measured** (`09` G6, D18): usefulness per lane, what was held back and why, coverage,
   verified outcomes and what each correction changed — and the per-layer debit of every *wrong because*
   finally has a reader. A receipt holds that a verified card names what closed it; the public acted
   rate counts what you did (F76).
10. **What does not change, and the two traps.** Calibration stays shadow (D13, S16-D5): no unit here
    mutes, nudges or moves an authority revision, and B22–B24 wait for a tenant that asks to arm. The
    `distinct_days` gate (*do not fix it before ADR-10*): no unit touches
    `feedback/units.unit_recommendation_learning`, `validate_learning`'s place before `govern` or a policy
    floor; no correction goes through L6's evidence route; and no expert commitment is marked `succeeded`
    (S16-D6), so no new graded ending reaches the one Adaptive unit that constant holds shut. A guard
    written first (M46.C1) fails on any of these, with the tripwire
    (`test_the_declared_violation_is_blocked_by_arithmetic.py`) in its verify. The open lane stays on
    demand (S16-D7).

### 8.5 · What will be built — tree block `yc2_w27_s16` (M46, M47), proposed

Written to `baseline/yc2w27-s16/tree_s16.yaml` for the lead to merge into `tree.yaml`.

**M46 — your correction changes the next judgment, and never silently** (§3.1, §3.2, §4): C1 the guard,
first · C2 one ledger — `0240`, the one writer, the dashboard's door · C3 your correction — `0241`, the
store, your door on a file, the card's *wrong* with your words, and a question card's *wrong* (a question
you call wrong is retired and never asked again in its words; the card offers it) · C4 the expert reasons from it — the
check's words, the prompt, the dossier, the fingerprint, the trigger, never silently, the delta · C5 the
brief learns — `0242`, the store, the expert's replacing proposal · C6 the morning brief's door and
M46's acceptance on Postgres (§6's own file).

**M47 — a file that ends says how; the week and the board measure it** (§3.3, §3.4, G6): C1 one way to
resolve a card, an answered ask resolves it, how each decision ended · C2 your numbers for a kind of work,
and what came of it in the dossier · C3 the scorecard, its route, the receipts, the acted rate · C4 the
golden set — your acts and a card's end in the case contract and the runner, F57's verified close, three
new cases (F59 a correction on one file, F60 one for a kind of work, F61 one click is never a pattern),
ONE re-record, the acceptance.

**40 units (23 in M46, 17 in M47), critical path 7** — three chains of seven: `0241` → the correction
store → the dossier → the fingerprint → the trigger → the re-record → the acceptance; `0240` → the one
writer → the dashboard's door → the card's *wrong* with your words → a question's *wrong* → the question
card offers it → M46's acceptance; and `0241` → the store → the dossier → the fingerprint → the delta → the
scorecard → its route. Migrations
`0240`–`0242` — ⛔ `0240` is not written: STEP-18's `0210` (`61d679ed`) already keeps every reason, and
`M46.C2.L-contract.V0.U01` is built by it (§3.1). Outside the block:
STEP-13's last units first (its *Answer* action edits `deliver/actions.py`), STEP-14's card and STEP-15's
brief (this step's own dependencies — M46.C6.U01 waits for `executive/morning.py`), STEP-17's feedback
test (M46.C2.U01 takes its eight markers off).

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| S16-D1 | Where does your correction live? | **its own record on the file** (`founder_corrections`), read by the expert's dossier — the road your answers took; one for a kind of work prints beside that kind's playbook; one for the company is your own preferences line of the brief. Not `user_model_proposals` (unwritten persona JSON); not L6's Organization brain (the expert reads no brain, and its review route is two acts for your own words) | the same |
| S16-D2 | Does a bare *wrong* (no words) bring its file back to the expert? | **yes, that file only** — one review, about 2¢ at Sonnet-class; the verdict and its reason are in front of the expert; nothing else learns from one click | the same |
| S16-D3 | A correction for a whole kind of work — every file of it re-thought now, or each as it next moves? | **now** — nearest deadline first, inside the $2 day and ten a pass; the rest carried, said | each as it next moves (how a playbook change rides today) |
| S16-D4 | The eleven reasons on a card — all eleven, or the four groups the card already carries, with your words? | **four groups and your words** — the words are what the expert reads; the reason only routes the per-layer debit | four groups |
| S16-D5 | Arm calibration (D13) now that it runs? | **no, and not in this step** — it scores the packs' rules (general's 5, Sales' 20 on your org; Admin's and the Founder Office's none) and never an expert card; your corrections reach the expert instead. B22–B24 leave STEP-16 and wait for a tenant that asks to arm | shadow (D13 A) |
| S16-D6 | Mark an expert commitment `succeeded` when the ask it answers is answered? | **not now** — the card resolves `verified` with its evidence (M47), which is what you see and what the scorecard counts; a `succeeded` commitment would put graded endings in front of the Adaptive unit that only the `distinct_days` constant holds shut — answer ADR-10 first | not built |
| S16-D7 | The open lane's weekly review (§3.5)? | **not now** — its report counts kinds across organisations, and with one tenant it counts one mailbox; the expert now reads each touch's words whole. On demand, as today; revisit with the second mailbox (`09` G8) | on demand |
| S16-D8 | Repeated verdicts on one kind of card — propose a kind-wide correction to you? | **not now** — the scorecard shows your verdicts by kind; proposing from clicks needs L6's floors on them, the evidence route beside the `distinct_days` gate | not built |
| S16-D9 | `03` F82 — a changed brief does not re-judge verdicts stored per item: re-judge any? | **none automatically** — a resolution claim names its brief since STEP-13 (F83), the expert reads each touch's words whole, and a screen verdict lapses in a day | as today |
| S16-D10 | A question card — may you call it *wrong*, and does learning read it? | **yes, and yes** — *"don't ask me this"* is the most useful thing you can say about a question: the verdict is kept on the file (the expert sees it, S16-D2), the question is retired and never asked again in its words, and your words, if any, are a correction of the file; calibration never reads it. A move that rested on that question stays held with no card, counted on the scorecard as *held — its question called wrong* | answer and snooze only, as STEP-13 built it |

ADR-10 (an Adaptive entry with an expiry) is not needed by this plan — nothing here writes a learned brain —
and stays yours.

### 8.7 · Risks

- **One more re-record** — the prompt (v4), two new dossier sections and three new cases: the board is
  restated in its five places, and in production every live file is reviewed once more after the deploy
  (about 2¢ a file, ten a pass).
- **A model that cites poorly asks you more questions.** Never silently turns an uncited correction into a
  question; the live pass (D50) says how often on Sonnet, and a Haiku pass would say the same for it.
- **The dashboard's verdicts reach readers that never saw one**: the adaptive lease's weekly proposals
  (three *bad timing* on two days make a seven-day lease on a compiled capability) and calibration's
  shadow precision. Measure the lease on the golden set before the deploy; calibration applies nothing.
- **A correction for a kind of work re-thinks every file of the kind** (S16-D3) — a burst, bounded by ten
  a pass and $2 a day, carried and said.
- **A correction stands until you withdraw it.** An old one keeps being cited — "outweighed", with a
  reason — and the dossier shows the newest few, the rest counted. Nothing expires on its own.
- **Verified closes will be rare at first.** An ask closes *answered* for six kinds of closing message
  (an approval granted or blocked, an intro made, a requested document sent …); most close *replied* —
  honest, and the scorecard says which. Whether F57's signed NDA closes *answered* is measured when its
  case is re-recorded.
- **Three steps edit the same files** — `deliver/actions.py` (STEP-13's *Answer*, STEP-14's card, three
  units here), `deliver/pipeline.py` (STEP-13's question card, then here), `reason/expert/dossier.py` and
  `verify.py` (STEP-13, then here). Build in order, after STEP-13's last units.
- **STEP-14 and STEP-15 are not planned yet.** M46.C6.U01 names `executive/morning.py` from STEP-15 §3.1;
  if STEP-15 builds elsewhere, the unit follows it.
- **STEP-17's statement census reads the extension route's statements** — M46.C2.U02 moves them to the one
  writer and restates that test in the same unit.
- **The question card's *wrong* is planned on the lead's word.** `deliver/pipeline.QUESTION_ACTIONS` is in
  no branch at `fbd0aeaa` (STEP-13's question card, M36.C2.L-interface.V3.U05, was not yet committed);
  M46.C3.U05–U07 follow whatever STEP-13 lands. And a question called wrong leaves its move held with no
  card — never silent, because the scorecard and the file say so, but a file can go quiet that way.

### 8.8 · Found while building (12 Oct, provisional ids)

- **s16-F14 · A write-only declaration names its writer by a file that only has to exist.**
  `platform/table_coverage.UNREAD_WRITES` gives each write-only table its writer, and
  `tests/platform/test_a_table_nothing_reads_is_declared.py` checks only that the named file exists — not
  that it writes the table. When M46.C2.L-data.V1.U02 moved `card_feedback_revisions`' INSERT from
  `api/intelligence_routes.py` to `deliver/verdicts.py`, the declaration kept naming the route and stayed
  green; it was corrected in the same commit by hand. A stale writer reads as a measurement. Not built
  here (a new guard, not this unit's): each declared writer ∈ `writers_of(table)`.
- **s16-F15 · The caller of `ask` does not yet know a question you called wrong.** Since
  M46.C3.L-data.V0.U05, `context/founder_questions.ask` returns the retired `CALLED_WRONG` question when a
  review asks words you called wrong. `reason/expert/asks.ask_the_founder` handles only `ANSWERED` that way;
  given the retired question it would expire the open question signal and file a new one bound to a retired
  question — a signal no card can pass (`QUESTION_SIGNAL_PREDICATE` needs the question open). Dormant: no
  question is retired `CALLED_WRONG` until M46.C3.L-integration.V4.U06 (the question card's *wrong*, in
  `deliver/actions`). `asks.py` is STEP-14's until it merges; the caller's half — treat it as
  `ANSWERED_ALREADY`, file no signal, count the file *held — its question called wrong* — rides with U06.
- **s16-F16 · Two steps name the same golden cases.** STEP-14's tree (`M43.C6.L-data.V1.U02`–`U07`) authors
  F59–F64 (the Boardy introductions); this block's `M47.C4.L-data.V1.U04`–`U06` author F59–F61 (a
  correction on one file, one for a kind of work, one click is never a pattern). Whichever merges second
  renumbers; these three are not written yet (they wait for `tests/replays/`).
- **s16-F17 · The prompt waits for the dossier.** `M46.C4.L-interface.V0.U02` (`expert-review.v4`, the
  checklist's words for a correction) is buildable now, but it moves every expert cassette key: the golden
  lane is red from it until the ONE re-record (`M47.C4.L-integration.V5.U07`), which waits on STEP-14's
  files and `tests/replays/` — and its words name dossier sections (`WHAT YOU CORRECTED`, `[corr:…]`) the
  dossier will not print until `M46.C4.L-logic.V2.U03`. Built with the dossier, just before the re-record.

**Found 16 Oct, building the units that waited on STEP-14** (provisional ids):

- **s16-F18 · The team lane resolved cards with nothing saying why.** `reason/team/emit` set
  `cards.state = 'resolved'` by two raw UPDATEs, with no event: a resolved card could not say what ended it.
  Both now go through the one writer, `platform/card_lifecycle.resolve_cards` (`situation_cleared`,
  `superseded`), which writes a `card.resolved` event per card; `context/file_outcomes` reads them as
  cleared and replaced. ✅ M47.C1.L-data.V0.U01 (`296cbb45`).
- **s16-F19 · A receipt word formatted in is a statement assembled at run time.** The verified-card
  receipt first built its SQL with `f"… '{RESOLVED}' …"` from an import inside its builder: the statement
  census could not read it whole and the run-time ratchet moved 272 → 273. Caught by the unit's own pin
  run, before its commit; the words are inlined as literals, and the test holds them equal to the
  lifecycle's. ✅ M47.C3.L-integration.V2.U03 (`d6659787`).
- **s16-F20 · Your numbers per dossier would read every file per file.** `kind_numbers.numbers_for_kind`
  with no files reads `files_for` — the tenant's whole file list — and the sweep reads every file's
  dossier: O(n²). The sweep now measures each kind ONCE a pass over the files it already read (all are read
  before any is reviewed, so every dossier of a kind reads the same numbers), and the endings of a kind's
  files are one read (`ended_for_files`). ✅ M47.C2.L-logic.V4.U02 (`846718e2`).
- **s16-F21 · A commit message named one declaration too many.** `e507b68a` (the scorecard) says
  `scorecard.compose` and `scorecard_for` were declared unreached until the route; only `scorecard_for`
  was — `compose` is called by it. The code and its guard were right; recorded here, as the log is
  append-only.
- **s16-F22 · An owner check in `card_action` read the old scopes rule.** U04's owner-only test for a kind
  or company correction wrote `ctx.scopes is None`, which `tests/test_open_loops.py` keeps out of the card
  routes (seeing and acting use one rule). Found by the group guard; it reads `ctx.is_org_admin` and the
  admin seat now. ✅ `cdf58447`.

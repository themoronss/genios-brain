# 00 · Start here — the steps, their order, their owners

**Written for:** everyone. **Status as of:** 2026-10-05. Read `04` and `05` first if you have not
— this page assumes you know *why*.

---

## The shape

```
YC-II W27 · GeniOS as a 30-year chief of staff
│
├── Phase 0 · Ground truth            STEP-00  STEP-01
├── Phase 1 · Remember everything     STEP-02  STEP-03  STEP-04  STEP-05  STEP-06
├── Phase 2 · The expert's desk       STEP-07  STEP-08  STEP-09  STEP-10
├── Phase 3 · Expertise               STEP-11            (authoring starts in parallel with Phase 1)
├── Phase 4 · The expert thinks       STEP-12  STEP-13
├── Phase 5 · What you see            STEP-14  STEP-15
├── Phase 6 · Learning from you       STEP-16
└── Across all phases                 STEP-17  STEP-18
```

**Order is data flow, then dependency.** Nothing above can reason better than what the layer
below remembers. The one exception is `STEP-02`: it is the cheapest visible win — cards stop
flip-flopping and most of the model spend disappears — and it depends on nothing, so it goes first.

---

## The steps

| Step | Status | Owner | What it does | The number that must move |
|---|---|---|---|---|
| [`STEP-00`](STEP-00-PENDING-owner-rohit-and-harsh-one-branch.md) | **PENDING** | Rohit (push) · Harsh (deploy) | one branch, one deployed baseline — ✅ merged, suite green, baseline kept (5 Oct) | `harsh/mvp` vs `speedrun008`: 13 / 28 → 0 / N ✅ · pushed ⏳ · deployed ⏳ |
| [`STEP-01`](STEP-01-NEXT-the-golden-set.md) | **NEXT** | Claude · Rohit labels | your mailbox becomes the exam: ~50 must-detect / must-abstain cases, a replay scorer | a measured before-score |
| [`STEP-02`](STEP-02-TO-BUILD-the-change-gate.md) | TO BUILD | Claude | no new evidence → no new decision, zero model calls | `l4_llm_decision` ~870/day → < 50; cards stop flipping |
| [`STEP-03`](STEP-03-TO-BUILD-the-gate-keeps-everything.md) | TO BUILD | Claude | the gate sets attention, never deletes | mails with content deleted: 258 → 0 |
| [`STEP-04`](STEP-04-TO-BUILD-who-is-us.md) | TO BUILD | Claude · Rohit (D6) | one answer to "who is us", used everywhere | cards with you as the subject: ≥ 3 → 0 |
| [`STEP-05`](STEP-05-TO-BUILD-every-item-enters-memory.md) | TO BUILD | Claude | every kept mail, meeting and screen item enters the graph | in memory: ~27/395 mails, 2/34 meetings → ≥ 95% |
| [`STEP-06`](STEP-06-TO-BUILD-nothing-lost-silently.md) | TO BUILD | Claude | every item and every situation has a visible end state | items with no recorded end state → 0 |
| [`STEP-07`](STEP-07-TO-BUILD-the-company-brief.md) | TO BUILD | Claude · Rohit confirms | the company brief — goals, work in motion, people — read by every model call | brief exists, versioned, in 100% of prompts |
| [`STEP-08`](STEP-08-PENDING-owner-harsh-the-resync.md) | **PENDING** | Harsh | re-read the mailbox, 180 days, after 03–07 are live | the deleted mail is back with content |
| [`STEP-09`](STEP-09-TO-BUILD-workstreams.md) | TO BUILD | Claude | a file per piece of work in motion — investor, application, intro, hire, filing | Boardy intros tracked per contact: 3/7 → 7/7 |
| [`STEP-10`](STEP-10-TO-BUILD-history-patterns-analytics.md) | TO BUILD | Claude | the expert's numbers — timelines, reply times, cadence, waves, bounces, coverage | every number on a card traceable to a calculator |
| [`STEP-11`](STEP-11-TO-BUILD-founder-playbooks.md) | TO BUILD | Claude drafts · Rohit reviews (D2, D3) | what a professional knows about raising, programs, intros, compliance, hiring | 6 playbooks accepted |
| [`STEP-12`](STEP-12-TO-BUILD-the-expert-pass.md) | TO BUILD | Claude · Rohit (D1, D7) | one strong-model judgment per changed file: frame, rivals, scenarios, best move, draft | golden must-detect ≥ 90% |
| [`STEP-13`](STEP-13-TO-BUILD-check-every-claim.md) | TO BUILD | Claude | every sentence sourced, every number calculated, the lane chosen, unknowns asked | forbidden outputs on the golden set → 0 |
| [`STEP-14`](STEP-14-TO-BUILD-the-card.md) | TO BUILD | Claude · Rohit (D8) | one file, one living card, in the gold shape | duplicate cards per subject → 0 |
| [`STEP-15`](STEP-15-TO-BUILD-the-morning-brief.md) | TO BUILD | Claude · Rohit (D9) | 08:00 — what changed, what is stuck, what I would do, drafts | one brief a day, read in under 3 minutes |
| [`STEP-16`](STEP-16-TO-BUILD-learning-from-you.md) | TO BUILD | Claude | your feedback and real outcomes change the next judgment | a correction changes the next decision, replayably |
| [`STEP-17`](STEP-17-TO-BUILD-real-tests.md) | TO BUILD | Claude · Harsh (CI) | Postgres in CI, the golden set in CI, every SQL statement explained | pg-gated test files that never run: 150 → 0 |
| [`STEP-18`](STEP-18-TO-BUILD-known-bugs.md) | TO BUILD | Claude | the live bugs already found, each with its seam | each bug's production probe goes green |

---

## How we work through it

1. **One step at a time**, in the order above, unless a step says it can run in parallel.
2. Before a step starts: its file is re-read against the code (a line number can move), and its
   *"what is true"* section is re-measured. **If the measurement disagrees with the file, the
   file is corrected first.**
3. A step is **DONE** only when its number moved on production and its `verify` command exits 0
   with no skips. The file is then renamed `-DONE-` and its title updated in the same commit.
4. Anything noticed on the way that is not this step becomes a line in `03-FINDINGS.md` §E — never
   a silent fix.
5. Claim before editing, release after (`trace-claim.sh`). One writer per file.

## Where this meets the other work

| | |
|---|---|
| `../YCW27/` | the receipts-and-audit programme. Its open items (`19-PENDING-who-owns-what.md`) still stand; none of them blocks this folder, and `STEP-18` absorbs the ones this plan touches |
| `origin/harsh/mvp` | Harsh's production fixes of 2–4 Oct. `01-CROSSCHECK.md` §6 lists what they already fixed, so nothing here re-fixes it |
| The Design Atlas v2 | `01-CROSSCHECK.md` §5 checks every claim this plan rests on, before any unit was written |

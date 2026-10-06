# YC-II W27 — GeniOS as a 30-year chief of staff

**Opened:** 2026-10-05. **Branch at writing:** `speedrun008` @ `2dc61dac`, which is **28 commits
ahead of and 13 behind** `origin/harsh/mvp`, the branch production runs. Merged the same day:
0 behind since `568a245d` (`STEP-00`).
**Sits beside** `../YCW27/` — that programme built the six layers and their receipts; this one
makes them **think about your company the way an expert would**. Nothing in `../YCW27/` is
superseded.

---

## Why this folder exists

On 2026-10-05 you said three things:

1. *A company does not run on formulas and rules. It runs on patterns and analytics.* Use the
   model so GeniOS reasons like a full-time, 30-year expert — **context reasoning, from
   patterns, history, analytics and scenarios.**
2. *Read the data yourself.* The Startup India update never reached you; emails never reached
   you; Boardy introduced you to people and those introductions never completed.
3. *Plan first, in detail — what is wrong, what is expected, how it will work — then we build it
   one step at a time.*

This folder is that plan. Every claim in it is either measured on production (read-only, metadata
only) or read in the code, and says which.

## The answer in five lines

1. **GeniOS forgets before it thinks.** Of ~395 mails, 258 were deleted at the first gate and 69
   more were called junk by a filter that knows nothing about you. **27 reached reasoning.**
   Meetings vanish when their time passes. Screen follow-ups are built and hidden.
2. **The model is used — but never as the expert.** It filters one email at a time, reads each one
   without knowing what work it belongs to (code then squeezes the result into 16 boxes), and
   re-decides the same ~30 situations every 15 minutes (70% of ~2,000 calls a day). It is never
   given the whole file and asked what an expert would ask.
3. **The fix is an expert loop.** Remember everything. Keep a file for every piece of work in
   motion. Compute the history, patterns and numbers. Let one strong model think about a file
   **only when something in it changed** — frame, rival explanations, scenarios, the best move,
   the draft. Check every sentence. Show you only what needs you.
4. **The Design Atlas already designed this** (one bounded judgment pass, Plane R's patterns,
   history, analytics and scenarios, the change gate, five lanes) — and production never built
   it. Production runs the one thing the Atlas forbids instead.
5. **Nineteen steps**, each with a number on production that must move before it counts as done.

## Read in this order

| # | File | What it gives you | For |
|---|---|---|---|
| 1 | [`04-NOW-VS-SHOULD-VS-EXPECTED.md`](04-NOW-VS-SHOULD-VS-EXPECTED.md) | **What you see now, what you should see, what you will see** — case by case: Startup India, Boardy, investors, programs, meetings, screen, hiring, bounces | Rohit |
| 2 | [`05-HOW-THE-EXPERT-THINKS.md`](05-HOW-THE-EXPERT-THINKS.md) | **How it will work** — patterns, history, analytics, scenarios; who does what; four worked examples from your mailbox | Rohit, then everyone |
| 3 | [`06-DECISIONS.md`](06-DECISIONS.md) | the thirteen decisions only you can make, each with a recommendation and a default | Rohit |
| 4 | [`00-START-HERE.md`](00-START-HERE.md) | the step table — status, owner, order, what each step moves | everyone |
| 4a | [`07-WHAT-IS-DONE.md`](07-WHAT-IS-DONE.md) | **what is finished, with its proof, and what is still owed** — the push, each finished step, Harsh's list after the deploy | everyone |
| 4b | [`08-FOR-HARSH-deploy-and-after.md`](08-FOR-HARSH-deploy-and-after.md) | **the deploy and what to run after** — what changes at runtime, the re-queue, the toolkit pin, the probes, what not to do | Harsh |
| 5 | [`01-CROSSCHECK.md`](01-CROSSCHECK.md) | what is actually true, measured, before planning — production, code, the Atlas, Harsh's branch | Harsh, coding agent |
| 6 | [`02-PLAN.md`](02-PLAN.md) | the plan: sections → functions → components → units, each with expected · true · how · why · outcome · verify | Harsh, coding agent |
| 7 | [`03-FINDINGS.md`](03-FINDINGS.md) | defects, false alarms, already built, genuinely missing, open questions, numbers with sources | everyone |
| 8 | `STEP-nn-*.md` | one per step — what, why, how, what will happen, expected, verify, depends on, owner | whoever builds it |
| 9 | `../../tree.yaml`, block `yc2_w27` | the block as addressable units — proposed as 43, ✅ built as 53 (51 green, 1 retired, 1 blocked on Harsh), each with one artifact and one verify command; `00-START-HERE.md` summarises it | whoever builds it |
| 10 | `baseline/` | `production_state.sql` — every production statement behind the baseline, read-only — and the dated outputs | Harsh, whoever re-measures |

## Conventions (the same as `../YCW27/`)

- A step file is named `STEP-nn-<STATUS>-<slug>.md` and its first line carries the same status.
  Statuses: `NEXT`, `TO BUILD`, `PENDING` (title names the owner), `DONE`, `WITHDRAWN`, `RETIRED`.
- A step is **done when its number moved on production**, not when its code merged. *A skip is not
  a pass.*
- **The push is batched** (`06` D10). A step built and green locally stays `PENDING` — owner Rohit
  (push) and Harsh (deploy) — until the batch is deployed and its production number moves.
- Bottom-up, one unit at a time; a parent is never started before its children are green.
- `[CODE]` = read in the repository · `[PROD]` = measured on production · `[ATLAS]` = Design Atlas
  v2 or the Secret War audit · `[MODELLED]` = an estimate or an illustration, labelled as such.

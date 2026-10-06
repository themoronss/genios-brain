# 00 · Start here — the steps, their order, their owners

**Written for:** everyone. **Status as of:** 2026-10-06. Read `04` and `05` first if you have not
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
| [`STEP-00`](STEP-00-PENDING-owner-harsh-one-branch.md) | **PENDING** | Harsh (deploy) — Rohit's push ✅ 6 Oct | one branch, one measured baseline — ✅ merged; both suites run, every failure attributed; production baseline committed with its SQL (5 Oct) | `harsh/mvp` vs `speedrun008`: 13 / 28 → 0 / N ✅ · pushed ✅ `77aba10e` · deployed ⏳ |
| [`STEP-01`](STEP-01-PENDING-owner-harsh-the-golden-set.md) | **PENDING** | Harsh (deploy) — Rohit's push ✅ 6 Oct; labels optional | your mailbox becomes the exam — ✅ 40 founder cases and the Atlas replays 01–07 driven through the real chain on Postgres; the before-score committed (6 Oct) | a measured before-score ✅ must-detect 4/30 · must-abstain 5/10 · forbidden outputs 4 · Atlas 0/80 · pushed ✅ `77aba10e` · `golden-pg` on GitHub: `07` §7 |
| [`STEP-02`](STEP-02-PENDING-owner-rohit-and-harsh-the-change-gate.md) | **PENDING** | Rohit (push, batched) · Harsh (deploy, migration `0191`) | no new evidence → no new decision, zero model calls — ✅ built, QA green (6 Oct): on all 40 golden cases an unchanged sweep makes 0 model calls | `l4_llm_decision` ~870/day → < 50; cards stop flipping |
| [`STEP-03`](STEP-03-PENDING-owner-rohit-and-harsh-the-gate-keeps-everything.md) | **PENDING** | Rohit (push, batched) · Harsh (deploy, migration `0192`) | the gate sets attention, never deletes — ✅ built, QA green (6 Oct): on the golden set 0 of 86 mails dropped, the 33 it used to delete archived with their rule and body, every case marked as before | mails with content deleted: 258 → 0 ⏳ after the deploy |
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
   **The push is batched** (`06` D10): a step finished and green locally is renamed
   `-PENDING-owner-rohit-and-harsh-` — push, deploy, then its production number — and, once
   pushed, `-PENDING-owner-harsh-`, as `STEP-00` and `STEP-01` are now; it becomes `-DONE-` only
   after that. Code cites a step by its number and folder, never by its file name, so a rename
   touches no code.
4. Anything noticed on the way that is not this step becomes a line in `03-FINDINGS.md` §E — never
   a silent fix.
5. Claim before editing, release after (`trace-claim.sh`). One writer per file.

## The next block — tree `yc2_w27`, in Rohit's order (2026-10-05)

*"Database ka part, B1, B17, B18, B19, aur phir step 01 golden set — perfectly align karo."* Every
item was root-caused against the code on scratch databases before it became a unit. The block is in
`tree.yaml` as `yc2_w27` — proposed with 43 units, each with one artifact and one verify command.

✅ **Built on Rohit's go of 2026-10-05** (*"go start karo, best tareeke se karke complete karo"*):
**53 units — 51 green, 1 retired, 1 blocked.** Where contact with the code showed a gap, the build
drew a new unit rather than widening an old one; each is in `tree.yaml`.

| # | Milestone | What it ships | Units proposed | Built |
|---|---|---|---|---|
| 1 | `M16` the database suite is green | 50 failed → 0. 27 are one live bug (B2, the edge vocabulary). The other 23 are test-side: a script, three expiring test clocks, six outgrown fixtures, two text guards. No engine change outside B2 | 16 | ✅ 18 of 18 — 16,736 passed, 0 failed (`baseline/m16-green/`) |
| 2 | `M17` nothing captured is lost silently | B17 — the funnel writes its zeros, in every lane. B18 — a failed extraction is read again; first, a fingerprint claimed by an event that is gone stops blocking its re-landed copy (that also fixes B20). B19 — Gmail attachments are fetched; Harsh records one live response shape first | 10 | ✅ 10 green · 1 retired · ⛔ 1 blocked: `M17.C3.L-integration.V2.U04`, pinning the Composio toolkits, needs the SDK the production image runs — Harsh |
| 3 | `M18` calibration runs, and only proposes | B1 — the shadow switch lands before the one-line fix, because the fix alone arms unattended muting (`06` D13) | 5 | ✅ 5 of 5 — it completes on Postgres and mutes nothing until a tenant is armed |
| 4 | `M19` the golden set drives the engine | `STEP-01`, rewritten from its claim-by-claim check: `finalize_l1`, one clock, recorded model answers, a witness for every must-abstain case | 12 | ✅ 18 of 18 — the before-score, `03` §F.1 |

Every milestone after `M16` depends on it, because its verify runs on the scratch database.
`M17`, `M18` and `M19` do not depend on each other; Rohit's order sequences them. The critical path
is 8 units (`M16.C1` → `M16.C6` → `M18`).

**QA, 2026-10-06 at `83dd87f3`** (`baseline/yc2w27-qa/qa_record.txt`) — every unit's own verify
on an empty scratch database, the whole suite with and without it, the `golden-pg` lane, the board
and the hermetic job: **55 pass / 1 fail / 0 skip**. The one fail is the blocked unit above
(`M17.C3.L-integration.V2.U04`, *no tests ran*); every other check exits 0.

Nothing here is pushed. Rohit pushes the batch (`06` D10). ✅ **Pushed 2026-10-06** (`77aba10e`) — what
is done and what is owed, step by step: `07-WHAT-IS-DONE.md`; Harsh's notes, with every command:
`08-FOR-HARSH-deploy-and-after.md`. **After the deploy** (Harsh):

1. re-queue the attachments the `file_name` refusal dead-lettered —
   `scripts/requeue_refused_attachments.py --org <org> --database-url … --apply`, run only once the
   connector fix is live (before it, every row is refused five more times);
2. read the first `refetch_last_error` that comes back — the connector now names the shape of a
   response it cannot read (`STEP-18` B19);
3. pin the Composio toolkits — `M17.C3.L-integration.V2.U04`.

## Where this meets the other work

| | |
|---|---|
| `../YCW27/` | the receipts-and-audit programme. Its open items (`19-PENDING-who-owns-what.md`) still stand; none of them blocks this folder, and `STEP-18` absorbs the ones this plan touches |
| `origin/harsh/mvp` | Harsh's production fixes of 2–4 Oct. `01-CROSSCHECK.md` §6 lists what they already fixed, so nothing here re-fixes it |
| The Design Atlas v2 | `01-CROSSCHECK.md` §5 checks every claim this plan rests on, before any unit was written |

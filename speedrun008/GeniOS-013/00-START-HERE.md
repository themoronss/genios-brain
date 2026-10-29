# GeniOS-013 · From facts about mail to an understanding of the work

**Written for:** Rohit (everything in this file, then 01, 02 and 04) and Harsh with the coding agents Harsh assigns (everything).
**Date:** 28 Oct 2026.
**Measured on:** a local copy of the design partner's org, taken from production in one read-only transaction at 2026-10-28 12:45 UTC. Code read at `harsh/mvp` `7d2c3615`; every `file:line` is from that head.
**Status:** a plan. Nothing in it is built. Rohit opens each step.
**No names, by design.** This repo is public. The ideal cards are referred to by their ids in the private ideal file (`p1`, `i1` … `l1`) and a short description.

---

## ⭐ Since 29 Oct: the plan is in five parts. Start here

Read [09 · What we are building, why and how](09-WHAT-WHY-HOW.md) first. It sets out:
- what GeniOS is (from the launch film);
- the test it must pass first (`i1`, the film's own example);
- the five parts and the four loops;
- why it hasn't worked so far;
- the ten rules every step follows.

Then read [10 · The acceptance set](10-ACCEPTANCE.md): the cards, goals and replay every part is measured against.

| Part | Folder |
|---|---|
| P1 · Orchestrator: what runs when (the four loops, the triggers, the clock, the budget) | [P1-ORCHESTRATOR](P1-ORCHESTRATOR/) |
| P2 · Notebook (Context Graph, L3): the evidence and the conclusions, checked before they are kept | [P2-NOTEBOOK](P2-NOTEBOOK/) |
| P3 · Plane D: domain expertise, what a professional knows | [P3-PLANE-D](P3-PLANE-D/) |
| P4 · Plane R: reasoning, how a professional thinks | [P4-PLANE-R](P4-PLANE-R/) |
| P5 · Cards: the intelligence a person sees, and what they do with it | [P5-CARDS](P5-CARDS/) |

Every part folder holds the same five files:
- `01-WHATS-EXACTLY-THERE`;
- `02-WHATS-FAILING-AND-WHY`;
- `03-EXPECTED-VS-HAPPENING`;
- `04-WHAT-NEEDS-TO-BE-DONE-NOW`;
- `05-HOW-AT-PRODUCTION-LEVEL`.

The four-question files below (01–08) are the 28 Oct analysis the parts build on.

---

## How this folder is organised: four questions, in order

| # | The question | File |
|---|---|---|
| 1 | **What is happening?** The detailed reasoning: where it breaks, and why | [01-WHAT-IS-HAPPENING](01-WHAT-IS-HAPPENING.md) |
| 2 | **What should happen?** How GeniOS should work instead | [02-WHAT-SHOULD-HAPPEN](02-WHAT-SHOULD-HAPPEN.md) |
| 3 | **How does it get fixed?** Eight steps: what, why and how | [03-HOW-IT-GETS-FIXED](03-HOW-IT-GETS-FIXED.md) |
| 4 | **How does it run smoothly?** Rollout, measurement, cost, storage, new customers, tools, agents | [04-HOW-IT-RUNS-SMOOTHLY](04-HOW-IT-RUNS-SMOOTHLY.md) |

Supporting files:

| File | Holds |
|---|---|
| [05-THE-WORK-OBJECT](05-THE-WORK-OBJECT.md) | The specification of the "piece of work": fields, tables, loops, links, claims, checks, a worked example |
| [06-MEASUREMENTS](06-MEASUREMENTS.md) | Every number used here, with the SQL to re-run it on production |
| [07-DECISIONS](07-DECISIONS.md) | Six decisions for Rohit, each with a default |
| [08-LOG](08-LOG.md) | An append-only record of what was built and measured |

---

## The four answers on one page

### 1 · What is happening

- **The brain (L2) thinks well.** On the accelerator application (`i1`) it reached almost the same reading as the ideal card: a stalled reconsideration, traction numbers that rose between updates, and one short follow-up to send.
- **It is handed the wrong bundle.** Mail is filed by sender, not by piece of work:
  - one application is split into 2 files;
  - one intro platform is a single file of 500 mails and 61 people, too big to judge at all.
- **It is woken at the wrong time.** Only new mail wakes it (138 of 138 runs), yet 13 of the 20 ideal cards are about something that did *not* happen.
- **It has no company context.** No brief (138 of 138 dossiers), no expert playbook (38 of 38 current dossiers), no approved goals.
- **Good answers are thrown out.** A word-by-word checker held 66 of 86 results, and the founder saw "We held…".
- **Nothing it concludes is saved.** Admission runs in "shadow", and 0 of the graph's 16,792 facts came from the brain. So every judgment:
  - re-reads ~70,000 characters;
  - is capped at ~12 a day;
  - is forgotten afterwards.

  The cards come mostly from old rules: 71 of 103.

**The root:** the architecture's L3 has two halves. The Evidence Graph (what the sources said) is built. The Intelligence Graph (what GeniOS concluded) is not.

### 2 · What should happen

**GeniOS keeps an up-to-date understanding of every piece of work, and only thinks about what changed or what is overdue.** Each piece of work has a small saved page:
- what it is, and which goal it serves;
- where it stands, and whose move it is;
- what is owed, and what we have claimed;
- what should happen next, and by when;
- the latest conclusion.

The flow then works like this:
1. New items from any tool attach to the page.
2. The brain reads the page plus only what is new, and proposes an updated page.
3. Code checks the update and saves it.
4. A clock notices missed dates.
5. Cards are views of pages.

### 3 · How it gets fixed

| Step | What | Done when |
|---|---|---|
| 0 | Make "good" measurable: card score, work score, stage of loss, from one command | baseline recorded (today 8/20 cards, 28/220 fields) |
| 1 | The piece-of-work contract and tables, built beside today's situations | the 17 in-window ideal items fit |
| 2 | The brain writes the page; code checks each change; loops close only with evidence | ≥ 15 of 17 pages right |
| 3 | Read the page and only what is new; re-think only on a real change | dossier ≤ 12k characters; 0 wasted re-reads |
| 4 | The clock: expected-by dates wake the brain; budget goes to important work first | ≥ 10 of 11 silence items raised |
| 5 | Cold start: who we are; kinds and goals usable while unconfirmed; first pass on day one | ≥ 8 of 10 ideal goals proposed |
| 6 | One card per piece of work; old rule cards off for this org; no "held" cards | ≥ 15 of 17 ideal cards right; 0 duplicates |
| 7 | Inputs, in parallel: keep mail from people in active work, bounces join their work, retry attachments, 365 days at onboarding | the archived and bounced items reach their work |

### 4 · How it runs smoothly

- **Releases:** every step is gated on the local copy, then switched on for one tenant with a row, measured the next day, and switched off the same way.
- **First fixes:**
  - CI must be green (today `golden-pg` and `database` fail);
  - `/health` must name the running build (today it says `dev`).
- **Health:** `daily_health` gains numbers for the pieces of work. Pages past their date, held changes, wasted re-reads, duplicates and budget skips are all visible within a day.
- **Cost:** reading in proportion to what changed, finding silence for free, the old flow's model calls switched off, and onboarding as a one-time budget.
- **Storage:** the database is already over its ceiling (about 570 MB against 472 MB on 27 Oct). Pages add about 1 MB; retention for the heavy tables is proposed.
- **Growth:** new tools add members, not redesigns. Agents work from the page and write their results back to it.

---

## Decisions for Rohit (full text in [07](07-DECISIONS.md))

| # | Decision | Default |
|---|---|---|
| D1 | L2 may use **unconfirmed** kinds and goals for reasoning and priority, labelled. Approval stays with the founder | yes |
| D2 | A one-time onboarding budget; the daily L2 budget is re-set from the measured cost after Step 3 | ~$20 one-time; $2/day until Step 3 |
| D3 | More goal proposals during onboarding | 10 in week one, then 3 a week |
| D4 | Capture 365 days at onboarding | 365 |
| D5 | For this org, after Step 6, only the work path delivers cards | yes |
| D6 | The stored-event fetcher, which reads only our own database, is on by default | yes (Harsh) |

## A correction to what was said earlier

GeniOS does not "read only half the mailbox" or "park whole mails for an attachment". The 547 parked rows are attachments, and all 547 of their mails were read. The real numbers: of 1,829 mails, 1,193 (65%) were emitted and 636 (35%) were archived.

The claim-check counts were also restated: it held 57 of 63 results with the older check and 9 of 23 with the newer one.

## How this relates to the other folders

- **GeniOS-008 (the architecture)** is unchanged. This plan completes its L3 Intelligence Graph and the L2 → L3 write-back, which is step 11 of the Orchestrator.
- **GeniOS-012 (loss points D1–D32).** Its loss points are still true as symptoms.
  - Superseded by the piece of work: the L3 filing items. These are one counterparty with several live situations, waves, any reply closing every ask, a bounce erasing the waiting card, and conflicting numbers overwriting each other.
  - Continued in Step 7: its L1 items.
  - Reused here: H-01…H-28 and goals S28–S31.
- **Beside, not instead.** The old lanes stop delivering for this org only after Step 6 passes, and only by an activation row.

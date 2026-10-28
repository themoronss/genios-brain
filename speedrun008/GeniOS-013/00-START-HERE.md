# GeniOS-013 · Finish L3's second half: from facts about mail to an understanding of the work

**Written for:** Rohit (§1 to §4) and Harsh with the coding agents he assigns (everything).
**Date:** 28 Oct 2026.
**Measured on:** a local copy of the design partner's org. It was taken from production in one read-only transaction at 2026-10-28 12:45 UTC. The code was read at `harsh/mvp` `7d2c3615`, and every `file:line` in this folder is from that head.
**Status:** this is a plan. Nothing in it is built yet. Rohit opens each step.

**No names, by design.** This repo is public. The ideal cards are referred to by their ids in the private ideal file (`p1`, `i1` … `l1`). No person, company or mail text appears here.

---

## §1 · The answer in one page

**The question.** A Claude session read the founder's mailbox and produced 20 good cards and 10 goals. GeniOS read the same mailbox and produced:
- 103 live cards, few of them useful;
- 7 goals, none of them live.

Why?

**What we measured** (details and SQL in [01](01-WHAT-IS-TRUE.md)):

1. **The model is not the problem.** When L2 judges a file, it usually reads it the way Claude did. Take `i1`, an accelerator that rejected the application and invited updates. L2:
   - named the stalled reconsideration;
   - noticed that the founder's traction claims rose between updates;
   - proposed one concise follow-up, with a draft.

   Then the claim check blocked it over formatting: a date written another way, a first name, "UTC". What the founder saw was "We held the one we found…".
2. **The context graph is rich, but it holds no conclusions.** It has 16,792 facts and 2,352 relations, all timestamped. Every fact is one of two kinds:
   - what a source said (6,148);
   - what code computed (10,644).

   **0 facts come from L2's reasoning.**
3. **L2's conclusions have no write path.**
   - The admission code says so in a comment: "⛔ SHADOW: nothing here touches `context_situations`" (`context/l2_admission.py:25`).
   - Merging two pieces of work, or linking them, has no code that would apply it.
   - L2 has written 30 interpretations, and nothing in reasoning or delivery reads them.
4. **So GeniOS never keeps what it understood.** Every judgment:
   - starts again from about 70,000 characters of raw evidence;
   - is capped by a ~$2/day budget, which works out to about 12 judgments a day;
   - wakes only on new mail (all 138 runs);
   - is used once, for a card, and then forgotten.
5. **The rules still decide what the founder sees.** Cards come from situations made by rules. Those rules key work by sender: "a file is one counterparty's correlations". 71 of the 103 live cards come from them.

**The trunk root cause.** Design Atlas v2 splits L3 into two graphs:
- an **Evidence Graph**: what the sources said;
- an **Intelligence Graph**: what GeniOS concluded. In the Atlas's words, *"L3 only remembers what L2 concluded."*

In production, only the Evidence Graph exists. We measured nine symptoms: wrong unit of work, goals stuck, silence invisible, loops never closed, huge dossiers, held cards, a tiny budget, three card engines, and no measurement. All nine follow from that missing half ([01 §10](01-WHAT-IS-TRUE.md)).

**The fix in one line.** Build the core of the Intelligence Graph: a stored **piece of work**, which is the *situation* as Atlas v2 means it.
- L2 writes it.
- L3 checks and keeps it.
- A clock watches it.
- Cards are made from it.

There is no new layer, no memory product and no third-party service, and it lives in the same database ([03](03-THE-WORK-OBJECT.md)).

---

## §2 · The steps

Each step is built and gated on the local copy first, then switched on for this org in production. Details, units and commands are in [02](02-PLAN.md).

| Step | What | Size | Done when |
|---|---|---|---|
| **0** | Make "good" measurable: a card score, a work score and the stage where each item was lost, from one command | S | baseline recorded (today: cards **8/20** found, fields **28/220**) |
| **1** | The piece-of-work contract and its tables, built beside today's situations | M | 17 hand-filled works validate, and every in-window ideal card's facts fit the contract |
| **2** | L2's write path: admission applies the change instead of logging it; loops close only with evidence; works can merge, gain members and split | L | ≥ 15 of 17 works are right (members, status, whose move, loops) |
| **3** | L2 reads the work first, then only what is new, and re-judges only on a real change | M | median dossier ≤ 12k characters; 0 re-judgments without new input |
| **4** | The clock: each work has an expected-by date, silence wakes L2, and the budget goes to important work first | M | ≥ 10 of the 11 in-window silence items raised |
| **5** | Cold start: who we are; kinds and goals usable while unconfirmed; a one-time onboarding pass | M | ≥ 8 of 10 ideal goals proposed; a playbook in ≥ 90% of dossiers |
| **6** | One card path: cards come from works, the old lanes stop delivering for this org, and no "held" card is ever shown | M | ≥ 15 of 17 ideal cards carry the right recommendation; 0 duplicates |
| **7** | Input fixes, in parallel: archive rescue, bounce → work, attachment text, the capture window | S–M | the archived ideal item reaches its work; bounces show on their works |

*In-window* means the 17 ideal cards whose mail falls inside the 180-day capture window. `i6`, `s1` and `s2` are older and depend on decision D4.

---

## §3 · What Rohit decides

Full text, defaults and consequences are in [04](04-DECISIONS.md).

| # | Decision | Default |
|---|---|---|
| D1 | L2 may use **unconfirmed** kinds of work and goals for reasoning and priority, clearly labelled. Approving them stays with the founder | yes |
| D2 | A one-time onboarding budget for the first pass over history. The daily L2 budget is re-set from the measured cost after Step 3 | ~$20 one-time; $2/day until Step 3 |
| D3 | The weekly cap on goal proposals is lifted during onboarding | 10 in the first week, then 3 a week |
| D4 | The capture window at onboarding goes from 180 to 365 days | 365 |
| D5 | For this org, once Step 6 passes, only the work path delivers cards | yes |
| D6 | The stored-event fetcher, which reads only our own database, is on by default and separate from the Gmail fetchers' switch | yes (Harsh) |

---

## §4 · A correction to what was said earlier

Earlier in this investigation Rohit was told two things: that GeniOS "reads only half the mailbox", and that it "parks whole mails because of an attachment". **Both were wrong.**

- The 547 "parked" rows are **attachment stubs**, and all 547 of their parent mails were emitted.
- The real numbers: of 1,829 mails in the window, **1,193 (65%) were emitted** and **636 (35%) were archived**.
- 547 attachments were not read:
  - 421 unsupported, almost all calendar invites (the calendar itself is captured separately);
  - 125 failed downloads;
  - 1 had no OCR engine available.

Step 7 is sized to these corrected numbers ([01 §3](01-WHAT-IS-TRUE.md)).

---

## §5 · How this relates to the other folders

- **GeniOS-008 (the architecture)** is unchanged. This plan completes its L3 Intelligence Graph and the L2 → L3 write-back, which is step 11 of the Orchestrator ("write back to L3 with compare-and-set").
- **GeniOS-012 (ideal → live, loss points D1–D32).** Its loss points are still true as symptoms.
  - Superseded by the work object (Step 2): the L3 filing items. These are: one counterparty with several live situations; a wave never treated as one subject; any reply closing every ask; a bounce erasing the waiting card; equal-rank conflicting numbers overwriting each other.
  - Carried into Step 7: its L1 items, such as the window and the archive.
  - Reused here: the work Harsh built since 23 Oct, H-01 … H-28 and goals S28–S31 (block G, `goal_impacts`, `goal_proposal`, `company_goals`, `cards.goal_refs`).
- **The cutover rule still holds: beside, not instead.**
  - Works are built beside today's `context_situations`. The old lanes keep running.
  - For this org, the old lanes stop delivering only when Step 6's gate passes, and then by an activation row, not by deleting code.

---

## §6 · Read in this order

| # | File | What it holds | For |
|---|---|---|---|
| 00 | this file | the answer, the steps, the decisions, the correction | everyone |
| 01 | [01-WHAT-IS-TRUE](01-WHAT-IS-TRUE.md) | every measured number, with the SQL to re-run it | Harsh, agents |
| 03 | [03-THE-WORK-OBJECT](03-THE-WORK-OBJECT.md) | the piece of work: contract, tables, loops, links, claims, admission rules, a worked example | everyone |
| 02 | [02-PLAN](02-PLAN.md) | the steps: why, what, how (by module), switches, tests, gate, risks, units | Harsh, agents |
| 04 | [04-DECISIONS](04-DECISIONS.md) | D1–D6 with defaults | Rohit |
| 05 | [05-LOG](05-LOG.md) | append-only record of what was built and measured | everyone |

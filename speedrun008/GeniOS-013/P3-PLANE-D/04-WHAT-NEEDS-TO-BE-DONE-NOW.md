# P3 · Plane D · 04 · What needs to be done now

Proved in the notebook first. A step is done only when:
- its tests pass;
- its done-when holds;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing worse.

The principle: **the knowledge is mostly right, so make it arrive whole, fill what's missing, and get it reviewed.** Rewrite nothing that is right.

---

## Decisions for Rohit

| # | Question | Recommendation |
|---|---|---|
| D-P3-1 | **How is knowledge chosen for a situation?** | By what the situation **is and holds**, across every domain: its kind of work and stage, and its events (a meeting held, a renewal date, a registration, a promise, a rejection). Several items per situation are allowed. Not by one key from one domain |
| D-P3-2 | **Is unreviewed knowledge used?** | Yes, labelled "not yet reviewed", as today. A rule you have rejected is never used |
| D-P3-3 | **How does the review happen?** | One sitting per capability (20–40 minutes each). Founder Office first, then the Admin items the founder's work uses. Accept, edit or reject each line; the reviewer's name and date are recorded; only the reviewer's acceptance flips `draft` → `stable` |
| D-P3-4 | **In what order is the missing knowledge written?** | Meetings (prepare and follow through) → introductions → vendor and renewals (Admin's renewal management, re-pointed) → compliance (Admin's licence and registration, re-pointed) → hiring → partner. Every line is sourced, AI-drafted, and reviewed by you |

## Steps

### P3-1 · One index of all the knowledge
- **What:** compile every capability, playbook, move, stage, rule of thumb and situation across **all** domains into one index. Each item records:
  - what it is about: the kinds of work, the stages, and the events it speaks to (meeting held, deadline, renewal, rejection, promise past its date, introduction made …);
  - its review state and source;
  - an id that can be cited.
- **Test:** the index finds, for each in-copy ideal card, the items a human would pick:
  - `c2` → renewal management;
  - `b2`, `i3` → follow-up coordination, plus investor relations "before an investor call";
  - `c1` → licence and registration;
  - `i1` → "investors do not chase", "a pass is a date, not a verdict", plus the conditional deferral.
- **Done when:** for all 17 in-copy ideal cards, the right items are found and no wrong domain's item is returned.

### P3-2 · Show it whole
- **What:** one renderer, used by the product and the notebook. Its output is bounded by a size budget, and a cut is always counted, never silent. It shows:
  - stages with their typical durations, "quiet means" and "ends when";
  - **every step of every move**;
  - **every rule with its conditions** (applies when, breaks down when, failure modes);
  - review state and ids.
- **Test:**
  - the investor dossier contains "write the same day" and "it reads their quiet, never ours";
  - a situation with no matching item says so, by kind and by event, rather than showing nothing.
- **Done when:** on re-judging, `i3` comes back as "send the follow-up" and `i2` as "answer the question", or each has a stated reason why not. This also needs P4-2's precedence.

### P3-3 · Fill the founder's missing kinds of work
- **What:** author meetings, introductions, vendor and renewals, compliance, hiring and partner, in the same shape as investor relations:
  - stages with sourced typical durations;
  - quiet means;
  - moves with their steps;
  - rules of thumb with their conditions.

  Re-use Admin's approved items wherever they already say it. AI drafts each line with its source; nothing is invented.
- **Test:** each new item has at least two golden cases from the copy: one where it must speak, one where it must stay silent (P3-6).
- **Done when:** the share of the notebook's situations with expertise behind them rises from 29% to **at least 85%**, and `b2`, `b3` and `c2` are re-judged as the ideal calls them.

### P3-4 · Your review
- **What:** a review sheet per capability. Each line shows its source and your three buttons (accept, edit, reject). A local file or a page is fine. Your accepted lines become `stable` and `approved` with your name and date. Rejected lines are never shown to the model again.
- **Done when:** Founder Office is reviewed. The five situations approved but never flipped (1 Oct) are flipped by their reviewer.

### P3-5 · Fix the two known wrong items
- **What:** narrow `money-owed-either-way` to real money owed, and make `dependency-stated` keep its quote. Each fix gets a test case from the 4 Oct live cards.
- **Done when:** both cases pass, and no false "payment obligation" card appears on the copy.

### P3-6 · A test for every piece of knowledge
- **What:** each item (rule, move, stage) lists the golden cases where it must be cited and where it must not. A test runs the selection (P3-1) and the citation check (P4-5) over them.
- **Done when:** every Founder Office item and every Admin item the founder's work uses has its cases, and they pass.

## Order and dependencies

```
P3-1 index ─► P3-2 render whole ─► (P4-2 precedence, P4-5 citations) ─► re-judge i2, i3
           └► P3-3 fill missing kinds ─► P3-6 tests ─► re-judge b2, b3, c2
P3-4 review (Rohit) can run alongside from now; P3-5 is independent
```

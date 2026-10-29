# P2 · Notebook · 02 · What's failing, and why

"Us" means the AI sessions that built the product and the notebook under Rohit's direction. "Mine" means this notebook's own code (29 Oct). None of these is a misunderstanding by Rohit.

F1–F8 and N1–N8 were written on 29 Oct morning. F9–F12 and N9–N10 come from the deeper measurement in [01](01-WHATS-EXACTLY-THERE.md). P0 comes from the review on 29 Oct evening.

---

## P0 · The plan itself was not complete

**Evidence.** Rohit asked whether P2 was written perfectly. Four references were read in full, and every requirement each one places on the Notebook was checked against P2's six files and the built notebook. The references were:
- the ideal dashboard;
- the expected outcomes ([10](../10-ACCEPTANCE.md) and the card-by-card trace);
- Design Atlas v2;
- the launch film, with Rohit's description of the loops.

| Reference | Requirements | Fully covered | Partly | Missing | Contradicted by the plan | Another part's |
|---|---|---|---|---|---|---|
| The ideal dashboard | 89 | 2 | 63 | 18 | 3 | 3 |
| Design Atlas v2 and the GeniOS-008 architecture | 90 | 2 | 63 | 16 | 7 | 2 |
| The expected outcomes | 71 | 6 | 47 | 11 | 5 | 2 |
| The launch film and the loops | 59 | 4 | 38 | 13 | 1 | 3 |
| **All** | **309** | **14** | **211** | **58** | **16** | **10** |

**The 16 places where the plan would have built the wrong thing, and where each is now fixed:**

| The plan said | Why it was wrong | Fixed in |
|---|---|---|
| System mail is grouped by its sender | A payment processor's renewal notice never meets the vendor's situation, so `c2` can't form; a processor's or portal's mail belongs to what it is about | 07 §2.3 |
| Archived mail is read only when it belongs to a live situation | When the obligation mail is the only trace of the work (`f2`'s reminders), there is nothing for it to belong to | 07 §2.3, D-P2-3 |
| The model writes how long a gap has lasted, and counts in summaries | Every number served must be counted by code | 07 §0 rule 7, A-8, I-17 |
| A situation goes dormant after its playbook's window, or 90 days | A timer can put `i1` or `s1` to sleep while a door is open in writing, or while we owe them | 07 §5.3 |
| Other parts read the Notebook's tables; capture reads it to promote and to purge | Atlas: L1 never reads L3, and every read goes through the API | 07 §0 rule 3, §12, §14 |
| The Notebook forms situations by clustering, and code makes situations | Atlas: L2 forms situations and L3 only admits them | 07 §4.1, P2-9 |
| A parallel set of conclusion tables kept beside the old situations for good | Atlas: one chain, no second graph | 07 §1, D-P2-12: `work_items` heads the one chain and replaces `context_situations` per tenant at cutover; Atlas III.4 is amended with your yes |
| The model writes the six confidence words | Atlas A.4: each dimension is computed by units, never asserted | 07 §9.4 |
| Raw copies are dropped once clean text exists | Raw evidence a fact points at is never deleted while provenance points at it | 07 §14 |
| Goal links to proposed goals, unremarked | The architecture links only admitted situations to live, printed goals; it needs amending with Rohit's yes | D-P2-13, 07 §6.4 |
| Proposed goals sit in the goals block the model reads | The same: two separate blocks | D-P2-13 |
| Links have four relations | Atlas and the work object need about twenty, each with writer, evidence and validity | 07 §4.6 |
| A goal's next move is one open card owed by us | When nothing is owed by us, the next move is GeniOS's next check (`f4`); some goals need two cards (`i2` and `i3`) | 07 §6.1 |
| A timer may make work dormant with nothing owed | "Nothing owed by whom?": a timer must never quiet work we owe (`s1`) | 07 §5.3, I-9 |
| An expected-by date must be in the future when set | That erases `f3`, `i3`, `c1`, `i2` and `b3`, the silences 13 of the 20 ideal cards rest on | 07 §4.3 |
| System mail about a situation may be noise when the sender isn't the subject | The same as the first row, at the level of placement | 07 §2.3, A-19 |

**Cause.** P2 was written from the measured failures of the product and the notebook, against the 20 ideal cards and the 10 goals. It was not checked element by element against the four references: everything the ideal dashboard shows, everything Atlas v2 requires of L3, and everything the film promises.

**Whose:** mine.

**The fix:** the full specification [07](07-THE-NOTEBOOK-SPEC.md), the decisions and steps in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md), and the line-by-line trace [08](08-REQUIREMENTS-TRACE.md). The trace shows that each of the 309 requirements lands in a section and a step.

---

## In the product

### F1 · Nothing GeniOS concludes is saved (the root)

- **Evidence:**
  - Admission runs "in SHADOW: nothing here touches the situations". Of its 34 decisions, 24 said "admit", and nothing was written.
  - 30 interpretations were written and nothing reads them.
  - **None of the 16,792 facts came from the brain**: 10,644 were computed by code, and 6,148 read from events.
  - On 28 Oct the brain concluded "this is a portal correction, not an investor relationship". It was logged, and the file is still an investor relationship.
- **Why it matters:**
  - The brain re-reads about 70,000 characters every time, so it is capped at about 12 files a day (P1 F3).
  - It can't notice silence, because no expected-by date is stored.
  - Wrong notes stay wrong, and the rule cards win.
- **Cause:** the Intelligence Graph, the second half of L3, was designed (Atlas v2: "L3 only remembers what L2 concluded") and never built. Admission was left in shadow.
- **Whose:** us (architecture).

### F2 · The wrong unit: the sender, not the business situation

- **Evidence:** a file is "one counterparty's correlations", computed on each read and never stored (264 files).
  - One application sits in 2 files; the incubator's programme sits in 4.
  - The intro platform is one file of **500 mails, 322 threads and 61 people**. It was stopped 31 times as too big and never judged. This loses `f3`, `b1` and `b3`.
- **Cause:** files were built for signal correlation, before the business situation was defined as the unit of work (GeniOS-013 [05](../05-THE-WORK-OBJECT.md)).
- **Whose:** us (design).

### F3 · Notes are never reconciled, so they never close

- **Evidence:**
  - 87 of 87 promises are open (83 past due), and 208 of 212 questions are open.
  - On the accelerator, two notes are both false, because the updates were sent on 11, 13 and 26 Aug:
    - "promise open";
    - "dependency waiting on the founder".
  - The old rule engine turned the false note into a card: "you are 71 days late".
- **Cause:** each rule writes its own note, and nothing decides which note is true now. That is the brain's job, and its conclusion is not saved (F1).
- **Whose:** us (design).

### F4 · Situations come from rules, and quiet work is put to sleep

- **Evidence:**
  - 1,528 situations come from a fixed list of types.
  - A 45-day default puts quiet situations to sleep; 282 are dormant. Yet quiet work is exactly where the founder's best intelligence lies (`i2`, `b3`).
- **Cause:** situations are formed by rules, not by reasoning ("the situation is formed by reasoning" is Atlas v2's rule).
- **Whose:** us (design and configuration).

### F5 · Goals are stuck behind one door

- **Evidence:**
  - A goal is live only when its brief line is accepted. 0 of 29 lines are accepted, so there are 0 goal links and 0 goals on cards.
  - The proposals are also built on F2's files: they count a government portal and an incubator as investors.
- **Cause:** the door was built (GeniOS-012), but the founder's approval step has no place in the founder's day yet, and proposed goals may not be used in reasoning.
- **Whose:** process and design (planned in GeniOS-009 G6; not finished).

### F6 · The founder's actions, executions and Screen are stored but never joined to the work

- **Evidence:** none of these updates a business situation's page or a goal:
  - 211 card events;
  - 105 executions, with 55 outcomes;
  - 526 situation outcomes;
  - 141 Screen thread summaries.
- **Cause:** the Act and Maintain loops don't exist yet (P1 F5).
- **Whose:** unfinished work.

### F7 · Archived mail carries no text

- **Evidence:**
  - 636 of 1,829 mails were archived by the gate, with no clean text. Only the encrypted raw copy is kept, for 180 days.
  - One application's "still incomplete" reminders are among them (`f2`).
- **Cause:** a deliberate production choice: archived words are kept away from models (capture pipeline, F37). The notebook recovers them locally from the stored encrypted payload.
- **Whose:** a decision for Rohit ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md), D-P2-3).

### F8 · Only 180 days are captured

- **Evidence:** three ideal cards (`i6`, `s1`, `s2`) and one ideal goal rest on March–April mail.
- **Whose:** an onboarding setting (GeniOS-013 Step 7 proposes 365 days at onboarding).

### F9 · Most of the graph is about a department that is switched off

- **Evidence:** Support is off for this org, yet:
  - **730 of the 1,164 active situations (63%)** are support-desk types: 667 "first response overdue" and 63 "ticket ageing";
  - **3,590 of the 16,792 facts (21%)** track first responses.

  Every chain recomputes them (P1 F9).
- **Cause:** the support readings run for every tenant (`context/runner.py`, the support pass; GeniOS-013 U13-31 names it). Nothing asks whether the department is switched on.
- **Whose:** us (configuration and design).

### F10 · The founder's answers never arrive

- **Evidence:**
  - GeniOS asked the founder 40 questions in the first week and got **0 answers** (22 still open, 18 retired).
  - There are 0 decisions and 0 corrections recorded.
- **Why it matters:** the answers are the best evidence there is. Only the founder knows whether an offer was accepted (`h1`) or a call happened. And "every Done teaches" has nothing to learn from.
- **Cause:** the questions are written, but there is no place in the founder's day to answer them (P5) and no Act loop to read the answers back in (P1 F5).
- **Whose:** unfinished work.

### F11 · Evidence text expires on a clock that ignores the work

- **Evidence:** clean text is deleted 180 days after **capture**, and the encrypted raw mail too ([01](01-WHATS-EXACTLY-THERE.md) §5).
  - With a 365-day onboarding, every old mail's text expires 180 days after the day it was captured, whatever its own date.
  - A situation alive longer than that (a fundraise, a long hire) loses the words behind its earlier pages.
- **Cause:** retention was set per table, for privacy and size, before any conclusion existed that would need the evidence.
- **Whose:** us (design). It needs a decision (D-P2-7).

### F12 · One tenant fills the database

- **Evidence:**
  - Production reported 570 MB against a 472 MB ceiling on 27 Oct (and 544 MB the day before).
  - The same rows load into the local copy as about 280 MB, so the rest is most likely dead rows from rewriting the whole company every chain. Production's own table sizes were not read.
  - The largest live tables are provenance links (49 MB), **one week of Screen captures (45 MB)** and raw copies (30 MB).
- **Why it matters:** the database can't hold this tenant within its plan, let alone a second.
- **Cause:** whole-company rewrites on every chain (P1 F9), the support desk above (F9), and raw Screen captures kept for months.
- **Whose:** us (architecture).

## In the notebook

### N1 · A goal is only a sentence

- **Evidence:** the 15 goals hold a statement, a category, a why, linked situations and evidence. They have none of these:
  - target or captured quote;
  - plan or progress;
  - status or next move;
  - approval state or parent.
- **Why it matters:** a goal can't say what is missing, so no card comes from a goal.
- **Whose:** mine (goals were built as a list).

### N2 · Two sets of links between goals and situations, disagreeing

- **Evidence:** each page's goal links and relate's `goals.work_ids` disagree on **53 of 233** linked situations: 21 are linked only by the page, 32 only by relate.
- **Whose:** mine.

### N3 · The wrong size of goal

- **Evidence:**
  - one goal per investor (three of them) instead of one fundraising goal with those conversations as moves;
  - one goal holding **163** situations (the intro platform), which is an activity, not an outcome;
  - **no umbrella "get into an accelerator this cycle"**, so 21 live situations have no goal. 18 of them are programme applications, and 6 of those have open cards (one is `f2`).
- **Whose:** mine (the goal prompt had no grain rule, and there is no parent or child).

### N4 · No lifecycle, so old dates keep making cards

- **Evidence:**
  - 63 open cards against the ideal's 20. Many are "Overdue: confirm a slot in July", raised because an expected-by date passed.
  - No situation is ever marked dormant, and nothing decays.
- **Whose:** mine.

### N5 · Facts don't travel between situations

- **Evidence:** the incubator's final-review milestone never reached the accelerator page, so `i1` was the opposite call. Of the 138 links in `b2`:
  - 130 are "part of" links made by code, hanging each introduction under the intro platform's own situation;
  - 8 came from relate's one call over all 421 situations;
  - none links the incubator's milestone to the accelerator.
- **Whose:** mine (cross-situation facts travel only through that one call, and the judge sees only linked situations).

### N6 · Inputs are mail and calendar only

- **Evidence:** no Screen, no executions, no founder actions. "Every Done teaches" has nothing to read.
- **Whose:** not built yet.

### N7 · The path forward in time keeps an old copy of the grouping rules

- **Evidence:** `nb/update.py` has its own clustering. It hasn't had the 29 Oct fixes:
  - the registrable domain;
  - the archived-noise rule;
  - the person-first channel rule;
  - the system-thread routing.
- **Whose:** mine.

### N8 · The page had to shrink to fit the API

- **Evidence:**
  - The full page returned API 400 "The compiled grammar is too large". Each third of it compiles alone.
  - So the six confidence words, links and per-loop reasons were dropped from the page, and topic now follows from metric in code.
- **Whose:** an API limit, found by test. A new field needs a probe first (`contracts.py` says so).

### N9 · Every mail is treated as the founder's

- **Evidence:** the notebook has no notion of who may see a piece of evidence. Every page mixes whatever mail it holds. The product marks every mail with its visibility ("participants"), and the notebook ignores it.
- **Why it matters:**
  - For one founder this is harmless.
  - For a team, a member's private thread could reach a page the founder or another member sees.
- **Whose:** mine. It was a single-founder prototype by design, and it must be solved before a team is onboarded.

### N10 · Grouping is proved on one mailbox only

- **Evidence:** Phase D was measured once: about 1,800 mails, 107 model calls, $1.11, 2.7 minutes. The intro platform's 500 mails were split well.
  - No mailbox two, five or ten times larger has been grouped.
  - No team of several mailboxes has been grouped, with threads that cross between them.
- **Why it matters:** onboarding a larger customer may hit cluster sizes the prompt can't hold, or cost more than the plan says.
- **Whose:** not tested yet (P1-10's drill and P2-12 below).

---

## Summary

| Failure | Whose | Kind |
|---|---|---|
| P0 the plan itself incomplete (14 of 309 covered) | mine | planning; fixed by 07, 04 and 08 |
| F1 nothing saved | us | architecture (the root) |
| F2 wrong unit | us | design |
| F3 notes never close | us | design |
| F4 rule situations, dormancy | us | design, config |
| F5 goals stuck | process | planned, not finished |
| F6 actions not joined | unfinished | not built |
| F7 archived text | decision | Rohit's call |
| F8 180 days | config | onboarding setting |
| F9 the support desk for everyone | us | config, design |
| F10 no answers arrive | unfinished | not built (P5, P1) |
| F11 text expires on capture's clock | us | design; Rohit's call (D-P2-7) |
| F12 one tenant fills the database | us | architecture |
| N1–N7 | mine | notebook code and design |
| N8 | API | a limit, found by test |
| N9 every mail is the founder's | mine | prototype scope |
| N10 grouping proved once | not tested | drill needed |

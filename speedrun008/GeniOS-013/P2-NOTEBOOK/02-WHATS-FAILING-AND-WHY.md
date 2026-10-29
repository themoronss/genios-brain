# P2 · Notebook · 02 · What's failing, and why

"Us" means the AI sessions that built the product and the notebook under Rohit's direction. "Mine" means this notebook's own code (29 Oct). None of these is a misunderstanding by Rohit.

---

## In the product

### F1 · Nothing GeniOS concludes is saved (the root)

- **Evidence:** admission runs "in SHADOW: nothing here touches the situations". 30 interpretations are written and nothing reads them. **0 of 16,792** facts came from the brain. On 28 Oct the brain concluded "this is a portal correction, not an investor relationship". It was logged, and the file is still an investor relationship.
- **Why it matters:** the brain re-reads about 70,000 characters every time, so it is capped at about 12 files a day (P1 F3). It can't notice silence, because no expected-by date is stored. Wrong notes stay wrong. The rule cards win.
- **Cause:** the Intelligence Graph, the second half of L3, was designed (Atlas v2: "L3 only remembers what L2 concluded") and never built. Admission was left in shadow.
- **Whose:** us (architecture).

### F2 · The wrong unit: the sender, not the business situation

- **Evidence:** a file is "one counterparty's correlations", computed on the fly and never stored.
  - One application sits in 2 files; the incubator's programme sits in 4.
  - The intro platform is one file of **500 mails, 322 threads, 61 people**, stopped 31 times as too big, never judged. This loses `f3`, `b1` and `b3`.
- **Cause:** files were built for signal correlation, before the business situation was defined as the unit of work (GeniOS-013 [05](../05-THE-WORK-OBJECT.md)).
- **Whose:** us (design).

### F3 · Notes are never reconciled, so they never close

- **Evidence:** 87 of 87 promises are open (83 past due) and 208 of 212 questions are open. On the accelerator, a "promise open" note and a "dependency waiting on the founder" note are both false, because the updates were sent on 11, 13 and 26 Aug. The old rule engine turned the false note into a card: "you are 71 days late".
- **Cause:** each rule writes its own note, and nothing decides which note is true now. That is the brain's job, and its conclusion is not saved (F1).
- **Whose:** us (design).

### F4 · Situations come from rules, and quiet work is put to sleep

- **Evidence:** 1,528 situations come from a fixed list of types. 667 of them are support-desk situations, although Support is off. A 45-day default puts quiet situations to sleep. Yet quiet work is exactly where the founder's best intelligence lies (`i2`, `b3`).
- **Cause:** situations are formed by rules, not by reasoning ("the situation is formed by reasoning" is Atlas v2's rule).
- **Whose:** us (design and configuration).

### F5 · Goals are stuck behind one door

- **Evidence:** a goal is live only when its brief line is accepted. 0 of 29 lines are accepted, so there are 0 goal links and 0 goals on cards. The proposals are also built on F2's files: they count a government portal and an incubator as investors.
- **Cause:** the door was built (GeniOS-012), but the founder's approval step has no place in the founder's day yet, and proposed goals may not be used in reasoning.
- **Whose:** process and design (planned in GeniOS-009 G6; not finished).

### F6 · The founder's actions, executions and Screen are stored but never joined to the work

- **Evidence:** 211 card events, 105 executions with 55 outcomes, 526 situation outcomes and 141 Screen thread summaries. None of them updates a business situation's page or a goal.
- **Cause:** the Act and Maintain loops don't exist yet (P1 F5).
- **Whose:** unfinished work.

### F7 · Archived mail carries no text

- **Evidence:** 636 of 1,829 mails were archived by the gate, without text. One application's "still incomplete" reminders are among them (`f2`).
- **Cause:** a deliberate production choice: archived words are kept away from models (capture pipeline, F37). The notebook recovers them locally from the stored encrypted payload.
- **Whose:** a decision for Rohit ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md), D-P2-3).

### F8 · Only 180 days are captured

- **Evidence:** three ideal cards (`i6`, `s1`, `s2`) and one ideal goal rest on March–April mail.
- **Whose:** an onboarding setting (GeniOS-013 Step 7 proposes 365 days at onboarding).

## In the notebook

### N1 · A goal is only a sentence

- **Evidence:** the 15 goals hold statement, category, why, linked situations and evidence. There is no target, captured quote, plan, progress, status, next move, approval state or parent.
- **Why it matters:** a goal can't say what is missing, so no card comes from a goal.
- **Whose:** mine (goals were built as a list).

### N2 · Two sets of links between goals and situations, disagreeing

- **Evidence:** each page's goal links and relate's `goals.work_ids` disagree on **53 of 233** linked situations: 21 are linked only by the page, 32 only by relate.
- **Whose:** mine.

### N3 · The wrong size of goal

- **Evidence:**
  - one goal per investor (three of them) instead of one fundraising goal with those conversations as moves;
  - one goal holding **163** situations (the intro platform), which is an activity, not an outcome;
  - **no umbrella "get into an accelerator this cycle"**, so 21 live situations have no goal. 18 of them are programme applications, 6 with open cards (one is `f2`).
- **Whose:** mine (the goal prompt had no grain rule, and there is no parent/child).

### N4 · No lifecycle, so old dates keep making cards

- **Evidence:** 63 open cards against the ideal's 20. Many are "Overdue: confirm a slot in July", raised because an expected-by date passed. No situation is ever marked dormant, and nothing decays.
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

- **Evidence:** `nb/update.py` has its own clustering. It hasn't had the 29 Oct fixes: the registrable domain, the archived-noise rule, the person-first channel rule, the system-thread routing.
- **Whose:** mine.

### N8 · The page had to shrink to fit the API

- **Evidence:** the full page returned API 400 "The compiled grammar is too large". Each third of it compiles alone. The six confidence words, links and per-loop reasons were dropped from the page; topic now follows from metric in code.
- **Whose:** an API limit, found by test. A new field needs a probe first (`contracts.py` says so).

---

## Summary

| Failure | Whose | Kind |
|---|---|---|
| F1 nothing saved | us | architecture (the root) |
| F2 wrong unit | us | design |
| F3 notes never close | us | design |
| F4 rule situations, dormancy | us | design, config |
| F5 goals stuck | process | planned, not finished |
| F6 actions not joined | unfinished | not built |
| F7 archived text | decision | Rohit's call |
| F8 180 days | config | onboarding setting |
| N1–N7 | mine | notebook code and design |
| N8 | API | a limit, found by test |

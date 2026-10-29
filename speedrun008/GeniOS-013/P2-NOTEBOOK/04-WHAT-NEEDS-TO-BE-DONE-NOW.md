# P2 · Notebook · 04 · What needs to be done now

There are two tracks, as in P1:
- **The notebook track (P2-1 to P2-12).** It builds the missing half of the Notebook locally and proves it.
- **The relief track (Q1 to Q3).** These are small changes to today's product that stop it filling its database with a department the company doesn't have. They need Rohit's approval and Harsh's hands.

A step is done only when:
- its tests pass;
- its done-when holds;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing worse.

---

## Decisions for Rohit

Each has a recommendation. Saying "go" accepts all of them.

| # | Question | Recommendation |
|---|---|---|
| D-P2-1 | **Is the business situation the unit of work?** | Yes: one application, one conversation, one introduction, one renewal, one hire. Not a sender, not a thread |
| D-P2-2 | **What does a goal hold?** | The fields below. One optional parent level (an umbrella goal with sub-goals), then plan steps, then situations. No OKR or key-result objects for now |
| D-P2-3 | **May archived mail be read?** | In the notebook, yes (it is, now). In the product: read an archived mail **only when it belongs to a live situation** (an application's reminders, a renewal notice). Bulk mail stays unread |
| D-P2-4 | **How far back at onboarding?** | 365 days, so the March–April ideal items are reachable (GeniOS-013 Step 7) |
| D-P2-5 | **May proposed goals be used before you confirm them?** | Yes, labelled "proposed". They never appear on a card as confirmed |
| D-P2-6 | **Which inputs come next?** | Screen first (already captured), then the founder's actions, answers and executions, then other tools as they connect |
| D-P2-7 | **How long is the text of evidence kept?** | **As long as a live situation or goal cites it**, and 180 days after that situation ends. Mail that no situation holds (bulk, noise) stays as today: 180 days after capture. A page keeps its admitted quotes, with their source ids, until the tenant is erased. Today every text is deleted 180 days after capture (F11) |
| D-P2-8 | **Support-desk readings for a company without Support?** | **Stop them now** (Q1). They are 63% of the active situations and 21% of the facts, for a department this company doesn't have (F9) |
| D-P2-9 | **The database plan** | Move production to a **larger database plan before the second customer**, and cut the churn first (Q1 here, R2 in P1). One tenant is already over the ceiling (F12) |
| D-P2-10 | **Teams** | Single founders first. A team is onboarded only after visibility on pages is built and tested (P2-10) |
| D-P2-11 | **Money for P2's notebook steps** | About **$5 more** for the notebook, on top of P1's $15 (its cap goes from $35 to $40). Most P2 steps are code; the model cost is re-judging the situations they touch, and the grouping drill |

## The goal object (D-P2-2)

| Field | Meaning | Written by |
|---|---|---|
| statement | The end, in the founder's words, at most 200 characters | model, then founder |
| category | One of Rohit's eight: investment, funding, business, sales, projects, progress, process, hiring | model |
| parent | An optional umbrella goal | model, then founder |
| target | What counts (a number, a count, or a state) **and where it was said** (a quote and its mail) | model, checked by code |
| captured | The moment of commitment: a verbatim quote and its source | model, checked by code |
| why, proof | Why the goal exists, with a quote | model, checked by code |
| plan | 3–6 steps, each done, doing or next. A done step carries its date from a situation; a doing step names the situation working it | model, checked by code |
| progress | One of: an outcome counted against the target; verified plan steps; or **unknown, with the reason** (never 0) | code (P4-4) |
| status | on track, at risk, or blocked, with a reason line | code by rule (P4-4); the model writes the reason |
| next move | The open card (and its situation) that moves this goal next, owed by us | model, checked by code |
| gaps | What is missing, and how long it has been missing | model |
| approval | proposed, confirmed, not now (until a date), or dropped, plus the founder's answers to the four questions | founder |
| versions | Every change kept, with what changed and why | code |

## The plan at a glance

| Step | What | Track | Needs | Model cost | Done when |
|---|---|---|---|---|---|
| P2-1 | The goal object | notebook | — | $0 | the ideal's 9 goals stored and read back whole |
| P2-2 | One link set | notebook | P2-1 | $0 | 0 disagreements; every live situation linked or listed |
| P2-3 | Lifecycle | notebook | P3 "dormant after" | ≈$0.50 | the stale July cards gone, no ideal card lost |
| P2-4 | What changed, and why, on every version | notebook | — | $0 | the replay lists each day's changes from these records |
| P2-5 | New kinds of evidence | notebook | P1-4 | ≈$0.50 | an action and an outcome cited in a judgment |
| P2-6 | Facts travel along goals and links | notebook | P2-2 | ≈$1 | the incubator's milestone in the accelerator's dossier (`i1`) |
| P2-7 | The founder's decisions, approvals and answers | notebook | P2-5 | $0 | approving a goal changes its label in the next run |
| P2-8 | The check grows with the notebook | notebook | each step | $0 | invariants cover goals, links and lifecycle |
| P2-9 | One copy of the grouping rules | notebook | with P1-4 | $0 | both paths group the same threads the same way |
| P2-10 | Visibility on evidence and pages | notebook | — | $0 | a private mail never reaches another person's page (test) |
| P2-11 | Retention that follows the work | notebook | D-P2-7 | $0 | a report of what today's rule would delete from live work |
| P2-12 | Grouping at scale | notebook | P2-9 | ≈$3 | a mailbox 3× larger grouped within budget, the 17 still found |
| Q1 | Stop the support desk for a company without Support | product | D-P2-8 | saves | 730 fewer active situations, 3,590 fewer facts |
| Q2 | Read production's table sizes and dead rows | product | — | $0 | the churn measured, and a clean-up plan written |
| Q3 | Keep the text that live work cites | product | D-P2-7 | $0 | no live situation's evidence expires |

---

## The notebook track

### P2-1 · The goal object
- **What:** the table and its checks, as above.
- **Test:** the ideal's 9 in-copy goals, typed in as a fixture, are stored and read back with no field lost.
- **Done when:** the fixture passes, and the new goal invariants hold:
  - every goal has a target, or says "target not stated";
  - every done step has a date;
  - progress is never 0 without a count behind it.

### P2-2 · One link set
- **What:** a single situation-to-goal table. Each link holds:
  - a relation: advances, threatens, depends on, or unclear;
  - a "through" phrase: how the situation moves the goal;
  - its evidence;
  - who linked it (the page, or relate).

  `goals.work_ids` and the page's own links both write here.
- **Test:** writing the same link from both places gives one row.
- **Done when:**
  - there are 0 disagreements (53 today);
  - every live situation is linked to a goal or listed as "not linked", and the list is shown, never hidden.

### P2-3 · Lifecycle
- **What:** a situation is live, waiting, dormant, done or history, with its reason and the date it entered that state.
  - It goes dormant after its playbook's "dormant after" (P3), or after 90 days with nothing owed.
  - It comes back to live on any new evidence.
  - A card may not stand on a dormant, done or history situation (P5).
- **Done when:** the stale July cards are gone (with P5-1), and no in-copy ideal card is lost.

### P2-4 · What changed, and why, on every version
- **What:** each situation version and goal version stores a one-line "what changed and why", and the fields that changed.
- **Done when:** the replay report (P1-8) can list each day's changes from these records alone.

### P2-5 · New kinds of evidence
- **What:** three new kinds:
  - Screen thread summaries and verdicts;
  - the founder's actions (done, later, not now, answers, delegations);
  - executions and their outcomes.

  For each one:
  - it has an instant and an as-of rule;
  - it is placed into its situation (P1-4);
  - it can be cited by id, like a mail.
- **Done when:** a founder action and an execution outcome appear in their situation's dossier, and a judgment cites them.

### P2-6 · Facts travel along goals and links
- **What:** a situation's new milestone or decision is offered to two kinds of situation, as "news from the same goal" in their dossier (P4 uses it):
  - the other situations of the same goal;
  - linked situations.
- **Done when:** the incubator's final review appears in the accelerator page's dossier (`i1`), dated, with its source.

### P2-7 · The founder's decisions, approvals and answers
- **What:** all of these are stored as evidence, with who and when:
  - answers to the four goal questions;
  - answers to GeniOS's questions (40 were asked in the product's first week, and 0 answered: F10);
  - card answers, "not now", and approvals.

  Approving a goal changes its state, and how every later dossier labels it.
- **Done when:** approving one goal locally changes its state and its label in the next judge run, and an answered question settles the loop that asked it.

### P2-8 · The check grows with the notebook
- **What:**
  - **goal pages:** quotes are word for word; dates come from printed situations; the next move points at an open card; unknown is never 0;
  - **links and lifecycle:** they must be consistent;
  - **visibility:** a page shown to a person cites only evidence that person may see (with P2-10);
  - **reasoning patterns:** the conditions of any pattern the model cites (with P4-5).
- **Done when:** the invariant set covers goals, links, lifecycle and visibility, and passes on the rebuilt build.

### P2-9 · One copy of the grouping rules
- **What:** `update.py` calls `works.py` (shared with P1-4).
- **Done when:** a test proves both paths group the same threads the same way.

### P2-10 · Visibility on evidence and pages (D-P2-10)
- **What:**
  - Every piece of evidence carries who may see it, taken from the product's own fields (`visibility_scope`, `visibility_principals`). A seat's private mailbox is visible to that seat; a shared thread to its participants and the company.
  - Every page records the audience of the evidence it cites.
  - A dossier or a card built for a person uses only what that person may see. A situation that mixes audiences is split, or shown with the private part withheld and counted.
- **Test:** a synthetic second seat with one private thread in a shared situation. The founder's page never quotes it; the seat's page does.
- **Done when:** the test passes, and the invariant "no page cites evidence outside its audience" holds.

### P2-11 · Retention that follows the work (D-P2-7)
- **What:** each piece of evidence knows which live situations and goals cite it. A report lists what today's rule (180 days after capture) would delete that live work still cites, and what the new rule would keep.
  - The copy never expires anything, so locally this is a report.
  - In the product it becomes the retention rule (Q3, then [05](05-HOW-AT-PRODUCTION-LEVEL.md) §6).
- **Done when:** the report runs on `b2`, and every item on it is explained.

### P2-12 · Grouping at scale
- **What:** Phase D (grouping) run on a larger mailbox: the copy's six months with every thread cloned twice under new ids and shifted dates, about 5,400 mails. Measured:
  - cost and time;
  - the largest cluster the prompt was given;
  - the share of threads placed by code and by the model;
  - whether the 17 in-copy ideal items are still each one situation.
- **Done when:**
  - the cost grows no faster than the mail;
  - no cluster is cut short;
  - the 17 are still found.

## The relief track (today's product)

Owner: Harsh, with the agents Harsh assigns. Each goes live per tenant behind a row, and is measured before and after.

### Q1 · Stop the support desk for a company without Support (D-P2-8)
- **What:** run the support readings (`context/runner.py`'s support pass: first response overdue, ticket ageing) only for a tenant whose Support domain is switched on. This is the support part of GeniOS-013 U13-31.
- **Done when:** for this org, 730 fewer active situations and about 3,590 fewer facts after a week, the chain shorter (measured with P1 R1), and no card the founder had acted on is lost.

### Q2 · Read production's table sizes and dead rows
- **What:** one read-only query on production for each table's size, its live rows and its dead rows. It is run by a person with production access; the coding sessions don't read production.
- **Done when:** the gap between 570 MB and the 280 MB of live rows is explained table by table, and a clean-up plan is written. The plan covers vacuum, Screen capture retention per org, and provenance trimming.

### Q3 · Keep the text that live work cites (after D-P2-7)
- **What:** until the notebook's rule is ported, a mail's clean-text expiry is extended while its thread has an open question or promise, or a date ahead.
- **Done when:** no thread with open work loses its text, measured weekly.

---

## Order and dependencies

```
P2-1 goal object ─► P2-2 one link set ─► P2-6 facts travel ─► (P4-6 goal reasoning)
P2-3 lifecycle ──────────────────────────────────────────────► (P5-1 when a card is raised)
P2-4 change records ─► (P1-4 evolve, P1-8 replay)
P2-5 evidence kinds ─► P2-7 decisions and answers ─► (P1-5 act)
P2-8 checks grow with each step
P2-9 one copy of the rules (with P1-4) ─► P2-12 grouping at scale ─► (P1-10 onboarding drill)
P2-10 visibility ─► (teams, D-P2-10)
P2-11 retention report ─► Q3
product:  Q2 measure ─► Q1 support desk off ─► (P1 R2)          Q3 after D-P2-7
```

## How P2 lines up with the 28 Oct plan (GeniOS-013 [03](../03-HOW-IT-GETS-FIXED.md))

| P2 step | 28 Oct units it proves or replaces |
|---|---|
| The situation page, its members, loops and claims | U13-05 (`contracts/work_item.py`), U13-06 (the tables), U13-07 (`context/work_store.py`) |
| P2-1, P2-2 goals and links | U13-27 (block G, proposed goals with ids) |
| P2-3 lifecycle | U13-24 (the stop rule instead of a default window) |
| Q1 support desk | U13-31 (support readings only for an activated Support) |
| D-P2-4 365 days | U13-38 |
| D-P2-3 archived mail | the promotion path in [05](05-HOW-AT-PRODUCTION-LEVEL.md) §4 |

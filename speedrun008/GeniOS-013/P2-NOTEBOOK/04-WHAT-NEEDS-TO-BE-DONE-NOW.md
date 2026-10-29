# P2 · Notebook · 04 · What needs to be done now

Everything here is proved in the notebook first. A step is done only when:
- its tests pass;
- its done-when holds;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing worse.

---

## Decisions for Rohit

| # | Question | Recommendation |
|---|---|---|
| D-P2-1 | **Is the business situation the unit of work?** | Yes: one application, one conversation, one introduction, one renewal, one hire. Not a sender, not a thread |
| D-P2-2 | **What does a goal hold?** | The fields below. One optional parent level (an umbrella goal with sub-goals), then plan steps, then situations. No OKR or key-result objects for now |
| D-P2-3 | **May archived mail be read?** | In the notebook, yes (it is, now). In the product: read an archived mail **only when it belongs to a live situation** (an application's reminders, a renewal notice). Bulk mail stays unread |
| D-P2-4 | **How far back at onboarding?** | 365 days, so the March–April ideal items are reachable (GeniOS-013 Step 7) |
| D-P2-5 | **May proposed goals be used before you confirm them?** | Yes, labelled "proposed"; they never appear on a card as confirmed |
| D-P2-6 | **Which inputs come next?** | Screen first (already captured), then the founder's actions and executions, then other tools as they connect |

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

## Steps

### P2-1 · The goal object
- **What:** the table and its checks, as above.
- **Test:** the ideal's 9 in-copy goals, typed in as a fixture, are stored and read back with no field lost.
- **Done when:** the fixture passes, and the new goal invariants hold:
  - every goal has a target, or says "target not stated";
  - every done step has a date;
  - progress is never 0 without a count behind it.

### P2-2 · One link set
- **What:** a single situation-to-goal table: relation (advances, threatens, depends on, unclear), a "through" phrase (how the situation moves the goal), evidence, and who linked it (page or relate). `goals.work_ids` and the page's own links both write here.
- **Test:** writing the same link from both places gives one row.
- **Done when:**
  - 0 disagreements (53 today);
  - every live situation is linked to a goal or listed as "not linked", and the list is shown, never hidden.

### P2-3 · Lifecycle
- **What:** a situation is live, waiting, dormant, done or history, with its reason and the date it entered that state.
  - It goes dormant after its playbook's "dormant after" (P3), or after 90 days with nothing owed.
  - It comes back to live on any new evidence.
  - A card may not stand on a dormant, done or history situation (P5).
- **Done when:** the stale July cards are gone (with P5-1), and no in-copy ideal card is lost.

### P2-4 · What changed, and why, on every version
- **What:** each situation version and goal version stores a one-line "what changed and why" and the fields that changed.
- **Done when:** the replay report (P1-8) can list each day's changes from these records alone.

### P2-5 · New kinds of evidence
- **What:** Screen thread summaries and verdicts; the founder's actions (done, later, not now, answers, delegations); executions and their outcomes.
  - Each new kind has an instant and an as-of rule.
  - Each is placed into its situation (P1-4) and can be cited by id like a mail.
- **Done when:** a founder action and an execution outcome appear in their situation's dossier, and a judgment cites them.

### P2-6 · Facts travel along goals and links
- **What:** a situation's new milestone or decision is offered to the other situations of the same goal and to linked situations, as "news from the same goal" in their dossier (P4 uses it).
- **Done when:** the incubator's final review appears in the accelerator page's dossier (`i1`), dated, with its source.

### P2-7 · The founder's decisions and approvals
- **What:** answers to the four goal questions, card answers, "not now", and approvals, stored as evidence with who and when. Approving a goal changes its state and how every later dossier labels it.
- **Done when:** approving one goal locally changes its state and its label in the next judge run.

### P2-8 · The code check grows with the notebook
- **What:**
  - **goal pages:** quotes are word for word; dates come from printed situations; the next move points at an open card; unknown is never 0;
  - **links and lifecycle:** they must be consistent;
  - **reasoning patterns:** the conditions of any pattern the model cites (with P4-5).
- **Done when:** the invariant set covers goals, links and lifecycle, and passes on the rebuilt build.

### P2-9 · One copy of the grouping rules
- **What:** `update.py` calls `works.py` (shared with P1-4).
- **Done when:** a test proves both paths group the same threads the same way.

## Order and dependencies

```
P2-1 goal object ─► P2-2 one link set ─► P2-6 facts travel ─► (P4-6 goal reasoning)
P2-3 lifecycle ──────────────────────────────────────────────► (P5-1 when a card is raised)
P2-4 change records ─► (P1-4 evolve, P1-8 replay)
P2-5 evidence kinds ─► P2-7 decisions ─► (P1-5 act)
P2-8 checks grow with each step
P2-9 one copy of the rules (with P1-4)
```

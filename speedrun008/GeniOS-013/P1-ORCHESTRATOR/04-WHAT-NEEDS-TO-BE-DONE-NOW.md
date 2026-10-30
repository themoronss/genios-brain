# P1 · Orchestrator · 04 · What needs to be done now

There are two tracks:
- **The notebook track (P1-1 to P1-10).** It builds the four loops locally, on the copy, and proves them. [05](05-HOW-AT-PRODUCTION-LEVEL.md) says how the same thing goes into the product afterwards.
- **The relief track (R1 to R6).** These are small changes to today's product. They can start now, in parallel, so the product stops filling its day with one tenant and a new design partner can be onboarded safely. They need Rohit's approval and Harsh's hands.

A step is done only when:
- its tests pass;
- its done-when number is met;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing got worse.

---

## Decisions for Rohit

Each has a recommendation. Saying "go" accepts all of them; name any you want changed.

| # | Question | Recommendation | Why |
|---|---|---|---|
| D-P1-1 | **When does Evolve run?** | **In the notebook:** one step per day, at 06:00 company time, so the replay can be checked day by day. **In the product:** on every wake-up, after a 10-minute quiet window (a burst of mails is one run), plus a 06:00 local pass for the dates and the morning view | "As my company's data evolves" means within minutes. A page judgment costs about $0.02, so this is affordable once work is per situation |
| D-P1-2 | **What wakes a situation or a goal?** | Five triggers: new evidence; a date crossing a rung (7 days, 1 day, today, passed) for a stated deadline, an expected-by date or a goal's due date; a goal changed; the founder acted; the Maintain schedule. Each fires once per rung | These cover the 13 of 20 ideal cards that are about something that did not happen |
| D-P1-3 | **How much may it spend?** | **Onboarding, once per customer:** reasoning up to $10 for six months of mail (`b2` cost $8.41) and up to $15 for 365 days, plus reading the mail at capture as today ($14.92 for this org's 180 days). **Every month after that:** Evolve under $0.50 a day (about $15 a month) and Maintain under $1 a week (about $4 a month), so reasoning stays under about $20 a month. Reading new data is extra: today about $1.90 a day, $57 a month (P2 decides whether it stays). Over a cap: work in priority order, and list what was skipped | Today's product spends about $5.70 a day ($170 a month) on this tenant, and still judges only about 11 files a day |
| D-P1-4 | **Which model?** | Keep the production model (claude-sonnet-5, thinking off) for parity. Run the acceptance set once on a stronger model, to know the ceiling | Cost parity with production; a measured ceiling before any upgrade |
| D-P1-5 | **Whose clock?** | The company's time zone, from its record, shown beside UTC wherever a time is printed. In the notebook **and** in the product's dossiers | `f1` failed on UTC alone, and the product prints UTC only too |
| D-P1-6 | **In what order inside a run?** | Goal first: evidence → place → situations → goals → cards | Cards that come from a goal's missing step (`f3`, `i1`) need the goal before the card |
| D-P1-7 | **Where do the loops run in production?** | In a **worker process of their own**: the same code, its own start command. The API only queues work and reads results | Today the brain lives inside the web server: a deploy kills a chain mid-run, and the API and the brain share one process (F14) |
| D-P1-8 | **Relief now: take the whole-company passes off the per-mail chain?** | **Yes.** Run them on the 6-hourly tick, per tenant, behind a row. Keep three days side by side for this org before trusting it | A chain is 97 min, 68 of them whole-company passes. One tenant fills the day, so a second would double everyone's wait (F9) |
| D-P1-9 | **New customers, before the new path is ready?** | Onboard **design partners only**, each armed by a written runbook: the brain on, founder-fit packs, Founder Office on, an onboarding budget. Once the new path passes the acceptance set, **every new tenant starts on it by default**, with no switch flipped by hand | Today a new founder gets old sales and support rule cards and no brain (F10) |
| D-P1-10 | **Onboard in waves?** | **Yes.** The last 30 days first, so live work is understood and first intelligence comes within about 2 hours. Then the rest of the window (365 days, `07` D4) in the background, which refines situations and goals | Capture runs at about 16 mails a minute: 365 days would take hours before anything useful appeared |
| D-P1-11 | **Money for P1's notebook steps** | About **$15 more** for the notebook, so its cap goes from $20 to $35. $10.76 is left today, and P1's steps cost about $13–15 | P1-3 is a fresh onboarding build (about $9). The replay and drills add about $5 |

## The plan at a glance

| Step | What | Track | Needs | Model cost | Done when |
|---|---|---|---|---|---|
| P1-1 | One clock | notebook | — | ≈$0.02 | `f1` judged in the right tense |
| P1-2 | A record of every run | notebook | — | $0 | every command writes one complete row |
| P1-7 | Spend in order, never silently short | notebook | P1-2 | $0 | a capped run lists every skipped item |
| P1-4 | Evolve: wake-ups, then only the touched work | notebook | P1-1, P1-2, P1-7, P2 page dates | under $0.50 a day | the replay passes |
| P1-3 | Onboard: goal first, in waves | notebook | P2-1, P4-6, P5-1 | under $10 | the stage gate in [10](../10-ACCEPTANCE.md) §5 |
| P1-5 | Act comes back in | notebook | P1-4 | ≈$0.20 | the replay's act events are applied |
| P1-6 | Maintain on a schedule | notebook | P2-5, P4-7 | under $1 a week | at most 30 open cards, no ideal card lost |
| P1-8 | The replay, 23 → 28 Oct | notebook | P1-4, P1-5, P1-6 | ≈$3 | every event on its day |
| P1-9 | Two tenants at once | notebook | P1-4, P1-7 | ≈$1 | isolated, fair, one cap |
| P1-10 | The onboarding drill | notebook | P1-3 | ≈$1 | [06](06-NEW-CUSTOMER-ONBOARDING.md) §5 targets met, crash and restart included |
| R1 | Measure today's runs | product | — | $0 | every chain and tick writes a row; `/health` names the code |
| R2 | Whole-company passes off the per-mail chain | product | R1, D-P1-8 | saves | chain under 30 min; cards unchanged over 3 days side by side |
| R3 | The company's time in every dossier | product | — | $0 | dossiers print local time beside UTC |
| R4 | The morning brief on its own schedule | product | R1 | $0 | 7 of 7 days, within 15 min of 08:00; a miss alerts |
| R5 | Stop paying twice for a bad answer | product | R1 | saves ≈39% of R-9's waste | at most one retry, with the error shown; waste under 10% |
| R6 | A runbook for onboarding a design partner | product | D-P1-9 | — | one dry run on a test tenant, no step missing |

---

## The notebook track

### P1-1 · One clock
- **What:** a new module, `nb/clock.py`. It takes the company's time zone and the build's instant, and gives:
  - `stamp(t)`: "Fri 23 Oct, 07:10 IST (01:40 UTC)";
  - `day(t)`: the company's local date;
  - `relative(t)`: "later today, 11:30 IST", "in 3 days", "2 days ago";
  - `rung(due)`: one of more than 7 days, within 7 days, tomorrow, today or passed, counted in local days.
- **Used by:**
  - `judge.py`: the system prompt's "now", the dossier header, timeline lines, meetings;
  - `cards.py`: its "today" and "passed" rules;
  - the Evolve runner (P1-4): the date rungs.
- **The time zone comes from the company page** (Phase B), or `orgs.timezone` in the copy. The model never guesses it.
- **Tests** (`tests/test_clock.py`):
  - 2026-10-23 01:40 UTC prints as "Fri 23 Oct, 07:10 IST (01:40 UTC)";
  - a meeting at 05:00 UTC prints as "10:30 IST, later today";
  - a zone with summer time is right on both sides of the change;
  - a date with no time is a whole local day;
  - a rung changes at local midnight, not UTC midnight.
- **Done when:** `f1` is re-judged as "join the panel at the time, with one number" (same or close to the ideal), and nothing else in the acceptance set gets worse.
- **Cost:** one situation re-judged, about $0.02.

### P1-2 · A record of every run
- **What:** a new table, `notebook.loop_runs`, and `nb/ledger.py`. Every command opens a run and closes it. A run records:
  - the loop (onboard, evolve, act, maintain) or the command;
  - the build, and the instant it moved from and to;
  - what woke it, counted by trigger;
  - the situations and goals it touched;
  - the cards it opened, updated and closed;
  - its model calls and their cost (each row of `notebook.runs` gets the run's id);
  - what it skipped and why;
  - its errors, and its status: ok, partial, failed or cap hit.
- `nb.cli status` shows the last runs.
- **Tests:**
  - a run with a fake model writes one complete row;
  - a run that hits the cap lists every skipped item;
  - a run that crashes is closed as failed, with the error.
- **Done when:** every command writes its row.

### P1-7 · Spend in order, never silently short
(Built before P1-4 because the loops spend through it.)
- **One cap for all processes.** Reservations live in the database, not in the process, so two runs at once can't both spend the last dollar.
- **Priority classes**, in this order:
  1. the founder acted;
  2. we owe something, or a date is today or passed;
  3. a goal is at risk or blocked;
  4. the nearest deadline;
  5. the stakes;
  6. the rest.
- **Before a run:** a dry-run estimate of calls and cost per phase.
- **At the cap:** stop, and list what was skipped, with the reason.
- **At most 10 subjects per sweep** (P4 07 §2.7): the rest are carried to the next sweep with a watermark and listed as skipped, never dropped.
- **A failed answer is retried once, with the error shown to the model.** It is never re-asked blindly.
- **Tests:**
  - a run with a tiny cap judges the top items and lists the rest as skipped;
  - two processes started together never pass the cap;
  - an answer that fails twice is held with its reason, not paid a third time.
- **Done when:** no run ever ends short without saying so.

### P1-4 · Evolve: wake-ups, then only the touched work

**4a · Wake-ups.** A new table, `notebook.wakeups`, and `nb/triggers.py`. They come from five sources:
1. **New evidence** since the last instant (mail, calendar, Screen):
   - evidence in a known thread wakes that thread's situation;
   - a new thread wakes "place".
2. **The date index:** each page's expected-by date, each open loop's due date, each stated deadline and each goal's due date. One fires when it crosses a rung since the last instant, in local days (P1-1). Each wake-up carries its `rung_kind` (a stated date reaching today; an expected-by date, set from the party's own reply pace at 5 or more instances, else the stage's prior; a stage past its normal length; a verify-by date; a calendar event's end instant, fired at minute grain rather than by local day), as P4 07 §2.1 maps them.
3. **A goal changed:** confirmed, edited, or its status moved. It wakes the goal's linked situations.
4. **The founder acted** (P1-5).
5. **The schedule** (P1-6).

Each wake-up has a key (build, subject, trigger, rung or evidence id), so it can fire only once. Wake-ups for one situation in one run become one judgment.

**4b · The runner.** `nb/loops.py`, `evolve(build, until)`. One run per step:
1. read the wake-ups;
2. place new threads, using `works.py`'s own functions (`update.py`'s older copy of the rules goes);
3. judge the touched situations, from their page plus what is new; then mark their dependents dirty (P2's `dependents()`) and re-run only those, to a fixed point with a cap of 3 rounds, writing a receipt on non-convergence (P2 §10.3);
4. write goal pages for the touched goals;
5. open, update or close cards;
6. close the run in the ledger.

The command `nb.cli update` stays, and calls the runner.

**Tests:**
- a day with no new mail and no date crossing makes **zero** model calls;
- a day with one new reply re-judges one situation and its goal;
- a deadline crossing "today" re-judges that situation with no new mail;
- the same rung never fires twice;
- an expected-by date from July that was already judged as passed does not fire again;
- a second full sweep is never run: only dirty dependents are re-judged, and a fixed point that does not converge in 3 rounds writes its receipt.

**Done when:** the replay (P1-8) passes, and each day costs under $0.50.

### P1-3 · Onboard: goal first, in waves
- **What:** one command, `nb.cli onboard`, that runs today's `all` in the goal-first order, in two waves (D-P1-10).
  - **Wave 1, the last 30 days:**
    1. evidence;
    2. recover archived text;
    3. company page (who we are, our addresses, our time zone);
    4. parties;
    5. situations;
    6. judge each live situation, ours first;
    7. relate (goals, links, code-found situations);
    8. **goal pages** (P4);
    9. **cards from pages and from goals' missing steps** (P5);
    10. reports.
  - **Wave 2, the rest of the window:**
    - place the older threads into the situations wave 1 found, or into new ones;
    - judge only the situations that history changes, and new live ones;
    - refine the goals;
    - update the cards.
- **Every phase is a checkpoint in the ledger.** A crash resumes at the phase it stopped in, and never pays twice for a judged situation.
- **A dry-run estimate comes first** (calls and cost per phase).
- **Depends on:** P2-1 (the goal object), P4-6 (goal reasoning), P5-1 (when a card is raised).
- **Tests:**
  - stop the process in the middle of judging, start it again: it resumes, and the cost of judged situations is not paid twice;
  - the dry-run estimate is within 20% of the real cost.
- **Done when:** a fresh build at the ideal's instant meets the first gate in [10](../10-ACCEPTANCE.md) §5 (same or close on at least 11 of 17, and no opposite call):
  - wave 1's cards include the ones that need the founder now (`f1` and `f2` at least);
  - reasoning costs under $10.

### P1-5 · Act comes back in
- **A1 · The founder's word:** Done, Later (until a date), Not now, an answer, an option chosen, a draft edited. Each becomes evidence on its situation (`notebook.actions`) and a wake-up.
- **A2 · Delegate to a person:** the card moves to that person, and the page records who now owns the move.
- **A3 · Delegate to an agent:**
  - the agent's draft is held for the founder's approval;
  - once approved, the send is recorded as *reported*;
  - it becomes *verified* only when the sent mail is seen in the evidence. Those are the check-in states.
- **Locally:** actions come from a private `answers.jsonl` or from `nb.cli act`. In the product they come from `card_events`, `decisions` and executions with their outcomes.
- **Tests:**
  - a recorded "submitted" on `f2` closes its card and moves the accelerator goal's plan step;
  - "Not now until a date" hides a card until that date, then wakes it;
  - an agent's send stays *reported* until the mail appears.
- **Done when:** the replay's act events are applied correctly.

### P1-6 · Maintain on a schedule
- **Daily** (02:00 company time):
  - a situation with no movement past its window goes dormant;
  - a card whose date passed with nothing owed by us closes;
  - check-in states are updated;
  - the date index is rebuilt and checked.
- **Weekly:** correlate and analyse (P2-5 and P4-7), over pages rather than mail, and on the batch API.
- Both are runs with ledger rows.
- **Test:** the stale July scheduling cards close, and no ideal card is lost.
- **Done when:** open cards are at most 30 (from 63), with every in-copy ideal card still present or correctly closed.

### P1-8 · The replay
- **What:** `nb.cli replay --from <instant> --to <instant> --step 1d`.
  - It copies a build to a new id and runs Evolve one day at a time, at 06:00 company time.
  - It writes a per-day report: wake-ups by trigger; situations and goals touched; cards opened, updated and closed; cost; and, beside them, what [10](../10-ACCEPTANCE.md) §3 says should have happened that day.
- **Done when:**
  - the 23 → 28 Oct replay handles every listed event on its day;
  - each day costs under $0.50;
  - a quiet day costs nothing.

### P1-9 · Two tenants at once
- **What:** two builds run as two tenants through the same runner at the same time, for example one at 23 Oct and one at 25 Oct. They share one worker pool and one cap, and each build runs one at a time.
- **Tests:**
  - no row of one build is read by the other (a check query on every table the runner touches);
  - each build's ledger accounts for every one of its calls;
  - the work interleaves: neither build waits for the other's whole run.
- **Done when:** both finish with the same results they get alone, and the shared cap holds.

### P1-10 · The onboarding drill
- **What:** on P1-3's own build, three disruptions:
  - a crash in the middle of each phase;
  - a restart during wave 2, the way a deploy restarts a process;
  - a cap hit in wave 2;
  - a second seat connecting a mailbox: its threads join the existing investor and hiring situations, an item only that seat holds stays private to the seat, and the company patterns gain n.

  It writes the onboarding report: time to first intelligence, time to everything judged, cost per phase, what was skipped.
- **Done when:** the targets in [06](06-NEW-CUSTOMER-ONBOARDING.md) §5 are met, with every disruption resumed and nothing paid twice.

---

## The relief track (today's product)

These change today's code. Owner: Harsh, with the agents Harsh assigns. Each goes live per tenant behind a row, and is measured before and after.

### R1 · Measure today's runs
- Write one row per tick and per chain into a `loop_runs` table: what woke it, its stages and their times (from `platform/stage_timer.py`, today log-only), counts, cost and errors. **No behaviour changes.**
- Set the build SHA at deploy, so `/health` names the running code (U13-42).
- **Done when:** a day of chains can be read from the table, not rebuilt from the funnel's write times.

### R2 · Take the whole-company passes off the per-mail chain
- **What:** move the whole-company refreshes inside `context/runner.process_pending` to the 6-hourly tick, per tenant, behind a row. These are the period, support, meeting and channel, outreach, document, spend, history and attention passes, and any other pass that reads the whole company; the exact list is read from the code. The per-event part stays on the chain.
- **Watch:** for 3 days, keep the old chain's cards and the new chain's cards side by side for this org.
- **Done when:**
  - the chain is under 30 minutes;
  - a new mail waits under 30 minutes;
  - the cards differ only in timing.
- **Risk:** the old lanes' readings refresh every 6 hours instead of every ~100 minutes. They are retired at the parity gate anyway.

### R3 · The company's time in every dossier
- Print the company's local time beside UTC in the expert and L2 dossiers (`reason/expert/dossier.py:194`), and count "today" in the company's day.
- **Test:** the same examples as P1-1.
- **Done when:** a golden case like `f1` is read in the right tense.

### R4 · The morning brief on its own schedule
- Compose the brief from its own job, at 08:00 company time, not at the tail of a sweep.
- Record each day's outcome: composed, or failed with its reason.
- Alert at 08:30 if there is none.
- **Done when:** 7 of 7 days, each within 15 minutes of 08:00.

### R5 · Stop paying twice for a bad answer
- Check R-9's answer shape as soon as it arrives.
- Retry once, at most, and show the model what failed.
- Record the failing field, so P4 can fix the prompt or the schema.
- **Done when:** under 10% of R-9's spend goes on discarded answers (today 39%).

### R6 · A runbook for onboarding a design partner (D-P1-9)
- **What:** one script and one page, extending `scripts/activate_tenant.py`. They:
  - switch the brain on (expert review, L2 reasoning, L2 cards);
  - switch the packs that fit a founder (Founder Office on; sales and support off unless the company sells or supports);
  - set the capture window (365 days) and the onboarding budget;
  - then watch the first day's health.
- **Done when:** a dry run on a test tenant completes with no step done by memory.

---

## Order and dependencies

```
notebook:  P1-1 clock ─┐
           P1-2 ledger ┼─► P1-7 budget ─► P1-4 evolve ─┬─► P1-5 act ─────┐
                       │                               ├─► P1-6 maintain ┼─► P1-8 replay ─► P1-9 two tenants
                       │   (P2-1, P4-6, P5-1) ─► P1-3 onboard ─► P1-10 drill
                                                       └─ P1-6 also needs P2-5, P4-7
product:   R1 measure ─► R2 relief ─► R4 brief ─► R5 retries        R3 clock (any time)      R6 runbook (after D-P1-9)
```

- P1-1, P1-2 and P1-7 cost almost nothing, and can be built first.
- R1 and R3 can start the same day, on the product.
- The rest of the notebook track waits for the parts it calls.

## How P1 lines up with the 28 Oct plan (GeniOS-013 [03](../03-HOW-IT-GETS-FIXED.md))

| P1 step | 28 Oct units it proves or replaces |
|---|---|
| P1-4 wake-ups, the date index | U13-22 (`work_clock`), U13-23 (priority bands) |
| P1-3 onboard | U13-28 (the onboarding pass), U13-38 (365 days), `07` D2 (onboarding budget), D3 (goal proposals) |
| P1-6 maintain | U13-24 (the stop rule instead of a default window) |
| R1 measure | U13-39 (health numbers), U13-42 (build SHA) |
| The cutover in [05](05-HOW-AT-PRODUCTION-LEVEL.md) §7 | U13-31 (only the work path delivers), `07` D5 |

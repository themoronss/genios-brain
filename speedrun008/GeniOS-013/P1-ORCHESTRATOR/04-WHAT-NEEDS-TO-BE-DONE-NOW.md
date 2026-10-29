# P1 · Orchestrator · 04 · What needs to be done now

Everything here is proved in the **notebook first** (local, on the copy). [05](05-HOW-AT-PRODUCTION-LEVEL.md) says how the same thing goes into the product. A step is done only when:
- its tests pass;
- its done-when number is met;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing got worse.

---

## Decisions for Rohit

| # | Question | Recommendation | Why |
|---|---|---|---|
| D-P1-1 | **When does Evolve run?** | Once a day at a fixed local time (06:00 company time), plus on demand. Per signal later, in the product | A day forward costs cents. The founder reads intelligence in the morning. A batch is easier to check |
| D-P1-2 | **What wakes a situation or a goal?** | Five triggers: new evidence; a date crossing a rung (7 days, 1 day, today, passed) for a stated deadline or an expected-by date; a goal changed; the founder acted; the Maintain schedule | These cover the 13 of 20 ideal cards that are about something that did not happen |
| D-P1-3 | **How much may it spend?** | Onboarding up to $10 for a company this size; Evolve under $0.50 a day; Maintain under $1 a week. Over the cap: work in priority order and list what was skipped | `b2` cost $8.41 to onboard. A day touches a handful of situations |
| D-P1-4 | **Which model?** | Keep the production model (claude-sonnet-5, thinking off) for parity. Run the acceptance set once on a stronger model, to know the ceiling | Cost parity with production; a measured ceiling before any upgrade |
| D-P1-5 | **Whose clock?** | The company's time zone (from its record), shown beside UTC wherever a time is printed | `f1` failed on UTC alone |
| D-P1-6 | **In what order inside a run?** | Goal first: evidence → place → situations → goals → cards | Cards that come from a goal's missing step (`f3`, `i1`) need the goal before the card |

## Steps

### P1-1 · One clock
- **What:** every time a model is shown (dossier header, system prompt, the times of meetings and mails, expected-by dates) is printed in the company's time zone with UTC beside it. "Today" means the company's today.
- **Test:** 2026-10-23 01:40 UTC prints as "Fri 23 Oct, 07:10 IST (01:40 UTC)". A meeting at 05:00 UTC prints as "10:30 IST, later today".
- **Done when:** `f1` is re-judged as "join the panel at the time, with one number" (same or close to the ideal, in the right tense), and nothing else in the acceptance set gets worse.
- **Cost:** one situation re-judged, about $0.02.

### P1-2 · A record of every run
- **What:** every command writes one row to a run ledger. It holds:
  - the loop and the build;
  - the instant it ran from and to;
  - the triggers it found;
  - the situations and goals it touched;
  - the cards it opened, updated and closed;
  - its model calls and their cost;
  - what it skipped and why, and its errors.
- **Test:** a run with a fake model writes one complete row; a run that hits the cap lists every skipped item.
- **Done when:** every command writes its row, and `nb.cli status` shows the last runs.

### P1-3 · Onboard as one command, goal first
- **What:** today's `all`, reordered:
  1. evidence;
  2. recover archived text;
  3. company page;
  4. parties;
  5. situations;
  6. judge each situation;
  7. relate (goals, links, code-found situations);
  8. **goal pages** (P4);
  9. **cards from pages and from goals' missing steps** (P5);
  10. reports.

  Each step writes its run record (P1-2).
- **Depends on:** P2-1 (goal object), P4-6 (goal reasoning), P5-1 (when a card is raised).
- **Done when:** a fresh build at the ideal's instant meets the targets set for this stage in [10](../10-ACCEPTANCE.md) §5. The first gate is same-or-close on at least 11 of 17 and zero opposite calls.

### P1-4 · Evolve, one day at a time
- **What:** rebuild `update.py` on `works.py`'s own functions, so there is one copy of the grouping rules. Each run:
  - takes the new mail, calendar and Screen since the last instant;
  - places each new thread into its situation, a new situation, or noise. The placing step is shown the open situations **and goals** and asked which one each thread touches;
  - fires the date triggers from stored dates (D-P1-2);
  - re-judges only the touched situations, then only the touched goals;
  - opens, updates or closes cards.
- **Test:**
  - a day with no new mail and no date crossing makes zero model calls;
  - a day with one new reply re-judges one situation and its goal;
  - a deadline crossing "today" re-judges that situation without any new mail.
- **Done when:** the replay (P1-8) handles every event in [10](../10-ACCEPTANCE.md) §3 on the right day, and each day costs under $0.50.

### P1-5 · Act comes back in
- **What:** the founder's actions become evidence on their situation and wake it up:
  - Done, Later, Not now, an answer, an option chosen, a draft edited, a delegation.
  - Locally they come from an answers file or a command. In the product they come from `card_events` and executions with their outcomes.
- **Test:** a recorded "submitted" on `f2` closes its card and moves the accelerator goal's plan step; a "not now" hides a card until its date.
- **Done when:** the six act-type events of the replay are applied correctly.

### P1-6 · Maintain on a schedule
- **What:**
  - **daily lifecycle:** situations with no movement past their window go dormant; a card whose date passed with nothing owed by us closes; check-in states are updated;
  - **weekly:** correlate and analyse (P2-5 and P4-7).

  Both are commands that write run records.
- **Test:** the stale July scheduling cards close; no ideal card is lost.
- **Done when:** open cards are at most 30 (from 63), with every in-copy ideal card still present or correctly closed.

### P1-7 · Spend in order, never silently short
- **What:** before a run, a dry-run estimate. Under the cap, work in this order:
  1. situations where we owe something;
  2. goals at risk or blocked;
  3. the nearest deadline;
  4. the stakes.

  Over the cap, stop and list what was skipped. Budgets are read from the ledger at each call, so two runs at once can't both spend the last dollar.
- **Test:** a run with a tiny cap judges the top items and lists the rest as skipped, with the reason.
- **Done when:** no run ever ends short without saying so.

### P1-8 · The replay
- **What:** `replay --from <instant> --to <instant> --step 1d` copies a build, runs Evolve day by day, and writes a per-day report: what changed, what was expected (§3 of [10](../10-ACCEPTANCE.md)), and the cost.
- **Done when:** the 23 → 28 Oct replay handles every listed event on its day.

## Order and dependencies

```
P1-1 clock ─┐
P1-2 ledger ┼─► P1-3 onboard (needs P2-1, P4-6, P5-1) ─► P1-4 evolve ─► P1-8 replay
P1-7 budget ┘                                          └► P1-5 act ─────┘
                                                       └► P1-6 maintain (needs P2-5, P4-7)
```

P1-1, P1-2 and P1-7 can be built first; they cost almost nothing. The rest wait for the parts they call.

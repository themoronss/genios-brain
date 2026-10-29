# P1 · Orchestrator · 03 · What's expected, and what's happening

**Expected** comes from Rohit's own words:
- the launch film (26 Oct);
- Rohit's 29 Oct description of the loops:
  - "new customer → data → notebook → business situation → goals → intelligence";
  - "new data → questioning from the angle of the business situations and goals → notebook update → … → cards";
  - "notebook → correlate, analyse, lifecycle → business situation → goals update → cards";
- GeniOS-009 and 010.

**Happening** is measured ([01](01-WHATS-EXACTLY-THERE.md)): the product on the design partner's first week, 22–28 Oct, and the notebook on build `b2`.

| # | Expected | Happening in the product | Happening in the notebook |
|---|---|---|---|
| 1 | **Proactive.** "You're not checking dashboards, not tagging anything, and not prompting more and more" | Sweeps run every 15 min, and L2 thinks only when mail arrives | A person runs commands |
| 2 | **"Exactly as my company's data evolves"**: new data is read through the situations and goals already known | Every chain redoes the whole company (68 of its 97 min), and the judge re-reads the whole file. Nothing it concluded is kept | A situation is re-read from its last saved page plus only the new mail. Goals are not yet used to question the new data |
| 3 | **What didn't happen is noticed**: a reply that should have come, a follow-up never sent | 138 of 138 L2 runs came from new mail; 0 of 47 expert triggers were a date or a silence | An overdue expected-by date makes a card for every date, including stale ones from July |
| 4 | **New data shows up fast** | A new mail waits 2.5 h (median) before L2 has read it; its card comes at the end of the next chain | Not run as a loop yet |
| 5 | **"Every department, every goal, every situation"**: goals are where the work is organised | Goals sync from accepted brief lines only. 7 proposed, 0 confirmed, 0 cards linked | Goals are formed after the pages, and cards don't come from goals |
| 6 | **One reading per situation, one piece of intelligence about it** | Three card makers; a subject repeats up to 9 times | One card per situation, but 63 cards against the ideal's 20 |
| 7 | **Onboarding gives useful intelligence on day one** | "Ready" after 3 h 39 min, with 14 old-lane cards and 3 files reviewed by the brain. A first look at every file would take over three weeks at the daily budget | `all` runs in about 40 min for $8.41 and judges all 378 situations |
| 8 | **A new customer gets GeniOS without anyone flipping switches** | A new tenant gets the old rule packs and no brain; this org's brain was switched on by hand | One build, everything on |
| 9 | **Delegate to a person or an agent, and every Done teaches** | Card actions, executions and outcomes are stored, but not read back into situations or goals. 105 tracked commitments, 0 completed | Not represented |
| 10 | **Maintain:** correlate, analyse, decay and prioritise, as routine | 18 upkeep jobs every 6 h, all on the old graph | Not represented; the card flood shows it |
| 11 | **The company's own time** ("today 11:30" means today, 11:30, there) | Dossiers say "UTC" only. The morning brief does use the time zone, but it was missing one day and 5.5 h late another | UTC only; the `f1` card was wrong because of it |
| 12 | **Spend goes where it matters** | A $2-a-day wall for the judge, hit every day. 39% of its spend was thrown away on answers that failed their check | Ours first, then newest. The cap is summed over all builds |
| 13 | **What ran, and why, can be seen** | Records per layer, not per run. Stage times are in the log only. `/health` says "dev" | Every model call logged; no record of a whole run |
| 14 | **A day forward costs little** | About $5.70 a day after onboarding | Not run yet. The target is under $0.50 a day for reasoning |
| 15 | **More customers don't slow anyone down** | One tenant keeps the reasoning busy almost all day (chains back to back) | One build at a time |

## Where the notebook already matches what's expected

1. **Pages instead of re-reading.** A situation is re-judged from its saved page plus the new mail only: a median dossier of 4,800 characters against the product's 70,000. This is what makes a loop affordable.
2. **The as-of discipline.** A build knows its instant. Nothing after it is read, including meetings the copy hadn't seen yet. A replay can therefore be honest, day by day.
3. **Ours first.** When the budget is short, the situations where we wrote, or where something was asked, are judged first.
4. **One gateway for the model.** Every call is priced, capped, logged and attributable.

## Where the product already has what's needed

1. **Capture on time.** The light tick polls each source on its own cadence. Gmail was read every 15.5 min (median) all week.
2. **Durable first pull.** The sync job checkpoints, heart-beats and resumes after a crash or a deploy.
3. **Single flight per org.** A lease means two runs never work one org at once. A run that finds the org busy queues a trigger instead of losing it.
4. **Switches are rows, per tenant**, not global flags.
5. **Daily health per tenant**, with alerts.

These nine stay. The plan in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md) builds the loops on them.

## What "done" means for P1

| Measure | Today | Target |
|---|---|---|
| Replay 23 → 28 Oct: each event moves the right situation, goal and card on its day ([10](../10-ACCEPTANCE.md) §3) | not run | all |
| A day with no new mail and no date crossing | not measured | 0 model calls |
| Reasoning cost of one Evolve day | not run | under $0.50 |
| Onboarding a founder-size company (reasoning only, once) | $8.41, about 40 min (notebook) | under $10 for six months ($15 for 365 days). First intelligence within 2 h of connect, everything judged within 24 h |
| A month of reasoning after onboarding | about $113 (product, reasoning and cards) | under about $20 |
| New mail on a live situation → its page and card updated | 2.5 h wait, then a 97-min chain (product) | 90% within 30 min (product) |
| A date crossing (7 days, 1 day, today, passed) → that situation judged | never | within 2 h |
| The morning view at 08:00 company time | missing 1 day in 7, late another | every day, within 15 min |
| A run without a ledger row | every run | none |
| A new tenant that needs a switch flipped by hand | all of them | none |
| Two tenants at once | not run | neither waits longer because of the other; caps hold; nothing crosses between them |

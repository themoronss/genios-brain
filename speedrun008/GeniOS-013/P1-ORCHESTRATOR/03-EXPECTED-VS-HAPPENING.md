# P1 · Orchestrator · 03 · What's expected, and what's happening

**Expected** comes from Rohit's own words:
- the launch film (26 Oct);
- Rohit's 29 Oct description of the loops:
  - "new customer → data → notebook → business situation → goals → intelligence";
  - "new data → questioning from the angle of the business situations and goals → notebook update → … → cards";
  - "notebook → correlate, analyse, lifecycle → business situation → goals update → cards";
- GeniOS-009 and 010.

**Happening** is measured ([01](01-WHATS-EXACTLY-THERE.md)): the product on the design partner's first week, 22–28 Oct, and the notebook on build `b2`, measured again on 30 Oct. The target for each row is specified in [07](07-THE-ORCHESTRATOR-SPEC.md).

| # | Expected | Happening in the product | Happening in the notebook |
|---|---|---|---|
| 1 | **Proactive.** "You're not checking dashboards, not tagging anything, and not prompting more and more" | Sweeps run every 15 min; a chain starts on new mail or on the 6-hour tick, and nothing records why | A person runs commands |
| 2 | **"Exactly as my company's data evolves"**: new data is read through the situations and goals already known | Every chain redoes the whole company (69 of its 97 min, the same with or without new mail), the judge re-reads the whole file (about 11,000 characters), and L2's watermark has not moved since 22 Oct, so every chain re-reads all 286 subjects. Nothing it concluded is kept | A situation is re-read from its last saved page plus only the new mail. Goals are not yet used to question the new data |
| 3 | **What didn't happen is noticed**: a reply that should have come, a follow-up never sent | 0 date wakes in the week: 0 of 47 expert triggers were a date or a silence; 42 dated signals came due and none woke a judgment; L2's relabel of the date triggers is broken | An overdue expected-by date makes a card for every date, including stale ones from July; 23 of 63 cards come from dates alone |
| 4 | **New data shows up fast** | A new mail is read by L2 36–54 min after capture, and its chain ends 123–140 min after capture (medians); every card is born between 07:00 and 13:59 IST, because the judge's budget is spent in one burst after 00:00 UTC | Not run as a loop yet |
| 5 | **"Every department, every goal, every situation"**: goals are where the work is organised | Goals sync from accepted brief lines only, and are in no fingerprint. 11 proposed, 0 confirmed, 0 cards linked | The company page proposes goals and the judge sees them, but the card is decided before the goals are revised, and no card comes from a goal |
| 6 | **One reading per situation, one piece of intelligence about it** | Three card makers; a subject repeats up to 9 times | One card per situation, but 63 cards against the ideal's 20 |
| 7 | **Onboarding gives useful intelligence on day one** | The first 14 cards (old lanes) at 1 h 46 min; "Ready" at 3 h 39 min through the busy path, with 0 expert reviews and 0 goals. A first look at every file takes weeks at the daily budget | `b2`: $8.41, about 17 min of model time, all 378 situations judged (built by separate commands; `all` has no resume) |
| 8 | **A new customer gets GeniOS without anyone flipping switches** | A new tenant gets the old rule packs and no brain; this org's brain was switched on by hand | One build, everything on |
| 9 | **Delegate to a person or an agent, and every Done teaches** | Card actions are declared no trigger; an act waits for the next chain. 3 card actions in the week, all on 22 Oct; 105 executions, 0 completed | Not represented |
| 10 | **Maintain:** correlate, analyse, decay and prioritise, as routine | About 20 upkeep jobs every 6 h from process start, all on the old graph, none with its own record; the six patterns fired 0 times in 408 evaluations | Not represented; the card flood shows it |
| 11 | **The company's own time** ("today 11:30" means today, 11:30, there) | Dossiers say "UTC" only; the caps roll at 05:30 IST; the support clock uses UTC working hours (718 situations). The brief uses the zone, but was missing one day, 5.5 h late another, and late by a cut tick on three | UTC only, the date arithmetic too; the `f1` card was wrong because of it |
| 12 | **Spend goes where it matters** | A $2-a-day wall for the judge, in UTC days, spent in one morning burst. 39% of its spend was thrown away on answers that failed their check. Nothing orders spend across sites | Ours first, then newest. The cap is read once per process, so two runs don't see each other |
| 13 | **What ran, and why, can be seen** | Records per layer, not per run; every run labelled `bundle`. Stage times are in the log only. `/health` says "dev". Health rows on 2 of 7 days | Every model call logged; no record of a whole run |
| 14 | **A day forward costs little** | About $5.70 a day after onboarding | Not run yet. The target is under $0.50 a day for reasoning |
| 15 | **More customers don't slow anyone down** | One tenant keeps the reasoning busy 82% of the week (chains back to back) | One build at a time; one org by construction |
| 16 | **A switch does what it says** | The kill switches don't bind the background threads; a cut tick keeps running beside the next; the per-org cap stops the pull but not the chain; the parity gate's code has no caller | No switches |
| 17 | **A day can be replayed** | Only synthetic golden cases replay | `update` moves a build in place and has never run on a real build |

## Where the notebook already matches what's expected

1. **Pages instead of re-reading.** A situation is re-judged from its saved page plus the new mail only: a median dossier of 4,800 characters against the product's 11,000 (mean of a paid judgment). This is what makes a loop affordable.
2. **The as-of discipline.** A build knows its instant. Nothing after it is read, including meetings the copy hadn't seen yet. A replay can therefore be honest, day by day.
3. **Ours first.** When the budget is short, the situations where we wrote, or where something was asked, are judged first.
4. **One gateway for the model.** Every call is priced, capped, logged and attributable.

## Where the product already has what's needed

1. **Capture on time.** The light tick polls each source on its own cadence. Gmail was read every 15.5 min (median) all week.
2. **Durable first pull.** The sync job checkpoints, heart-beats and resumes after a crash or a deploy.
3. **Single flight per org.** A lease means two runs never work one org at once. A run that finds the org busy queues a trigger instead of losing it.
4. **Switches are rows, per tenant**, not global flags.
5. **Daily health per tenant**, with alerts.

These stay. The plan in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md) builds the loops on them.

## What "done" means for P1

| Measure | Today | Target |
|---|---|---|
| Replay 23 Oct → 2 Nov: each event moves the right situation, goal and card on its day ([10](../10-ACCEPTANCE.md) §3), the clock-only events included | not run | all |
| A day with no new mail and no date crossing | not measured | 0 model calls |
| Reasoning cost of one Evolve day | not run | under $0.50 |
| Onboarding a founder-size company (reasoning only, once) | $8.41, about 17 min of model time (notebook) | under $10 for six months ($15 for 365 days). First intelligence within 2 h of connect, everything judged within 24 h |
| A month of reasoning after onboarding | about $113 (product, reasoning and cards) | under about $20 |
| New mail on a live situation → its page and card updated | the chain it rides ends 123–140 min after capture (product) | 90% within 30 min of arrival (product) |
| A timed rung (a surface time, an event's end) | never | fired within 2 min of its instant |
| A date crossing (7 days, 1 day, today, passed) → that situation judged | never | within 2 h |
| The morning view at 08:00 company time | missing 1 day in 7, late another | every day, within 15 min |
| A run without a ledger row | every run | none |
| A new tenant that needs a switch flipped by hand | all of them | none |
| A switch whose claim disagrees with what ran | not checked | none, checked daily |
| Two tenants at once | not run | neither waits longer because of the other; caps hold; nothing crosses between them |

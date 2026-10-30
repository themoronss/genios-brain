# P1 · Orchestrator · 02 · What's failing, and why

Each failure lists its evidence, its cause, and whose it is. "Us" means the AI sessions that built the product and the notebook under Rohit's direction. None of these comes from a misunderstanding by Rohit.

F1–F8 were written on 29 Oct morning and F9–F15 that afternoon. On 30 Oct all of them were measured again, and F16–F23 were added; corrections to the earlier numbers are marked. The numbers are in [01](01-WHATS-EXACTLY-THERE.md).

---

## F1 · Three reasoning paths run in one sweep, so there are three card makers

**Evidence:**
- `reason/runner.run_all` runs, one after the other: the expert pass, the L2 pass, the compiled lane, one run per active pack, and narration (`reason/runner.py:1943-2157`).
- The first week's 111 cards came from the L2 path (33), the compiled lane (36), the legacy lane (41) and the team emitter (1). One subject carries up to 9 cards.
- The old lanes are about 29% of the week's model spend.

**Cause:** each programme step added a new pass beside the old one, and planned to retire the old one later. The old ones were never retired (STEP-12 added the expert pass; GeniOS-008 added the L2 pass; the legacy lanes were never switched off for this tenant).

**Whose:** us, through architecture and process. It is a strangler migration that was never finished.

## F2 · GeniOS wakes up when mail arrives, not when something should have happened

**Evidence:**
- **0 date wakes in the week.** Of 47 recorded expert triggers: 43 first look, 2 new evidence, 2 past normal (both together with new evidence). 42 dated signals came due in the week; none woke a judgment.
- **The date triggers that exist can't reach L2 correctly.** L2 relabels the expert's triggers by substring (`reason/l2/sweep.py:198-204`): `reply_overdue` becomes `deadline_crossed`, `date_closing_in` becomes `bundle`, and `expected_reply_absent` can never be produced.
- **13 of the 20** ideal cards are about something that did *not* happen: an evaluator who went quiet, a question left unanswered, a follow-up never sent, a referral that never came.
- *Correction (30 Oct):* "138 of 138 L2 runs were started by new mail" was too strong. Every row says `bundle` because that is the only value written; 28 of 67 chains read no new event and still ran 67 of the 138 requests, as carry-over after the budget's daily roll. What woke a run is simply not recorded.

**Cause:**
- The expert pass computes its date rungs only when a chain happens to run, by diffing against its last review; 35 of 50 reviews had no date at all and 14 a date already passed, so there was no rung left to cross.
- No stored expected-by date exists to wake a page (P2), and no index of "what is due when" exists (P1).

**Whose:** us, through design. The L2 pass was built new-evidence-first, and the clock was left for later.

## F3 · Re-reading everything makes it expensive, so it is capped and most work is never judged

**Evidence:**
- A paid judgment reads about **11,000 characters** (mean of the 86 results; max 35,000). *Correction (30 Oct):* the 29 Oct figure of 70,000 was a mean over all 138 rows, driven by one oversized file refused 31 times.
- R-9's budget of $2 a day allows about 12 paid consults a day.
- 80 subjects have ever been judged by L2 (48 files and 32 seeds; *correction:* not "80 of 264 files").
- 16 of 20 re-judgments came with no new mail in between.

**Cause:** nothing the brain concludes is saved (P2 F1). So the Orchestrator has no small "page plus what changed" to send; it can only send the whole file again.

**Whose:** us, through architecture: the Intelligence Graph was never built. The Orchestrator inherits the problem.

## F4 · Switches that report success while nothing happens

**Evidence:**
- `reason/cutover.py` lists the cutover switches as data; its parity functions have no production caller, and its measured-at date is still empty.
- `runner.py` records that `l3_activation` once had **no reader**: "`POST /v1/admin/l3/activate` wrote a row, the console showed the tenant as on … and the sweep ran a SHADOW pass that published nothing."
- **The kill switches don't bind the background** (30 Oct): `kill_switch_all` is read only by API requests; a per-org kill switch stops the sweep's pull and chain but not the warm lane, the sync worker or the heavy tick's upkeep; `GENIOS_SCHEDULER_ENABLED=false` leaves three threads running; the per-org daily cap stops the pull but not the chain.

**Cause:** every step added its own switch, and nothing lists the switches together or checks them against what actually ran.

**Whose:** us, through process.

## F5 · The four loops don't exist as loops

**Evidence:**
- **Onboard:** no first-day pass understands the company. Goals come only from accepted brief lines, and none are accepted (11 proposed, 0 confirmed).
- **Evolve:** only the L2 pass's new-bundle step and the expert pass's triggers. No step places new evidence into a business situation.
- **Act:** what the founder does is stored, but nothing wakes the situation: card actions are declared no trigger; 3 card actions in the week, all on 22 Oct; 105 executions, 0 completed; 0 rows in `decisions`.
- **Maintain:** about 20 upkeep jobs on the 6-hour tick, all on the old graph. The six cross-situation patterns were evaluated 408 times and fired 0 times.

**Cause:** the sweep was designed around signals → situations → cards. The loops are newer requirements (GeniOS-009 and 013, and Rohit's 29 Oct message) with no runner yet.

**Whose:** unfinished work.

## F6 · The clock is UTC, almost everywhere

**Evidence:**
- **The notebook:** `b2`'s judge was told "the mailbox was read through 2026-10-23 01:40 UTC". It read a panel slot of 11:30–12:00 as happening now; in fact 01:40 UTC is 07:10 in India, so the panel was four hours away, and the card said "Confirm whether you attended the panel today" (`f1`). The date arithmetic is UTC too: a date passes at 23:59:59 UTC, which is 05:29:59 IST the next day (`nb/checks.py:109-110`).
- **The product:** both dossiers print "as of … UTC" (`reason/expert/dossier.py:194`); the daily caps and site budgets roll at 00:00 UTC (05:30 IST); the daily health day is UTC; all 718 support "first response overdue" situations use UTC working hours, 09:00–18:00 UTC, which is 14:30–23:30 IST. Only the brief, quiet hours, the Screen promoter and meeting-day reads use the company's zone.
- The zone is empty at signup and inferred from send hours on the 6-hour tick; weekends are a constant and holidays an empty set.

**Cause:** no company-clock object exists; each site reads the zone, or not, on its own.

**Whose:** **mine** for the notebook's judge (29 Oct); us for the product.

## F7 · The notebook has no runner, only commands

**Evidence:**
- Every phase is run by hand. `all` has no resume: running it again repays the company page, the parties and the situations, and overwrites the title, kind and status of works already judged.
- `update.py` keeps its own older copy of the grouping rules (four differences, confirmed 30 Oct), moves a build in place with no copy, and reads no meeting, party, goal, founder act or Maintain step.
- The cap reads the all-build spend once, when a run starts, and keeps reservations in memory, so two runs at once don't see each other. Nothing keeps two commands off one build.

**Cause:** the notebook was built phase by phase to prove the page-per-situation idea, not yet to run as a loop.

**Whose:** **mine**, and known: it is the next step by design.

## F8 · The notebook decides a card before its goal is revised, and never from a goal

**Evidence:** *correction (30 Oct):* the 29 Oct wording, "a card is decided before its goal exists", was half wrong. The company page proposes goals before any work is judged (15 in `b2`), and the judge sees them. What stands:
- the card is decided inside each judgment, before `relate` forms and revises the goals;
- `nb/cards.py` never reads a goal, so no card comes from a goal's missing step;
- 23 of `b2`'s 63 cards were raised from a date alone.

Two ideal cards were missed this way: `f3` (a referral silent for 24 days) and `i1` (one update carrying the new milestone).

**Cause:** the page-first order of GeniOS-013 Step 2, with goals added as a later phase.

**Whose:** **mine**, from design. The loop order in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md) fixes it.

---

## F9 · Every chain redoes the whole company, so one tenant fills the day

**Evidence (67 chains, 22–28 Oct):**
- A chain takes **97 min** (median; p90 123). 69 of those minutes are `context/runner.process_pending`'s org-wide passes: period, support, meeting and channel touches, outreach, documents, spend and history, attention, situation refresh and lifecycle. Chains with no new L2 event spend the same 69 min as chains with about 22.
- `run_all` has a 26-minute floor with no paid call; each paid judgment adds about 2.5 min, one after another.
- The org's reasoning was busy 82% of the week's wall time; 47 of 66 chains began within 3 minutes of the last one's end.
- A new mail is read by L2 36–54 min after capture, and the chain it rides ends 123–140 min after capture (medians). *Correction (30 Oct):* the 29 Oct "147 min" was the warm lane's wait for Screen sessions, not for mail.
- The database is over its ceiling: 570 MB against 472 MB on 27 Oct. Every chain rewrites the whole-company readings, and the purges chase them.

**Cause:**
- The design rule in `process_pending` is "a period read that is only refreshed by a separate schedule is a period read that is always stale", so every whole-company reading is refreshed on every call.
- The Orchestrator has no difference between "new evidence on a few situations", which should be quick and small, and "upkeep of the whole company", which can be nightly.

**Whose:** us, through architecture.

**Why it matters for new customers:** chains for different tenants run one after another in one sweep thread, with one warm-lane slot for the whole platform. A second tenant of this size would roughly double everyone's wait. This is an estimate: no multi-tenant run has been measured.

## F10 · A new customer would not get the brain

**Evidence** (`platform/intelligence_onboarding.NOT_DEFAULT_ON`, `packs/wiring.py:30-31`, the domains' `domain.yaml`):
- **Off for a new tenant:** expert review, L2 reasoning, L2 cards, the brief's writer, card copy, calibration apply, cards from situations.
- **On for a new tenant:** L1 semantic, L2 analytic and patterns, the Admin domain, five L4 defaults, and the sales, general, admin and customer-support rule packs.
- **Domains:** only Admin is `default_on`. Founder Office is off, though it is the founder's own domain.
- **This org** had expert review, L2 reasoning, L2 cards and Founder Office switched on by hand on 21 Oct, and sales and support disabled by hand on 3 Oct.

**What a new founder would get today:** old sales and support rule cards on a founder's mailbox, a template brief, and no judgment.

**Cause:** each brain feature was built as "off until a person has looked at a live run". That was right for a first tenant. No onboarding step was ever written that arms the brain for the next ones.

**Whose:** us, through process.

## F11 · The brain's budget is a daily wall in UTC, and a third of it is wasted

**Evidence:**
- R-9 (the L2 judge) spent $1.88–1.96 every UTC day, always in one burst right after 00:00 UTC (06:47–13:10 IST), then refused the rest of the day: 95 refusals, 38 results carried as "over budget".
- **So every card after 23 Oct was born between 07:00 and 13:59 IST.** A mail at 15:00 IST waits for the next day's burst.
- **$5.28 of R-9's $13.55 (39%)** went on 30 answers that failed validation and 6 that were cut off. A failed answer is retried at full price; R-2 narration threw away 70%.
- Onboarding has no budget of its own. At about 12 consults a day, a first look at every file takes weeks.

**Cause:**
- The budget's day is UTC (`reason/bundle/budget.py:238`) and it is spent first-come first-served from the start of that day.
- It was sized for an ordinary day, not for a first week.
- An answer's shape is checked only after it is paid for.

**Whose:** us, through design. GeniOS-013 [07](../07-DECISIONS.md) D2 already proposes a one-time onboarding budget.

## F12 · Work at a local hour slips, and nobody is told

**Evidence:**
- 6 morning briefs in 7 local days: 23 Oct 08:00, **24 Oct none**, 25 Oct 13:31, 26 Oct 08:24, 27 and 28 Oct 08:36 IST.
- The 26–28 Oct delays are cut ticks (F19). 24 and 25 Oct are not explained by any slow sweep, and nothing records why.
- All 6 were written by the template (the writer is off, F10), yet each stored "why" says a Haiku draft and a Sonnet escalation failed. Neither ran.
- On 3 of 5 days the brief came 20–90 min before that day's first card, so it could not mention it.

**Cause:** the brief is composed at the tail of a sweep. Whatever delays the sweep delays the brief, and nothing checks afterwards that it went out.

**Whose:** us, through design. The false "why" text is the brief's own (P5's part); the missing schedule is P1's.

## F13 · Nobody can see what a whole run did

**Evidence:**
- Stage times go to the log only (`platform/stage_timer.py`). The chain times in [01](01-WHATS-EXACTLY-THERE.md) were rebuilt from the funnel's write times.
- No record per run of what woke it, which situations it touched, what it cost or what it skipped. Subjects past the pass cap of 10 get no row at all.
- `/health` reports `build_sha: "dev"`. The daily health row exists for 2 of 7 days, and its funnel column sums the day's chains.

**Cause:** records were added per layer (`l1_sync_runs`, `pipeline_counters`, receipts, `daily_health`), never per run.

**Whose:** us, through process.

## F14 · The brain lives inside the web server

**Evidence:**
- One process (`Procfile`: `web: uvicorn …`) serves the API and runs the scheduler, the sync-job worker, the warm lane and the Screen promoter as daemon threads.
- A deploy restarts all of them: a durable sync job resumes from its checkpoint; a chain in flight is lost, and its events wait for the next heavy tick (up to 6 h) because the next light tick sees nothing newly emitted.
- The 6-hour tick is counted from process start, so it drifts with every restart. The pod changed once in the week.

**Cause:** the no-broker rule ("no Celery or Upstash") was met with threads in the API process. That was simple and right for one tenant. It has no room for many.

**Whose:** us, through architecture.

## F15 · Onboarding says "Ready" before GeniOS understands anything

**Evidence:** on 22 Oct the progress screen reached "Ready" 3 h 39 min after connect. By then the old lanes had made 14 cards (at 1 h 46 min, from a scheduler chain started mid-backfill), the brain had reviewed **0** files (*correction:* not 3), and no goal had been proposed. "Ready" came through the busy path: the job waited 900 s for the org's lease, then wrote "Finishing in the background" (`api/routes.py:3864-3881`). The first goal proposals and the first brief review came on days 5 and 6.

**Cause:**
- "Ready" means "the job finished", not "GeniOS understood something".
- Onboarding has no step that builds the company page, the situations and the goals first. It reuses the incremental chain with a bigger backlog.

**Whose:** us, through design (GeniOS-013 Step 5, "cold start", is the planned fix).

---

## F16 · The pass reads everything every time, even when it decides nothing

**Evidence (30 Oct):**
- The L2 watermark has never moved past the first bundle of 22 Oct. So every chain re-reads all 534 bundles and 286 subjects and relies on the fingerprint to say "unchanged".
- One oversized file, refused 31 times at the per-call ceiling, sits in the pass every time, takes one of its 10 slots, never gets judged, and holds the watermark.
- The expert pass reads every file each chain to compute its fingerprint (180 files).

**Cause:** the change gate runs after the read, and a failed subject pins the watermark instead of being parked.

**Whose:** us, through code (P4's pass; P1 owns what is handed to it).

## F17 · A tick that runs long is abandoned, but keeps running

**Evidence:** a tick is cut off after 20 min (`platform/scheduler.py:110-118`), but its thread is not stopped: the loop sleeps 15 min and starts the next tick while the old one runs on, chain and brief included. 16 of 526 Gmail gaps are 33–36 min (20 + 15), 13 of them right after a chain start; these explain the brief's 24–36 min delays on 26–28 Oct.

**Cause:** a timeout without cancellation, in a process with no queue.

**Whose:** us, through code.

## F18 · Spend has no order across the run, and a skip leaves no trace

**Evidence:**
- Each model site has its own daily pool. Nothing orders spend across sites, so the old lanes' narration and decisions spend while the judge is refused.
- Inside a pass, subjects past the cap of 10 are only counted in a log line and in a receipt the chain does not keep.
- The 95 budget refusals and the 38 "over budget" results are rows nobody reads.

**Cause:** budgets were added per site as each site was built.

**Whose:** us, through design.

## F19 · Nothing records why a run started, so lateness can't be explained

**Evidence:** the trigger is the constant `bundle` (L2) or `event` (runs). 11 of 66 chains started with no event captured since the previous start, and the cause (the heavy tick, a deferred trigger, or carry-over) is not recorded. A card's lateness can't be split into capture, wake, judgment or delivery, because no timing stamps exist on a page or a card.

**Cause:** no run ledger (F13), and no named wake-ups.

**Whose:** us, through process.

## F20 · Founder acts and results don't come back in

**Evidence:**
- A card action is declared no trigger (`reason/expert/triggers.py:25-30`). An answer, a correction or a "wrong" verdict reaches the expert fingerprint and waits for the next chain.
- `founder_asked` cannot fire: both callers omit it (`reason/expert/sweep.py:287`).
- An agent's result wakes only the realtime outbox.
- The 3 cards the founder took on 22 Oct are still `acted`, with no close.

**Cause:** the Act loop was never built (F5); the old path treated an action as the end of a card.

**Whose:** us, through design.

## F21 · Onboarding reads in one wave, under one lease, with the chain

**Evidence:** during the backfill the whole chain runs every 6 rounds of pages and once at the end of each source, each time repeating every org-wide pass. The job's own last pass waited 15 min for the lease held by a scheduler chain, then gave up and said "Ready". The window (180 days here) is read newest first in one go; nothing useful is shown until a chain happens to finish.

**Cause:** onboarding reuses the incremental chain (F15) and shares its lease.

**Whose:** us, through design.

## F22 · The notebook's cap is not one cap

**Evidence:** each process reads the spend of all builds once at start and reserves in memory; two runs at once can each spend the same remaining amount. A worst-case reservation is 9.5 times the real cost of a judgment, so a run near its cap refuses work long before it has spent it. A timed-out call is counted as $0, though the provider may have billed it.

**Cause:** the gateway was built for one command at a time.

**Whose:** **mine**, known (P1-7 fixes it).

## F23 · The notebook can't replay time

**Evidence:** `update` moves a build in place, so a replay from `b2` would destroy the snapshot the scorecard compares against. Saved times are wall clock (`judged_at`, card times, version times), so "the page as of day D" can't be read back. Nothing steps through the minute-grain moments a day holds (`f1`'s 11:10 popup, its 12:05 follow-up). `update` has never run on a real build.

**Cause:** the replay was planned (P1-8) and not yet built.

**Whose:** **mine**, known.

---

## Summary: whose fault

| Failure | Whose | Kind |
|---|---|---|
| F1 three paths | us | architecture: an unfinished migration |
| F2 new mail only | us | design |
| F3 re-read and cap | us | architecture (P2's missing notebook) |
| F4 switches | us | process |
| F5 no loops | unfinished | planned, not built |
| F6 UTC almost everywhere | me (notebook) and us (product) | code |
| F7 no runner | me (notebook) | not built yet |
| F8 card decided before goals, never from them | me (notebook) | design order |
| F9 whole company every chain | us | architecture |
| F10 new tenants get no brain | us | process |
| F11 UTC budget wall and waste | us | design |
| F12 local-hour work slips | us | design |
| F13 no run record | us | process |
| F14 inside the web server | us | architecture |
| F15 "Ready" too early | us | design |
| F16 the pass reads everything | us | code (P4's pass) |
| F17 abandoned ticks keep running | us | code |
| F18 no order across spend | us | design |
| F19 no wake cause | us | process |
| F20 acts don't come back | us | design |
| F21 onboarding in one wave | us | design |
| F22 the notebook's cap | me (notebook) | not built yet |
| F23 no replay | me (notebook) | not built yet |

# P1 · Orchestrator · 02 · What's failing, and why

Each failure lists its evidence, its cause, and whose it is. "Us" means the AI sessions that built the product and the notebook under Rohit's direction. None of these comes from a misunderstanding by Rohit.

F1–F8 were written on 29 Oct morning. F9–F15 come from the deeper measurement of 22–28 Oct in [01](01-WHATS-EXACTLY-THERE.md).

---

## F1 · Three reasoning paths run in one sweep, so there are three card makers

**Evidence:**
- `reason/runner.run_all` runs, one after the other:
  - the expert pass;
  - the L2 pass;
  - the domain compiler;
  - the legacy pack lanes.
- The live cards come from three makers: 38 from old signal rules, 33 from old situation rules, and 31 from the brain.
- The same subject repeats up to 9 times.

**Cause:** each programme step added a new pass beside the old one, and planned to retire the old one later. The old ones were never retired.
- STEP-12 added the expert pass.
- GeniOS-008 added the L2 pass, in shadow.
- The legacy lanes were never switched off for this tenant.

**Whose:** us, through architecture and process. It is a strangler migration that was never finished.

## F2 · GeniOS wakes up when mail arrives, not when something should have happened

**Evidence:**
- **138 of 138** L2 runs were started by new mail.
- Of the 47 recorded expert triggers, 43 were "first look", 2 "new evidence" and 2 "past normal". **None was a date or a silence.**
- Yet **13 of the 20** ideal cards are about something that did *not* happen. Four examples:
  - an evaluator who went quiet;
  - a question left unanswered;
  - a follow-up never sent;
  - a referral that never came.

**Cause:**
- The L2 pass's request step (R1) reads only "bundles stored since this pass's watermark".
- No stored expected-by date exists to wake it (see P2), so a silence can't be noticed.
- `deadline_crossed` and `expected_reply_absent` exist as constants in `contracts/reasoning_result.py`. Nothing produces them except a relabelling of the expert's own triggers.

**Whose:** us, through design. The L2 pass was built new-evidence-first, and the clock was left for later.

## F3 · Re-reading everything makes it expensive, so it is capped and most work is never judged

**Evidence:**
- Every judgment re-reads about 70,000 characters (up to 280,000).
- R-9's budget of $2 a day allows about 12 judgments a day.
- Only 80 of 264 files have ever been judged.
- 16 of 20 re-judgments came with no new mail.

**Cause:** nothing the brain concludes is saved (P2 F1). So the Orchestrator has no small "page plus what changed" to send; it can only send the whole file again.

**Whose:** us, through architecture: the Intelligence Graph was never built. The Orchestrator inherits the problem.

## F4 · Switches that report success while nothing happens

**Evidence:**
- `reason/cutover.py` lists seven switches.
- `runner.py` records that `l3_activation` once had **no reader**: "`POST /v1/admin/l3/activate` wrote a row, the console showed the tenant as on … and the sweep ran a SHADOW pass that published nothing."
- The activation of the L1 to L3 seam was a global boolean "set in no environment".

**Cause:** every step added its own switch, and nothing lists the switches together or checks them against what actually ran.

**Whose:** us, through process.

## F5 · The four loops don't exist as loops

**Evidence:**
- **Onboard:** there is no first-day pass that understands the company. Goals come only from accepted brief lines (`sync_from_brief`), and none are accepted (7 proposed, 0 approved).
- **Evolve:** there is only the L2 R1 step (new bundles) and the expert pass's triggers. No step places new evidence into a business situation.
- **Act:** what the founder does is stored, but nothing reads it back into the situations or goals:
  - card actions: 3 in the first week;
  - executions: 105 tracked commitments, of which 50 pending, 35 expired, 20 cancelled and **none completed**;
  - decisions: 0 rows in `decisions`.
- **Maintain:** there are 18 upkeep jobs on the 6-hour tick, but all of them look after the old graph. None correlates, analyses or decays the conclusions, because no conclusions are kept.

**Cause:** the sweep was designed around signals → situations → cards. The loops are newer requirements (GeniOS-009 and 013, and Rohit's 29 Oct message) with no runner yet.

**Whose:** unfinished work.

## F6 · The clock is UTC-only, in the notebook and in the product

**Evidence:**
- **The notebook:** in build `b2`, the model was told "the mailbox was read through 2026-10-23 01:40 UTC".
  - It read a panel slot of "11:30–12:00" as happening now.
  - In fact 01:40 UTC is 07:10 in India, so the panel was four hours away.
  - The resulting card said "Confirm whether you attended the panel today" (`f1`).
- **The product:** the expert dossier states its instant as "as of YYYY-MM-DD HH:MM UTC" (`reason/expert/dossier.py:194`), and the L2 judgment reads that dossier whole.
  - The org's time zone, `Asia/Kolkata`, is in `orgs.timezone`, but no dossier prints it.

**Cause:** neither judge was ever given the company's time. Only the delivery side (quiet hours, the morning brief) reads the time zone.

**Whose:**
- **mine** for the notebook's judge (29 Oct);
- us for the product.

## F7 · The notebook has no runner, only commands

**Evidence:**
- Every phase is run by hand (`nb.cli all`, then single phases).
- `update.py` keeps its own older copy of the grouping rules. The works agent listed four on 29 Oct:
  - `org_key` clustering;
  - the old archived-noise rule;
  - the channel rule weighted by count only;
  - `thread:<id>` singletons.
- Each process keeps its own budget reservations, so two runs at once don't see each other's.

**Cause:** the notebook was built phase by phase to prove the page-per-situation idea, not yet to run as a loop.

**Whose:** **mine**, and known: it is the next step by design.

## F8 · The notebook's order makes cards before goals

**Evidence:** `all` runs judge (each page decides its own card), then relate (goals formed, links made), then judge again (only the merged and linked situations), then cards. So:
- a card is decided before its goal exists;
- no card comes from a goal's missing step.

Two ideal cards were missed this way:
- `f3`: a referral silent for 24 days;
- `i1`: one update carrying the new milestone.

**Cause:** the page-first order of GeniOS-013 Step 2, with goals added as a later phase.

**Whose:** **mine**, from design. The loop order in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md) fixes it.

---

## F9 · Every chain redoes the whole company, so one tenant fills the day

**Evidence (68 chains, 22–28 Oct):**
- A chain takes **97 min** (median; 90th percentile 122). 68 of those minutes are the L2 rule pass, `context/runner.process_pending`.
  - That pass refreshes, for the whole company: period situations, support situations, meeting and channel touches, outreach state, the document register, contract spend, histories, attention, situation states and resolutions.
  - A chain that came with no new signal at all still spent 71 min there (26 Oct, 02:19 UTC).
- A new chain starts about every 100 min. So the reasoning of this **one** tenant runs back to back almost all day.
- A new mail waits **2.5 h** (median; 90th percentile 3.3 h) before L2 has processed it. Its card comes at the end of the chain after that.
- The database is over its ceiling: 570 MB against 472 MB on 27 Oct. Every chain rewrites the whole-company readings, and the purges chase them.

**Cause:**
- The design rule in `process_pending` is "a period read that is only refreshed by a separate schedule is a period read that is always stale". So every whole-company reading is refreshed on every call.
- The Orchestrator has no difference between:
  - "new evidence on a few situations", which should be quick and small;
  - "upkeep of the whole company", which can be nightly.

**Whose:** us, through architecture.

**Why it matters for new customers:**
- Chains for different tenants run one after another inside a tick, with one warm-lane slot for the whole platform.
- A second tenant of this size would roughly double everyone's wait. A tenth would make "proactive" meaningless.
- This is an estimate: no multi-tenant run has been measured. But it follows directly from the measured 97-minute chain and the code's one-at-a-time lanes.

## F10 · A new customer would not get the brain

**Evidence** (`platform/intelligence_onboarding.NOT_DEFAULT_ON`, `packs/wiring.DEFAULT_PACKS`, `Domain Expertise/*/domain.yaml`):
- **Off for a new tenant:** expert review, L2 reasoning, L2 cards, the morning brief's writer and card copy. Each is "armed per tenant" by a person.
- **On for a new tenant:** the sales, general, admin and customer-support rule packs, all active.
- **Domains:** only Admin is `default_on`. Founder Office is off, though it is the founder's own domain.
- **This org** had expert review, L2 reasoning, L2 cards and Founder Office switched on by hand on 21 Oct. Its sales and support packs were disabled by hand on 3 Oct.

**What a new founder would get today:** old sales and support rule cards on a founder's mailbox, a template brief, and no judgment.

**Cause:**
- Each brain feature was built as "off until a person has looked at a live run". That was right for a first tenant.
- No onboarding step was ever written that arms the brain for the next ones.

**Whose:** us, through process.

## F11 · The brain's budget is a daily wall, and a third of it is wasted

**Evidence:**
- R-9 (the L2 judge) has $2 a day of its own, and it hit that every day from 22 to 28 Oct.
  - 95 calls were refused for budget.
  - 38 results were carried as "over budget".
- **$5.28 of R-9's $13.55 (39%)** was spent on 30 answers that failed validation and 6 that were cut off. They were paid for and thrown away.
- Onboarding has no budget of its own. At about 11 judgments a day, a first look at 264 files takes over three weeks.

**Cause:**
- The budget was sized for an ordinary day, not for a first week.
- A failed answer is retried at full price, because the answer's shape is checked only after it is paid for.

**Whose:** us, through design. GeniOS-013 [07](../07-DECISIONS.md) D2 already proposes a one-time onboarding budget.

## F12 · Work at a local hour slips, and nobody is told

**Evidence:**
- 6 morning briefs in 7 days. **None on 24 Oct. 25 Oct's came at 13:31 IST**, five and a half hours late.
- All 6 were written by the template (the writer is off, F10).
- The compose step counts its failures, but only in the sweep's return value and the log. No table records why a brief is missing.

**Cause:** the brief is composed at the tail of a sweep, after the chain loop. Whatever delays or breaks the sweep delays or drops the brief, and nothing checks afterwards that it went out.

**Whose:** us, through design.

## F13 · Nobody can see what a whole run did

**Evidence:**
- Stage times are written to the log only (`platform/stage_timer.py`). The chain times in [01](01-WHATS-EXACTLY-THERE.md) had to be rebuilt from the funnel's write times.
- There is no record per run of:
  - what woke it;
  - which situations it touched;
  - what it cost;
  - what it skipped.
- `/health` reports `build_sha: "dev"`, so nobody can say which code ran.

**Cause:** records were added per layer (`l1_sync_runs`, `pipeline_counters`, receipts, `daily_health`), never per run.

**Whose:** us, through process.

## F14 · The brain lives inside the web server

**Evidence:**
- One process (`Procfile`: `web: uvicorn …`) serves the API and runs the scheduler, the sync-job worker, the warm lane and the screen promoter as threads.
- A deploy restarts all of them:
  - a durable sync job resumes from its checkpoint;
  - a chain in flight is lost and starts again from the top.
- A tick that passes 20 minutes is abandoned and keeps running in the background while the next tick starts. Under load, several old ticks can run at once on one database pool, which is shared by the session pooler's 15 clients.

**Cause:** the no-broker rule ("no Celery or Upstash") was met with threads in the API process. That was simple and right for one tenant. It has no room for many.

**Whose:** us, through architecture.

## F15 · Onboarding says "Ready" before GeniOS understands anything

**Evidence:** on 22 Oct the progress screen reached "Ready" 3 h 39 min after connect. By then:
- the old lanes had made 14 cards;
- the brain had reviewed 3 files;
- no goal had been proposed.

The first goal proposals and the first brief review came on days 5 and 6.

**Cause:**
- "Ready" means "the old chain ran once".
- Onboarding has no step that builds the company page, the situations and the goals first. It reuses the incremental chain with a bigger backlog.

**Whose:** us, through design (GeniOS-013 Step 5, "cold start", is the planned fix).

---

## Summary: whose fault

| Failure | Whose | Kind |
|---|---|---|
| F1 three paths | us | architecture: an unfinished migration |
| F2 new mail only | us | design |
| F3 re-read and cap | us | architecture (P2's missing notebook) |
| F4 switches | us | process |
| F5 no loops | unfinished | planned, not built |
| F6 UTC only | me (notebook) and us (product) | code |
| F7 no runner | me (notebook) | not built yet |
| F8 cards before goals | me (notebook) | design order |
| F9 whole company every chain | us | architecture |
| F10 new tenants get no brain | us | process |
| F11 budget wall and waste | us | design |
| F12 local-hour work slips | us | design |
| F13 no run record | us | process |
| F14 inside the web server | us | architecture |
| F15 "Ready" too early | us | design |

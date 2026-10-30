# P1 · Orchestrator · 01 · What's exactly there

**What this file answers:** what exists today for what runs when, in the product and in the notebook, measured, with file paths. [02](02-WHATS-FAILING-AND-WHY.md) says what fails and why; [07](07-THE-ORCHESTRATOR-SPEC.md) is the target.

**The part:** what runs, when, for which business situation or goal, in what order, at what cost. That covers the four loops (Onboard, Evolve, Act, Maintain), the wake-ups and the date index, the company's clock, the budget and its order, the record of each run, the switches, the worker process, health, and many tenants at once. The Orchestrator never judges anything (P4 does), never stores a conclusion (P2 does), never authors knowledge (P3 does) and never words or ranks a card (P5 does).

**Read at:** product code `a729b968` (29 Oct), the code production runs. The notebook is the local prototype (`Local Database (Rohit_Org_GV2)/notebook/nb/`). **Measured on:** the local copy of the design partner's org, cut from production on 28 Oct at 12:45 UTC. Production restarted this org from empty on 21 Oct and captured its mailbox again on 22 Oct, so **22–28 Oct is a measured first week of a new tenant**. The notebook is measured on build `b2` (as of 23 Oct, 01:40 UTC). Every number has its query in the measurement notes (private; no names).

**Status key:** ✅ works · 🟡 partly · ❌ broken · ⬜ not built.

**Corrections to the 29 Oct version of this file,** each measured again on 30 Oct (details in the sections below):
- "A new mail waits 147 min for L2" was the wait of Screen sessions in the warm lane, not of mail. A new mail is read by L2 about **36–54 min** after capture (median, two counts), and the chain it rides ends about **123–140 min** after capture.
- "138 of 138 L2 runs were started by new mail" overstates it: the trigger field holds the constant `bundle` on every row. 28 of 67 chains read no new event at all and still ran 67 of the 138 requests (carry-over after the budget's daily roll). 138 is request rows: 86 got a result, 38 were refused for budget with no model call.
- A paid judgment re-reads about **11,000 characters** (mean of the 86 results; max 35,000), not 70,000. The 70,000 is a mean over all 138 rows, driven up by one oversized file refused 31 times.
- "80 of 264 files judged" mixed two units: the 80 L2 subjects are 48 files and 32 seeds.
- At "Ready" the brain had reviewed **0** files, not 3 (the first review came at 20:34 UTC, after Ready). "Ready" came through the busy path, after a 15-minute wait for the org's lease.
- "$25.44 on the onboarding day" includes $3.66 spent before the reconnect; from connect to "Ready" it was $17.55.
- The notebook judges a page in about **8 seconds** of model time (379 calls in 7.7 min at 8 at once), not 30 seconds; onboarding's judging is about 51 worker-minutes, not 200.

---

## 1 · Every function of the Orchestrator, and whether it works (product)

### 1.1 · Getting data in on time

L1 does the capture. The Orchestrator only decides when it runs.

| Function | Where | Status | Measured, 22–28 Oct |
|---|---|---|---|
| Pull new mail and calendar on a schedule | `platform/scheduler.py`: a light tick every 15 min polls only the sources that are due (`capture/acquire/cadence.py:75-91`: Gmail 15 min, Calendar 1 h, Drive 1 h, HubSpot 2 h, Notion 12 h, default 6 h), oldest-due first | ✅ | Gmail polled every 15.5 min (median; p90 16.4; longest gap 41 min). Calendar every 61.6 min. 3 Gmail pulls failed in 656 incremental runs; 54 of 656 runs brought anything new |
| Real-time push (a new mail reaches reasoning in about 2 min) | Composio webhook → `platform/warm_lane.py` | ⬜ not in use | No mail row in the warm lane all week. Push is registered only by an operator script (`scripts/composio_triggers.py --apply`); nothing in the engine registers it at connect. The warm lane carried 611 Screen sessions and 16 deferred chain calls, which waited a median 148 min for the org's lease |
| First pull at connect (the backfill) | OAuth adoption → `sync_jobs` → `platform/sync_worker.py` → `_onboarding_sync_bg`. Heart-beats every 30 s, checkpoints per page, resumes after a crash | ✅ | 22 Oct: 2,240 mails captured in 2 h 18 min (16 a minute) and 136 calendar events in 45 s. The first attempt failed (cause not recorded) and the job resumed (`attempts = 2`) |
| Stop pulling for a paused org, a lapsed plan, a spent day or a full plan quota | `run_sync_sweep`: `_org_paused`, `_plan_expired`, `_llm_over_daily_cap`, `_sync_headroom` | 🟡 | The per-org cap ($25 and 20,000 calls a UTC day) stops only the pull, a sync-job start and a re-read; an over-cap org is still chained (`api/routes.py:1297-1300`) |
| Notice a revoked login and mark the connection | `_connection_still_valid` | ✅ in code | Not exercised this week |

### 1.2 · Waking the brain up (triggers)

| Function | Where | Status | Measured |
|---|---|---|---|
| Reason when new data arrives | A light tick chains an org only when its sources landed something new (`chain_only_on_new_data`). The heavy tick (every 6 h, counted from process start) chains every org with no such check | 🟡 | 67 chains after connect. 41 of 66 started with no new qualified signal; 11 with no event of any kind captured since the previous start |
| Record why a run started | `reasoning_results.trigger`; `reasoning_runs.trigger_kind` | ❌ | The trigger is the constant `bundle` on all 138 L2 rows and `event` on all 153 reasoning runs. Nothing records why a chain started |
| Give every situation a first look | Expert pass trigger `first_look` | 🟡 | 43 first looks in the week. The expert pass reads every file each chain to compute its fingerprint (180 files with a non-private event) |
| Reason when a date comes close or passes, or a reply doesn't come | Expert triggers `date_closing_in`, `reply_overdue`, `past_normal`; L2's `deadline_crossed` and `expected_reply_absent` (constants in `contracts/reasoning_result.py`) | ❌ | 0 date wakes in the week. Of 47 recorded expert triggers: 43 first look, 2 new evidence, 2 past normal (both with new evidence). Of the 50 reviews' inputs, 35 had no date at all and 14 a date already passed. L2's relabel of the expert triggers is broken (`reason/l2/sweep.py:198-204`): `reply_overdue` becomes `deadline_crossed`, `date_closing_in` becomes `bundle`, and `expected_reply_absent` can never be produced |
| Dates that do move something | The legacy `commitment_overdue` rule; execution deadlines on the heavy tick | 🟡 | 27 overdue signals on 23–26 Oct, for old backfilled commitments (median 2,169 h past due). 35 executions expired 40–85 min after their deadline, at the next pass. 42 dated signals came due in the week; none woke a judgment |
| Reason when a goal changes | Goals sync from accepted brief lines at the start of `run_all` | ⬜ | Goals are not in any fingerprint (`reason/l2/sweep.py:112-130`). 11 goals proposed, 0 confirmed |
| Reason when the founder acts, or an agent or execution ends | Card actions are declared no trigger (`reason/expert/triggers.py:25-30`). An answer, a correction or a "wrong" verdict enters the expert fingerprint and is seen by the next chain. An agent's result wakes only the realtime outbox | ⬜ | 3 founder actions in the week, all "I'll do it myself" within 2.5 min on 22 Oct; their cards stay `acted`. `founder_asked` cannot fire: both callers omit it (`reason/expert/sweep.py:287`). 105 executions: 50 pending, 35 expired, 20 cancelled, **0 completed**; 0 rows in `decisions` |
| Do things at a local hour (the morning brief at 08:00 company time) | `_compose_due_briefs` at the tail of each sweep (`api/routes.py:1110-1124`); `executive/morning.py` | 🟡 | 6 briefs in 7 local days: 23 Oct 08:00, **24 Oct none**, 25 Oct 13:31, 26 Oct 08:24, 27 and 28 Oct 08:36 IST. The 26–28 Oct delays are cut ticks (§1.4); 24 and 25 Oct are not explained. All 6 written by template with 0 model calls, yet each stored "why" says a Haiku draft and a Sonnet escalation failed, which never happened. On 3 of 5 days the brief was composed 20–90 min before the day's first card |

### 1.3 · Choosing what to work on, and in what order

| Function | Where | Status | Measured |
|---|---|---|---|
| Skip what hasn't changed | Fingerprints: `reason/change_gate.py`, the expert and L2 passes | 🟡 | The gate runs after the read: every subject is still read and fingerprinted each chain. The L2 watermark has never moved past the first bundle of 22 Oct (`post_pass_watermarks`), so every chain re-reads all 534 bundles and 286 subjects and relies on the fingerprint. One oversized file, refused 31 times, holds the watermark. `change_gate.SWEEP_EVERY` assumes a 6-hour beat; chains run about every 100 min |
| Most important first | Expert pass: nearest deadline first, 10 a pass. L2 pass: files before seeds, then a deadline within a week, then newest evidence, then importance; 10 a pass (`reason/l2/sweep.py:80-100`) | 🟡 | Neither ranks "we owe something" or "a goal is at risk". Subjects past the cap of 10 get no row; they are counted only in a log line and in a receipt the chain does not keep |
| One run per org at a time; fair across orgs | `org_run_leases` (120 s lease, 30 s beat); capture oldest-due first | ✅ capture · 🟡 reasoning | Reasoning runs org after org inside one sweep thread; the warm lane has one global slot. Only one tenant is in the data, so fairness cannot be measured |

### 1.4 · Running the work

| Function | Where | Status | Measured |
|---|---|---|---|
| Redo only what changed | The chain (`api/routes._run_l2_chain`): `context/runner.process_pending`, then `reason/runner.run_all`, then cards | ❌ | **A chain takes 97 min** (median; p90 123; longest 150). **69 min of it is `process_pending`'s whole-company passes**, the same 69 min with no new L2 event (28 chains) as with about 22. `run_all` has a floor of 26 min with no paid model call; each paid judgment adds about 2.5 min, because judgments run one after another (`reason/l2/sweep.py:390-401`). Building cards takes 10 s |
| A new mail's path to a card | — | ❌ | Captured 1.6 min after it arrives (median). Read by L2 36–54 min after capture (median, two counts; p90 about 90). The chain it rides ends 123–140 min after capture (p90 about 185). Mail to a card on the same subject can be traced for 1 of 89 mails only |
| When cards appear | — | 🟡 | Every card after 23 Oct was born between 07:00 and 13:59 IST, because the judge's budget is spent in one morning burst (§1.5). Only 14 of 66 chains delivered a card |
| One path, so one card per situation | `reason/runner.run_all`: goals from the brief → expert pass → L2 pass → compiled lane → one run per pack → narration (`reason/runner.py:1943-2157`) | ❌ | Three card makers ([02](02-WHATS-FAILING-AND-WHY.md) F1) |
| Goals before cards | Goals synced from accepted brief lines at the start of `run_all` | ❌ | No brief line is accepted, so no goal reaches a pass |
| Survive a crash or a deploy | Sync jobs checkpoint and resume; leases expire in 120 s; warm-lane rows retry with back-off and park after 5 failures | 🟡 | A tick is cut off after 20 min, but its thread keeps running (`platform/scheduler.py:110-118`): 16 of 526 Gmail gaps are 33–36 min (20 + 15), 13 of them right after a chain start. A chain started by a tick has no durable record: a deploy mid-chain loses it, and its events wait for the next heavy tick (up to 6 h) |

### 1.5 · Money

| Function | Where | Status | Measured |
|---|---|---|---|
| Caps per tenant and per model site | `_llm_over_daily_cap` ($25 and 20,000 calls a day, per org); `reason/bundle/budget.py` per site: the L2 judge R-9 $2 a day and $0.25 a call; R-7 $2; narration R-2 $2; the brief writers $0.25; card copy R-10 $0.50 | 🟡 | Each site has its own pool; nothing orders spend across sites. The cap's day is a **UTC day** (`budget.py:238`), so it rolls at 05:30 IST |
| Spend in priority order, and say what was skipped | R-9's gate | 🟡 | R-9 spent $1.88–1.96 every UTC day, always in one burst after the 00:00 UTC roll (06:47–13:10 IST), then refused the rest of the day: 95 refusals in the week (58 daily budget, 37 per-call ceiling), 38 results carried as "over budget". They are counted; nobody sees them |
| Don't pay for answers that are thrown away | The gate allows 2 attempts, both priced (`reason/bundle/gate.py:298-391`) | ❌ | Of R-9's $13.55, **$5.28 (39%)** went on 30 answers that failed validation and 6 that were cut off. R-2 narration threw away 70%. Across all L4 sites, $7.09 of $16.13 (44%) |
| What a tenant costs | `llm_costs`, priced by `platform/metrics.cost_usd_sql` | measured | **$17.55 from connect to "Ready"** ($13.43 L1 reading the backfilled mail), $27.78 in the first 24 h. **$5.67 a day after that** (23–27 Oct; $4.34–6.86): $1.88 reading the data and $3.78 reasoning and cards, about $170 a month. The old lanes are about 29% of spend |

### 1.6 · Knowing what ran

| Function | Where | Status | Measured |
|---|---|---|---|
| A record per capture run | `l1_sync_runs` | ✅ | 676 rows |
| A count per chain | `pipeline_counters` (the five stage counts) | 🟡 | 68 sweeps. Counts per stage, not per run; a user's Sync pass writes none; `signals_detected` survives on 26 of 68 |
| A record of a whole run: what woke it, what it touched, what it cost, what it skipped | — Stage times go to the log only (`platform/stage_timer.py`) | ⬜ | The chain times above were rebuilt from the counters' write times |
| Daily health per tenant, with alerts | `platform/daily_health.py`, after a heavy tick; alerts through one webhook (`GENIOS_OPS_ALERT_WEBHOOK`, empty by default: log only) | 🟡 | 2 rows in 7 days (26 and 27 Oct), both alerting "database over its ceiling": 544 MB, then 570 MB, against 472 MB. Its funnel column sums the day's chains, so a day reads 16,126 situations formed for an org with about 1,400. Not alerted: chain length, queue age, a missing brief, a spent site budget |
| Which code is running | `/health` | ❌ | `build_sha: "dev"`: nothing sets `GENIOS_BUILD_SHA` at build or deploy |

### 1.7 · Switches and a new customer

| Function | Where | Status | Measured |
|---|---|---|---|
| Per-tenant switches as rows | `l1_semantic_activation`, `l2_v2_activation`, `l3_activation`, `l4_activation`, `tenant_packs`, kill switches | 🟡 | The rows work. But the kill switches do not bind the background threads: `kill_switch_all` is read only by API requests; a per-org kill switch stops the sweep's pull and chain but not the warm lane, the sync worker or the heavy tick's upkeep; `GENIOS_SCHEDULER_ENABLED=false` leaves three threads running |
| A new tenant gets the brain | `platform/intelligence_onboarding.make_tenant_live`, at the start of every chain | ❌ | See §4: the old rule packs and no brain |
| One list of switches, checked against what ran | `reason/cutover.py` lists the L2 cutover switches | ⬜ | Data only: its parity functions have no production caller (`reason/reasoning_health.py` lists them as unreached); `PARITY_MEASURED_AT` is still empty |
| An honest onboarding progress screen | `onboarding_progress`: connecting → emails → calendar → processing → graph → intelligence | ❌ | "Ready" at 3 h 39 min, after the job waited 900 s for the org's lease and wrote "Finishing in the background" (`api/routes.py:3864-3881`). It overwrites its start time on resume, so the row alone says 15 min |
| Goals at onboarding | The weekly brief review; L2's goal proposals | 🟡 | The first brief review ran on day 5 (27 Oct); L2 proposed 11 goals on 27–28 Oct. None confirmed |

## 2 · How a day runs in the product today

All of it runs inside **one API process** (`Procfile`: `web: uvicorn …`, no workers), on four daemon threads started at boot: the scheduler, the sync-job worker, the warm lane and the Screen promoter.

```
every 15 min   pull the due sources ─► new events for the org? ─► THE CHAIN (≈97 min) ─► morning briefs due
                                                                  ├─ provision, switch-on, re-read unread mail
                                                                  ├─ process_pending: every org-wide pass .... ≈69 min
                                                                  │    (period, support, meeting and channel,
                                                                  │     outreach, documents, spend and history,
                                                                  │     attention, situation refresh and lifecycle)
                                                                  ├─ reason/runner.run_all ..................... ≈27 min
                                                                  │    goals from the brief → expert pass → L2 judge
                                                                  │    → compiled lane → one run per pack → narration
                                                                  └─ cards, post-passes, purge ................. ≈10 s
every 6 h      from process start: the same pull, a chain for EVERY org, then about 20 upkeep jobs in series:
               card lifecycle · retention purges · billing · naming · parked, attachment and recapture drains ·
               seats · time-zone inference · the executive sweep · distribution · weekly calibration (shadow) ·
               weekly learning · weekly brief review · graph upkeep; then the daily health row
any time       a user's Sync → a durable job (backfill → drain → run_all → cards)
```

**What the numbers say** (67 chains, 22–28 Oct):

| | Median | 90th percentile |
|---|---|---|
| Chain, start to cards | 97 min | 123 min |
| of which `process_pending` | 69 min | 73 min |
| of which `run_all` and cards | 27 min | 50 min |
| Time between chain starts | 100 min | 171 min |
| Share of the week the org's reasoning was busy | 82% of wall time | — |

47 of 66 chains began within 3 minutes of the previous one's end. The chain time is the same every day, with or without new mail: it is the shape of the chain, not its load.

## 3 · Onboarding as built

The full path is in [06](06-NEW-CUSTOMER-ONBOARDING.md). On 22 Oct (UTC):

| Time | What happened |
|---|---|
| 15:31:23 | Connect: the sync job is queued |
| 15:32:10 | The first mail captured |
| 15:44:13 | A scheduler chain starts during the backfill (94 min) |
| 16:41 | The first judge results (10) |
| **17:17:24** | **The first 14 cards (1 h 46 min after connect),** from the old lanes |
| 17:50:33 | The last mail of the backfill (2,240 in 2 h 18 min) |
| 18:55–19:10 | The job's own pass waits 900 s for the org's lease, then marks "Ready" with "Finishing in the background" |
| 19:10:16 | **"Ready", 3 h 39 min after connect:** 14 cards, 0 expert reviews, 0 goals |
| 20:34 | The first expert review |

The window was the founder's pick (60 days by default; this org chose 180), capped at about 5,000 messages per source. During a backfill the whole chain runs every 6 rounds of pages and once at the end of each source.

## 4 · What a new tenant gets switched on, and what this org has

`make_tenant_live` runs at the start of every chain and switches a tenant on, unless a row already says otherwise.

| Switch | A new tenant, automatically | This org |
|---|---|---|
| L1 semantic lane; L2 analytic and patterns | on | on (system, 21 Oct 16:38) |
| Domains (L3) | Admin only (`default_on: true`). Founder Office, Sales and Support off | Admin (system); Founder Office **by hand**, 21 Oct 17:28 |
| Rule packs | sales, general, admin, customer_support, all **active** (`packs/wiring.py:30-31`) | admin, founder_office, general active; sales and customer_support disabled by hand (3 Oct) |
| L4: roster v2, ranking v2, bundle, critique, brief | on | on (system) |
| L4: **expert review, L2 reasoning, L2 cards** | **off** (`NOT_DEFAULT_ON`: "a bill a tenant never agreed to"; L2 cards "a cutover") | **on, by hand,** 21 Oct 17:28 |
| L4: the brief's writer, card copy, calibration apply, cards from situations | off | off |

**So today a new founder would get** sales and support rule cards on a founder's mailbox, a template brief, and **no judgment**. Everything this org sees from the brain was switched on by hand (`scripts/activate_tenant.py`, whose default features are only roster v2 and ranking v2).

## 5 · The clock

| Where | Clock | Effect |
|---|---|---|
| The morning brief's hour, quiet hours, the Screen promoter's day, meeting-day reads, resolving "Friday" | the company's zone (`orgs.timezone`) | right |
| The daily caps and the site budgets (`date_trunc('day', now())` in a UTC session), the over-budget carry, the L2 fingerprint's date rungs, the daily health day, both dossiers ("as of … UTC") | **UTC** | the judge's day starts at 05:30 IST; "today" in a dossier is UTC's |
| The support clock: all 718 `first_response_overdue` situations | **UTC working hours** (`ResponsePolicy` default offset 0, Mon–Fri 09:00–18:00) | the working window is 14:30–23:30 IST; every stored overdue figure is a UTC computation |
| The org's zone itself | inferred from send hours on the heavy tick; empty at signup | read in several places; no company-clock object |
| Weekends and holidays | weekends a constant (Sat, Sun); holidays an empty set | nothing supplies a calendar |

## 6 · Maintain as built

- **About 20 upkeep jobs** run in series in one thread on the heavy tick (`api/routes.py:1335-1725`). None writes a record of its own; each failure is only logged.
- **Lapses, dormancy and archiving run on every chain**, inside `process_pending`, over the whole company: situations go dormant at 45 days and archived at 180. Today: 1,164 active, 282 dormant, 80 resolved.
- **The six cross-situation patterns** were evaluated 408 times (6 × 68 chains, at chain start) and fired **0** times.
- **Weekly learning** ran twice and **calibration** 7 times, all in shadow, muting nothing.
- **The fixed-point guard** is a whole-company state hash compared across sweeps (`context/runner.py:466-550`), not a set of dirty situations.

## 7 · In the notebook (the local prototype)

| Piece | File | What it does |
|---|---|---|
| Commands | `nb/cli.py` | `init`, `status`, `evidence`, `recover`, `company`, `parties`, `works`, `judge`, `relate`, `cards`, `export`, `scorecard`, `compare`, `update`, `all` |
| A build | `nb/config.BuildSettings` | One instant (`as_of`), one model, one cap, an optional dry run. The first writing command records the instant and the model; a different one is refused |
| Order of `all` | `cli.run_all` (`nb/cli.py:117-135`, pinned by a test) | evidence → recover archived text → company page → parties → situations → judge each one → relate (goals, links, merges, two code-built situations) → judge again → cards → reports. **No resume:** running `all` again repays the company page, the parties and the situations, and overwrites the title, kind and status of works already judged (`nb/works.py:481-486`) |
| Safe to repeat | — | `evidence`, `recover`, `judge` (without `--force`, it resumes) and `cards`. `company` adds a version and calls the model again each time |
| Moving forward in time | `nb/update.py` | One step to `--until`, never run on a real build. It moves the build **in place** (no copy), so running it on `b2` would destroy the 23 Oct snapshot. It joins new mail to its works, places new threads with one call per cluster, re-judges works whose expected-by date passed, and remakes cards. It does not touch meetings, parties, the company page, goals, links or merges, reads no founder act, has no Maintain pass, and **keeps its own older copy of the grouping rules** |
| Model calls | `nb/llm.py` | One gateway. Every call is priced before it is sent (a worst-case reservation, 9.5 times the real cost of a judgment), logged in `notebook.runs` with its cost, and refused above the cap. The cap reads the all-build spend **once**, when a run starts, and keeps reservations in memory, so two runs at once don't see each other. A timed-out call counts as $0 |
| Concurrency | `judge.run(workers=N)` | N situations judged in parallel (4 by default; `b2` ran with 8). Ours first, then newest first |
| Clock | `BuildSettings.as_of` | Nothing after the instant is read. But **every date is UTC**: a date passes at 23:59:59 UTC (05:29:59 IST the next day, `nb/checks.py:109-110`), "today" is the UTC date, and the judge is shown "UTC" only. The company's zone is given to the company-page call and then dropped. Saved times (`judged_at`, card times, version times) are wall clock, so a replay cannot ask for "the page as of day D" from them |
| Goals | `nb/company.py:174-184` | The company page proposes goals before any work is judged (15 in `b2`) and the judge sees them. But the card is decided inside the judgment, before `relate` revises the goals, and `nb/cards.py` never reads a goal |
| Locks | — | Nothing keeps two commands off one build |

### Measured on build `b2`

| Step | Calls | Cost | Time (model) |
|---|---|---|---|
| Company page | 1 | $0.096 | 1.0 min |
| Parties | 9 | $0.664 | 1.9 min |
| Situations | 107 | $1.109 | 2.7 min |
| Judge, 379 situations, 8 at once (plus a 12-situation sample and 12 failed grammar probes) | 401 | $6.366 | 7.7 min for the 379 |
| Relate | 1 | $0.172 | 2.0 min |
| Judge again (10 situations) | 10 | in the judge line | 0.7 min |
| Cards, export, scorecard, compare | 0 | $0 | seconds |
| **Total** | **531** | **$8.41** | about 17 min of model time; built by separate commands over 32 min |

**Two figures for planning:**
- A situation costs **about $0.016** to judge.
- A judgment takes **about 8 seconds** (mean 8.1 s, median 7.1 s, longest 42 s), so 8 workers judge about one a second.

**Spend so far:** $9.24 of the notebook's $20 cap, $10.76 left.

There is no scheduler, no trigger and no loop beyond the commands a person runs.

# P1 · Orchestrator · 01 · What's exactly there

**The part:** what runs, when, for which business situation, in what order, at what cost. That covers the four loops (Onboard, Evolve, Act, Maintain), the triggers, the clock, the budget, and the record of each run. The Orchestrator never judges anything and never stores a conclusion.

**Read at:** the product code on `harsh/mvp` `7d2c3615`, which is what production runs. The engine on the local `speedrun008` is the same code. The notebook is the local prototype (`Local Database (Rohit_Org_GV2)/notebook/nb/`).

**Measured on:** the local copy of the design partner's org, cut from production on 28 Oct at 12:45 UTC. That org's production data was started again from empty on 21 Oct, and its mailbox was captured again on 22 Oct. The activation rows say "prod test 21 Oct, fresh DB". So **22–28 Oct is a measured first week of a new tenant**, and this file uses it that way.

**Status key:** ✅ works · 🟡 partly works · ❌ doesn't work · ⬜ not built.

---

## 1 · Every function of the Orchestrator, and whether it works (product)

### 1.1 · Getting data in on time

L1 does the capture. The Orchestrator only decides when it runs.

| Function | Where | Status | Measured, 22–28 Oct |
|---|---|---|---|
| Pull new mail and calendar on a schedule | `platform/scheduler.py`: a light tick every 15 min, which polls only the sources that are due (`select_due`) | ✅ | Gmail was polled every 15.5 min (median). The longest gap in 7 days was 42 min. Calendar was polled hourly. 3 pulls failed in 7 days |
| Real-time push (a new mail reaches reasoning in about 2 min) | Composio webhook → `platform/warm_lane.py` | ⬜ not in use | 0 of 4,784 events arrived by push. The warm lane is used only to queue a chain that found its org busy |
| First pull at connect (the backfill) | OAuth adoption → `sync_jobs` → `platform/sync_worker.py` → `_onboarding_sync_bg`. It checkpoints, heart-beats and resumes after a crash | ✅ | 22 Oct: 2,240 mails backfilled (180-day window) in 2 h 18 min, and 136 calendar events. The first attempt failed and the job resumed. Connect → "Ready" took 3 h 39 min |
| Stop pulling for a paused org, a lapsed plan, a spent day or a full plan quota | `run_sync_sweep`: `_org_paused`, `_plan_expired`, `_llm_over_daily_cap`, `_sync_headroom` | ✅ in code | Not exercised this week |
| Notice a revoked login and mark the connection | `_connection_still_valid` | ✅ in code | — |

### 1.2 · Waking the brain up (triggers)

| Function | Where | Status | Measured |
|---|---|---|---|
| Reason when new data arrives | Light tick: the chain runs only for an org whose sources landed something new | 🟡 | 68 chains in 7 days. But each one redoes the whole company ([1.4](#14--running-the-work)) |
| Give every situation a first look | Expert pass trigger `first_look` | 🟡 | 43 first looks in 7 days. **80 of 264 files** have ever been judged ([06](../06-MEASUREMENTS.md)) |
| Reason when a date comes close or passes | Expert trigger `date_closing_in`; L2 trigger `deadline_crossed` (a constant in `contracts/reasoning_result.py`) | ❌ | 0 of 138 L2 runs. 0 of the 47 recorded expert triggers |
| Reason when an expected reply doesn't come | Expert trigger `reply_overdue`; L2 trigger `expected_reply_absent` | ❌ | 0 and 0 |
| Reason when a goal changes | — | ⬜ | Goals: 7 proposed, 0 confirmed |
| Reason when the founder acts, or an execution ends | — The L5 executive sweep tracks commitments, and L6 learns weekly, but neither wakes a situation | ⬜ | 3 founder actions on cards in 7 days. 105 tracked commitments: 50 pending, 35 expired, 20 cancelled, **0 completed** |
| Do things at a local hour (the morning brief at 08:00 company time) | `_compose_due_briefs` at the end of each sweep; `executive/morning.py` | 🟡 | 6 briefs in 7 days. **None on 24 Oct. 25 Oct's came at 13:31 IST.** All 6 were written by the template, because the brief's writer is not switched on |

### 1.3 · Choosing what to work on, and in what order

| Function | Where | Status | Measured |
|---|---|---|---|
| Skip what hasn't changed | Fingerprints: `reason/change_gate.py`, the expert and L2 passes | 🟡 | 16 of 20 re-judgments came with no new mail in between |
| Most important first | Expert pass: nearest deadline first, at most 10 a pass. L2 pass: a deadline this week, then newest evidence, at most 10 a pass | 🟡 | Neither ranks "we owe something" or "a goal is at risk" |
| One run per org at a time; fair across orgs | `org_run_leases` (single flight); capture runs oldest-due first | ✅ capture · 🟡 reasoning | Reasoning runs org after org, inside one tick, with one warm-lane slot for the whole platform |

### 1.4 · Running the work

| Function | Where | Status | Measured |
|---|---|---|---|
| Redo only what changed | The chain (`api/routes._run_l2_chain`) | ❌ | **A chain takes 97 min** (median; 90th percentile 122 min; longest 150). **68 min of it is the L2 rule pass over the whole company**, even when 0–2 new signals came in. A chain starts about every 100 min, so this one tenant keeps the reasoning busy almost all day. **A new mail waits 2.5 h** (median) before L2 has processed it |
| One path, so one card per situation | `reason/runner.run_all`: expert pass → L2 pass → compiled lane → legacy packs → narration | ❌ | Three card makers ([02](02-WHATS-FAILING-AND-WHY.md) F1) |
| Goals before cards | Goals are synced from accepted brief lines at the start of `run_all` | ❌ | No brief line is accepted, so no goal reaches a pass |
| Survive a crash or a deploy | Sync jobs checkpoint and resume. A chain holds a lease and is re-run. A tick is cut off at 20 min and the next one still fires | ✅ | — |

### 1.5 · Money

| Function | Where | Status | Measured |
|---|---|---|---|
| Caps per tenant and per model site | `_llm_over_daily_cap` ($25 a day and 20,000 calls, checked per org before a pull); `reason/bundle/budget.OWN_BUDGETS` (the L2 judge R-9: $2 a day, $0.25 a call; the expert R-7: $2 a day; narration $2; the brief writer $0.25; card copy $0.50) | ✅ | The caps hold |
| Spend in priority order, and say what was skipped | R-9's gate | 🟡 | **R-9 hit its $2 every day.** 95 calls were refused for budget, and 38 results were carried as "over budget". These are counted, but nobody sees them |
| Don't pay for answers that are thrown away | — | ❌ | Of R-9's $13.55, **$5.28 (39%)** went on 30 answers that failed validation and 6 that were cut off |
| What a tenant costs | `llm_costs`, priced by `platform/metrics.cost_usd_sql` | measured | **$25.44 on the onboarding day** (22 Oct UTC), $14.92 of it L1 reading the backfilled mail. **$4.34–6.86 a day after that**: about $5.70 a day, $170 a month |

### 1.6 · Knowing what ran

| Function | Where | Status | Measured |
|---|---|---|---|
| A record per capture run | `l1_sync_runs` | ✅ | 676 rows |
| A count per chain | `pipeline_counters` (the funnel) | ✅ | 68 chains |
| A record of a whole run: what woke it, what it touched, what it cost, what it skipped | — Stage times go to the log only (`platform/stage_timer.py`) | ⬜ | The chain times above had to be rebuilt from the funnel's write times |
| Daily health per tenant, with alerts | `platform/daily_health.py`, after each heavy tick | ✅ since 26 Oct | Both days alerted "database over its ceiling": 544 MB, then 570 MB, against 472 MB |
| Which code is running | `/health` | ❌ | It reports `build_sha: "dev"` (GeniOS-013 [04](../04-HOW-IT-RUNS-SMOOTHLY.md)) |

### 1.7 · Switches and a new customer

| Function | Where | Status | Measured |
|---|---|---|---|
| Per-tenant switches as rows | `l1_semantic_activation`, `l2_v2_activation`, `l3_activation`, `l4_activation`, `tenant_packs`, the kill switch | ✅ | — |
| A new tenant gets the brain | `platform/intelligence_onboarding.make_tenant_live`, run at the start of every chain | ❌ | See §4: a new tenant gets the old rule packs and no brain |
| One list of switches, checked against what ran | — `reason/cutover.py` lists seven for the L2 cutover only | ⬜ | — |
| An honest onboarding progress screen | `onboarding_progress`: connecting → emails → calendar → processing → graph → intelligence | 🟡 | It said "Ready" after the old lanes ran. On that day the brain had reviewed 3 files |
| Goals at onboarding | The weekly brief review (`reason/brief_review`) and L2's goal proposals | 🟡 | The first brief review ran on day 5 and proposed 29 lines. L2 proposed 7 goals on days 5–6. None is accepted |

## 2 · How a day runs in the product today

All of it runs inside **one API process** (`Procfile`: `web: uvicorn …`), on four background threads: the scheduler, the sync-job worker, the warm lane and the screen promoter.

```
every 15 min   pull the due sources ─► did the org get new mail? ─► THE CHAIN (≈97 min) ─► morning briefs that are due
                                                                    ├─ provision, switch-on, re-read unread mail
                                                                    ├─ L2 rule pass over the whole company ... ≈68 min
                                                                    │    (period, support, meeting, outreach, document,
                                                                    │     spend and history passes, attention, situation refresh)
                                                                    ├─ reason/runner.run_all ................. ≈27 min
                                                                    │    goals from the brief → expert pass → L2 judgment
                                                                    │    → compiled lane → legacy packs → narration
                                                                    └─ cards, post-passes, purge .............. ≈1 min
every 6 h      the same pull and chain, then 18 upkeep jobs, in these groups:
               card lifecycle · retention purges · billing · naming of threads, people and companies ·
               parked, attachment and recapture drains · seats · time zones · L5 executive sweep ·
               distribution · weekly calibration (shadow) · weekly learning · weekly brief review ·
               graph upkeep
               then the daily health row
any time       a user's Sync → a durable job (backfill → L2 drain → run_all → cards)
```

**What the numbers say** (68 chains, 22–28 Oct):

| | Median | 90th percentile |
|---|---|---|
| Chain, start to cards | 97 min | 122 min |
| of which the L2 rule pass | 68 min | 73 min |
| of which `run_all` and cards | 27 min | 50 min |
| Time between chain starts | ≈100 min | — |
| A new mail's wait until L2 has processed it | 147 min | 199 min |

The chain time is the same every day (93–102 min), so it isn't a warm-up effect. It's the shape of the chain.

## 3 · Onboarding as built

The full path is in [06](06-NEW-CUSTOMER-ONBOARDING.md). In short:
1. The founder connects Gmail and Calendar (Composio OAuth).
2. The status poll adopts the connection and queues one durable job.
3. The job pulls Gmail, then Calendar:
   - the window is the founder's pick (60 days by default; this org chose 180);
   - it stops at about 5,000 messages per source;
   - every 6 rounds of pages it lets L2 read what has landed.
4. When the pull is done:
   - L2 drains everything, in chunks of 500;
   - `run_all` runs once;
   - cards are built;
   - the progress screen says "Ready".

**On 22 Oct:**
- It took 3 h 39 min.
- The model cost that day was $25.44.
- The founder got 14 cards from the old lanes.
- The brain had reviewed 3 files.

## 4 · What a new tenant gets switched on, and what this org has

`make_tenant_live` runs at the start of every chain. It switches a tenant on, unless a row already says otherwise.

| Switch | A new tenant, automatically | This org |
|---|---|---|
| L1 semantic lane; L2 analytic and patterns | on | on |
| Domains (L3) | Admin only (`default_on: true`). Founder Office, Sales and Support are off | Admin, and Founder Office (on by hand, 21 Oct) |
| Rule packs | sales, general, admin, customer_support, all **active** (`packs/wiring.ensure_defaults`) | admin, founder_office, general active; sales and customer_support disabled by hand (3 Oct) |
| L4: roster v2, ranking v2, bundle, critique, brief | on | on |
| L4: **expert review, L2 reasoning, L2 cards** | **off.** The reasons in `NOT_DEFAULT_ON`: they are "a bill a tenant never agreed to", and L2 cards are "a cutover" | **on, by hand, 21 Oct** |
| L4: the brief's writer, card copy, calibration apply, cards from situations | off | off |

**So today a new founder would get:**
- sales and support rule cards on a founder's mailbox;
- a morning brief written by template;
- **no expert review and no L2 judgment.**

Everything this org sees from the brain was switched on by hand.

## 5 · In the notebook (the local prototype)

| Piece | File | What it does |
|---|---|---|
| Commands | `nb/cli.py` | `evidence`, `recover`, `company`, `parties`, `works`, `judge`, `relate`, `cards`, `export`, `scorecard`, `compare`, `update`, `all`, `status` |
| A build | `nb/config.BuildSettings` | One instant (`as_of`), one model, one cap, an optional dry run. The first command that writes records the instant and the model. A different `--as-of` or `--model` is refused, so a different instant or model means a new build id |
| Order of `all` | `cli.run_all` | evidence → recover archived text → company page → parties → situations → judge each one → relate (goals, links, merges, two code-built situations) → judge again (merged, linked, new) → cards → reports |
| Moving forward in time | `nb/update.py` | The first Evolve, never run as a replay. It does four things: a new mail in a known thread joins its situation; new threads are placed by one model call per cluster; a situation whose expected-by date passed is judged again; cards are remade. **It keeps its own older copy of the grouping rules** |
| Model calls | `nb/llm.py` | One gateway. Every call is priced before it is sent (a worst-case reservation), logged in `notebook.runs` with its cost, retried on a passing error, and refused above the cap. The cap is summed over all builds, but **each process keeps its own reservations** |
| Concurrency | `judge.run(workers=N)` | N situations judged in parallel. Ours first (situations where we wrote, or something was asked), then newest first |
| Clock | `BuildSettings.as_of` | Nothing after the instant is read, including meetings the copy didn't yet know (`known_at`). **The model is shown UTC only** |

### Measured on build `b2` (as of 23 Oct, 01:40 UTC)

| Step | Calls | Cost | Time |
|---|---|---|---|
| Company page | 1 | $0.096 | 1 min |
| Parties | 9 | $0.664 | 2 min |
| Situations | 107 | $1.109 | 2.7 min |
| Judge, 378 situations, 8 workers (plus a 12-situation sample and grammar probes) | 401 | $6.366 | about 25 min |
| Relate (plus 2 code-built situations judged) | 3 | $0.172 | 2.7 min |
| Judge again (10 situations) | 10 | in the judge line | 1.3 min |
| Cards, export, scorecard, compare | 0 | $0 | seconds |
| **Total** | | **$8.41** | about 40 min |

**Two figures for planning:**
- A situation costs **about $0.017** to judge.
- A worker judges one in **about 30 seconds**: 25 min × 8 workers ÷ 378.

There is no scheduler, no trigger and no loop beyond the commands a person runs.

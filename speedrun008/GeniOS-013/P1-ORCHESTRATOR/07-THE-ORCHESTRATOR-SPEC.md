# P1 · Orchestrator · 07 · The Orchestrator, specified in full

**What this file is:** the full specification of P1: what runs, when, for which situation or goal, in what order, at what cost, for every customer. [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md) holds the decisions and the step-by-step build; each step cites the section here it builds. [08](08-REQUIREMENTS-TRACE.md) traces every requirement from the six sources to a section and a step. [01](01-WHATS-EXACTLY-THERE.md) and [02](02-WHATS-FAILING-AND-WHY.md) hold the measured facts this file's "Today" lines cite.

**The sources:**
1. Design Atlas v2: the Orchestrator A to Z (L2 · O), the call budget (II.2), how the graph stays current (L3), the state machines (III.3), debugging (III.6), the failure catalogue (III.7), cost and latency (III.8), what a subscription switches on (IV.1), the first hour (A.10), and the honest state, fix list, build order, measures and rules (V.1–V.6); with the GeniOS-008 architecture, rules and migration plan.
2. The ideal dashboard: every date, age, next check, timed drop, receipt and history line it shows.
3. The expected outcomes: [10](../10-ACCEPTANCE.md) (the replay, the targets) and the card-by-card trace.
4. The earlier plans: GeniOS-009 (the loops), GeniOS-011 and GeniOS-012 (the run gate, the switches, production readiness), GeniOS-013's own 28 Oct plan, and YC-II W27's decisions.
5. The launch film, with Rohit's description of the four loops.
6. What the other four parts of GeniOS-013 need from P1 (their "Owed by other parts" rows).

**Written for:** Harsh and the coding agents Harsh assigns, and Rohit as the reviewer of every decision in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).

**Read at:** product code `a729b968` (29 Oct); the notebook as of 30 Oct; the local copy of the design partner's org (cut 28 Oct, 12:45 UTC).

---

## §0 · Sixteen rules P1 never breaks

1. **P1 never judges, never stores a conclusion, never authors knowledge and never words or ranks a card.** It makes no model call of its own: the judgment and the placement call are P4's, the door is P2's, the words are P5's. A guard fails any loop module that imports or calls a model client, or writes a page, a goal's status or a card other than through P2's door and P5's card step (OG-15). It decides what runs, when, for which subject, in what order, at what cost, and records that it did.
2. **Nothing runs without a named trigger, and every run writes one row.** Nothing reasons continuously or on a bare timer (Atlas L2 · O). A run with no row is a defect, found by a test.
3. **Every wake-up has a key and fires once.** The key is (tenant, subject, trigger, rung or evidence id), across re-runs, restarts and replays. A rung already judged never fires again.
4. **A date wakes a judgment, never a card.** The card comes only from the judged page (P5 D-P5-1). The one date that wakes no judgment is an `outbox_due` instant: it only calls P5's delivery step for a card already written (§5.2).
5. **The company's clock, everywhere.** Every "today", every rung, every local hour and every cap's day is the company's local day; UTC is printed beside it, never instead. A weekday is always derived from its date, never typed. A seat's own zone governs only that seat's morning brief (§2.1).
6. **No run reads the wall clock.** Each run is given its instant (`eval_time`) and stores it, so it can be replayed at that instant. A value computed against "now" (days waiting, overdue hours, an age) is never stored as a fact.
7. **Evolve touches only the work its wake-ups name,** in the order evidence → place → situations → goals → cards. Whole-company work runs only in Maintain.
8. **One run per subject at a time.** Arrivals during a run coalesce into the next one; a run that loses a race is re-queued once against the new state, never merged.
9. **Spend in priority order, under one cap held in the database, and never silently short.** Every skipped or carried subject is listed with its reason. Safety items are never deferred for budget.
10. **A failed answer gets only P4's ladder, with the error shown** (P4 07 §15): a malformed answer one repair; a generic answer one retry; a timeout or a model error one retry, on a narrower packet and on the policy's fallback model, then `abstain`. Together they make at most one extra paid call per input hash, the one shared allowance P4 07 §15 states, so never a third paid attempt. P1 adds no paid attempt of its own, and recovers a parked subject only as §9.6 says.
11. **A failed run leaves its subject exactly as it was,** with a failure row. A failed run is never read as "nothing to do", and never marks anything handled.
12. **Silence is a finding only where the source was read through the instant.** Each run records its coverage per source; a partial or unconnected source gives "unknown", never "overdue".
13. **Every switch is a row in one registry, with a test that flipping it changes what runs.** A loop in shadow writes nothing a person sees.
14. **A tenant moves to the new path only through the parity gate,** its numbers written down before the run; an absent measurement counts as a failure.
15. **A new tenant needs no switch flipped by hand,** once the new path is the default.
16. **One tenant never delays another.** Every row carries `org_id`; no query runs without it; a tenant's backlog never reaches another tenant's first hour or critical work.

## §0b · The four loops, for every customer's data

| Loop | Started by | What runs | For a founder | For a team |
|---|---|---|---|---|
| **Onboard** (once per tenant; again per new seat and per new source) | Connect | Phases 0–8 (§6): capture in waves, the company page and the organisation, parties, situations judged ours first, goals proposed, first intelligence, then history in the background | First intelligence within 2 hours of connect, everything in the window judged within 24 hours, reasoning under $10 once for six months of mail ($15 for 365 days); at most 30 open cards after both waves, with no ideal card lost | A team's onboarding cap is set before its first run. A second seat or a new tool is an Onboard run for that seat or source, placed into the situations the company already has |
| **Evolve** (on every wake-up) | New evidence (after a 10-minute quiet window), a date reaching its rung, news, a goal change; and a daily pass at 06:00 company time | Only the touched subjects, in the order evidence → place → situations → goals → cards (§5) | New mail on a live situation moves its page and card within 30 minutes for 9 in 10; a date crossing is judged within 2 hours; a quiet day costs 0 model calls; a day under $0.50 | The same; a seat's private items stay private through every run |
| **Act** (on every founder act and every result) | A press on a card, an answer, a goal act; an agent's result; an execution outcome | The act is evidence and wakes only its subject, at the highest priority (§7) | The next judgment cites the act | A member's act wakes the subject for that member's visibility |
| **Maintain** (nightly at 02:00 and weekly, in the company's time) | The schedule | Dormancy and lapses by stop rule, check-in states, predictions due, the date index's integrity, the weekly analyse pass, calibration in shadow (§8) | Open cards stay at most 30 for a founder-size company with no ideal card lost; the weekly reasoning under $1 | The weekly numbers per department, read from each subject's domain on the ledger (§10.1); the support view per tenant |

## §0c · The map: what exists, what is adapted, what is built

| Piece | Today | Becomes | Verdict |
|---|---|---|---|
| `platform/scheduler.py` (one thread; a 15-minute light tick and a 6-hour heavy tick counted from process start) | Runs capture, chains and upkeep inside the API process; a cut tick keeps running | The capture schedule moves into the worker; the heavy tick becomes Maintain at 02:00 company time; a timeout cancels | **ADAPT** |
| `capture/acquire/cadence.py` (per-source cadence, oldest due first) | Works: Gmail every 15.5 min (median) | Kept as the capture producer; a forced pull before a timed wake that depends on a source (§5.2) | **KEEP** |
| `platform/sync_worker.py` (durable sync jobs, checkpoints, heartbeat) | Works; resumed once on 22 Oct | Kept for capture; onboarding's phases above it are new (§6) | **KEEP** |
| `platform/warm_lane.py` (queue rows, `SKIP LOCKED`, leases, back-off, park after 5) | Carries Screen sessions and deferred chains; one global slot | Its queue pattern becomes `loop_wakeups` (§3.3, §12.2) | **ADAPT** |
| `org_run_leases` (single flight per org, 120 s lease) | Works | One run per tenant at a time for Evolve (§12.4) | **KEEP** |
| `api/routes._run_l2_chain` (the 97-minute chain) | Whole company on every call | Runs unchanged inside the runner as "legacy Evolve" until each tenant's gate (§11.6), then retires | **REPLACE** |
| `context/runner.process_pending` (the per-event drain and every org-wide pass) | 69 min per chain, the same with or without new events | The per-event drain stays on Evolve; the org-wide passes move to Maintain (relief R2, §16) | **SPLIT** |
| `reason/runner.run_all` (goals, expert pass, L2 pass, compiled lane, packs, narration) | Three card makers, one after another | The L2 sweep is called by Evolve for the touched subjects (§5); the other makers retire per tenant at the gate | **ADAPT** |
| `reason/expert/triggers.py` (first look, new evidence, date closing in, reply overdue, past normal) | Computed only inside a chain; 0 date wakes in the week | Its trigger set seeds the producers (§3.2); the date logic moves into the date index (§4) | **ADAPT** |
| `reason/l2/sweep.py` `_trigger_of` (relabels expert triggers by substring) | Broken: `expected_reply_absent` unreachable | Replaced by the trigger enum on the request (§3.1); fixed now in the product (relief R7) | **FIX** |
| `reason/change_gate.py`, the fingerprints | Gate after the read; `SWEEP_EVERY` assumes 6 hours | Kept; the wake-up decides what is read, the gate decides whether a call is made (§3.6) | **KEEP** |
| `reason/cutover.py` (cutover switches as data) | Parity functions with no caller | Folded into the switch registry and the parity gate (§11) | **ADAPT** |
| `platform/intelligence_onboarding.make_tenant_live` | Old packs on, the brain off | New tenants on the new path by default (§11.6); until then the runbook (R6) | **ADAPT** |
| `scripts/activate_tenant.py` | The manual path that armed this org | The runbook's script (R6); validates every name and the preconditions' order (§11.7) | **ADAPT** |
| `executive/morning.py` `_compose_due_briefs` (at the tail of each sweep) | Missing one day in seven, late on four | Its own job at 08:00 company time (§8.3; relief R4) | **ADAPT** |
| `platform/daily_health.py` | 2 rows in 7 days; sums chains | A loop line per tenant from the ledger (§15) | **ADAPT** |
| `platform/stage_timer.py` | Log lines only | Replaced by the ledger (§10) | **REPLACE** |
| `pipeline_counters` (five stage counts per chain) | Kept per chain | Kept, written from the ledger per run and per tenant per day (§10.4) | **KEEP** |
| `executive/` sweep (executions, reminders, escalations on the heavy tick) | The only date-driven loop; 6-hour resolution | Its rungs go into the date index and fire at their instant; L4 decides each one (§8.4) | **ADAPT** |
| New: `genios_engine/reason/loops/` | — | `triggers.py`, `dates.py`, `queue.py`, `runner.py`, `onboard.py`, `evolve.py`, `act.py`, `maintain.py`, `ledger.py`, `clock.py`, `budget.py`, `policy.py`, `worker.py`; and, outside it, `platform/switches.py` (the registry and the one gate function, §11.2, §11.3) | **BUILD** |
| New tables | — | `loop_wakeups`, `loop_runs`, `tenant_loop_policy`, `date_index`, `switch_registry_checks`, `parity_gate`, `outcome_labels`, `weekly_rollups`, `subject_leases`, `learning_shadow_rows`; and `plan_economics`, a platform table (§9.1) | **BUILD** |
| Notebook: `nb/cli.py` commands, `nb/update.py`, `nb/llm.py` | Commands only; `update` moves a build in place; the cap per process | `nb/clock.py`, `nb/ledger.py`, `nb/triggers.py`, `nb/dates.py`, `nb/loops.py`, a database-held cap, `nb.cli clone`, `onboard`, `replay`, `drill` (04 P1-1 to P1-10) | **BUILD** |

---

## §1 · What P1 is, and where it stops

### 1.1 · Its jobs

- **When:** the wake-ups (§3), the date index (§4) and the schedule (§8); the company's clock that all of them read (§2).
- **What and in what order:** the four loops (§5–§8), each a thin sequence of calls into P2, P3, P4 and P5.
- **At what cost:** one cap per tenant, spent in priority order, never silently short (§9).
- **Record:** one ledger row per run (§10); health and alerts from it (§15).
- **Switching:** the policy rows, the switch registry and the parity gate (§11).
- **Running:** the worker process, the queue, the lanes, many tenants at once (§12, §13).
- **Proving:** the replay and the drills (§14).

### 1.2 · Where each other part begins

| Part | What P1 hands it | What P1 receives | Never P1's |
|---|---|---|---|
| **L1 Signals** | The capture schedule; a forced pull before a timed wake that depends on a source; EvidenceNeed fetch jobs with their cost cap and expiry | Captured events; per source its state, its cadence, `last_read` and its read-through instant (coverage) | Reading or classifying a mail |
| **P2 Notebook** | The run's subjects, `eval_time`, the dirty set to a fixed point | `due_dates()`, `still_open(work_id, since_version)`, `dependents(work_id)`, the fingerprint, the door's verdicts (ADMIT, HOLD, REJECT), founder acts | Storing a page, a goal or a fact |
| **P3 Plane D** | — (P3 is a resource P4 consults) | The domain and pack states for the switch registry; a capability's stage priors and stop rules (for expected-by dates and dormancy) | Choosing knowledge |
| **P4 Plane R** | A `ReasoningRequest` per subject (trigger, `rung_kind`, `change_kind`, `eval_time`, budget, and `viewer` from the wake-up's `seat`), at most 10 subjects per sweep | The result, its receipt, and its next wake-ups (step 12: `wake_on`, `due_dates`) | Classifying the need, choosing the depth, judging; the model rules (P4 07 §0) |
| **P5 Cards** | The card step, last in every run; the moments a card should surface (the surface time as a rung); the 08:00 brief job; the outbox's due rows | Cards opened, updated and closed per run (for the ledger) | Raising, wording, ranking or delivering a card |
| **L4 Executive** | Its tick, and the instants of its ladder rungs and next checks, from the date index | Execution outcomes (as Act wake-ups) | Deciding a rung, an approval or a send |
| **L6 Learning** | The weekly learning and calibration jobs, in shadow | Labels, as evidence | Arming calibration |

### 1.3 · The objects P1 owns

| Object | Table | Section |
|---|---|---|
| A wake-up | `loop_wakeups` (product), `notebook.wakeups` (notebook) | §3.3 |
| A dated entry | `date_index` (product), `notebook.date_index` (notebook) | §4.2 |
| A run | `loop_runs` (product), `notebook.loop_runs` (notebook) | §10.1 |
| A tenant's policy | `tenant_loop_policy` | §11.1 |
| A switch | `platform/switches.py` (the registry) and `switch_registry_checks` | §11.2 |
| A situation type's gate state and its way back | `parity_gate` | §11.5 |
| A spend reservation | the reservation rows (product), `notebook.budget` (notebook) | §9.2 |
| An outcome label for L6 (append-only) | `outcome_labels` | §7.6 |
| A tenant's loop line per day | `daily_health` | §15.1 |
| A tenant's weekly rollup and quality line | `weekly_rollups` | §8.2 |
| A subject's lease (one run per subject) | `subject_leases` | §12.4 |
| A learning switch's shadow rows (kind, count, window) | `learning_shadow_rows` | §11.2 |
| Plan economics (a platform table, one row per plan) | `plan_economics` | §9.1 |
| The company clock | `reason/loops/clock.py`, `nb/clock.py` | §2 |

Every table here that holds tenant rows is on the erasure list from the step that adds it (§13.4, OG-14); `plan_economics` holds none and is outside it (§13.1).

---

## §2 · The company clock

### 2.1 · The zone

- **One IANA zone per tenant,** held on the company page (P2 §3.4) with `zone_confirmed`. It is asked at signup, or taken from the browser (§6.1 phase 0), pre-filled on the company page and confirmed there in phase 2; judging waits for that confirmation up to minute 60 (§6.1).
- **Inference is only a suggestion.** Today's inference from send hours on the heavy tick becomes a proposed value, labelled "unconfirmed".
- **Until the zone is confirmed,** every instant prints as UTC with "time zone unconfirmed"; nothing says "today", "now" or "overdue" from UTC alone, and nothing interrupts except containment (P5 07 §6.3). The hourly day-rung sweep, the 06:00 pass and the 08:00 brief job each write their ledger row `skipped` with reason `zone_unconfirmed`, fire no day rung and compose no brief; instant rungs still fire, printed in UTC. Phase 6's first brief (§6.1) is shown on the first screen but not pushed (no email, no popup) until the zone is confirmed, its row reading `zone_unconfirmed`. The day rungs stay unfired, so the first sweep after the confirmation fires, once, the rung each entry then stands at.
- **A seat may set its own zone,** stored on the seat record (P2), for its own morning view: that seat's local day then sets its 08:00 brief and the brief's once-a-day claim (§8.3). Everything else (rungs, caps, the company's days, "today" on a card) uses the company's zone, and both zones print with UTC beside them.

### 2.2 · The functions

`reason/loops/clock.py` (product) and `nb/clock.py` (notebook) are the only places that turn an instant into local time. Every other module calls them.

| Function | Gives | Example |
|---|---|---|
| `stamp(t)` | The instant in the company's time, with UTC beside it | "Fri 23 Oct, 07:10 IST (01:40 UTC)" |
| `day(t)` | The company's local date | 23 Oct |
| `weekday(d)` | The weekday, derived from the date, never typed | 1 Nov 2026 is a **Sunday** |
| `relative(t, now)` | A relative phrase, computed at view time and never stored (P5 07 §4.9), so it re-renders each local day. A dated due reads "later today", "tomorrow", "later this week" (inside the current week), "in N days" or "passed"; a `window_end` due (§4.1) reads "this week" or "next week" by the week of §2.7, with "(rolling)" when its window rolls; a due with no date reads "anytime". A week or rolling due is stored as its window end (or none) with its reason, never as a phrase. A past instant that is not a due (a source's `last_read`) reads "N min ago" under an hour, "N h ago" under a day, then the date | "later today, 11:30 IST", "in 3 days"; a `window_end` due of Sun 25 Oct reads "this week" on Fri 23 Oct and "passed" on Mon 26 Oct; a dated due of Fri 23 Oct reads "later today" on 23 Oct; a rolling `window_end` recomputes its end at each local midnight and keeps reading "this week (rolling)"; a due with no date reads "anytime" every day; a `last_read` 4 minutes back reads "4 min ago", 70 minutes back "1 h ago" |
| `rung(due, now)` | The rung a date stands at, counted in local days (§4.3) | within 7 days, tomorrow, today, passed |
| `day_end(d)` | The last second (23:59:59) of local day d, stored as a UTC instant (P2 07 §13). A date with no time is due at `day_end(d)` and is passed only when `eval_time` is after it | `day_end(24 Oct)` in India is 24 Oct, 18:29:59 UTC |
| `week(t)` | The company week holding t: its start, its end and its label, from the company page's `week_start` (§2.7) | 23 Oct 2026: "W43, 19–25 Oct" |
| `period(t, kind)`, `period_end(kind, t)` | For kind `week` · `month` · `quarter` · `fiscal_year` in the company's calendar (quarters counted from `fiscal_year_start`, §2.4): t's day as day N of M, and the instant the period ends (`day_end` of its last day). A pace is N / M, computed, never typed; the pace bar's drawing is the Home screen's | 23 Oct 2026: October, day 23 of 31, pace 74%; this quarter ends 31 Dec at local midnight |
| `working_days(a, b)`, `next_working_morning(t)` | Working-day arithmetic in the company's calendar (§2.4) | "Mon 26 Oct, 09:00" after a Friday |
| `local_hour(tenant, name)` | The instant of a named local hour on a local day (§2.5) | Maintain at 02:00, the brief at 08:00, the delivery hour at 09:00 |

### 2.3 · Local days and instants

- **A date with no time is a whole local day.** A deadline stated as a date passes at local midnight at its end, never at 23:59:59 UTC: it is due at `day_end(d)`, so "passed" begins at the local-midnight crossing (`f2` reads "today" for the whole of 24 Oct in India). A loop due on a date is broken only after its local due day has ended (P2 07 §13).
- **A date with a time is an instant, at minute grain.** `f1`'s 11:20 join and its 11:30–12:00 slot are instants.
- **The two are never mixed in one rung or one entry.** Each date-index entry carries one grain, `minute` or `local_day`, which P2's `due_dates()` passes from the source text (§4.2). A day rung is crossed at local midnight; an instant rung at its minute.
- **A daylight-saving change** is handled by the zone: an instant keeps its absolute time; a local hour keeps its wall-clock hour on both sides of the change.

### 2.4 · The working week and holidays

- **Per tenant, on the company page:** the working days (Monday to Friday by default), the working hours (09:00 to 18:00 by default), a holiday list (empty until set, shown as "holidays not set"), the week's first day `week_start` (Monday by default, §2.7) and `fiscal_year_start` (1 Jan by default; quarters and the fiscal year are counted from it, §2.2).
- **Each rung kind states what happens on a non-working day:** a stated date fires as stated (`b1` is due on Sat 24 Oct and fires that day); an expected-by date and a stage rung roll to the next working morning ("wait until Monday"). The rule is a default per rung kind, held as a data row that `clock.py` reads, never code (§4.1); a tenant may set its own per kind on its policy row (`non_working_rules`, §11.1); each entry keeps the rule it was written under, and P5 shows it on the card's timing line.
- **A wait counted in working days** (a stage's norm stated in working days) counts working days; a reply "two days overdue" over a weekend is not silence. The unit (calendar or working days) of every lead time, stage norm, day-count threshold and ladder day is a field on its source row (P3's stage priors and day-count rules, the company's `approval_lead_times`, L4's ladder row), so the same 2-day lead time over a weekend gives two dates under the two units, and changing the field changes the date with no code change.
- **The support clock** (today 718 situations computed on UTC working hours, 14:30–23:30 IST) reads these hours (relief R3).

### 2.5 · The local hours

Per tenant, on the policy row's `local_hours` (§11.1), each with a default. A per-tenant start jitter of up to 10 minutes, so that tenants in one zone don't all start at once, applies to the start of the nightly, daily-pass and weekly jobs only; the brief hour is composed within `brief_margin` and the delivery hour is exact:

| Hour | Default | What runs |
|---|---|---|
| Maintain, nightly | 02:00 | §8.1 |
| The Evolve daily pass | 06:00 | the day's timed rungs scheduled, the morning's drafts, and any straggler day rung the hourly sweep has not fired (§5.1); a midnight rung is fired by the sweep within the hour (§4.6), never first here |
| The morning brief | 08:00 | P5's brief, composed by its own job (§8.3) |
| The delivery hour (`delivery_hour`) | 09:00 | the morning drop of the day's cards and Later's "tomorrow"; P5 reads it as `local_hour(tenant, delivery)` |
| Maintain, weekly | Sunday 03:00 | §8.2 |

**The daily pass has a deadline:** the day's first delivery rung (the delivery hour by default) less `pass_margin` (30 minutes by default, on `local_hours`); the start jitter moves the start, never the deadline. The pass begins with a forced pull of every connected source, each bounded as in §4.6 (60 seconds by default) with its read-through recorded, so the previous day's late evidence is in before it judges; a source that fails or times out is recorded "not read through" and the pass goes on. It finishes, drafts included, by its deadline (the ideal's pass ends at 07:10 for a 09:00 drop, deadline 08:30); an overrun alerts (§15.3).

### 2.6 · `eval_time`, and two times on everything

- **Every run is given its instant** (`eval_time`): in production the moment the run starts, in a replay the replayed instant. It is passed into every call and stored on the run row. No module on the run path reads the wall clock (Atlas L0).
- **Every version, card version and ledger row keeps two times:** the evidence time (what it is as of: the run's `eval_time`, which P2 stores as `as_of` and `known_at`, P2 07 §13) and the recorded time (the wall clock when the row was written). History is rendered from the evidence time; debugging reads both. A version Onboard makes from history is judged at the run's `eval_time`, never back-dated; its history line is dated by the newest evidence it cites (that evidence's `occurred_at`), so history from before a restart still reads in its own order.
- **An as-of read at instant T filters on the evidence time** (P2's `known_at`, `as_of(T)`), never on the recorded time. A replay writes every version with the replayed instant as its evidence time and the wall clock as its recorded time, so a snapshot read at replayed day D is never emptied by a later wall clock (GeniOS-011 08 F3; §14.1).
- **Values computed against "now"** (days waiting, overdue hours, ages) are computed by tools at read time from typed dates, never written as stored facts (GeniOS-008 migration L3-5).

### 2.7 · Days, weeks and caps

- **A cap's day is the company's local day** (today the judge's day rolls at 05:30 IST, F11).
- **"This week" is defined once,** as `week(t)`: the week in the company's zone starting on the company page's `week_start` (Monday by default, which makes it the ISO week and gives its number; for a `week_start` other than Monday the label is the week's start date, "week of 18 Oct", not an ISO number). It is used for the weekly pass, the weekly spend (the sum of ledger rows inside `week(t)`, §10.3), AER and HIR rollups and the activity tiles: a tile on Fri 23 Oct 2026 reads 19 to 25 Oct (W43). A week before connection reads "not measured", never 0.

### 2.8 · Today

The zone is read in several places with no clock object. The brief, quiet hours, the Screen promoter and meeting-day reads use it; the caps, the site budgets, the fingerprint's rungs, the daily health day and both dossiers use UTC; the support clock uses UTC working hours. The notebook's dates are UTC-only, and its judge is shown UTC only ([01](01-WHATS-EXACTLY-THERE.md) §5, §7).

---

## §3 · Wake-ups

### 3.1 · The triggers: one closed list

A run starts only from a wake-up, and every wake-up names its trigger from the closed list P4's request carries (P4 07 §2.1; D-P1-2):

| Trigger | Means | Detail it carries |
|---|---|---|
| `new_evidence` | Evidence arrived for a subject: a mail, a meeting, a document, a Screen item, a tool's record; or a source changed state | the evidence ids; for a new thread or a batch not yet placed, "place"; the `change_kind` of the map below |
| `date_rung` | A date in the index reached a rung (§4.3) | `rung_kind`, the rung, the date and its provenance |
| `news` | P2 offered a checkable fact from one situation to others (a milestone, an opened conflict; P2 07 §10.2), or an accepted company-page change | the fact's id and its source situation or company-page line |
| `goal_changed` | A goal was confirmed, edited, dropped, reached, merged (with the surviving id), had its due set, or moved status | the goal's version and what changed |
| `founder` | A founder act (P2 §7.2): a press on a card, an answer, a correction, a goal act, a recorded decision | the act, with the card and page versions it was made on |
| `maintain` | The schedule, and what only the schedule finds (a prediction due, a stop rule passed); or a check's version changed (P4) | the job and what it found (`check_changed` for a check) |
| `need_met` | An EvidenceNeed was met, found unavailable, or expired | the need's id and its outcome |
| `outcome` | An L4 execution ended, or an agent returned a result | the execution or delegation id |
| `human_ask` | The founder asked for depth ("why?", "look closer") | the ask; it is admitted even when the material-change gate would end the run (§3.6) |

**Every other name maps onto it,** the Atlas's ten triggers, GeniOS-008's and GeniOS-009's names and today's code's included, and so do P1's own events. A table-driven test maps every name below to one value:

| Name | Trigger | `rung_kind`, `change_kind` or detail |
|---|---|---|
| `bundle` (today's only value), a new signal bundle, new evidence | `new_evidence` | renamed |
| `deadline_crossed`, a deadline crossed; the expert's `date_closing_in` | `date_rung` | `stated_deadline`, `decision_deadline` or `goal_due` |
| `expected_reply_absent`, an expected reply absent; the expert's `reply_overdue` | `date_rung` | `expected_by` |
| a stage past its normal length; the expert's `past_normal` | `date_rung` | `stage_overdue` |
| verification due | `date_rung` | `verify_by` |
| `checkin_due` (GeniOS-009 G7), a due check-in or an execution's next check | `date_rung` | `execution_check` or `ladder_rung` (L4's instants, §4.1) |
| a goal change (GeniOS-009 G2) | `goal_changed` | what changed |
| `owner_change`, an owner change | `new_evidence`, `founder` or `outcome`, by what changed it | `change_kind = owner_assigned` |
| a recorded decision | `founder` | the act |
| a completed action | `outcome` | the execution or delegation id |
| a prediction that missed | `maintain` | the prediction's id (§8.1 step 4) |
| a human asking for depth; `founder_asked` | `human_ask` | the ask |
| the expert's first look; a situation's first look on connect | `new_evidence` | `change_kind = first_look` (§4.8) |
| a cited unit, law, pattern, tool or pack changed; an authority (org) revision changed | `maintain` | `change_kind = unit_changed` or `authority_changed`, one per subject whose last receipt pins it or whose fingerprint inputs include it (§8.1 step 8); an accepted claim has no wake-up of its own: it reaches its subjects through P2's dependents and the fingerprint |
| a source changes state: connected, expired, newly shared, coverage moved | `new_evidence` | subject kind `connection`, `change_kind = source_state`; it fans out to the situations and goals whose last receipt recorded that source as unknown, partial or blocking (§3.7) |
| a new source connected | `new_evidence` | subject kind `connection`, detail `source_onboarding`: one Onboard wave for that source (§6.5) |
| a held item retried (held → candidate) | `new_evidence` | detail `retry_hold` (§3.8) |
| evidence a person supplies (an upload, a linked document) | `new_evidence` | `change_kind = evidence_supplied` (§3.5) |
| an accepted change to a company-page line | `news` | `change_kind = company_fact` (§3.7) |

A run labelled only `bundle` or `event`, as every run is today, is a defect.

`change_kind` is set by P1 only for the kinds in the map below. For evidence that changes one part of an existing page (`document_signed`, `approval_received`, `meeting_held`, an owner or approval from a founder act or an L4 record), it is the kind P2's door returns for the admitted diff, which P1 copies unchanged onto the wake-up and the request; P1 never derives it from text, and it is none when the door returns none. The kinds are P4's list (P4 07 §2.6).

### 3.2 · A producer for every trigger

| Trigger | Producer | When it writes |
|---|---|---|
| `new_evidence` | Capture's landing hook (L1), after the quiet window per subject, or per connection for evidence not yet placed (§3.5); the API for an upload, a linked document or a manual Sync | per batch of evidence |
| `new_evidence` (`source_state`, `source_onboarding`) | L1's connection record | when a source is connected, expires, is newly shared, or its coverage moves |
| `new_evidence` (`retry_hold`) | P2's door | when evidence lands that matches a hold's expected items or its EvidenceNeed (§3.8) |
| `new_evidence` (Screen) | The hourly Screen batch (§8), per seat with Screen on | once an hour over the seat's new moments; an hour with none writes a `nothing_due` row and makes 0 calls |
| `date_rung` | The date index's producers (§4.6): a minute-grain scheduler for instants, an hourly sweep for day rungs | when a rung is crossed |
| `news` | P2's door, when an admitted version offers a fact as news, or a company-page change is accepted (`company_fact`) | in the run that admitted it |
| `goal_changed` | P2's goal door (P2 §6.4) | in the run, or the API call, that changed it |
| `founder` | The API, on every founder act | at once |
| `maintain` | The schedule (§8); or P4, when a check's version changes (detail `check_changed`, P4 07 §16, RG-10) | at the tenant's local hours; at once for `check_changed` |
| `need_met` | P2's need matcher; L1's fetch job | when the need's state moves |
| `outcome` | L4's execution store; the delegation route | when the outcome is recorded |
| `human_ask` | The API | at once |

**A trigger with no producer is a defect the switch registry reports** (§11.2). Today only `new_evidence` (as `bundle`) is ever produced; `founder_asked` is unreachable, and the date triggers are computed only inside a chain ([01](01-WHATS-EXACTLY-THERE.md) §1.2).

### 3.3 · The wake-up row (`loop_wakeups`)

| Field | Meaning |
|---|---|
| `id`, `org_id` | Identity and scope (P2 §0 rule 5) |
| `trace_id` | For `new_evidence`, the trace id of the newest evidence in the bundle (the ids are in `detail`); for `date_rung`, `maintain` and `goal_changed`, the trace id of the newest member evidence of the subject version the entry or goal rests on, so a card's lineage returns one trace id from card version to raw event |
| `key` | (tenant, subject, trigger, rung or evidence id), unique for the life of its rung or evidence (§3.4). A rung is named by its entry and its rung; an evidence id is P2's canonical item id, so one message captured twice is one key. A replay adds its build id |
| `loop` | onboard, evolve, act, maintain |
| `job` | For a fetch job (§3.8): `fetch_thread` · `backfill_window` · `re_extract_attachment`; empty for a wake-up |
| `subject` | `{kind: situation · goal · connection · seat · org, id, version}` |
| `trigger`, `rung_kind`, `change_kind`, `detail` | §3.1 |
| `request_id` | The id of the `ReasoningRequest` it produced (P4 07 §2.1). Every consumed wake-up that reaches a subject has one; an `outbox_due` wake-up and a fetch job have none; a duplicate carries the original's |
| `due_at` | When it may be claimed: now, after the quiet window, or a rung's instant |
| `priority` | The class of §9.3, set by code from the trigger and the subject's state |
| `severity` | 4 when the subject's last page says so, or a deterministic safety signal flags the new evidence (P3's hard constraints, P5's containment, P5 07 §6.3); otherwise the last page's severity. §3.5 and §5.4 read it |
| `state` | `pending` · `claimed` · `done` · `coalesced` · `skipped` · `cancelled` · `missed` · `failed` · `parked`. A wake-up carried by the sweep cap or the budget stays `pending`, and only its run's row lists it as skipped; so does one refused for `paused` or `plan_expired`, unclaimed with its reason set, until resume or renewal (§11.3); `skipped` is for a wake-up refused for good before it fires (§3.6, §11.3) |
| `lease_until`, `attempts`, `run_id` | The claim, the retries, and the run that consumed it |
| `seat` | The seat whose evidence or act it carries; its visibility bounds the run (P2 §14). A wake-up with no seat (a date rung, a `maintain` job, news) runs at the subject's page audience, never wider, and the run row records which |
| `visibility`, `schema_version` | The narrowest visibility of the evidence or act it carries; the row's schema version (§13.1) |
| `reason` | For `skipped`, `cancelled`, `missed`, `failed` and `parked`, and for a `pending` one refused at the gate: a code from the closed list of §10.1, with optional words beside it |

### 3.4 · Fires once

- **The key holds for the life of its evidence id or rung, not only while pending.** A second wake-up whose key already exists is not run: it writes a `loop_runs` row with status `duplicate`, 0 calls and cost 0, carrying the original's `request_id`. The same mail arriving by a webhook replay and again through Screen is one run, one situation and one `duplicate` row.
- **A rung fires once per crossing, and never again** (§4.3): a July expected-by date that a page already judged as passed does not wake it every day. A moved date's new entry starts at its next rung not yet fired, so a rung fired before the move never fires again.
- **A replay's wake-ups carry the replay's build id,** so a replay never collides with the live tenant's keys, and two replays of the same base produce the same wake-up list, their keys compared without the build id (§14.1).

### 3.5 · Coalescing, the quiet window and bursts

- **A burst of evidence is one run:** evidence for one subject waits a 10-minute quiet window after its last arrival (D-P1-1), then becomes one wake-up. The window holds at most 20 minutes after the first arrival (`quiet_window_max` on the policy row, §11.1); then the run starts even if mail is still arriving, so a trickle of one mail every 9 minutes runs at the 20-minute mark.
- **Evidence not yet placed** (a new thread) waits its window as one batch per (tenant, connection), the window restarting at each arrival. One wake-up is written with subject kind `connection` and trigger `new_evidence`, and the place step (§5.2 step 2) turns it into subjects.
- **No quiet window** (`due_at` = now) for: evidence a person supplies (an upload, a linked document, a need met by the founder), which also takes priority class 1 and `change_kind = evidence_supplied` so P4 runs a delta (P4 07 §2.6); a `need_met` wake-up (§3.8); and a severity-4 subject (`severity`, §3.3), which fires at once. A severity-3 subject keeps its window and is claimed alone after it (§5.4).
- **All wake-ups for one subject that are due when a run starts become one judgment,** and the run is shown every reason that woke it (`i1` on 23 Oct: five mails between 09:07 and 09:18 and the news of the held review, one judgment), carried in the request as `woken_by` (P4 07 §2.1; owed by P4, 04).
- **Coalescing never widens what a page shows:** wake-ups whose evidence sits at different visibilities are never merged into one request that writes a page visible to a seat lacking some of that evidence. P2 §14 decides the page; P1 passes the widest visibility the writing seat may see.
- **A wake-up that arrives while its subject's run is in flight** is coalesced into the next run, never dropped and never run in parallel.
- **A broadcast is one wake-up:** the sends at one instant to about 33 recipients (27 Oct, [10](../10-ACCEPTANCE.md) §3) are one pending wake-up before placement, and the wave situation (P2 07 §4.8) is the one subject after it, never one per recipient. A reply or a bounce on any one recipient's thread, a new thread included, is placed to the wave through its correlation and wakes that situation only, with no new situation or card (a reply from one of the 12 recipients of `i4`'s update).

### 3.6 · Before a wake-up fires

In order, all by code and with no model call:
1. **The tenant may run:** not paused, plan not lapsed, no kill switch, the loop's policy row not `off` (one gate function for every door, §11.3); and the subject's domain is live or in shadow (§11.4) and, when the policy row's `capability_allowlist` is not empty, its capability is in it (`not_in_wedge` otherwise, no judgment call; §11.3 step 7). In a domain not subscribed, the wake-up is `skipped` with reason `domain_off` and no judgment call; in shadow it runs and publishes nothing. A paused tenant or a lapsed plan leaves the wake-up `pending` and unclaimed, with reason `paused` or `plan_expired`, until resume or renewal (§11.3).
2. **The subject is still open and unchanged where it matters,** checked before every wake-up, `ladder_rung`, `execution_check` and `outbox_due` included: P2's `still_open(work_id, since_version)`. On a resolved, merged or superseded subject, a clock wake-up (a date rung, a ladder rung or check, an outbox row, a held prerequisite) is `cancelled` with reason `already_handled` ("outcome evidence exists"), and L4 and P5 send nothing; on resolution, every pending clock wake-up of the situation is cancelled (P2's owed row ATLAS-68). A `new_evidence` or `news` wake-up on a resolved subject is not cancelled: it runs P2's reopen check (a contradicting member, or the awaited party writing after an auto-close), and the run may end in an L2 `reopen` (P2 07 §5.1). That holds within the tenant's `reopen_window` (policy row §11.1, 90 days by default, or the playbook's stop rule where one is set); after it, the evidence is placed as new work (§5.2 step 2). On a merged subject, the evidence goes to the survivor. A cancelled or moved meeting drops the wake-ups it set. **A situation under an active embargo** (§4.1) fires only `new_evidence`, `need_met`, `news`, `founder`, `outcome` and `human_ask` wake-ups, and its own `lease_end`; its other date rungs, its `maintain` and its `goal_changed` wake-ups are `skipped` with reason `embargo` (the lease id in `detail`), and the `lease_end` judgment reads the goals as they then stand (`i1` after its update send: nothing until Fri 13 Nov unless a reply comes). A severity-4 subject is never held.
3. **A rule transition comes first:** when an expectation is missed, P2's rule transition runs first (0 calls); a judgment is woken only if the new state needs reasoning (P2's owed row ATLAS-41). Whether it does is P4's material-change gate on the post-transition fingerprint; P1 never decides it.
4. **The fingerprint:** an identical re-sent mail or file changes no fingerprint and costs 0 calls (P2's owed row ATLAS-23), but it never removes the request. A re-sent mail under a new message id still produces a `ReasoningRequest` with its request id, and P4 returns termination `unchanged_gate` and writes its one receipt for that request id (P4 07 §16); the run row says `no_material_change`. The same message captured twice is one key and a `duplicate` (§3.4). Whether a changed subject needs a model call is P4's material-change gate (P4 07 §2.6); P1 records its answer ("no material change") as a normal end, never a failure, and never retries it. A `human_ask` is exempt: P4 runs it as a delta at depth 1 even when nothing is new (P4 07 §2.6).
5. **Coverage:** a wake-up that rests on silence (an expected-by date, a stage overdue) records the coverage of the sources it depends on; with a source partial or not connected, the run is told so, and the page says "unknown", never "overdue" (rule 12).

### 3.7 · News, goals, sources and waiting

- **News:** a checkable fact admitted on one situation (a milestone, a held review, an opened conflict) wakes the situations and goals P2 names as its receivers, once per item, so it reaches them before the founder acts (`i1` gains the incubator's milestone on 23 Oct).
- **Goals:** a goal confirmed, edited, dropped, reached, merged, given a due date, or moving status wakes the goal (a dropped one excepted) and its linked situations once, in the same run, nearest due first and bounded by the sweep's cap, except where a lease holds a situation (§3.6 step 2): its `lease_end` judgment then reads the goals as they stand; on a merge every linked situation is re-checked once against the survivor and none loses its goal; a second sweep with the same goals makes 0 calls. A goal is also woken when a linked situation's stage, status or outcome changes in the run (it joins step 5's touched set, §5.2), when a delegated send in a linked situation turns verified (§7.2), when an `event_end` wake fires for a situation a goal plan step is waiting on (its done-when names the meeting: the linked goals join step 5's touched set once, so P2's `goal_progress` is rewritten from the plan rows in the same run), by news, by its `goal_due` rung (its `target_by`), by the founder's answer to one of its four questions (trigger `founder`), and by the weekly Maintain pass; a goal whose linked set did not move and has no such wake makes 0 calls (the fingerprint). A goal with no live linked situation is woken on its own due date and by Maintain. A goal reached wakes the goal step that raises its one "goal reached, confirm" card (P5).
- **Sources:** a source changing state (connected, expired, newly shared, coverage moved) is `new_evidence` with `change_kind = source_state` and the connection as subject (§3.1); it wakes, once, the situations and goals whose last receipt recorded that source as unknown, partial or blocking (connecting billing wakes the goal G-1A03D9 blocked on it, and `p1`); an expiry marks them "unknown", never "overdue".
- **Company facts:** an accepted change to a company-page line (P2 §3.4) is offered as news (`change_kind = company_fact`) to the situations P2 names as its receivers (P2 07 §10.2 item 5: those in any state whose open loops owed by us share the line's topic or metric), plus any whose last receipt cites that line, once per change (`s1` re-raised when the product changed; P2 07 §5.3); a change that reaches no subject is left to Maintain.
- **Waiting:** a waiting situation wakes on whichever comes first, a matching reply or its date; the other rung is cancelled when one fires (`f4`: the reviewer's comments, or Mon 26 Oct 10:00). A first mail from a party we wait on wakes the waiting situation even in a new thread (placement through `waiting_for`; P2's owed row IDEAL-74).
- **Snoozed:** a put-off situation keeps receiving evidence; a matching arrival wakes it before its return date (`l1`). Its `surface_time` and deadline rungs stay active during the snooze, so a put-off high or critical card still wakes at its surface time before its return date ("Back early: the deadline is near", P5).
- **Prerequisites:** an approved agent step that waits on another card (`p1`) is held as a wake-up on that card's resolution, then dispatched by L4 (§7.4).

### 3.8 · Held, waiting for evidence, and asked for depth

- **A HOLD from the door** raises one EvidenceNeed for what it lacks (P2 07 §5.1) and is retried as a `new_evidence` wake-up with detail `retry_hold`: written by P2's door when evidence lands that matches the hold's expected items or its need, and by Maintain's nightly retry (§8.1). P1 owns that retry and the "held → candidate on new evidence" wake-up. A retry that is still held waits for the next match; it never loops.
- **An EvidenceNeed** puts the situation in `awaiting_evidence`; P1 schedules L1's fetch job (the full thread, older history, an attachment) with the need's cost cap, expiry and idempotency key, charges no model call while it waits, and writes `need_met` when the need is met, unavailable or expired. A `need_met` wake-up is keyed on the need's id and fires once, at once (§3.5); its request carries `change_kind = need_met`, so P4 picks the delta depth. Any other wake-up reaching a situation in `awaiting_evidence` with no new material makes 0 calls and ends `waiting_for_evidence`.
- **The fetch is a worker job:** a row in `loop_wakeups` with `job` = `fetch_thread` · `backfill_window` · `re_extract_attachment`, run by P1's worker with L1's code. Its key is the need's idempotency key, so a second request for one need returns the first job. Its cost cap is a reservation against the database-held cap (§9.2), and an over-cap fetch is refused with its reason. Past the need's expiry it is `cancelled` and `need_met` (expired) is written; its result lands as evidence and writes `need_met` (met or unavailable).
- **Every fetch reads the connection's capture window** (the value §6.2 writes through, 365 days by default), never a built-in 60-day default or an empty config; a need beyond the window is unavailable, with the window as its reason. The stored-event fetcher (full text from our own database, no provider call) is armed by default, apart from the Gmail fetchers' switch.
- **A long-horizon need** (history beyond the window read) is a `BACKFILL_WINDOW` fetch job with its own cost cap, never "cannot see" (Atlas V.2).
- **`human_ask`** is admitted even when the material-change gate would end the run (one delta call, §3.6 step 4), and is booked to Act's budget under the tenant's cap.

### 3.9 · Today

Only new mail starts a chain, by the light tick's "new events" test or by the heavy tick, which chains every org every 6 hours. 41 of 66 chains started with no new qualified signal. The trigger recorded is the constant `bundle`. The expert pass's date triggers fired 0 times; L2's relabel of them is broken; `founder_asked` cannot fire; goals are in no fingerprint; card actions are declared no trigger ([01](01-WHATS-EXACTLY-THERE.md) §1.2).

---

## §4 · The date index

### 4.1 · What is indexed

Every date that can wake a subject is one entry, of one of these kinds. Each kind is passed to P4 as the wake-up's `rung_kind` under the same name, so P4 07 §2.1 lists them all (owed by P4, 04):

| Kind | Where it comes from | Rungs | On a non-working day |
|---|---|---|---|
| `stated_deadline` | a date or a time stated in the mail or the calendar, on the page (P2 `due_dates()`) | 7 days, tomorrow, today, passed (local days); an instant fires at its minute | as stated |
| `window_end` | a due stated as a week or a window ("this week", "next week", "by month end"): the window's last local day (the company week of §2.7), with the stated words as its reason. Rolling = a window whose end is recomputed each local day from the stored words. A due with no date at all ("anytime") is no entry | 7 days, tomorrow, today, passed | the stored rule |
| `our_date_soon` | a stated date of ours | when it comes within 7 days, and again at its surface time (P5 D-P5-1) | as stated |
| `surface_time` | a card's act-by less the effort and the dependency's lead (P5 07 §6.2) | at the instant (minute grain) | as stated; the next working morning when the step is flagged `working_hours_only` (a call to an office, `c1`; the flag set by P5 on the step) |
| `stated_slot` | a slot stated in a mail inside a longer calendar event (the review's 11:30–12:00 inside 10:30–13:00) | at the slot's start and end; the event's own window only as a fallback | as stated |
| `event_end` | a calendar event's end, always written for the situation the event belongs to, apart from any `stated_slot` entry (which may fire earlier); its wake also puts the goals whose plan step waits on the meeting in step 5's touched set, once (§3.7) | at the end instant, minute grain | as stated |
| `expected_by` | an expectation of a reply or an act: from the party's own pace at 5 or more independent instances (`p.reply_time`); below that, the stage's prior (P3), basis `stage_prior` ("sparse, n of 5"); with neither, the day ladder: 7, 14 and 30 days from the ask, active only while the ask is open and its stop rule has not passed. The basis shown names its n and the lag | the date; on the day ladder, one rung each | the next working morning |
| `stage_overdue` | `t.days_in_stage` past the stage's typical duration (P3's stage priors) | the date the stage passes its norm | the next working morning |
| `threshold` | a situation type's day-count rule (P3), set when the situation starts (`i3`: 15 days after a meeting with no follow-up); counted in calendar days unless the rule states working days | the date | the next working morning |
| `decision_deadline`, `notice_date` | P4's tools (`d.decision_deadline`, `d.notice_date`) | 7 days, tomorrow, today, passed | as stated |
| `window_shrinking_at`, `irreversible_near_at` | P4's time states, computed by its tools: the deadline less `d.recovery_window` and the preparation lead; `m.point_of_no_return` less N days (seeded at 7, P4 07 §2.2) | the instant, once (§4.3) | as stated |
| `verify_by` | the page's verify date: P4's `d.verify_by`, from the done-when and the capability's typical lag (P3), by default 3 working days after an act was reported done. When it passes with the source read through and no proof, the check-in turns "not verified", never closed, and one judgment is woken; with the source partial it reads "unknown" | the date | the next working morning |
| `next_check` | a waiting card's next check (P5); a date with no time is the start of that local day, unless the founder or the card gave a time | the instant | as stated |
| `auto_close` | a quiet wait's close date: the last move of either side plus the playbook's `stop_rule.maximum` (P3), in the rule's unit, or an auto-close date the evidence states; provenance `rule` with the rule's id; superseded at every new last move (`b3`: 24 Jul plus 100 calendar days = 1 Nov). Whether it closes by code or asks "close, or one last move?" is the rule's `on_stop` (§8.1) | the start of that local day | as stated |
| `snooze_return` | Later's or Not now's return (a Not now with a date), resolved on the company clock to one instant: in 4 hours from `eval_time`; tomorrow at the delivery hour; in 3 days; after an event = the event's end, stored with `follows` so it moves with the event ("after the panel" = 12:00); a picked date with no time = the start of that local day, so the return is judged before the day's first delivery | the instant | as stated |
| `lease_end`, `embargo` | a lease on the page (P2 §5.4): its `expires_at`, or its `expires_on_event` resolved through `follows`. "GeniOS waits 3 weeks" after a send is an `embargo`; a lease of N weeks ends at the send instant plus N × 7 days, in local time (`i1`: 23 Oct plus 21 days, Fri 13 Nov). The entry keeps the lease's `on_expiry` (raise, close, recheck), and the wake-up's detail carries it for P4; P1 acts on none of them. While an embargo is active it holds back its subject's clock wake-ups (§3.6 step 2) | the instant | as stated |
| `ladder_rung`, `execution_check` | L4's reminders, escalations and `next_check_at` | the instant | L4's rule |
| `outbox_due` | a held interruption's window opening (P5 07 §6.3). Its wake-up makes no `run_subject`: P1 fires the instant, calls P5's delivery step (which re-checks `still_open` and moves the card from held to budgeted or to the digest) and records it on the ledger. Whether anything is sent is P5's lane rule: a waiting card writes no `outbox_due` entry (`f4`, `b3`: no notification) | the instant | P5's rule |
| `goal_due`, `renewal` | a goal's due date (`target_by`); a dated renewal (`c2`) | 7 days, tomorrow, today, passed | as stated |
| `prediction_due` | a stored prediction's `by` date (P2's `predictions`, P2 07 §7.5; P4 07 §17.3), claimed by Maintain's nightly scoring (§8.1 step 4), never by the hourly sweep | the date | as stated |
| `number_outside_band` | the nightly `q.anomaly` over the counts a page cites (P4 07 §12.1); the entry keeps the last band state per page and count, wakes only on a change from in band to out of band, and resets when the count returns | once per crossing | — |
| `date_unknown` | a date the subject needs and nobody has stated: a goal whose due is not set, "asap", "ongoing", or a date not in the evidence (G-19E3CB, G-1A13D6, G-19F807, G-1A15CC; "next cohort, date not in the mail"), with its reason as text. It is never replaced by a default number, and gives no day count: days left come only from a typed date, never 0 for an unknown one. Its owner asks the founder (a question card, P5) or watches a public source (an EvidenceNeed with a cost cap and a cadence); an unanswered question is re-asked every `reask_every` up to `reask_max` (from the policy row, §11.1: 7 days and 3 by default), then shown as unanswered. The answer replaces it with a dated entry and its rungs | none: it fires no rung; its re-ask is Maintain's (§8.1 step 1) | — |

**The last column is a default, held as data:** each kind's non-working rule is a row `clock.py` reads, never code, and a tenant may set its own per kind on its policy row (`non_working_rules`, §11.1); each entry keeps the rule it was written under (§4.2). The unit of every lead time, stage norm and ladder day (calendar or working days) is a field on P3's stage priors or on L4's ladder row.

### 4.2 · The entry

| Field | Meaning |
|---|---|
| `org_id`, `subject` | the situation, goal, card, execution or lease it belongs to, with the version it came from |
| `trace_id` | the trace id of the newest member evidence that version rests on, copied from the writer (§3.3) |
| `seat`, `visibility`, `schema_version` | the seat whose evidence set it, the narrowest visibility of that evidence, and the row's schema version (§13.1) |
| `kind` | §4.1 |
| `grain`, `at`, `local_date` | `minute` with `at` (an instant with its zone), `local_day` with `local_date` (a whole local day), or `none` for `date_unknown`. P2's `due_dates()` passes the grain from the source text, not from the stored instant; a validator rejects an entry carrying both `at` and `local_date` |
| `provenance` | mail text (with the quote's evidence id), calendar, founder, rule (with the rule's id), or tool; and `set_by` |
| `basis` | for an expected-by date: `stated`, `pace (n=…)`, `stage_prior` (with "sparse, n of 5" when some instances exist), `day_ladder`, `founder` or `relative`, mapped to P2 07 §4.3's basis: `stated`, `founder` and `relative` as named; `pace` to `cadence`; `stage_prior` to `playbook`, with "sparse, n of 5" kept as display detail; `day_ladder` to a new P2 value `day_ladder` (owed by P2, 04) |
| `non_working_rule` | the rule it was written under (§2.4, §4.1) |
| `next_rung`, `next_rung_at` | the next rung not yet fired, and its instant |
| `useful_until` | the instant until which a late fire still helps, set by the producer: for a surface time, the act-by or the event's start; for a ladder rung, L4's rule; for a day rung, the end of its day (§4.6) |
| `card_due` | true on the one entry that is its card's due (below) |
| `state` | `active` · `superseded` · `removed` · `done` · `suspended` (its domain deactivated: it fires nothing until reactivation, §11.4) |
| `follows`, `offset_minutes`, `offset_source` | for an event-relative entry: the event it follows, the offset (start minus N, end plus N) and where the offset came from (the host's request, a rule, the founder: `p1`'s 11:20 is the 11:30 start less the host's "10 mins prior"), so it moves when the event moves |
| `owner`, `reask_every`, `reask_max`, `asked_at`, `asked_count` | for `date_unknown`: who resolves it (`founder` · `public_source` · `none`) and its re-ask cadence (§4.1) |

**One due instant per card:** each card has one entry marked `card_due`: the card's `by` as P5 types it, the earliest not-yet-passed one of its page: its act-by for a decision, conflict or question card; its next check (`next_check`) or close date (`auto_close`) for a waiting card; its window end (`window`, `rolling` kept) for a window; none for `anytime` (surfaces read "anytime"). A waiting card's next check is its `card_due`; surface times and reminders are rungs that fire drops and never become the due. Every surface (the banner, the Next pill, the goal line, the approvals row) reads that one entry through one read, and all move together when its instant passes: to the next `card_due` when a later act-by exists, else every surface reads "passed" (the ideal's `p1` shows 11:20 in one place and 11:30 in another).

### 4.3 · Rungs

- **For a date:** more than 7 days, within 7 days, tomorrow, today, passed, counted in local days. Each crossing fires once.
- **For an instant:** at the instant, at minute grain.
- **One vocabulary:** the same rung is used by the wake-up, by P2's fingerprint (a rung, never a value, so an hourly tick re-judges nothing), and by P5's surface time. Today the fingerprint uses hour offsets (−24, 0, 24, 48 and 168 h) while the plan named local-day rungs; they become this one list.
- **A ladder for a deadline,** not a single date: `c2`'s renewal on 29 Oct is raised, decided by Wed 28 Oct, and the day itself, each a rung.
- **A time state is a rung too:** P4's `window_shrinking_at` and `irreversible_near_at` instants fire once each, and `passed` is the breached state, so a situation crossing into any of them is judged with no new mail.

### 4.4 · Who writes entries

- **P4, at step 12 of every run** (`wake_on`, `due_dates`), inside the subject's savepoint with its receipt, in the sweep that judged it (P4 07 §2.7; §5.2). This includes a `threshold` entry in the run that opens the situation, from P3's day-count for its type; an `auto_close` entry in the run in which the wait starts, from P3's stop rule; the time-state instants (§4.3); and, after a reported send, or a sent mail read in the evidence (the founder's own), in a wait-for-reply situation, one `embargo` with its `lease_end` (the capability's wait) and one `expected_by` (basis pace or prior). Until then only what §3.6 step 2 lets through wakes that situation.
- **P2,** from a page's dates and open loops (`due_dates()`, which includes `wake_on.at`), and from leases. P2's goal door, when a goal's due is set or edited, or the goal is dropped or reached, writes, supersedes or removes its `goal_due` entry. From each stored prediction's `by` date (`predictions`, P2 07 §7.5), one `prediction_due` entry, superseded if the date moves, `done` when scored.
- **P5,** from Later's returns, waiting cards' next checks, the surface times, and the outbox's held windows. P5 marks the `card_due` entry when it writes the card's `by`; P1 moves the mark to the next not-yet-passed `by` in the same read when the instant passes.
- **L4,** from its ladder rungs and next checks.
- **The calendar,** through L1: every event's start and end, moved or cancelled with the event.

### 4.5 · Superseded, removed, cancelled

- **A changed date makes a new entry;** the old one is `superseded`, so the history keeps both.
- **A resolved, merged or rejected subject removes its entries,** and its pending clock wake-ups are cancelled (§3.6 step 2). A dropped or reached goal removes its `goal_due` entries and cancels their wake-ups. New evidence on a resolved or auto-closed situation still wakes it within its `reopen_window` (§3.6 step 2), and P4 may reopen it through an L2 `reopen`; its `auto_close` entry is then superseded.
- **A cancelled or moved meeting** removes or moves the entries that follow it (4 of the 8 meetings after 23 Oct are cancelled in the copy). On a move the old entries are `superseded`, the new ones keep their offsets and each fires once at its new minute; a rung that fired before the move never fires again (§3.4).
- **A date that no longer counts never fires:** an entry whose source stated date has `valid_to` or `replaced_by` set (P2 07 §4.2), a `stated_slot` already past that no later mail restated, and a fact P2 marks stale are `superseded` or `removed` on admission. None fires a rung, or counts as missed or overdue (a stale July "confirm a slot" whose move is theirs fires nothing); a slot restated later fires on its new date only.
- **A date older than the subject's stop rule** is handled once by Maintain: closed (§8.1 step 2) when the situation is quiet, done or not owed by us; replaced once by a `date_unknown` entry (reason: older than the stop rule; owner `none`, so it fires no rung and is never re-asked) when it is live and owed by us. Either way it writes no wake-up, and never keeps waking its subject or holding a card (P5 G-9: 37 of `b2`'s 63 cards stand on dates from January to August).

### 4.6 · The producers

- **A minute-grain scheduler** fires instants: surface times, event ends, slots, snooze returns, next checks, lease ends, time-state instants, ladder rungs, outbox windows. A date-only snooze return is an instant at the start of its local day. Day-grain entries (`local_day`: `auto_close`, day rungs) belong to the hourly sweep. It claims what is due with a lease and writes the wake-up within 2 minutes of the instant (§15.2); a later claim records its lag and alerts (§15.3).
- **An hourly sweep** writes and fires the day rungs crossed since its last run, in local days, so a rung that crosses at local midnight is woken within the hour and judged within 2 hours (§15.2). The 06:00 pass only catches stragglers and schedules the day's timed rungs; it is never the first chance for a midnight rung. Prediction dates are left to Maintain (§8.1 step 4).
- **A forced pull before a timed wake:** when a timed wake's answer depends on a source (did they reply before `f1`'s 11:10?), P1 asks L1 for a pull of that source first, waits for it within a bound (60 seconds by default, per tenant on the policy row), and records how far it was read; if the pull fails or times out, the wake proceeds with "source not read through".
- **Catch-up after downtime:** a rung missed while the worker was down fires late only while `eval_time` is at or before its entry's `useful_until` (`p1`'s 09:00 drop at 09:20 still helps); otherwise the wake-up is written `missed` with reason `past_useful_until`, and the entry's next rung is computed (`f1`'s 11:10 drop is useless at 11:40, after the panel's 11:30 start).

### 4.7 · Coverage of the index

- **Nightly** (§8.1): every open situation, loop and goal with a known date has an active entry; an open situation with a known deadline and no pending wake-up is a defect, alerted (Atlas III.6). A date that no longer counts (§4.5) is excluded from the check.
- **Integrity:** a situation in `awaiting_evidence` with no open need, a deadline with no rung, a resolved situation with no outcome link are each found, listed on the nightly run row and alerted (§15.3).
- **A report** of the index's coverage at a replay's start: `f1` (11:30), `f2` (24 Oct), `b1` (24 Oct), `c1` (26 Oct), `f4` (26 Oct 10:00), `c2` (29 Oct), `l1` and `b3` (1 Nov) are all present.

### 4.8 · History never fires the past

- **While Onboard reads history,** an entry whose instant is before the run's `eval_time` is recorded as passed, never fired: `f2`'s reminders of 8–9 Oct, `i3`'s 8 Oct call and `h1`'s offer of 5 Aug fire nothing on day one. Only the present state of each situation is judged and delivered.
- **Recorded as passed does not mean unjudged:** phase 4 judges each live situation once at `eval_time` (trigger `new_evidence`, `change_kind = first_look`), so a promise overdue on connect day, a relationship past its stop rule and a condition now true each get one first-look judgment, never one per missed rung.
- **A replay** fires each entry when its replayed instant is reached, never before (§14.1).

### 4.9 · Today

No date index exists. The date logic that exists is scattered: the expert pass diffs its rungs when a chain runs; the L2 fingerprint has hour offsets; card expiry and snoozes and execution checks are swept on the heavy tick. 495 of 1,611 qualified signals carry a due date; 42 came due in the week; none woke a judgment ([01](01-WHATS-EXACTLY-THERE.md) §1.2).

---

## §5 · Evolve

### 5.1 · When it runs

- **On every wake-up** (§3), after the 10-minute quiet window for evidence (D-P1-1), at once for an act (§7) and at the instant for a timed rung (§4.6).
- **A day rung within the hour:** a day rung crossed at local midnight is written and fired by the hourly sweep in the hour after the crossing (§4.6), so its situation is judged by 02:00 local with no new mail, inside the 2-hour promise (§15.2).
- **A daily pass at 06:00 company time** (§2.5): the day's timed rungs scheduled, the morning's drafts, and any day rung the hourly sweep has not fired (a straggler; the pass is never the first chance for a midnight rung), so that the 08:00 brief and the first delivery (09:00 on the ideal's day) find the work done.
- **Nothing else.** No bare tick runs Evolve; a tick only claims wake-ups that are due.

### 5.2 · One run, in order

A run takes one tenant's due wake-ups (at most 10 subjects, §5.4) and does, in this order:

| # | Step | Owner | Model calls |
|---|---|---|---|
| 1 | **Evidence.** What capture has landed is the input. Before a timed wake whose answer depends on a source, a forced pull of that source, bounded in time, its read-through recorded (§4.6) | L1 | 0 |
| 2 | **Identity and place.** P2's party merges and identity links that code can confirm run first (0 calls), so two spellings of one person are one party before any situation that needs them is judged (`b3`). Then a mail in a known thread with no new party joins its situation by continuation; "no new party" is P2's continuation check against the thread's known parties, and any new party, or any doubt, goes to P4's placement call (P4 07 §10), never to a code rule. A batch not yet placed (one wake-up per connection, §3.5) is turned into subjects here. A new introduction offer becomes its own situation with its own yes or no; a broadcast to many recipients joins the one situation that holds it (§3.5) | P2 (identity, continuation), P4 (placement) | 0, else 1 per batch |
| 3 | **Situations.** For each touched situation: P2's rule transition first (§3.6); the domain check of §3.6 step 1 on the placed subject, with the wedge check beside it (`not_in_wedge` when the policy row's `capability_allowlist` is not empty and the subject's capability is not in it, §11.3 step 7); then, if a judgment is needed, P4's sweep (`l2_pass`) with the touched subjects, which calls `run_subject` per subject with its `ReasoningRequest` (trigger, `rung_kind`, `change_kind`, `eval_time`, budget, and `viewer`: the wake-up's `seat`, or the page's audience when it has none, §3.3); the loops never call `run_subject` directly. A subject never runs before one it cites or depends on (P2's links): one whose cited subject is in the same sweep waits for the next dependents round (step 4) and reads the admitted version (`f1` after `p1`, reading `p1`'s new conflict); the rest go in priority order (§9.3). Every wake-up that reaches a subject produces a request with a request id, so "no run" and "gated" stay distinguishable | P2, P4 | 0–3 per subject (P4 07 §2.2) |
| 4 | **Dependents.** After each admitted version, P2's `dependents(work_id)` are marked dirty and re-run until no version changes, at most 3 rounds, with a non-convergence receipt naming what stayed dirty and the cap; never a second full sweep (P2 07 §10.3). A dependent's re-runs count toward that subject's 3 calls for the trigger chain (keyed by `trace_id`, P4 07 §2.5), never a fresh budget | P2, P4 | as step 3 |
| 5 | **Goals.** The touched goals are exactly: the goals linked to a situation whose stage, status or outcome changed in this run; the goals linked to a situation in which a delegated send turned verified (§7.2); the goals whose plan step waits on a meeting whose `event_end` fired in this run (§3.7); and the goals woken directly (a `goal_changed` wake, once, for any change but a drop, its linked situations re-checked in step 3; news; a `goal_due` rung on `target_by`, the founder's answer to one of the goal's questions, the weekly pass; §3.7). Their pages are written (P4 07 §9.2) before any card; a goal whose linked set did not move and has no such wake makes 0 calls (the fingerprint) | P4 | 0–1 per goal |
| 6 | **Cards.** P5 opens, versions or closes cards from the admitted page versions and goal versions, last | P5 | 0 (the card writer's call, when on) |
| 7 | **Schedule and close.** Each subject's next wake-ups (step 12 of its P4 run) are written into the date index inside that subject's savepoint, in the same transaction as its receipt, in the sweep that judged it (§4.4); step 7 marks the consumed wake-ups done, in the last sweep with the card step's writes, and closes the ledger row (§10) | P1 | 0 |

**One transaction per sweep** (P4 07 §2.7, unchanged): every subject's result is computed first; no write happens during a model call; then all are applied through P2's door with one savepoint per subject. **An Evolve run is several sweeps, in order:** the situations sweep (step 3), each dependents round of step 4 as its own sweep (at most 3), then the goals sweep (step 5), with the cards (steps 6 and 7) made in the last. Each is its own transaction, so the next sweep reads committed versions (`f1`'s round reads `p1`'s admitted conflict). A subject that comes back `stale_read` is re-queued once against the new version; stale a second time, it is parked (reason `stale`, "stale twice") and never run a third time; a change of the tenant's revision alone never makes a run stale. **Each model answer is kept the moment it arrives,** outside the sweep's transaction, in P4's answer store keyed by (subject, input fingerprint, `eval_time`). A crash loses only the writes of the sweep in progress, never its answers: the run's earlier sweeps stay committed, the open sweep's subjects are re-queued, and each applies its stored answer at 0 calls; only an answer that never arrived is paid again. A rerun after a commit finds the page version present and the fingerprint unchanged, and judges nothing; its card step still takes every admitted page or goal version of the tenant that no closed run's card step has taken (read from the ledger), so a crashed run's committed pages get their card exactly once.

**An `outbox_due` wake-up is not a run of these steps.** It makes no `run_subject` and no model call: P1 calls P5's delivery step, which re-checks `still_open` and moves the held item to budgeted or to the digest (P5 07 §6.3); P1 only fires the instant and records it on the ledger, and writes no card itself (§0 rule 4).

### 5.3 · What a run never does

- **It never starts a later step for a subject while an earlier step for that subject is pending** (Atlas II.0).
- **It never edits a card in place:** a card changes only by a new version from a new page version (P5 07 §7.5), and the card step wakes only when a page version changed, or finds an admitted version no card step has taken yet (§5.2). Closing or snoozing a card, in Maintain or by a founder act, changes its state, never its words.
- **It never quiets a flapping card with a formula.** A card that flaps is quieted only by P4's material-change gate and P5's version rule. No policy row, switch or fallback makes a formula or a code rule decide in the model's place; `off` stops a loop, it never substitutes an answer.
- **It never re-judges because something unrelated moved:** a pack, a unit, a law, a pattern or a tool changed, rejected or withdrawn at minor or major re-judges only the pages whose last receipt cites it, and the subjects that last abstained for that gap, queued in Maintain (§8.1 step 8) and never in Evolve; an authority (org) revision marks only the subjects whose last receipt pins it or whose fingerprint inputs include it (queued the same way), and an accepted claim only the subjects it reaches through P2's dependents and the fingerprint, with no wake-up of its own; an accepted company-page line reaches only the situations P2 names as its receivers (open loops owed by us sharing the line's topic or metric, in any state, P2 07 §10.2 item 5) and those whose last receipt cites the line, once per change, as news (§3.7). A marked subject is re-run only if P4's material-change gate says so; the rest keep their result at 0 calls. A policy-row change re-judges on adoption, one tenant at a time; a patch version re-judges nothing (P4 07 §2.6; P3 07 §8).
- **It never runs a whole-company pass.** Those belong to Maintain (§8).

### 5.4 · At most 10 subjects a sweep

- **A sweep takes at most 10 subjects** (P4 07 §2.7), chosen in priority order (§9.3). The rest stay pending with a watermark, are listed on the run's row as skipped with `sweep_cap`, and are claimed by the next sweep, which starts at once if work remains. Nothing is dropped. A subject that ended `incomplete` for its budget is not carried this way; it returns only as §9.5 says.
- **Urgent work never waits for a sweep's end.** A class 1 wake-up (§9.3), a timed rung, and any subject at severity 3 or 4 (`severity`, §3.3) is claimed first, in a sweep of its own; its result is applied and handed to P5's card step as soon as it is done. A sweep of one never counts against another sweep's 10 and is never carried by the cap. Only lower-severity work shares a sweep and waits for its end.
- **The same holds for Onboard,** whose waves are worked through as successive sweeps of 10 (§6.2).
- **A subject that fails** (refused at the per-call ceiling, too large, malformed twice) is parked with its reason after P4's ladder (§9.6) and never holds the watermark for the others (today one oversized file refused 31 times holds L2's watermark at the first bundle, [02](02-WHATS-FAILING-AND-WHY.md) F16).

### 5.5 · The work P2 asks to be re-judged

P1 schedules, as wake-ups in priority order, the re-judgments P2 names: pages left `incomplete` after a contract change; works affected by an evidence withdrawal; works restored by `revert_run`; situations whose importance P2 re-opens (a linked goal at risk, three or more new members, a new `evidence_for` or `blocks` link); and situations P2 refreshes (a member's text recovered or promoted, a founder answer that cites the situation, a newly connected source placing items in it through that source's Onboard wave, a merge absorbed) (P2 07 §5.2, §20). The list is exactly P2's: a test compares the two, so a name P2 adds is added here.

### 5.6 · Costs and the quiet day

- **A quiet day** is one with no new evidence that places into or changes a situation, and no rung crossed; mail absorbed by continuation or the fingerprint with no material change counts as no change. **It makes 0 model calls,** writes 0 versions, and still writes its ledger rows (the daily pass and the date sweep, each saying "nothing due"). It reads only the date-index rows due by now and the pending wake-ups, each by index; the run row records its statement count (§10.1).
- **An unchanged subject writes only its one receipt** (termination `unchanged_gate`, P4 07 §16) **and no other per-subject row** (no page version, no audit row, no admission-log row, no new date entry: its entries stand); it is counted on the run's row.
- **An Evolve day stays under $0.50** for a founder-size tenant. At about $0.016 a judgment that is about 30 judgments; the replay's busiest day (27 Oct: 46 new threads, a broadcast to about 33 recipients ([10](../10-ACCEPTANCE.md) §3), a goal reached) must still pass, with placement as the main load, and makes at most 5 judgments, counted from the ledger apart from the placement calls (P4-12's done-when).

### 5.7 · Today

The chain runs the whole company on every call (97 min, 69 of them org-wide passes), then `run_all`'s three card makers. `process_pending` repeats every org-wide pass on every call by design. Judgments run one after another inside the chain. There is no step that places new evidence into a situation, no dependents' fixed point (only a whole-company state hash compared across sweeps), and no one-transaction sweep ([01](01-WHATS-EXACTLY-THERE.md) §1.4, §6).

---

## §6 · Onboard

### 6.1 · The phases

Onboard is one run per phase, each a checkpoint with a ledger row. It runs for a new tenant, and again for a new seat or a new source (§6.5).

| Phase | What GeniOS does | What the founder sees | Target, from connect |
|---|---|---|---|
| **0 · Connect** | OAuth; the tenant's rows created from defaults: the company page, the policy rows, the activation rows, the model-policy rows (§11.6). The time zone asked at signup or taken from the browser. **Capture policies off** for every seat and source not turned on (Screen off by default); reading starts only for what is on, and the ledger records which | "Connected. Reading your last 30 days first" | 2 min |
| **1 · The last 30 days** | Capture of wave 1: the last 30 days of mail, and the calendar from 14 days back to 14 days ahead, newest first (D-P1-10); several mailboxes in parallel (§6.5) | Mails read, as a count | 30 min |
| **2 · Who you are** | The company page: name, our addresses, the time zone (confirmed here; pre-filled from signup or the browser, never inferred from send hours), what the company does, the founders, `customer_kind`, jurisdiction; the minimum organisation record: seats, owners, the reporting line (`seat_responsibilities.reports_to`), channels, approval thresholds, critical vendors (about 10 minutes of the founder's time; L4's routing is not marked ready until the minimum is there) | "This is how we understand your company": confirm or correct | 35 min |
| **3 · Who is who** | The parties | — | 40 min |
| **4 · Your work** | The situations in wave 1, placed and judged: ours first, then the nearest dates. Each judged in sweeps of 10 (§5.4). Relationships, commitments and conditions held by about minute 40, the first situation admitted by about hour 1 (both measured) | "N things in motion", by kind | 90 min |
| **5 · Your goals** | Goals proposed from the situations, each with its target, its evidence and the situations that serve it, labelled "proposed" (at most 10 in the first week, then at most 3 a week, P4 07 §9.1). The founder's first-screen priorities are captured as Adaptive leases with an expiry (P3); the behaviour brain starts observe-only | "We think you are driving toward these": confirm, edit or drop | 100 min |
| **6 · First intelligence** | Cards from the pages and from the goals' missing steps, only those that need the founder now, ranked (P5). **The first brief** at about hour 2, at most 3 items, each with its evidence and coverage, the first day's only interruption (P5 D-P5-17), pushed only once the zone is confirmed (§2.1) | The first cards, and the first brief | **2 h** |
| **7 · History** | Wave 2: the rest of the window (up to 365 days), captured in the background, newest first; older threads placed into the situations already found, or into new ones; only the situations history changes are judged again; the goals refined. **No rung for a date already past fires** (§4.8) | "Reading your older history; it may sharpen your intelligence" | **24 h** |
| **8 · Daily life** | Evolve on each wake-up; Maintain at night; the brief at 08:00 company time; the normal interruption budget | — | from day 2 |

**The rules of the phases:**
- **The zone before judgment (phases 2 and 4).** Judging starts once the zone is confirmed or the browser's zone is accepted. If neither has happened by minute 60, wave 1 is judged with the zone marked unconfirmed (no "today" or "overdue" from UTC, §2.1), and every situation judged that way is re-queued as one wake-up when the zone is confirmed.
- **Placement in bulk (phase 4).** Placement runs as batches of one compact line per thread, grouped by counterparty, to P4's placement call, which proposes works `{title, kind, members, status, parent}` (the parent for an introduction's child); P2's door admits them; each admitted work becomes a wake-up for its first full judgment, in the order of §9.3. The same bulk mode runs for a new seat or source (§6.5) and for any large backfill (a window extension, or more threads than the policy row's `bulk_threshold`).
- **What wave 1 cannot see (phase 4).** Every wave-1 request carries the per-source coverage ("mail read from <date>"), so the page and its card say "History before <date> not read" (P4 words it, P5 shows it). An open ask or commitment judged in wave 1 whose answer needs older evidence (`p1`'s traction values, months old) raises an EvidenceNeed (`BACKFILL_WINDOW`, capped, §3.8), and L1 fetches that thread first, ahead of the rest of wave 2.
- **Goals (phase 5).** A pass that proposes zero goals does not end the phase silently: its ledger row carries the reason, the first screen shows "no goal found yet", and goal proposal is retried at the next weekly pass (§8.2). The first-screen priorities are leases the founder stated, expiring by default at the end of the stated quarter, else after 90 days (P3 owns the rank, P2 stores it); the Adaptive-leases switch (§11.2) governs only leases learned from behaviour.
- **History (phase 7).** Wave 2's capture starts once the founder has confirmed the window, or once the stored default has stood until phase 6 wrote its cards (§6.2), and its judging only after wave 1's cards are written; it runs in the onboarding lane (§12.3), below any Evolve or Act wake-up of the same tenant. A situation history does not change gets no new version and 0 calls; one it changes gets one version carrying what changed and why; a change to a wave-1 card is a new version of it, never a hold-back. Then goals are proposed again from the changed situations, under the same caps: at most 10 proposals in the first 7 days from connect, across both waves and the weekly pass, then at most 3 a week; each stays `proposed` until the founder confirms. `i6`, `s1` and `s2` rest on mail older than the 30 days, older even than the copy (which starts on 25 Apr): no wave-1 card can carry them, and they wait for wave 2's 365 days ([10](../10-ACCEPTANCE.md)).

**"Ready" shows only when phase 6 has written its cards, or the reason it wrote none** ("378 situations judged: all waiting, quiet or outside the window read"), **and the activation row of every live domain and the minimum organisation record** (seats, the reporting line, channels) **exist;** otherwise the first screen names what is missing. **No card of any lane,** a placeholder or an old lane's, reaches a tenant in Onboard before phase 6 writes: the old lanes are off for a tenant on the new path (§11.6). The progress row keeps its first start time across a resume (today a resume overwrites it).

### 6.2 · Budget, estimate and order

- **One one-time onboarding budget per tenant** (D-P1-3): reasoning up to $10 for six months of mail, $15 for 365 days, for a founder; at most half to wave 1. It is a hard stop, held through the reservation (§9.2); `b2`'s $8.41 is a measurement, not the ceiling. A team's number is set before its first run: the first Onboard run of a tenant with two or more seats is refused until its onboarding budget and its daily judgment cap are set explicitly and P2's visibility proof (P2-10) has passed for that tenant; a null onboarding budget or daily judgment cap on a tenant with two or more seats fails the policy row's validator. A founder gets the defaults.
- **A dry-run estimate first:** calls and cost per phase, within 20% of the real cost, and the sweeps it needs (the situations divided by 10, rounded up) with the minutes per sweep, so the 2 h and 24 h targets are checked against it. For k seats it prints k, the mail count per mailbox, and a suggested onboarding budget (the estimate plus a 20% margin, from the measured cost per situation and about one situation per five mails); the owner accepts or edits it, and the value is written to the policy row with who set it and when. The estimate is compared with the plan cap's headroom (the plan cap less the first week's Evolve and Maintain holdback); if the suggested onboarding budget exceeds it, the first Onboard run is refused `over_budget` before any spend, names the shortfall, and starts only on a larger plan or a staff override with an audit note (§11.1).
- **The sweep rate:** Onboard's sweeps run back to back, with no quiet window between them; up to 8 of a sweep's 10 subjects are judged at once (`l2_pass`'s concurrency, P4 07 §2.7).
- **The window is the founder's pick,** written through to the connection, 365 days by default for a founder-led company. Wave 1's 30 days start at connect; before wave 2 starts, the founder sees the window (the stored default), the estimated reasoning cost and time, and confirms or changes it. If neither has happened by the time phase 6 has written its cards, wave 2 starts on the stored default; a narrower window set later stops the rest of wave 2 and keeps what is judged. The 24 h target runs from connect either way.
- **At the cap:** the skipped situations are listed (to the founder too), and the daily Evolve picks them up in priority order. Never silently short.
- **The reading of the mail at capture** (L1's extraction, $13.43 of $17.55 from connect to "Ready" today) is metered on its own line, apart from reasoning.

### 6.3 · Checkpoints and resume

- Every phase is a checkpoint. A crash, a deploy or a restart resumes in the phase it stopped in; a situation already judged (its page version present) is never paid for twice; a re-run of a wave never duplicates a situation.
- An onboarding stuck in one phase for more than an hour alerts (§15.3).
- History rebuilds never delete situations or human resolutions, and never re-mint their ids: ids are derived from the subject's key, so a re-run upserts.

### 6.4 · The first screen

Built from the ledger and the source rows, never from a fixed list: per source its state, one of `connected` · `partial` · `expired` · `never_connected` · `not_connectable` (derived from P2's `sources` row and L1's connection record, with a `last_ok` instant; P2's coverage `state` keeps its own four values, P2 07 §2.6), its coverage (`read_from` and `read_through`, the oldest and the newest instant read, and whether each wave completed, §10.1) and when it was last read ("read N min ago", computed at view time from `last_read` with `clock.relative()`, never stored); the threads read; what cannot be read; the goals proposed against those confirmed; and every goal in an explicit state, P2's `proposed`, `approved` or `active` (P2 07 §6.4), each shown as P2 returns it, unmeasured goals as "?", cards with no goal visible as "Not linked to a goal yet". Each milestone's time is recorded on the ledger: connect; wave 1 captured; relationships, commitments and conditions held (target 40 min); the company page shown (target 35 min) and confirmed; the first situation admitted (target 1 h); the first goals; the first cards; the first card delivered; the first brief; everything in the window judged (target 24 h); the first positive judgment (`first_positive_judgment`, time to first value, Atlas V.4): the first founder act on a delivered card that marks it useful or acts on it (acted on, approved, confirmed), read from P2's founder-act row with its `card_id` and written by Act (§7.6). When wave 2 ends, `onboarding_view` also returns the finished-onboarding summary from the ledger (time to first intelligence, time to everything judged, reasoning and reading cost per phase, and what was skipped with its reason), shown to the founder once on the first screen.

### 6.5 · A second seat, a new source

- **A teammate connecting a mailbox is an Onboard run for that seat,** not a new tenant: its window captured; its threads placed into the company's existing situations (or new ones) with the seat's visibility; only the situations touched judged; an item only that seat holds stays private to it (the other seat sees a withheld count with no words); the company patterns gain n. What the company already knows that the seat may see is on the seat's first screen within 5 minutes, with no re-reading (§15.2). The seat or source takes its own line of the onboarding budget, or a time-boxed override (§11.1).
- **Mailboxes are captured in parallel,** one pull per mailbox on its own cadence, so wave 1 takes the longest mailbox, not the sum. If the provider's rate limit forces serial capture, phase 1's target becomes 30 minutes times the number of mailboxes, and the 2-hour target is restated the same way (§15.2).
- **A new tool** (chat, documents, a CRM) is one onboarding wave for that source, a wake-up with the connection as its subject, its evidence placed into the situations already known; no second card is made for a situation that has one.

### 6.6 · What a new tenant gets

From its first day, once the new path is the default (D-P1-9, §11.6): the brain on; the packs that fit the company (the Founder Office and Admin for a founder; Sales and Support only when the company sells or supports); its onboarding budget; Screen and calibration off; learning in shadow. **No row is written by hand.** Until then, a design partner is onboarded by the runbook (relief R6).

Each thing done by hand for the design partner has its replacement:

| Done by hand today | Replaced by | Owner |
|---|---|---|
| The plan state (an internal plan that never expires) | the plan set at signup | P1 |
| The switches, and L2 cards per situation type | the policy and activation rows from defaults (§11.6) | P1 |
| Brief lines naming senders and work | the goals confirmed in phase 5 | P1, P4 |
| Our own addresses (self identity) | proposed at connect from the mailbox's address and domain, confirmed in phase 2 | P2 |
| The history window | the founder's pick, with its estimate (§6.2) | P1 |
| The resync of older mail | wave 2 (phase 7) | P1, L1 |
| The promotion of archived founder mail | P2's promotion path through a need (P2 07 §2.3) | P2 |
| The catch-up budget | the onboarding budget (§6.2) | P1 |
| The categories | Plane D's default lists | P3 |

### 6.7 · Today

Onboarding is the incremental chain with a bigger backlog: no waves, no company-understanding step, no onboarding budget, no first-day goal pass. On 22 Oct the first 14 cards came at 1 h 46 min from a scheduler chain started mid-backfill; "Ready" came at 3 h 39 min through the busy path, with 0 expert reviews and 0 goals; goals came on days 5 and 6 ([01](01-WHATS-EXACTLY-THERE.md) §3).

---

## §7 · Act

### 7.1 · What comes back in

- **Every founder act** (P2 §7.2: Done, It's done, Later until a date, Not now, an answer, an option chosen, a side picked, a correction, a draft approved or edited, a delegation, a goal confirmed, edited or dropped, a recorded decision, Feedback) is stored by P2 as evidence on its situation, with the card version and the page version it was made on, and wakes **only that situation**, with trigger `founder` at the highest priority (§9.3). A press made on a moved card version is refused as stale (P5 07 §10.4) and wakes nothing.
- **A document the founder links or uploads** against a card or a need is evidence a person supplied: stored on that situation, it wakes only that situation, at once and at class 1 (`new_evidence` with `change_kind = evidence_supplied`, §3.5), or as `need_met` when it meets an open need. The same file a second time (same `content_digest`) still writes its request and one receipt (`unchanged_gate`), and costs 0 calls (§3.6 step 4).
- **A question's answer** fans out, under the cap, to exactly its dependents: the situations and drafts P2's `dependents(work_id)` returns, and the goals linked to it (`advances`, `threatens`, `depends_on`); nothing unrelated wakes (the traction number picked on `p1` re-drafts the panel note and the investor updates, unblocks the "settle the number" step on `i1`, `i2`, `i3` and `f1`, and wakes the goals `p1` serves or threatens).
- **Every result:** an agent's result, an L4 execution outcome, a person's Done on a delegated step, each with trigger `outcome`, stored as evidence on its situation (P2 §7.3), and waking only that situation.

### 7.2 · Reported is not verified

- **A delegated send stays `reported` until the sent mail is seen** in the evidence, then `verified` (the check-in states, P5 07 §8.2). A verified send updates its situation and its goal in the same run.
- **After a reported send, or a sent mail read in the evidence (the founder's own), in a wait-for-reply situation,** P4's step 12 writes the one `embargo` with its `lease_end` (the capability's wait) and one `expected_by` entry (basis: pace or prior) (§4.4). Until then no other wake-up prompts a further send; only what §3.6 step 2 lets through wakes the situation.
- **Done never closes a card by itself:** P1 schedules a `verify_by` wake-up that looks for the proof the done-when names; only that proof closes it (P5 07 §8.3). Where no connected source can show the outcome, the person's word ("It's done") is that proof, and a passed date with no confirmation goes to verify, never straight to missed (P5 07 §8.3, §8.7; `f2`). When `verify_by` fires, P2's rule transition runs first (0 calls). Proof found (a document or a mail matching the done-when, never a status field) moves the situation on to resolved through the door. None found returns it to `in_progress`, its card to verify on the first miss (P5 07 §8.3, §8.7), and writes a new `verify_by` entry on the next working morning, superseding the old one; `verify_misses` (policy row, 2 by default) counts the re-armed windows before the founder is asked again.
- **A dispatched agent step with no result** by its timeout wakes its situation with "no result yet". The timeout is stored on the delegation row (24 hours by default for a draft step, set per agent kind) and written at dispatch as a date-index entry of kind `execution_check`. A result that returns after a material page change is re-checked against the current version, or held as "the page changed since the task was given" (P2 §7.3).

### 7.3 · Founder controls take effect at once

A correction writes a locked version; a Later or a Not now with a date sets a locked return (`snooze_return`); "not relevant" closes the work or mutes its card for its scope; an answered question settles its loop and cancels that loop's pending `expected_by` and `stage_overdue` wake-ups (`already_handled`), and its question card stays in place as answered; a question retired as wrong writes no wake-up, and a later arrival never re-raises it in its words (P5 owns the card and the retired hash, P4 the wording); an approved goal moves its linked work up one class (§9.3). A later model pass never overwrites any of them (P2's locks). **A kind-wide correction** in the founder's own words wakes every open situation of that kind as `founder` wake-ups (class 1), nearest deadline first, inside the daily cap; the rest are carried and listed, never dropped.

### 7.4 · Holding a step for its prerequisite

An approved agent step that waits on another card ("runs when you resolve `p1`") is held as a wake-up on that card's resolution; when it fires, L4 dispatches it. If the prerequisite card is dismissed or expires instead, the step returns to the founder with the reason and is not dispatched. P1 never sends: GeniOS drafts, a person approves the exact bytes, L4 executes (P5 07 §10.4). Immediately before each send, as before each rung (§8.4), L4 calls `still_open(work_id, since_version)`; a situation no longer open cancels the send with "already handled: outcome evidence exists".

### 7.5 · Drafts and their words

Every draft, and every card text from the card step (§5.2 step 6), passes P2's `settle_text(text, as_of)`, with `as_of` the run's `eval_time`, before it reaches approval; L4's execute step calls it again on the exact bytes before send (P2's owed row IDEAL-28). The draft task's cost, including a draft made before it is asked for on a high or critical card (P5 D-P5-21), is charged to Act's budget. So is the nudge draft made when a waiting card turns (`f4`, Mon 26 Oct 10:00), although a date rung woke it; it is listed on the run row beside the 0-call rule transition.

### 7.6 · Outcomes go to learning

An act's outcome (acted on, dismissed, settled, late) and an execution's are passed to L6 as labels through data; nothing is armed (§11.2). Each outcome is one append-only label row `{org_id, trace_id, work_id, card_id, outcome: acted_on · dismissed · settled · late, at, due_at, visibility, schema_version}`; late means the closing instant is after `due_at`. L6 reads it as data, never as an arming signal. The tenant's first act that counts as a positive judgment (§6.4) is also written as the milestone `first_positive_judgment` on its Onboard row. **A Feedback or correction that names a reason** ("wrong because") is a `founder` wake-up for its subject whose detail carries the reason and the blamed unit, from the card's receipt pins. In the same run P1 passes it to P4 in the next judgment's request (P4 07 §17.2) and queues it in P3's review queue.

### 7.7 · Today

Card actions are declared no trigger; an answer, a correction or a "wrong" verdict waits for the next chain; `founder_asked` cannot fire; an agent's result wakes only the realtime outbox. In the week: 3 card actions on 22 Oct, their cards still `acted`; 105 executions, 0 completed; 0 decisions ([01](01-WHATS-EXACTLY-THERE.md) §1.2).

---

## §8 · Maintain

### 8.1 · Nightly, at 02:00 company time

Each job a ledger run of its own, in this order:
1. **The date index:** rebuilt and checked (§4.7); every open situation with a known date has its active entry, and every situation with a member newer than `judged_through` has a pending wake-up, evidence waiting its quiet window included (P2's invariant I-13); dates older than a stop rule closed, or replaced by a `date_unknown` entry with owner `none`, once (§4.5). Each `date_unknown` entry with owner `founder`, `asked_count` below `reask_max` and `asked_at` plus `reask_every` passed gets one `maintain` wake-up for its subject (detail: `re_ask`) that asks P5 to re-raise the question; the entry's `asked_at` is set and `asked_count` raised; at `reask_max` it reads "unanswered" and no more wake-ups are written; a founder answer or a `public_source` answer replaces the entry.
2. **Lifecycle, by stop rule, never by a default window.** A stop rule's `close_at` (its clock start, the last move of either side, plus `stop_rule.maximum` in the calendar or working days it states, on the company clock) is held as a date-index entry written by P4's step 12 and superseded on every new last move (§4.4); Maintain wakes, as `maintain`, any situation whose rule passed with no entry. When the rule passes: with `on_stop: close`, P4's `u.stop_rule` closes the page by code with the rule cited, and the awaited party's next mail reopens it; with `one_last_move`, or a rule with no maximum, the situation gets one question ("close, or one last move?"), once. Where no playbook applies, only P2's own rule quiets work (90 days with nothing owed by either side, recorded by name, P2 07 §5.3); no other count of days, today's 45 included, makes work dormant. Nothing is quieted, and no card lapses by time alone, while its situation is live and owed by us or the other side left a door open in writing. A card whose date passed with nothing owed by us closes, with its recorded cause (P5 07 §8.7); every open card whose situation is quiet, done, merged or history is closed with its reason (P5 closes it through its lifecycle, on P1's wake).
3. **Check-in states** are re-evaluated (P5 07 §8.2); waiting cards whose stated date passed close or turn (P5).
4. **Predictions due** are scored (true, false, or unknown with a reason), whether the card is open or closed (P4 07 §17.3). This job claims the `prediction_due` entries whose date passed (never the hourly rung sweep); a miss writes one `maintain` wake-up for the page's situation (detail: the prediction's id, what was predicted, what happened) and one label to L6 (observe-only); a true or unknown prediction writes no wake-up. A verified outcome writes its `prediction_actual` row through P2, once, in the same run (P2 07 §7.5, P4 07 §17.3).
5. **The no-call counts the week reads:** `company_checks()`, `performance()`, `metrics()`, `q.anomaly` over the counts each page cites (waking a page once per crossing, `number_outside_band`), the higher-order and competing-goal candidates (P4 07 §12.1).
6. **The Notebook's jobs per tenant** (P2 07 §0b): the quiet-work rule, staleness marking, leases expiring (each lease past its `expires_at` expires and writes its `on_expiry` outcome), deadline-bound work resolved, thread state, delivery and party-state recompute, retention holds, evidence withdrawals, pattern counts, size per tenant; temporary-item expiry (text dropped at 7 days, `memory_temporary_count` reported) and the context-health row (`context_health()`: the share of facts seen within 7 days, the last touch per party); contract upgrades (pages left incomplete are listed and queued as re-judgments in priority order, P2 07 §20.9).
7. **Held items:** each hold still open is checked against the evidence since it was held; one that now matches its expected items or its EvidenceNeed is retried once (`retry_hold`, §3.8); a retry still held waits for new evidence and never loops. Subjects parked for the provider are recovered here, only as §9.6 allows.
8. **Cited-change re-judgments** (§5.3): for each unit, law, pattern, tool or pack changed, rejected or withdrawn at minor or major, the pages whose last receipt pins it (P4's lookup by receipt pins) and the subjects that abstained for that gap each get one wake-up, trigger `maintain`, `change_kind = unit_changed`; for an authority (org) revision, each subject whose last receipt pins the revision or whose fingerprint inputs include it gets one, `change_kind = authority_changed`; an accepted claim queues no wake-up of its own (§5.3); a patch queues nothing; a policy-row change queues only when the tenant adopts it, one tenant at a time.
9. **Retention** (the platform's retention job, run on this schedule): per `tenant_retention_policy` (P2 07 §14), dossier text and per-event traces older than the policy's days (both rebuildable), promoted Screen deltas, and the old admission log once the old lanes are off are expired, skipping every row P2's retention-hold list protects; the rows freed are recorded on the run row. When the database is over its ceiling this job runs first (§17).
10. **Plane D's per-unit stats** (`expertise_unit_stats`, P3 07 §11).
11. **The card census** (P5 07 §16.2); open cards over `open_card_bound` (policy row, 30 for a founder-size tenant) raise one alert (§15.3), listed with their goal link ("Not linked to a goal yet" when none).
12. **The invariants:** P2's 28 run at the end of every onboarding build (§6), at the start of every replay clone build before its first day (§14.1), after every Evolve day and every replay day, and here every night for every tenant with a live loop row; a failure fails the day (P2 07 §15). I-8 (spend under the cap) is read from the ledger sum (§10.3) against the policy row's cap. An Evolve day ends at the tenant's next 02:00.
13. **The replay sample:** a sample of the day's receipts replayed from stored answers with no model call, giving the same verdicts with the wall clock moved a day later (P4 07 §16). On a change to a check's version, P4 writes one `maintain` wake-up (detail `check_changed`, §3.2; P4 RG-10) and P1 runs the same sample at once, with 0 calls; an unchanged check writes none.
14. **The health row** (§15.1).

The org-wide passes that run on every chain today (period, support, meeting and channel touches, outreach, documents, spend and history, attention, situation refresh) move here, on their own schedule per tenant (relief R2).

### 8.2 · Weekly, on Sunday at 03:00 company time

On the batch API where a model is used, each a ledger run, the weekly key as the claim so a repeat or a second replica does nothing:
- **the analyse pass** over pages, not mail, under $1 a tenant a week (P4 07 §12.2); it re-tests every held learning candidate and every Adaptive lease due in the week (a held candidate is promoted once when new support has come, else stays held);
- **the company patterns'** refresh through admission (P4 07 §12.3);
- **goal proposals** (at most 3 a week; in the first 7 days from connect, the 10 shared with Onboard's waves, §6.1) and the brief drafter (at most 8 lines a section);
- **the goal wake:** one `maintain` wake-up (subject kind `goal`) per `approved` or `active` goal, its linked situations live or not; a goal whose linked set did not move makes 0 calls by the fingerprint (§3.7, §5.2 step 5);
- **calibration, in shadow** (applies nothing until armed by Rohit's decision, W27 D13): it writes would-mute and would-nudge rows per card kind with their counts and changes no card, level or mute; confidence and prediction calibration compared; usefulness per lane; the interruption budgets' would-tune rows, in shadow (P5);
- **the weekly justified-silence sample** (P5 07 §16.3);
- **Plane D's gap backlog and coverage report** (P3 07 §11);
- **the learning pass** (L6);
- **the weekly rollup:** for the company week that ended before the pass (`week(t)` of §2.7 for the previous week, counted from the tenant's `week_start`), one `weekly_rollups` row per tenant with AER and HIR (P2's `aer_hir()`) and the steps per agent (P2's `agent_track()`), each with its numerator and denominator and its delta against the previous stored week, and a week with no agent stored as `no_agents`; no row is written for a week before the tenant's first connection, and a week with no row reads `not_measured` in the view, never 0;
- **the weekly quality line,** per tenant, on the same `weekly_rollups` row, each number from its owner and against its bar: card usefulness (at least 70%) and important-situation recall (P5); the held share (25% or less: subjects ending `held` over subjects judged) and no single no-card reason above 30% of judged files (`judged_no_card` by P5's reason), both summed from `loop_runs` outcomes through the one totals function (§10.3); the cost per admitted situation (P4); the filed share (at least 90%) and meeting coverage (at least 90%) (L1); parity with the ideal (the scorecard, §14.5), read only for a tenant with a labelled set, else "not measured". The bar for usefulness is 70% unless P5's floor (P5 07 §16.2) is higher. A number under its bar alerts (§15.3);
- **the benchmark re-run:** the golden board re-scored by receipt replay, with 0 calls (§14.6).

### 8.3 · The morning brief, on its own job

- **Composed by its own job at the brief hour** (`local_hours`, 08:00 company time by default, §2.5; a seat's own zone only when it sets one), once per seat per local day; the row is the claim, so two replicas compose once. For a seat with its own zone, that zone's local day sets both the brief hour's start and the once-a-day claim; every other use stays on the company's zone (§2.1).
- **Its outcome is recorded every day:** composed, or not composed with its reason. On a tenant's connect day the row is `skipped` with reason `not_due` ("first brief sent") and nothing is composed (the first brief is phase 6's, §6.1). The row stores, for the seat and day, the per-source coverage it read and the counts of threads, meetings and situations it checked and found quiet (from `metrics()`, P5 07 §6.7), so a later view prints the same line.
- **An alert at the brief hour plus `brief_margin`** (30 minutes by default, on `local_hours`; 08:30 for the defaults) if a due brief does not exist.
- **It starts after the 06:00 pass,** so it reads that morning's cards (today it is composed before the day's first card on 3 of 5 days). It waits for the day's daily-pass row to close, at most until the pass deadline (§2.5) or 15 minutes past the brief hour, whichever comes first; past that it composes on what exists, and its row says the pass was not finished.
- What the brief says is P5's (P5 07 §6.7). **Every delivery of the brief** (an email, a chat digest) is an outbox row written by the brief job in the same run, due at the brief's instant; no delivery rides a tick.
- **The brief is composed the same way with `push_brief` on or off** (§11.2); the flag only decides whether an outbox row is written for a seat that did not ask for one. A seat that asked by email gets one outbox row a day either way.

### 8.4 · L4's tick

L4's executive step runs when its rungs fire from the date index (§4.1 `ladder_rung`, `execution_check`), not on the 6-hour tick, as two named calls in a fixed order: plan commitments, then the lifecycle advance of each due execution, both before distribution, so a reminder decided in a run leaves in the same run (Atlas L4). The ladder is L4's: L4 writes one `ladder_rung` entry per rung, anchored at the execution's creation instant, never at its deadline (day 1 notify, day 3 remind, day 7 escalate, day 14 critical, at most 6 rungs), each with its non-working-day rule; P1 fires each at its instant and never computes the days. P1's pre-fire check (§3.6 step 2) runs before every `ladder_rung`, `execution_check` and `outbox_due` wake-up; a stale one is written `cancelled` with its reason and L4 sends nothing; L4 checks again at the moment of send (§7.4). A rung for an absent seat goes back to L4 (P5 07 §15.4). **L4's tick is a ledger run** whose row stores the sweep's `reasons` counts (`no_action`, `window_closed`, and the rest): a tick whose refusals are all benign (`no_action`, nothing examined for want of a live domain) ends `nothing_due`; a tick whose refusals are configuration reasons (`window_closed`) ends `partial` and alerts once a day (§15.3).

### 8.5 · Screen, on its own schedule

Only for a seat with Screen on (Screen is off by default, §6.1 phase 0). The hourly batch and the promoter run only for a tenant with at least one live or shadow domain activation row; for any other tenant the hour writes a `skipped` row (reason `domain_off`) and makes 0 calls. The seconds tier (saving a moment, the remind popup) is L1's. Each job is a ledger run under its own cap (§9.1), on the company clock:
- **The hourly batch, per seat:** over the seat's new moments, P2's keep-or-drop and P4's reason step, on the batch API at half price; kept moments go to L1 through the promoter, as `new_evidence` (§3.2). An hour with no new moment writes a `nothing_due` row and makes 0 calls. A seat's moments stay private to it (§13.1).
- **Weekly:** the five-line persona (P2's `preferences`).

### 8.6 · Today

About 20 upkeep jobs run in series in one thread on the heavy tick, every 6 hours from process start, none with a record of its own. Lapses, dormancy and archiving run on every chain over the whole company. The six patterns fired 0 times in 408 evaluations. The executive sweep runs on the heavy tick: 120 reminders and 94 escalations, 0 completions. The brief is composed at the tail of each sweep ([01](01-WHATS-EXACTLY-THERE.md) §1.2, §6).

---

## §9 · Spend

### 9.1 · The caps

| Cap | Where it is held | Default for a founder |
|---|---|---|
| **The tenant's daily judgment cap** | the policy row (§11.1), `daily_judgment_cap_usd` | the Evolve day's budget: $0.50 for a founder-size tenant ([10](../10-ACCEPTANCE.md) §5's target), never above what remains of the plan cap's period spread over its remaining local days; severity-4 items pass it (§9.2); P4's sites inside it (P4 07 §14) |
| **Reading** (L1's extraction, entity resolution) | the plan cap's period, through the §9.2 reservation, and the sync quota (§11.3 step 3) | metered on the reading line; a manual Sync or `POST /sync` draws on the same line as scheduled capture |
| **The one-time onboarding budget** | the policy row, per wave | $10 for six months, $15 for 365 days, at most half to wave 1 (D-P1-3). Booked on the phase and wave rows and never counted against the daily judgment cap; the plan cap holds back the first week's Evolve and Maintain allowance before onboarding may use the rest; the estimate is checked against that headroom first (§6.2) |
| **Maintain's weekly cap** | the policy row | under $1 a week for every model call a Maintain job makes (the nightly "close, or one last move?" questions, the weekly analyse pass, goal proposals, the brief drafter), stopped in priority order at the cap |
| **Act's budget** | the policy row | the draft task, the delta runs acts cause, and `human_ask` runs |
| **The plan cap** | the policy row, `plan_cap {amount, period}`, set from the plan's `plan_economics` row at signup and on a plan change | the plan's model allowance (Atlas III.8's unit economics), a number P1 reads, never an assumption in a document; the period is a month by default, or the company week (`week(t)`, §2.7), in the company's zone |
| **Screen's checks** | the policy row | 300 a day per seat |
| **The EvidenceNeed fetches** | the policy row | a cost cap per need and per tenant per day (L1's fetch job, §3.8) |
| **The platform's cap** | configuration | above every tenant's caps |

- **`plan_economics`, a platform table, one row per plan:** the model-spend allowance per month, the total-cost ceiling, `price_per_seat_month` and `seats`, and the Atlas III.8 assumptions as fields (situations per team-day, the share that reaches a model, calls per model situation, tokens in and out per call). Billing owns the price and the seats; `plan_economics` holds a copy, read by plan name. A month's total cost past the ceiling alerts (Cap hit, §15.3). Changing the row changes the caps with no code change.
- **A cap's day is the company's local day** (§2.7); a plan period rolls at the company's local midnight.
- **After the replay** (P1-8) the measured cost per judgment is written in 08-LOG; the $0.50 default changes only by a decision recorded there, applied on the policy row at the parity gate. Until that gate the product keeps R-9's $2 a day.
- **Every model call goes through the register** with a per-tenant, per-site policy row (model, thinking, ceilings, fallback; P4 07 §14), with the tenant's cap as the outer limit. A new tenant gets defaults; nothing is set by hand. **A site's own ceiling** reached ends that subject `over_budget` for that site only (P4's termination; the ledger's reason is `cap_hit`); the tenant cap is untouched and the subject is carried.
- **Every automatic job that uses a model has a cap,** Screen's checks and the EvidenceNeed fetches included; a refusal at a job's cap writes a `cap_hit` row and one alert per cap per day.
- **During a tenant's cutover** the old path and the new path have separate budgets, so a weak old card cannot spend what a strong new judgment needs (Atlas L5): a `legacy` and a `situation` spend pool on the policy row, the legacy pool unable to draw on the situation pool or its reserved share; and the day's card allowance (P5's count, today `budget_per_day × active seats` in the old makers) split into a judged share and a legacy share, so a morning of formula cards cannot take an afternoon judgment's slot.

### 9.2 · One cap, held in the database

- **Reservations live in the database,** not in a process, so two runs started together can never both spend the last dollar.
- **Before a call:** a reservation of the call's expected cost, from the measured cost of the same task and size, with a margin (not today's worst case, which is 9.5 times the real cost of a judgment). After the call, the real cost is settled.
- **A reservation must fit every cap that applies:** the day, the plan cap's period, and the onboarding line or the job's own cap (§9.1), with a staff override (§11.1) read through the same path. The reservation row names the cap it draws on, so onboarding never spends the Evolve day and a spent day never stops onboarding. It carries `org_id`, `trace_id`, `run_id`, `visibility` and `schema_version` like every P1 row (§13.1). **The one exception is a severity-4 subject** (§9.3): it is reserved past the tenant's caps (the day, the plan cap's period, the onboarding line), its spend booked on the ledger against the cap it passed, with one alert (Cap hit, §15.3); the platform's cap and a lapsed plan still bind.
- **A timed-out call** is recorded as "unknown, may have been billed", never as $0.
- **The ledger is the spend:** every model call carries its run id; the tenant's spend is a sum over ledger rows.

### 9.3 · The order of spend

When the cap is short, work is done in this order, by code and from written rules (the model never orders work, Atlas II.2):
1. **The founder acted** (`founder`, `human_ask`, `outcome`).
2. **Something is owed by us, or a date is today or passed;** safety items (severity 4: irreversible loss within days, safety, legal, money at scale) are never deferred for budget at all.
3. **A goal at risk or blocked;** the linked work of a goal the founder approved moves up one class (§7.3).
4. **The nearest deadline.**
5. **The stakes:** the stored tier of the last judgment (critical, then high).
6. **The rest.**

**One sort key, from stored fields only:** the class; then L1's triage class of the evidence (P0 to P3); then the stored tier of the last judgment (critical, high, standard; a subject never judged counts as standard); then time to due, nearest first; then age, oldest `due_at` first. Tier and severity are read as stored on the page; no model is called to order work and no model score enters the key. A sweep's choice of 10 (§5.4) and the queue's claim (§12.3) use the same key.

Zero-call work (rule transitions, deterministic units, gated subjects) runs first overall, and costs nothing. Bands 1 and 2 keep a reserved share of the day's cap (60% to start), so a morning of routine work cannot spend what an afternoon's owed item needs (GeniOS-013 U13-23). A subject linked to a live or proposed goal at high or critical tier shares the reserved share only when it is also clock-due (class 2); otherwise it is deliberately left out of it, ranked by classes 3 to 5. **Shadow work** (a domain or a tenant in shadow, §11.4) comes after class 6 and never draws on the reserved share. **A placement batch** is spent in the class of its most urgent thread, reserved at the measured cost of a batch of the same size, and booked on the placement line apart from judgments (§10.1).

**The Atlas's order maps onto this** (zero-call, state transitions, routine, conflict, consequential; Atlas II.2): zero-call work and P2's rule transitions (§3.6 step 3) run first; routine, conflict and consequential are the depths P4 picks inside a run's budget (§9.4; P4 07 §2.2), so they set what a run may cost, not when it is claimed. Between subjects the classes and the key decide, so a short cap never spends on a routine item what a higher class needs. Severity 4 is exempt from both.

### 9.4 · Each run's budget

Every `ReasoningRequest` carries its budget from the tenant's remaining allowance: calls, tokens, tools, retrieval and seconds (P4 07 §2.1). P4 chooses the depth and the calls inside it (P4 07 §2.2); a run that would overrun ends `incomplete`, names the exhausted budget, and leaves the previous page standing. P1 records the calls used.

### 9.5 · At the cap

- **Stop, in priority order** (severity 4 excepted, §9.2). For each subject not judged, P1 sends its request with a zero remaining budget, so P4 writes `abstain` with termination `incomplete` and `exhausted = day` (P4 07 §15). Its wake-up stays `pending`, in P1's carry queue in priority order; only the run's row lists it as skipped (`over_budget`, "think later").
- **An `incomplete` subject is not re-claimed in the same window with the same budget.** Its wake-up's `due_at` moves to the cap's next window (`exhausted = day`: the next local midnight); new evidence or a changed budget brings it back sooner; a truncation adjusts the budget (§9.6) rather than repeating the call.
- **Maintain's weekly cap, when reached,** stops the pass in priority order and lists the pages skipped; they carry to the next week.
- **An alert fires when any skipped item is ours to do** (class 2).
- **Never silently short:** the work done and the work skipped are both listed, with what was carried; the founder's surfaces show an unreasoned owed situation as "not yet judged: budget", never hide it.

### 9.6 · Retries

- **A malformed or truncated answer gets at most one repair,** carrying only the failing part and the error, and its failing field is recorded so P4 can fix the prompt or the schema.
- **A truncation adjusts the subject's budget** instead of retrying the same size.
- **Attempts are counted per input hash, across P4 and P1.** P4 owns the in-run ladder for a timeout or a model error: the original call, then one retry on a narrower packet and on the policy's fallback model, then `abstain` with termination `timeout` or `model_error` and the previous page standing. The repair, the generic-answer retry and this retry share one allowance of one extra paid call per input hash (P4 07 §15 states the combined allowance), so at most 2 paid calls. P1 adds no paid attempt: such a subject is parked with reason `parked` (P4's termination in `detail`) and reaches the daily health report, and it is judged again only when a new wake-up reaches it. P1 re-queues a subject only for a failure that is not the model's (a crash, a `stale_read`, a lost lease), and the re-queue reuses P4's stored answers (§5.2). An `abstain` with open EvidenceNeeds is `waiting_for_evidence`, not a failure.
- **A subject parked for the provider** (`parked`, with `timeout` or `model_error` in `detail`) needs no person. Maintain (§8.1 step 7) writes it one `maintain` wake-up only when its input fingerprint has changed since it was parked, or after a provider-wide outage (the health row shows those failures across subjects, §15.1) once the ledger shows calls through P4 answered again, and then at most once per input fingerprint: the oldest such subject first, the rest in the same run once it is answered. P1 makes no probe call of its own. Otherwise it stays parked, reason `parked`, detail `recovery_exhausted`, with one alert (Work that will not settle, §15.3). A subject parked for any other reason stays parked.
- **No expertise, or a missing capability:** P4 returns `abstain` with a gap row (P3's backlog). P1 closes the wake-up `done`, records status `abstained` with the gap row's id, makes no repair and no retry, and re-wakes the subject (as `maintain`) only when P3's pack pointer for that kind changes.
- **The Screen instant check is not a subject.** P1 never re-queues, repairs or retries it; its timeout or failure writes a counted row, never an error a person sees.
- **Never a payment beyond P4's ladder for the same input.** The target: under 10% of spend on discarded answers (today 39% of the judge's, 44% of all L4 sites').

### 9.7 · What it costs

| | Today's product (measured) | Target |
|---|---|---|
| Onboarding, **once** | $17.55 from connect to "Ready" ($13.43 L1 reading the backfilled mail); $27.78 in the first 24 h | reasoning under $10 for six months of mail (`b2`: $8.41), under $15 for 365 days; reading the mail at capture metered on its own line |
| A normal day | $5.67 ($1.88 reading the data, $3.78 reasoning and cards); the judge capped at $2 | under $0.50 for reasoning |
| Maintain | inside the day above | under $1 a week, on the batch API |
| **A month** | **about $170** | reasoning under about $20 (Evolve about $15, Maintain about $4); reading the data as P2 decides |

### 9.8 · Today

Each model site has its own daily pool, in UTC days; nothing orders spend across sites. The judge spent its $2 in one burst after 00:00 UTC every day and refused the rest, so every card was born between 07:00 and 13:59 IST. 39% of the judge's spend went on discarded answers. The per-org cap stops the pull but not the chain. The notebook's cap is per process ([01](01-WHATS-EXACTLY-THERE.md) §1.5, §7).

---

## §10 · The run ledger

### 10.1 · One row per run (`loop_runs`)

| Field | Meaning |
|---|---|
| `run_id`, `org_id`, `trace_id`, `loop`, `phase` | which loop and, for Onboard, which phase. `run_id` is derived from (org_id, `eval_time`, loop, phase, sequence: the carry or re-queue count), never random: every stage row, counter and receipt of the pass carries it, so a pass is one key read, and re-running the same instant finds the existing row |
| `seat_of_origin`, `visibility`, `schema_version` | the seat or seats whose evidence or act woke it, and the narrowest visibility of what it carries (§13.1) |
| `parent_run_id` | the run this one continues (a carried sweep, a resumed phase, a re-queue) |
| `triggers` | the wake-ups consumed, counted by trigger and rung kind |
| `eval_from`, `eval_to` | the instants judged (a replay's replayed instants) |
| `started_at`, `finished_at` | when it ran, in UTC and in the company's time |
| `code_sha`, `policy_version` | the code and the policy rows it ran under |
| `snapshot_revision` | the L3 revision at the run's start (what its situations sweep reads); each subject entry also stores the revision it read, later than the start for a subject in a dependents round or the goals sweep, which reads after an earlier sweep committed (§5.2) |
| `subjects` | the situations and goals touched, each with: the version before and after; its domain, as P3 and P4 returned it; its `request_id`, `bundle_hash`, `reasoning_runs` id and `eval_time`; `prior_run_id`, the last run that touched it; `door`, P2's verdict (ADMIT, HOLD or REJECT) with its reason; and its own `calls` and `cost`, summed from the call rows with its `request_id` |
| `cards` | each (card_id, version, opened · versioned · closed), from P5. Every page version and card version stores the `run_id` that made it, so the link runs both ways: a card's history and its "What happened" count read the ledger, and its timing stamps are one join away |
| `calls`, `tokens_in`, `tokens_out`, `cost` | from the model calls carrying this run id; with the refused, the repaired and the discarded counted apart. Split by line: reasoning (with placement on its own line, apart from judgments) · reading (L1's extraction, entity resolution, Screen) · other. Cost is stored in USD; the display currency is applied at view time. Each call row (`llm_costs`; `notebook.runs` in the notebook) carries its `run_id` (a subject's call also its `request_id`), its `stop_reason`, its `output_tokens` and its outcome (`kept` · `repaired` · `discarded`), so the share of spend on discarded answers is a sum (§9.6); a receipt's calls, tokens and cost are read from the call rows with its `request_id` |
| `model`, `units` | the model per site (from the call rows or the receipt pins); the units that ran and that were declined, counted from P4's receipts |
| `reads` | the database statements the run made (a quiet day's handful of indexed reads is a measured number) |
| `counters` | the five pipeline counts of this run (§10.4) |
| `outcomes` | the touched subjects counted by how they ended, from one closed list: `judged_card`, `judged_no_card` (with P5's reason), `held`, `refused`, `truncated`, `carried_budget`, `fell_back`, `budget_exhausted`, `gated`, `abstained`, `domain_off`, `shadow`, `parked`, `requeued`; the counts sum to the subjects touched. A run whose sweep re-queued a `stale_read` subject counts it `requeued` and closes `requeued` (when nothing else ends it worse); the continuing run carries `parent_run_id` = that run |
| `non_convergence` | `{cap, still_dirty: [subject ids]}`, written when the dependents loop (§5.2) stops at its cap (3) with subjects still dirty; it raises one Work-that-will-not-settle alert (§15.3); absent otherwise |
| `receipts` | the `reasoning_runs` ids of P4's runs (P4 07 §16), each with its pins: the pack hash, the library hash, the model policy, the prompt versions, the authority revision, the config version and the pack's `updated_at`; and the domains of the package each run used. A run row plus its receipts is enough for a receipt replay with no model call |
| `skipped` | each subject not done, with its reason from the closed list below |
| `coverage` | per source: its state (connected · partial · expired · never_connected · not_connectable, §6.4); its coverage (full · partial · unknown · not_connected, P2 07 §2.6); `read_from` and `read_through`, the oldest and the newest instant read; and whether its wave completed |
| `timing` | per touched subject: `evidence_at`, `ingested_at`, `signal_published_at` (L1), `woken_by` (the highest-priority consumed wake-up's trigger, the one the request names in `trigger`, with its `rung_kind` beside it, the full list kept in the request's `woken_by`; `none` when the judgment had no wake-up row), `claimed_at`, `judged_at`, and from P5 `card_at` (P5 07 §13.1); `claimed_at` separates the queue's wait from the run's time |
| `errors` | each with its step and subject, naming every attempt ("timeout, retry (narrower, fallback model) failed"); for a repaired or discarded answer, the failing field (its path) and the error shown to the repair |
| `status` | `ok` · `partial` · `failed` · `cap_hit` · `no_material_change` · `duplicate` · `abstained` · `incomplete` · `requeued` · `waiting_for_evidence` · `nothing_due` · `skipped` |

- **A run that depends on a source not connected or expired,** or read through an instant earlier than the one it needs, closes `partial` with that source named; a wake resting on silence there records "unknown", never "overdue".
- **The skip reasons are one closed list,** shared by `skipped`, the gate's refusals (§11.3) and the wake-up's `reason` (§3.3): `sweep_cap`, `over_budget` (the tenant's day, plan period or onboarding line; never P5's interruption `budget`), `cap_hit` (a job's or a site's own cap), `parked` (its `detail` P4's termination, or `recovery_exhausted`, §9.6, which is a detail, not a reason), `stale`, `shadow`, `paused`, `plan_expired`, `sync_quota`, `killed`, `off`, `domain_off`, `lane_off`, `not_in_wedge`, `zone_unconfirmed` (the company's zone not yet confirmed, §2.1), `past_useful_until` (a rung missed in downtime, past its entry's `useful_until`, §4.6), `duplicate` (a key that already exists, §3.4), `embargo` (held back by an active embargo, the lease id in `detail`, §3.6 step 2), `already_handled` (a clock wake-up on a resolved, merged or superseded subject, §3.6 step 2), `readiness` (card delivery paused for the tenant; wake-ups and judgment go on, §11.3 step 9), `timeout` (a tick past its timeout, §12.5), `not_due` (a job the policy says is not due that day: the connect-day brief, §8.3). A visit that finds nothing new ends status `nothing_due`, not a skip. A subject stopped at the tenant cap also ends `incomplete` with `exhausted = day` (§9.5). Delivery's why-nots (`below_gate`, `budget`, `cooldown`, `muted`, `shadow`, `situation`) are P5's rows, written through P2's `surface.why_not`, and L4's tick `reasons` (`no_action`, `window_closed`, §8.4) are L4's counts; the ledger links them and never re-codes them. A reason outside the list fails OG-8.

### 10.2 · Rules

- **Append-only:** a row is never updated in place after it closes; a later run is a new row linked by `parent_run_id`, and each subject entry names its `prior_run_id`, so run 2 on a situation points to run 1 and run 1 is unchanged. The application's role has no UPDATE on a closed `loop_runs` row.
- **Every run writes one,** a zero-call run, a run that raises no card, a quiet day's daily pass and a run the door held or refused included. A test fails any loop path that can finish without its row.
- **A run that crashes** is closed as `failed`, with its error, by the next worker that finds its lease lapsed: one close event on the open row, never a rewrite of a closed one.
- **A failed or abandoned run leaves its subject exactly as it was:** its page version, its card and its attention state unchanged; its wake-up `failed` or `parked`, never `done`, `skipped` or handled; the row's `errors` names each attempt ("timeout, retry (narrower, fallback model) failed"). The next sweep never reads it as nothing to do.
- **Every model call carries its run id,** and a subject's call its `request_id`, in the product (`llm_costs`) and in the notebook (`notebook.runs`).

### 10.3 · Totals come from rows

Every total anyone sees (runs, model calls, spend, runs by calls per run, cards opened, versioned and closed per day, the month summary, the receipts page) is a sum over `loop_runs` and `reasoning_runs` through one function; a typed or cached total is a defect (P4 07 §18; P5 07 §13.5). Spend that belongs to no card (the history read, a run that raised nothing) is booked on its own rows. The same function gives:
- **`spend_vs_cap(tenant, period)`:** the sum over `loop_runs` and `llm_costs` against the cap of that period, the only source for the spend bar a person sees;
- **`cost_by(tenant | situation | judged subject)`:** calls, tokens and cost per tenant, per judged subject and per admitted situation (the sum over the receipts of the runs that produced that subject's admitted version, joined by `receipts` and the run id), per tenant per day and per month, beside the cost per seat-month (the month's cost divided by the plan's `seats`) against its `price_per_seat_month` (§9.1). The sum over subjects plus the spend that belongs to no card equals the run's total.

### 10.4 · The five counters, from the ledger

`pipeline_counters`' five stages are written per run, as the row's `counters`, and summed per tenant per day from the ledger through the one totals function (Atlas V.2), never by summing whole-company chains (today a day reads 16,126 situations formed for an org with about 1,400). Each has one source: `signals_detected` from L1's landing count, `situations_formed` from P2's new situations only, `capability_resolved` and `decision_emitted` from P4, `card_delivered` from P5. A user's Sync pass writes its counters like any run.

### 10.5 · Answering "why didn't it run?"

With a request id on every subject a wake-up reached, P2's `why_no_card` and P4's six questions can answer, from rows: `no_run` (no wake-up row and no request id, and which producer never fired), `gated` (a request ran and the gate stopped it), `abstained`, a missing capability, an unscheduled unit, or answered (P4 07 §16; P5 07 §13.4).
- **Every producer writes a ledger row each time it runs,** even with 0 wake-ups (an empty capture poll: `nothing_due`): capture's landing hook per batch, the minute scheduler, the hourly sweep, the 06:00 pass, Maintain. A source whose cadence says not yet writes no row, since no job ran. For a subject with evidence or a due date in the window and no request id, `no_run` names the producer that should have woken it and that producer's last row.
- **`explain(subject)`,** for the support view (§15.4), returns six answers in this order, each read from rows, and names the first that fails: (1) the why-not receipt; (2) the decision or execution row (L4); (3) the admission verdict (admit, hold or reject, and why); (4) the run receipt, abstained included; (5) the domain live (its activation row); (6) the signal published, or dropped as `not_carried` or outside the window read (L1).

### 10.6 · Today

No run ledger. `pipeline_counters` holds five counts per chain (68 sweeps), and stage times go to the log. What woke a chain, what it touched, what it cost and what it skipped are recorded nowhere; subjects past the cap get no row ([01](01-WHATS-EXACTLY-THERE.md) §1.6).

---

## §11 · Switches, the parity gate and the cutover

### 11.1 · The policy row (`tenant_loop_policy`)

One row per tenant per loop, each change a new version with who set it and when:

| Field | Meaning |
|---|---|
| `state` | `off` · `shadow` · `live` |
| `caps` | the caps of §9.1: `daily_judgment_cap_usd`, `plan_cap`, the onboarding lines per wave, Maintain's weekly cap, Act's budget, Screen's checks, the fetch caps; for a tenant in cutover, the `legacy` and `situation` pools and the card allowance's split |
| `override` | `{until, daily_cap, subjects_per_sweep}`, for a long resync: set only by a staff act with an audit note, expiring by itself, read by the budget through the same reservation (§9.2), spent in the §9.3 order; `subjects_per_sweep` above 10 needs P4's agreement (P4 07 §2.7) |
| `models` | a pointer to P4's per-tenant, per-site rows (the model, thinking and fallback; P4 07 §14), never a copy |
| `quiet_window`, `quiet_window_max` | 10 minutes after the last arrival, and at most 20 minutes after the first, by default (§3.5) |
| `reopen_window` | how long a resolved subject still runs P2's reopen check on new evidence: 90 days by default, or the playbook's stop rule where one is set (§3.6 step 2) |
| `verify_misses` | the re-armed `verify_by` windows before the founder is asked again, 2 by default (§7.2) |
| `bulk_threshold` | the threads above which placement runs in bulk (§6.1); its default is set from the load drill (§13.3) |
| `date_unknown` | `reask_every` (7 days by default) and `reask_max` (3 by default), copied onto each `date_unknown` entry (§4.1, §4.2) |
| `open_card_bound` | the open cards above which the nightly census alerts, 30 for a founder-size tenant (§8.1 step 11) |
| `local_hours` | §2.5 |
| `non_working_rules` | per rung kind, what a non-working day does (§2.4); the default is §4.1's column |
| `timeouts` | the lease wait (30 s, §12.4) and each tick kind's timeout (§12.5) |
| `lanes` | the onboarding lane, the worker share (§12.3) |
| `lane_state` | per output lane (the agent lane, and each output lane P5 names): `on` or `off`. A lane can be stopped alone, before any investigation, without turning off the loop |
| `capability_allowlist` | for a design partner, the wedge capabilities it starts with (ids named by P3); empty means the full set, as for the golden tenant |
| `readiness` | `ready`, or `paused` with the "never" line that broke (§15.5), with who and when; `weeks_at_bar`, the weeks running that the weekly quality line (§8.2) has been at every bar, set to 0 by a week under one; and `unwatched_ok`, true only when every condition of §15.5 holds, `weeks_at_bar` at 4 or more among them |
| `notes`, `set_by`, `set_at` | the audit line |

**In shadow** a loop writes its pages, goals and cards to their tables marked shadow, and nothing reaches a person; **in live** it publishes. A loop that publishes while its row says shadow is a defect a guard catches (§19).

### 11.2 · One registry of every switch

`platform/switches.py` lists every switch that changes behaviour, per tenant where it is per tenant:
- the loop rows (§11.1);
- the activation rows per situation type for the one-judge cutover (P4-17), and the cutover switches today's `reason/cutover.py` lists, each a row: `publisher`, `require_admission`, `execution_mode`, `fundraising_route`, `observing_laws`, `cards_from_situations`;
- every L1 to L4 activation, `tenant_packs`, and each domain's state (live, shadow, not subscribed) with its pack pointer (P3 07 §9);
- the card switches: `card_copy`, `cards_from_situations`, and the flags `push_brief` and `predictive_card` (P5);
- **the flags awaiting a product decision** (`push_brief`, `predictive_card`, and any other the Atlas leaves open): off by default, armed only by a policy row a person sets, with `set_by`, `set_at` and a note; the registry shows them as "undecided";
- the learning switches, none armed by default: calibration apply, `recommendation_acceptance`, the staged mute ladder, Adaptive leases learned from behaviour (W27 D13). Arming is per tenant and changes only through Rohit's decision recorded in 08-LOG; in shadow, a would-mute, would-down-rank or would-apply is written as a shadow row (kind, count, window) in `learning_shadow_rows` and nothing else is written. The Adaptive-leases switch governs only learned leases, not the ones the founder states;
- the wedge's `capability_allowlist` (§11.1), with its flip test: a capability outside it is skipped with `not_in_wedge`;
- every environment flag that changes behaviour, and the kill switches.

Each entry holds its meaning, its owner, its precondition, what breaks if it is flipped alone, whether it is armed, its `row` (table and key), `set_by` and `set_at` (from the row's audit or the activation tool's read-back log, §11.7), and **the ledger evidence that proves it ran**. A row whose `armed`, `precondition` or `owner` disagrees with the code (a default value, the activation precondition table, an environment flag's default) fails CI (OG-10). A daily check compares each switch's claim with what the ledger shows ran, and alerts on a disagreement ("the switch reported success while nothing happened", [02](02-WHATS-FAILING-AND-WHY.md) F4); for a domain row it compares the state with the domains in that day's receipts (a live or shadow domain must appear when at least one subject of that domain was claimed that day; an off or absent one must not). Each switch has a test that flipping it changes what runs in the same sweep. A trigger with no producer (§3.2) is reported here too.

**The armed-state baseline,** checked daily; a switch armed with no decision row (`set_by` and a decision id) alerts:

| Switch | Baseline |
|---|---|
| Calibration apply, the staged mute ladder, learned Adaptive leases, `recommendation_acceptance` | off |
| The model decider | unset |
| A top-tier (Opus-class) model in any site's policy | none; P4's validator allows one only as the depth-3 or second-pass override with its record in 08-LOG, and refuses it anywhere else (P4 07 §14) |
| Sales and Support for the design partner's own org | off until a decision row from Rohit |
| `push_brief`, `predictive_card` | off, "undecided" |

### 11.3 · One gate for every door

Every door that can start work (the schedule, the queue's claim, a user's Sync, `POST /sync`, a backfill, an upload, an API act) asks one function, in one order:
1. the tenant exists and is not paused (`paused`);
2. its plan is not lapsed (`plan_expired`). A lapsed plan blocks model spend only; reads and the dashboard still work. An unreadable billing row is treated as not lapsed for reads and access, logged and alerted, with spend still bounded by the caps;
3. its plan's sync quota is not full, for a door that pulls (`sync_quota`);
4. no kill switch, global or per tenant (`killed`);
5. the loop's row is not `off` (`off`);
6. no cap that binds is spent: the day, the plan cap's period, the onboarding line (`over_budget`); a severity-4 subject passes (§9.2);
7. on the placed subject, before its judgment: its domain is live or shadow (`domain_off` otherwise; §11.4) and, when the policy row's `capability_allowlist` is not empty, its capability (read from the same pointer) is in it (`not_in_wedge` otherwise); no judgment call either way;
8. before L4 dispatches a step: its output lane is `on` (`lane_off`);
9. before a card is delivered: the tenant's `readiness` is `ready` (`readiness`: delivery only; wake-ups and judgment go on, and the cards are written as shadow and listed).

**The kill switches bind every thread and every worker,** not only API requests. A refusal for `paused` or `plan_expired` leaves the wake-up `pending` and unclaimed with that reason, and resume or renewal claims it; a cap refusal (`over_budget`) carries it (§9.5); any other refusal is a `skipped` wake-up with its reason from the closed list (§10.1). **A refusal is always a row:** a tenant refused at the gate with no wake-up to skip still gets one `loop_runs` row per local day, status `skipped`, with its reason, and one alert per tenant per day for a lapsed plan. Wake-ups already pending when a plan lapses stay `pending`, unclaimed, with reason `plan_expired`; producers write no new ones while it lapses; renewal resumes them, and the tenant's next Maintain step 1 (I-13, §8.1) runs at once, writing a wake-up for every situation with a member newer than `judged_through`; rungs crossed during the lapse follow §4.6's catch-up. **A manual Sync or `POST /sync` is charged to the same reading line and the same cap as scheduled capture** (§9.1's reading row).

### 11.4 · Domains

- **A domain is live, in shadow, or not subscribed** (Atlas IV.1; P3's `off`). P1 reads the domain's state before every wake-up of a subject in it. **A domain with no row is not subscribed:** it contributes no unit and no wake-up.
- **Where the domain comes from:** a subject's domain is read from its capability pointer (P3). An unplaced wake-up is placed first (§5.2 step 2); the domain check runs on the placed subject, before step 3.
- **Not subscribed:** facts are captured only when a live domain needs them (P2's and L1's rule); no judgment call; the wake-up is `skipped` with `domain_off`.
- **In shadow:** a full run with its receipts, written as shadow, with the why-not `shadow`, inside the same caps and after the live work (§9.3); no card reaches anyone.
- **Live:** full judgment and cards.
- **Deactivating a domain** cancels its subjects' pending wake-ups with `domain_off` and sets their date entries `suspended` (§4.2), never deleted. A suspended entry fires nothing; a rung that falls due while suspended is written `missed` with `domain_off` and never fires later. Reactivation sets the entries `active`, and the next minute-grain and hourly pass writes the wake-ups the date index and the unconsumed evidence call for (the rebuild of §12.5).
- **The plan sets the entitled domains** and a domain's state lies within them (P3 07 §9); P1 reads only the plan's name. The activation tool (§11.7) refuses a state outside entitlement; a plan change adds or removes entitlement rows with a ledger row, and a domain no longer entitled goes off through the deactivation rule above. **A domain goes from shadow to live** only after its pack passes the bar in shadow (P3 07 §8, D-P3-8), through the parity gate (§11.5): one commit, with its way back.

### 11.5 · The parity gate

- **Per tenant and per situation type.** The new path runs in shadow beside the old one; the gate compares them on the acceptance set ([10](../10-ACCEPTANCE.md)) and the tenant's golden cases: must-detect, must-abstain and forbidden outputs, the ideal cards same or close, opposite calls, open cards, replay events on their day, the Evolve day's cost.
- **A switch flips only when the new path is equal or better than the old** on must-detect, must-abstain and forbidden outputs, on the golden board and on the tenant's golden cases.
- **The thresholds are written down before the run** (in 08-LOG), as `reason/cutover.py` already demands; the gate reads that line (date, numbers, who) and records its id on its row. `measured_at` is empty until the numbers are read; a gate with no threshold line, or one dated after the run, fails, and an absent measurement counts as a failure.
- **Side by side for at least three days** on the tenant's copy; then Rohit's approval, recorded in 08-LOG; then one switch, one commit, with a one-line way back and a day's watch; a same-day rollback is flipping the row back. A gate with no approval line refuses to flip.
- **One type at a time.** The first type switched is awaiting reply and outreach (the investor, introduction and incubator cases; P4 05 §10), for the design partner's tenant only; later types follow in the order Rohit approves, each after its own gate. Switching one type leaves every other type, and every other tenant, on the old path.
- **A failed gate** leaves the tenant on the old path with the failing lines named on its row. **Rolling a loop back to shadow** keeps every page, goal, receipt and ledger row and only stops the new cards' delivery; no conclusion is lost.
- **The recall guard:** fewer cards must come from merging, never from dropping; P1 counts cards from situations, uninterpreted cards and cards from raw signals on every pass (P5's `card_source`), and by comparison key (P5's `COMPARISON_KEYS`, P5 07 §2.5), and writes the counts on the pass's ledger row. A key present on the old path and absent on the new, with no merge link to a surviving card, is a drop and fails the gate (Atlas L5).
- **For a tenant, the old makers stop delivering only after the gate passes:** the legacy and compiled lanes, the old decision maker and R-1, and the Support readings while Support is off; every one of them can be switched back by its row.
- **One maker per subject:** for a tenant past its cutover, the count of distinct card makers delivering per subject is 1, recorded on every pass; any other value fails the day and alerts. Before cutover the count is recorded, not enforced.
- **The gate's state** and its way back are stored per type and per tenant in `parity_gate` (org_id, situation_type, state off · shadow · live, `thresholds_written_at`, the threshold line's id, `measured_at`, the measured lines, `decided_by`, `decided_at`, `way_back`); the stored way back restores the old state in one row change.

### 11.6 · New tenants

- **Until the gate passes** on the golden tenant and on two more design partners (D-P1-9), a new customer is a design partner, armed by the runbook (relief R6).
- **After that, every new tenant starts on the new path, live, from its first day:** the company page, the policy rows, the activation rows and the model-policy rows are created from defaults; the default-on set is derived (every feature minus the declared exclusions, each exclusion with its written reason), so a new feature can never be silently absent. The brain (`expert_review`, `l2_reasoning`, `l2_cards`) and `cards_from_situations` are on, and every old maker is off (the legacy and compiled lanes, the old decision maker and R-1, the Support readings), so no card is delivered by an old writer. Nothing is switched by hand.
- **The packs by kind:** chosen at phase 0 from the signup answer (founder-led, sells, supports) and re-evaluated when the company page confirms `customer_kind` at phase 2. A tenant whose setup says founder-led gets the Founder Office with Admin, live; any other setup does not get the Founder Office. Sales and Support are off for a founder (P3 07 §9, D-P3-10), a recorded departure from the Atlas's shadow default; for a company that sells or supports they start in shadow and go live only when their pack has passed the bar (§11.4). A change flips the pack rows through the activation tool (§11.7), in precondition order, with a ledger row, never by hand.
- **The design partner's own org** keeps the domains Rohit opened; the defaults above apply only to new tenants, and a replay or an onboarding re-run never changes them.
- **Provisioning runs at the top of every run** and of the daily pass, idempotently: the domains, the tenant packs, the semantic row, the policy and model-policy rows. It never fails the run, and writes what it created on the run's row; a second run creates nothing.
- **The notebook has only the new path:** `nb.cli fixture` and every notebook build run it with the six cost-bearing rows of the last exclusion below on by construction. That exclusion applies only to product tenants made by `make_tenant_live` before the gate's commit; the other exclusions hold for every tenant, the notebook's included.

**The declared exclusions,** each with its reason:

| Excluded from the default-on set | Reason | Leaves the list when |
|---|---|---|
| Calibration apply, the staged mute ladder, `recommendation_acceptance`, learned Adaptive leases | off for good until Rohit's decision (W27 D13, §11.2) | never; armed per tenant only by that decision |
| Screen | a capture policy each seat turns on (§6.1) | never |
| `push_brief`, `predictive_card` | undecided product flags (§11.2) | when the product decision is recorded in 08-LOG |
| The domain `general`; the legacy, compiled and rule lanes | the old path; a new tenant's cards come only from admitted page versions | never |
| `expert_review`, `l2_reasoning`, `l2_cards`, `cards_from_situations`, `card_copy`, `morning_brief` | cost-bearing, and switched only at the cutover; on through the runbook (R6) for a design partner until the gate; product tenants only (the notebook's are on by construction, the last bullet above) | in the gate's commit (D-P1-9), which deletes this row; the derived set then includes them, as the second bullet above says |

### 11.7 · The activation tool, and reading it back

- **A feature is activated only by a per-tenant activation row** with a mandatory audit note; an activation without one is refused, and removing the row is the rollback. A global environment flag may only be a kill switch.
- **The tool validates every name before the first flip,** applies features in their preconditions' order (expert review, then L2 reasoning, then L2 cards), refuses a retired or unknown name instead of dropping it, and its dry run lists exactly the switches meant, with their missing preconditions.
- **A flip is read back:** after every change, the live state is read from one staff route, `GET /admin/live-state/{org}` (every activation row, live and stamped off; the behaviour flags set or unset; the deployed SHA; the schema head), and the result is logged as a dated line with its one-line rollback.
- **The staff read route** parses each statement and accepts only SELECT, WITH or SHOW; anything else is refused (403) and logged. Each production read runs on Rohit's yes for that read, and its output is written outside the repo, never committed.
- **Deploy per step or per switch,** and read a one-day number before the next; never a big-bang deploy.
- **The release gate:** `scripts/release_gate.py` exits 0 only if (1) CI is green on the SHA; (2) the migrations apply in order on a fresh database and on a copy of production's schema head; (3) a change to a prompt, a check or a model site had a capped real-model pass; (4) the golden board did not regress on either path; (5) the next day's daily health cards are at least half the 14-day median.
- **A change to a policy row's model or thinking** (P4 07 §14) is adopted for a tenant only after the capped live pass on that row is in 08-LOG; without it the change is refused.

### 11.8 · Today

Switches are rows per tenant, which works. But the kill switches don't bind the background threads; `reason/cutover.py`'s parity functions have no caller; this org's brain was switched on by hand, 50 minutes after its system rows; and `scripts/activate_tenant.py`'s default features are only roster v2 and ranking v2 ([01](01-WHATS-EXACTLY-THERE.md) §1.7, §4).

---

## §12 · The process and the queue

### 12.1 · The API and the worker (D-P1-7)

- **The API** serves requests. It writes wake-ups (a founder act, an upload, a manual Sync) and reads results. It runs no scheduler, no chain and no loop.
- **The worker** is the same image with its own start command (`worker: python -m genios_engine.reason.loops.worker`). It holds the producers (the date index's scheduler, the schedule, the capture cadence, and the Screen lanes for a tenant with Screen on, §8), the queue's consumers, and capture's schedule (today's `platform/scheduler.py`).
- **One chain body.** A user's Sync, `POST /sync` and a backfill are capture jobs that end by writing wake-ups; the same runner, gate (§11.3), ledger row and pipeline counters apply, and no door has its own chain body. The old post-passes move to Maintain (relief R2) or to their rungs (`verify_by`, the meeting rungs).
- **Nothing a founder relies on depends on the founder's Mac being awake.** Passes, rungs and agent jobs run on the server.

### 12.2 · The queue

- **`loop_wakeups`, claimed with `FOR UPDATE SKIP LOCKED`** and a 2-minute lease, heart-beaten every 30 s (the warm lane's pattern, kept): one pending row per key.
- **A failed run** (a failure that is not the model's, §9.6) retries with capped back-off (10 s to 10 min), reusing P4's stored answers (§5.2), and is parked after 5 attempts for a person, with an alert.
- **Postgres only:** lease rows, no advisory locks, no LISTEN or NOTIFY, safe for several worker instances.

### 12.3 · Lanes

- **A global pool of N workers,** each claiming the most urgent due wake-up by the order below. The pool is held as slot-lease rows in Postgres, set per deployment: 1 on the product (today's warm-lane slot) until the load drill (§13.3) passes at pool 4 while pool 1 failed or sat above 70% worker use (or the founder decides), then 4; the notebook and its other drills start with 4, and the load drill runs both.
- **The claim order:** the class first (Act, then the classes of §9.3); within a class, round-robin across tenants; within a tenant, the §9.3 sort key.
- **Each tenant's share:** at most 1 Evolve run and 1 Act run in flight per tenant, with its own caps; its daily pass starts at its own local hour with its start jitter (§2.5).
- **Onboarding has its own lane,** with its own slots and at most 2 tenants at once, so a big first week or a 365-day backfill can never take the Evolve slot of the tenants already live; inside a tenant, wave 2 runs below that tenant's own Evolve and Act wake-ups; the others queue with an honest estimate.

### 12.4 · One run per subject, one Evolve per tenant

- **One Evolve run per tenant at a time** (`org_run_leases`, kept), so one sweep's transaction never races another for the same tenant. A second caller (a manual Sync during a running Evolve) waits at most the lease wait (`timeouts` on the policy row, 30 s by default), then returns with its wake-up written `pending` (`new_evidence` or `human_ask`), which the lane claims after the holder closes. No event is lost.
- **One run per subject at a time** across all loops, held by a per-subject lease row (`subject_leases`: org_id, subject) taken inside the claim and heart-beaten like a wake-up's lease: an Act run and an Evolve run never judge the same subject together. The loser leaves its wake-up pending, coalesced into the next run (§3.5).

### 12.5 · Deploys and crashes

- **On deploy** a worker stops claiming new work, finishes or releases what it holds (leases lapse in 2 minutes), and exits. Every step is idempotent, so the next worker carries on.
- **A crash mid-run** leaves no half-written run: the open sweep rolls back; sweeps already committed stay (§5.2); the run row is closed `failed` by the next worker, and the open sweep's wake-ups return to pending. A crash before a commit loses that sweep's writes, not its answers: each answer already in P4's answer store is applied on re-queue at 0 new calls (§5.2); only a call that was in flight with no stored answer is paid again. A subject whose commit landed is never paid again, because its request id returns the stored result (P4's intake) and its page version is checked first.
- **A timeout cancels its work.** Each tick kind has its timeout (`timeouts` on the policy row): an overrunning tick is cancelled, its run closed `failed` with reason `timeout`, and the next tick fires on its schedule. No abandoned tick keeps running beside the next one (today's cut tick does, [02](02-WHATS-FAILING-AND-WHY.md) F17).
- **All P1's caches** (the date index, the wake-up table, a queued dirty set) can be dropped and rebuilt from Postgres, giving identical pages and identical wake-ups (P2 07 §12.3):
  - the date index from `due_dates()` of the active pages, the leases, the goals, the stored predictions (`predictions`, P2 07 §7.5), P5's returns and next checks, L4's rungs and the calendar's events (§4.4);
  - the pending wake-ups from the date index, the unconsumed evidence and the open needs;
  - the fired rungs from the rung kind and date cited in each page's last receipt, so nothing fires again;
  - the queued dirty set from the last admitted versions.

### 12.6 · Today

One API process with four daemon threads; the 6-hour tick counted from process start; a cut tick keeps running; a chain started by a tick has no durable record, so a deploy mid-chain loses it ([01](01-WHATS-EXACTLY-THERE.md) §2).

---

## §13 · Many tenants

### 13.1 · Isolation

- **Every row P1 writes to a table that holds tenant rows carries `org_id`, `trace_id`, its visibility and its schema version** (wake-ups, date entries, runs, reservation rows); the visibility is the narrowest of the evidence or act it carries. No P1 query of such a table runs without `org_id`. `plan_economics` is a platform table keyed by plan name, outside OG-11 and the erasure list, read by plan name only (§9.1).
- **P1 reads the Notebook only through P2's API,** with the asking seat's visibility; it never reaches into another layer's tables.
- **A seat's private item stays private through every path:** wake-ups, runs, ledger rows and cards carry the seat of origin; an item only that seat holds is never placed where another seat sees it. A ledger line, a skipped line or a support-view line for a seat-private subject shows other seats only a count, never its words; the row itself holds ids only.
- **Tested:** a check query on every table the runner touches finds no row of one tenant read by another.

### 13.2 · Fairness

- **One tenant's backlog never delays another tenant's founder:** each tenant has its own share and caps; the onboarding lane is separate; Act comes first for every tenant. The day's card allowance per seat is P5's count (§9.1), never a P1 cap.
- **One tenant's failure** is recorded with its `org_id` and never touches another's run; a bad source never stops the others.

### 13.3 · The load drill

Before any second customer is onboarded without a person in the loop: the engine against the local copy, with the golden tenant cloned under new ids 2, 5 and 10 times, each size at pool 1 and at pool 4 (§12.3), measuring each time the new-mail-to-page time, the queue's wait (from `claimed_at`) and the run's time, worker use, database statements and size, and cost. The freshness promises (§15.2) must hold at each size at the pool the product will run; pool 1 is reported beside it and decides the pool rule (§12.3).

### 13.4 · Leaving

When a tenant leaves or is erased: its wake-ups are cancelled, its loop rows set to `off`, its leases released; a run already in flight is cancelled at its next savepoint and its sweep's transaction rolls back, so it commits nothing. The minute scheduler and the hourly sweep read the loop row's state before writing a wake-up, so an erased tenant's date entries never fire. Then the erasure path removes its conclusions with its evidence, and `loop_wakeups`, `loop_runs`, `tenant_loop_policy`, `date_index`, `parity_gate`, `switch_registry_checks`, the reservation rows, `daily_health` and its loop health rows, the outcome label rows (§7.6), `weekly_rollups`, `subject_leases` (released first), `learning_shadow_rows`, and its activation rows, with them; each new P1 table is checked against the erasure list when it lands (OG-14). No wake-up is produced for a tenant with no active connection and no live loop row.

### 13.5 · The second tenant

A fixture tenant that sells and supports, with different goals, runs as a third build through the same runner as the two-tenant run (§14.3) and passes every loop test (clock, ledger, spend, wake-ups, Evolve, Maintain) with no code change. The code holds no literal of the design partner's data (P5 07 §15.10): a search of `reason/loops/` and `nb/loops.py` finds no name, address, id or amount of theirs.

### 13.6 · Today

Fairness exists for capture only (oldest due first). Reasoning for all tenants runs in one serial loop inside the sweep thread, with one warm-lane slot for the platform. Only one tenant is in the data, so no multi-tenant run has been measured ([01](01-WHATS-EXACTLY-THERE.md) §1.3).

---

## §14 · The replay and the drills

### 14.1 · The replay

- **Two replays, never confused.** **The event-time replay** (`nb.cli replay`, this section) re-judges a clone through every due instant, in one of two modes. `--mode recorded` (the default) takes each judgment from P4's answer store or cassette, keyed (subject, input fingerprint, `eval_time`) (§5.2), runs it through P4's converter and P2's admission, makes 0 model calls and costs $0; a subject with no stored answer is listed on the day's report by its key and not judged. `--mode live` calls the model through the register like any run, under the replay's cap, and runs only after a recorded run of the same range has been read. **The receipt replay** (`nb.cli replay-run <run_id>`, and Maintain's nightly sample, §8.1) rebuilds one past run from its stored answer: it loads no model client, a model call from it raises, and it returns the stored result with 0 calls (P4 07 §16). OG-12 and P5's CG-30 guard the same two paths, the receipt replay and the recorded mode (§19).
- **The command:** `nb.cli replay --from <build> --to <instant> [--mode recorded|live]`. It first **clones** the build to a new id (`nb.cli clone`), so the source build (`b2`, the scorecard's base) is never changed, and P2's 28 invariants run on the clone before the first replayed day.
- **It steps through every due instant, not one run a day** (D-P1-14): evidence arrives in batches at its real capture instants and is woken after the 10-minute quiet window; each timed rung fires at its instant (23 Oct: 09:00 for `p1`, 11:10 for `f1`, 12:05 for `i1`'s after-panel reminder); the 06:00 daily pass, the 08:00 brief and the 02:00 Maintain run at their local hours; the weekly pass on its day.
- **It reads nothing after the instant:** mail by its capture time, meetings by `known_at`, goals, cards and founder acts by the time they were made. An as-of read at instant T keys on the evidence time (the `eval_time` P1 passes; P2's `known_at`, P2 07 §2 `as_of(T)`), never on the wall-clock recorded time: the replay's own versions and cards carry the replayed instant as their evidence time and the wall clock as their recorded time (§2.6), so a snapshot read at replayed day D holds the replay's versions up to D, is not empty, and holds none from a later replayed day. A meeting's cancellation or move applies from its own recorded time; before that instant the meeting is live and may set wake-ups. It never reads the wall clock to decide anything.
- **Coverage in a replay:** each source's read-through is the earlier of the replayed instant and the copy's last capture of that source. The last day in the copy (28 Oct, cut at 12:45 UTC) is partly read, and an expected-by or silence finding after a source's last capture reads "unknown", never "overdue" (rule 12).
- **Fixtures** state their dates as offsets from the run's `eval_time`; a fixture with a fixed calendar date beside a wall-clock window is refused (OG-2).
- **It runs from 23 Oct 07:10 IST (01:40 UTC) to 2 Nov,** past the copy's last evidence, so the clock-only events happen with no new mail: `f4` turns on Mon 26 Oct at 10:00, `c1` on 26 Oct, `b1`'s rows lapse on 24 Oct, `b3` auto-closes and `l1` wakes on Sun 1 Nov; `c2` keeps its decide-by date of Wed 28 Oct, its 28 Oct and 29 Oct rungs each fire once, and it stays open until a decision act is replayed (it is owed by us, so Maintain does not close it), then closes. On every replayed day with no new evidence, the 02:00 Maintain and the 06:00 pass open 0 cards, write 0 versions, make 0 card-writer calls and send no notification.
- **A quiet day** is one with no new evidence that places into or changes a situation and no rung crossed; mail that the fingerprint or the continuation rule absorbs counts as no change.
- **Each replayed day writes a report** beside [10](../10-ACCEPTANCE.md) §3: wake-ups by trigger and rung kind; situations and goals touched; judgments and placement calls, counted apart; cards opened, versioned and closed, beside what 10 §3 expects; cost, Evolve's and Maintain's on separate lines; the time from a mail's arrival to its page version and to its card, per source with its n, as p50, p90, p95 and the share within 30 minutes; what was skipped; in recorded mode, what would have been written and the held and refused counts per check, which show whether a check is too strict or too loose; a pass or fail line per expected event, among them "every new introduction offer is one wake-up and its own situation with its own yes or no, none appended to the intro platform's large situation, and the new situations equal the offers"; and the state (card ids and lane, deliveries) at each instant of the expected-instants list, authored from the ideal and kept as rows of 10 §3, a mismatch failing that instant. At each day's end the acceptance measures are written (§14.5), and `scripts/parity.sh` (U13-04) runs read-only against the clone: the card score (`ideal_card_gap`), the work score (`ideal_work_gap`) and the stage of loss (`ideal_trace`) for every ideal id, its line appended to 08-LOG.
- **Repeatable:** two replays from the same base give the same wake-up list (keys compared without the build id, §3.4), the same run keys (each `run_id`'s key compared without the org id and the build id, since each replay has its own org id, §14.3; never equal run ids), the same ledger counts and the same cards opened or closed per day, and in recorded mode the same held and refused counts. In recorded mode or on a fake model all are identical; with the real model a difference is written to the day's report as a variance line naming the subject and the call.
- **A replay day passes** when every listed event happens on its day, the state at each of its expected instants matches, all 28 of P2's invariants hold, a quiet day costs $0, each other day costs under $0.50, and the busiest day (27 Oct: 46 new threads, a broadcast to about 33 recipients, 10 §3) makes at most 5 judgments, counted apart from placement calls. The day's cost gates are read on a live run and count Evolve; Maintain's weekly run (Sunday 03:00) is judged on its own line against its weekly cap (under $1).

### 14.2 · The onboarding drill

On a fresh onboarding build at the ideal's instant, and on a fresh fixture tenant (a seeded founder mailbox, created from defaults with no row written by hand; P1 provides it as `nb.cli fixture`, which P3, P4 and P5 also use, on the new path with the six cost-bearing rows on by construction, §11.6):
- a crash in the middle of each phase; a restart during wave 2, the way a deploy restarts a process; a cap hit in wave 2;
- a second seat connecting a mailbox: its threads join the existing investor and hiring situations, an item only that seat holds stays private to it, the other seat sees a withheld count, and the company patterns gain n.

It writes the onboarding report: the time of each milestone (§6.4) against its target, the relationships, commitments and conditions held (40 min) and the first situation admitted (1 h) among them; time to first intelligence; time to first value (connect to the first positive judgment); time to everything judged; the open cards after wave 1 and after wave 2; the cost per phase, reading (L1's extraction, entity resolution, Screen) and reasoning on separate lines; and what was skipped. A missed milestone is written in 08-LOG as an open decision for Rohit, with its measured time. It passes when every disruption resumed and nothing was paid twice, the open cards after both waves are at most 30 for a founder-size tenant with no ideal card lost, and the targets of [06](06-NEW-CUSTOMER-ONBOARDING.md) §5 hold.

### 14.3 · Two tenants at once

Two builds run as two tenants through the same runner at the same time (one at 23 Oct, one at 25 Oct), sharing one worker pool, each with its own tenant cap under one platform cap; neither build draws on the other's. No row of one is read by the other; each build's ledger accounts for every one of its calls; the work interleaves; both finish with the same results they get alone, and every cap holds. Every replay, golden run and drill gets its own org id, connection id and scratch schema, derived from its build id, so two overlapping runs never read each other's mailbox.

### 14.4 · The stage gates

The end-state targets of [10](../10-ACCEPTANCE.md) §5 are reached through four gates, each written before it is run:

| Gate | Passes when | Step |
|---|---|---|
| **G-Onboard** | A fresh onboarding build at the ideal's instant: at least 11 of the 17 in-copy ideal cards same or close, 0 opposite calls, `f1`, `f2` and `p1` among wave 1's cards, reasoning under $10 | P1-3 |
| **G-Replay** | Every event of 10 §3 on its day, the clock-only events to 2 Nov included; all 28 invariants every day; a quiet day $0; every other day under $0.50, Evolve counted, on a live run; 27 Oct at most 5 judgments | P1-8 |
| **G-Drill** | 06 §5's targets with every disruption resumed and nothing paid twice; at most 30 open cards after both waves | P1-10 |
| **G-Parity** | 10 §5's end-state targets, measured on the copy, before a tenant's switch (§11.5) | P1-11 (the gate), run per tenant at [05](05-HOW-AT-PRODUCTION-LEVEL.md) §7 step 8, one switch per commit |

### 14.5 · Before and after every step

Before and after every P1 step: the always-hold set (P2's invariants, every unit test, the repo's CI guards with the card guard, the situation-site ratchet and the layer guard among them, no held or checker text reaching a person, the caps) and the acceptance scorecard ([10](../10-ACCEPTANCE.md): ideal cards same or close of 17, opposite calls, open cards, goals matched, status and next move, events on their day, the Evolve day's cost), written into 08-LOG; after each onboarding build and each replayed day, `scripts/parity.sh` adds its three scores (§14.1). A step that makes any line worse, or turns any guard red, is not done.

**Every paid pass** (a fresh onboarding build, a live replay, a drill) begins with one or two real calls whose `stop_reason` and `output_tokens` are read; a stop at the output ceiling aborts the pass before the rest is paid for. The ledger's total for a paid pass is within 5% of the provider's reported usage for the same window, or the scorecard's cost is marked unreliable.

### 14.6 · The golden run

`golden_run --org <org> --from <instant> --to <instant> --path old|new|both` runs the golden set (the founder cases and the Atlas replays) through the real chain on Postgres for the chosen tenant and period, with its own ids (§14.3). It writes the board (must-detect, must-abstain, forbidden outputs, ideal cards same or close, opposite calls) beside the acceptance set, and `golden_run diff` compares the old path's board with the new one's. The old path's board is stored with its run id before any switch, as the parity gate's baseline (§11.5); the replay's golden day is P1-8's baseline. The same inputs on the same path give the same board; a tenant or a period outside the golden set is refused with its reason.

### 14.7 · Today

The product has a replay for synthetic golden cases only (`tests/replays/engine_runner.py`), and `scripts/measure_chain.py` times one chain on a local copy. The notebook's `update` moves a build in place and has never run on a real build; nothing steps through a day's minutes ([01](01-WHATS-EXACTLY-THERE.md) §7).

---

## §15 · Health, alerts and the support view

### 15.1 · The loop line, per tenant per day

From the ledger, never from logs: one row per tenant per local day, written idempotently (a re-run of the job replaces nothing and adds nothing), each line printed beside the previous day's value.
- **The loops:** runs per loop; wake-ups fired, by trigger and rung kind; situations and goals judged; cards changed, by maker and lane, and the card makers delivering per subject (1 for a tenant past its cutover, §11.5); refusals, by reason; the high-priority items skipped; errors, receipt-write failures among them; the subjects parked (after P4's ladder, or stale twice, §9.6, §5.2), with their reason; `plan_state` (active · grace · expired).
- **Freshness:** the time from new mail to updated page and to card, as p50, p95 and the share within 30 minutes (§15.2); each source's state and `last_read`, from which every "read N min ago" is computed at view time (`clock.relative`) and never stored; the date index's coverage (§4.7); the switch-against-ledger check (§11.2).
- **Spend:** cost against each cap, with reasoning, reading (L1's extraction, entity resolution, Screen) and other on separate lines; model calls and their failures; the discarded share of spend (healthy under 10%, §9.6); calls and cost per situation; judgments skipped for budget.
- **The Notebook's and Plane R's own lines** (P2 05 §9; P4 05): the judge's line and its top unit failures; the expert, L2 and admission counts and the funnel; the held changes' reasons, and changes held against admitted; situations by state and band; invariant failures; goals with no next move; open loops past their date; size against its budget, and the database's size; facts or situations of a department that is off (0); units approved but not live, each with its reviewer named (P3 04 P3-12; 0).
- **The work numbers, each with its healthy value:** works past their expected-by date and not judged (0 at the day's end); re-judgments with no new input (0); cards per work (1); the median dossier size (12,000 characters or less); changes held against admitted (low and stable: outside it when the held share passes 25%, the weekly bar of §8.2, or a held-change reason is flagged, below); judgments skipped for budget (low: outside it above 20% of a day's wake-ups three days running); founder corrections a week (falling: outside it above the mean of the previous four weeks).
- **The week** (§2.7): AER and HIR from P2's `aer_hir`, and important-situation recall from P5; a week before connection reads "not measured".

A held-change reason at more than twice its previous day's count, with at least 10 held, is flagged on the health row as a likely prompt or schema change, and alerts (Work number, §15.3).

### 15.2 · What the founder can count on

| Promise | Target | Measured from |
|---|---|---|
| New mail on a live situation → its page and card updated | 90% within 30 min of the mail's arrival, quiet window included, per source | `evidence_at` (the arrival) to `card_at` in the ledger's timing stamps; p50, p95 and the share within 30 min |
| Evidence a person supplies (an upload, a linked document, a need the founder meets) → a decision-ready page | within 2 min, one call | the wake-up's `due_at` and the receipt |
| A signal ingested → published | under 60 s for a webhook; hourly for the Screen memory batch; p95 per tenant per day | L1's `landed_at` and `published_at` |
| A date crossing a rung → that situation judged | within 2 h | the wake-up's `due_at` and its run |
| A timed rung (a surface time, an event end) | fired within 2 min of its instant | the wake-up |
| The morning brief | the brief hour (08:00 company time by default), within 15 min, every day | the brief's job row |
| A new customer's first hours | wave 1 captured within 30 min; relationships, commitments and conditions held within about 40 min; the first situation admitted within about 1 h of connect | the onboarding milestones (§6.4) |
| A new customer's first intelligence | within 2 h of connect (wave 1) | the onboarding milestones |
| Everything in the window judged | within 24 h of connect | the onboarding milestones |
| A new seat | what the company already knows that the seat may see, on its first screen within 5 min; its own first intelligence within 2 h of the seat connecting | the seat's onboarding milestones |
| A loop that should have run | ran, or an alert said why not | the ledger |
| A routine judgment, from wake-up to result | under 20 s, under 60 s for a high-stakes one (Atlas III.8) | the receipt |

**The 30 minutes, added up:** capture's wait (up to the source's cadence, about 15.5 min for Gmail today), the quiet window (10 min after the last arrival, §3.5), the judgment (under 20 s) and the card step. The notebook's replay cannot measure capture's wait, since its capture time is the arrival, so this promise is measured in the product.

### 15.3 · Alerts

Each alert is a rule in code with an owner and a once-per key, so a repeat of the same occurrence fires nothing. All go through one configured webhook, proven in production with a test alert; a missing webhook shows red on the support view and in the switch registry, and an alert sent with none records a failed delivery, never only a log line (today the webhook is empty by default, so alerts only reach a log).

| Alert | Fires when | Once per | Owner |
|---|---|---|---|
| Loop not run | a loop did not run in its period | loop, period | P1 |
| Promise missed | a promise of §15.2 is missed, the 24-hour "everything judged" included; an onboarding milestone more than 25% later than its target | promise, tenant, day | P1 |
| Daily pass late | the 06:00 pass has not finished, drafts included, by its deadline before the day's first delivery rung (§2.5) | tenant, day | P1 |
| No brief | no morning brief by the brief hour plus `brief_margin` (30 minutes by default, on `local_hours`: 08:30 at the defaults) | seat, day | P1 |
| Cap hit | any cap is hit: the tenant's, a site's, the onboarding budget, Screen's checks, an EvidenceNeed fetch's | cap, day | P1 |
| Owed item skipped | an item of class 2 (§9.3) is skipped or carried for budget, named with its reason; or any subject carried or skipped in more than 3 sweeps in a row | item | P1 |
| Model refusing | more than 5 consecutive model calls, or half of a day's calls, are refused or fail at the provider | tenant, day | P4 |
| Late or stuck work | a wake-up fired later than its tolerance; a queue older than its latency target; a run left open past its lease; a wake-up parked | wake-up or run | P1 |
| Tick failed | a tick timed out, or crashed; a store write failed (a read-only database) | tick | P1 |
| Date without a wake-up | a deadline with no wake-up (§4.7) | entry | P1 |
| Unsupported state | a situation in `awaiting_evidence` with no open need, or resolved with no outcome link (§4.7) | situation, day | P1 |
| Work that will not settle | non-convergence of the dependents' fixed point; repeated failure on one subject | subject, day | P1 |
| L4's tick refused | a tick that planned nothing because its refusals are configuration reasons (`window_closed` and the like); a tick whose refusals are all benign (`no_action`, no live domain) fires nothing | tenant, day | L4 |
| Switch | a switch whose claim disagrees with the ledger; a trigger with no producer | switch | P1 |
| Tenant silent | connected sources with zero live domains, zero activation rows, or zero runs in 24 hours (Atlas III.6: "no activation row, so nothing runs"); a daily pass's `nothing_due` row counts as a run | tenant, day | P1 |
| Quiet day spent | a quiet day with model calls | tenant, day | P1 |
| Cards surge or fall | new cards more than twice the tenant's usual day (P5); cards under half the median of the last 14 days (`cards_below_half_median`; a median of 0 never alerts) | tenant, day | P5 |
| Lane reads nothing | a lane that ran on a prior day reads nothing for a day (`lane_no_data`) | lane, day | L1 |
| Source | a source whose coverage is not complete (partial, expired, never connected), shown in the coverage line from the connector's real state; a run made on stale data, marked partial. A `not_connectable` source never reads overdue | source, state entered | L1 |
| Signal late | ingest to a published signal past its target (§15.2) | tenant, day | L1 |
| Work number | a number of §15.1 outside its healthy value (the work numbers, the discarded share); a held-change reason flagged as a likely prompt or schema change (§15.1) | number or reason, tenant, day | P1 |
| Quality line under its bar | any number of the weekly quality line under its bar (§8.2) | number, tenant, week | P1 |
| Open cards over the bound | open cards over `open_card_bound` (policy row; 30 for a founder-size tenant) at the nightly census (§8.1 step 11), listed with their goal link | tenant, day | P5 |
| Database | the database over its ceiling | tenant, day | P1 |
| Onboarding stuck | an onboarding in one phase for more than an hour | phase | P1 |
| Plan expired | a plan expired | tenant, day | P1 |

**P5's alerts** (P5 07 §16.6: a sweep that raises no card while every why-not is an unhealthy reason, with that sweep's report of cards raised and why-nots by reason; interruptions over budget; a breach of a "never" line, §15.5) are computed by P5's census and delivered through this same webhook, once per occurrence, with their owner.

### 15.4 · The support view

Per tenant: each loop's state, its last runs, what was skipped and why, the onboarding phases with their times, the switches and their evidence, the webhook's state. For one subject, `explain(subject)` (§10.5) gives six answers read from rows, in order: the why-not receipt; the decision or execution row; the admission verdict (admit, hold or reject, and why); the run receipt, abstained included; the domain live (its activation row); the signal published, or dropped as not carried or outside the window read. The first failing answer is named. A ledger or skipped line for a seat-private subject shows other seats only a count, never its words.

The controls: pause, resume, re-run one phase, and stop one lane (the agent lane, or any output lane P5 names) for one tenant while its other loops and every other tenant run on. Each is an audited act with its author, and takes effect within one tick.

### 15.5 · The tenant's readiness to run unwatched

A tenant runs without a person watching only when P5's census has every "never" line at 0, the speed target is met, usefulness is at its bar (70%, or P5's floor when higher, P5 07 §16.2; §8.2), and the weekly quality line (§8.2) has been at its bars for four weeks running. The state is held per tenant on the policy row: `ready`, or `paused` with the "never" line that broke it, who set it and when; `weeks_at_bar`, the weeks in a row the quality line met every bar, set back to 0 by a week under one; and `unwatched_ok`, true only when all four hold (`weeks_at_bar` at 4 or more), so a missed speed target, a usefulness under its bar or fewer than four weeks at the bars sets it false while delivery goes on, watched by a person. A breach of a "never" line pauses that tenant's card delivery (cards still listed, in shadow; wake-ups and judgment go on) and alerts its owner; delivery resumes only when every "never" line reads 0.

### 15.6 · Which code is running

`/health` names the deployed code (the build SHA set at build and deploy) and the schema head; the ledger's rows carry the same SHA.

### 15.7 · Today

The daily health row exists for 2 of 7 days, sums chains, and alerted only "database over its ceiling". Alerts go to a webhook that is empty by default. `/health` says "dev". Nothing alerts on a chain's length, a queue's age, a missing brief or a spent site budget ([01](01-WHATS-EXACTLY-THERE.md) §1.6).

---

## §16 · The product now: the relief track

These change today's product, behind a row per tenant, measured before and after, while the notebook proves the loops. Owner: Harsh, with the agents Harsh assigns; each needs Rohit's approval (04).

| # | What | Done when |
|---|---|---|
| **R1** | **Measure today's runs:** one `loop_runs` row per tick, per chain and per Sync pass: what woke it, its stages and their times (from `platform/stage_timer.py`), counts, cost, errors. Set the build SHA at build and deploy. `scripts/release_gate.py` with conditions 1, 2, 3 and 5 (§11.7). No behaviour change | a day of chains can be read from the table; `/health` names the code; `release_gate.py` exits non-zero on a seeded failure of each of its four conditions |
| **R2** | **Take the whole-company passes off the per-mail chain:** the org-wide passes inside `context/runner.process_pending` (period, support, meeting and channel touches, outreach, documents, spend and history, attention, situation refresh; the exact list read from the code) move to their own schedule per tenant, at night in the company's time; the per-event drain stays on the chain. For 3 days the old chain's cards and the new chain's are kept side by side | the chain under 30 min; a new mail on a live situation reaches its card within 30 min; the cards differ only in timing |
| **R3** | **The company's time in every dossier and every clock:** both dossiers print local time beside UTC (`reason/expert/dossier.py:194`, `reason/l2/dossier.py`), "today" counted in the company's day; the site budgets' and the daily cap's day in the company's day; the support clock in the company's working hours | a golden case like `f1` is read in the right tense; the judge's day rolls at local midnight |
| **R4** | **The morning brief on its own job** at 08:00 company time, its outcome recorded each day, an alert at 08:30 | 7 of 7 days, each within 15 min of 08:00 |
| **R5** | **Stop paying twice for a bad answer:** the answer's shape checked as soon as it arrives; at most one repair, carrying only the failing part; the failing field recorded | under 10% of the judge's spend on discarded answers (today 39%) |
| **R6** | **A runbook for onboarding a design partner** (D-P1-9): one script and one page, extending `scripts/activate_tenant.py`: §11.6's six exclusions on in their preconditions' order (expert review, L2 reasoning, L2 cards, `cards_from_situations`, `card_copy`, `morning_brief`); the packs that fit a founder; the wedge's `capability_allowlist`; capture policies per seat and source (Screen off); the capture window (365 days) and the onboarding budget; the time zone confirmed by the founder; then the first day's health read | a dry run on a test tenant completes with no step done from memory |
| **R7** | **Name the wake-ups right** (D-P1-16): the trigger enum on L2's request replaces `_trigger_of`'s substring relabel (`reason/l2/sweep.py:198-204`); `founder_asked` passed by its callers; a subject that fails twice parked so it no longer holds L2's watermark at the first bundle | 0 runs labelled only `bundle`; the watermark advances; the oversized file is parked with its reason |
| **R8** | **Make the switches and the ticks bind** (D-P1-16): the kill switches and the paused and plan-expired checks read by every thread (the warm lane, the sync worker, the heavy tick's upkeep); a cut tick cancels its work; the per-org daily cap stops the chain as well as the pull | a kill switch stops every thread within one tick; no tick runs beside the next; an over-cap tenant is not chained |
| **R9** | **Retention in the product** (U13-41): the platform's retention job nightly per tenant, in the company's night, behind a row, per `tenant_retention_policy`, first when the database is over its ceiling (§8.1 step 9) | a database over its ceiling falls under it after one run; a held row survives |

## §17 · Failure handling

| What goes wrong | What happens | Never |
|---|---|---|
| A worker crashes or is deployed mid-run | its leases lapse in 2 min; its wake-ups return to pending; the open sweep rolls back, and sweeps already committed stay (§5.2); the run row closed `failed` by the next worker | a judged situation paid twice; a half-written run |
| The model provider is slow or down | P4's ladder runs (one retry, on a narrower packet and on the policy's fallback model, then `abstain`: one shared allowance of one extra paid call per input hash, P4 07 §15); P1 adds no attempt and the subject is parked with its reason (§9.6); health shows it. Maintain recovers a subject parked after P4's `timeout` or `model_error` termination (in its `detail`) with one `maintain` wake-up and no person, only when its input fingerprint has changed or after a provider-wide outage once calls through P4 are answered again (read from the ledger; P1 makes no probe call of its own), and then at most once per input fingerprint; otherwise it stays parked with detail `recovery_exhausted` and one alert; a subject parked for any other reason stays parked. If every call is refused, existing cards stay open, each subject is parked once, and one alert fires (§15.3); a lane that reads nothing for a day alerts `lane_no_data` | a payment beyond P4's ladder; a failure read as "nothing to do"; an outage that empties the cards |
| A subject has no expertise, or a capability is missing | P4 returns `abstain` with P3's gap row; P1 closes the wake-up `done`, records the run `abstained` with the gap row's id, makes no repair or retry, and re-wakes the subject (as `maintain`) only when P3's pack pointer for that kind moves | a retry until a model answers |
| An answer is malformed or cut off | one repair carrying only the failing part; a truncation adjusts the budget | a blind re-ask |
| Two runs race on one subject | the loser is re-queued once against the new version (`stale_read`) | a blind merge |
| A cap is hit | work stops in priority order; the skipped items are listed and carried; one alert per cap per day, and one for each skipped item that is ours to do (§15.3) | a silent short; a safety item deferred |
| A source's login is revoked, or a source is partial | capture marks it; Evolve keeps judging dates on what it has and says what it cannot see | silence treated as a finding |
| A rung is missed while the worker is down | fired late if still useful, else written `missed` and the next rung computed | a stale drop after its moment |
| A meeting is cancelled or moved | its wake-ups are dropped or moved with it | a prep or follow-up for a meeting that did not happen |
| The database is over its ceiling | an alert; Maintain's retention runs first | a silent drop |
| A plan lapses, or the tenant pauses | no wake-up is claimed and none produced; pending wake-ups stay `pending` and resume on renewal or resume (§11.3); reads still work; one `loop_runs` row per local day lists the refusal in `skipped` with its reason (`paused`, `plan_expired`); one alert per tenant per day for a lapsed plan | spend; a silent drop of the tenant's work; a lapse seen only as an alert or a log line |
| Admission holds many in one sweep | none of those subjects is saved; the old pages stand; the held reasons are listed on the run row and counted in health | a held version shown as admitted |
| A page is reported wrong | the founder's correction writes a locked version (§7.3) and wakes that subject only | a later model pass over the correction |
| A tenant is deleted | §13.4: its wake-ups cancelled, every P1 row erased with its evidence | a P1 row left behind |
| An onboarding phase is stuck | it resumes from its checkpoint; after an hour, an alert | "Ready" without first intelligence |
| A receipt cannot be written | that subject's savepoint rolls back, an error row is written, health counts it; the previous page stands | a result without a receipt |
| A failed run | its subject stays exactly as it was, with a failure row | a subject marked handled because its run failed |
| The time zone is unconfirmed | instants print UTC with "time zone unconfirmed"; nothing says "today" from UTC; interruptions wait (containment excepted) | "today" on the wrong day |

---

## §18 · Tests

Each test is a fixture from the ideal cards ([10](../10-ACCEPTANCE.md)), the replay or an adversarial case, run in the notebook first and against the product's path at its step. **The full list of each step's tests is under its Test in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md);** this table names them by area.

| Area | Tests |
|---|---|
| **Clock** (P1-1) | 01:40 UTC prints "Fri 23 Oct, 07:10 IST (01:40 UTC)"; a 05:00 UTC meeting prints "10:30 IST, later today"; a date with no time is a whole local day and passes at local midnight; a rung changes at local midnight, not UTC midnight; a zone with summer time is right on both sides of the change; 1 Nov 2026 prints as a Sunday; a two-working-day reply owed from a Friday is due Tuesday; an unconfirmed zone prints "time zone unconfirmed" and says no "today" |
| **Ledger** (P1-2) | a run with a fake model writes one complete row; a run that hits the cap lists every skipped item; a crashed run is closed `failed` with its error; a zero-call run, a no-card run and a held run each write a row; every model call carries its run id |
| **Spend** (P1-7) | a tiny cap judges the top items in priority order and lists the rest; two processes started together never pass the cap; a malformed answer that fails its one repair is held with its reason, and a timeout pays at most P4's ladder (2 calls), never a third; a safety item is judged though the cap is short; bands 1–2 keep their reserved share; a fake client that refuses every call leaves the existing cards open, parks each subject once with its reason, fires one alert within one tick, and the health row counts the failures |
| **Wake-ups and dates** (P1-4) | a day with no new mail and no date crossing makes 0 calls; one new reply re-judges one situation and its goal; a deadline reaching "today" re-judges its situation with no new mail; the same rung never fires twice; a July expected-by date already judged as passed does not fire again; five mails in 11 minutes are one judgment; a broadcast to many recipients is one wake-up and no card per recipient; `f1`'s 11:10 surface time fires at 11:10 after a forced pull; `f4` wakes on the reviewer's reply or Mon 10:00, whichever is first, and the other is cancelled; a cancelled meeting drops its wake-ups; a resolved situation cancels its pending wake-ups; a rung missed in downtime fires late only if still useful |
| **Evolve** (P1-4) | the order evidence → place → situations → goals → cards holds; a three-step dependent chain converges in 3 rounds, a cyclic one stops at the cap (3) with `non_convergence` on the run row; a second full sweep is never run; at most 10 subjects a sweep, the rest carried with their reason; a stale read is re-queued once |
| **Onboard** (P1-3) | a stop in the middle of judging resumes without paying twice; the dry-run estimate is within 20% of the real cost; "Ready" never shows before phase 6; no past rung fires during history; wave 1's cards include `f1`, `f2` and `p1`; a team's first run is refused until its cap is set |
| **Act** (P1-5) | a recorded Done ("submitted") on `f2` moves its card to verifying, and only the proof (the confirmation, or "It's done" where no source can show it) closes it and moves the accelerator goal's plan step; "Later until a date" hides a card until that date, then wakes it, and a matching arrival brings it back early; an agent's send stays reported until the mail appears; a press on a moved card version wakes nothing |
| **Maintain** (P1-6) | the stale July scheduling cards close, and no ideal card is lost; the brief is composed at its brief hour every day (08:00 by default), and its absence alerts `brief_margin` later (08:30 by default); predictions due are scored; the date index's coverage report finds a seeded deadline with no wake-up; a ladder rung due at 09:00 is fired by the minute scheduler, planned and advanced by L4, and its reminder's outbox row carries the same run id and leaves in that run, while a seeded order with distribution before the executive step fails |
| **Replay** (P1-8) | every event of 10 §3 on its day; the clock-only events to 2 Nov; a quiet day $0; two replays give the same wake-up list; a recorded replay of 23 Oct to 2 Nov makes 0 calls, costs $0, and gives the same wake-up list and the same held and refused counts twice |
| **Many tenants** (P1-9) | no row of one build is read by the other; each ledger accounts for its calls; the work interleaves; each build's tenant cap holds under the one platform cap, and neither build draws on the other's; when build A's model client raises on every call, A's run is closed `failed` with A's `org_id` and B completes with its alone-result; one source with an expired login leaves the same tenant's other sources pulled and judged, and the run row shows that source's coverage as partial |
| **Drill** (P1-10) | each disruption resumes; nothing is paid twice; the second seat's private item stays private |
| **Switches** (P1-11) | flipping each switch changes what runs; a switch whose claim disagrees with the ledger alerts; a kill switch stops every thread; a shadow loop publishes nothing; a new fixture tenant needs no row written by hand; the registry has no switch whose effect is a formula verdict, and a seeded one fails OG-10; a fixture tenant has calibration apply, `recommendation_acceptance`, the staged mute ladder and learned Adaptive leases all unarmed, and a weekly calibration run on it writes only shadow rows (kind, count, window) and leaves every card, threshold and mute unchanged |
| **Process** (P1-12) | a deploy mid-run loses nothing; a timeout cancels its work; a parked wake-up alerts; the caches rebuilt from Postgres give identical wake-ups; a manual Sync during a running Evolve waits at most the lease bound, then returns with its wake-up pending, and the wake-up is claimed within one tick of the holder's finish, with 0 events lost |
| **Failure classes** (each at its row's step) | one fixture per row of §17, each showing its "What happens" and none of its "Never", at these steps: P1-1 the unconfirmed zone; P1-2 a failed run; P1-3 a stuck onboarding phase; P1-4 no expertise, a race, a missed rung, a cancelled or moved meeting, admission holding many, a receipt that cannot be written; P1-5 a page reported wrong; P1-6 the database over its ceiling; P1-7 the provider slow or down, a malformed answer, a cap hit; P1-9 a revoked or partial source, a deleted tenant; P1-11 a lapsed plan or a pause; P1-12 a worker crash or deploy |

## §19 · Guards (CI)

| Id | Fails when | Step |
|---|---|---|
| OG-1 | A loop path can finish without writing its `loop_runs` row (a syntax-tree check over `reason/loops/` and `nb/loops.py`, with a seeded mutation) | P1-2 |
| OG-2 | A module on the run path reads the wall clock (`datetime.now`, `time.time`, `now()` in SQL) instead of `eval_time`; or a loop's test fixture states a fixed calendar date beside a wall-clock window | P1-1 |
| OG-3 | Code computes "today", a weekday, a local hour or a cap's day without `clock.py`; or a P1 write stores a value derived from now (an age, days waiting, overdue hours, a relative phrase) instead of the typed date | P1-1 |
| OG-4 | A wake-up is written without a key, a trigger from the closed list, or a producer named in the registry | P1-4 |
| OG-5 | A date rung creates or edits a card directly, instead of waking a judgment | P1-4 |
| OG-6 | Evolve's path calls a whole-company pass (the org-wide passes of `process_pending`, a full sweep) | P1-4, R2 |
| OG-7 | A model call happens outside the register, without a run id, or without a reservation against the database-held cap. Scope: `reason/loops/` and `nb/` now; repo-wide once P4-16 registers the call families outside the register today, with an allowlist that only shrinks | P1-7 |
| OG-8 | A skip, a carry or a cap stop leaves no listed reason on its run's row, or any P1 row writes a reason outside the closed list (§10.1) | P1-7 |
| OG-9 | A loop publishes while its policy row says `shadow`, or runs while it says `off` | P1-11 |
| OG-10 | A switch that changes behaviour is missing from the registry, or has no test that flipping it changes what runs; a registry row's `armed`, `precondition` or `owner` disagrees with the code (its default value, the activation precondition table, an environment flag's default); a learning switch is armed with no decision id in 08-LOG; or a switch's effect is a formula or a code rule deciding in the model's place | P1-11 |
| OG-11 | A P1 query of a table that holds tenant rows runs without `org_id`; such a table lacks `org_id`, `trace_id`, `visibility` or `schema_version`, or a row is written to it without them (`plan_economics`, a platform table, is outside this check, §13.1); or P1 reads another layer's tables instead of its API | P1-4 (reads only through P2's API), P1-9 (every P1 table that holds tenant rows has the four columns) |
| OG-12 | A receipt-replay path (`nb.cli replay-run`, Maintain's replay sample) or a recorded replay (`nb.cli replay --mode recorded`) imports a model client, or a model call from it does not raise; any replay writes to its source build; or a replay reads a row whose evidence or known time is after its instant | P1-8, P1-6 |
| OG-13 | A door that starts work skips the one gate function (§11.3) | P1-11 |
| OG-14 | A table P1 adds that holds tenant rows is missing from the erasure list (`plan_economics`, a platform table, is outside, §13.1) | each table's own step (P1-2, P1-4, P1-5, P1-6 for `weekly_rollups` and `learning_shadow_rows`, P1-7, P1-11, P1-12 for `subject_leases`, R1) |
| OG-15 | A module under `reason/loops/` or the notebook's `nb/clock.py`, `nb/ledger.py`, `nb/triggers.py`, `nb/dates.py`, `nb/loops.py` imports a model client, a gateway or a prompt, or calls one; calls P4's `run_subject` directly instead of P4's sweep (`l2_pass`); or writes a page, a goal's status or a card other than through P2's door and P5's card step. Model work goes only through P4's sweep, the placement call, the goal run and the analyse pass | P1-4 |
| OG-16 | A module under `reason/loops/` or `nb/loops.py` imports or calls a send, a reply or a connector write (P1 never sends, §7.4) | P1-5 |
| OG-17 | Loop code (`reason/loops/`, `nb/loops.py`) names a department, a domain, a pack or a situation type, or holds a literal of a tenant's data (a name, an address, an id, an amount; P5's CG-12 extended to P1). `platform/switches.py` is outside this scope: it holds domain names only as data rows | P1-4, P1-9 |
| OG-18 | In L4's tick, the distribution call comes before the executive step (plan commitments, then advance each due execution, §8.4) | P1-6 |
| OG-19 | An onboarding, replay or rebuild path issues a `DELETE` on situations, works, cards, decisions or founder acts, or mints an id not derived from its subject's key | P1-3, P1-8, P1-12 |
| OG-20 | `scripts/release_gate.py` (§11.7) is missing, or one of its conditions has no test that makes it exit non-zero | R1 (conditions 1, 2, 3, 5), P1-11 (adds condition 4) |

Each guard is a syntax-tree check where it reads code, and each has a test and a mutation that proves it catches what it names; a guard changed in the same change as the code it guards is re-proved (the repo's rule). The loop modules (`reason/loops/`, `nb/loops.py`) are registered with the repo's layer guard as modules that may call only P2's, P4's and P5's entry points, with its mutation test added at P1-12; the card guard, the situation-site ratchet and the layer guard stay green at every step (§14.5).

---

## §20 · What changes against today

| Today | Target |
|---|---|
| A 15-minute tick and a 6-hour tick inside the web server; chains back to back | A worker of its own; wake-ups with keys; work in proportion to what changed |
| Only new mail starts a chain; every run labelled `bundle` | Nine named triggers, each with a producer; a date, a silence, a goal change, an act or a result wakes only its subject |
| No date index; 0 date wakes in the week | Every date that can wake a subject indexed, with its rungs in local days and its instants at minute grain |
| 97-minute chains, 69 minutes of them whole-company passes | Evolve touches only the named subjects; whole-company work only in Maintain at night |
| UTC caps and dossiers; cards born only 07:00–13:59 IST | The company's clock everywhere; caps by the local day |
| Each site with its own UTC-day wall; 39% of the judge's spend discarded | One database-held cap per tenant, spent in priority order, never silently short; one repair at most |
| No run ledger | One append-only row per run, with its triggers, subjects, cards, cost, skips, coverage and timing |
| Onboarding is the chain with a bigger backlog; "Ready" at 3 h 39 min with 0 reviews | Named phases, two waves, a one-time budget; first intelligence within 2 h; "Ready" only after first intelligence |
| Founder acts and results wait for the next chain | Every act and result is evidence and an Act wake-up at the highest priority |
| About 20 upkeep jobs on the 6-hour tick; the brief at the tail of a sweep | Maintain at 02:00 and weekly, each job a ledger run; the brief on its own job at 08:00 |
| Switches that report success while nothing happens; kill switches that don't bind the threads | One registry, checked daily against the ledger; one gate for every door |
| A new tenant gets the old packs and no brain | A new tenant on the new path by default, no row by hand |
| No replay of real history | An event-time replay of 23 Oct to 2 Nov, and the onboarding and load drills |

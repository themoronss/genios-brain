# P1 · Orchestrator · 05 · How it will be done at production level

**Owner:** Harsh, with the coding agents Harsh assigns. Claude writes units with their tests on request. Rohit approves each tenant's activation.
**Rule:** nothing here starts before the same step has passed in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)). The relief track (R1–R9) is the only exception, and each of its steps is behind a row. The full specification is [07](07-THE-ORCHESTRATOR-SPEC.md); this file is how it goes into the product.

---

## 1 · The target: one orchestrator, four loops, one path

Today's sweep runs three reasoning paths (expert, L2 in shadow, legacy lanes) and the compiler pass. Every chain redoes the whole company. The target is one path per tenant, and work in proportion to what changed:

```
producers                          queue                         workers (their own process)
  capture: new evidence ──┐                                      ┌─ ONBOARD   once per tenant, in waves; re-runnable
  date index (minute, hourly)┤                                   ├─ EVOLVE    each wake-up, after a 10-min quiet window
  goal changed ───────────┼──► loop_wakeups (one row per key) ──►├─ ACT       each founder action or execution outcome
  founder acted (API) ────┤      priority · due · tenant         └─ MAINTAIN  nightly lifecycle; weekly correlate + analyse
  schedule (local hours) ─┘
                each run: place → situations (L2 judge on pages) → goals → cards → close
                each run writes one ledger row: what woke it, what it touched, what it cost, what it skipped
```

**Whole-company work happens only in Maintain**, at night in the company's time, and over pages rather than mail. Evolve touches only the situations and goals its wake-ups name.

## 2 · The pieces, and where they live

**Process (D-P1-7):**
- **API.** Serves requests. It writes wake-ups (a founder action, a manual Sync) and reads results. It no longer runs the scheduler, the chain or the workers.
- **Worker.** The same image with its own start command, for example `worker: python -m genios_engine.reason.loops.worker`. It holds:
  - the producers (the date index, the schedule);
  - the queue consumers;
  - the capture schedule that today lives in `platform/scheduler.py`.
- **Deploys.** A worker stops claiming new work, finishes or releases what it holds (leases are 2 minutes), and exits. Every step is idempotent, so the next worker carries on.

**Code:** a new package, `genios_engine/reason/loops/`, one module per job.

| Module | Job |
|---|---|
| `triggers.py` | Turns events into wake-ups, one producer per trigger of the closed list (07 §3.1: new evidence, date rung, news, goal changed, founder, maintain, need met, outcome, human ask). It starts from the expert pass's trigger set (`reason/expert/triggers.py`). Keys are idempotent: (tenant, subject, trigger, rung or evidence id) |
| `dates.py` | The date index (07 §4): every kind of entry, its rungs, a minute-grain scheduler for instants and an hourly sweep for day rungs, the forced pull before a timed wake, catch-up after downtime |
| `queue.py` | The `loop_wakeups` table: one pending row per key, claimed with `FOR UPDATE SKIP LOCKED` and a lease (the warm lane already works this way) |
| `runner.py` | Consumes the queue. One Evolve run per tenant at a time (the existing `org_run_leases`) and at most one Act run; one run per subject at a time across loops (07 §12.3–12.4). Wake-ups for one subject coalesce into one run. Steps run in the goal-first order. Each step is wrapped, so a failure costs that subject only and is retried on the next run |
| `onboard.py`, `evolve.py`, `act.py`, `maintain.py` | The four loops, each a thin sequence of calls into P2, P3, P4 and P5 |
| `ledger.py` | The `loop_runs` table (§5) |
| `clock.py` | The tenant's time zone from the company page, with its confirmed flag, the working week and the holidays, used for every printed time, every "today", every rung, every local hour and every cap's day (07 §2) |
| `budget.py` | Reads spend from the ledger, not from the process. Ranks the wake-ups (§6). Stops at the cap and lists what was skipped |
| `policy.py` | Reads `tenant_loop_policy` (§4) |
| `platform/switches.py` (outside this package, §4) | The registry of every switch, the daily check against the ledger, and the one gate function every door asks (07 §11.2–11.3) |
| `worker.py` | The worker's entry point: the producers, the consumers and the capture schedule (07 §12) |

**Tables:**

| Table | Holds |
|---|---|
| `loop_wakeups` | id, tenant, loop, subject (situation, goal, connection, seat or org), trigger, rung or evidence id, due at, priority class, severity, seat, visibility, request id, state (pending, claimed, done, coalesced, skipped, cancelled, missed, failed, parked), lease, attempts, run id; full field list: [07](07-THE-ORCHESTRATOR-SPEC.md) §3.3 |
| `loop_runs` | One row per run (§5; 07 §10.1) |
| `date_index` | One row per date that can wake a subject: its kind, instant or local day, provenance, basis, rungs and state (07 §4.2) |
| `tenant_loop_policy` | One row per tenant per loop: state (off, shadow, live), caps (daily and one-time), model and thinking per site, the quiet window, the local hours (Evolve's daily pass, Maintain, the morning view), notes, who set it and when |

**Lanes and limits:**
- A global pool of N workers (1 on the product until the load drill passes by its pool rule, then 4; the notebook and its other drills start with 4; 07 §12.3).
- Onboarding has its own lane, with at most 2 tenants at once. A big first week can never starve the daily Evolve of the tenants already live, and the others queue with an honest estimate.
- Act wake-ups have the highest priority.
- Maintain uses the Message Batches API at half price, at night in each tenant's own time.

## 3 · The date index: how silence becomes a wake-up

- Every situation page (P2) stores its expected-by date and its stated deadlines. Every open loop stores its due date, every goal its deadline, every lease its end, every waiting card its next check; L4's ladder rungs and the calendar's event ends are entries too (07 §4.1). They are indexed by (tenant, instant or local date).
- A minute-grain scheduler fires instants (a surface time, an event's end, a slot, a snooze's return, a ladder rung); an hourly sweep fires the day rungs crossed since its last run: within 7 days, tomorrow, today, passed, counted in the company's local days. Both write wake-ups.
- The key carries the rung, so a date fires once per rung and never again. A page that already knew it was overdue is not judged again for nothing.
- This is what makes the 13 of 20 ideal cards about things that didn't happen reachable. Today the L2 pass reads new bundles only (`reason/l2/sweep.py` R1), and 0 of 138 runs were started by a date.

## 4 · Activation: rows, not flags, with one list of switches

- **One row per tenant per loop** in `tenant_loop_policy`, moving `off` → `shadow` → `live`.
  - In shadow the loop writes pages, goals and draft cards to their tables, flagged as shadow, and nothing reaches the founder.
  - In live it publishes.
- **The legacy lanes and the expert pass are switched off for a tenant only after the parity gate.**
  - The gate is the acceptance set ([10](../10-ACCEPTANCE.md)), run on that tenant's golden cases.
  - Its numbers are **written down before the run**, as `reason/cutover.py` already demands.
- **New tenants (D-P1-9).**
  - Until the new path passes the acceptance set on the golden tenant, a new customer is a design partner, armed by the runbook (R6).
  - After that, `make_tenant_live` gives every new tenant the new path, live, from its first day. There is nothing to compare against for a new tenant, so nothing is switched by hand.
  - The old sales and support packs stop being defaults for a founder tenant (P3 §3).
- **All switches get one registry,** in `platform/switches.py`. It lists the seven cutover switches, every L1–L4 activation, every loop row and every environment flag that changes behaviour, each with its meaning and with the ledger evidence that proves it ran.
  - A daily check compares what each switch says against what the ledger shows actually ran.
  - That ends "the switch reported success while nothing happened" (P1 F4).

## 5 · Health, alerts, rollback

**The ledger, `loop_runs`, one row per run:**
- tenant, loop, run id, code SHA, policy version;
- started, finished, the instant it judged from and to;
- what woke it (counts by trigger);
- what it touched (situations, goals);
- cards opened, updated and closed;
- model calls, cost, and how many were refused or thrown away;
- what it skipped and why;
- errors, and status (ok, partial, failed, cap hit).

**Health:** `platform/daily_health.py` gains a loop line per tenant, read from the ledger:
- runs per loop;
- wake-ups fired, by trigger;
- situations and goals judged;
- cards changed;
- cost;
- high-priority items skipped;
- errors;
- the time from new mail to updated page.

**What the founder can count on** is one list, [07](07-THE-ORCHESTRATOR-SPEC.md) §15.2: each promise with its target and the ledger stamp it is measured from. New mail on a live situation, for example, reaches its page and card for 90% within 30 minutes of the mail landing, quiet window included. One function computes every promise from `loop_runs`, `loop_wakeups` and the onboarding milestones, never from logs or write times; its test is in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md). This file keeps no second copy of the list.

**Alerts:**
- a loop that didn't run in its period;
- a promise above missed;
- a cap hit with skipped items that we owe;
- a switch whose claim disagrees with the ledger;
- the database over its ceiling;
- an onboarding stuck in one phase for more than an hour;
- the full list is 07 §15.3, each with an owner, through a webhook proven in production (today it is empty by default).

**Rollback:**
- Set the tenant's loop row back to `shadow`.
- The legacy lanes can be re-enabled per tenant by their own rows.
- Nothing is deleted, so a rollback loses no conclusion.

## 6 · Money

**Priority, when the budget is short:**
1. the founder acted;
2. we owe something, or a date is today or passed;
3. a goal is at risk or blocked;
4. the nearest deadline;
5. the stakes;
6. the rest.

The first two keep a reserved share of the day's cap (60% to start, D-P1-15); safety items are never deferred. What is skipped is listed in the run's row and in the daily health. Every cap's day is the company's local day (today the judge's rolls at 05:30 IST).

**Budgets per tenant:**
- one per loop, from `tenant_loop_policy`;
- onboarding has a **one-time** budget of its own, so a first week never eats the daily one (F11);
- the platform-wide cap stays above them all.

**Answers are checked before a retry.** A malformed answer is repaired once, with the error shown, and its failing field recorded (R5); never a third paid attempt on one input (P4 07 §15). Today 39% of the judge's spend is thrown away.

**Cost per founder-size tenant at today's prices** (claude-sonnet-5, thinking off), from what was measured:

| | Today's product (measured, 22–28 Oct) | Target (from the notebook's measured unit costs) |
|---|---|---|
| Onboarding, **once** | $17.55 from connect to "Ready" ($13.43 L1 reading the backfilled mail); $27.78 in the first 24 h | Reasoning under $10 for six months of mail (`b2`: $8.41 for 378 situations), under $15 for 365 days. Plus reading the mail at capture. Whether the notebook path still needs L1's per-mail extraction is a P2 question |
| A normal day | $4.34–6.86, about $5.67: $1.88 reading the data (L1, entity resolution, Screen) and $3.78 reasoning and cards. The judge is capped at $2 and makes about 12 paid consults | Under $0.50 for reasoning: 10–25 touched situations at about $0.02. Reading the data as today, unless P2 changes it |
| Maintain | inside the day above | Under $1 a week, on the batch API |
| **A month** | **about $170**: $57 reading the data, $113 reasoning and cards | **Reasoning under about $20** (Evolve about $15, Maintain about $4). Reading the data: $57 today, P2's question. Measured, not estimated, once the replay runs (P1-8) |

**A cost figure is quoted to a customer only when it is a measured row of P1-8's report,** never from the Target column above. That report gives the cost per tenant, per judged subject and per admitted situation, from `cost_by` over `loop_runs` and `llm_costs` (07 §10.3).

## 7 · Migration order

1. **Measure (R1).** The ledger row per tick and per chain, and the build SHA. No behaviour change.
2. **Relief (R2–R5, R7–R9).** Each behind a row, for this org first:
   - the whole-company passes move off the per-mail chain;
   - the company's time goes into the dossiers;
   - the morning brief gets its own job;
   - retries are checked;
   - the wake-ups are named right, and the switches and the ticks bind (R7, R8);
   - retention runs nightly per tenant (R9).
3. **The worker process** (D-P1-7). Today's chain runs unchanged inside the new runner, as "legacy Evolve", so every run gets a ledger row and goes through the queue before any logic changes.
4. **The date index and clock wake-ups** on today's L2 pass (U13-22, U13-23), with the onboarding budget (`07` D2).
5. **The notebook tables (P2) in production, in shadow**, written by the new L2 page judge (P4) for one tenant.
6. **Goal pages for that tenant, in shadow.**
7. **Cards from pages and goals for that tenant, behind its row.** The old makers keep running beside them, and the founder sees only the old ones.
8. **The parity gate** (P1-11, G-Parity of 07 §14.4) on that tenant's golden cases, one switch per commit. If it passes:
   - the new path goes live;
   - the expert pass and the legacy lanes are switched off for that tenant (U13-31, `07` D5).
9. **New tenants start on the new path** (D-P1-9). Existing tenants switch at their own gates.

At every stage the old path keeps working until the gate passes. A failed gate means the tenant stays where it is, with the failing lines named.

## 8 · Capacity: how many tenants one deployment carries

**Today (measured on one tenant):**
- A chain is about 97 minutes, and chains run back to back.
- Chains for different tenants run one after another inside a tick, with one warm-lane slot for the platform.
- So the engine keeps about **one** founder-size tenant current. Each further tenant of this size adds roughly another chain-length to everyone's wait. This is an estimate: no multi-tenant run has been measured.

**Target (from the notebook's measured unit times):**
- A page judgment takes about 8 seconds of model time (mean 8.1 s; `b2`: 379 judgments in 7.7 min at 8 at once).
- A tenant's normal day is 10–25 judgments, so about 2–4 worker-minutes.
- One worker can then carry many founder-size tenants for Evolve. The limits become:
  - the model provider's rate limits;
  - the database;
  - onboarding, which takes about 51 worker-minutes of judging for a founder-size tenant (`b2`'s 379 judgments), plus the hours of capture.
- So onboarding is its own lane, with at most 2 at once.

**Proved before any second customer:**
- P1-9: two tenants in the notebook;
- then a load drill: the engine against the local copy, with the golden tenant cloned under new ids, 2, 5 and 10 times;
- measured each time: the time from new mail to page; worker use; database statements and size; cost.

## 9 · Failure modes and what happens

| What goes wrong | What happens |
|---|---|
| A worker crashes or is deployed mid-run | Its leases lapse in 2 minutes. The wake-up returns to pending. Steps are idempotent: a judged situation is not paid twice, because its page version is checked first, and an answer already in P4's answer store is reused; only a call in flight with no stored answer is paid again |
| A run passes its timeout | Its work is cancelled, never left running beside the next (today a cut tick runs on) |
| A rung is missed while the worker is down | It fires late only if still useful; otherwise it is written `missed` and the next rung computed |
| The model provider is slow or down | P4's ladder runs: one retry, on a narrower packet and on the fallback model, then abstain; with the repair and the generic-answer retry it shares one extra paid call per input hash, so at most 2 paid calls (P4 07 §15). P1 adds no attempt: the wake-up is parked with its reason, and Maintain recovers it only as [07](07-THE-ORCHESTRATOR-SPEC.md) §9.6 says. Health shows it |
| A tenant's login is revoked | Capture marks the connection (as today, `_connection_still_valid`). The tenant's Evolve keeps judging dates on what it has, and says what it cannot see |
| A cap is hit | Work stops in priority order. The skipped items are listed, and an alert fires if any is ours to do |
| The database is over its ceiling | An alert, and Maintain's retention runs first. Nothing is dropped silently |
| A plan lapses, or the tenant pauses | No wake-up is produced and none is claimed; pending ones stay pending and resume on renewal or resume. Reads still work (`billing.py`'s rule) |
| An onboarding phase is stuck | It resumes from its checkpoint. After an hour in one phase, an alert fires |

## 10 · Leaving: offboarding and erasure

- When a tenant leaves, or is erased:
  - its wake-ups are cancelled;
  - its loop rows are set to `off`;
  - its worker leases are released.
- Then the existing erasure path deletes its conclusions with its evidence, and every P1 table with them. The list is [07](07-THE-ORCHESTRATOR-SPEC.md) §13.4's: `loop_wakeups`, `loop_runs`, `tenant_loop_policy`, `date_index`, `parity_gate`, `switch_registry_checks`, the reservation rows, `daily_health` and its loop health rows, the outcome label rows, `weekly_rollups`, `subject_leases`, `learning_shadow_rows`, and the activation rows (`plan_economics`, a platform table, is outside it). Each new P1 table joins the list in the step that adds it (OG-14).
- No wake-up is produced for an org that has no active connection and no live loop row.

## 11 · What must never happen

- **A run that spends without a ledger row.**
- **A loop that publishes while its row says `shadow`.**
- **A tenant switched to the new path without its parity numbers written down first.**
- **Silence treated as a finding when a source was not fully read.** The ledger records coverage per source.
- **Whole-company work on the per-mail path.**
- **A new tenant that needs a switch flipped by hand** once the new path is the default.
- **One tenant's backlog delaying another tenant's founder.**
- **A switch that reports on while nothing runs,** or a kill switch that does not stop every thread.
- **A rung that fires twice, or a date that makes a card by itself.**

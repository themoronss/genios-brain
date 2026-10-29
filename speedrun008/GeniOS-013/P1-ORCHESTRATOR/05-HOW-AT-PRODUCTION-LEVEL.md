# P1 · Orchestrator · 05 · How it will be done at production level

**Owner:** Harsh, with the coding agents Harsh assigns. Claude writes units with their tests on request. Rohit approves each tenant's activation.
**Rule:** nothing here starts before the same step has passed in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)).

---

## 1 · The target: one orchestrator, four loops, one path

Today's sweep runs three reasoning paths (expert, L2 in shadow, legacy lanes) and the compiler pass. The target is one path per tenant:

```
triggers ──► queue of wake-ups ──► loop runner (per tenant, per loop)
  new evidence (capture)              ├─ ONBOARD   first-day pass, once per tenant (re-runnable)
  a date crossing a rung              ├─ EVOLVE    daily, plus each wake-up
  a goal changed                      ├─ ACT       on each founder action or execution outcome
  the founder acted                   └─ MAINTAIN  daily lifecycle, weekly correlate and analyse
  the schedule
                 each run: place → situations (L2 judge on pages) → goals → cards → close
                 each run writes one ledger row: what woke it, what it touched, what it cost, what it skipped
```

## 2 · The pieces, and where they live

**Code:** a new package `genios_engine/reason/loops/`, one module per job:

| Module | Job |
|---|---|
| `triggers.py` | Turns events into wake-ups. Starts from the expert pass's trigger set (`reason/expert/triggers.py`: first look, new evidence, date closing in, reply overdue, past normal) and adds goal changed, founder acted and scheduled. The keys are idempotent: (tenant, subject, trigger, due instant) |
| `queue.py` | A `loop_wakeups` table, with one pending row per key and a lease per worker |
| `runner.py` | Consumes the queue. Never two runs on one subject at once. Runs the steps in the goal-first order. Each step is wrapped, so a failure costs that subject only and is retried next run |
| `onboard.py`, `evolve.py`, `act.py`, `maintain.py` | The four loops, each a thin sequence of calls into P2/P3/P4/P5 |
| `ledger.py` | The `loop_runs` table: one row per run, the same fields as the notebook's run record |
| `clock.py` | The tenant's time zone from `orgs.timezone`, used for every printed time and every "today" |
| `budget.py` | Reads spend from the ledger, not from the process. Ranks the wake-ups: we owe something → goal at risk or blocked → nearest deadline → stakes. Stops at the cap and lists what was skipped |

**Tables:**
- `loop_runs` and `loop_wakeups`, both new;
- `tenant_loop_policy`: a per-tenant row with the cap for each loop, the model and its thinking settings, and the Evolve hour.

## 3 · The date index: how silence becomes a wake-up

- Every situation page (P2) stores its expected-by date and its stated deadlines. Every goal stores its due date.
- An hourly job reads the dates that crossed a rung since the last check: 7 days, 1 day, today, passed. It writes wake-ups.
- This is what makes the 13 of 20 ideal cards about things that didn't happen reachable. Today the L2 pass reads new bundles only (`reason/l2/sweep.py` R1).

## 4 · Activation: rows, not flags, with one list of switches

- **One row per tenant per loop** (`loop_activation`): `off` → `shadow` → `live`.
  - In shadow the loop writes pages, goals and draft cards to their tables, flagged as shadow, and nothing reaches the founder.
  - In live it publishes.
- **The legacy lanes and the expert pass are switched off for a tenant only after the parity gate.**
  - The gate is the acceptance set ([10](../10-ACCEPTANCE.md)), run on that tenant's golden cases.
  - Its numbers are **written down before the run**, as `reason/cutover.py` already demands.
- **All switches get one registry.** The seven cutover switches and every new loop row are listed in one table with their meaning.
  - A daily check compares what each switch says against what the ledger shows actually ran.
  - That ends "the switch reported success while nothing happened" (P1 F4).

## 5 · Health, alerts, rollback

- **Health:** `platform/daily_health.py` gains a loop line per tenant: runs, wake-ups fired, situations and goals judged, cards changed, cost, skipped high-priority items, errors.
- **Alerts:**
  - a loop that didn't run on its day;
  - a cap hit with skipped items that we owe;
  - a switch whose claim disagrees with the ledger.
- **Rollback:** set the tenant's loop row back to `shadow`. The legacy lanes can be re-enabled per tenant by their own row. Nothing is deleted, so a rollback loses no conclusion.

## 6 · Cost at production scale

From the notebook's measured build (`b2`), at today's model (claude-sonnet-5, thinking off):

| Loop | Per tenant | How it stays low |
|---|---|---|
| Onboard | about $8–10 once, for ~400 situations and ~1,800 mails | Pages are judged once. The system prompt is cached. Placement uses the cheapest model that passes the acceptance set |
| Evolve | under $0.50 a day | Only touched situations and goals. A day with nothing new makes zero calls |
| Maintain | under $1 a week | Correlate and analyse read pages, not mail. They can run on the batch API at half price |

That is about **$25 a month** per founder-size tenant at today's prices. It is measured, not estimated, once the replay runs (P1-8).

## 7 · Migration order

1. Clock and ledger: no behaviour change.
2. The notebook tables (P2) in production, in shadow, written by the new L2 page judge (P4) for one tenant.
3. Goal pages for that tenant, in shadow.
4. Cards from pages and goals for that tenant, behind its row. The old makers keep running in parallel, and the founder sees only the old ones.
5. The parity gate on that tenant's golden cases. If it passes, the new path goes live and the expert pass and legacy lanes are switched off for that tenant.
6. The same for the next tenant.

At every stage the old path keeps working until the gate passes. A failed gate means the tenant stays where it is, with the failing lines named.

## 8 · What must never happen

- **A run that spends without a ledger row.**
- **A loop that publishes while its row says `shadow`.**
- **A tenant switched to the new path without its parity numbers written down first.**
- **Silence treated as a finding when a source was not fully read.** The ledger records coverage per source.

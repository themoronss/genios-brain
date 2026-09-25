# L3-06 · The timer — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ THE LOUDEST CLAIM IN THIS PLAN WAS FALSE

Written in **five** documents, and presented as the **second of three** highest-value items in
Layer 3:

> *"⛔ THE BIGGEST FUNCTIONAL GAP — nothing evaluates when nothing arrives.
> `due_evaluation` 0 files · `next_evaluation` 0 files.
> **Five of the supplied documents name this independently** (LCX-14, CL-03, TL-01, BW-14,
> LCW-04). A promise due Thursday, with no new mail on Friday, produces nothing — and the
> product's entire value proposition is noticing exactly that."*

**Elapsed time is evaluated at four levels, all of them live and three of them already pinned.**

| | |
|---|---|
| `platform/scheduler` | a **heavy tick every 6 hours** runs L1 → L2/L3/L5 for **every org**, whether or not one message arrived |
| `reason/runner` | per-rule **cooldowns**, so repeated ticks over unchanged data do not re-card a subject |
| `executions` | ⛔ **`next_check_at` IS a registered due instant**, with a real due query: `and (next_check_at is null or next_check_at <= :n)` |
| `situations` | `age_uncorrelated_situations` moves a quiet situation to `dormant` **on time alone** |

⛔ **And `test_the_heavy_sweep_still_reasons_for_every_org` already pins the first one**, asserting
exactly what this step was going to build:

```python
res = routes.run_sync_sweep()
assert sorted(two_orgs.chained) == ["org_new", "org_quiet"]
assert res["orgs"] == 2 and res["orgs_skipped_no_new_data"] == 0
```

### 1.1 · How the grep lied

`due_evaluation` and `next_evaluation` genuinely return zero. **They are not the names this system
uses.** The mechanism is a scheduler thread, a cadence in hours, a cooldown per rule and a column
called `next_check_at` — and a search for two invented names found none of them.

⛔ **Four steps in a row have now corrected their own premise by measuring instead of grepping for a
word I expected.** This is the most expensive instance: it was the headline of an entire wave.

---

## 2. What was genuinely missing — one asymmetry

`test_the_light_tick_is_marked_and_asks_for_chain_on_new_data_only` pins that the **light** tick
asks for the optimisation. **Nothing pinned that the heavy tick does not.**

⛔ **And the cost argument pushes the wrong way.** `run_sync_sweep`'s own docstring says the chain
*"costs ~11k statements at zero events"*, so skipping quiet orgs on the heavy tick reads as a free
win. **It is not a win. It is the entire ability to notice that nobody replied** — and every
existing test would still pass, because the sweep tests call `run_sync_sweep` directly and the
light-tick tests assert the optimisation is *present*. **A reader looking for prior art would find
only encouragement.**

### 2.1 · Built — four guards, nothing else

| | |
|---|---|
| the heavy tick must not ask for the shortcut | the line that would silently end time-based intelligence |
| the light tick must keep asking | ⛔ **both directions** — the saving must survive, or every 15-minute tick pays a full chain per quiet org |
| the heavy tick runs `run_maintenance_sweep`, not `run_sync_sweep` | it also carries card expiry, snooze-wake, retention and billing — **four clocks with no other home** |
| the heartbeat stays bounded | root-caused 2026-08-18 → 08-21: one hung Composio call froze **every** tick for **three days**, silently, because a bare `except` never fires on a hang |

---

## 3. ⛔ The one real gap this step found, and where it belongs

**`situation_interpretations.valid_until` has no reader.**

Written by `context/interpretation_store.py` (built in L2-5). The only `valid_until` reads in the
engine are `correlation_people` and `authority_view`, on **different tables**.

Migration 0183's own comment:

> *"⛔ NULLABLE ON PURPOSE. An interpretation that never expires is not an interpretation."*

**So an expired interpretation stays live for ever.** Same `one writer, zero readers` shape as
L3-02's coverage columns.

⛔ **Not fixed here. `expired` is literally one of the five words in L3-16** (`insert · noop ·
restated · reversed · expired`), and building it here would put the revision machinery in the wrong
step. Recorded and routed.

---

## 4. Result

```
FULL SUITE   13,208 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-06: 13,204 passed · 14 failed
```

**+4 tests · 0 regressions · no migration · no model call.**

**Technique 3 — four mutations, all red:** heavy tick takes the shortcut; heavy tick loses the other
four clocks; light tick stops saving; the heartbeat unbounded.

## 5. What this step does NOT do

* ⛔ **It does not build a timer.** Four exist. Building a fifth beside them is the over-scaffolding
  refused at L3-01 (`DecisionRef`), L3-03 (`scoped_absence`) and L3-05 (lineage).
* **It does not add `next_evaluation_at` to situations.** The 6-hour recompute already crosses every
  boundary; a per-predicate due instant would be an **optimisation**, and there is no measurement
  showing the recompute is too slow. ⛔ **An optimisation with no measurement behind it is a guess
  with a schema change attached.**
* **It does not read `valid_until`.** L3-16.

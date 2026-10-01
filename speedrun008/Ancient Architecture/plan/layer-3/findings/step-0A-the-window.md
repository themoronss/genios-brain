# L3-0A · The window — premise check

**Run:** 2026-09-25 · premise checked BEFORE any code · **no code written yet**

---

## ⛔ The premise check corrected this step three times, and it shrank each time

| I planned to build | measured | verdict |
|---|---|---|
| **A1** raise the backfill window | `BackfillWindow` · `backfill_window_for` · `with_backfill_days` · wired at `platform/wiring.py:86` · admin endpoint `PATCH /connections/{id}/backfill-window` · **5 test files** | ⛔ **NOT A BUILD — one API call** |
| **A2** progressive sync | `backfill_drain` — background, pages until the cursor is exhausted, `cursor_store=None` so it never advances the incremental watermark, `pages_per_round` tuned **1 → 8** against a live run | ⛔ **ALREADY BUILT** |
| **A2b** L2 must run on the new history | `context/backfill.py` — `backfill_layer2`, aliases → correlations → situations, **oldest-first**, safe to re-run | ⛔ **ALREADY BUILT** |

**Three of three things this step was going to build already exist.**

---

## 1. What is actually missing — one seam

```
POST /connections/{id}/backfill   →  backfill_drain            (capture)   ✅
POST /situations/backfill          →  backfill_layer2           (L2)        ✅
                                       ⛔ nothing chains them
```

**Two separate, manually-triggered endpoints.** An operator who raises the window and drains a
tenant's history lands the events — and whether situations are rebuilt from them depends on a
**second endpoint nobody is told to call.**

### ⛔ 1.1 · And the orders disagree, which is why the chain matters

| | order |
|---|---|
| `backfill_drain` (capture) | **newest-first** — *"newest-first + an advancing watermark meant the older tail was never re-requested"* |
| `backfill_layer2` (L2) | **oldest-first**, and its docstring says why |

> *"Events are replayed **oldest-first**. Correlation generations depend on the gap between an event
> and a group's existing span, so **processing newest-first would open a fresh generation for every
> old event and shatter one history into dozens of situations.**"*

**So the two halves are individually correct and the order between them is load-bearing.** The L2
replay must run **after** the capture drain, over the landed events, oldest-first — which is exactly
what `backfill_layer2` does and exactly what nothing calls.

### 1.2 · The normal sweep is nearly right, and "nearly" is the risk

`context/runner.py:269`:

```sql
order by coalesce(se.triage_lane, 'P3') asc, se.occurred_at asc
```

**Oldest-first *within a lane*, lane-first globally.** For incremental mail that is fine — everything
arrives in roughly one lane per sweep. ⛔ **For a 365-day drain it is not the guarantee
`backfill_layer2` gives**, which is why the explicit replay exists.

---

## 2. Cost check

| | |
|---|---|
| **model calls** | ⛔ **none** — extraction is cached, *"a document is extracted once, ever"* |
| **`vocabulary_fingerprint`** | unchanged |
| **migration** | **none** — the setting lives in `connections.capture_scope` jsonb |
| **re-extraction** | none for already-seen documents; new history is a one-time extraction cost |
| **code** | **one wiring change ＋ its tests** |

⛔ **The step the plan called "raise the window and build progressive sync" is a config write and
one chain.**

---

## 3. What this step is now

| unit | |
|---|---|
| **0A-U1** | chain the L2 replay to the capture drain — `backfill_layer2` runs **after** `backfill_drain` reports its summary, in the same background task |
| **0A-U2** | ⛔ **it must run even when the drain reports `TRUNCATED`** — a capped drain still landed events, and leaving them uncorrelated is the *"features look broken while being perfectly implemented"* failure `context/backfill.py` was written to prevent |
| **0A-U3** | the chain **never aborts the drain** — L2-7's lesson: *"a receipt that can abort the thing it is a receipt for turns an accounting failure into a product failure"* |
| **0A-U4** | a test that drives the real endpoint and asserts `backfill_layer2` ran, with the drain's own `cursor_exhausted` recorded either way |
| **0A-U5** | ⛔ **the operator runbook** — window → drain → verify, as a HARSH-ORDER entry, because the window is the operator's action and not a deploy |

## 4. Done criteria

- [ ] capture backfill chains to the L2 replay in one background task
- [ ] the chain runs on `TRUNCATED` as well as on `done`
- [ ] an L2 replay failure is logged and **cannot** fail the drain
- [ ] a test drives the endpoint and proves both halves ran, in order
- [ ] technique 3: neutralise the chain → the probe goes red
- [ ] the runbook names the window, the drain and the verification query
- [ ] full suite: 0 regressions

## 5. What this step does NOT do

* **It does not choose the window.** 365 is the recommendation; the number is Rohit's.
* **It does not raise it.** That is an operator action against a live tenant, through the endpoint
  that already exists.
* **It does not build held-candidate recovery** — ⛔ **and that is now a known consequence.** Widening
  history improves coverage for facts that were held, and nothing re-examines them. That is Wave 4's
  step, and this step's findings are why it exists.

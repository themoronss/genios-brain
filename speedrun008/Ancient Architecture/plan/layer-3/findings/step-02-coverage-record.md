# L3-02 · The coverage record — findings

**Run:** 2026-09-25 · premise checked before any code · ⛔ **no migration — the plan was wrong**

---

## 1. ⛔ The premise check corrected this step three times

| the plan said | measured |
|---|---|
| *"the absence contract is 3 of 8 ingredients"* | ⛔ **wrong** — `capture/coverage/` is a **7-module subsystem** |
| *"`context/` reads L1's coverage zero times"* | ⛔ **wrong** — five reads of `source_coverage`, 40+ modules use `coverage_ready` |
| *"needs a migration"* | ⛔ **wrong** — migration **0178** added every column already |

**All three corrections shrank the step. What was left is one function.**

### 1.1 · Two different things were being conflated

| | question | state |
|---|---|---|
| **domain readiness** | *can we see this domain for this org at all?* | ✅ computed per sweep · persisted to `source_coverage` · on the QES · read in 40+ modules |
| **quantitative coverage** | *of this window, how much did we land?* | ⚠️ measured · persisted · ⛔ **read by nobody** |

⛔ **`coverage_ready` is the licence to make a negative inference. It is not a measurement of how
much was read.** Conflating them is how *"we can see email"* becomes *"we read the mailbox"* — which
is the exact substitution the benchmark caught in public.

### 1.2 · The real defect: one writer, zero readers

Migration **0178** added `cursor_exhausted`, `page_budget_spent`, `claimed_total` and
`claimed_is_estimate` to `l1_sync_runs`. `api/routes.py:372` writes them on every sync.

**No `select` in the engine reads them back. Anywhere.**

⛔ **That is `not_carried` one seam further along than the class usually appears.** The value does
not stop inside `capture/` — it reaches storage and stops there, **which is harder to see because
the write looks like success.**

### 1.3 · And FX-08's distinction was already available

`l1_sync_runs.error` has existed since the table did. *"A rate limit produces an empty adapter
result instead of an error"* — both land `scanned = 0`, and `error` is what separates them.
**Nothing had ever read it for that purpose.**

---

## 2. What was built — `capture/coverage/window.py`

| | |
|---|---|
| `SyncHealth` | `HEALTHY · SUCCESS_EMPTY · PARTIAL · FAILED · UNKNOWN`, closed, guarded both ways |
| `ABSENCE_CAPABLE` | ⛔ **`{HEALTHY}` only** — `SUCCESS_EMPTY` deliberately excluded |
| `WindowCoverage` | frozen · `completeness_bp → None` not `10000` · `is_estimate` travels with the number |
| `coverage_for_window()` | the read that did not exist, over `[since, until)` |
| `.describe()` | ⛔ *"read 37 of about 465 from gmail"* — the sentence |

### 2.1 · Five rules that are the whole module

1. ⛔ **No denominator → `None`, never 100%.** *"18 of 18"* is what a confident 100% looks like.
2. ⛔ **The denominator is a MAX, not a SUM.** Consecutive sweeps report the provider's total for
   the *same corpus*; summing them multiplies the mailbox by the number of times we looked at it,
   and the ratio then shrinks every sweep while the mailbox stands still.
3. ⛔ **`error` is checked BEFORE `scanned == 0`.** A window with one failure and nine clean runs is
   **not healthy** — the failure is exactly where the missing mail would be.
4. ⛔ **`cursor_exhausted is NULL` counts as NOT finished.** Every row written before 0178 is null,
   and treating silence as completion is the fabricated 100% in a different costume.
5. ⛔ **Health alone is not a licence.** A healthy sweep with no denominator read everything it was
   **offered** — which is not everything that **exists**. Both conditions, or neither.

**And `indexed > claimed_total` clamps rather than raising:** Gmail's estimate runs low routinely,
and a checker that treated the excess as an error would fire on a perfectly correct sweep.

---

## 3. ⛔ A wrong claim I had already published, now corrected

`14-BENCHMARK-WHY.md` §2.2 said *"`context/` reads L1's coverage ZERO times."* **That was false**,
and it had been committed and presented. The grep behind it asked only for the quantitative
symbols; the sentence generalised to all coverage.

**The section's conclusion survives — the benchmark's number cannot be said today — but its
evidence did not, and the file now carries the correction in place rather than quietly.**

---

## 4. Result

```
FULL SUITE   13,164 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-02: 13,143 passed · 14 failed
```

**+21 tests · 0 regressions · ⛔ no migration · no model call.**

**Technique 3 — five mutations, all red:** 100% instead of `None`; the denominator summed;
`SUCCESS_EMPTY` made absence-capable; the health checks reordered; a null cursor read as finished.

## 5. What this step does NOT do

* **It does not put the sentence on a card.** `describe()` exists and nothing calls it yet — that
  is **L3-02b**, deliberately a separate step because the carry crosses three seams.
* **It does not gate any absence claim.** `can_support_absence` is the input; the gate is **L3-03**.
* ⛔ **It does not know a `source` the sweep never named.** A window for a source with no
  `l1_sync_runs` rows is `UNKNOWN`, which is correct and is also the state a mis-typed source name
  produces. **A caller passing the wrong string gets an honest "we did not look" for the wrong
  reason** — recorded because it is the way this read can mislead.

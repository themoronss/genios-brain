# S2 — DONE · the value was withheld for the wrong reason, and the real one is worse

**Unit:** `M14.C2.S2` · **Owner:** me · ✅ **2026-10-02** · **18 tests · 6/6 mutations caught**
**Planned as:** *"a stale `value_state` string — contained, and do NOT invent a value."*
⛔ **It became the sharpest product-level finding in the layer.**

---

## 1 · What the plan said, and what measuring the reason found

`08-PLAN-v2` §3 priced this as a comment fix with one gate: *the fix for a wrong reason is the
reason, not the answer*, so **measure what is actually missing** before writing a new reason.

That measurement went three steps and each one moved the finding:

```
step 1   does anything branch on the literal?          ⛔ NO — the only occurrence was the writer
step 2   does the counterfactual ledger exist?         ⛔ YES — migration 0072, with a receipt
step 3   then what WOULD carry a rupee value?          ⛔⛔ macv_ledger — and nothing writes it
```

## 2 · ⛔ The claim that was wrong, in two ways at once

`api/intelligence_routes.py`, before:

```python
# `0` and "we have no way to know yet" are different claims, and returning 0 for both is how
# an absent measurement becomes a reported result. Value attribution needs the counterfactual
# ledger (L7-12), which does not exist — so this says so rather than inventing a number.
...
"value_state": "unavailable_no_counterfactual_ledger",
```

| | |
|---|---|
| ⛔ **wrong 1** | `counterfactual_ledger` **exists** — `migrations/0072_counterfactual_ledger.sql`, a view joining signal → card → `card_events` → verdict → `delivery_outbox` → `executions` → `execution_outcomes` → `llm_costs`, one row per recommendation, with a production receipt asserting the join reaches end to end. **Atlas gap #7 is CLOSED** |
| ⛔ **wrong 2** | it was never the ledger that would carry money. It answers *"did this recommendation lead to anything"*. It has **no monetary column**, and neither does `execution_outcomes` (a label and durations) or `llm_costs` (tokens only) |

> ⛔ **The first sentence of that comment is one of the best in the repository and the citation
> under it was false.** *The principle was right; the evidence it pointed at was not.*

## 3 · ⛔⛔ THE FINDING · the North Star ledger has never had a writer

`migrations/0012_l6_feedback.sql:35`:

> *"F8 MACV ledger — **the North Star**. caught→acted→resolved; distinct-deal SUM + non-deal COUNT
> (anti-inflation double-count rule). **The number the customer can verify**."*

```sql
create table if not exists macv_ledger (
    id text primary key, org_id text not null,
    period text not null,              -- YYYY-MM (tenant-local, never wall-clocked)
    deal_id text, amount numeric, resolved_signal_id text,
    created_at timestamptz not null default now()
);
```

⛔ **Measured across the whole repository — five occurrences, and not one of them is a read or a
write:**

| Where | What it does |
|---|---|
| `migrations/0012_l6_feedback.sql` | creates it, and calls it the North Star |
| `migrations/0033_org_data_cascade.sql:84` | adds the org cascade FK |
| ⛔ `genios_engine/api/account_routes.py:670` | **the deletion list** — so `/reset` erases it |
| ⛔ `tests/test_reasoning_retention.py:27` | **the retention test's** table list |
| ⛔ `docs/LAYER_MAP.md:15` | claimed `feedback/` **writes** it — it does not |

> ⛔⛔ **Nothing ever inserts a row and nothing ever selects one. The only code that touches the
> product's headline value ledger is the code that deletes it.**

This is *a record nobody reads is presence without effect* turned inside out: **a ledger that exists
only in the delete list.** Both of its two code references say *"remember to wipe this."*

## 4 · Why `None` stays — and why this was a REASON change

The handler's own first sentence settles it: *"`0` and 'we have no way to know yet' are different
claims, and returning 0 for both is how an absent measurement becomes a reported result."*

⛔ **Reading an empty `macv_ledger` to report `0` would be exactly that defect**, committed by the
very code written to prevent it. So `value_recovered_inr` stays `None`; only the reason changed.

## 5 · What changed

| File | Change |
|---|---|
| `genios_engine/api/intelligence_routes.py` | the comment — the false citation replaced with the measurement, quoting the old sentence so the record survives; `value_state` → **`"unavailable_macv_ledger_has_no_writer"`**; ⛔ **the docstring** — it said *"ROI / intervention rate stay null"* and **both halves were stale**: `intervention_rate` is computed from `acted / fired`, and `outcomes_recorded` is a real `count(*)` |
| `docs/LAYER_MAP.md` | the `feedback/` cell said *"Precision windows, nudges, mutes, MACV."* ⛔ **MACV removed**, with the measurement in the cell. The other three are asserted real by test |
| `tests/api/test_the_value_is_withheld_for_the_right_reason.py` | **18 tests** |

### ⛔ The rename, and the risk I took knowingly

`value_state` is user-visible. Before renaming it I measured: **nothing in this repository branches
on the literal** — the only occurrence was the writer — and `value_state` has only ever had **one**
value, so no client can be switching on a set.

⛔ **A client OUTSIDE this checkout cannot be measured from here, and I am saying so rather than
implying I checked.** A client that string-matches falls through to its default, which is strictly
better than displaying a false cause to a founder. Both the reasoning and the limit are recorded in
a comment beside the field.

## 6 · ⛔ The guard has teeth, and they are pointed at the reason

The string states a fact **about the repository**. So the test binds it to that fact:

| | Check |
|---|---|
| ⛔ **`test_the_north_star_ledger_still_has_no_writer`** | **add an `insert into macv_ledger` anywhere in `genios_engine/` or `scripts/` and this fails**, naming the endpoint, its comment and `LAYER_MAP.md` as the three things to update together |
| `test_the_north_star_ledger_still_has_no_reader_either` | both directions — a reader appearing would mean the endpoint is the reader it is waiting for |
| `test_the_north_star_ledger_exists_in_the_schema` | ⛔ it is **unwritten, not missing** — *a table nobody writes is not a table nobody built* |
| `test_no_monetary_column_in_the_tables_the_endpoint_already_reads` | why `None` is right and not a missing join — parametrised over `0072`, `0041`, `0004` |
| `test_the_layer_maps_three_remaining_claims_are_real` | ⛔ **correcting one cell is where a second false claim slips in**, so each survivor is measured |

```
✅ baseline: 18 passed

  M1 · the FALSE ledger name back in value_state      ✅ CAUGHT (2 failed)
  M2 · value_recovered_inr becomes 0                  ✅ CAUGHT
  M3 · a WRITER appears for macv_ledger               ✅ CAUGHT
  M4 · a READER appears for macv_ledger               ✅ CAUGHT
  M5 · the false claim ASSERTED again, unattributed   ✅ CAUGHT
  M6 · LAYER_MAP claims MACV again                    ✅ CAUGHT

✅ baseline again: 18 passed        6 caught · 0 survived
```

## 7 · ⛔⛔ My own fault, and the rule was in the docstring of the test that broke on it

My first version asserted the false sentence was **absent**:

```python
assert "ledger (L7-12), which does not exist" not in src
```

⛔ **It failed on the correct fix** — because the corrected comment **quotes** the old sentence in
order to say it is false. And the docstring I had written directly above that line reads: *"a grep
for a known-false phrase matches the record of its own correction."*

> ⛔ **Eighteenth instance of this pattern in the programme, and the first in which I wrote the rule
> into the docstring of the test that then violated it.**

The repair is the general one: ⛔ **a guard must check ATTRIBUTION, not PRESENCE.** The phrase may
appear; every occurrence must sit within four lines of a marker that identifies it as the old
wording (`used to read`, `CITATION WAS WRONG`, `CORRECTED`). A relapse adds an **unmarked**
occurrence and fails — which `M5` proves. *A log is append-only and corrections are new lines, so a
guard that forbids the words cannot tell a correction from a relapse.*

## 8 · Verify

```bash
.venv/bin/pytest tests/api/test_the_value_is_withheld_for_the_right_reason.py -q   # 18 passed
.venv/bin/pytest tests/api tests/feedback \
    tests/platform/test_every_package_says_what_it_does_not_call.py -q             # 175 passed
.venv/bin/pytest -q                                                               # the FULL suite
```

## 9 · ⛔ What this hands to Rohit

**The product's headline number has no producer.** `macv_ledger` was designed as `feedback/`'s job —
it lives in `0012_l6_feedback.sql` and `LAYER_MAP` listed it under `feedback/` — and the writer was
never built. ⛔ **That is not a bug to fix quietly:** what counts as recovered value, which deals
attribute, and the *"anti-inflation double-count rule"* the migration names are product decisions,
and the migration's own `distinct-deal SUM + non-deal COUNT` is a specification nobody implemented.

⛔ Until it is written, `/v1/insights/stats` is **correct** to say so — and now it says so truthfully.

## 10 · Doctrine

| Rule |
|---|
| ⛔ **a guard must check attribution, not presence** — a correction quotes what it corrects |
| ⛔ **the fix for a wrong reason is the reason, not the answer** — and measuring the reason moved this from a comment fix to a product finding |
| ⛔ **a table nobody writes is not a table nobody built** |
| ⛔ **a ledger that appears only in the delete list is presence without effect, inside out** |
| ⛔ **correcting one cell is where a second false claim slips in** — assert the survivors |
| **a string that states a fact about the repository must be checked against the repository** |
| **a docstring describing two fields that have since been implemented reads as a measurement of today** |
| **say what you could not measure** — an external client is invisible from this checkout |

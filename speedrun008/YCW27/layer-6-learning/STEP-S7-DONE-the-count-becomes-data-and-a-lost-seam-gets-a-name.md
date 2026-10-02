# S7 — DONE · the count becomes data, and a lost seam gets a name

**Unit:** `M14.C2.S7` · **Owner:** me · ✅ **2026-10-02**
**Two halves, both planned as `S7`:** (b) the unread ledgers' last question · (a) guards per package
**(b)** 20 tests · **9/9** mutations · **(a)** 55 tests · **8/8** mutations
**Atlas:** `L7-29` · the no-silent-drop contract

---

## PART b · ⛔⛔ a seam we threw away was reported as a seam that had nothing

### 1 · What the gate found

`08-PLAN-v2` planned a refusal-rate receipt over `learning_input_rejections` *"once a denominator
exists."* ⛔ **It already does, and not there.** `org_rule_discovery_runs.counters` holds
`candidates`, `admitted`, `human_review`, `refused` and `refused_<reason>` per run — in a table that
**is** read, by `already_discovered` and by the sweep's `LEFT JOIN`. **The discovery route's
accounting is complete.**

⛔ So the gap was in the ledger's **other** writer. `feedback/store._read_optional_seam` catches a
read that raises, records it, and returns `()`. Its own comment states the defect it half-fixed:

> *"`learning_input_rejections` exists (migration 0046) and its own comment calls it 'sanitized
> isolation of a malformed/lineage-less input' — and **nothing in the codebase ever wrote to it**.
> So the layer's isolation ledger recorded nothing, and an input the system deliberately
> quarantined was indistinguishable from one that never arrived. **That is the no-silent-drop
> contract failing in the one place built to uphold it.**"*

⛔ **The WRITE was built and the READ never was** — and the return value stayed `()`, so the seam
arrived at `run_learning` identical to an empty one. *"No human has judged a card yet"* and *"the
verdict table read raised and we threw it away"* were one line in `degraded_seams`.

The Atlas names it — **`L7-29`**: *"Sweep completes with every required input seam empty →
'Learning healthy' is reported for no-op execution → Mark degraded/insufficient-input → **Expose
per-seam freshness, coverage, and empty REASON** → **Empty canonical verdict seam breaches a
declared health SLO**."* And L5 learned the same shape: *a dead row cannot tell "we chose not to
send" from "we lost it".*

### 2 · ⛔⛔ And the delivery seam was reported degraded on EVERY run, forever

```python
degraded_seams = {name for name, rows in (
    ("outcomes",   getattr(batch, "outcomes", ())),
    ("feedback",   getattr(batch, "feedback", ())),
    ("deliveries", getattr(batch, "deliveries", ())),   # ⛔ the field is `delivery`
) if not rows}
```

The default fired **every time**, so the delivery seam was always listed and ⛔ **`degraded` was
always True.**

> ⛔ **A flag that is always set is a flag nobody reads** — the same shape as `receipts.py`'s own
> *a gate that is always red is a gate nobody reads.*

⛔ **A `getattr` with a default converts a wrong attribute name into a plausible value.** On a
dataclass, `batch.delivery` would have raised `AttributeError` the first time it ran. And the
comment directly above that block says *"A run that proposed nothing because its inputs were empty
is NOT a healthy run that found nothing to learn, and the two were indistinguishable from the
counts"* — **the fix was built and one of its three seams was wrong.**

### 3 · What changed

| File | Change |
|---|---|
| `feedback/store.py` | `LearningBatch.quarantined` · `HEALTH_SEAMS` and `QUARANTINABLE_SEAMS` as shared tuples · the quarantine threaded through both optional seams |
| `feedback/orchestrator.py` | ⛔ `degraded_seams` derived from `HEALTH_SEAMS` (the typo gone) · `quarantined_seams` in `counts` |
| `platform/receipts.py` | ⛔ **two** correctness receipts; the seam list **derived** from `store.QUARANTINABLE_SEAMS` |

⛔ **A missing table is NOT a quarantine.** `card_feedback_verdicts` legitimately predates some
deployments, and conflating *absent* with *lost* would make the receipt red on a tenant whose schema
is simply older.

⛔ **Routine discovery refusals are excluded from the receipt.** `record_refusal` writes to the same
table under `seam = "brains.org_discovery"` for every candidate the gate turns down — healthy, and
already counted per run. Counting those would make the receipt red on working tenants.

### 4 · ⛔ A test double that was kinder than the database

`M4` — *"a missing table counts as a quarantine"* — **SURVIVED** on the first run. My fake
connection answered *"this table does not exist"* and then returned an empty result for a read of
it. PostgreSQL raises. So the test passed for the wrong reason and deleting the `_table_exists`
guard changed nothing it could see.

> ⛔ **A test double that cannot fail the way production fails is a test that proves nothing.**

---

## PART a · ⛔⛔ guards per package becomes DATA — and `STEP-10` was aimed at the wrong package

### 5 · The number, and why it was prose

`STEP-10` claimed *"L5 is 9,431 lines and carried 2 of the programme's 33 receipts — 4,715 lines per
guard against L4's 881"*. `deliver/` carried **5**, the figure was **1,886**, and **four** of the
five worked. The count was derived once, by hand, by filtering `Receipt.layer` — the digit
`LAYERS.py` forbids reading alone — and then repeated in **eleven documents**, where **no assertion
depended on it.**

### 6 · ⛔⛔ Derived, it points somewhere else entirely

```
package     receipts  correctness    lines  lines/guard
feedback           9            5    4,040          448     ← best
reason             8            5   41,363        5,170
deliver            7            5   10,020        1,431
capture            5            5   47,184        9,436
readiness          5            0        —            —
context            2            2   50,877       25,438     ⛔⛔ WORST
executive          2            1    6,230        3,115
platform           1            1   11,950       11,950
packs              1            0    8,188        8,188
```

> ⛔⛔ **`context/` is 50,877 lines with TWO guards.** `STEP-10` spent a whole step on `deliver/`
> because a hand-derived number said 4,715 — **`context/` is 5.4× worse than that**, 13× worse than
> `deliver/`'s real figure at the time, and `deliver/` is now the **third-best covered package in
> the product.**

⛔ **`packs/` is 8,188 lines with one PRESENCE receipt and zero correctness** — the state `feedback/`
was in before `S5`. Named rather than fixed here.

### 7 · The mapping is DECLARED, and that was measured first

⛔ An outer-`from` resolver fails on **4 of 40** receipts, each reading `select … from ( <subquery>
)` — a derived table whose real source is inside the parentheses. Two earlier parsing attempts
produced confident wrong answers: `[a-z_]+` stops at the digit in `l2_convergence` and reports table
`l`, and `jsonb_each` is a function. *A resolver that is merely stricter is not more correct.*

⛔ **A third category exists, and forcing it into a package would be a lie.** Some claims go red for
reasons no package can fix — a tenant with no seats, no manager, no pack binding, no channel. Those
are declared `READINESS` and counted separately, because calling them `deliver/`'s guards would
inflate a package's coverage with work it cannot do.

⛔ **`Receipt.layer` is not touched.** `receipts(layer)` filters on it, the labels carry two
vocabularies (`944b4f76` *"all seven layers"* vs `22d598b1` *"all six product layers"*), and sorting
that out changes operator behaviour. `test_the_package_is_never_derived_from_the_layer_label`
asserts this module never reads it.

### 8 · ⛔ The second direction caught me twice, on its first run

I built the declaration from a dump that **truncated each claim at 62 characters**, so two keys were
cut short. Direction one reported them undeclared and direction two reported them stale — **naming
both halves of one mistake.**

> ⛔ *A totality guard that runs one way is half a guard* — and the half that is easy to skip is the
> half that found this.

---

## 9 · ⛔⛔ A harness defect that could have falsified every mutation run in this session

`S7(a)`'s final *"baseline again"* assertion **failed**: `receipts()` reported a layer `L8` that
appears **nowhere** in the source.

⛔ **A stale `__pycache__`.** The harness mutates a file, runs pytest in a subprocess (which
compiles and caches the MUTANT), then restores the source — and when the restore lands in the same
mtime-second with the same size, Python reuses the mutant's `.pyc`. **A restored file was read as
the mutant.**

⛔ **Which direction does that bias?** Toward **false kills**: a later run importing an earlier
mutant fails for the wrong reason and is scored CAUGHT.

⛔ **So every harness in this session was re-run** with `PYTHONDONTWRITEBYTECODE=1` and a
`__pycache__` clear before each invocation:

```
s2  6 caught · 0 survived      s5  8 · 0      s7b  9 · 0
s3  8 · 0                      s6  9 · 0      s7a  8 · 0
s4  8 · 0
```

⛔ **Every count identical to the original.** Nothing was mis-scored — but *it had to be checked,
and the check existed only because the harness asserts its baseline AFTER the run as well as
before.* `STEP-14`'s lesson, paying for itself a second time.

## 10 · ⛔ And one guard forced its own update

`S6`'s `test_the_remaining_unread_ledgers_are_still_unread` was parametrised over
`["learning_input_rejections", "learning_metrics"]` with the docstring *"when one gets a reader this
fails and the `F11` tally is updated deliberately."* ⛔ `S7` gave the first one a reader and **the
test failed**, exactly as promised — so the tally moved from *four unread* to *one* as a deliberate
edit rather than a discovery weeks later.

> ⛔ **A declared silence that fails the build when it stops being true is the only kind worth
> writing.**

```
unread of F11's four ledgers:   4 → 2 (S6) → ⛔ 1 (S7)   — only `learning_metrics` remains
receipts                        38 → 40
feedback/ CORRECTNESS            3 → 5                    (0 before S5)
```

## 11 · Verify

```bash
.venv/bin/pytest tests/feedback/test_a_quarantined_seam_is_not_an_empty_one.py -q        # 20
.venv/bin/pytest tests/platform/test_a_receipt_names_the_package_it_guards.py -q         # 55
.venv/bin/pytest tests/platform tests/feedback -q
.venv/bin/pytest -q                                                                # FULL suite
```

## 12 · ⛔ What this hands to Rohit

⛔⛔ **`context/` is the next layer to re-measure, not a choice I should make quietly.** 50,877
lines, two guards. The programme spent `STEP-10` on `deliver/` because a hand-derived number pointed
there; the derived number points at `context/`, and `packs/` has one presence receipt and no
correctness question at all.

## 13 · Doctrine

| Rule |
|---|
| ⛔ **a flag that is always set is a flag nobody reads** — the delivery seam was degraded on every run |
| ⛔ **a `getattr` with a default converts a wrong attribute name into a plausible value** |
| ⛔ **a test double that cannot fail the way production fails is a test that proves nothing** |
| ⛔ **a stale `__pycache__` makes a restored file read as the mutant** — bias is toward FALSE KILLS |
| ⛔ **a declared silence that fails the build when it stops being true is the only kind worth writing** |
| ⛔ **a totality guard that runs one way is half a guard** — it caught two truncated keys |
| ⛔ **an absent seam is not a lost seam** — and neither is a routine refusal |
| **derive the list from the source of truth: health seams from the dataclass, quarantinable seams from the reader, legal pairs from the contract** |

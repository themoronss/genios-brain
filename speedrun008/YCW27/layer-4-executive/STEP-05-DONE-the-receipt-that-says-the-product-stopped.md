# Step 5 — ✅ DONE · the receipt that says the product stopped

> **Unit** U1 · **16 tests · 5 mutations, one of which found a half-guard I had shipped**
> **The success condition was that it goes RED.** It does: 3,582 across all orgs.

---

## 1 · What was actually true

The product had produced **no card for six days**. `L1`, `L2` and `L3` wrote rows on 2026-09-30;
`L4` and `L5` stopped on 2026-09-25.

⛔ **And all thirty receipts were green on the thing that stopped.** Four of them for reasons worth
stating:

| | Receipt | Value | Why it was green |
|---|---|---|---|
| #19 | more than one candidate is ever considered | 11 | candidates **are** produced — 8,044 of them |
| #21 | the system has abstained at least once | 1,772 | ⛔ **green BECAUSE of the defect.** Abstention is healthy and this measures that it *happens* — so abstaining **100% of the time** satisfies it perfectly |
| #22 | decisions become tracked commitments | 75 | green on append-only history, forever |
| #14 | the live pass has actually run | 2,376 | the pass runs. It emits nothing |

**The one receipt that was red for the right reason was #13** *"at least one seat has a manager"* =
0 — which is **block 2** (the ladder). **Block 1** (the input) had no receipt at all. That is what
this step built.

## 2 · What was built

| Artifact | What |
|---|---|
| `reason/unit_health.ReasoningEra` + `REASONING_ERAS` + `current_reasoning_era()` | the era boundary, **declared with the measurement that establishes it** |
| `platform/receipts._ERA_SELECTS_NOTHING_SQL` | the query, and the reasoning for every line of it |
| receipt **#31**, L2 | *"the current reasoning era selects, not only defers"* |
| `tests/platform/test_a_reasoning_era_that_selects_nothing.py` | 16 tests |

### The three answers, and why there are three

    -1   the era produced no runs with candidates    -> FAIL, and it is a DIFFERENT sentence
     N   N runs had candidates and selected NONE      -> FAIL, and N says how many
     0   at least one selection happened              -> PASS

⛔ **The `-1` is the whole design.** The natural shape —
`having count(*) > 0 and count(selected) = 0` — returns **no rows** for an era that produced
nothing, every caller reads that as "no violation", and the receipt goes **green on a completely
dead pipeline**. That is the exact state it exists to detect.

### ⛔ A conjunction, not a count

A high defer rate is **healthy**: the previous era deferred **8,208** times and still produced
**1,157** decisions. A receipt that counted defers would have been red through the product's best
month. The defect is a selection rate of **exactly zero** over runs that had something to select
from — which is audit D's rule one layer up: *a count without its dimension is not a measurement.*

### ⛔ And it only asks about runs that had candidates

A run with no candidates cannot select one. Counting it would make the receipt red for every
abstention the layer is **designed** to make.

## 3 · Scenario → result

| Scenario | Result |
|---|---|
| the era ran and selected nothing | ⛔ **FAIL**, with the count — `org_66bca…` 480 · `org_2f1bc0…` 849 · `org_e97e86…` 2,253 · **all orgs 3,582** |
| the era produced no runs at all | ⛔ **FAIL** at `-1`, not a vacuous pass |
| one selection happened | PASS |
| a run abstained with no candidates | not counted — correct |
| the boundary is not an ISO date | `ValueError` before it touches SQL |

## 4 · ⛔ The era bound is not a weakening — it is the entire thing that makes it work

Measured, with the bound removed:

    with the era bound      3,582   ⛔ correctly RED
    without it (both eras)      0   ✅ GREEN

The previous era's **1,157 selections hide the current era's zero.** Without the bound this
receipt averages a live implementation with a retired one and reports neither.

> **A receipt over append-only history needs a lower bound, or it is not a gate but a monument.**
> — audit D, and this is its second application.

## 5 · ⛔ What the mutations found — including a half-guard I had shipped

| | Mutation | Caught? |
|---|---|---|
| M1 | the `-1` arm → `0` (vacuous pass restored) | ✅ |
| M2 | **the whole era bound → `where 1=1`** | ⛔ **SURVIVED all 15 tests** |
| M3 | count defers instead of selections | ✅ |
| M4 | drop the `exists (candidates)` restriction | ✅ |
| M5 | strip the measurement out of the era declaration | ✅ |

⛔ **M2 is the most dangerous mutation of the five**, because on production it turns 3,582 (red)
into 0 (green) — the receipt becomes a liar while every test passes. It survived because
`test_the_builder_imports_the_era_rather_than_restating_the_date` proves the boundary is
**imported**, and nothing proved it was **used**.

> ⛔ **Declared and written are two directions, and one alone is half a guard.** The import is the
> declaration; the boundary appearing in the predicate is the writing.

`test_the_boundary_actually_REACHES_the_sql` closes it, and now catches M2.

## 6 · And one of my own tests failed on its own prose

`test_the_builder_imports_the_era_rather_than_restating_the_date` walks the AST for inlined dates
and excluded the docstring by **value**. ⛔ `ast.get_docstring()` returns the **cleaned** text while
the node holds the **raw** one, so the comparison never matched and the assertion failed on the
builder's own docstring. Excluding the node **by identity** — it is the function's first statement
— is exact. The eleventh instance of a check that read prose as code.

## 7 · What this receipt does *not* claim

Not the cause. The cause was `GENIOS_L4_LLM_DECISION_MAKER = true` with the Anthropic spend limit
refusing every call since 2026-09-25 11:09 UTC and `reason/llm_decision_maker.py:20`'s declared
*"Failure is DEFER, never the formula"* — **a deliberate design, not a bug.**

A receipt reports a state. The reason is in
[`05-RECROSSCHECK-why-the-queue-is-empty.md`](05-RECROSSCHECK-why-the-queue-is-empty.md); the
choice is **DECISION #5**.

⛔ **This receipt will stay red until decision #5 is answered — and that is correct.**

# ⛔ STEP 3.1b · THE FOURTH RESOLVER HOP — loops over constant collections

**Written 2026-10-04, after measuring and before any build.** `3.1` declared four sites
`resolvable-deferred` and said why: *"a fourth resolver hop with a 102-table blast radius is its own
unit with its own baseline, not a silent addition to this one."* This is that unit.

---

# ⛔⛔ PART 0 · THE DOCTRINE CHECKLIST — written FIRST, because reading the table was not enough

`2.2`'s plan-vs-actual recorded: *"the next step's plan should carry a written check of its own
guards against the previous step's doctrine, because reading the table was demonstrably not
enough."* ⛔ **`3.1`'s plan did not carry one, and the same class of defect appeared twice.** Here it
is, and every guard this step writes is checked against it before the step closes.

| # | the rule | ⛔ how it will be broken here if I am not careful |
|---|---|---|
| 1 | **length is not content** (`len(x) > N`) | a declaration entry check that counts characters instead of requiring evidence. ⛔ Appeared in `2.1`, `2.2` and `3.1` |
| 2 | **an OR over a hand-listed token set is not a check** | the same, in disjunction form. ⛔ Four occurrences so far |
| 3 | **a threshold a test reads from the thing it guards is a variable** | the new ceiling must be asserted near the actual, not just `actual <= CEILING` |
| 4 | **a declaration that cites its source satisfies the test that the source exists** | any guard asserting "X is still in the file" must exclude the block quoting X |
| 5 | **a quoted example is counted as a real one** | ⛔ this step's declarations will quote loop code; count distinctly |
| 6 | **the test must read what the measurement reads** | source, not runtime values |
| 7 | **state an expectation only after measuring it** | no `== N` that was not measured first |
| 8 | **a declaration can falsify its own measurement** | any "appears in 0 files" claim must exclude its own declaration |
| 9 | **a grade needs its converse guarded** | if entries are categorised, assert each category's membership both ways |
| 10 | **establish the baseline before AND after** | ⛔ already bitten once in this step's own research — see Part 1 |
| 11 | **a test cannot catch a weakening of itself** | mutate the source, never the test file |
| 12 | **the observer counts its own instrument** | this step adds loop detection; its own declarations contain loops |

---

# PART 1 · THE MEASUREMENT, AND THE TWO THINGS IT CHANGED

## ⛔⛔ 1 · THE NAIVE DESIGN IS WRONG, and it would have broken a number other things read

The obvious implementation expands each loop statement into one statement per table. Measured:

| | before | ⛔ naive after |
|---|---|---|
| `statements` | 2,885 | **3,036** (+151) |
| `unresolved` | 621 | **631** — ⛔ **it goes UP** |
| `unresolved_table` | 16 | 7 |

⛔ `statements` stops meaning *"SQL statements in the source"* and becomes *"statement × table
instantiations"* — and it is the **denominator of the share assertion** and a number
`scripts/context_coverage_report.py` prints. ⛔ And `unresolved` **rises**, because expanding one
statement into five leaves five statements each still carrying the *other* holes (`{column}`,
`{key_column}`), so a genuine improvement would read as a regression.

✅ **The correct design: attribution expands, the statement count does not.** The loop map feeds
`_table_usage` only; `resolution()` keeps counting source statements and simply stops counting a
table hole the loop map can close. Measured:

```
statements                       2,885    ✅ unchanged
statements whose table hole closes    9
unresolved_table                16 → 7
new (table, verb, file) facts       278    over 106 tables
```

## ⛔⛔ 2 · `3.1`'s `not-a-table` DECLARATION IS WRONG

`3.1` declared `scripts/rebuild_graph.py` as `not-a-table`:

> *"`create table if not exists {tbl}_bak_{ts} as …` — the hole is part of a name being MINTED, not
> an engine table being read."*

⛔ **It describes a statement that was never counted.** `_SQL_SHAPE` matches only
`select|insert|update|delete|with`, so the `create table` line carries no counted hole at all. The
**one** statement in that file that does is:

```sql
delete from {tbl} where org_id=:o
```

— an unambiguous **delete of eight real graph tables**. ⛔ So the entry is wrong in both halves: the
category and the construct. **I declared the wrong statement**, and a declaration that cites the
wrong line is worse than none because it reads as a measurement somebody took.

⛔ **And the category then has no members**, which makes every assertion over it vacuous — rule 9 of
the checklist, and `1.4`'s surviving mutation.

## ⛔ 3 · The research itself hit rule 10 before the plan was written

The first delta measurement reported *"no change: 621 → 621, 16 → 16."* ⛔ **`resolution()` is
`lru_cache`d and the probe cleared `_table_usage` and `_exported_table_constants` but not
`resolution`.** A stale cache made the measurement say the opposite of the truth. *Establish the
baseline or the harness is theatre* — and clearing two of three caches is theatre with a prop.

## ✅ 4 · And the hop closes a site that is already declared, which is the guard working

`context/merge.py` is in `NAME_CONSTANT_TABLE_SITES` (`_NODE_REFERENCES`, verb `update`). The loop
hop closes its three holes — ⛔ and one of them is a **`select`**:

```sql
select {id_column} from {table} where org_id=:o and {owner_column}=:n
```

So the existing declaration attributes **only `update`** and the hop adds the missing **read**. ✅
`3.1`'s guard asserts every declared site still has a hole, so closing it will **fail that test** —
exactly as designed. The declaration has to be retired or narrowed in the same change.

---

# PART 2 · THE UNITS

```
U01  ⛔ correct 3.1's wrong `not-a-table` entry, and drop the empty category
U02  the loop hop, ATTRIBUTION-ONLY — statements must stay 2,885
U03  retire/narrow the declarations the hop closes, including merge.py's missing read verb
U04  re-ratchet 16 → 7, with the baseline compared before and after
```

## U02's bounds, declared before writing it

| allowed | ⛔ refused |
|---|---|
| `for X in (…literal strings…)` where **every** element is a known table | a **mixed** collection — one unknown element and the loop answers for nothing |
| `for X in CONSTANT` where CONSTANT resolves through the three existing hops | a constant built by a call, a comprehension or a slice |
| `for X, _ in PAIRS` — first element of a tuple target | any other position; `for _, X in …` is not guessed |
| a `for` statement and a comprehension | `while`, `enumerate`, `zip`, `dict.items()` |

⛔ **One hop, as before.** The loop's iterable resolves through the existing constant machinery and
nothing further. A resolver that chases arbitrarily far is one nobody can predict.

---

# PART 3 · WHAT THIS WILL NOT DO

| ⛔ not doing | why |
|---|---|
| changing `statements` | ⛔ measured: the naive design inflates it by 151 and `unresolved` rises. A number other things read does not change meaning for this |
| resolving `{column}` / `{key_column}` / `{id_column}` | they are not table names. `3.1` established that 92% of the old headline was this, and it is still not a gap |
| `scripts/wipe_org_data.py` | ⛔ reads `information_schema` at run time **on purpose** — *"a positive selection cannot be out of date."* Resolving it would replace a correct design with a stale list |
| `api/home_routes.py` | the table is a **function parameter**; closing it needs the call graph |
| `capture/connectors/database.py` | **tenant configuration**, unknowable from source, and already guarded by an identifier validator |

⛔ **Done** means: the full suite green with no new skips, every mutation caught or reported invalid
with its reason, **the before/after baseline of every dependent finding printed and explained**,
**every guard checked against Part 0 line by line**, and the audit written.


---
---

# ⛔ CLOSED 2026-10-04 · PLAN vs ACTUAL

| | planned | ⛔ actual |
|---|---|---|
| **units** | 4 | **4**, plus a verb fix the plan did not contain |
| `unresolved_table` | 16 → 7 | **16 → 7** ✅ the measurement was right |
| **declarations** | retire what closes | 6 retired · 1 retracted · 1 **added** · ⛔ **2 categories retired** |
| **tests** | — | **56** (28 + 28) |
| **mutations** | — | **17 caught · ⛔ 1 real hole · 1 dead clause removed** |

## ✅ The plan's three best decisions

* ⛔⛔ **Part 0, the doctrine checklist.** `2.2` asked for it and `3.1` did not carry one, and the
  same defect class appeared twice. This plan carried it — and **rule 6 had already been broken
  when it was written**: the guard's helper re-derived the metric's logic and had drifted. ⛔ The
  checklist did not prevent that; **it is what found it.** That is the argument for keeping it.
* ✅ **Measuring the naive design before writing it.** `statements` 2,885 → 3,036 and `unresolved`
  **rising** is not something a code review would have caught; it needed the numbers. The built
  design is different *because* of the measurement.
* ✅ **Committing in writing to the before/after comparison.** ⛔ It is the only reason the
  delete-as-read bug was found instead of four correct declarations being retired. **The commitment
  was worth more than the hop.**

## ⛔ Where the plan was wrong, or incomplete

**1 · It had no verb fix in it.** The plan's Part 1 described a `102-table blast radius` as a reason
for caution and did **not** predict that the radius would land on a pre-existing bug. ⛔ The hop
alone is three lines; the step is the bug.

**2 · It said `3.1`'s `not-a-table` entry was wrong and understated it.** The plan said the entry
*"describes a statement that was never counted."* True — ⛔ and it also had the **wrong category**,
and the correction emptied a second category (`resolvable-deferred`), and emptying a category means
**deleting the test that guarded it**. Three consequences from one misfiled entry, and the plan
foresaw one.

**3 · It did not foresee that the hop would make a declaration redundant without closing its
hole.** `context/merge.py`'s `NAME_CONSTANT_TABLE_SITES` entry now provides **zero** unique facts —
measured — and it is **kept**, because its prose states something a generic resolver does not. ⛔ A
test now asserts the redundancy, so a future reader meets it as a measured fact rather than
discovering it as dead code.

## ⛔⛔ And the one thing to carry forward

The real hole this step's mutations found was **a test whose own NAME promised something its body
did not contain** — `test_the_FIRST_element_of_a_tuple_target…` tested `zip` and a plain name and
**never a tuple target**. ⛔ That is a thirteenth rule for the next checklist:

> **assert the thing the name claims** — and when one test carries several cases, splitting it is
> what stops one case hiding the absence of another.

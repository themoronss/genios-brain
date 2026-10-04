# ⛔⛔ STEP 3.1 · THE "639 UNRESOLVED SQL STATEMENTS" — and why that number was the wrong one

**Written 2026-10-04, after measuring and before any build.**

The plan describes this step as *"the **639 unresolved SQL statements** (22%) — a table name passed
through a **function argument** needs dataflow, not constant substitution. Today the two known
cases are declared; the share is asserted so it cannot grow silently."*

⛔⛔ **Three of those four clauses are wrong, and measuring them is the step.**

---

# PART 1 · THE MEASUREMENT

```
"unresolved SQL statements"                        645     ⛔ the plan says 639
⛔ with a hole in a TABLE POSITION                  49     7%
   with holes ELSEWHERE ONLY                       596    92%
```

## ⛔ 1 · It is not 639. It is 645, and it grew while nobody was looking

The plan's own sentence says *"the share is asserted so it cannot grow silently."*

⛔⛔ **CORRECTED IN PLACE 2026-10-04 — this paragraph was wrong when written.** It said *"there is
no such assertion."* **There is one**, in
`tests/platform/test_a_table_nothing_reads_is_declared.py`::

    assert r["unresolved"] / r["statements"] <= 0.30

⛔ The defect is its **threshold**, not its absence: 30% against an actual **22.4%** is about **220
statements of headroom**, so it cannot notice anything. The number grew by **six** during Phases 1
and 2 — some of it from the receipts those phases added — and the guard stayed green throughout. ⛔
And its docstring still read *"639 of 2,867"*.

**So the clause describing the safeguard is still the evidence**, just not of what this paragraph
first claimed: *a ceiling with slack is not a ratchet*. ⛔ The correction is kept here rather than
only in the audit, because a plan read later is read as written.

## ⛔⛔ 2 · 92% of the number is not about tables at all

A statement is counted "unresolved" when it carries any `{placeholder}`. Splitting by whether a
hole sits in a **table position** (`from`/`join`/`into`/`update` immediately before it):

| | count | what the holes are |
|---|---|---|
| ⛔ hole in a **table position** | **49** | a table name the resolver could not see |
| holes **elsewhere only** | **596** | predicates, column lists, joins, order-by fragments, bind parameters |

The dominant hole names are **shared SQL fragment constants**, not tables:
`{AUTHORITATIVE_SIGNAL_JOINS}` ×133 · `{AUTHORITATIVE_SCORE_SQL}` ×116 ·
`{AUTHORITATIVE_REASON_CODE_SQL}` ×81 · `{AUTHORITATIVE_SIGNAL_PREDICATE}` ×62 ·
`{_COLUMNS}` ×27 · `{VISIBLE_FACT_SQL}` ×14 …

⛔ **And 17 of them are my own.** `{o}` in `platform/receipts.py` is `_org_filter`'s output — the
string `" and org_id = :org"`. The metric counts a correctly-parameterised org filter as an
unresolved SQL statement, **seventeen times, in the module that sits next to the one defining the
metric.**

So *"639 unresolved SQL statements"* conflates **"a table we cannot see"** with **"a predicate
assembled from a constant"**, and reports the second as though it weakened table coverage. The
number that matters for table coverage is **49**.

## ⛔ 3 · Of those 49, more than half are resolvable today

| of the 49 | count | why the resolver misses it |
|---|---|---|
| ⛔ **an IMPORTED table constant** | **27** | `_module_table_constants` only looks at constants declared **in the same module**. `HISTORY_TABLE = "metric_history"` lives in `context/analytic/history.py` and the 15 statements using it are in `anomaly.py`, which **imports it on line 68** |
| ⛔ **genuinely dynamic** | **~21** | a table from a function argument, a loop variable or an attribute — the dataflow case the plan names |
| `{?}` in a table position | 3 | `{self._table}` in `capture/connectors/database.py`. ⛔ Not a false positive — `_template` renders `{NAME}` for a bare name and `{?}` for anything else, so these are real dynamic sites |

The five imported constants are all ordinary: `HISTORY_TABLE` (15), `COHORT_MEMBERSHIP_TABLE` (6),
`_TABLE` (3), `COHORT_DEFINITION_TABLE`, `L1_SEMANTIC_TABLE`, `BUNDLE_TABLE`. Each is defined with a
**known table name** as its value, in a module the using module imports.

## ⛔ 4 · "The two known cases are declared" is true about the declaration and false about the count

`NAME_CONSTANT_TABLE_SITES` holds **2** entries (`context/merge.py`, `feedback/store.py`). The
dynamic table holes are spread over **14 modules**:

```
4  platform/l3_activation.py        3  capture/connectors/database.py   3  context/merge.py ✅
2  platform/l2_activation.py        2  platform/l4_activation.py        2  scripts/wipe_org_data.py
1  api/account_routes.py            1  api/home_routes.py               1  capture/journey.py
1  context/backfill.py              1  feedback/store.py ✅             1  scripts/e2e_verify.py
1  scripts/equivalence_check.py     1  scripts/rebuild_graph.py
```

⛔ **Twelve of the fourteen are declared nowhere.** The declaration is not wrong; the sentence
describing the situation is.

---

# PART 2 · THE UNITS

## ⛔⛔ U01 · split the metric — `unresolved_table` and `unresolved_fragment`

One number answering two questions is why this step was mis-scoped in the plan. `resolution()`
gains both counts, the old key stays so nothing that reads it breaks, and the **table** count is
the one the coverage guard asserts.

⛔ **Blast radius, stated before touching anything.** `resolution()` is read by
`scripts/context_coverage_report.py` and by `tests/platform/test_a_table_nothing_reads_is_declared.py`.
Changing the resolver changes `table_usage`, `writers_of`, `readers_of`, `written_and_unread`,
`undeclared_unread_writes` and the deletion list — ⛔ which is **exactly the "observer alters what
it measures" risk**, so the baseline for all of them is captured **before** and compared **after**,
and any change in a finding is reported rather than absorbed.

## U02 · resolve imported table constants

27 of the 49. A constant imported from another module, whose value is a known table, is **as much a
read as a literal** — the module's own docstring says *"a name-constant is a read — third time this
programme has paid for that."* ⛔ It pays for it a fourth time here, one import away.

⛔ Bounded deliberately: **one hop, direct `from X import NAME` only.** No transitive resolution, no
re-exports, no `import X; X.NAME`. A resolver that chases arbitrarily far is one nobody can predict,
and *a re-export is not a definition*.

## U03 · declare the dynamic sites

The 12 undeclared modules, each with what its table comes from. ⛔ `database.py`'s is the
interesting one: `self._table` is **trusted tenant config** with an identifier validator beside it
(*"unsafe {what} identifier"*), which is a different risk class from `wipe_org_data.py` looping over
a list this repo owns. The declaration says which.

## ⛔ U04 · the ratchet the plan already asked for

Both counts asserted against a declared ceiling, so neither can grow silently. ⛔ The number grew
639 → 645 with nothing to stop it, and **a share that is only described is not a share that is
asserted.**

---

# PART 3 · ORDER, AND WHAT THIS WILL NOT DO

```
U01  split the metric      ⛔ baseline captured BEFORE, compared AFTER
U02  imported constants    49 → ~22 table-unresolved
U03  declare the 12 dynamic sites
U04  the ratchet on both counts
```

| ⛔ not doing | why |
|---|---|
| resolving the 596 fragment holes | they are not table names. Substituting `AUTHORITATIVE_SCORE_SQL` would make the rendered SQL longer and answer no question the coverage module asks |
| dataflow analysis for `{table}` | a table from a function argument needs the call graph. **Declaring it is the honest answer**, and the plan says so |
| transitive constant resolution | one hop, by design — see `U02` |
| changing `{o}` in `receipts.py` | ⛔ the org filter is **correct**; the METRIC counting it was wrong. Fixing the code to flatter the measurement is the inversion this programme refuses |

⛔ **Done** means: the full suite green with no new skips, every mutation caught or reported invalid
with its reason, **the before/after baseline of every dependent finding printed and explained**, and
the audit written.


---
---

# ⛔ CLOSED 2026-10-04 · PLAN vs ACTUAL

| | planned | ⛔ actual |
|---|---|---|
| **units** | 4 | **4**, plus one hop the plan did not foresee |
| `unresolved_table` | 49 → ~22 | **49 → 16** |
| **declared sites** | 12 | **9** + 2 already declared = 11 ⛔ because three hops closed more than expected |
| **tests** | — | **29** |
| **mutations** | — | **20 caught · 0 surviving · 2 real holes closed** |

## ✅ Where the plan was right, and it was the most useful plan yet

* **Measuring before scoping.** The plan's own Part 1 is the step: it found that 92% of the headline
  was not about tables, that 17 of it was our own org filter, and that the ratchet existed with 8
  points of slack. ⛔ **Without that, this step would have been "resolve 639 placeholders"** — weeks
  of work on predicates that were never a problem.
* **Committing to the before/after baseline in writing.** It was captured, compared three times,
  and the conclusion (*no verdict moved, and that was luck*) is only sayable because the numbers
  were taken first.
* **Bounding the resolver at one hop.** Two tests exist for the forms left out (relative imports,
  `import X` + `X.NAME`), so the bound is declared rather than remembered.
* **Refusing the fourth hop.** 102 tables through the erasure loop is its own unit with its own
  baseline. `3.1b` is in the plan rather than silently inside `3.1`.

## ⛔ Where the plan was wrong

**1 · It expected ~22 and the answer is 16**, because it foresaw **one** resolver hop and there were
**three**. The local-alias case — `table = L3_ACTIVATION_TABLE` — is not in the plan at all, and it
was eight of the twenty-four.

**2 · It said "declare the 12 undeclared dynamic sites" and there are 9**, in **four categories**
the plan did not have. ⛔ And the categories turned out to matter more than the count: calling
`context/backfill.py`'s inline tuple of literal table names "dynamic" would have been **false**, and
`scripts/wipe_org_data.py`'s `information_schema` read is **unresolvable by design** and should
never be closed.

**3 · It framed the ratchet as absent.** It exists; its **threshold** is the defect. ⛔ *"There is no
such assertion"* in Part 1 of this plan is itself wrong, and the audit corrects it: the assertion is
there and has 220 statements of headroom.

## ⛔⛔ What the plan could not have contained

Two of my own guards had real holes, and one came from reading the previous steps' doctrine and
writing the same mistake anyway:

| ⛔ the hole | the shape |
|---|---|
| `STATEMENT_FLOOR` | the test asserted `statements >= STATEMENT_FLOOR` and **the floor is the constant** — lowering it weakened the test. A threshold read from the thing it guards |
| an `or` in a content check | ⛔ **the fourth occurrence.** Removing *"a validator runs first"* left *"unsafe"* standing in a quoted message, and the disjunction passed |

⛔ `2.2`'s plan-vs-actual said *"the next step's plan should carry a written check of its own guards
against the previous step's doctrine, because reading the table was demonstrably not enough."*
**This plan did not carry one, and the same class of defect appeared twice.** `3.1b`'s plan must.

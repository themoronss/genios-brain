# ⛔⛔ AUDIT · STEP 3.1 — the number this step was scoped around was the wrong number

**2026-10-04.** The plan: *"the **639 unresolved SQL statements** (22%) — a table name passed
through a **function argument** needs dataflow, not constant substitution. Today the two known
cases are declared; the share is asserted so it cannot grow silently."*

⛔⛔ **Measured: three of those four clauses are wrong, and the fourth describes a safeguard whose
absence is the reason the first clause is out of date.**

```
"unresolved SQL statements"                645 → 621
⛔ holes in a TABLE POSITION                49 → 16    the figure that bears on table coverage
   holes ELSEWHERE ONLY                   596 → 605   predicates, column lists, bind parameters
sites accounted for                          2 → 11
tests                                        29
```

---

# PART 1 · WHAT THE NUMBER ACTUALLY WAS

## ⛔ 1 · It is not 639. It is 645 — and the clause describing the safeguard is the evidence

The plan says *"the share is asserted so it cannot grow silently."* The assertion **existed**:

```python
assert r["unresolved"] / r["statements"] <= 0.30
```

⛔ Against an actual share of **22.4%**. That is **eight percentage points of slack — about 220
statements of headroom.** A ceiling that loose cannot notice anything, which is exactly how 639
became 645 during Phases 1 and 2, some of it from the receipts those phases added.

⛔ And the guard's own docstring still read *"639 of 2,867 statements"*. **A comment's count ages
faster than its claim** — the rule `2.1` produced, found again in the test that was supposed to
hold the line.

## ⛔⛔ 2 · Ninety-two percent of it was never about tables

A statement counted as "unresolved" if it carried **any** `{placeholder}`. Splitting by whether a
hole sits where a table belongs:

| | count | what the holes are |
|---|---|---|
| ⛔ **table position** | **49** | a table the resolver could not see |
| **elsewhere only** | **596** | `{AUTHORITATIVE_SIGNAL_JOINS}` ×133 · `{AUTHORITATIVE_SCORE_SQL}` ×116 · `{AUTHORITATIVE_REASON_CODE_SQL}` ×81 · `{_COLUMNS}` ×27 · `{VISIBLE_FACT_SQL}` ×14 … |

The 596 are **shared SQL fragment constants** — predicates and column lists assembled once and
interpolated in many places, which is good practice. Resolving them would lengthen the rendered SQL
and answer no question this module asks.

⛔ **And seventeen of them were ours.** `{o}` in `platform/receipts.py` is `_org_filter`'s output,
the string `" and org_id = :org"`. **A correctly parameterised org filter, counted as an unresolved
SQL statement, seventeen times, one module from the one that defines this measurement.** ⛔ The
filter is right; the metric was wrong, and the fix belongs in the metric — fixing the code to
flatter the measurement is the inversion this programme refuses.

## ⛔⛔ 3 · Three of the 49 were the resolver's own regexes

```python
_TABLE = r"([a-z_][a-z_0-9]*)"
_VERBS = {"insert": rf"insert into {_TABLE}", "update": rf"update {_TABLE} set", …}
```

Those templates match `_SQL_SHAPE`, carry a `{_TABLE}` hole in a table position, and **are not SQL
at all**. ⛔ **The observer was counting its own instrument.** Same family as `{o}`, except this one
is in the measuring module itself.

⛔ **Why a declaration and not a heuristic.** The obvious filter is *"skip a statement containing a
regex character class"* — and **SQL contains them**: `0047_l3_domain_compiler.sql` has
`expertise_id ~ '^expertise_[0-9a-f]{64}$'`. A heuristic that cannot tell a `check` constraint from
a regex would hide real statements, which is the failure this module exists to prevent. Three named
sites are cheaper to read and impossible to over-apply.

✅ **And `_table_usage` was never affected** — its verb regexes look for `([a-z_][a-z_0-9]*)` after
the keyword, and `{_TABLE}` does not match a class without `{`. Only the **count** was wrong, never
the attribution.

---

# PART 2 · THREE RESOLVER HOPS, 49 → 16

## ⛔ The import hop — 49 → 27, and the only one that recovered knowledge

`_module_table_constants` looked at constants **in the same module** whose value was a known table.
⛔ `HISTORY_TABLE = "metric_history"` lives in `context/analytic/history.py`; the **fifteen**
statements interpolating it live in `anomaly.py`, **which imports it on line 68**.

*A name-constant is a read* — the rule this module's own docstring says the programme has paid for
three times (`learning_event_inbox` called write-only, `authority_rules` read 3 readers as 1,
`_NODE_REFERENCES` a write nothing could see). ⛔ **It paid a fourth time, one import away.**

⛔ **Bounded on purpose: one hop, direct `from X import NAME` only.** No transitive resolution, no
`import X` plus `X.NAME`, no relative imports, no re-exports — *a re-export is not a definition*,
and the two forms left out are declared and tested rather than forgotten.

**This hop recovered 16 (table, file) attributions** across 5 tables — 9 files reading
`metric_history` that the resolver could not see.

## ⛔ The own-patterns hop — 27 → 24

Three sites, by declaration, as above.

## ⛔ The local-alias hop — 24 → 16, and it recovered nothing

All three activation modules do the same thing:

```python
table = L3_ACTIVATION_TABLE                      # already resolvable
f"insert into {table} (org_id, domain, …)"       # interpolates the LOCAL name
```

So the constant was found and the statement still read as unresolved, because the hole carries the
**alias**. Eight of the 24.

✅ **And it added ZERO new attributions**, measured: every aliasing module already referenced its
own table in a plain literal elsewhere in the same file. ⛔ **Worth saying plainly rather than
implying it recovered something** — this hop made the metric honest and recovered no lost
knowledge.

⛔ **Ambiguity is refused, not guessed.** A local bound to two different table constants in one
module resolves to **nothing** and the hole stays — the same answer `resolve_alias` gives a
contended person name, and for the same reason: picking one is a silent re-attribution that nothing
records.

---

# PART 3 · ⛔ THE OBSERVER PROBLEM, CHECKED RATHER THAN ASSUMED

The plan committed to this before anything was touched, because changing a resolver changes every
finding derived from it.

**Captured before, compared after, all three hops:**

| finding | before | after |
|---|---|---|
| `resolution.unresolved` | 645 | **621** |
| `known_tables` | 189 | ✅ 189 |
| `table_usage` tables | 185 | ✅ 185 |
| `written_and_unread` | 9 tables | ✅ the same 9 |
| `undeclared_unread_writes` | () | ✅ () |
| `stale_unread_declarations` | () | ✅ () |
| unreceipted per package | api 28 · capture 17 · context 33 · deliver 10 · executive 6 · feedback 9 · mcp 1 · packs 2 · platform 24 · reason 29 | ✅ identical |
| `deletion_list` | 102 | ✅ 102 |

✅ **No verdict moved.** ⛔ **And that was luck, not design.** Every affected table already had at
least one visible reference, so recovering 16 attributions changed nothing. A table referenced
**only** through an imported constant would have been reported write-only — which is precisely the
bug `_template`'s docstring says the programme has already paid for three times. The pinned values
are now asserted in the guard so a future resolver change cannot move them quietly.

---

# PART 4 · THE SIXTEEN, EACH WITH A CATEGORY

⛔ **The categories matter more than the count**, because they are four different problems.

| category | n | sites |
|---|---|---|
| ✅ `resolved-elsewhere` | 1 | `api/account_routes.py` — `for tbl in _ORG_SCOPED_TABLES`, and `deletion_list()` already reads that constant off the AST on purpose. The generic resolver leaving the hole open costs nothing |
| ⛔ `resolvable-deferred` | 4 | `capture/journey.py` (tuple-unpacking over `_LEDGERS`) · `context/backfill.py` (⛔ an **inline tuple of literal table names**, the most trivially resolvable hole in the engine) · `scripts/e2e_verify.py` · `scripts/equivalence_check.py` |
| ⛔ `runtime` | 3 | `api/home_routes.py` (the table is a **function parameter** — the dataflow case) · `capture/connectors/database.py` ×3 (**tenant configuration**, and the one site with a real injection surface, which the module already guards with an identifier validator) · `scripts/wipe_org_data.py` (⛔ reads `information_schema` **at run time**, and says why: *"a positive selection cannot be out of date"*) |
| ⛔ `not-a-table` | 1 | `scripts/rebuild_graph.py` — `create table … {tbl}_bak_{ts}`, a timestamped backup being **minted**, not an engine table being read |
| ✅ already declared | 2 | `context/merge.py`, `feedback/store.py` via `NAME_CONSTANT_TABLE_SITES` |

⛔ **`resolvable-deferred` is a deliberate refusal, not an omission.** A fourth resolver hop —
loops over constant collections — has a **102-table blast radius** through the erasure list, and
*noticed something adjacent? New unit, not a silent fix.* It gets its own unit and its own
baseline. Every deferred entry says it is resolvable and points at the other three, and a test
asserts both, because **a resolvable hole described as if it were unresolvable is the worst of the
four categories: it tells the next reader there is nothing to do.**

---

# PART 5 · ⛔⛔ THE SELF-WITNESS FAMILY, FOURTH VARIANT

My own test expected four verb patterns in the source and found **five**. The fifth is inside
`SELF_MEASURED_PATTERNS`' own comment, which **quotes** the pattern it excludes as its example.

> **The declaration about an instrument being measured is itself matched by a measurement of that
> instrument.**

The family so far, one variant per step:

| step | the variant |
|---|---|
| `2.1` | a declaration **falsifies its own count** — writing *"appears in 0 files"* put the word in a file |
| `2.2` | a declaration **satisfies the test that its source exists** — it quoted the rule, so deleting the original passed |
| `2.2` | a **correction's names** were checked against nothing — the fix for a stale comment was about to be one |
| `3.1` | a **quoted example is counted as a real one** |

⛔ The fix each time is to **count distinctly** or **exclude the block** — never to delete the
quote, because the quote is what makes the declaration readable.

## ⛔ And three of my own checks were weak again

| the check | ⛔ why it was wrong |
|---|---|
| `table_holes(_VERBS["read"])` | read the **runtime value**; the f-string is evaluated at import, so there is no hole left. **The resolver reads the file, so the test must read the file** |
| `any(tok in why for tok in (…))` | ⛔⛔ **the third time.** `2.1` replaced one, `2.2` wrote another, `3.1` wrote a third — and this one rejected a *correct* entry for saying "FUNCTION PARAMETER" when the list held lowercase `parameter`. Replaced with a derived form: a reason must **quote code** |
| `len(verbs) == 4` | an expectation stated instead of measured. ⛔ It is **three**: `"(?:from|join) {_TABLE}"` escapes its own counter, because `_TABLE_HOLE` wants whitespace after the keyword and the pattern has `join)` — ✅ which makes the declaration's claim of exactly three right, and right for a reason worth knowing |

---

# PART 6 · THE RATCHET, BUILT

```python
RESOLUTION_CEILINGS = {"unresolved_table": (16, "…")}
STATEMENT_FLOOR = 2_800
```

| decision | why |
|---|---|
| **absolute, not a share** | a share is what failed. 16 is small enough that +1 is visible |
| **no slack** | the guard asserts the ceiling is within 2 of the actual. ⛔ *A ceiling far above the actual is the old failure wearing a new number* |
| ⛔ **the fragment count is NOT ratcheted** | fragments grow for ordinary reasons — extracting a `where` clause into a constant is good practice, and failing the build for it would teach people to inline SQL |
| **raising it is a decision** | the guard's message says to declare the new hole with a category **and** raise the number in the same change, so both appear in one diff |
| **a floor under `statements`** | *a resolver that answers for 1 of 104 answers nothing* — a drop in reach fails the build instead of quietly shrinking every finding |

---

# PART 7 · ⛔ TWO PROCESS SLIPS, RECORDED BECAUSE THEY WOULD HAVE PRODUCED A FALSE GREEN

## ⛔ 1 · A full-suite run against a tree that had already moved

The full suite was started, and **then** one test file was edited — a caching change to
`_open_holes`. ⛔ pytest collects at the start, so the run in flight was executing the **pre-edit**
copy. Its result would have been reported as the step's green, for a file that no longer exists in
that form.

✅ Killed at 66% and restarted. The change was caching-only and the file passes either way, so
nothing was hidden — ⛔ but *"never claim passing without running the command and reading its
output"* means the output has to be **of the thing being shipped**, and a 12-minute run is not a
reason to accept a stale one.

## ⛔ 2 · The guard broke the rule of the module it guards

The caching change itself was wrong on first write. `lru_cache` over a function returning a `dict`
hands **the same object** to three tests — and `table_coverage.table_usage()`'s own docstring says
*"A fresh outer dict each call so a caller cannot poison the cache."* ⛔ **The guard broke the house
rule of the module it was written to guard.** Now the cache holds a tuple of pairs and the public
helper builds a fresh dict from it.

---

# DOCTRINE THIS STEP PRODUCED

| rule |
|---|
| ⛔⛔ **the observer counts its own instrument** — a measurement over source will match the patterns it measures with |
| ⛔⛔ **a quoted example is counted as a real one** — count distinctly, or exclude the block; never delete the quote |
| ⛔ **one number answering two questions will be quoted for the wrong one** |
| ⛔ **a ceiling with slack is not a ratchet** — assert the ceiling is near the actual, or it cannot notice |
| ⛔ **a resolvable hole declared unresolvable is worse than an undeclared one** — it says there is nothing to do |
| ⛔ **the test must read what the measurement reads** — a runtime value is a different object from the source |
| ⛔ **an OR over a hand-listed token set is not a check** — third occurrence; derive it instead |
| ⛔ **state an expectation only after measuring it** — `== 4` was wrong and the truth was more interesting |
| ⛔ **a hop that recovers nothing should say so** — honesty about a fix's reach is part of the fix |
| ⛔ **a suite started before the last edit is a stale green** — collection happens once, at the start |
| ⛔ **a guard must obey the house rule of the module it guards** — a cached `dict` is a poisonable cache |

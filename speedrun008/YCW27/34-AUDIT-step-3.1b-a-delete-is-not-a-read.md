# ⛔⛔ AUDIT · STEP 3.1b — the hop was the small part. `delete from X` was counted as a read of X.

**2026-10-04.** `3.1` deferred this hop in writing: *"a fourth resolver hop with a 102-table blast
radius is its own unit with its own baseline, not a silent addition to this one."* ⛔ **That
sentence is the only reason a pre-existing bug was found instead of four correct declarations being
retired on the strength of it.**

```
unresolved_table          16 → 7      ceiling re-ratcheted to 7, slack 0
statements                   2,885    ✅ unchanged — the measured decision
unresolved_fragment       605 → 614   the nine moved buckets, they did not vanish
table_usage tables        185 → 186
⛔ written_and_unread        9 → 9    SAME COUNT, MEMBERSHIP TURNED OVER
declarations            6 retired · 1 retracted · 1 added · 2 CATEGORIES retired
tests                     56 (28 + 28)
                          ⛔ I predicted the suite at 15,493 and it reported 15,494. The extra
                          one is `test_a_table_nothing_reads_is_declared`, parametrised over
                          `sorted(RETRACTED_UNREAD_WRITES)` — retracting `source_identity_map`
                          took that table 2 → 3 and added a guard case with no edit. ✅ The
                          declaration tables are genuinely wired, and the discrepancy was
                          accounted for rather than waved through
```

---

# PART 1 · ⛔⛔ THE BUG: A DELETE WAS A READ

```python
_VERBS = {"delete": rf"delete from {_TABLE}",
          "read":   rf"(?:from|join) {_TABLE}"}      # ⛔ `delete from cards` matches BOTH
```

Latent for as long as this module has existed. ⛔ **The loop hop amplified it a hundredfold**,
because `api/account_routes.py`'s tenant erasure loop is:

```python
for tbl in _ORG_SCOPED_TABLES:                       # 102 tables
    c.execute(text(f"delete from {tbl} where org_id=:o"), {"o": org})
```

Resolving that one hole attributed a **spurious read to 102 tables at once**, and four of them
stopped being reported write-only:

```
⛔ written_and_unread  9 → 5   card_feedback_revisions · contract_spend_attributions
                              human_events · source_identity_map
⛔ stale_unread_declarations  0 → 4   ← four CORRECT declarations about to be retired
```

✅ **Caught by the before/after comparison the plan committed to in writing.** Without it, this step
would have deleted four true statements and called it progress.

## ⛔ What fixing it revealed

`"read": rf"(?<!delete )(?:from|join) {_TABLE}"` — measured:

| | |
|---|---|
| spurious read facts removed | **139**, across **106 tables** |
| ⛔ tables losing their **only** read attribution | **5** |
| ⛔ among them | **`macv_ledger`** — the North Star number the customer verifies. Its only "read" was `delete from macv_ledger`. ✅ This **mechanically proves** what `19-PENDING` records as a product finding: *referenced only by the delete list* |
| ⛔ and | **`warm_lane_slots`** — a write-only table that had been **hidden by its own delete** |

✅ And a subquery's read survives, which is tested: `delete from a where x in (select 1 from b)`
attributes `delete: a` and `read: b`.

---

# PART 2 · ⛔ THE NAIVE HOP WAS WRONG, AND IT WAS MEASURED BEFORE BUILDING

| | before | ⛔ naive | ✅ built |
|---|---|---|---|
| `statements` | 2,885 | **3,036** (+151) | **2,885** |
| `unresolved` | 621 | **631** — ⛔ *rises* | 621 |
| `unresolved_table` | 16 | 7 | **7** |

⛔ Expanding each loop statement into one per table makes `statements` stop meaning *"SQL statements
in the source"* — a number the share assertion divides by and `scripts/context_coverage_report.py`
prints — and makes `unresolved` **rise**, because expanding one statement into five leaves five
each still carrying the other holes (`{column}`, `{key_column}`). **A real improvement reading as a
regression is worse than no improvement.**

✅ **So attribution expands and the statement count does not.** The loop map feeds `_table_usage`;
`resolution()` keeps counting source statements and simply stops counting a hole the map can close.

## The bounds, declared before the code and each one tested

| ✅ admitted | ⛔ refused |
|---|---|
| `for X in (…literal strings…)` where **every** element is a known table | a **mixed** collection — one unrecognised element and the loop answers for **nothing** |
| `for X in CONSTANT`, resolved through the three `3.1` hops | a constant built by a call, comprehension or slice |
| the **first** element of a tuple target | any other position — which position holds the table is not knowable from the shape |
| `for` statements and comprehensions | `while`, `enumerate`, `zip`, `dict.items()` |
| | ⛔ an **empty** collection — the `1.4` vacuity hole, in a new place |

---

# PART 3 · ⛔ `3.1`'s OWN DECLARATION WAS MISFILED

`3.1` filed `scripts/rebuild_graph.py` as `not-a-table`:

> *"`create table if not exists {tbl}_bak_{ts} as …` — the hole is part of a name being MINTED, not
> an engine table being read."*

⛔ **It describes a statement that was never counted.** `_SQL_SHAPE` matches only
`select|insert|update|delete|with`, so a `create` carries no hole here at all. The **one** counted
statement in that file is:

```sql
delete from {tbl} where org_id=:o
```

— an unambiguous **delete of eight real graph tables** over `for tbl in _GRAPH_TABLES`. ⛔ Wrong in
both halves: the category and the construct. **A declaration citing the wrong line is worse than
none, because it reads as a measurement somebody took.**

## ⛔ And two categories were retired, not emptied

| category | why it is gone |
|---|---|
| `not-a-table` | one member, misfiled |
| `resolvable-deferred` | four members (plus two the measurement found), **all closed by this hop** — it was deferring to this unit |
| `resolved-elsewhere` | its one member (`api/account_routes.py`) is closed outright |

⛔ **An empty category makes every assertion over it vacuous** — the hole that let a mutation survive
in `1.4`. Three entries remain, all `runtime`, and the test's category set is now `{"runtime"}`.
✅ The test that guarded `resolvable-deferred` was **deleted with it**: a test over an empty set
passes vacuously, which is worse than no test because it reads as coverage.

---

# PART 4 · THE TWO DECLARATIONS THAT MOVED

## ⛔ `source_identity_map` — the retracted entry had PREDICTED its own retraction

It said: *"TWO writers, and the second is only visible because of `NAME_CONSTANT_TABLE_SITES`:
merge.py repoints it in the generic node-reference loop. **Read by nothing.**"* ⛔ And the loop hop
makes the **read** in that same loop visible:

```sql
select {id_column} from {table} where org_id=:o and {owner_column}=:n
```

✅ So `context/merge.py` reads it and always has; the name-constant declaration attributed only the
`update` verb. ⛔ **Its mover — *"MOVES WHEN identity resolution reads back its own map"* — was
answered by a resolver change, not by new code.**

## ⛔⛔ `warm_lane_slots` — hidden by its own delete, and write-only BY DESIGN

`platform/warm_lane.py` inserts, updates and deletes it, and nothing reads it. ⛔ Until the verb fix,
its own `delete from warm_lane_slots` read as a read, so **the module appeared to read the table it
only writes.**

✅ **And "read by nothing" is correct here, which is a different kind of entry from the other
eight.** It is a **lease table**: the row's existence *is* the state, `primary key (slot)` enforces
it, and the holder learns the outcome from

```sql
insert … on conflict (slot) do update … where s.lease_until < now() … RETURNING slot
update warm_lane_slots set … where slot = :n and holder = :h        -- via rowcount
```

⛔ **So it IS read — through `returning` and `rowcount`, which no verb pattern in this module can
express.** A **fifth blind spot**, recorded in the entry because the table would otherwise read as
a gap. Its mover says **never**: a `select` over a lease table is a race, which is why the claim is
a conditional write.

## ⛔⛔ The count held while the membership turned over

```
before  9 tables   …  source_identity_map
after   9 tables   …  warm_lane_slots
```

**A step that reported only the count would have reported *no change*.** This is what a baseline
comparison is for and what a bare number hides.

---

# PART 5 · ⛔ THE GUARD HAD DRIFTED, AND TWO PROCESS TRAPS

## ⛔ Two implementations of one question

`3.1` put the hole-exclusion logic in `resolution()` and its guard re-derived it in a helper of its
own. ⛔ When this hop landed, **the metric stopped counting nine holes and the guard's copy did
not** — so it went on asserting that declared sites still held holes the metric had already closed.

> **Two implementations of one question will disagree on the day one of them is right.**

✅ `open_table_holes()` is now the single answer and both read it — which also removed the cache the
guard was keeping, and with it the poisoning hazard `3.1` introduced and then fixed.

## ⛔ The research hit the stale-cache trap before the plan was written

The first delta measurement reported *"no change: 621 → 621, 16 → 16."* ⛔ **`resolution()` is
`lru_cache`d, and the probe cleared `_table_usage` and `_exported_table_constants` but not
`resolution`.** A stale cache made the measurement say the opposite of the truth.

*Establish the baseline or the harness is theatre* — ⛔ **and clearing two of three caches is
theatre with a prop.**

---

# PART 6 · ✅ THE DOCTRINE CHECKLIST, ANSWERED LINE BY LINE

`2.2` recorded that *"the next step's plan should carry a written check of its own guards against
the previous step's doctrine"*, `3.1`'s plan did not, and the same class of defect appeared twice.
⛔ **This plan carried one.** How it held:

| # | the rule | ✅ how this step's guards answer it |
|---|---|---|
| 1 | length is not content | no `len(x) > N` anywhere in the 26 new tests |
| 2 | an OR over a token set is not a check | the lease entry is held to `"returning" in why **and** "rowcount" in why` — a conjunction, because both halves are the evidence |
| 3 | a threshold read from the thing it guards is a variable | `ceiling == 7` **and** `actual == ceiling` — absolute, not relative to itself |
| 4 | a declaration citing its source satisfies the test the source exists | no "X is still in the file" check over a block that quotes X |
| 5 | a quoted example is counted as a real one | no counting regex runs over the new declarations |
| 6 | the test must read what the measurement reads | ⛔ **this is the one that had already broken** — `_open_holes` now returns `TC.open_table_holes()` |
| 7 | state an expectation only after measuring it | every pinned number — 7, 2,885, 9, 186, 139, 102 — was measured before it was written |
| 8 | a declaration can falsify its own measurement | no absence-count claims added |
| 9 | a grade needs its converse guarded | the category set is asserted **equal** to `{"runtime"}`, not merely to contain it |
| 10 | establish the baseline before AND after | ⛔ done three times, and the second run is what caught the delete-as-read bug |
| 11 | a test cannot catch a weakening of itself | every mutation targets the source |
| 12 | the observer counts its own instrument | the lookbehind is asserted **in the pattern's source**, not only in its effect |

⛔ **Rule 6 had already been broken when the checklist was written** — the drifted helper. The
checklist did not prevent it; it is what found it.

---

# PART 7 · ⛔ THE MUTATIONS — one real hole, one piece of dead code, and a claim turned into a proof

```
17 caught · ⛔ 1 REAL HOLE closed · ⛔ 1 dead clause removed · 5 invalid by label or no-op
```

## ⛔⛔ The real hole: a test's own NAME was the false witness

`test_the_FIRST_element_of_a_tuple_target_resolves_and_the_second_does_not` asserted a `zip(...)`
case and a plain-`Name` case. ⛔ **It never contained a tuple target at all**, so a mutation that
guessed the second element passed it. The name said `tuple target`; the body did not have one.

✅ Rewritten with a real `for table, when in PAIRS` over a constant of `(table, column)` pairs —
which is `capture/journey.py`'s actual shape — and split into three tests so one case can no longer
hide the absence of another. *Assert the thing the name claims.*

## ⛔ Dead code, found by a mutation that changed nothing

`if literals and len(known_ones) == len(literals) …` — deleting `literals and` changed no
behaviour, because an empty collection yields an empty `known_ones` and the `if not tables:
continue` below already refuses it. ✅ **Removed rather than kept as belt**: a reader has to be able
to tell a guard from a decoration.

## ✅ And one claim was turned into a proof

A mutation removing the self-pattern exclusion from `open_table_holes()` survived the `3.1b` file.
⛔ I claimed the guard lives in the `3.1` file instead — and then **ran it against both** rather
than leaving the claim standing:

```
against tests/.../test_a_delete_is_not_a_read.py            ⛔ SURVIVED
against tests/.../test_the_resolver_says_what_it_cannot_see.py   ✅ CAUGHT
```

⛔ *A worker's "it passes" is hearsay* — and so is my own.

## ⛔ Five invalid, each named

| | |
|---|---|
| **M4** | deleting dead code changes nothing — a **no-op**, not a survivor, and it found the dead code |
| **M8** | my mutation added an unused assignment instead of expanding the statement list. Re-run properly: **4 tests failed**, including `test_the_statement_count_did_NOT_move` |
| **M18** | `"RETIRED 2026-10-04"` appears **twice** (one per retired category); replacing one left the other |
| **M20** | removed one sentence and left `BY DESIGN` standing earlier in the same entry |
| **M21** | removed one of **two** mentions of `returning`. ⛔ Not tightened: requiring both would be asserting a count in prose, which `2.1` forbids |

---

# DOCTRINE THIS STEP PRODUCED

| rule |
|---|
| ⛔⛔ **`delete from X` is not a read of X** — and a regex that cannot tell them apart hides write-only tables behind their own deletes |
| ⛔⛔ **a resolver improvement must not change what a shared number MEANS** — measured: the naive design inflates `statements` by 151 and makes `unresolved` rise |
| ⛔⛔ **two implementations of one question will disagree on the day one of them is right** |
| ⛔ **a count that holds while its membership turns over is a finding a bare count hides** |
| ⛔ **clearing two of three caches is theatre with a prop** |
| ⛔ **a mixed collection answers for nothing** — half-resolving a list is worse than not resolving it |
| ⛔ **`returning` and `rowcount` are reads no verb pattern can express** — the fifth blind spot |
| ⛔ **retire an emptied category, and delete the test that guarded it** — a test over an empty set reads as coverage |
| ⛔ **a declaration citing the wrong line is worse than none** |
| ✅ **a deferred unit is where a pre-existing bug surfaces** — the deferral in `3.1` is what made the blast radius visible |

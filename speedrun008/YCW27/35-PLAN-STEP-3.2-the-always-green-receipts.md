# ⛔⛔ STEP 3.2 · THE ALWAYS-GREEN RECEIPTS — a receipt over an empty table proves nothing

**Written 2026-10-04, after measuring and before any build.**

The plan's line: *"If `H8.3` says `merge_history` is empty, receipt 42 is structurally green
forever. Gate it on a marker the way the learning receipts are, so it reads 'not yet exercised'
rather than 'passing' — `P2`."*

⛔ **The intent is right and the mechanism it cites is the wrong one**, and the surface that would
consume the answer cannot represent it.

---

# ⛔⛔ PART 0 · THE DOCTRINE CHECKLIST — thirteen rules now

`3.1b`'s plan carried this and it is what **found** the drifted guard. ⛔ Rule 13 is new, from
`3.1b`'s own mutations.

| # | the rule | ⛔ how this step could break it |
|---|---|---|
| 1 | **length is not content** | a witness-declaration entry checked by character count |
| 2 | **an OR over a hand-listed token set is not a check** | five occurrences so far; the obvious shape here is a list of allowed statuses |
| 3 | **a threshold a test reads from the thing it guards is a variable** | "every correctness receipt has a witness" must not be asserted against a count the source sets |
| 4 | **a declaration that cites its source satisfies the test that the source exists** | the witness declarations will quote receipt claims |
| 5 | **a quoted example is counted as a real one** | counting receipts by regex over `receipts.py` will match the docstrings |
| 6 | **the test must read what the measurement reads** | ⛔ broke in `3.1b`; the witness derivation must have ONE implementation |
| 7 | **state an expectation only after measuring it** | no `== 32` that was not measured |
| 8 | **a declaration can falsify its own measurement** | — |
| 9 | **a grade needs its converse guarded** | assert every correctness receipt has a witness AND no presence receipt does |
| 10 | **establish the baseline before AND after** | ⛔ `evaluate()` cannot run here — **no database**. So the baseline is *structural*, and that limit is stated rather than papered over |
| 11 | **a test cannot catch a weakening of itself** | mutate the source |
| 12 | **the observer counts its own instrument** | `receipts.py` will contain the word `witness` in prose and in code |
| 13 | ⛔ **assert the thing the name claims** — and split a test that carries several cases | NEW, from `3.1b`: a test named for a tuple target contained none |

---

# PART 1 · THE MEASUREMENT

```
receipts                           48      32 correctness · 16 presence
⛔ correctness receipts needing a witness   32
   presence receipts needing one            0   ← they FAIL on an empty table already
witness table derivable from the outer FROM 45 of 48
⛔ not derivable                             3
evaluate() statuses today            PASS · FAIL · ERROR      ⛔ no third answer
```

## ⛔ 1 · Only the correctness receipts are vulnerable, and that halves the problem

A **presence** receipt (`expect(0) is False`) asks *"did anything happen"* and **fails** on an empty
table. ✅ It is self-witnessing. A **correctness** receipt (`expect(0) is True`) asks *"did the wrong
thing happen"*, and over an empty table it returns 0 and **passes having proved nothing**.

So the work is 32 receipts, not 48 — and the distinction is already in the data (`expect(0)`), not
in a list anybody maintains.

## ✅ 2 · The witness is DERIVABLE for 45 of 48

The outer `from <table>` of a receipt's own SQL names a known table in 45 cases. The witness is
then `select count(*) from <that table>` with the same org filter: ⛔ **non-zero means the claim was
actually exercised.**

The three that do not derive, each for a different and interesting reason:

| receipt | outer | ⛔ why |
|---|---|---|
| *"every reasoning unit that says nothing is one we declared"* | `jsonb_each` | a **derived-table outer**. ✅ Its real source is already declared in `receipt_coverage`: *"the real source is `reasoning_reasoner_results`"* |
| *"the counterfactual ledger joins end to end"* | `counterfactual_ledger` | ⛔⛔ **it is a VIEW**, not a table (`create or replace view`, `0072`). ✅ And it is a **presence** receipt, so it needs no witness anyway |
| *"a deleted tenant leaves nothing behind"* | — | a `with recursive` over **`information_schema`**. ✅ A schema-level claim: the schema always has rows, so a witness would be noise |

## ⛔⛔ 3 · AND THE SURFACE CANNOT REPRESENT A THIRD ANSWER

`api/routes.py`:

```python
failed = [r for r in rows if r["status"] != "PASS"]
return {"ready": not failed, "passing": len(rows) - len(failed), …}
```

⛔ **Everything that is not `PASS` is counted as failed.** Adding `NOT_EXERCISED` would turn every
unexercised receipt into a reported failure — the opposite of the intent.

⛔ And the deeper question the shape hides: **should an unexercised receipt count as ready?** The
endpoint's own docstring answers it:

> *"these receipts answer the question health metrics never asked: an empty sweep looked healthy,
> **a skip read as a pass**, and 'Present / Wired / Tested' was communicated as active
> intelligence."*

⛔⛔ **A `NOT_EXERCISED` receipt counted as ready IS a skip reading as a pass** — the exact defect
the endpoint exists to prevent. So `ready` must require receipts to be **exercised**, not merely
not-failed.

⛔ **THIS IS A VISIBLE BEHAVIOUR CHANGE** on a live endpoint: a tenant with sparse data will report
`ready: false` where it previously reported `true`. ✅ It is not a new product decision — the
endpoint's docstring states the principle and this implements it — but it is the kind of change that
has to be said out loud rather than discovered, and it goes to Rohit on the pending page.

## ⛔ 4 · One view, and it is invisible to the coverage module

Measured: the whole schema has **exactly one** view, `counterfactual_ledger`. It is referenced by
four modules including `api/intelligence_routes.py` and `platform/receipts.py`, and it appears in
**neither** `_known_tables()` nor `table_usage()` — because both read `create table`. ⛔ A **sixth
blind spot**, with exactly one member, and that member is queried by production code and by a
receipt. ✅ Narrow enough to declare rather than engineer around.

---

# PART 2 · THE UNITS

```
U01  Receipt gains a `witness`, DERIVED from the outer FROM, with the three exceptions declared
U02  evaluate() gains NOT_EXERCISED as a fourth status
U03  ⛔ the readiness surface learns the third answer — and `ready` requires EXERCISED
U04  the views blind spot, declared · and the guard suite with its ratchet
```

## ⛔ U01's bounds, declared before the code

| ✅ | ⛔ |
|---|---|
| the outer `from <known table>` of the receipt's own SQL | a table named anywhere else in the SQL — a join or a subquery is not the subject |
| the same `:org` filter the receipt carries | inventing an org filter a receipt does not have |
| a **declared** witness where derivation fails | guessing one from the claim's words |
| correctness receipts only | presence receipts, which already fail on empty |

---

# PART 3 · WHAT THIS WILL NOT DO

| ⛔ not doing | why |
|---|---|
| running `evaluate()` against production | ⛔ **no database in this checkout.** Every number here is structural, and `P1` stays unmet for all 48 receipts |
| deciding which tables SHOULD be empty | that is the tenant's data, not a code claim |
| making `table_coverage` understand views | ⛔ one member. Declaring it is cheaper and does not invite a `create view` parser |
| changing any receipt's SQL | the receipts are right; what was missing is the third answer |

⛔ **Done** means: the full suite green with no new skips, every mutation caught or reported invalid
with its reason, **Part 0 answered line by line**, the behaviour change on `/readiness` recorded on
Rohit's page, and the audit written.


---
---

# ⛔ CLOSED 2026-10-04 · PLAN vs ACTUAL

| | planned | ⛔ actual |
|---|---|---|
| **units** | 4 | **4** |
| witnesses | 32 | **31** — one schema-level claim needs none, as the plan predicted |
| **tests** | — | **25** |
| **mutations** | — | **19 caught · ⛔ 2 real holes closed** |
| ⛔ **checklist rules broken** | 0 intended | **3**, and the checklist caught all three |

## ✅ What the plan got right, and it was the most load-bearing part

* ⛔⛔ **It found that the plan's own cited mechanism was the wrong one.** *"Gate it on a marker the
  way the learning receipts are"* — a marker prevents a false RED and this is a false GREEN. Writing
  that down first is why the step built a witness and a status rather than adding a predicate that
  could not have worked.
* ⛔⛔ **It found the consumers before touching them.** `api/routes.py` counting everything-but-PASS
  as a failure, and the CLI's literal dict that **raises `KeyError`** — ✅ a crash, discovered by
  reading the consumers in Part 1 rather than by shipping.
* ✅ **It named the behaviour change on `/readiness` in advance**, with the docstring quoted as the
  authority. So `R24` is a recorded decision rather than an operator's surprise.
* ✅ **It stated its own blind spot**: `evaluate()` cannot run here — no database — so every number
  is structural and `P1` stays unmet for all 48. ⛔ Rule 10 of the checklist is answered ⚠️ rather
  than ✅, on purpose.

## ⛔ Where the plan was wrong, or short

**1 · It did not foresee the unification.** ⛔⛔ *A witness IS a presence receipt* — three exist
byte-identical — is the best finding in the unit and the plan has no hint of it. It surfaced only
because a test could not be made to pass three times running.

**2 · It said "45 of 48 derive" and the built number is 31 of 32.** Both are right and they measure
different things: 45 receipts have a derivable outer table, and only the **correctness** ones need
one. ⛔ The plan's figure invited the wrong scope, and Part 1's own next paragraph corrected it.

**3 · It did not predict that `witness_sql` would need to validate the derived name.** An outer
`from` can name a function, a CTE or a view, and a witness over a non-existent relation **raises**.
⛔ The first version did not check, and the three exceptions only became *necessary* once it did.

**4 · It had no line about the test doubles.** ⛔ One of the two real holes was entirely inside a
fake: identifying a witness by suffix, which many receipts share. *A test double that misclassifies
its inputs passes for the wrong reason*, and no plan so far has had a line asking whether the
fixtures can tell their inputs apart. **Rule 14.**

## ⛔⛔ The checklist, and the argument for it

Three rules broke — the sixth `or`-over-a-token-list, the fifth self-witness variant, and rule 12
caught by the ratchet. ✅ **All three were caught**, two by the checklist's own items and one by the
machinery a previous step built.

⛔ And rule 2 has now failed **six times across four steps**. Writing it down is demonstrably not
enough; what works is the derived replacement. **The next plan's checklist should carry the derived
FORM beside each rule, not just the prohibition** — *"a reason must quote code whose identifier
appears in the module"* is a rule that can be applied, where *"do not use a token list"* is one that
can be agreed with and then broken.

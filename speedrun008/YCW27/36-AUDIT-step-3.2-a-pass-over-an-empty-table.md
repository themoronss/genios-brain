# ⛔⛔ AUDIT · STEP 3.2 — a pass over an empty table is not a pass

**2026-10-04.** The plan's line: *"receipt 42 is structurally green forever. Gate it on a marker the
way the learning receipts are, so it reads 'not yet exercised' rather than 'passing' — `P2`."*

⛔ **The intent was right, the mechanism it cited was the wrong one, and the surface that would
consume the answer could not represent it — one of them would have crashed.**

```
receipts                       48    32 correctness · 16 presence
witnesses                      31    derived from each receipt's own outer `from`
declared exceptions             3    a derived-table outer · a VIEW · a schema-level claim
evaluate() statuses          3 → 4   PASS · FAIL · ERROR · ⛔ NOT_EXERCISED
consumers reading one table   1 → 3  ⛔ one of them would have raised KeyError
tests                          25
mutations               19 caught · ⛔ 2 REAL HOLES closed
```

---

# PART 1 · THE MECHANISM THE PLAN CITED IS THE OPPOSITE ONE

The learning receipts' marker — `and counts->>'evaluations' is not null` — prevents a **false
RED**: it stops a run completed before a contract existed being judged against it, because *a gate
that is always red is a gate nobody reads.*

⛔ `3.2`'s problem is the mirror: a **false GREEN**. A correctness receipt (`expect(0) is True`)
asks *"did the wrong thing happen"* and answers 0 when it did not — and **over an empty table it
also answers 0.** No predicate added to its own SQL can tell those apart, because they are the same
query returning the same number for different reasons.

✅ So the answer is not a marker in the SQL but a **witness beside it**: a second query whose
non-zero result means the claim was actually exercised. And a **third status**, because `PASS` and
`FAIL` cannot carry the distinction.

## ✅ Only the correctness receipts needed one, and that halved the problem

A **presence** receipt (`expect(0) is False`) asks *"did anything happen"* and **fails** on an empty
table. ✅ Self-witnessing. 32 correctness, 16 presence — and the distinction is already in the data,
not in a list anybody maintains.

⛔ Though `expect(0) is True` is a **two-point probe of a predicate, not a classification**: *"the
tenant is still being fed"* has a RANGE predicate, so it answers True to both 0 and 7. For a range
receipt the witness is right to run, and a test that assumed otherwise was wrong before the code
was.

## ✅ The witness is DERIVED for 31 of 32

The outer `from <table>` of the receipt's own SQL, counted with the **receipt's own** scoping. ⛔
Only the outer one: a table named in a join or a subquery is not the subject of the claim.

⛔ **And a first version appended the org filter unconditionally** — correct for all 48 receipts
today (measured: 0 of 48 disagree) and wrong as a rule. A fleet-wide correctness receipt's table may
carry no `org_id` column, and the witness would **raise** rather than answer. ⛔ The real set cannot
test that case, so it is constructed.

⛔ **And it did not check that the derived name IS a table.** An outer `from` can name a function, a
CTE or a view — a witness over a non-existent relation does not report *unexercised*, it **raises**.
✅ The refusal is what makes the three exceptions necessary rather than incidental.

| exception | ⛔ why |
|---|---|
| *"every reasoning unit that says nothing is one we declared"* | a **derived-table outer** (`jsonb_each`). ✅ Its real source was **already declared** in `receipt_coverage` — *"the real source is `reasoning_reasoner_results`"* — so this witness is that declaration's sibling, not a new judgement |
| *"the counterfactual ledger joins end to end"* | ⛔⛔ its outer name is a **VIEW**, and it is a **presence** receipt besides |
| *"a deleted tenant leaves nothing behind"* | `with recursive` over **`information_schema`**: a claim about the schema's foreign keys, where a witness would always pass and therefore say nothing |

---

# PART 2 · ⛔⛔ A WITNESS IS A PRESENCE RECEIPT

The best thing in the unit, and it took **three failed test attempts** to see.

The derived witness for a correctness receipt over table T is `select count(*) from T where 1=1 …`
— and for three tables that is **byte-identical** to an existing receipt:

| table | the presence receipt whose SQL it equals |
|---|---|
| `expertise_packages` | *"compiled expertise packages exist"* |
| `delivery_outbox` | *"the delivery control plane has run"* |
| `learning_runs` | *"the learning engine has executed"* |

✅ **So *"was this claim exercised"* and *"has this layer ever run"* are the same question.** Three of
them were written by hand; the other 28 are now derived instead of waiting to be written. ⛔ It is a
coherence check on the design rather than a duplication to remove.

⛔ **And it made a test unanswerable three times**, which is how it was found:

| attempt | ⛔ why it was wrong |
|---|---|
| 1 | asserted FEWER witnesses ran than exist — but with every claim answering 0, **every** correctness receipt passes and every witness legitimately runs. The premise, not the code |
| 2 | matched witness SQL by **membership** — two receipts over one table share one witness string, so *"this SQL was asked"* says nothing about who asked |
| 3 | **counted** the calls — and three receipts' own SQL *is* a witness, so the counts could never balance |

✅ Settled with a fixture of **two** receipts, where attribution is unambiguous. ⛔ And the fixture
walked into the collision twice itself — first the failing receipt's SQL equalled its witness, then
the passing one's — which is confirmation that the collision is **structural, not incidental**.

---

# PART 3 · ⛔⛔ THE SURFACES COULD NOT REPRESENT A THIRD ANSWER, AND ONE WOULD HAVE CRASHED

```python
# api/routes.py            failed = [r for r in rows if r["status"] != "PASS"]
# scripts/runtime_receipts.py   mark = {"PASS": …, "FAIL": …, "ERROR": …}[r["status"]]
```

⛔ The endpoint counted everything-but-PASS as a failure. ⛔⛔ **And the release-gate CLI held a
literal dict lookup, which raises `KeyError` on a status it has not met** — so adding
`NOT_EXERCISED` would have **crashed the release gate**, not disagreed with it.

And the endpoint's own docstring promises *"the same list the release-gate CLI runs, **so the
operator surface and the release gate cannot drift apart about what 'ready' means**."* ⛔ They had
already drifted in **shape**, which is the kind of drift a promise about content does not catch.

✅ `RECEIPT_STATUSES` is now the one answer — `{status: (ready?, meaning)}` — and all three read it.
⛔ A first version of the endpoint's new block wrote `status in ("FAIL", "ERROR")`: **a third
implementation, in the same change that added the constant to prevent exactly that.**

## ⛔⛔ AND `ready` NOW REQUIRES EXERCISED — a visible behaviour change

The docstring again: *"an empty sweep looked healthy, **a skip read as a pass**, and 'Present /
Wired / Tested' was communicated as active intelligence."*

⛔ **An unexercised correctness receipt counted as ready IS that skip.** So `NOT_EXERCISED`
withholds readiness rather than merely being reported — and a tenant with sparse data will now show
`ready: false` where it showed `true`.

✅ Not a new product decision: the paragraph states the principle and this implements it. ⛔ But it
changes what an operator sees for most tenants today, so it is **`R24`** on Rohit's page with the
alternative spelled out, not left to be discovered.

---

# PART 4 · THE RATCHET CAUGHT ITS OWN AUTHOR

`witness_sql` builds `f"select count(*) from {table} …"` where `table` is a **regex match over
another receipt's SQL**. ⛔ That is a table-position hole, and `3.1b`'s ratchet failed the build:

```
unresolved_table  8  against a ceiling of 7
```

✅ **The only real proof a ratchet works.** Declared `runtime` in `TABLE_HOLES_NOT_CLOSED`, and the
ceiling raised **7 → 8 in the same diff** — which is exactly what the guard's message demands:
*declare the hole AND move the number in one change, so both appear in one diff.*

⛔ `statements` also moved **2,885 → 2,888**, deliberately: the witness builder and its exceptions
are three real SQL statements. ✅ That is the engine gaining SQL, which is ordinary — what the guard
exists to catch is the loop hop **expanding** the list, which would have added 151 at once.

## ⛔ And the views blind spot, declared

`_known_tables()` reads `create table`, so a view is invisible to it and to every measurement built
on it. ✅ Measured: the whole schema holds **exactly one** — `counterfactual_ledger` — and it is
**live**: `api/intelligence_routes.py` queries it and an L7 receipt counts its joined rows.
`SCHEMA_OBJECTS_NOT_SEEN` declares it, both directions guarded. ⛔ A table nobody can see is a table
nobody can audit.

---

# PART 5 · ⛔ TWO REAL HOLES, AND THE FIFTH SELF-WITNESS VARIANT

## ⛔⛔ Hole 1 · a test double that misclassified its inputs

The fakes identified a witness by **suffix** — `sql.endswith("where 1=1 and org_id = :org")` — and
**many receipts end exactly that way**, because `_org_filter` appends it. ⛔ So a receipt's own query
was treated as a witness, the broken-witness fake raised on it, and
`test_a_witness_that_raises_makes_the_receipt_an_ERROR` **passed for the wrong reason**: it saw an
ERROR, just not the one it was asserting about.

> ⛔ **A test double that misclassifies its inputs passes for the wrong reason** — and a suffix
> heuristic is the same family as a hand-listed token set.

✅ The fakes now derive the witness set from `witness_sql` itself.

## ⛔ Hole 2 · the case the real set cannot provide

Deleting the receipt-scoped org filter is a **no-op on all 48 receipts today**, so every test
written against the real set survived it. ✅ The fleet-wide case is now **constructed**, because the
current set cannot provide it.

## ⛔⛔ The fifth variant of the self-witness family

My check that the old pattern is gone searched the whole file — and **both modules' comments QUOTE
the code they replaced**, to explain what changed. ⛔ So the check against the old pattern found my
own explanation of why it is gone.

| step | variant |
|---|---|
| `2.1` | a declaration **falsifies its own count** |
| `2.2` | a declaration **satisfies the test that its source exists** |
| `2.2` | a **correction's names** were checked against nothing |
| `3.1` | a **quoted example counted as a real one** |
| `3.2` | ⛔ a **comment quoting the code it replaced** satisfies the check against that code |

✅ Fixed by searching code lines only. ⛔ **Never by deleting the quote** — it is what makes the
change readable.

## ⛔ And the sixth `or`-over-a-token-list

`3.1`'s own guard held `any(tok in why for tok in ("FUNCTION PARAMETER", "TENANT CONFIGURATION",
"information_schema"))` — and `3.2` added a `runtime` entry saying *"REGEX MATCH"*, a perfectly good
reason that was **not on the list**. ⛔ So a **correct** entry was rejected. ✅ Replaced with a
derived form: a `runtime` entry must quote code whose identifier appears in the module it is about.

⛔ And the first version of **that** was too strict — it demanded the quoted text verbatim and
rejected `_weekly(conn, org, table: str, …)`, an honest citation written with an ellipsis.

> ⛔ **A derived check that is too strict rejects a true statement** — the mirror of a token list
> that is too loose. Both replace reading with a rule, and both are wrong in one direction.

---

# PART 6 · ⛔⛔ AND A GUARD THAT ALREADY EXISTED CAUGHT ME TWICE

The full suite failed on `tests/test_spec_deferrals_resolve.py` — a file this step never touched.

## ⛔ First: a dangling citation, mine

`api/routes.py` recorded the behaviour change with *"it is recorded in `19-PENDING`"*. ⛔ That guard
exists because **four** comments in this engine once deferred to a record that was never created,
and its docstring states the cost exactly: *"a reviewer starting X5 cannot find the assumptions X3
made"* — *"the deferral reads as diligence right up until somebody follows it."*

⛔⛔ **`19-PENDING` is not a resolvable target.** The guard resolves a path on disk or a name defined
in the tree, and that is a bare label. ✅ Fixed to the full path,
`speedrun008/YCW27/19-PENDING-who-owns-what.md`.

> ⛔ *A citation that does not resolve reads as a measurement and is not one* — a rule this
> programme has written into its own guards four times over, **while leaving one dangling in the
> engine.** The guard that caught it is older than any of them.

## ⛔⛔ Then: the sixth self-witness variant, from EXPLAINING the guard

The fix's comment explained what the guard was built for — and **named the record it greps for**. ⛔
Its sibling test fired on my explanation.

| step | variant |
|---|---|
| `2.1` | a declaration falsifies its own count |
| `2.2` | a declaration satisfies the test that its source exists |
| `2.2` | a correction's names were checked against nothing |
| `3.1` | a quoted example counted as a real one |
| `3.2` | a comment quoting the code it replaced |
| `3.2` | ⛔⛔ **explaining a guard trips the guard** — the token had to go unnamed |

✅ Rewritten without the token, and the comment says why it is unnamed, so the next person does not
restore it.

---

# PART 6 · ⛔ A PROCESS ERROR

The platform suite was run **concurrently with the mutation harness**, which edits source files in
place. ⛔ One test failed on a file the harness had mutated at that instant, and the failure was
reported as real. ✅ Re-run sequentially: clean.

Same family as `3.1`'s stale suite — *the output has to be of the thing being shipped* — and the
rule is now: **never run a suite while a mutation harness is running.**

---

# PART 7 · ✅ THE DOCTRINE CHECKLIST, ANSWERED

| # | the rule | ✅ how it held, or ⛔ how it broke |
|---|---|---|
| 1 | length is not content | ✅ no `len(x) > N` |
| 2 | an OR over a token set is not a check | ⛔⛔ **BROKE** — sixth occurrence, in `3.1`'s guard, rejecting a correct entry. Replaced with a derived form |
| 3 | a threshold read from the thing it guards | ✅ the ceiling is asserted equal to the actual |
| 4 | a declaration citing its source | ✅ — and ⛔ the comment-quoting variant broke instead |
| 5 | a quoted example counted as real | ✅ |
| 6 | the test must read what the measurement reads | ✅ the fakes derive the witness set from `witness_sql` |
| 7 | state an expectation only after measuring | ⛔ broke three times on one test, each time corrected by measuring |
| 8 | a declaration can falsify its own measurement | ✅ |
| 9 | a grade needs its converse guarded | ✅ every correctness receipt has a witness **and** no presence receipt does |
| 10 | baseline before and after | ⚠️ **structural only — there is no database here**, and that limit is stated rather than papered over |
| 11 | a test cannot catch a weakening of itself | ✅ |
| 12 | the observer counts its own instrument | ⛔⛔ **BROKE, and the ratchet caught it** — the witness builder added a table hole |
| 13 | assert the thing the name claims | ⛔ broke twice: a test named for a total, and one named `came_DOWN` after the ceiling went up. Both renamed to what they assert |

⛔ **Three rules broke and the checklist caught all three.** That is the argument for carrying it,
and `3.1b` made the same argument from the other direction.

---

# DOCTRINE THIS STEP PRODUCED

| rule |
|---|
| ⛔⛔ **a pass over an empty table is not a pass** — a correctness receipt needs a witness, and `NOT_EXERCISED` is not ready |
| ⛔⛔ **a witness IS a presence receipt** — the two questions are one, and three were already written by hand |
| ⛔⛔ **a test double that misclassifies its inputs passes for the wrong reason** |
| ⛔ **a derived check that is too strict rejects a true statement** — the mirror of a loose token list |
| ⛔ **a literal dict lookup over a status crashes on a status it has not met** — a promise about content does not catch drift in shape |
| ⛔ **`expect(0) is True` is a two-point probe of a predicate, not a classification** |
| ⛔ **the case the real set cannot provide must be constructed** — a no-op mutation on today's data is not a no-op as a rule |
| ⛔ **never run a suite while a mutation harness is running** |
| ✅ **a ratchet that catches its own author is the only proof a ratchet works** |

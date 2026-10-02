# S5 — DONE · the inbox landed; the `kind` did not — and the rows are dropped on the floor

**Unit:** `M14.C2.S5` · **Owner:** me · ✅ **2026-10-02** · **27 tests · 8/8 mutations caught**
**Atlas:** Layer 7 gap **#1**'s residue — ⛔ **narrowed from "no inbox" to "no `kind`"**
**Plan:** [`08-PLAN-v2-from-the-atlas.md`](08-PLAN-v2-from-the-atlas.md) §6 — *"a declared silence,
not a build"*

---

## 1 · What the plan said, and what one grep changed

`08-PLAN-v2` §6 priced this as two declared silences: *"the structured preference inbox is a surface
that does not exist, and a function that names the reader it does not have is a surface that was
never built."*

⛔ **Then `orchestrator.py:188` turned out to mention an inbox** — and the measurement that followed
is the step.

## 2 · ⛔⛔ The chain: written in production, loaded into every batch, consumed by nothing

```
migrations/0046_l6_learning_hardening.sql   learning_event_inbox — "trusted structured
                                            events/memory, idempotent, with a lease"
reason/moments/store.record_feedback        ⛔ INSERTS a row for every moment-feedback action
api/moment_routes.py:746                    ⛔ reached in PRODUCTION
feedback/store.py                           loaded into EVERY weekly batch as `batch.inbox`
feedback/units.py                           ⛔ NO unit reads it  (asserted on the AST)
orchestrator.run_learning                   counts the rows it is about to drop as
                                            `inbox_unconsumed` → `learning_runs.counts`
```

⛔ **So *"Empty until the inbox lands"* — the docstring on both stub units — was stale. The inbox
landed.** And `orchestrator.py`'s justification for its counter said:

> *"Empty at both ends today, so it costs nothing — **but the day something starts writing to that
> table, rows would be read and dropped on the floor with no counter moving anywhere.** Naming the
> count makes that arrival visible instead of making it a mystery about why learning ignores a
> ledger somebody just wired up."*

> ⛔⛔ **That day had already come, and the comment's own prediction is what happened.** The
> reasoning was right; only the premise went stale.

## 3 · ⛔ The gap is a `kind`, not a table — and that decides who can close it

Every row written today carries `payload.kind == "moment_feedback"` — a card action, not an explicit
first-person instruction with a subject, a scope and exceptions.

| | |
|---|---|
| a **table** | a migration. `learning_event_inbox` already exists, idempotent on `(org, actor, source_ref)`, with `payload`, `visibility`, `observed_at` and ⛔ a **`lease_until`** column for exactly a dated directive |
| a **`kind`** | ⛔ a **SURFACE** where a founder states a preference or a dated directive. **There is none** |

⛔ **And `LearningTarget` has no `PREFERENCE` member**, so a bounded personal preference would have
to arrive as `BEHAVIOR` with a resolved `subject_principal` — which `governance.preflight` already
refuses when a private-scoped proposal has no principal. **The sink exists; the input does not.**

### ⛔ Everything downstream of `unit_temporary_memory` is already built

The Atlas's worked example is *"Pause outreach for seven days"* (`L7-18`): *"Create
Runtime/temporary entry with mandatory TTL … Pause applies for declared period and has zero
influence afterward."* Five pieces, **all five present**:

```
LearningTarget.RUNTIME · govern() → TEMPORARY · publish_runtime → temporary_memories
(expires_at NOT NULL) · preflight's three expiry checks · brain_pipeline.expire_leases
```

⛔ **The missing input is the whole of the gap** — which is why `S5` is a declaration and not a
build.

### ⛔ And a model is not the answer

The Atlas is explicit, and it is quoted in the declaration so nobody closes this with a parser:

> *"**Adding a model directly to empty units would produce eloquent ungrounded preferences. First
> wire typed evidence**; then use a model narrowly where language ambiguity is irreducible."*

Its own improvements table makes the inboxes **P1** — *"Implement explicit preference and
temporary-memory inboxes"* — not the extraction.

## 4 · ⛔⛔ What was BUILT: the layer's first correctness receipt

The re-crosscheck measured `feedback/` at **four receipts, all four PRESENCE checks** — *"has the
learning engine executed"*, *"has calibration executed"* — every one satisfied by a single
successful tick. ⛔ **`inbox_unconsumed` was written into `learning_runs.counts` and read by
nothing.** *The reader is half the unit.*

```python
Receipt("L7", "no completed learning run hides whether it dropped inbox rows",
        "select count(*) from learning_runs where status = 'completed' "
        f"and counts->>'inbox_unconsumed' is null{o}",
        lambda n: n == 0, ...)
```

```
receipts            35 → 36
feedback/ receipts  4 → 5      ⛔ CORRECTNESS: 0 → 1
```

### ⛔ Why this claim and not *"the loop dropped nothing"*

`inbox_unconsumed > 0` is the **known state of a declared gap**, so a receipt on the drop would be
red on every tenant with any moment feedback, forever. ⛔ And `platform/receipts.py` already carries
the rule, written for a different claim:

> *"a gate that is always red is a gate nobody reads. **The claim is the one that is true today and
> false when it gets worse**."*

So the receipt **guards the visibility**: the counter is the only thing that will make the arrival
of a consumer — or of a second writer — discoverable. Delete the counter, or complete a run without
it, and it goes red. `test_the_claim_guards_the_visibility_and_not_the_drop` asserts the SQL says
`is null` and **not** `> 0`.

## 5 · The mutation run — baseline first, 8/8

```
✅ baseline: 27 passed

  M1 the receipt is removed                      ✅   M5 the stale sentence re-ASSERTED       ✅
  M2 ⛔ the claim becomes the ALWAYS-RED one      ✅   M6 expires_at loses NOT NULL            ✅
  M3 the count stops being persisted             ✅   M7 a SECOND inbox writer appears        ✅
  M4 ⛔ a unit starts consuming the inbox         ✅   M8 a NEW inbox kind appears             ✅

✅ baseline again: 27 passed              8 caught · 0 survived
```

⛔ **`M4` and `M6` reported "ANCHOR MISSING — COUNTS NOTHING" on the first run** (a line-wrapped
docstring and a differently-spaced column). Fixed and re-run. *An invalid mutation is not a
surviving mutation* — `S4`'s rule, holding again.

## 6 · ⛔⛔ My own fault — the same class, THIRD time in one session, in the test documenting it

My guard read:

```python
assert "batch.inbox" not in units      # ⛔ failed on correct code
```

…and the corrected docstring I had **just written** explains that the inbox is *"loaded into every
weekly batch as `batch.inbox`"*. ⛔ **A docstring that explains a gap contains the words of the
gap.**

| | The three instances |
|---|---|
| `S2` | asserted a false phrase was absent; the correction **quoted** it → *check attribution, not presence* |
| `S2`'s own docstring | carried the rule it then broke |
| ⛔ **`S5`** | asserted a code string was absent from a file whose **documentation** names it |

> ⛔ **The sharper form of the rule: a claim about CODE must be checked against the AST, not against
> the text.** An attribution window would also have passed here and would have been the **wrong
> tool** — the question is not *"who said this"* but *"does any unit read this attribute"*, and only
> the AST answers it.

The guard now walks `units.py`'s AST for `*.inbox` **and** for `getattr(batch, "inbox", …)`, because
the orchestrator reaches it the second way and a guard that knew only attribute access would miss
it.

## 7 · What changed

| File | Change |
|---|---|
| `platform/receipts.py` | ⛔ **the layer's first correctness receipt** |
| `feedback/units.py` | both stub docstrings — the stale sentence quoted and corrected, the `kind` named, the lease machinery inventoried, the Atlas's *"first wire typed evidence"* recorded |
| `feedback/orchestrator.py` | ⛔ the stale premise *"empty at both ends today"*, with the writer and route that falsified it |
| `feedback/target_policy.py` | both stub entries — the inbox named, a `MOVES WHEN` inside the reason (there is no mover column), and ⛔ why neither is a `DELEGATED` placeholder |
| `tests/feedback/test_the_inbox_landed_and_nothing_consumes_it.py` | **27 tests** |

## 8 · Verify

```bash
.venv/bin/pytest tests/feedback/test_the_inbox_landed_and_nothing_consumes_it.py -q   # 27 passed
.venv/bin/pytest tests/platform tests/feedback tests/contracts -q                     # 1,419
.venv/bin/pytest -q                                                                   # FULL suite
```

## 9 · ⛔ What this hands to Rohit

**Atlas Layer 7 #1 is its own P1, and it is a SURFACE, not engineering in this layer.** A founder
needs somewhere to say *"pause outreach for seven days"* or *"always cc my co-founder on investor
threads"*. Everything behind that sentence exists — the inbox, the idempotency, the lease column,
the TTL ceiling, the expiry sweep, the audit trail. ⛔ **And the inbox is already carrying rows
nobody reads**, counted every week in `learning_runs.counts`.

⛔ **Not a model.** The Atlas's own warning is quoted in the code: a parser pointed at free text
would produce *"eloquent ungrounded preferences."*

## 10 · Doctrine

| Rule |
|---|
| ⛔ **a claim about code must be checked against the AST, not against the text** — the sharper form of `S2`'s rule, and the third instance of the class in one session |
| ⛔ **a docstring that explains a gap contains the words of the gap** |
| ⛔ **the gap is a `kind`, not a table** — a table is a migration, a `kind` is a surface, and the difference decides who can close it |
| ⛔ **a gate that is always red is a gate nobody reads** — so guard the visibility, not the known drop |
| ⛔ **a comment's reasoning can be right while its premise goes stale** — the counter was built for exactly the day that arrived |
| **the missing input can be the whole of the gap** — five downstream pieces, all built |
| **an invalid mutation is not a surviving mutation** |

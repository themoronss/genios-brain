# Step 6 — ✅ DONE · the signal bundle · owner: us

> **Status:** TO BUILD · **not blocked on the API limit** · scope bounded by [Step 5](STEP-05-NEXT-object-placement.md)
> **Tree:** `M9.C1`, units `U01`–`U05`

---

## 1 · What is true today

No bundle exists. Related signals arrive at Layer 2 as **separate loose events**, so four signals
about one renewal become four weak situations instead of one strong one.

The coverage receipt — which **does** exist, per source and frozen at capture — is carried on the
*signal*, not on a group.

## 2 · What must be true

Layer 2 receives **one bundle per group of incoming signals**, carrying the candidate relationships
and the coverage that licenses a negative claim about them.

## 3 · The units

| Unit | What | ⛔ The constraint that matters |
|---|---|---|
| `U01` | `QualifiedEnterpriseSignalBundle` contract | the receipt **reuses** `SourceCoverage` — per source, **never blended**. *"A tenant with complete calendar coverage and 8% email coverage has two different licences to make a negative claim, and one blended number would grant the stronger one to both."* |
| `U02` | the bundle table | keyed so a replayed signal is idempotent |
| `U03` | the grouper — entity, thread, time window, commitment, meeting | ⛔ **it must not read the graph.** The moment it does, L1 imports L3 and the topology test fails the build. This is Step 5's decision made concrete |
| `U04` | the coverage receipt on the group | ⛔ **never 100% by default.** *"Defaulting it full would write Gemini's failure into our own contract."* Unknown stays `None` |
| `U05` | the publisher emits it **beside** `qualified_signals` | built beside the old path, not over it; both counted on one sweep before either is retired |

## 4 · Scenario → expected result

| Scenario | Expected |
|---|---|
| three signals about one vendor renewal arrive together | **one** bundle, three signals, candidate relationships named |
| Drive is not connected | the receipt says so per source; the bundle does **not** claim a complete search |
| the same signal replays | one bundle, not two |
| the grouper is given a graph handle | ⛔ the topology test fails |
| a negative claim is made from the bundle | it carries the coverage that licenses it, or it is not made |

## 5 · What we are NOT doing here

| Not doing | Why |
|---|---|
| relationship reasoning over the graph | that is Layer 2's, over Layer 3's graph. This groups what **arrived together**, nothing more |
| replacing `qualified_signals` | both paths run for one release and are compared first |
| a new coverage number | one exists, per source, and it is better than a blended one |

## 6 · Known unsound verify

`U02`'s verify names `tests/platform/test_migrations_apply.py`, **which does not exist**. Either add
the unit that creates it or change the verify. Recorded so it is not discovered mid-build.

---

# Progress

| Unit | What | Status |
|---|---|---|
| `U01` | `QualifiedEnterpriseSignalBundle` contract | ✅ **DONE** · `tests/contracts/test_the_bundle_carries_its_coverage.py` — 11 passed |
| `U02` | the bundle table | ⬜ next |
| `U03` | the grouper | ⬜ |
| `U04` | the coverage receipt on the group | ⬜ |
| `U05` | the publisher emits it beside `qualified_signals` | ⬜ |

## U01 — what was built, 2026-09-30

`genios_engine/contracts/signal.py` · `QualifiedEnterpriseSignalBundle`, frozen.

| Field | Why it is shaped that way |
|---|---|
| `signal_ids` | ⛔ **at least one, and each listed once.** An empty bundle is a grouper that ran and had nothing to say — that belongs in a receipt, not on a boundary. A repeat means it double-counted, and every denominator computed from the bundle is then wrong by that much |
| `subject_key` | **nullable on purpose.** A group can be real — *"these three arrived in one thread"* — before anybody can name the business object. Forcing it would invent one |
| `candidate_relationships` | ⛔ named `candidate_`, not `relationships`. It is a proposal made from what arrived together; the word is what stops a reader treating a time-window coincidence as a fact |
| `coverage` | `SignalCoverage.as_dict()`, **per source** |
| `unresolved` | not an error list — L2 reads it to decide whether to **ask** rather than guess, which is why it rides the contract instead of a log |

### ⛔ The validator that carries the rule

A top-level `completeness_bp` is **refused at construction**:

> *"A tenant with complete calendar coverage and 8% email coverage has two different licences to
> make a negative claim, and one blended number would grant the stronger one to both."*

And `coverage_for(source)` returns **`None`, never zero**, for a source it knows nothing about —
*"we read 8%"* and *"we do not know what we read"* license different claims.

### Why the dict and not the class

`contracts/` may import nothing but `platform` and the standard library, so it cannot hold
`SignalCoverage` itself. It carries that class's existing `as_dict()` jsonb shape — the one already
stored on C-12 — rather than a second serialisation that would drift from it.

### One defect found while building it

The default was `MappingProxyType({})`, which pydantic cannot deep-copy. Every **other** validation
error on the model was swallowed while rendering that one — *"a bundle carries at least one
signal"* arrived as *"cannot pickle 'mappingproxy' object"*. The refusal was correct and
unreadable. Now a plain `{}`, matching `contracts/situation.py`.

### Proof

```
tests/contracts/test_the_bundle_carries_its_coverage.py    11 passed
tests/contracts + topology + object placement             657 passed · 0 failed
```

---

# ✅ DONE — 2026-09-30 · all five units

| Unit | Artifact | Tests |
|---|---|---|
| `U01` | `contracts/signal.py` · `QualifiedEnterpriseSignalBundle` | 11 |
| `U02` | `migrations/0186_signal_bundles.sql` | cascade + shape guards |
| `U03` | `capture/esqe/bundle.py` · the grouper | 23 (with U04) |
| `U04` | `bundle.merged_coverage` | ↑ |
| `U05` | `capture/esqe/publisher.py` · emits beside `qualified_signals` | 9 |

**Verified:** `tests/capture` + `tests/contracts` + topology + object placement + erasure —
**5,921 passed · 1 failed** (the 1 is the pre-existing OCR one, [Step 8](STEP-08-PENDING-HARSH-ocr.md)).

## The four rules this step is made of

**1 · Identity joins have no window; proximity joins do.**
A thread is a thread whether its messages are four minutes or four months apart — splitting one on
a clock produces two half-threads that each look like a complete conversation. An **entity** is not:
"Acme" in January and "Acme" in September are the same company and not the same event. Without
`ENTITY_WINDOW` (7 days) every mention of a frequent counterparty collapses into one ever-growing
bundle that means nothing.

**2 · ⛔ Merged coverage takes the WEAKEST per source, never an average.**
A claim about a group is only as licensed as its least-covered member. If one signal was captured
when 8% of the mail had been read, a negative claim about the group rests on that 8% however
well-covered its siblings were. Averaging 9500 and 800 gives 5150 — **a licence neither member
has.** Same law `ConfidenceVector` uses when it bounds a composed score by its weakest axis.
And **unknown beats any percentage**: *"we do not know what we read"* is weaker than any number.

**3 · ⛔ The id is the idempotence.**
`bundle_id` is a hash of the org and the **sorted** member ids, so a replayed connector page
produces the same id and the insert collapses to one row. A serial id would have made every replay
a second bundle and every denominator computed from bundles wrong by however many times the page was
retried. Sorted, because the group is a **set**.

**4 · ⛔ Built from `emitted`, never from `qualified`.**
A signal the gate refused at V-2…V-7 did not cross this seam. A bundle listing it would hand Layer 2
a group whose members it cannot fetch, and a coverage denominator over rows that were never
published. A test reads the publisher's own source to pin it, because the wrong version is one line
shorter.

## What did NOT change

⛔ **Built beside the old path, not over it.** With no `bundle_store` the pass behaves exactly as
before — same emitted rows, same stored count, same refusals — and the new parameter defaults to
`None`, so every existing caller works unchanged. That is what lets both paths run for a release and
be compared on one sweep, the rule `deliver/card_source` already keeps at L5.

## Two design notes worth keeping

**Two subjects in one group names neither.** That is not a bundle with two subjects — it is a group
the joins over-merged, and naming one of them would hide it.

**An unnameable group says so.** `unresolved` carries *"no subject could be named for this group"*
rather than leaving it blank, because that sentence is what an `EvidenceNeed` is raised from in
[Step 7](STEP-07-evidence-need.md).

## The schema refuses the blended number

`0186` has **no `completeness_bp` column**. The contract's validator can refuse one at construction,
but anything holding a connection could write a column — so the schema does not offer the shape.


---

## ⛔ 2026-10-01 · the title line of this file was stale, and is corrected above

This file's **first line** read `Step 6 — TO BUILD · the signal bundle · owner: us` while the `✅ DONE — 2026-09-30` section below recorded the
work as built, and the filename had already been renamed to `...-DONE-...`. Three labels on one
piece of work and one of them disagreed with the other two.

**Why this is recorded rather than quietly fixed.** A heading that says *TO BUILD* on finished work
is the same defect as a stale comment: it reads as a status somebody checked. Anyone auditing the
programme by scanning headings would have counted this step as outstanding and, worse, might have
rebuilt it. Found while assembling `07-LEDGER-every-step-what-why-how-outcome.md`, which reads the
first line of every step file — the ledger could not have been written without resolving it.

**What was verified before the title was changed:** the artifacts named in the DONE section exist in
the tree, and the full suite is 14,534 passed / 0 failed. The title was not made to agree with the
others; it was made to agree with the code.

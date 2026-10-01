# Step 15 — Coverage on the signal

**Status:** NOT STARTED · **Effort:** days · **Depends on:** 3, 5 · **Engine:** D
**Moves:** metric 6 · benchmark check #4, completed

> **Added after the first plan.** Step 5 builds the denominator. Nothing carried it to the signal,
> so a negative claim still could not prove itself.

## 1. Why this step exists

This is the lesson the benchmark teaches most clearly, and it is an **epistemic** one:

> **"No follow-up email found"** means nothing until you know whether the search covered 100% of
> the mail or 8% of it.

Gemini's worst failure was exactly this — it reported the size of its context as the size of the
mailbox. Claude's strongest behaviour was publishing a coverage table before any finding.

`coverage/declaration.py` already makes the argument, one level up, for **channels**:

> *"It is the difference between 'this customer has no support tickets' and 'we have no source
> that could carry a support ticket.' The first is a finding; the second is a blind spot wearing a
> finding's clothes."*

Step 5 extends that to **objects** — how many existed, how many were fetched, did the cursor
exhaust. **This step carries that answer onto the signal**, so every downstream negative claim
inherits its own proof.

### Five different realities that all look like "nothing found"

| | Reality |
|---|---|
| A | No such email exists |
| B | It exists but was never indexed |
| C | It exists, was indexed, but the query missed it |
| D | It exists but entity resolution failed |
| E | It exists but L1 filtered it |

Today these are **indistinguishable downstream**. A, B and E are separable with data L1 already
has (the denominator, and the drop ledger). C and D belong to L2 and the query layer, and this
step must at least stop **claiming** them.

## 2. Current status

| Field | On QES? |
|---|---|
| `coverage_ready` (bool — is a channel connected) | ✅ |
| `evidence_coverage` | ❌ |
| `source_coverage` | ❌ |
| `query_scope` / time window | ❌ |
| retrieval completeness | ❌ |

`coverage_ready` answers *"could a source have carried this?"* — a different and narrower question
than *"how much of what that source holds did we read?"*

## 3. Expected result

A signal that supports a negative claim carries the window and the completeness behind it. The
sentence a founder sees becomes:

```
NO FOLLOW-UP FOUND
  window        2026-08-01 → 2026-09-01
  calendar      42 / 42 indexed
  email         465 / 465 indexed, cursor exhausted
  evidence      none found
```

instead of

```
NO FOLLOW-UP FOUND
```

## 4. Edge cases

| # | Scenario | What must happen |
|---|---|---|
| E1 | The source total is an **estimate** (Gmail's is) | labelled as an estimate on the signal, never as a fact |
| E2 | Coverage is unknown | say `unknown` — **not 100%** |
| E3 | A positive claim | coverage is still carried; it costs nothing and makes replay comparable |
| E4 | Coverage changes after the signal was published | the signal keeps the coverage **as of its own capture** — a later backfill does not retroactively strengthen an old claim |
| E5 | Multi-source signals | coverage per source, not one blended number |
| E6 | Integer basis points | coverage is a ratio → **integer bp at the boundary**, because V-7 rejects floats |

**E4 is the subtle one.** Coverage is a property of the observation moment, not of the tenant.
Storing a live pointer would make yesterday's claim silently change its meaning tonight.

## 5. How to do it

| Unit | What |
|---|---|
| 15-U1 | a coverage block on C-12: window, per-source indexed/total, completeness in **integer bp**, `estimated` flag |
| 15-U2 | the publisher fills it from step 5's completeness rows, **as of capture** |
| 15-U3 | `unknown` is representable and is the default |
| 15-U4 | the migration + the widened projection carry it (step 3's pattern) |
| 15-U5 | a test that a negative-shaped signal without coverage **cannot** be published |

## 6. Test cases

T1 a signal carries its window and completeness (RED today) · T2 unknown coverage is `unknown`,
never 100% · T3 an estimated total is labelled · T4 a later backfill does **not** change an old
signal's coverage · T5 no float reaches storage · T6 per-source breakdown survives for a
multi-source signal.

## 7. Verify

```bash
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
uv run --no-sync pytest tests/capture/coverage -q -p no:randomly
uv run --no-sync pytest tests/test_l2_reads_what_l1_publishes.py -q -p no:randomly
```

## 8. Done criteria

**Ticked 2026-09-24. All five closed — nothing deferred.**

- [x] **the coverage block exists on C-12 and crosses the seam** — `SignalCoverage` on the
      contract, migration **0180**, and the store's INSERT, upsert and parameter map all name it.
      Produced by `_coverage_of(summary)` in the publisher, driven by a test rather than asserted
      on the dataclass.
- [x] **`unknown` is the default and is representable** — `None` on the contract; `claimed_total
      is None` → `completeness_bp is None`, never 10000; and a producer that cannot state a window
      returns **no block at all** rather than a full one. §9's first rule, at three levels.
- [x] **estimates are labelled** — `is_estimate` travels with the number. Gmail's total is
      `resultSizeEstimate` and Google named it that; unlabelled, *"465 of 465"* reads as a count
      somebody could be held to. `indexed > claimed_total` is legal and caps at full, because a
      low estimate happens on perfectly correct sweeps.
- [x] **T4 green — coverage is frozen at capture** — both dataclasses are frozen, AND the block
      holds no org id, no query and no run id, which a test names explicitly. A live pointer would
      be the forbidden behaviour wearing a value's clothes.
- [x] **a negative-shaped signal without coverage cannot publish** — `_a_negative_claim_carries_
      its_proof` on C-12. `broken` is the only negative state; **`unknown` deliberately is not** —
      it asserts nothing, and requiring proof of a non-claim would make the conservative answer
      the expensive one.

### 8.1 · The alignment this step closes

| | |
|---|---|
| **step 5** | built the denominator on the sweep |
| **step 12** | built the rule that `BROKEN` requires coverage ≥ 9000 bp — **with nothing wired in** |
| **step 15** | is that somewhere |

At 8% an overdue promise reads `UNKNOWN`; at 95% it may read `BROKEN`. Nothing about the promise
changed — only what we can prove about having looked. Driven end to end through step 12's real
resolver.

### 8.2 · Two locks, not a duplicate

Step 12 refuses to **resolve** to `broken` below 9000 bp; the contract refuses to **publish** one
with no coverage. Step 12's gate only guards the resolver, and a caller constructing a signal
directly bypasses it entirely. Two locks, because the cost of being wrong is telling a founder they
broke a promise they kept.

## 9. What this step must NOT do

**Do not default coverage to 100%.** That is the exact failure this whole step exists to prevent.
Do not blend multi-source coverage into one number. Do not store a float. Do not let a later
backfill rewrite an old signal's coverage.

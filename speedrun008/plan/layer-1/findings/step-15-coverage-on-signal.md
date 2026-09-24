# Step 15 · Coverage on the signal — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** 15-U1…U5 **ALL DONE** · migration **0180** · nothing deferred

---

## 1. Premise check — every premise confirmed

| Written premise | Verdict |
|---|---|
| `coverage_ready` is the only coverage on QES | ✅ confirmed — and it is a **boolean about channel connectivity** |
| `evidence_coverage` / `source_coverage` / `query_scope` absent | ✅ confirmed |
| Step 5 built the denominator | ✅ `claimed_total` · `claimed_is_estimate` · `cursor_exhausted` · `scanned` |

`coverage_ready`'s own docstring already states what it buys — *"the licence to make a NEGATIVE
inference"* — and then answers a narrower question than the licence requires: **"could a source have
carried this?"** rather than **"how much of what that source holds did we read?"**

Cost check: contracts + publisher + store. Post-extraction, no prompt, no vocabulary.
`vocabulary_fingerprint` = `a3d5496aa0d3`.

---

## 2. ⛔ The alignment — three steps that were one finding

This is the step that closes a loop opened two steps ago:

| | |
|---|---|
| **step 5** | built the denominator **on the sweep** |
| **step 12** | built the rule that `BROKEN` requires coverage ≥ 9000 bp — **with nothing wired in.** `CommitmentFacts.coverage_bp` was an input a caller had to supply from somewhere |
| **step 15** | is that somewhere |

At 8% an overdue promise reads `UNKNOWN`; at 95% it may read `BROKEN`. **Nothing about the promise
changed — only what we can prove about having looked.** Asserted end to end by
`test_the_coverage_figure_feeds_step_twelves_broken_gate`, which drives step 12's real resolver.

---

## 3. What was built

| Unit | What |
|---|---|
| **15-U1** | `SourceCoverage` + `SignalCoverage` — window, per-source indexed/total, completeness in integer bp, `is_estimate` |
| **15-U2** | `_coverage_of(summary)` in the publisher, read off the sweep **as of capture** |
| **15-U3** | `None` is UNKNOWN and is the default, on the contract and at the producer |
| **15-U4** | migration **0180** + the store's INSERT, upsert and parameter map |
| **15-U5** | **a signal in a negative state cannot publish without coverage** |

### 3.1 · The four rules §9 lays down, each as a line of code

| §9 | How |
|---|---|
| *do not default coverage to 100%* | `claimed_total=None` → `completeness_bp` is **`None`**, and `is_unknown` is True. A producer that cannot state a window returns no block at all rather than a full one |
| *do not blend multi-source coverage* | `SignalCoverage` has **no** `completeness_bp` — only `for_source()`. A test asserts the blended property does not exist, because adding one would grant the calendar's licence to the mailbox |
| *do not store a float* | integer bp throughout, truncated; a round-trip test walks the serialised block |
| *do not let a backfill rewrite an old signal's coverage* | §3.2 |

### 3.2 · E4, and the mechanism rather than the intention

> Coverage is a property of the **observation moment**, not of the tenant.

A signal that said *"no follow-up found, 8% of the window indexed"* keeps saying 8% after a backfill
takes the tenant to 100%. **The claim was made with 8% of the evidence and its strength has not
changed** — only our ability to make a NEW and better claim has.

Two things enforce it, and neither is a convention:

* both dataclasses are **frozen**, so a later pass cannot mutate a published block;
* the block holds **no org id, no query, no run id** — a test names those explicitly. There is
  nothing in it that could resolve against today's numbers when read tomorrow. A live pointer would
  be exactly the forbidden behaviour wearing a value's clothes.

### 3.3 · 15-U5 — two locks on the same door

Step 12 refuses to **resolve** to `broken` below 9000 bp. The contract now refuses to **publish**
one with no coverage at all.

They are not duplicates. Step 12's gate acts on the figure it is handed and a caller that hands it
nothing gets `unknown` — good, but it only guards the resolver, and **a caller constructing a
`QualifiedEnterpriseSignal` directly bypasses it entirely.**

Two locks, because the cost of being wrong is telling a founder they broke a promise they kept.

**`unknown` is deliberately NOT a negative state.** It asserts nothing, it is the honest answer when
we could not tell, and requiring proof of a non-claim would make the conservative answer the
expensive one — which is precisely how a system learns to say `broken` instead.

---

## 4. The five realities, and what this step can honestly separate

| | Reality | Separable? |
|---|---|---|
| A | no such email exists | ✅ with the denominator |
| B | it exists but was never indexed | ✅ **this step** |
| C | indexed, but the query missed it | ❌ L2's |
| D | indexed, but entity resolution failed | ❌ L2's |
| E | L1 filtered it | ✅ the drop ledger already records it |

**C and D are not ours, and the step's own §1 says this must at least stop CLAIMING them.** It does:
the block states what was INDEXED, and never that a query over it was complete. A signal saying
*"465 of 465 indexed"* makes no assertion about whether the right query ran.

---

## 5. Test result

```
FULL SUITE      12719 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 15: 12695 passed · 14 failed
```

**Zero regressions, +24 tests.** Migration 0180 · no model call · no re-extraction · no prompt
change.

---

## 6. What this step does NOT do

* **It does not make coverage complete.** It makes it **stated**. A tenant reading 8% still reads
  8% — the difference is that the claim now says so.
* **It does not backfill old signals.** Every signal published before this carries `null`, which
  reads as `unknown`, which is true.
* **It does not render the coverage table.** The block is on the signal; the sentence a founder
  sees is Layer 5's.
* **It does not measure anything on real data.** The producer reads from a live sweep, and the
  figures come with the corpus — Harsh's.

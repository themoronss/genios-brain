# Step 7 · Intent split and the silent predicates — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** 7-U1′ · U2 · U3 · U4′ · U6 **DONE** · 7-U5 **nothing to retire** ·
7-U1 (the split) **NOT DONE, deliberately — it costs a third re-extraction**

---

## 1. Premise check — one unit already done, one unit's goal REFUSED by the contract, and a bill

| Written premise / unit | Verdict |
|---|---|
| 7-U6 · *"pin `len(SignalType)` in a test"* | ✅ **ALREADY DONE** — pinned at 16 in three tests |
| 7-U6 · *"correct the 14-member prose"* | ❌ **confirmed open** — still says fourteen in **4 places** |
| 7-U1 · *"intent as its own contract"* | ⚠️ **ALREADY TRUE** — `MessageIntent` is its own contract with its own closed enums |
| 7-U1 · *"intent as its own CALL"* | ⛔ **costs a full re-extraction** — see §2 |
| Done criterion · *"intent has … evidence"* | ❌ **the contract REFUSES this, with a good argument** — see §3 |
| 7-U4/U5 · *"four types have never fired"* | ⚠️ **half wrong** — all four have detector tests proving the predicate CAN fire |
| 7-U2 · disagreement is folded by `merged_with` | ✅ confirmed |
| 7-U3 · `unknown` rate uncounted | ✅ confirmed |

> **Sixth step in a row whose written premises the code corrected**, and the first where a done
> criterion asks for something the codebase has already argued against in writing.

---

## 2. ⛔ THE COST CHECK — 7-U1 would be the THIRD full re-extraction

```python
# capture/semantic/vocabulary.py
_SETS = MappingProxyType({
    "intent": INTENT,        # ← IN the fingerprint
    ...
})
```

`intent` is a closed set inside `_SETS`, `_SETS` feeds `vocabulary_fingerprint()`, and that digest
is a component of the `l1_extraction_results` cache key.

> **Taking intent out of LLM-2's prompt moves the fingerprint and re-extracts the entire corpus.**
> Step 4 already incurred one such bill (`151b9dabf235 → a3d5496aa0d3`) and it is still unpriced.
> A second one, for attributability rather than for a correctness fix, is a much weaker case.

And it is not a one-off cost: a separate intent call is **another model call on every message,
forever** — where step 6's proposer at least skips anything under 80 characters.

### 2.1 · The cheaper reading of the same goal

The stated purpose of 7-U1 is *"when the answer is wrong you cannot distinguish 'intent was wrong'
from 'the whole extraction was wrong'."* That is a question about **attribution**, and splitting the
call is only one way to get it.

`MessageIntent` already has `observed_anything` — a derived property saying whether the reader
learned anything at all. **A confidence derived from what the model already returns needs no prompt
change, no new call, and no re-extraction** — and it is *more* correct by doctrine 1, because a
model's self-reported certainty must never become a stored score.

**Recommended shape:** derive intent confidence from the axes actually answered, record the
disagreement (7-U2) and the unknown rate (7-U3), and **do not split the call.** The split is
recorded as an option with its price, for Harsh.

---

## 3. The done criterion the contract refuses — and it is right

> *"intent has its own contract, confidence and **evidence**"*

`contracts/intent.py` argues against the evidence half explicitly:

> **NO `evidence` FIELD, DELIBERATELY.** *Every other claim in `contracts/extraction` carries spans
> because every other claim is about a PHRASE — a commitment, an amount, a date — and a reader
> must be able to see the words. Intent is not that shape: it is one reading of the WHOLE message,
> and "the tone is warm" or "a person composed this" have no quotable span to point at. A field for
> them would invite a model to manufacture a citation for something that is not a quotation, which
> is worse than having none.*

That reasoning is correct and it agrees with §9 of the step itself: *"Do not rebuild the
observation-vs-judgement split — it is correct."*

**So the criterion is amended, not met:** intent gets a **confidence**, and does **not** get
evidence. Manufacturing a span for "the tone is warm" is the fabricated-receipt failure this whole
architecture exists to prevent.

---

## 4. The four "silent" types — the premise is half right, and the half that is wrong matters

> *"Nothing says whether the tenant had none, or whether the predicate cannot fire."*

Something does. Every one of the four has detector tests that fire it:

| Type | Detector tests referencing it |
|---|---|
| `ESCALATION` | 3 |
| `INFORMATION_CONFLICT` | 3 |
| `ANOMALY` | 2 |
| `AVAILABILITY_CHANGE` | 1 |

**So the predicates CAN fire, and 7-U5 (*"retire any type no fixture can fire"*) retires nothing —
every one of the four already has its fixture.** What is unknown is why they never fired *in
production*, which is a corpus question, not a code one.

`DELIVERY_FAILURE` (member 16, added in step 2) has 19 tests of its own and has also never fired in
production, for a reason we know exactly: **migration 0176 is not applied**, so the insert would be
refused by a CHECK constraint.

> **The real 7-U4 is therefore not "make them fire" but "make the difference between *the tenant
> had none* and *the predicate is unreachable* visible in a report."** That is what the step's own
> §1 asks for and what neither the tests nor the ledger answer today.

---

## 5. What is genuinely left

| Unit | Status |
|---|---|
| **7-U6a** · prose says fourteen in 4 places | **OPEN** — cheapest real fix in the step |
| **7-U1′** · a DERIVED intent confidence, no prompt change | **OPEN** — replaces the split |
| **7-U2** · record the intent↔extraction disagreement instead of folding it | **OPEN** |
| **7-U3** · `unknown` rate per source | **OPEN** |
| **7-U4′** · report *never fired* vs *cannot fire*, per type | **OPEN**, reshaped |
| 7-U5 · retire an unfireable type | **NOTHING TO RETIRE** — all 16 have fixtures |
| 7-U6b · pin `len(SignalType)` | **ALREADY DONE** (3 tests) |
| 7-U1 · split the model call | **NOT DOING IT** — §2. Recorded as a priced option for Harsh |


---

## 6. What was built

### 6.1 · 7-U6a — the stale taxonomy prose, fixed so it cannot expire again

Five sites in `esqe/` still described a **fourteen**-member taxonomy. It has been sixteen since
step 2, and it was fifteen before that (migration 0139's `availability_change`).

**Fixed by removing the counts, not by updating them.** *"TOTAL over the 14 members"* became
*"TOTAL over every `SignalType` member"*; *"the closed 14-member taxonomy"* became *"the closed
`SignalType` taxonomy"*. A prose count over a closed set is a comment with an expiry date, and this
one had already expired twice.

The guard is **scoped**, deliberately: `validate/dates.py` has a number-word table containing
`"fourteen"` and a legitimate *"fourteen-day window"*, `reason/retention.py` says *"roughly fourteen
rows on this tenant"*, and `contracts/conflict.py` says *"ALG-14 table has seven rows"*. All three
are true and none is about this taxonomy. **A guard that cries wolf is a guard somebody deletes
rather than obeys**, so it only looks at modules that name `SignalType`.

### 6.2 · 7-U1′ — a DERIVED intent confidence

`MessageIntent.confidence_bp` counts the seven OBSERVED axes that were actually answered.
`engagement` is excluded: it is the judged half, derived from the others, and counting it would let
one reading vote twice on how much of the message was read.

**Derived and never asked for, forced by two rules that happen to agree:**

| | |
|---|---|
| Doctrine 1 | a model may DESCRIBE, never SCORE. Its self-reported certainty must not become a stored confidence |
| The cost check | asking for it changes LLM-2's prompt → moves `vocabulary_fingerprint` → **a third full re-extraction** |

It measures the COMPLETENESS of the reading, not the probability it is right — and that is exactly
what the step asked for: *"intent read nothing here"* is now distinguishable from *"the whole
extraction failed"*.

### 6.3 · 7-U2 — the disagreement, recorded

`MessageIntent.disagreements_with` plus `EsqeOutcome.intent_disagreements`, computed **before** the
fold — because `merged_with` is what destroys the evidence, so a disagreement computed after it is
always empty. There is a source-level test on that ordering, since it is invisible in the output.

**An absence is never a disagreement.** `merged_with` already says why: *"a `None` or an `unknown`
from the fuller read is an ABSENCE, not a correction."* Counting silence would flag most of the
corpus and train every reader to ignore the number.

**Reported, never resolved.** The merge rule is untouched; the fuller reading still wins.

### 6.4 · 7-U3 — the `unknown` rate, per source

`capture/intent_rate.py` (pure) plus three counters on `SyncSummary`, incremented **on the capture
loop**, with `intent_unknown_rate_bp` derived from them.

An event that never reached S4 — a structured bypass, a parked extraction — is in **neither**
counter. Counting it as unreadable blames the reader for messages nobody handed it; counting it as
read hides a real degradation behind events that were never candidates.

`intent_disagreements` sits beside `intent_unread` for a reason: **a rising disagreement count with
a flat unread count is a prompt that changed its mind, not one that went quiet** — and the two need
different fixes.

---

## 7. What was NOT built, and why

### 7.1 · 7-U1 — the model-call split. Priced and declined.

Removing intent from LLM-2's prompt moves `vocabulary_fingerprint` and re-extracts the whole
corpus — a **third** full bill, after step 4's (still unpriced) — plus a second model call on every
message forever, where step 6's proposer at least skips anything under 80 characters.

The stated purpose was attribution, and §6.2 delivers attribution for nothing. **The split is
recorded as a priced option for Harsh, not taken.**

### 7.2 · The done criterion asking for intent EVIDENCE — amended, not met

`contracts/intent.py` argues against it in writing and is right: *"'the tone is warm' or 'a person
composed this' have no quotable span to point at. A field for them would invite a model to
manufacture a citation for something that is not a quotation."* That is the fabricated-receipt
failure this architecture exists to prevent, and §9 of the step itself says the
observation-vs-judgement design is correct and must not be rebuilt.

A regression guard now asserts intent has **no** evidence field.

### 7.3 · 7-U5 — nothing to retire

All sixteen members have a test that fires them. The four "silent" types are a **corpus** fact, not
a code fault. `test_every_signal_type_has_a_fixture_that_fires_it` keeps that answerable from the
repo instead of re-derived by whoever asks next.

---

## 8. Test result

```
FULL SUITE      12549 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 7:  12530 passed · 14 failed
```

**Zero regressions, +19 tests.** 10 of the 18 in this step's own file were RED first, for the
intended reason.

**No migration. No new model call. No re-extraction** — `vocabulary_fingerprint()` still prints
`a3d5496aa0d3`, unchanged since step 4.

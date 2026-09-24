# Step 10 · `REVIEW` as a fourth outcome — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** **10-U0 BUILT · 10-U1…U4 DELIBERATELY NOT BUILT** — the step's own gate is unrun, and
its routing rule as written is unbuildable

---

## 1. The step gated itself, and I honoured the gate

§5's first unit and §8's first criterion both say the same thing:

> *"**MEASURE FIRST.** Replay the pilot's 68 floor-refused signals and count how many would become
> REVIEW. **68 or 0 both mean the thresholds are wrong** — and 0 means the step is not needed yet."*
>
> *"U0's measured count is in `STATUS.md` **before** any code was written."*

**The 68 is from the tenant re-synced away on 19 September.** So the count cannot be taken from
here, and building the outcome, the queue and the drain ahead of it would be exactly the mistake
this plan exists to prevent — with the step's own text as the witness.

Three independent reasons not to build U1–U4 today, and each stands alone:

1. **the measurement can cancel them** (§5);
2. **E1 forbids a partial ship** — *"a REVIEW with no drain is a slower drop — the queue and its
   drain ship in the same change"*, so U1–U4 are one unit or none;
3. **the routing rule as written cannot be built at all** — §3.

---

## 2. Premise check

| Written premise | Verdict |
|---|---|
| `PublicationOutcome` is closed at three | ✅ confirmed, and its docstring forbids a fourth at a call site in writing |
| The floor has **three** "travel anyway" overrides | ⚠️ **it has five** — `availability_change` and `delivery_failure` (step 2) joined `conflict`, `internal_kind` and `unscored` |
| `PARK` means *"blocked on something mechanical"*, not *"a person should look"* | ✅ confirmed |
| Thresholds must be rows with owners (E3) | ✅ **already has a home** — `org_qualification_floors` + `qualification_floor_changes`, with an owner and an append-only log |
| E5 · *"every reader of the enum must be found"* | ✅ tractable — **10 modules** reference it |
| 10-U2 · *"low confidence + high importance → REVIEW"* | ⛔ **UNBUILDABLE AS WRITTEN** — §3 |

> The "three overrides" count being stale does not weaken the step's argument — it strengthens it.
> *Uncertain ≠ drop* is **more** established than the plan assumed.

---

## 3. ⛔ The routing rule reads a value that does not exist yet

`finalize.py` fixes the order, and it is load-bearing:

```
conflicts  →  QUALIFY  →  lifecycle  →  PUBLISH
```

ALG-13 composes confidence inside `publisher.py`, which runs at **publish** — *after* qualify.

> **At the moment the floor refuses a signal, its confidence has not been computed.**

`qualification_drops` has no confidence column because there is nothing yet to put in one:

```
org_id · drop_id · signal_id · event_id · signal_type · predicate · subject_key
importance_bp · importance_version · floor_bp · components · payload_ref
```

Two ways out:

| | |
|---|---|
| move composition ahead of qualification | a pipeline reordering with real risk — for a step whose own measurement might cancel it |
| **route on what the drop point CAN see** | `importance_bp`, `floor_bp`, `components` — and **step 8 put `achievable_ceiling_bp` in exactly that reach** |

### 3.1 · And the second rule is better anyway

On a cold-start tenant *"high value"* cannot mean a high absolute score. Step 8 measured the whole
tenant topping out at **4,640 of 10,000** because the money term was unearnable.

> A signal at **2,400 against a ceiling of 3,000** is near-maximal for what it could ever have
> earned — and an absolute floor of 2,500 refuses it.

That population already has a name. Step 4 measured `relationship_change`: **published 4, dropped
54, band 880–1560** — *a type whose ceiling sits below the floor*. It is precisely what *"low
confidence but high value"* was reaching for, and step 8 is what made it expressible.

**Steps 4 → 8 → 10 turn out to be one finding seen three times.**

---

## 4. What was built — 10-U0, and only that

`capture/esqe/review_candidates.py`. **It routes nothing, stores nothing and changes no outcome.**

| | |
|---|---|
| `is_review_candidate` | refused **and** ceiling known **and** within `NEAR_CEILING_BP` of that ceiling |
| `measure_review_population` | refusals · candidates · unassessable · share · **per-type breakdown** |
| `thresholds_are_wrong` | **the step's gate as a property** — true when candidates are 0 **or** all of them |

Pure: no clock, no I/O, no model — so the same code answers a fixture here and a tenant in
production. A measurement that exists only as SQL in a runbook is a measurement nobody can test,
and this step's entire gate rests on its answer.

### 4.1 · The line that decides whether the measurement can lie

```python
#: None is NEVER coerced to a full scale
```

Every refusal written before step 8 has no `achievable_ceiling_bp`. Reading a missing ceiling as
10,000 would make each one look far below its limit and report a confident **zero candidates** — a
measurement concluding *"the step is not needed"* because it could not see. They are counted as
`unassessable` and reported beside the totals, so the honest headline can be *"we could not assess
900 of 1000"* rather than *"3% qualify"*.

### 4.2 · Why the per-type breakdown is not decoration

If one type dominates the population, **the answer is not a review queue at all** — it is that
type's floor, which is step 8's deferred 8-U3. A total with no breakdown cannot tell a systemic
floor problem from a scattered handful of genuinely borderline signals, and those two findings have
opposite fixes.

---

## 5. Guards held

| | |
|---|---|
| `PublicationOutcome` | **still closed at three.** §9: *"do not add the outcome at a call site"* — and adding it before its measurement is the same mistake one step earlier |
| The five floor overrides | untouched |
| `vocabulary_fingerprint` | `a3d5496aa0d3` — qualification is post-extraction and deterministic; no prompt, no cost |

---

## 5b. Test result

```
FULL SUITE      12611 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 10: 12598 passed · 14 failed
```

**Zero regressions, +13 tests.** 11 were RED first. **Nothing shipped**: no migration, no contract
change, no routing, no cost.

---

## 6. What happens next, and who unblocks it

**One query.** Run `measure_review_population` over the live `qualification_drops` and read three
numbers: `candidates`, `unassessable`, `by_type`.

| Result | What it means | What we do |
|---|---|---|
| `candidates == 0` | no population | **the step waits.** §5 says so in as many words |
| `candidates == refusals` | the threshold discriminates nothing | tune `NEAR_CEILING_BP`, re-run |
| one type dominates | a **floor** problem, not a review problem | do **8-U3** instead |
| a real scattered share | the step is justified | build U1–U4 **together**, with the drain (E1) |

Until then `PublicationOutcome` stays closed at three, which is what its own docstring demands.

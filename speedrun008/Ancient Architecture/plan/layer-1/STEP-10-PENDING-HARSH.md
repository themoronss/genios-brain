# Step 10 — PENDING · owner: Harsh

> **Status:** **10-U0 built · U1–U4 deliberately NOT built** · no migration, no cost, nothing shipped
> **What it is:** the step gated itself on a measurement, and the measurement needs your corpus.
> **Written:** 2026-09-24 · **Evidence:** [`findings/step-10-review-outcome.md`](findings/step-10-review-outcome.md)

---

## 1. TL;DR — what you have to do

| # | Action | Blocking? | Time |
|---|---|---|---|
| **1** | **Run one measurement (§3)** — it decides whether this step should exist at all | **YES — it is the whole step** | 10 min |
| **2** | Nothing else. **Nothing was shipped.** No migration, no contract change, no cost. | — | — |

---

## 2. Why nothing was built, and why that is the correct outcome

The step gates itself. Its own §5 and §8:

> *"**MEASURE FIRST.** Replay the pilot's 68 floor-refused signals and count how many would become
> REVIEW. **68 or 0 both mean the thresholds are wrong** — and 0 means the step is not needed yet."*
>
> *"U0's measured count is in `STATUS.md` **before** any code was written."*

**The 68 is from the tenant re-synced away on 19 September.** Three independent reasons not to build
the rest today, each standing alone:

1. **the measurement can cancel it** — §5 says so;
2. **E1 forbids a partial ship** — *"a REVIEW with no drain is a slower drop"*, so the outcome, the
   queue and the drain are one change or none;
3. **the routing rule as written cannot be built at all** — §4.

`PublicationOutcome` is therefore still closed at three, which is what its own docstring demands:
*"a fourth outcome invented at a call site would be an emit nobody reviewed."*

---

## 3. ⭐ The measurement — this is the whole ask

I built U0 as a **pure function**, not a script, so the same code that passes 13 tests here is the
code that answers your corpus:

```python
from genios_engine.capture.esqe.review_candidates import measure_review_population

# rows = every qualification_drops record for the org, as dicts with:
#   signal_type · importance_bp · floor_bp · achievable_ceiling_bp
report = measure_review_population(rows)

print(report.refusals, report.candidates, report.unassessable)
print(report.share_bp, report.by_type, report.thresholds_are_wrong)
```

```sql
select signal_type, importance_bp, floor_bp,
       (components ->> 'achievable_ceiling_bp')::int as achievable_ceiling_bp
from qualification_drops
where org_id = '<pilot org>';
```

> **`achievable_ceiling_bp` will be NULL on every row written before step 8 ships.** That is
> expected and handled: those rows count as `unassessable` and are reported separately, never
> folded into the total. If `unassessable` is most of the corpus, the honest answer is *"we cannot
> tell yet"* — **not** *"no candidates"*. A measurement that coerced a missing ceiling to full
> scale would report a confident zero and cancel the step for the wrong reason.

### 3.1 · What each answer means — and one of them cancels the step

| Result | Meaning | What we do |
|---|---|---|
| `candidates == 0` | no population | **the step waits.** §5 says so in as many words |
| `candidates == refusals` | the rule discriminates nothing — it has renamed the drop ledger | tune the threshold, re-run |
| **one type dominates `by_type`** | a **FLOOR** problem, not a review problem | do **8-U3** instead — see §5 |
| a real scattered share | the step is justified | build U1–U4 **together**, with the drain |

---

## 4. The premise correction — the routing rule reads a value that does not exist

10-U2 says *"low confidence + high importance → REVIEW"*. `finalize.py` fixes the order:

```
conflicts  →  QUALIFY  →  lifecycle  →  PUBLISH
```

ALG-13 composes confidence inside `publisher.py`, at **publish** — after qualify.

> **At the moment the floor refuses a signal, its confidence has not been computed.**
> `qualification_drops` has no confidence column because there is nothing yet to put in one.

So the rule routes on what the drop point **can** see, and step 8 put the right value there:
`achievable_ceiling_bp`. On a cold-start tenant *"high value"* cannot mean a high absolute score —
step 8 measured the whole tenant topping out at 4,640 of 10,000 with the money term unearnable.

**A signal at 2,400 against a ceiling of 3,000 is near-maximal for what it could ever have earned,
and an absolute floor of 2,500 refuses it.**

---

## 5. The thing worth noticing across three steps

| Step | What it found |
|---|---|
| **4** | `relationship_change` — published 4, **dropped 54**, band 880–1560. Its ceiling sits *below* the floor. Typing the lane could not fix it |
| **8** | *why* — the money term is 30% of the scale and unearnable on this tenant, so `achievable_ceiling_bp` exists to say so |
| **10** | the population *"low confidence but high value"* was reaching for **is that same set**, and step 8 is what made it measurable |

**Steps 4 → 8 → 10 are one finding seen three times.** If §3's `by_type` shows one type dominating,
the answer is not a review queue — it is **8-U3, a floor relative to the tenant's distribution**,
which is already deferred and waiting for the same corpus.

---

## 6. How to cross-check me

```bash
.venv/bin/python -m pytest tests/capture/esqe/test_a_refusal_can_be_worth_a_second_look.py -q
```
**Expect:** `13 passed`. 11 were RED first.

```bash
.venv/bin/python -c "
from genios_engine.contracts.publication import PublicationOutcome
print([o.value for o in PublicationOutcome])"
```
**Must print exactly `['emit', 'park', 'reject']`.** If a fourth appeared, this step shipped
something before its own measurement said it should.

```bash
.venv/bin/python -m pytest tests -q -p no:randomly
```
**Expect:** `12611 passed · 14 failed`. All 14 pre-existing.

---

## 7. What this step does NOT do

* **It ships no behaviour change of any kind.** No outcome, no queue, no drain, no routing.
* **It does not set a threshold.** `NEAR_CEILING_BP = 8000` is documented as a starting point for
  the measurement. The shipped threshold would be a per-tenant row with an owner (E3) — and
  `org_qualification_floors` already has exactly that shape.
* **It does not move confidence earlier in the pipeline.** §4 — that is a reordering with real
  risk, and it is not justified by a step whose measurement is unrun.

---

## 8. Send back to me

| # | Item | Your answer |
|---|---|---|
| 1 | §3 — `refusals` / `candidates` / `unassessable` | |
| 2 | §3 — `by_type`: does one type dominate? | |
| 3 | §3 — `thresholds_are_wrong`: true or false? | |
| 4 | §6 — did `PublicationOutcome` still print three values? | |

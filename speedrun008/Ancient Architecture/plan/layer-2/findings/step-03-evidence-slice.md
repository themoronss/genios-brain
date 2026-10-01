# L2-3 · The evidence slice — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · **no migration · no model call**
**Against:** `speedrun008` @ `db3e2c87`
**Result:** 19 tests, **12,976 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. ⛔ Premise — the step file contradicts itself, and §0 wins

| | |
|---|---|
| **§0**, written later by the re-analysis | *"This step **extends the existing builder for a new consumer**, and does not write a second one. A second slice builder would be a second answer to 'what may this reader see', which is the visibility defect waiting to happen."* |
| **§4**, written first | *"It does not replace `SituationContextSlice`… **This is a sibling with a different consumer.**"* |

**§0 is right, and L2-1 just paid the bill for the alternative.** Two classes sharing one job left
fifteen parameters across the Domain Expertise compiler annotated with the wrong one of them. A
second slice type would be that again — on the field that decides **who may read what**.

Settled as a build failure rather than a paragraph:
`test_there_is_exactly_one_slice_type_and_one_builder`.

---

## 2. ⛔ Four of the five completion criteria were ALREADY TRUE, and nothing was watching them

This is L2-0's finding in a different place. The properties hold; no test would have noticed them
stopping.

| # | criterion | measured |
|---|---|---|
| 2 | frozen, carrying `graph_version` + `evaluation_time` | ✅ `SituationContextSlice` is frozen and carries both, plus `selector_version` |
| 3 | one bounded read | ✅ **stronger than asked.** `build_context_slice` does **zero I/O** — facts, observations and neighbours all *arrive as arguments*, so it cannot N+1 because it cannot query. And `_bulk_load_facts` / `_bulk_load_obs` are **one org-wide query each** |
| 4 | visibility through the existing rule | ✅ and **the rule names this consumer in its own docstring** |
| 5 | recorded with the situation | ⛔ **HALF.** §4 below |

### 2.1 · The visibility rule already names the slice

`reason/runner._org_visible_clause`:

> *"ORG-LEVEL RULE AND SIGNAL EVALUATION NEVER READS A SEAT'S PRIVATE FACT (§3.4). A stance
> learned from seat 1's screen may inform seat 1's own query and entity 360 — never a team rule,
> a signal, **a situation slice** or a card."*

So U3's premise — *"a slice assembled for the org and handed to a reasoner acting for a seat is a
visibility leak through a new door"* — **describes a door that is already shut, upstream, at the
read.** Both fact loaders apply the clause; both are now guarded, because dropping it from one
leaves the other looking correct.

---

## 3. ⛔ THE MEASUREMENT — the slice's cost advantage is not structural

U0 asked for the number L2-5's cost check rests on. Measured through the **real builder**:

| facts / obs / neighbours | tokens |
|---|---|
| 3 / 2 / 1 | **326** |
| 8 / 6 / 4 | **714** ← §2's *"900-token slice"* |
| 15 / 12 / 9 | 1,279 |
| 30 / 25 / 20 | 2,509 |
| 60 / 50 / 40 | 4,934 |
| 100 / 80 / 60 | **8,049** ← §2's *"10,000-token thread"* |

§2 claims *"the difference between a 10,000-token thread and a 900-token slice is the whole
bill."*

⛔ **It holds for a small node and stops holding for a busy one.** An anchor with a hundred facts
produces a slice that costs as much as the thread it was meant to replace. **The saving comes from
the node being small, not from the slice being a slice** — and the busiest accounts are exactly
the ones a founder most wants reasoned about.

### 3.1 · So the number became a budget rather than a figure in a file

`SLICE_TOKEN_BUDGET = 2000`, sitting just above the 30-fact shape — a well-populated account with
its neighbours — and well below the shape that costs as much as a raw thread.

**It reports and never truncates.** *Dropping facts to hit a number is how a reasoner concludes
from evidence nobody chose to remove.* And it names both numbers, because *"too big"* is
unactionable while *"8,049 against a budget of 2,000"* is a decision.

### 3.2 · What still needs the pilot

p50/p90 **on real candidates** — the shapes above are driven through the real builder with
constructed inputs. `scripts/slice_weight.py` runs read-only against the pilot and prints exactly
this table. **Harsh item 25.**

---

## 4. ⛔ Criterion 5 is half true, and the missing half is the one U4 asked for

`expertise_builder.py:114` stores `context_slice_hash` in the package metadata.

**The hash is stored. The slice is not.**

U4's own words: *"So a replay can reconstruct the exact input. Without this, `reasoning_trace`
points at a conclusion whose premises are gone."*

A hash answers *"was this the same slice?"* and **cannot answer *"what was in it?"*** — it is a
fingerprint, not a record. So replay can detect drift and cannot reproduce the input.

**Deferred to L2-5, with its consumer**, on the same reasoning L2-2 used: storing a slice is a
migration plus a write path whose only reader is a reasoner trace that does not exist yet, and
**L2-0's finding was eight things built and never switched on.**

---

## 5. The receipts already travel — inside the facts, not beside them

§2 asks for *"observed facts about its entities, **with evidence refs**"*. Each fact in `facts`
and `neighbor_facts` carries:

```
source_ref_id        the pointer to what it rests on
fact_version_id      which version of the fact
independence_group   "source:gmail" — or "unattributed"
src_count            how many distinct sources agree
```

**One nuance, stated because it matters:** `source_ref_id` is `min(source_ref_id)` — a fact backed
by three sources carries **one** pointer plus `src_count`. So a reader can tell *how many* sources
agreed and can reach *one* of them. That is enough to check a fact and not enough to audit a
disagreement.

---

## 6. ⛔ `SituationContextSlice.evidence` is vestigial, and now it is declared

Measured:

* `build_context_slice` has **no `evidence` parameter**, so no caller can supply one;
* **no consumer reads it** — `context_adapter`, `expertise_builder`, `capability_resolver`,
  `reason/adapters/expertise` and `situation_projection` read twelve other fields between them;
* `to_semantic_dict` **includes it**, so it pins the slice hash at `()` on every slice ever made.

**A field in exactly the state L2-0 spent a step on — except this one is empty by design.**

### 6.1 · And filling it is not free

The slice's own docstring records why:

> *"`context_slice_hash` is carried in the expertise package's metadata, so it feeds the PACKAGE's
> content address… each sweep wrote a fresh ~238 kB row per situation. On the design partner's
> database that reached **4,086 rows and 995 MB — 67% of the whole database** for 127 distinct
> situations — and the project crossed its disk quota into read-only."*

Filling `evidence` moves every slice hash, every package content address and every stored package
row at once. **That is a decision with a measured price, not a tidy-up.**

So it is declared in `context/slice_silence.py`, with a reason and an **ENDS WHEN** — the same
idiom as `DARK_DOMAINS`, `UNROUTED_PATTERN_TYPES` and `SILENT_LANES`, checked in both directions.

### 6.2 · The guard found a second one on its first run

`schema_version` — also never set by the builder, and **correct**: `SITUATION_CONTEXT_VERSION` is
the dataclass default, so the version a slice claims is decided in exactly one place. A builder
that passed it would be a second copy of one constant. **Same reasoning as L1 step 18's
`_conversation` returning `{}` rather than a dict of `None`s.** Declared, with that reason.

---

## 7. Cost check

| | |
|---|---|
| model calls | **none** — no tokeniser either. The estimate is characters over a **declared** divisor, so a reader can check the arithmetic instead of trusting a library |
| migration | none |
| runtime behaviour | **unchanged** — the slice builder is untouched |
| new modules | two, both pure: `slice_weight.py` and `slice_silence.py` |

---

## 8. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | slice weight p50/p90 recorded | ⚠️ **measured through the real builder** and turned into a budget — §3. **p50/p90 on real candidates awaits the pilot** (Harsh 25) |
| 2 | `ReasonerSlice` frozen with both versions | ✅ **already true**, now guarded. §0's *extend, do not duplicate* applied — no second type |
| 3 | one bounded read, proven by a test | ✅ **already true**, proven twice: the builder does zero I/O; the loaders are one org-wide query each |
| 4 | visibility through the existing rule | ✅ **already true**, and the rule names *"a situation slice"* itself. Guarded at both loaders |
| 5 | the slice is persisted with the situation | ⛔ **half.** The hash is stored, the slice is not — deferred to L2-5 with its replay consumer. §4 |

**Three closed, one measured-and-bounded with its pilot half open, one half-true and deferred with
a reason.**

---

## 9. What this step does NOT do

* **It does not build a second slice type.** §1 — and §4 of the step file, which asked for one, is
  overruled by its own §0.
* **It does not fill `evidence`.** §6.1 — a measured price, and a decision, not a tidy-up.
* **It does not truncate anything.** The budget reports. Dropping facts to hit a number is how a
  reasoner concludes from evidence nobody chose to remove.
* **It does not persist the slice.** §4 — with L2-5, its only reader.
* **It does not add prior interpretations to the slice.** They are the fields L2-2 deferred, and
  they travel with their writer.

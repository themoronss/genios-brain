# L2-1 · Name it — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · **no migration · no model call**
**Against:** `speedrun008` @ `535d8770`
**Result:** 13 tests, **12,927 passed · 14 failed (all pre-existing) · 0 regressions**
**`vocabulary_fingerprint`:** `a3d5496aa0d3` — **unchanged**, measured before and after

---

## 1. Premise check — all three named problems were real, and the measurement found a fourth

The plan named three ambiguities. Each held. But **U0 — *"count every import of each and record
which one it resolves to"* — was the unit that mattered**, and what it found is not in the plan.

### 1.1 · The baseline the plan asked for

| | |
|---|---|
| mentions of `BusinessSituationObject` in `genios_engine` | **69** |
| imports resolving to `contracts.domain_expertise` (**v1, candidate**) | **20** |
| imports resolving to `contracts.situation` (**v2, admitted**) | **4** |
| files that CONSTRUCT a v1 in the engine | **2** — `situation_bso`, `situation_publisher` |
| test files that construct a v1 | **7** |

`situation_publisher.py` imports **both**, which is why it is the only file where the ambiguity was
ever visible — and it fixed it for itself, with `as LegacySituation`, at one import line.

---

## 2. ⛔ THE FINDING — the whole Domain Expertise compiler was annotated with the wrong one

`domain_shadow.py:881` is the only production call site:

```python
bso = publication.situation          # PublicationResult.situation -> contracts.situation, v2
package = compiler.compile(bso, context_slice)
```

and `DomainCompiler.compile(situation: BusinessSituationObject)` resolved that annotation to
**`contracts.domain_expertise` — v1, the candidate.**

**Fifteen parameters across eight modules said the same thing:**

```
domain_compiler.DomainCompiler.compile          capability_resolver._pattern_fire
capability_resolver.CapabilityResolver.resolve  expertise_builder.ExpertiseBuilder.build
knowledge_retriever._resolve_variants           knowledge_retriever.retrieve
evidence_aggregator.aggregate                   brain_resolver.resolve
context_adapter.ContextAdapter.__init__         runtime_brains.snapshot  (×3)
runtime_brains._selectors                       runtime_brains._situation_tokens
runtime_brains._build_snapshot
```

The candidate has **16 fields**. The object actually passed has **28**.

### 2.1 · Why nothing caught it, and the reason is itself the finding

The admitted object carries **seven compatibility properties** named for v1 fields —
`importance_bp`, `confidence_bp`, `contested_fields`, `findings`, `semantic_hash`, `domain_hints`,
`brain_subject_keys` — whose own docstring reads *"the v1 field name, as a read."*

`expertise_builder.py:76` does `min(situation.confidence_bp, expert.coverage_bp)` on a field that
exists on **v1 and not on v2**. It works only because of that shim. Remove one property and the
production path raises on the first situation.

⛔ **And `upgrade_situation` had already written the consequence down, in this repository, before
this step:**

> *"every consumer read the v1 compatibility views, **so the typed contract was decorative**"*

That sentence was about seven fields. It was true about the whole seam.

### 2.2 · The test suite proved the same thing from the other side

`tests/packs/compiler/l3_inputs.py` and `tests/test_domain_expertise_compiler.py` **construct v1**
and hand it to the compiler. Production constructs v1 in exactly two files, neither of which feeds
the compiler.

**So the shape the compiler is tested on is a shape production never sends it.** That is this
project's recurring defect — *"a unit built, tested, green — and called by nothing on a real
request path"* — in its type-level form.

### 2.3 · What was changed, and what was not

**One import line per module, eight modules.** The name in every signature body stayed
`BusinessSituationObject`; only where it resolves from moved. **Runtime behaviour is unchanged** —
Python does not enforce annotations, and the object passed is the same object it was yesterday.

What changed is that the seam now **says what it receives**.

---

## 3. The guard caught two more types on its first run

`contracts/situation_stages.py` — the table, checked both directions at import time.

`undeclared_situation_types()` immediately returned **`SituationDecision`** and
**`SituationOutcome`**. Neither is a situation: both are the **gate's answer about** one. Putting
them in `SITUATION_STAGES` would have made the table mean two things at once, so they are in
`NOT_A_STAGE` **with a reason each** — the same declared-silence idiom as `DARK_DOMAINS` and
`UNROUTED_PATTERN_TYPES`.

**A guard that finds something on the run it is written is a guard that was worth writing.**

---

## 4. ⛔ Premise correction — "the second and last file carrying digits" is wrong

The plan's U4 says `docs/LAYER_MAP.md` is *"the second and last file carrying digits. Update it, and
nothing else."*

**Three more carry the old names:**

| file | verdict |
|---|---|
| `docs/architecture/README.md` | **live** — and it already points at `LAYER_MAP.md` as *"the current code today"*, so its own diagram is a stale copy, not a rival authority |
| `docs/architecture/02-context-intelligence.md` | **frozen** — *"Status: Reference — frozen target vision, 2026-08-07"* |
| `docs/architecture/ENGINEERING-CONSTITUTION.md` | **frozen** — amendments are appended, never retyped |

Rewriting a document that declares itself a frozen record of a date would be **editing history
rather than recording it**, which is the opposite of what L2-0 did to `_hollow`'s stale count.

**So the two frozen files are DECLARED, with their reason, in `_FROZEN_BY_DESIGN`**, and a test
holds `LAYERS.py` and `docs/LAYER_MAP.md` to each other. Neutralising the rename turns that test
red — technique 3, applied.

---

## 5. Cost check

| | |
|---|---|
| prompt | unchanged — `capture/semantic/vocabulary.py` mentions `domain_expertise` **zero** times |
| `vocabulary_fingerprint` | **`a3d5496aa0d3`** before and after, measured both times |
| model calls | none |
| migration | none |
| re-extraction | **none** |
| runtime behaviour | **unchanged** — annotations are not enforced; the same object flows |

---

## 6. Completion criteria

| # | criterion | |
|---|---|---|
| 1 | `SituationCandidate` at the definition, alias marked deprecated with a date | ✅ `2026-12-24`, held in `situation_stages.ALIAS_REMOVAL` — **one place**, read by a test |
| 2 | `LAYERS.py` and `docs/LAYER_MAP.md` read Situation Intelligence / Plane D / Plane R | ✅ and the `LAYERS` dict is untouched — the digits stay as an **import rule**, and the docstring now says that is all they are |
| 3 | a guard refuses a third ambiguously-named situation type | ✅ **and it refused two on its first run** |
| 4 | full suite green with zero new failures, fingerprint unchanged | ✅ 12,927 passed · 14 pre-existing · `a3d5496aa0d3` |
| — | **not planned: the 15 wrong annotations** | ✅ corrected, and guarded |

**All four closed. Nothing deferred, nothing owed to Harsh.**

---

## 7. What this step does NOT do

* **It does not rename any file.** `situation_bso.py` and `situation_publisher.py` keep their
  names. Renaming a working file to match a doc is churn, and the doc was what was wrong.
* **It does not change the topology.** `LAYERS` keeps its dict and `test_layer_topology.py` is
  untouched and green.
* **It does not remove the old name.** One release, with a date.
* **It does not convert the 7 test files that construct a v1 candidate.** They are not wrong —
  a candidate is a real object with a real producer. What is wrong is that **no compiler test
  exercises what production sends**, and closing that is a test-realism unit, not a rename.
  Recorded here rather than folded in silently.
* **It does not touch the two frozen architecture documents.** §4.

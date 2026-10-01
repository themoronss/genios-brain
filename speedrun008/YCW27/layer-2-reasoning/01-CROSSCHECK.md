# L2 · cross-check — what is actually true in `reason/` + `packs/`

**Written for:** Harsh (CTO) and Rohit. **Date:** 2026-09-30. **No code written yet.**

`reason/` — 118 files, 40,065 lines. `packs/` — 34 files, 7,957 lines. **48,022 lines total**, the
second-largest surface in the product after `context/`.

> ⛔ **Every number below was measured by running a command, and each is followed by the command or
> the file:line it came from.** Two findings in this programme have already been wrong because I
> counted along the wrong dimension — `no_model_wired` in L1, and the graph-revision guard in L3. The
> rule that came out of those: *a count without its dimension is not a measurement*, and *a guard
> lives with the reader, not the writer.* This pass is written to be checkable, not believed.

---

## 0 · Why L2 is built AFTER L1 and L3, when it is numbered before L3

This is the question that makes the programme look incoherent, so it is answered first.

**The product layer numbers do not follow the data flow.**

```
  data flows:     L1 capture  ──▶  L3 context  ──▶  L2 reason  ──▶  L4 ──▶ L5 ──▶ L6
  we build:       M9          ──▶  M10         ──▶  M11        ──▶  M12 ──▶ M13 ──▶ M14
  Atlas numbers:  1                3                2                4      5      6
```

So the build order is **M9 → M10 → M11**, which reads as **layer 1 → layer 3 → layer 2**. That is not
a mistake and not indecision: it is the data flow, which is what `tree.yaml` records as
`requested_order` and what the programme agreed. **Nothing above can be fed better than the layer
below hands up.** L2 reads through L3's graph and consumes L1's signals; building it first would mean
tuning a reader against a source we were about to change.

⛔ **Consequence to accept:** for the rest of this programme, "next layer" means *next in the data
flow*, never *next number*. When a file says **L2**, it means the reasoning layer. When it says
**M11**, it means the fourth milestone. They are the same work.

---

## 1 · Current architecture — the four parts, measured

| Part | Where | Lines | What it is |
|---|---|---|---|
| Orchestrator | `reason/orchestrator.py`, `plan.py`, `runner.py`, `registry.py`, `engine.py` | — | loads context, selects units, runs them in order, validates, stops |
| **Plane R** | `reason/reasoners/`, `reason/unit.py`, `protocols.py` | — | *how* a professional thinks — domain-free |
| **Plane D** | `packs/` + `Domain Expertise/` YAML | 7,957 + YAML | *what* a professional knows — reviewed, compiled |
| Tools | `reason/baselines.py`, `authority.py`, `evidence.py`, `scoring.py` | — | exact operations on a frozen snapshot |

The single rule between the planes, from the layer README: **an R-Unit applies reasoning ON selected
D-Units, USING the current signal and context** — never the reverse.

### The plan pipeline, as the code actually runs it

```
CapabilityManifest
   │  ReasonerRegistry.topological_order()      ── refuses missing deps, self-deps, cycles
   ▼
ordered specs
   │  _select(ordered, capability, request)     ── drops OPTIONAL units with nothing left to read
   ▼
ordered, skipped
   │  _stage_index → PlannedStep tuple
   ▼
ExecutionPlan
   │  _validate_budget          ── declared latency ceiling
   │  _validate_metric_authorities
   │  validate_capability_sources(capability)   ⛔ validates the MANIFEST, after selection
   │  _validate_fallbacks
   ▼
plan.resolve(plan, registry, capability)        ── every DECLARED unit must be registered
```

---

## 2 · ⛔ Finding 1 · The `03-PROGRAM.md` spec for M11.C1 would be a REGRESSION

This is the most important thing in this document, and it is the reason this cross-check had to
happen before any code.

**What `03-PROGRAM.md:91` says to build:**

> `M11.C1` dependency-complete plans — plan compile **fails** when a scheduled unit declares a source
> no other scheduled unit produces.

**Why that is wrong.** `reason/plan.py:229` documents, at length, that this exact rule was
**deliberately removed** because it destroyed rosters:

> **THE STARVATION RULE IS THE SAME ON BOTH KINDS OF INPUT, AND IT DID NOT USED TO BE.** ... *every*
> declared field had to be absent before a unit was dropped, but *any* dropped dependency dropped its
> dependent. ... `core.tradeoff` declares four evaluative sources, and under the any-rule a single
> unfed one (an expertise that names no money fact, so `core.cost` drops) removed tradeoff, then
> `core.alternative`, then `core.validation` and `core.recommendation` behind it — **six units lost to
> one absent fact, each one receipted, none of them starved.**

The settled rule is: **a unit is dropped when it has NOTHING left to read.** Three of four sources
still reporting is three readings. And the reason it is safe is stated too — *"every unit here already
answers a missing prior with an explicit absent sentinel rather than a zero."*

⛔ **So building M11.C1.U01 as written would re-introduce the six-unit cascade this comment exists to
prevent.** Failing the compile is strictly worse than the any-rule: the any-rule dropped units, this
would refuse the whole plan.

**Verified:** `reason/plan.py:219-264`, read in full.

### What the real gap is, once the false one is removed

Four validations already exist and all of them are thorough:

| Guard | Where | Refuses |
|---|---|---|
| `validate_sources()` | `registry.py:148` | a registered unit whose default `source_units` names an unregistered unit |
| `validate_capability_sources()` | `registry.py:97` | a manifest naming a source it does not declare, does not make a dependency, or that is itself — **three refusals** |
| `validate_capability()` | `registry.py:157` | a declared unit that is not registered; a named source that is not registered |
| `topological_order()` | `registry.py:190` | a missing dependency, a self-dependency, a cycle |

⛔ **The one thing none of them checks:** `validate_capability_sources` is called at
`plan.py:370` — **after** `_select` has dropped units — but it validates the **manifest**, where the
dropped unit is still declared. So:

```
manifest declares A, B, C     B reads a_source = A     ✅ all four guards pass
_select drops A               (this situation cannot feed it)
plan schedules B              B reads A, and A will never run
```

**B stays scheduled — which is correct per the starvation rule — and nothing records that it lost a
source.** Its absent sentinel fires silently.

`SkippedStep` exists and carries `("dependency_not_scheduled", orphaned)` for a unit that WAS
dropped. **There is no receipt for a unit that was KEPT and lost one of its inputs.** Grepped: no
partial-starvation reason exists in the vocabulary.

> This is the same shape as `not_carried` and as L1's coverage doctrine: a reading computed over a
> narrower set of inputs than it declared, reported as if it read them all.

---

## 3 · ⛔ Finding 2 · The "two of `core.risk`'s three plugins are silent" claim is UNVERIFIED

`03-PROGRAM.md:92` calls this *"the live defect"* and M11.C1 is built on it.

**I could not find its source.** Grepped `speedrun008/YCW27/*.md` — the claim appears only in
`03-PROGRAM.md` itself, with no measurement, no query, no file:line behind it.

⛔ **It is therefore not a fact and nothing may be planned on it.** Given this session's record — two
confident findings already wrong — the honest status is **unverified**, and Step 1 of the plan is to
measure it or withdraw it.

⛔ **And it cannot be measured today.** Every production number since **2026-09-25 11:09 UTC** was
taken with the API spend limit refusing all model calls (L1 STEP-04, owner Rohit). A plugin that is
silent because the model never answered looks identical to one silent because its source was dropped.

---

## 4 · Finding 3 · The ConfidenceVector axes — the decision, with its cost measured

| | Axes |
|---|---|
| **Code** | `evidence` · `freshness` · `consistency` · `identity` · `coverage` · `analytic` |
| **Atlas v2** | `evidence` · `frame` · `temporal` · `causal` · `authority` · `coverage` |
| **Overlap** | **2 of 6** — `evidence`, `coverage` |

**Source:** `contracts/situation.py:126` (`CONFIDENCE_AXES`) and `:311` (`ConfidenceVector`).

### ⛔ The code's version is stronger than the Atlas's, in two ways the Atlas does not mention

**1 · `overall_bp` is bounded by the weakest axis composed into it.** The docstring states why:

> Composition is otherwise a machine for manufacturing certainty: several weak axes agreeing is not
> corroboration, and a mean over them produces a number larger than anything it was computed from.

**2 · `composed_from` is STORED, not inferred.** Also stated:

> *"we left freshness out because we could not measure it"* and *"freshness was fine"* are different
> facts that an inferred rule would collapse.

Every axis is nullable, and `None` means *no basis* — never zero. `coverage_bp is None` is
`COVERAGE_UNKNOWN`, which *"must never read as either fully covered or fully absent."*

### The cost of renaming, measured

```
$ for a in evidence_bp freshness_bp consistency_bp identity_bp coverage_bp analytic_bp; do ... done
```

| Axis | code files | test files | migrations |
|---|---|---|---|
| `evidence_bp` | 4 | 7 | 0 |
| `freshness_bp` | 6 | 5 | 0 |
| `consistency_bp` | 2 | 3 | 0 |
| `identity_bp` | 2 | 3 | 0 |
| **`coverage_bp`** | **27** | **22** | 0 |
| `analytic_bp` | 2 | 4 | 0 |

`ConfidenceVector(` construction sites: **3.** `composed_from` references: **28.** Migrations
touching any axis: **0** — the vector is not a column anywhere.

⛔ **The two axes that overlap are the two that are load-bearing.** `coverage_bp` alone is in 27 code
files, and `evidence_bp` in 4 — and both keep their names under either vocabulary. The four the Atlas
would rename are in **2-6 files each**.

**So this is a much smaller decision than the cross-check for L3 assumed — but it is still not mine.**
Renaming `freshness` → `temporal` is a wording change. Renaming `consistency`/`identity` →
`causal`/`authority` is **not a rename, it is a different measurement**: `identity_bp` counts open
merge proposals; "authority" would mean whether the source is entitled to assert the claim. Those are
different questions with different answers.

| Option | What it costs | What it risks |
|---|---|---|
| **A · keep the code's six**, correct the Atlas | one Atlas edit | the Atlas and the product disagree on paper until someone edits it |
| **B · rename the two wording-only axes** (`freshness`→`temporal`), keep the rest | ~11 files | half-aligned vocabulary, which is the worst of both |
| **C · adopt all six Atlas axes** | 2-6 files each, plus **inventing two measurements that do not exist** | ⛔ loses the weakest-link law's basis: an axis nobody can measure named in `composed_from` is refused by the validator, so `causal` and `authority` would be permanently `None` |

⛔ **My recommendation is A**, and the reason is C's risk: the code refuses to compose an axis with no
basis. Adopting `causal` and `authority` before anything can measure them means two of six axes are
`None` forever, and `overall_bp` is then composed from four — which is what the code does today with
six honest names.

**Still Rohit's call.** [open]

---

## 5 · ⛔ Finding 4 · "The five output lanes" collide with three existing vocabularies

`03-PROGRAM.md:93` says M11.C2 is *"the five output lanes, and the router that chooses one
deterministically."* Atlas v2 names them: **decision · investigation · conflict · monitor · suppress**.

**Measured:**

| Token | Hits in `genios_engine/` |
|---|---|
| `"decision"` | 43 |
| `"investigation"` | **0** |
| `"conflict"` | 22 |
| `"monitor"` | 8 |
| `"suppress"` | 7 |
| `OUTPUT_LANE` | **0** |
| `LANES =` | **0** |

So the lane **vocabulary** does not exist. But four of the five words already mean something else, in
three unrelated enums:

| Word | Already means | Where |
|---|---|---|
| `suppress` | a delivery decision, and separately a feedback outcome | `contracts/delivery.py:87`, `contracts/outcomes.py:56` |
| `monitor` | an execution mode — *"observe and wait for a response"* | `contracts/execution.py:131` |
| `conflict` | two sources disagreeing — a **hold reason** in L3 | `context/situation_publisher.py` |
| `lane` | ⛔ **a PACK lane** — compiled vs pack, about whether a card can cite an expert | `reason/uncited_lanes.py` |

⛔ **`reason/uncited_lanes.py` is the dangerous one.** Its "lanes" are about citation capability, not
output kind. A file named `lanes.py` added beside it would be read as the same concept by the next
person, and that file's own docstring explains what such a conflation already cost:
*"Layer 2 lost five readings to exactly that ambiguity."*

### And the five lanes are on a different AXIS from the code's existing outcome vocabulary

`DecisionOutcome` (`contracts/reasoning.py:301`) has **six** members:

```
decision · no_action · defer · insufficient_context · blocked · failed
```

`ReasoningDecision`'s docstring is explicit about why:

> ⛔ **IT IS NOT A DECISION TO ACT.** `outcome` may be `no_action`, `defer`, `insufficient_context`,
> `blocked` or `failed`, and each of those is a real decision that must survive to the surface. **A
> projection that only carries `decision` loses five sixths of the vocabulary.**

| | Question it answers |
|---|---|
| `DecisionOutcome` (built) | **did we reach a decision, and if not, why not** |
| Atlas lanes (missing) | **what kind of output should the human see** |

⛔ **These are orthogonal, not rivals.** A `decision` outcome could belong in the `decision` lane or
the `monitor` lane. An `insufficient_context` outcome is close to `investigation` but not the same —
one is a fact about our inputs, the other an instruction to the reader.

**So the lanes are a genuine addition, not a rename** — and anyone who "aligns" `DecisionOutcome` to
the five lanes destroys five sixths of a vocabulary the code deliberately protects.

---

## 6 · Finding 5 · Genuinely missing, verified by zero hits

| Thing | Hits | Status |
|---|---|---|
| the five pipeline counters — `signals_detected` → `situations_formed` → `capability_resolved` → `decision_emitted` → `card_delivered` | **0 each**, across `genios_engine/` and `migrations/` | ⛔ genuinely missing |
| `SituationSeed` | **0** | ⛔ genuinely missing |
| the five output lanes as a vocabulary | **0** | ⛔ genuinely missing (see §5) |
| a receipt for a KEPT unit that lost a source | **0** | ⛔ genuinely missing (see §2) |

⛔ **The counters matter more than they look.** With no funnel, *"we produced 28 cards"* cannot be
distinguished from *"we produced 28 cards out of 4,000 signals and lost 3,900 at a step nobody can
name."* Every layer in this programme has found at least one defect that a funnel count would have
surfaced years earlier.

---

## 7 · Named test files that do not exist

`tree.yaml`'s M11 units name verify commands for files that are absent:

| Named by | File | Status |
|---|---|---|
| `M11.C1.L-logic.V0.U01` | `tests/reason/test_a_plan_is_dependency_complete.py` | ❌ **MISSING** |
| `M11.C1.L-logic.V1.U02` | `tests/reason/adapters/test_a_skip_names_its_missing_input.py` | ❌ **MISSING** |

Expected — they are the tests the units would create. Recorded so nobody mistakes an unrunnable
command for a passing one. **This is the same defect class L3 found in its own tree rows and fixed.**

⛔ **Also note `tree.yaml` has TWO blocks with `id: M11`** — an older *"The remaining Layer 3 losses"*
and the new *"L2 Reasoning"*. The retired one should have been renumbered. Worth a line in the tree,
not a build unit.

---

## 8 · What is NOT wrong here

| | |
|---|---|
| the registry's four validations | thorough, and each refuses a real class of broken deployment |
| `ReasoningDecision` | ⛔ **IS** the DecisionObject. Settled by `tests/contracts/test_the_decision_object_is_one_object.py`. The Atlas calling it a gap is an Atlas error |
| `DECISION_PROJECTIONS` | the five projections and their single writers are documented **in the contract itself** |
| `CritiqueVerdict` | built — `("proceed", "modify", "hold")`. The Atlas's "targeted second pass" |
| the starvation rule | ⛔ correct, and **must not be reverted** — see §2 |
| `ContextSnapshot`, `ReasoningRequest` | built. Atlas calls them targets |
| Plane R / Plane D separation | holds. The dependency direction is one-way |
| `uncited_lanes.py` | correct, and names a real asymmetry — *not citing is not the same as not reasoning* |

---

## 9 · What M11 actually is, after this cross-check

| Unit as written | Verdict |
|---|---|
| `M11.C1.U01` plan compile fails on an unproduced source | ⛔ **REWRITE.** As specced it is a regression — see §2. The real unit is a **receipt**, not a refusal |
| `M11.C1.U02` a dropped unit leaves a `SkippedStep` naming its missing input | ✅ **already built** — `plan.py:258`. Needs verifying, not building |
| `M11.C2` the five output lanes + router | ✅ stands — genuinely missing, but **must not be merged into `DecisionOutcome`** and **must not be called `lanes`** near `uncited_lanes.py` |
| *(new)* the five pipeline counters | ⛔ add — nothing can be diagnosed without them |
| *(new)* the `core.risk` claim | measure it or withdraw it, **before** planning on it |

---

## 10 · The one thing to carry into the plan

⛔ **Two of the four things `03-PROGRAM.md` tells us to build in L2 are wrong**: one would revert a
deliberate design decision, and one is already built. A third rests on an unverified claim.

That is not a reason to distrust the programme — it is what a cross-check is **for**, and it is the
third time in three layers that reading the code before writing any changed what got built. L1's
`no_model_wired`, L3's revision guard, and now L2's starvation rule.

> **The pattern, stated once: this codebase's comments record decisions that the planning documents
> do not. Read the comment before you "fix" the code.**


---

## ⛔ 2026-10-01 · *"No code written yet"* at the top of this file was true on the day it was written

**L2's spine has since been built: STEP-01 to STEP-05 — 4 DONE, 1 RETIRED, plus Plane D (203 tests) and Plane R (59 guard tests).**

This file is a **crosscheck**, so *"no code written yet"* is not an error — it is what a crosscheck
says, and the date beside it is what makes it honest. It is noted here anyway because a reader
scanning for status reads that line as current, and this programme has now paid for that mistake
three separate times: a corpus comment that was true when written sent a whole unit to be specified
before it was withdrawn; seven step files carried `TO BUILD` titles on finished work; and
`02-DECISIONS.md` said *"all four open"* when two were closed.

**Nothing above is retracted.** The findings in this crosscheck are what the build was planned from,
and where one of them turned out to be wrong the retraction is recorded at the point it was found,
not here. For current status read
[`../07-LEDGER-every-step-what-why-how-outcome.md`](../07-LEDGER-every-step-what-why-how-outcome.md)
— or `../../07-LEDGER-...` from a plane folder.

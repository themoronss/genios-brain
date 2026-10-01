# Layer 2 as it actually is — read from the code, 2026-09-24

**Against:** `speedrun008` @ `b8dd3669`
**Purpose:** the honest current state, before the new architecture is planned onto it.
**Companion:** [`00-ARCHITECTURE-MAP.md`](00-ARCHITECTURE-MAP.md) — what the new names cost.

---

## 1. The one sentence that explains Layer 2

`context/angles/__init__.py`, unprompted, in its own first line:

> **"Layer 2 is a rule engine that looks like a model.** Nine of its correlators call none, its
> situation assembly calls none, and of the four model sites in the layer three never execute on a
> sweep. That is the design and it is the right one: **the same graph re-swept tomorrow by a
> different model version produces the same answers**."

And `support_situations` states the price in one line: **"that costs recall, and buys
replayability."**

⛔ **THE NEW ARCHITECTURE SAYS LAYER 2 "WILL BE REASONING VIA LLM". THAT IS A DIRECT REVERSAL OF
THIS TRADE, AND IT HAS TO BE A DECISION RATHER THAN A DRIFT.** §6.

---

## 2. What is actually in there

**111 modules.** Not one of them is dead — the shape is real, not scaffolding.

| | count | what |
|---|---|---|
| **correlators** | 9 | conversation · dependency · domain · history · membership · organization · people · resource · timeline |
| **situation producers** | 7 | analytic · attention · blocker · condition · meeting · outreach · support |
| **boundary** | 2 | `situation_bso.py` (assembles) · `situation_publisher.py` (admits) |
| **graph** | 1 + 9 | `graph_store.py` and its importers |
| **angles** | 4 | the ONLY places a model may be asked anything |

---

## 3. The production path, precisely

```
L1 publishes a QualifiedEnterpriseSignal
   ↓
context/pipeline.process_event(qualified_extraction=…)
   ↓  ⛔ NO MODEL CALL — see §4
   nodes · facts · observations written to the graph
   ↓
9 correlators group them            (deterministic)
   ↓
7 producers turn correlations into situations   (deterministic)
   ↓
situation_bso.build_business_situation()  →  v1  BusinessSituationObject  (16 fields)
   ↓
situation_publisher.decide_publication()
   upgrade_situation()                   →  v2  BusinessSituationObject  (28 fields)
   validate_situation()                      the L2 GATE · eight laws
   ↓
   only an ADMITTED v2 is exposed
   ↓
packs/compiler  (Layer D)             →  ExpertisePackage
   ↓                                      "Layer 3's entire output. Structured expertise only;
                                           no recommendation or decision."
reason/  (Layer R)                    →  DecisionCandidate
```

### 3.1 · Two `BusinessSituationObject`s, and they are stages not duplicates

Corrected in the companion map after a first reading got it wrong. **v1 is the candidate, v2 is the
admitted object.** `situation_publisher.py:464` calls `upgrade_situation`; its docstring says
*"losslessly move the live v1 assembly onto typed v2 homes"*, and `publish_situation` says *"expose
only an admitted strict object."*

The defect is that **two classes share one name**, so every mention in a diff or a traceback is
ambiguous. `LegacySituation` is already the alias, applied at exactly one import line.

---

## 4. ⛔ Layer 2 runs no model on the production path

`process_event`, in its own words:

> *"The production L1 → L2 seam. L1 already interpreted, validated and published this extraction as
> a QES. **Re-reading the prose with this layer's legacy prompt would create two semantic verdicts
> for one event**, so this branch performs no cache read and no call."*

The legacy LLM branch still exists and **raises** unless a compatibility caller passes one
explicitly.

### 4.1 · Where the models actually are

| package | files with a metered call |
|---|---|
| `capture` (L1) | 3 |
| `context` (L2) | **2, and neither on the production path** |
| `packs` (D) | 4 |
| **`reason` (R)** | **13** |
| `deliver` | 2 |
| `executive`, `feedback` | 0 |

**The reasoning already lives in Layer R.** That is not a gap — it is where the new architecture
says it should be.

### 4.2 · An ANGLE is the one thing a model may be asked

> *"An ANGLE is a question asked of one of those queues, and nothing else. **It is not a licence to
> read the graph.**"*

Four exist: `CONDITION_NOW_TRUE`, `REPLY_OWED_TRIAGE`, `BLOCKER_ABSENCE`,
`SAME_SITUATION_TWO_THREADS`.

And each is asked **only of a queue the deterministic layer itself refused** —
`derived.timeline.condition_review` (conditions `parse_condition` declined to guess at) and
`context_residue` (what no reading explained at all).

**This is a model placement doctrine, already written down and already enforced.** Any new reasoning
in L2 either extends it or overturns it, and the difference matters.

---

## 5. The new architecture, mapped on

| new | today | verdict |
|---|---|---|
| L2 consumes **Enterprise Signals** from L1 | ✅ exactly — `qualified_extraction` | **matches** |
| L2 consumes a **Domain Object** from Layer D | ⛔ **no such type** — §5.1 | **needs naming** |
| L2 **reasons via LLM** (Layer R) | ⛔ L2 is deterministic by design | **§6 — a real reversal** |
| L2 produces a **Business Situation** | ✅ v2, gated by eight laws | **matches, and already exists** |
| L3 is the **Context Graph** holding it | ⚠️ the graph is *upstream* today — §5.2 | **needs a decision** |
| L3 emits a **Decision Object** → L4 | ⚠️ `DecisionCandidate` lives in `reason` | **to confirm** |

### 5.1 · There is no "Domain Object", and what is nearest runs the other way

`grep` for `DomainObject` returns nothing. Layer D's exported types are `BrainKind`,
`BusinessSituationObject`, `SituationContextSlice`, `ExpertiseEvidence`, `ExpertisePackage`.

**`ExpertisePackage` is the nearest thing — and today it is Layer D's OUTPUT, produced FROM a
situation, not an input consumed to make one.** Its own docstring: *"Layer 3's entire output."*

So the new sentence *"Enterprise Signals & Domain Object → reasoning → Business Situation"*
**reverses the current direction**:

```
today   Situation  ──→  [Domain Expertise]  ──→  ExpertisePackage
new     Domain Object ──→  [reasoning]  ──→  Business Situation
```

**This is the single most important thing to settle**, because everything downstream of it depends
on which object is the input.

### 5.2 · The graph is upstream of the situation today, not downstream

Situations are **derived from** graph correlations. The new L3 *"Context Graph (with Business
Situation & details)"* reads as the graph **holding** situations.

Both can be true — the graph can feed correlation *and* accumulate what was concluded. But if the
intent is that the graph comes **after** the Business Situation, then the 9 correlators move with
it, and that is a far bigger change than a renumbering.

**→ needs one sentence from you, and the whole L2/L3 split turns on it.**

---

## 6. ⛔ The decision the new architecture forces

> *"The same graph re-swept tomorrow by a different model version produces the same answers."*

That property is bought by keeping the model out of situation assembly, and it is what makes a
replay an audit rather than a re-guess. Layer 1 spent three steps learning to protect the same
thing — `eval_time` as a parameter, no clock in a validator, byte-identical sweeps.

**Putting an LLM into Layer 2 spends it.** That may well be the right trade: the price already paid
is **recall**, and a deterministic reading finds exactly what somebody wrote a rule for.

Three ways to spend it, and they are not equally expensive:

| | what | costs |
|---|---|---|
| **A · widen the angles** | more bounded questions over refusal queues | almost nothing — the doctrine already allows it, and each angle is replayable because its input is a queue |
| **B · reason over the situation** | a model reads an assembled situation + expertise and concludes | replayability of the CONCLUSION, not of the assembly |
| **C · reason instead of correlating** | a model builds the situation | replayability entirely, and 9 correlators become prompt |

**The shadow pass already implements B.** §7.

---

## 7. ⛔ And B already exists, switched off

`reason/domain_shadow.shadow_compile` is *"L1 signals + Layer D expertise, reasoned"* — the new
Layer 2 in everything but name. It is **wired into the live sweep** at `reason/runner.py:1451`,
gated per tenant, and **`live=False` for every existing caller**: it compiles the package and drops
it on the floor.

Its own docstring:

> *"the corpus was 152 authored capabilities that could not produce a single card: the compile ran
> (behind a flag that is off), published nothing, and reasoned in SHADOW."*

**So the highest-value Layer 2 work may not be building anything.** It may be turning this on and
proving it — three things flip together: a real publisher, `require_admission=True`, and
`ExecutionMode.LIVE` with an emitted `signals` row.

---

## 8. What I could not determine from the code

| | why it matters |
|---|---|
| **the Layer D corpus size** — 152 or 211 | the denominator of every coverage claim L2 makes |
| **how many situations a real tenant produces, by type** | whether the 7 producers are balanced or one dominates |
| **what the shadow pass measures today** | it is the cutover gate, and nobody has read its tallies |
| **whether `feedback` (L6) reads L2 at all** | it imports `context` in **zero** files |

All four need the database. All four are Harsh item 1.

---

## 9. The four questions only you can answer

1. **Is `ExpertisePackage` the "Domain Object", or is a new type intended?** §5.1 — the direction of
   the whole layer depends on it.
2. **Does the Context Graph come before or after the Business Situation?** §5.2 — it decides whether
   the 9 correlators stay in L2 or move to L3.
3. **Which of A / B / C is meant by "reasoning via LLM"?** §6 — and if B, the answer may be "turn on
   what is already built" rather than "build".
4. **Is `DecisionCandidate` the Decision Object?** It lives in `reason` (Layer R) today, not in the
   graph.

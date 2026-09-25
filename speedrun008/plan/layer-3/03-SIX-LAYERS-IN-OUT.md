# The six layers — what each takes in, what each hands out

**2026-09-25** · the definitive list, as Rohit stated it, mapped onto the code.

```
L1  Enterprise Signals
L2  Signals Qualification      (Signals + Domain Expertise = Reasoning)
L3  Context Graph
L4  Executive
L5  Delivery
L6  Learning
```

⛔ **Domain Expertise and Reasoning are not layers.** They are L2's *other input* and L2's *verb*.
That is the whole change from the Globe, and the code already works that way:
`domain_shadow` compiles the expertise package, reasons over it and emits — in one pass, in one
function.

⛔ **And the order answers the open question.** L3 sits **between** L2 and L4, so it is **on the
line**, not beside it. A decision passes *through* the Context Graph on its way to being executed.

---

## The table

| | layer | **IN** | **OUT** | in code today |
|---|---|---|---|---|
| **L1** | Enterprise Signals | raw sources — Gmail, Calendar, uploads | **`QualifiedEnterpriseSignal`** | ✅ `capture/`, 153 modules, 29 QES fields |
| **L2** | Signals Qualification | **QES** ＋ **Domain Expertise** (Plane D) | ⛔ **`DecisionObject`** | ⚠️ the parts exist; the object is **five shapes** |
| **L3** | Context Graph | the **DecisionObject** ＋ its situation ＋ its outcome | ⛔ **the DecisionObject, carrying its own history** | ⛔ **does not exist** |
| **L4** | Executive | a decision | **`ExecutionObject`** | ✅ `executive/`, 25 modules, `contracts/execution.py` |
| **L5** | Delivery | an execution | **`DeliveryResult`** | ✅ `deliver/`, 36 modules, `contracts/delivery.py` |
| **L6** | Learning | delivery ＋ feedback ＋ outcome | **`LearningObject`** → the brains | ✅ `feedback/`, 12 modules, `contracts/learning.py` |

---

## L1 · Enterprise Signals

| | |
|---|---|
| **in** | Gmail, Calendar, uploads — 16 source categories defined, 2 connected |
| **out** | `QualifiedEnterpriseSignal` — 29 fields, with `importance_bp`, `evidence_refs`, and the **visibility stamped from the thread's recipient list** |
| **never** | interprets. It says *a commitment exists*, never *this commitment matters more than that one* |
| **state** | ✅ **complete.** 18 steps, benchmark 15 → 24 of 38, `vocabulary_fingerprint` unchanged |

---

## L2 · Signals Qualification — **Signals + Domain Expertise = Reasoning**

**Two inputs, not one.** That is what the formula says and it is why expertise is not a layer:

```
QualifiedEnterpriseSignal  ─┐
                            ├─→  reasoning  ─→  DecisionObject
Domain Expertise (Plane D) ─┘
```

| | |
|---|---|
| **in** | the QES **and** the authored corpus — 155 capabilities, all admissible |
| **inside** | graph writes · 9 correlators · 7 producers · 8 admission laws · V-9/V-10 · the slice · the validator · R-6 |
| **out** | ⛔ **the Decision Object** |
| **state** | ⚠️ **9 steps complete, and the output object is not one thing** |

### ⛔ The one problem at this boundary

*"The Decision Object"* is **five shapes** in the schema:

| shape | what it really is |
|---|---|
| `DecisionCandidate` | the in-memory candidate the reasoner ranks |
| `reasoning_run_outputs` | what one run produced, with its hash |
| `l4_reasoning_bundles` | the narrative, keyed on `decision_hash` |
| `decisions` (0015) | ⛔ **the query API's cache** — written by `api/intelligence_routes.py` and nothing else |
| `execution_outcomes` | what happened afterwards |

**L2-1 measured what two names for one thing cost: fifteen wrong annotations.** Five shapes for one
concept is why the Decision Object reads cleanly in a sentence and cannot be pointed at in the
schema — **and L3 cannot build a graph of them until one of the five IS it.**

---

## L3 · Context Graph — ⛔ the layer that does not exist

| | |
|---|---|
| **in** | the **DecisionObject** · the **situation** it was about · the **outcome** when it lands · the **evidence** it cited |
| **out** | ⛔ **the same DecisionObject, carrying its own history** — *"decided 3 times · ignored · ignored · dismissed as already handled"* |
| **never** | decides. It remembers, and it hands what it remembers to whoever decides next |

### Why it must exist — one measurement

Across the whole engine:

```
prior_decision  0     previous_decision  0     last_decision  0     past_decisions  0
```

**Nothing reads a prior decision when making a new one.** GeniOS decides every situation from
scratch, every sweep, with no memory of what it said last time or whether it worked.

**A system that can read those four lines does not send the fourth identical card. A system that
cannot sends it forever.**

### What exists toward it

| node / edge | state |
|---|---|
| situation · decision · outcome · entity | ✅ all four exist as rows |
| `outcome ─followed→ decision` | ✅ `execution_outcomes.decision_hash` |
| `situation ─anchored→ entity` | ✅ `context_situations.anchor_node_id` |
| `decision ─cited→ evidence` | ✅ `reasoning_evidence_id_map` |
| **`decision ─about→ situation`** | ⛔ **missing** — not one of the 16 `reasoning_*`/`l4_*` tables carries a `situation_id` |
| **`decision ─supersedes→ decision`** | ⛔ **missing** — no edge table, no parent column |

⛔ **`situation_interpretations` (migration 0183, built in L2-5) is already this graph's first
table** — one reading per (situation, slice), **with the slice**, so a conclusion can be replayed
against its own premises. It was built two steps ago without being called that.

**Four of five nodes and three of five edges exist. Two edges and one name are the whole layer.**

---

## L4 · Executive

| | |
|---|---|
| **in** | a decision |
| **out** | **`ExecutionObject`** — goal, ordered steps, owner per step, `priority_bp`, `expires_at` |
| **never** | changes the decision. It operationalises it |
| **state** | ✅ 25 modules · `contracts/execution.py` |

⛔ **The decision → execution link already exists**: `execution_id` hashes
`(org_id, decision_hash, plan_hash)` and **deliberately excludes the communication plan** — so one
decision with the same plan is one execution, however it is later routed.

---

## L5 · Delivery

| | |
|---|---|
| **in** | an `ExecutionObject` |
| **out** | **`DeliveryResult`** — channel, status, attempt history, `acted_at` |
| **never** | creates intelligence. It routes what already exists |
| **state** | ✅ 36 modules · `contracts/delivery.py` with `DeliveryCandidate`, `DeliveryDecision`, `DeliveryVerdict` |

**Late-bound on purpose.** Who, where and when are properties of *now*, not of when the decision was
made — which is why a card detected at 09:04 during a meeting lands at 11:40 in Gmail.

⛔ **L2-7 added `signals.situation_id` here**: the card loop runs over signals, so one situation
firing three rules produced three cards that could never merge. Migration 0182 gives the link a
home; the collapse ratio is still unmeasured on the pilot.

---

## L6 · Learning

| | |
|---|---|
| **in** | `DeliveryResult` ＋ feedback ＋ outcome |
| **out** | **`LearningObject`** → written to the brains |
| **never** | edits the Expert Brain. `BrainTarget` has **no expert value** — the write is unconstructable |
| **state** | ✅ 12 modules · `contracts/learning.py` · `contracts/learned_state.py` with a `CONSUMER_ALLOWLIST` |

**The loop closes into L2**, not into L3: what L6 learns is *what to believe*, which is Domain
Expertise's business. **What L3 remembers is *what we decided*, which is a different fact** — and
keeping them apart is the same `Observation ≠ Inference ≠ Hypothesis` discipline one level up.

---

## The whole chain, end to end

```
sources
  │
  ▼  L1 ──────────────────────────────────────────  QualifiedEnterpriseSignal
  │
  ├─◄─ Domain Expertise (Plane D · 155 capabilities)
  ▼  L2  Signals Qualification · reasoning ────────  DecisionObject        ⚠️ five shapes
  │
  ▼  L3  Context Graph ───────────────────────────  the decision + its history   ⛔ MISSING
  │
  ▼  L4  Executive ───────────────────────────────  ExecutionObject
  │
  ▼  L5  Delivery ────────────────────────────────  DeliveryResult
  │
  ▼  L6  Learning ────────────────────────────────  LearningObject
        │
        └──────────────────────────────────────────►  back into Plane D
```

**Five of the six layers are built.** The missing one is L3, and it is missing because the previous
architecture never had it — the Globe's layer index has no layer whose job is *remembering what was
decided*.

---

## What L3 needs, in order

| | | |
|---|---|---|
| **1** | ⛔ **Name the Decision Object** | one of the five becomes it; the others become its stages, its audit or its cache. L2-1's exact work |
| **2** | ⛔ **Carry `situation_id` into the decision** | L2-7's migration, one seam up. Without it there is no graph, only a log |
| **3** | the `decision ─supersedes→ decision` edge | supersession, revision, and what a mute must reach |
| **4** | the read path | the decision arrives at L4 carrying its own history |

**Step 2 is the same defect L2-7 found on `signals`** — the value is in scope when the decision is
persisted and is dropped. `not_carried`, at the next seam up.

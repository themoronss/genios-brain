# ⛔ Correction — the Context Graph PRODUCES the Business Situation

**2026-09-25** · supersedes the L2/L3 rows of [`03-SIX-LAYERS-IN-OUT.md`](03-SIX-LAYERS-IN-OUT.md)

Rohit: *"Context Graph ka outcome to Business Situation hoga na — kyunki Context Graph real truth
hai, aur yahi se cards banenge, details banenge, sab banega."*

**He is right, and the code agrees with him, not with the previous file.**

---

## 1. What the previous file got wrong

| | previous file | **correct** |
|---|---|---|
| L2 out | a Business Situation / a Decision Object | **facts, observations and correlations written into the graph** |
| L3 out | "the decision carrying its own history" | ⛔ **the `BusinessSituationObject`** |
| L3 state | "does not exist" | ⛔ **it exists, it runs on every sweep, and it is the biggest thing in the layer** |

I had the graph as something to be *built from* decisions. **It is the other way round: the graph is
what decisions are built from.**

---

## 2. The code says it in its own first paragraph

`context/situation_bso.py`, line 1:

> *"Layer 2 stores situations in `context_situations` and their **evidence across
> `context_correlation_members` + `graph_source_refs`**; **the graph slice comes from the same
> `NodeContext`** the reasoning engine already loads."*

And the live path, unchanged since it was measured in `01-CURRENT-STATE.md` §3:

```
QES
 ↓   facts · observations · nodes  ──────────►  THE GRAPH
 ↓
 9 correlators read the graph        correlation.py + 9 modules
 ↓
 7 producers turn correlations into situations
 ↓
 build_business_situation()   →  BusinessSituationObject
```

**A Business Situation cannot be made from one signal.** It is three emails, a meeting and a
silence, seen together. Seeing together *is* correlation, and correlation needs a graph. So the
Business Situation **must** come out of the graph — there is nowhere else it could come from.

---

## 3. The corrected table

| | layer | **IN** | **OUT** |
|---|---|---|---|
| **L1** | Enterprise Signals | sources | `QualifiedEnterpriseSignal` |
| **L2** | Signals Qualification | QES ＋ Domain Expertise | ⛔ **qualified facts · observations · edges — written INTO the graph** |
| **L3** | **Context Graph** | everything L1 and L2 ever wrote, accumulated | ⛔ **`BusinessSituationObject`** — the real truth, correlated across people, time and threads |
| **L4** | Executive | a Business Situation | a decision → `ExecutionObject` |
| **L5** | Delivery | an execution | **the cards** → `DeliveryResult` |
| **L6** | Learning | delivery ＋ outcome ＋ feedback | `LearningObject` → back into Domain Expertise |

**L2 qualifies one signal. L3 sees all of them at once.** That is the whole difference between the
two layers, and it is why they are two layers.

---

## 4. ⛔ So what IS missing — and it is sharper than "a layer"

The graph exists: **10 tables**, written by 14 modules. Its node vocabulary:

```
person · company · deal · meeting · task · thread · commitment · tenant
document · product_usage_event · product_account · subscription
```

**Twelve node types, and not one of them is `situation` or `decision`.**

And every module that writes the graph belongs to **L1 or L2**:

```
capture/pipeline · capture/screen/fingerprint · platform/screen_promoter
context/ ×9 · api/segments_routes
```

**`reason/` writes nothing. `executive/` writes nothing. `deliver/` writes nothing.
`feedback/` writes nothing.**

### The graph is the real truth about THE WORLD. It is not yet the truth about US.

It knows every person, deal, thread and commitment. It does not know:

| | |
|---|---|
| what we **concluded** | no `situation` node |
| what we **decided** | no `decision` node |
| what we **sent** | `deliver/` never writes back |
| whether it **worked** | `feedback/` never writes back |

⛔ **This is the real explanation of the `prior_decision = 0` measurement.** Nothing reads a prior
decision — not because a layer is missing, but because **the graph has no node type that could hold
one.** The truth flows in one direction and never returns.

---

## 5. The Layer 3 work, restated

Not *"build the Context Graph"*. It is built.

**Close its loop.**

| | | |
|---|---|---|
| **1** | ⛔ `situation` becomes a graph node | today it is a row in `context_situations` beside the graph, not a node inside it |
| **2** | ⛔ `decision` becomes a graph node | and `decision ─about→ situation` becomes an edge — the L2-7 defect, one seam up |
| **3** | `deliver/` and `feedback/` write back | `sent`, `opened`, `acted`, `ignored` are facts about the world too |
| **4** | the correlators may read them | then the fourth identical card cannot be produced, because the correlator can see the first three |

**`situation_interpretations` (migration 0183, built in L2-5) is step 1 waiting for a node type.**
It already stores one reading per (situation, slice), with the slice, so a conclusion can be
replayed against its own premises.

---

## 6. One thing this correction leaves open

Under this model, **Domain Expertise feeds L2** — *"Signals + Domain Expertise = Reasoning"*, per
signal, before the graph.

**Today it runs after:** `packs/compiler` consumes a finished `BusinessSituationObject` and produces
an `ExpertisePackage`. Its own docstring calls that package *"Layer 3's entire output."*

So expertise is currently a **consumer** of the situation, and the new model makes it an **input** to
qualification. That reversal was flagged in `01-CURRENT-STATE.md` §5.1 and is still the open one —
but it is an ordering question inside L2, not the L2/L3 boundary, which this file settles.

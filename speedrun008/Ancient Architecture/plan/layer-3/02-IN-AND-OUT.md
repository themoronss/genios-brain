# L2 in/out, L3 in/out — the Globe, the code, and the change

**2026-09-25** · answering: *"Layer 2 kya input le raha aur kya output de raha? Layer 3 ka kya input
hoga aur kya output? Previous architecture mein kaisa tha aur ab kaisa hoga?"*

---

## 1. The Globe — what was decided originally

From `GeniOS-Design-Globe.html`, the layer index table:

| layer | takes in | hands out |
|---|---|---|
| L1 Knowledge | raw sources | `QualifiedEnterpriseSignal` |
| **L2 Context Intelligence** | **qualified signals** | **`BusinessSituationObject`** |
| **L3 Domain Expertise** | **situation + context slice** | **`ExpertisePackage`** |
| L4 Reasoning Engine | situation + expertise | `DecisionObject` |
| L5 Executive | decision | `ExecutionObject` |
| L5.2 Delivery | execution | `DeliveryResult` |
| L6 Learning | delivery + feedback | `LearningObject` |

**In the Globe, L2 stopped at the situation and L3 was Domain Expertise.** Three separate layers —
2, 3, 4 — each handing the next one object.

---

## 2. What the code actually does today — measured

```
capture/          QES                                  ← L1, unchanged
   ↓
context/pipeline.process_event(qualified_extraction=…)
   ↓  graph writes · 9 correlators · 7 producers
SituationCandidate  (v1, 16 fields)
   ↓  eight admission laws + V-9/V-10
BusinessSituationObject  (v2, 28 fields)               ← L2's output, exactly as the Globe says
   ↓
packs/compiler  →  ExpertisePackage                    ← Plane D
   ↓
reason/  →  a DecisionCandidate, then an emitted `signals` row
   ↓
deliver/  →  a card
```

**So the Globe's L2 output is real and shipped.** What the Globe called L3 and L4 are in the code
as `packs/` and `reason/` — and this rebuild has been calling them **Plane D** and **Plane R**
rather than layers, which is the one naming change already made.

---

## 3. ⛔ What your model changes, and it is not a rename

> *"Layer 2 ka outcome hai Decision Object. Layer 3 toh un objects ki madad se graph hi banana
> hua na."*

| | Globe | your model |
|---|---|---|
| **L2 output** | `BusinessSituationObject` | ⛔ **`DecisionObject`** |
| **L3** | Domain Expertise | ⛔ **the Intelligence Graph** |
| what happened to expertise & reasoning | were L3 and L4 | become **planes** that L2 reasons *with* |

**The Globe's L2 + L3 + L4 collapse into one layer.** That is not a demotion — it says
**situation, expertise and reasoning are one act of interpretation**, and the planes serve it
rather than following it. The code already agrees: `domain_shadow` compiles the package *and*
reasons over it *and* emits, in one pass, inside one function.

⛔ **And the new L3 is something the Globe does not contain at all.** Search its layer index: there
is no layer whose job is *"remember what we concluded."* The closest is L6 writing to the dynamic
brains — which stores **what to believe**, not **what we decided and whether it worked.**

---

## 4. ⛔ THE MEASUREMENT THAT SETTLES WHY L3 MUST EXIST

Across all 185 tables and the whole engine:

```
prior_decision      0 occurrences
previous_decision   0
last_decision       0
past_decisions      0
```

**Nothing anywhere reads a prior decision when making a new one.**

And the schema says the same:

| link | exists? |
|---|---|
| decision → outcome | ✅ `execution_outcomes.decision_hash` |
| situation → decision | ⛔ **no `situation_id` on any of the 16 `reasoning_*`/`l4_*` tables** |
| decision → decision | ⛔ no edge, no parent, no supersession |

⛔ **So GeniOS decides every situation from scratch, every sweep, with no memory of what it
decided last time or whether it worked.** The Globe's own promise — *"a recommendation engine ends
at Deliver. GeniOS does not"* — is half-built: outcomes are recorded, and **nothing reads them back
into a decision.**

**That is Layer 3's entire reason to exist.**

---

## 5. So: what does Layer 3 take in, and hand out?

### 5.1 · In

| | from | exists today? |
|---|---|---|
| the **Decision Object** | L2 | ⚠️ as five shapes — §6 |
| the **situation** it was about | L2 | ⛔ **not linked to the decision** |
| the **outcome**, when it lands | L4/L5 | ✅ `execution_outcomes.decision_hash` |
| the **evidence** it cited | Evidence Graph | ✅ `reasoning_evidence_id_map` |

### 5.2 · ⛔ Out — and this is the question that actually needs answering

A graph does not "hand out" the way a pipeline stage does. It **accumulates** and it **answers**.
So there are two coherent shapes, and they are genuinely different products:

| | **A · L3 is BESIDE the line** | **B · L3 is ON the line** |
|---|---|---|
| L2 → | L4 directly | **L3**, then L4 |
| L3's output | a **query surface** — traversals, no object | ⛔ **the Decision Object, enriched with its own history** |
| answers | *"why did you tell me this?"* after the fact | **and also** *"have we decided this before? did it work?"* **before the fact** |
| Globe Rule 02 (one typed object per boundary) | ⚠️ L3 crosses no boundary | ✅ obeyed |
| what it changes | an audit surface | **the decision itself** |

⛔ **B is the one worth building, and the measurement in §4 is why.** If L3 only records, the system
still decides from scratch forever. If L3 is on the line, then the next decision about the same
situation arrives carrying:

```
this situation           sit_00cae…
decided before           3 times · 14 Aug, 2 Sep, 19 Sep
what we said             "review the renewal" · "review the renewal" · "review the renewal"
what happened            ignored · ignored · dismissed as "already handled"
```

**A system that can read those four lines does not send the fourth card.** A system that cannot
sends it forever — and that is the single most common way this class of product dies.

---

## 6. ⛔ The blocker before any of this: "the Decision Object" is five things

| shape | where | what it really is |
|---|---|---|
| `DecisionCandidate` | `contracts/` | the in-memory candidate the reasoner ranks |
| `reasoning_run_outputs` | audit | what one run produced |
| `l4_reasoning_bundles` | audit | the narrative, keyed on `decision_hash` |
| `decisions` (0015) | — | ⛔ **the QUERY API's cache.** Written by `api/intelligence_routes.py` and nothing else, keyed on `sha256(org│module│question│graph_version)`. Not the sweep's output at all |
| `execution_outcomes` | — | what happened afterwards |

**L2-1 measured what two names for one thing cost: fifteen wrong annotations across the Domain
Expertise compiler.** Five shapes for one concept is why *"the Decision Object"* reads cleanly in a
sentence and cannot be pointed at in the schema.

⛔ **A graph of decision objects cannot be built until one of those five IS the decision object.**

---

## 7. The two layer tables, side by side

```
GLOBE                                    NOW

L1  Knowledge         → QES              L1  Enterprise Signals   → QES
L2  Context           → Situation        L2  Situation Intelligence → DECISION OBJECT
L3  Domain Expertise  → ExpertisePkg       ├─ Plane D · Domain Expertise
L4  Reasoning         → Decision           └─ Plane R · Reasoning
L5  Executive         → Execution        L3  INTELLIGENCE GRAPH   → the decision, with its history
L5.2 Delivery         → DeliveryResult   L4  Executive            → ExecutionObject
L6  Learning          → LearningObject   L5  Delivery             → DeliveryResult
                                         L6  Learning             → LearningObject
```

**Nothing in the code has to move.** `packs/` and `reason/` keep their packages and stop being
called layers. The one genuinely new thing is L3 — **and it is new because the Globe never had it.**

---

## 8. What is already built toward it, without having been named

| | |
|---|---|
| `situation_interpretations` (L2-5, migration 0183) | one reading per (situation, slice), **with the slice**, so a conclusion can be replayed against its own premises. **This is the Intelligence Graph's first table** |
| `execution_outcomes.decision_hash` | the decision → outcome edge, already there |
| `reasoning_evidence_id_map` | the decision → evidence edge, already there |
| `signals.situation_id` (L2-7, migration 0182) | the situation → card link, added two steps ago |

**Four of the five node types and three of the five edges exist.** What is missing is the two edges
that make it a graph of decisions rather than a log of them — `decision ─about→ situation` and
`decision ─supersedes→ decision` — plus the naming in §6.

---

## 9. The one thing that needs your answer

**Is Layer 3 on the line, or beside it?**

| | |
|---|---|
| **B · on the line** *(recommended)* | the decision carries its own history, and the fourth identical card never gets sent |
| A · beside it | an audit surface. Everything in §4 stays true forever |

Everything else in this file is read from the code and needs no decision.

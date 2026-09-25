# The Globe's engines — where every one of them lives now

**2026-09-25** · measured against `GeniOS-Design-Globe.html` (417 KB) and the code

---

## 1. The short answer: nothing is dropped. All 18 exist.

⛔ **An engine and a layer are not competing concepts.**

| | |
|---|---|
| **a layer** | a **stage** — where work happens, in order |
| **an engine** | a **component** — a thing that does work |

**An engine lives inside a layer.** The Globe named engines because engines were its top-level
unit. The new list names layers because a layer is where an input becomes an output. Every engine
gets a home; not one is removed.

## 2. The map, measured

| Globe component | lives in | new layer |
|---|---|---|
| **Qualification Engine** | `capture/esqe/` | **L1** |
| **Connector Manager** | `ConnectionStore` + connectors | **L1** |
| **Signal Lifecycle Manager** | `LifecycleStore`, lifecycle routes | **L1** |
| **Correlation Engine** | `context/correlation*.py` — **10 modules** | **L2 → L3** |
| **Business Situation Engine** | `context/situation_bso.py` ＋ 7 producers | **L3** (it is the graph's read side) |
| **Capability Registry** | `packs/compiler/capability_resolver.py` | **L2** (Domain Expertise = L2's input) |
| **Graph Engine** | `context/graph_store.py` | ⛔ **L3 — the Evidence Graph** |
| **Version Manager** | `graph_versions` ＋ the as-of read | **L3** |
| **Freshness Manager** | `freshness_policy_id` on `graph_facts` | **L3** |
| **Context Quality Engine** | `context/health.py` → `graph_health` | **L3** |
| **Reasoning Engine** | `reason/runner.py` | ⚠️ **L2 and L4 — §4** |
| **Reasoning Orchestrator** | `reason/composer.py` | ⚠️ **L2 and L4 — §4** |
| **Executive Engine** | `executive/` — **26 modules** | **L4** |
| **Permission Manager** | `contracts/authority.py`, `authority_routes` | **L4** |
| **Delivery Engine** | `deliver/pipeline.py` | **L5** |
| **Delivery Orchestrator** | `deliver/outbox.py` | **L5** |
| **Retry Manager** | the outbox's retry path | **L5** |
| **Learning Orchestrator** | `feedback/orchestrator.py` | **L6** |

**18 of 18 present.** The Globe described the system accurately; it organised it by machine rather
than by stage.

## 3. ⛔ And Layer 3 gains one the Globe never had

| | |
|---|---|
| **Intelligence Graph** | ⛔ **no Globe equivalent** — the Globe's layer index has no component whose job is *remembering what was decided* |

That absence is the whole reason `prior_decision` appears **0 times** in the engine.

---

# 4. ⛔ THE FINDING — and it must be fixed before any Layer 3 code is written

## 4.1 · There are now FOUR numbering vocabularies, and `LAYERS.py` predicted this

`genios_engine/LAYERS.py`, unprompted, in its own docstring:

> *"Package names carry semantics, never digits: **the numbers have already changed twice across
> specs while the code did not**, so no digit ever appears in a package name."*

It already ships a translation table for **three** vocabularies. Rohit's list is the **fourth**:

| package | `LAYERS.py` | old dossier | Atlas | ⛔ **new list** |
|---|---|---|---|---|
| `capture` | 1 Enterprise Signals | L1 Capture | 1 | **L1** ✅ |
| `context` | 2 Situation Intelligence | L2 Context graph | 2 | ⛔ **L2 *and* L3** |
| `packs` | – Plane D · Domain Expertise | **L4** Domain packs | 3 | ⛔ **folded into L2** |
| `reason` | – Plane R · Reasoning | **L3** Reasoning | 4 | ⚠️ **L2 *and* L4** |
| `executive` | **5** Executive Intelligence | – | 5 | ⛔ **L4** |
| `deliver` | **6** Intelligence Distribution | L5 Delivery | 5.2 | ⛔ **L5** |
| `feedback` | **7** Learning Engine | L6 Feedback | 6 | ⛔ **L6** |

## 4.2 · The two collisions that will bite

**⛔ "Layer 3" means Domain Expertise in the code and Context Graph in the new plan.**

```
115 files say "Layer 3" or "L3"     →  3 of them say "Layer 3 Domain Expertise compiler"
118 files say "Layer 4" or "L4"     →  "Layer 4 reasons about whether something…"
```

`domain_shadow.py`'s first line is *"Layer 3 Domain Expertise compiler"*. Under the new list, that
module is **L2** and Layer 3 is the graph.

**⛔ And the tail is off by one.** `LAYERS.py` numbers `executive=5`, `deliver=6`, `feedback=7`.
The new list numbers them **4, 5, 6**. Every one of the 241 files mentioning L5/L6 is now ambiguous
without knowing which vocabulary the author meant.

## 4.3 · This is L2-1's defect, inverted and larger

L2-1 measured what **two names for one thing** cost: **fifteen compiler annotations naming the
wrong situation stage**. This is worse — **one name for two things**, across **233 files**.

## 4.4 · The defence already exists and just needs the fourth column

`LAYERS.py` is *"the single place a layer number lives"*, no package name carries a digit, and
`tests/test_layer_topology.py` enforces import direction as a build failure. Its own closing line
is the rule this question needs:

> ⛔ ***"always name the package, never the digit alone."***

---

# 5. What changes in the plan

⛔ **A step is inserted at the front. `LAYERS.py` must carry the new vocabulary before any module
is written against it**, or Layer 3's code will be annotated in a numbering the rest of the repo
reads differently — which is exactly the drift `LAYERS.py` exists to stop.

| | step | |
|---|---|---|
| ⛔ **L3-00** | **Add the new vocabulary to `LAYERS.py` and `docs/LAYER_MAP.md`** | a fourth column, a totality guard across all four, and a test that fails if a package gains a digit |
| **L3-0** | Name the Decision Object | unchanged |
| **L3-1 … L3-7** | as planned | unchanged |

### And one honest gap this exposes

**`reason/` straddles two layers under the new list.** `domain_shadow` is L2 work (signals +
expertise = reasoning); `runner`, `composer` and `store` are L4 work (choosing what to do). Their
own docstrings say so in the *old* numbering — *"Layer 3 Domain Expertise compiler"* beside
*"deterministic Layer 4 reasoning"* in the same package.

**This is not a bug and it is not urgent.** `LAYERS.py` already declares `reason` a **plane, not a
stage** — *"consulted rather than passed through"* — and the import rule it enforces is correct
either way. It is recorded here so nobody later reads the package boundary as a layer boundary.

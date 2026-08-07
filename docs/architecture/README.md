> **Created:** 2026-08-07 · **Status:** Reference — frozen target vision
> **Source:** distilled from `GeniOS Theory II.pdf` ("GeniOS New Architecture")
> **Purpose:** the single canonical description of the GeniOS target architecture, layer by layer, so a new thread can read this and immediately reason about what to change.

# GeniOS Architecture — Target Vision

This folder is the **frozen target-state specification** of GeniOS: the 7-layer
(+ one split) intelligence architecture, the engineering constitution, and the
data contracts between layers. It is the reference you point a new conversation at
("read this md, this is complete") before sharing one layer's detail and asking
what in the current code should change.

## How this folder is organised

| File | What it covers |
|---|---|
| [00-PRINCIPLES.md](00-PRINCIPLES.md) | What GeniOS is / is NOT, the mental model, the three loops, the four knowledge levels, deterministic-first, typed objects, the RAG-vs-GeniOS distinction. **Read this first.** |
| [01-knowledge-layer.md](01-knowledge-layer.md) | Layer 1 — read + normalize enterprise reality. Zero reasoning. |
| [02-context-intelligence.md](02-context-intelligence.md) | Layer 2 — the live digital twin: Context Graph Engine + Correlation Engine + Enterprise Situation Engine. |
| [03-domain-expertise.md](03-domain-expertise.md) | Layer 3 — compiled executable capabilities (four brains, the compiler, the capability factory). |
| [04-reasoning-engine.md](04-reasoning-engine.md) | Layer 4 — the moat. Orchestrator + reasoning units + decision maker. Deterministic. |
| [05-executive-engine.md](05-executive-engine.md) | Layer 5 — operationalize a decision (never re-decide it). |
| [05.2-delivery-engine.md](05.2-delivery-engine.md) | Layer 5.2 — who/where/when/what-format. Distribution only. |
| [06-learning-engine.md](06-learning-engine.md) | Layer 6 — learn & evolve from outcomes. Governed. Never executes. |
| [ENGINEERING-CONSTITUTION.md](ENGINEERING-CONSTITUTION.md) | Cross-cutting: coding rules, storage strategy, LLM-usage map, testing, performance goals, build order. |

## The stack, at a glance

```text
Layer 1  Knowledge Layer            read + normalize reality        (code: capture/)
   ↓
Layer 2  Context Intelligence       the live digital twin           (code: context/)
   ↓
Layer 3  Domain Expertise           compiled executable capability  (code: packs/)
   ↓
Layer 4  Reasoning Engine           situation → ranked decisions    (code: reason/)
   ↓
Layer 5  Executive Engine           decision → execution object     (code: executive/)
   ↓
Layer 5.2 Delivery Engine           who / where / when / format     (code: deliver/)
   ↓
Layer 6  Learning & Evolution       learn from outcomes             (code: feedback/)
```

Three kinds of systems: **Knowledge (L1–L3)** understand reality · **Decision (L4)**
turn reality into decisions · **Execution (L5–L6)** operationalize and improve.

## Typed objects flow down the stack — never prompts, never raw JSON

```text
SituationObject  →  Reasoning  →  DecisionObject  →  Executive  →  ExecutionObject
                                                          ↓
                                              Delivery  →  DeliveryObject
                                                          ↓
                                              Learning  →  LearningObject
```

## Target vision vs. current code — how to use this with `../LAYER_MAP.md`

- **This folder = the target** (the "should be", from the PDF).
- **`../LAYER_MAP.md` = the current code today** — a code-verified table mapping the
  live `genios_engine/*` packages to the same layer numbers. It is accurate and
  is deliberately kept; it is NOT superseded by this folder.
- Layer-by-layer work = reconcile the two: read the target file here, read the
  matching package in code (each layer file lists its `genios_engine/*` modules),
  and plan the delta.

## Frozen terminology (renames that superseded earlier drafts in the source)

- **Execution / Delivery split** — "Execution Brain" → **Executive Engine (L5)**; a
  separate **Delivery Engine (L5.2)** owns who/where/when. Action-planning and
  delegation live in delivery-side operationalization, not in decision intelligence.
- **Business Situation Builder → Enterprise Situation Engine** — it discovers,
  updates, merges, splits, enriches, retires situations continuously; not a one-shot builder.
- **Context Graph stores facts, not documents** — nodes are Deal/Person/Risk/…, and an
  email is only *evidence* for a fact.
- **Reasoning consumes Situations, not the raw graph.**
- **Domain Expertise is compiled executable capability, not a knowledge base / RAG.**
- **Confidence is a vector, not a single number.**

## What is intentionally NOT here yet

Per the author: earlier per-domain content, playbooks, and the older dossier/spec
docs are **not** treated as authoritative for the target. They can be re-added later,
per layer. This folder captures the *architecture*, not the domain content.

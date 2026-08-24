> **Created:** 2026-08-07 · **Status:** Reference — frozen target vision
> **Source:** `GeniOS Theory II.pdf` — "Layer 4 / Reasoning Engine / Components"

# Layer 4 — Reasoning Engine

**The core IP and moat.** Most engineering effort belongs here.

**One responsibility:** transform a **Business Situation** into a **ranked set of
executable decisions.** Not answers — **decisions.** This is the **only** place where
synthesis (thinking) happens.

**Current code:** `genios_engine/reason/` — orchestrator, reasoners, decision_maker,
engine, scoring, rules, signals_derived, baselines, foresight, simulation, authority,
composer, plan, protocols, registry, guards, audit, telemetry, replay.

## It is a deterministic pipeline, not an LLM

Think of it as a **CPU**, not a model: many small deterministic units, each doing one
job, composed into computation. It **consumes** the Context Graph + Capability Packages
and **produces Decision Objects** — it never produces another graph and never persists
state (stateless, horizontally scalable, no DB of its own).

## Three parts (and nothing more)

```text
Reasoning Engine
├── Part 1: Reasoning Orchestrator     controls execution (never reasons/decides)
├── Part 2: Reasoning Units            specialized deterministic analysis
└── Part 3: Decision Maker             the ONLY synthesis point
```

### Part 1 — Reasoning Orchestrator (a workflow scheduler)

Decides, per situation: **which** units run, in **what order**, which run in
**parallel**, which are **skipped**, **timeouts**, **fallbacks**, minimum confidence,
and **whether an LLM refinement is even needed**. It **never reasons, never calculates,
never decides.** This is the latency/scalability lever — e.g. an investor-follow-up
situation runs Context/Goal/Opportunity/Risk/Priority/Decision and skips
Pricing/Negotiation/Legal/Hiring.

### Part 2 — Reasoning Units (≈15–20 global, reusable across every domain)

Reasoning **never changes across domains**; only Domain Expertise changes. Grouped:

| Group | Units |
|---|---|
| Situation Understanding | Context · Timeline · Dependency · Constraint |
| Business Evaluation | Risk · Opportunity · Impact · Priority · Confidence |
| Optimization | Tradeoff · Resource · Scheduling · Cost · Policy |
| Decision Support | Alternative · Validation · Recommendation |
| Cross-cutting | **Executive Principles** · Goal · Temporal |

**Every unit has the identical internal framework:**

```text
Input → Validator → Retriever → Analyzer → Calculator → Evaluator → Object Builder → (Metrics)
```

- **Analyzer** is the brain of the unit and may hold **plugins** — many small
  deterministic contributors of partial evidence (e.g. Risk Analyzer = Time + Financial
  + Relationship + Organization + Behavioral + Adaptive + Policy plugins). Risk isn't one
  algorithm; it's ~20 small deterministic ones aggregated.
- **Calculator** = pure math (weighted score, Bayesian update, normalization, expected
  value, ranking, aggregation). **Evaluator** turns numbers into meaning (82 → High Risk).
- Every unit returns **one typed object** (RiskObject, PriorityObject, ConstraintObject…)
  with score, confidence (vector), reason, evidence, metadata.

You build **one reasoning framework + N implementations**, not N different systems.

### Executive Principles Unit (domain-agnostic heuristics that sit above every capability)

Resolve blockers before optimizing · high-impact/low-effort first · never violate
policy · preserve optionality under high uncertainty · prefer reversible over
irreversible decisions when evidence is weak · escalate below a confidence threshold ·
don't create work if existing commitments are overloaded.

### Part 3 — Decision Maker (the ONLY synthesis)

Receives all the unit objects (Risk + Opportunity + Priority + Constraint + Tradeoff +
Impact + Context + Capability Package), then:

```text
Evidence Aggregator → Decision Synthesizer → Decision Evaluator → Decision Ranker
→ Confidence Calculator → Decision Object Builder
```

Everything before this is *analysis*; this is *synthesis*. It generates candidate
decisions (Send update / Schedule meeting / Wait…), validates (reject invalid, e.g.
"budget missing"), ranks by expected value, attaches the confidence vector, and emits
a **Decision Object**.

## Reasoning happens in conceptual sub-layers

`Fact reasoning (what is true) → Constraint reasoning (what is allowed) → Goal
reasoning (what helps) → Tradeoff reasoning (which is better) → Decision reasoning
(what to do) → Communication (how to present).` One large problem becomes several tiny
deterministic ones, each with the right algorithm.

## Algorithm map (deterministic — no LLM)

| Concern | Method |
|---|---|
| Constraints | rule engine |
| Timeline / "when" | temporal logic |
| Priority | weighted scoring |
| Opportunity | pattern matching |
| Dependencies | graph traversal |
| Optimization | linear programming (when needed) |
| Ranking | multi-criteria decision analysis (MCDA) |
| Confidence | Bayesian updating / evidence aggregation |

## The Decision Object (contract to Layer 5)

```text
DecisionObject { id, type, inputs, evidence, assumptions, constraints,
                 score, confidence(vector), explanation, recommendations, metadata }
```

## LLM usage in Layer 4

- **LLM Refiner** — the single (optional) LLM stage: turns the decision into executive
  English. It **communicates, it never thinks** ("This opportunity is time-sensitive
  because…"). The decision already exists before it runs.
- **Consultant, not decider** — the Decision Maker may consult an LLM *only* when
  confidence is below threshold; it supplements deterministic reasoning, never replaces it.

## Frozen decisions

- Reasoning is a deterministic pipeline of uniform units, not an LLM.
- Orchestrator schedules; Units analyze; Decision Maker is the sole synthesis point.
- Reasoning produces Decision Objects — never a graph, never persisted state.
- Every unit shares one internal framework and returns one typed object.
- LLM only refines communication or consults on low confidence; never decides/ranks/scores.

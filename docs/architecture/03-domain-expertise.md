> **Created:** 2026-08-07 · **Status:** Reference — frozen target vision
> **Source:** `GeniOS Theory II.pdf` — "Layer 3 / Domain Expertise / How to build it / Capability Factory"

# Layer 3 — Domain Expertise

**One responsibility:** provide reusable **expertise as compiled, executable
capabilities**. It **never thinks and never decides** — it only supplies the
ingredients the Reasoning Engine composes.

**Current code:** `genios_engine/packs/` — the four brains + capability content
shipped as data: registry, capabilities, general_v1, sales_v1, merge, snapshot, wiring.

## Kill this misconception first

Domain Expertise is **NOT** a knowledge base, RAG, documents, Markdown, YAML, a prompt
library, a vector DB, or a fine-tuned model. Those are *representations*.

> **Domain Expertise is a compiled executable knowledge system that exposes
> capabilities to the Reasoning Engine.** — compiled · executable · capabilities.

The compiler mindset (like C++ → machine code, or JSX → JS):

```text
Human Expertise
   ↓
Capability Specifications
   ↓
Knowledge Compiler
   ↓
Executable Intelligence Objects
   ↓
Reasoning Engine
```

Expertise = *knowledge + pattern recognition + decision rules + mental models +
tradeoffs + experience + context awareness + evaluation criteria + strategies +
failure recognition.* Knowledge is only one component — you're buying "25 years of
decision-making," not 10,000 pages of documents.

## The four brains — author ONE, learn the rest

```text
Human Engineers → Expert (Universal) Brain      ← the only one you author
                        │
      ┌─────────────────┼─────────────────┐
      ▼                 ▼                 ▼
 Organization       Behavioral         Adaptive
 Builder            Builder            Learning
 (inferred +        (observed /        (optimized /
  configured)        learned)           learned)
```

| Brain | What it holds | How it's built | Where it lives |
|---|---|---|---|
| **Universal** | concepts, ontology, frameworks, playbooks, decision policies, mental models, heuristics, strategies, KPIs, best/failure/success patterns, risk models, checklists | **authored** by humans (books/experts/playbooks), compiler-validated, versioned | **Git** (source of truth) |
| **Organization** | company profile, products, pricing, ICP, GTM, SOPs, approval matrix, org structure, roles, KPIs, business rules, vocabulary | **discovered** (from CRM/website/docs/emails) + explicit config | Supabase (dynamic) |
| **Behavioral** | per-person/team patterns: comms style, working hours, follow-up cadence, risk appetite, decision style, "never discounts", "replies at night" | **learned** continuously from actions (attached to capabilities, not people-in-general) | Supabase (dynamic) |
| **Adaptive** | success/failure statistics, confidence, learned patterns, optimization, preference evolution | **learned** from outcomes (starts empty) | Supabase (dynamic) |

Universal = "what"; Organization = "how our company works"; Behavioral = "how these
people work"; Adaptive = "what actually works, statistically." **None of them decide.**

## The capability factory — the scalable model

Domain Expertise is a **Capability Factory**, not a knowledge repository. Adding HR /
Finance / Engineering later = adding capabilities + objects, **not** a new brain and
**not** new architecture.

```text
Domain → Capabilities → Objects → (Universal | Organization | Behavioral | Adaptive slices)
       → Relationships → Validation → Compiler → Compiled Capability Packages
       → Capability Runtime → Reasoning Engine
```

- **Capability** = a reusable business skill (Pricing, Negotiation, Discovery,
  Investor Follow-up, Hiring Review…). Each is independently authored / validated /
  compiled / published / versioned / tested.
- **Object (Intelligence Object)** = the *smallest reusable reasoning unit* inside a
  capability (Budget Qualification, ROI, Discount, Champion Detection…). **The reasoning
  engine reads objects, not brains.** Each object is a **vertical slice** merging all
  four perspectives — so the engine loads one Budget-Qualification object, not "four brains."

### Fixed object schema (every object, same shape)

ID · Capability · Purpose · Problem · Inputs · Outputs · Required Context · Concepts ·
Rules · Mental Models · Playbooks · Strategies · Dependencies · Relationships ·
Calculators · KPIs · Examples · Failure Patterns · Success Patterns · Confidence · Metadata.

### Object relationships

`depends_on · related_to · enables · conflicts_with · requires`. Author only the
meaningful semantic edges; the compiler derives transitive ones (Budget → Proposal →
Negotiation ⇒ Budget indirectly_affects Negotiation).

## The 5-stage lifecycle (Git → Runtime)

```text
Human Knowledge → Authoring (Git) → Compilation → Runtime Database → Runtime Cache → Reasoning Engine
```

- **Git** = engineering source of truth (authored knowledge; human-reviewed; runtime
  never reads Git directly).
- **Compiler (offline, not runtime)** validates (completeness, missing rules, circular
  refs, duplicates) and merges the Universal + Organization + Behavioral slices into a
  single **Compiled Intelligence Object**; the **Adaptive slice stays separate** because
  it changes continuously (so learning updates it without a full recompile).
- **Runtime DB (Supabase)** holds compiled objects, rules, relationships, indexes,
  embeddings, metadata + the live Adaptive/Behavioral/Organization brains.
- **Cache (Redis/in-memory)** holds frequently/recently used objects.
- **Runtime loads only the relevant compiled objects** for the active capability —
  never the whole brain (e.g. ~9 objects for a pricing query, not "all of Sales").

## What Layer 3 returns to Reasoning

**Capability Packages of typed objects — not documents, not prose.** Conceptually:

```typescript
loadCapability("pricing")            → { concepts, rules, mental_models, playbooks, constraints, strategies, kpis, relationships }
loadOrganizationContext("pricing")   → company policies (approval limit, pricing, products)
loadBehaviorContext(user, capability) → learned behavioral patterns
loadAdaptiveSignals(capability)       → historical success metrics + confidence
```

Every layer returns **typed objects**. The Domain Brain never says "send this email";
it only says "here is how pricing works." **Synthesis happens only in Layer 4.**

## Supporting sub-systems inside Layer 3

- **Brain Builder Pipeline** — the factory that constructs/refines the brains
  (Organization Analyzer, Behavior Analyzer, Adaptive Analyzer, Expert Compiler).
- **Knowledge Compiler** — packages brains into executable capability bundles.
- **Capability Runtime** — serves compiled packages to reasoning.

## LLM usage in Layer 3

Only for initial expert authoring / extraction. The compiler and runtime are
deterministic. LLM never decides which capability applies at runtime — that is the
Reasoning Orchestrator's job.

## Frozen decisions

- Domain Expertise = compiled executable capability, never a knowledge base / RAG.
- Author only the Universal Brain; Organization/Behavioral/Adaptive are built/learned.
- Objects (vertical slices) are the runtime unit; the engine loads objects, not brains.
- Git = authored source of truth; Supabase = runtime; compiler is offline.
- The Adaptive slice stays separate so learning avoids full recompilation.

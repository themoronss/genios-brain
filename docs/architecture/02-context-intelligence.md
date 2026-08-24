> **Created:** 2026-08-07 · **Status:** Reference — frozen target vision
> **Source:** `GeniOS Theory II.pdf` — "Layer 2 / Context Graph / Correlation / Business Situation / Enterprise & Domain Graph"

# Layer 2 — Context Intelligence

**One responsibility:** represent the **current state of the enterprise** — the live
digital twin. It answers exactly one question: **"What is true right now?"**

It is **NOT** a knowledge graph, **NOT** memory, **NOT** a domain brain. It never says
what *should* happen or what best practice is — only what currently exists.

**Current code:** `genios_engine/context/` — correlation, graph_store, situations,
identity, merge, canon, attention, health, projections, read_models, extract, llm,
guard, vocabulary, domain_spec, backfill, pipeline, runner.

## The critical reframing: build from qualified signals, store facts

The pipeline is **not** `Knowledge → Context Graph → Reasoning`. It is:

```text
Knowledge Layer
   ↓
Event Classification
   ↓
Signal Extraction        ← Enterprise Signal Qualification Engine (ESQE)
   ↓
Relevance Filtering
   ↓
Context Graph
   ↓
Business Situations
   ↓
Reasoning
```

The Context Graph is built from **qualified enterprise signals**, not raw data.
GeniOS filters like a human executive (90% of inbox noise is discarded).

### The graph stores FACTS, not documents

Nodes are business entities — **Company, Person, Deal, Meeting, Task, Risk,
Opportunity, Goal, Project, Decision, Policy, Preference, Commitment, Evidence** —
never `Email / PDF / Slack`. An email is only **evidence** for a fact. Example: not
"Email #482" but *"Customer Acme — Waiting on Proposal — since 3 days"* with the email
as evidence.

Every node carries system metadata: freshness, confidence, quality, lifecycle,
version, evidence count, source count, importance, projection tags.

## Layer 2 has three engines (not one)

```text
Layer 2 — Context Intelligence
├── Enterprise Correlation Engine     builds + enriches context
├── Context Graph Engine              maintains the graph over time
└── Enterprise Situation Engine       turns graph state into Business Situations
```

### A. Enterprise Signal Qualification Engine (ESQE) — the gateway

Decides, cheaply and mostly deterministically, whether a raw event even enters the
graph: **Ignore · Archive · Monitor · Context Graph.** A funnel, not one LLM call:
1. deterministic filtering (rules: promotions/social/unsubscribe/automated) — removes 50–70%,
2. metadata classification (labels, sender reputation, recipient count, subject, MIME),
3. domain-candidate detection (lightweight classifier / embeddings / small model),
4. capability detection (small classifier),
5. **LLM only as fallback** when confidence is low.

### B. Enterprise Correlation Engine

**Only job:** *"Do these signals describe the same business situation?"* It merges
disconnected signals into one enterprise situation (Slack + email + calendar + CRM =
one deal). It does not prioritize or recommend. Built as a **pipeline of deterministic
micro-engines**, each enriching before passing on:

`Event Collector → Signal Normalizer → Entity Matcher → Temporal Correlator →
Relationship Correlator → Resource Correlator → User Correlator → Goal Correlator →
Project Correlator → Policy Correlator → Conflict Detector → Missing-Context Detector →
Opportunity Detector → Risk Detector → Correlation Confidence → Situation Builder →
Context Publisher.`

### C. Context Graph Engine — maintains the live graph

Storage (Neo4j/Postgres/Supabase) is dumb; this is the logic on top. Components:
Graph Builder · **Graph Updater** (incremental only — never rebuild) · Graph Validator ·
**Freshness Manager** (fresh/stale/expired = confidence, not deletion) · Lifecycle
Manager · **Quality Manager** (coverage/completeness/consistency/connectivity) · Version
Manager (keep history, don't overwrite) · **Conflict Resolver** (mark conflicts, don't
overwrite; reasoning decides later) · Merge Engine (entity resolution: Acme = Acme Inc =
acme.io) · Pruning Engine (decay/archive) · Confidence Manager (per-fact confidence) ·
Index Manager · **Projection Manager** (one graph, many domain views) · Snapshot Manager ·
Graph Publisher. Plus a **Graph Health Monitor** (orphan %, duplicate rate, stale %,
avg freshness/confidence, conflict density, situation coverage).

### D. Enterprise Situation Engine (was "Business Situation Builder")

Converts the continuously-evolving graph into **bounded, executable Business
Situations** — the *process table* of the company (e.g. "Investor follow-up overdue",
"Enterprise deal blocked by legal", "Customer renewal at risk"). Renamed to *Engine*
because it continuously discovers, updates, merges, splits, enriches, validates, and
retires situations. Components: Situation Discovery · Classifier · Aggregator ·
Context Builder · Dependency · Priority Estimator · Freshness · Confidence · Lifecycle ·
Publisher · Archive.

**Situation schema (fixed):** ID, Type, SubType, Domain, Capability, Status, Current
State, Timeline, Owner, Stakeholders, Evidence, Dependencies, Constraints, Risks,
Opportunities, Missing Information, Related Situations, Confidence, Freshness,
Last Updated, Metadata.

## What the Context Graph contains (the 16 context components)

Entities · Relationships · Timeline · State · Intent · Tasks · Goals · **Authority**
(decision-maker/approver/influencer/champion/blocker/reviewer/stakeholder/owner/
executor/observer — heavily used in reasoning) · Resources · Constraints · Signals ·
Opportunities · Risks · Confidence · **Attention** (critical/high/medium/low/ignore/
needs-action/… — the reasoning engine reads this first) · Metadata.

Plus **dynamic preferences** ("CEO travelling this week", "customer asked for email not
calls") live here as *current state*; **stable behavioral preferences** ("CEO prefers
concise emails") live in the Behavior Brain (Layer 3).

## Domain Router / graph projections

Every event gets **domain tags** first; a **Domain Router** then loads only the
relevant domain (Sales/Support/Finance/…/Admin fallback). There is **one Enterprise
Graph** with per-domain **projections** (Sales view, Support view, Executive view) —
never duplicate graphs.

## Reasoning consumes Situations, not the raw graph

The Reasoning Engine must not traverse nodes/edges. The Situation Engine hands it
bounded Business Situations; the graph exists to maintain relationships and state.

## LLM usage in Layer 2

Minimal — entity/intent extraction, document parsing, metadata generation, semantic
normalization, and edge-extraction fallback only. **Never** for correlation,
relationships, priority, risk, opportunity, or confidence — those are deterministic.

## Frozen decisions

- Context Graph = current state / digital twin; answers "what is true now" only.
- Store facts + evidence, not documents.
- Incremental updates only; never rebuild the graph.
- Conflicts are marked, not resolved by overwrite.
- Situations (not the raw graph) are the artifact reasoning consumes.

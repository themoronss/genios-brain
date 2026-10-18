# GeniOS architecture — the one we build to

**Source:** Design Atlas v2 (29 Sep 2026). **Written for:** Rohit, Harsh and every coding agent. Every
layer folder in GeniOS-008 is judged against this page, never against what today's code happens to do.

## What GeniOS is

The company intelligence layer: *Palantir for company managers*. It connects company data, workflows,
dependencies and goals; detects execution gaps; decides the next action; directs it to the right person
or AI agent; monitors progress; and adapts until the goal is reached or human judgement is needed.
**Memory remembers, agents execute; GeniOS analyses and decides what is next.**

## The flow

```
Sources (Gmail, Calendar, Slack, Drive, CRM, Screen)
   │
   ▼
L1 Enterprise Signals ── QualifiedEnterpriseSignalBundle + coverage receipt ──┐
   ▲                                                                           ▼
   └──── EvidenceNeed (fetch thread / backfill / re-extract) ──── L2 REASONING (primary)
                                                                   Orchestrator + Plane R + Plane D + Tools
                                              ContextSnapshot ───▲         │ ReasoningResult
                                                                 │         ▼ (situation mutations)
                                                          L3 Context Graph — admits: ADMIT / HOLD / REJECT
                                                                   │ DecisionObject (when decision-ready)
                                                                   ▼
                                                          L4 Executive — a human decides → ExecutionObject
                                                                   ▼
                                                          L5 Delivery — card / brief / agent task
                                                                   ▼
                                                          L6 Learning — attribute the miss, adapt through data ──┐
                                                                                                                 │
                                          (mutes, thresholds, brains — read by L2; never a code edit) ◄──────────┘
```

**L1 + L2 + L3 together are the Reasoning Plane.** L2 is the primary layer: the situation is formed
*by reasoning* over the bundle, the expertise and what the company already knows. L3 only remembers what
L2 concluded.

## The layers

| Layer | Package | The one question | In | Out | Model | Never |
|---|---|---|---|---|---|---|
| **L0 Foundation** | `contracts/` `platform/` `api/` | What holds it up? | — | typed contracts, wiring, tenancy | never | business meaning |
| **L1 Enterprise Signals** | `capture/` | What happened, how reliable, which incoming signals belong together? | raw events | **QualifiedEnterpriseSignalBundle** + coverage receipt | extraction, detection, link suggestion | concludes a situation, reads the graph |
| **L2 Reasoning** | `reason/` + `packs/` | What does it mean, and what is the best next move? | bundle + ContextSnapshot + ExpertisePackage | **ReasoningResult**, EvidenceNeed, receipt | 0–3 bounded calls per situation | stores state, decides for a human |
| **L3 Context Graph** | `context/` | What does the company now know, and how is it connected? | ReasoningResult mutations, evidence facts | admitted situation (BSO), ContextSnapshot, **DecisionObject** | none | reasons by itself |
| **L4 Executive** | `executive/` | Who decides, and how does a decision become owned work? | DecisionObject | **ExecutionObject** (owner, deadline, channel, ladder) | wording only | a model deciding |
| **L5 Delivery** | `deliver/` | Who receives it, where, when, in what form? | ExecutionObject / ReasoningResult lane | card, brief, agent task, DeliveryResult | wording only, validated | adds a fact |
| **L6 Learning** | `feedback/` | What did reality teach, and which layer should change? | outcomes, judgments | mutes, pack config, brain proposals (data) | parse corrections only | edits code or the expert brain |

## Inside L1 — capture honestly

Connectors → landing (dedupe) → preprocess (documents, transcripts) → gate (park, never drop) → triage
→ **ESQE** (classify, extract, importance ALG-17, expiry ALG-19) → **signal correlation (incoming only)**
→ publisher (V-1…V-7) → **bundle + coverage receipt** to L2.

L1 must deliver: the **coverage receipt** (what was read and what was not); **absence-derived signals**
(no reply, no owner, no approval, no delivery); **six object types**: commitment, condition, open
question, delivery status, meeting follow-up link, thread terminal state; **entity resolution with
doubt**; **roles** (sender ≠ promisor ≠ owner ≠ approver); **version and supersession**; the
**untrusted-content boundary**; and the **EvidenceNeed executor**, which fetches exactly the fact L2
asks for.

## Inside L2 — where the system thinks

- **Orchestrator.** The controller; not a unit, not a plane. Its twelve steps:
  1. intake and idempotency;
  2. **material-change gate**: nothing new means 0 calls;
  3. read a bounded ContextSnapshot from L3;
  4. route domains and get the ExpertisePackage;
  5. classify the need: stage, evidence, time, impact, complexity;
  6. select units and compile a dependency-complete plan;
  7. run the deterministic units;
  8. **one bounded judgment pass**;
  9. validate every claim;
  10. choose the **lane**;
  11. write back to L3 with compare-and-set;
  12. hand off, write the receipt, schedule the re-check.
- **Plane D (`packs/`).** What a professional knows. Reviewed YAML is compiled into an immutable pack and served by the Domain Compiler as a bounded, hash-pinned ExpertisePackage.
  - **Four brains:** expert, organisation, behaviour and adaptive.
  - **Precedence when they conflict:** law → org policy → authority → constraint → expertise → behaviour → heuristic.
- **Plane R (`reason/`).** How a professional thinks. Domain-free R-Units in six groups: establish reality, understand, explain and anticipate, judge and choose, plan and mobilise, control–verify–learn.
- **Tools.** Dates, money, baselines and graph lookups, all run on the frozen snapshot. Tools calculate; units interpret; humans authorise.
- **Output:** one **ReasoningResult** with:
  - facts, inferences, hypotheses and unknowns;
  - the frame and its alternatives;
  - expected vs actual;
  - consequences;
  - the intervention mode and the best next move;
  - the decision need;
  - the **confidence vector**;
  - situation mutations;
  - EvidenceNeeds;
  - a provenance receipt.

## Inside L3 — trusted memory

- **Evidence Graph:** `graph_nodes`, `graph_facts`, `graph_edges`, with `authority_rank`. It records what the sources said.
- **Intelligence Graph:** situations → interpretations, and signals → decision → execution → outcome, as foreign keys only. It records what GeniOS concluded.
- **Admission:** `situation_publisher` returns ADMIT, HOLD or REJECT; a HOLD raises an EvidenceNeed.
- **Bounded query API:** seeds, hops, max nodes, unknowns and contradictions. It is bitemporal: when an event happened, when we learned it, and when it stopped being true.

## Cards — five lanes, a confidence vector

**Lanes:** decision · investigation · conflict · monitor · suppress (with a why-not receipt).
Uncertainty **routes** a finding to a lane; it never deletes it.

**Confidence vector:** evidence · frame · temporal · causal · authority · coverage. Each dimension gates a
different claim; there is no single scalar floor.

A card is a **living view** of one situation (versions, not new pings): what · why · now · evidence ·
unknowns · options · authority · actions · receipt.

## The model rules

The model may describe and propose: extract, detect, frame, hypothesise, word, parse a correction.
**It never scores, ranks, routes, chooses a recipient, grants a permission, does arithmetic, or writes to
the graph without validation.**

| Situation | Model calls |
|---|---|
| no material change | 0 |
| an exact rule or state transition | 0 |
| a routine situation | 1 |
| conflict or ambiguity | 2 |
| high-impact or irreversible | 2–3 |

## How today's code differs — what the rebuild changes

| | Today (old flow) | This architecture |
|---|---|---|
| Where a situation is born | `context/` forms and admits it **before** reasoning (`refresh_situations`, desk readings) | **L2** forms it from bundle + snapshot + expertise; L3 admits |
| L1 → L2 | per-event `qualified_signals` rows; bundles built and discarded | the **bundle** is the contract |
| L2's output | `ReasoningDecision` flattened into a `signals` row; **`ReasoningResult` does not exist** | **ReasoningResult** with lanes and confidence vector |
| Decision | none; **`DecisionObject` does not exist** | L3 mints it, L4 decides |
| Missing evidence | wait for the next sweep; EvidenceNeed has no fetcher | EvidenceNeed → L1 fetches it |
| Model on the decision path | expert pass bolted onto the old chain | one bounded pass inside the Orchestrator loop |

**Cutover rule (Atlas v2 L5):** the new path is built **beside** the old one; both run; the golden set
compares them; the switch happens only when the new path is at least as good.

**Build order:** L1 → L2 → L3 → L4 → L5 → L6, each layer judged against this page.

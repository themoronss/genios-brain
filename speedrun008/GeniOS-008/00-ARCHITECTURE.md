# GeniOS architecture — the one we build to

**Source:** Design Atlas v2 (29 Sep 2026). **Written for:** Rohit, Harsh and every coding agent. Every
layer folder in GeniOS-008 is judged against this page, never against what today's code happens to do.

**Amended:** 23 Oct 2026, with Rohit's yes (Rule 1.4): the goal object, `GoalImpact` and `GoalProposal`
([Goals](#goals--what-the-loop-works-toward), GeniOS-011 S26.U3).

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
| **L2 Reasoning** | `reason/` + `packs/` | What does it mean, and what is the best next move? | bundle + ContextSnapshot (with the live goals) + ExpertisePackage | **ReasoningResult** (with goal impacts and at most one goal proposal), EvidenceNeed, receipt | 0–3 bounded calls per situation | stores state, decides for a human |
| **L3 Context Graph** | `context/` | What does the company now know, and how is it connected? | ReasoningResult mutations and goal proposals, evidence facts | admitted situation (BSO), goal object and goal links, ContextSnapshot, **DecisionObject** | none | reasons by itself |
| **L4 Executive** | `executive/` | Who decides, and how does a decision become owned work? | DecisionObject | **ExecutionObject** (owner, deadline, channel, ladder) | wording only | a model deciding |
| **L5 Delivery** | `deliver/` | Who receives it, where, when, in what form? | ExecutionObject / ReasoningResult lane | card, brief, agent task, DeliveryResult | wording only, validated | adds a fact |
| **L6 Learning** | `feedback/` | What did reality teach, and which layer should change? | outcomes, judgments | mutes, pack config, brain proposals (data) | parse corrections only | edits code or the expert brain |

## Inside L1 — capture honestly

**Detailed spec: [`layer-1-enterprise-signals/05-BLUEPRINT-the-spec.md`](layer-1-enterprise-signals/05-BLUEPRINT-the-spec.md)** — groups G1–G7, units, contracts, algorithms, filters, acceptance tests.

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

**Detailed spec: [`layer-2-reasoning/05-SPEC-layer-2.md`](layer-2-reasoning/05-SPEC-layer-2.md)** (Rohit, 18 Oct). Its governing principle: **context-first, LLM-led.** The LLM is the reasoning engine (meaning, framing, history, patterns, consequences, next move); Plane D guides it, Plane R structures it, deterministic code only supports it (retrieval, IDs, permissions, integrity, exact numbers). The model judges in words with evidence, never an opaque score; routing, recipients, permissions and approvals stay outside it.

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
  - **goal impacts** (`GoalImpact`) and at most one **goal proposal** (`GoalProposal`), see [Goals](#goals--what-the-loop-works-toward);
  - EvidenceNeeds;
  - a provenance receipt.

## Inside L3 — trusted memory

- **Evidence Graph:** `graph_nodes`, `graph_facts`, `graph_edges`, with `authority_rank`. It records what the sources said.
- **Intelligence Graph:** situations → interpretations, and signals → decision → execution → outcome, as foreign keys only. It records what GeniOS concluded.
- **Admission:** `situation_publisher` returns ADMIT, HOLD or REJECT; a HOLD raises an EvidenceNeed.
- **Bounded query API:** seeds, hops, max nodes, unknowns and contradictions. It is bitemporal: when an event happened, when we learned it, and when it stopped being true.
- **Goals:** the goal object, its links to situations, and the admission of a goal proposal. See [Goals](#goals--what-the-loop-works-toward).

## Goals — what the loop works toward

*Amended 23 Oct 2026 (GeniOS-011 S26.U3). Rohit, 23 Oct, in chat: "aise bar bar goals manually nhi dal sakte
na" (we cannot keep adding goals by hand), and the Antler Singapore admission should have become a goal from
the context already in the graph. Recorded as GeniOS-009 `08-DECISIONS` D7 and D9–D12.*

GeniOS works *until the goal is reached*. So a goal is an object, every judgment says which goal it bears
on, and GeniOS proposes the goals it sees in motion. **A human makes a goal real.** Nothing a model or code
writes is ever an approved or active goal.

### The goal object (L3 owns it)

| Field | Meaning |
|---|---|
| `goal_id` | a stable id other layers point to (`goal:<id>` in a prompt) |
| `statement` | the goal in the founder's words, at most 200 characters |
| `status` | `proposed` → `approved` → `active` → `completed` · `superseded` · `cancelled` |
| `source` | `founder` (added by the founder) · `brief` (a drafter line the founder accepted) · `inferred` (a proposal still waiting) |
| `department` | a live domain of the tenant (D1) |
| `owner_seat`, `metric`, `target`, `deadline`, `parent_goal_id` | set by a person, or proposed and shown before approval; never chosen by a model |
| `subject_ref`, `evidence_refs` | for an inferred goal: the piece of work it rests on (`file:<id>`) and the lines it cites |
| `approved_by`, `approved_at` | the human who approved it. `approved` and `active` require it (a check constraint, not a convention) |

- **One goal per piece of work** (D10): an application, one raise, one hire, one partner. A broad goal
  ("Get into accelerator and incubator programs") stays; a goal for one piece of work may name it as its parent.
- **The door is the company brief** (D11). A goal is born when a brief `goals` line is accepted. A proposed
  goal is a pending brief line, and L3 syncs `company_goals` from the brief every sweep. One door, one approval
  path: `POST /v1/company-brief/proposals/{line_id}/decide`, owner only, one click.
- **Revisions:** every change to a goal is a new revision row, never an overwrite.

### `GoalImpact` (L2 writes it, L3 admits it as a link)

| Field | Meaning |
|---|---|
| `goal_ref` | a goal the dossier printed (block G); an unprinted goal is refused |
| `relation` | `advances` · `threatens` · `depends_on` · `unclear` — a word, never a score |
| `why` | the model's reading, in the founder's words |
| `evidence` | printed ids it rests on (`unclear` may stand on none) |
| `size_basis` | a printed tool line, or "not measurable" |

L3 writes a link (`goal_situation_links`) only when the situation is ADMITTED and the goal is live
(approved or active).

### `GoalProposal` (L2 proposes, L3 admits, a human approves)

| Field | Meaning |
|---|---|
| `statement` | the goal in the founder's words, at most 200 characters |
| `subject_ref` | the piece of work it is for (`file:<id>`): the judged subject itself, filled by code, never named by the model |
| `why` | why this is a goal the company is pursuing |
| `evidence` | printed ids; at least one is the company's own act (the founder applied, replied, met) |
| `parent_goal_ref` | optional: a live goal block G printed |
| `deadline`, `target`, `metric` | optional, and only as the dossier printed them |

- **At most one per judgment**, and none when a printed goal already names this work.
- **L3 admission** (`context/goal_admission`): ADMIT, HOLD or REJECT, by code. It holds a duplicate (the same
  work already has a pending, accepted or lately rejected goal, whoever proposed it), a proposal over the weekly
  cap (D12: 3 a week per tenant), and one with no evidence of the company's own act. An ADMIT writes a
  **pending** brief `goals` line with the structured fields. It never writes an approved or active goal.
- **The founder approves** on the card, on the home page or on the Goals page. Until then the goal is never
  printed to the model as the company's goal.

### Who may propose a goal

| Proposer | Reads | Status |
|---|---|---|
| the founder | — | adds a goal directly; it is approved in the same act |
| the brief drafter (`reason/brief_drafter`, weekly) | memory patterns, and since GeniOS-011 S27.U1 the files, open situations and in-motion lines; one goal per piece of work, refused when a goal already rests on that work | **built, the interim path** |
| the L2 judgment (R-9) | the whole dossier for one subject | planned: GeniOS-009 G1.6, G3.5, G4.5, G6.8 |

**Model rules for goals:** the model may propose a goal and word it. It never approves one, never chooses its
owner, never states a target or deadline the dossier did not print, and never marks one complete.

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
| Goals | free-text lines in the brief (`company_brief_lines`, section `goals`); no id, no link, no goal field in any judgment; only the weekly drafter proposes | a goal object in L3; L2 writes `GoalImpact` and `GoalProposal`; L3 admits; a human approves |

**Cutover rule (Atlas v2 L5):** the new path is built **beside** the old one; both run; the golden set
compares them; the switch happens only when the new path is at least as good.

**Build order:** L1 → L2 → L3 → L4 → L5 → L6, each layer judged against this page.

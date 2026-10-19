# L2 Reasoning — the plan

**Written for:** Rohit, Harsh and every coding agent. **Date:** 18 Oct 2026.

**Built to:**
- [`../00-ARCHITECTURE.md`](../00-ARCHITECTURE.md);
- the L2 spec [`05-SPEC-layer-2.md`](05-SPEC-layer-2.md) (Rohit's Layer 2 conversation, verbatim);
- the rules in [`../01-RULES.md`](../01-RULES.md).

**Starting point:** [`01-AS-IS.md`](01-AS-IS.md).

Every item below cites the spec section (`§`) or architecture section it implements. Nothing here is coded until
Rohit opens L2 for build.

---

## 0 · The principle L2 is built on (spec §"Context-First Reasoning Principle", §LLM roles)

> GeniOS must understand a company through its evolving context — not reduce it to predefined rules, formulas,
> fixed workflows or decision trees.

| | Does it | Does not |
|---|---|---|
| **The LLM** | Interprets meaning, frames the situation and its rivals, compares history and patterns, judges what matters, weighs consequences and options, and recommends the next move. **It is the reasoning engine.** | Approve, authorise, choose a recipient or channel, grant a permission, write to the graph without validation, invent a number |
| **Plane D (`packs/`)** | Gives the model what an expert knows: domain concepts, expected states, patterns *and* counter-patterns, past cases, evidence standards, the company's own knowledge (brief, brains, playbooks). **Guides interpretation; never predetermines the answer** | Act as a rulebook that decides |
| **Plane R (`reason/`)** | Gives the model *how* to think: the six groups (establish reality → understand → explain and anticipate → judge and choose → plan → verify) as reasoning capabilities the model executes | Act as a chain of formula units that decide |
| **Deterministic code** | Does retrieval, IDs, schema, permissions, versioning, idempotency, integrity, and **exact arithmetic when a numeric question really arises** (a date window, a reply time with its n, a sum). It is a *tool* the model reads | Decide meaning, importance, cause, priority or next move |
| **Validators** | Check that every claim cites evidence, quotes are in the source, numbers match their tool values, the facts / inferences / hypotheses / unknowns are kept apart, and authority boundaries hold | Guarantee semantic truth (golden tests and outcomes measure that) |

**How this sits with the architecture's model rules.**
- The architecture says the model never scores, ranks, routes or permits.
- Under this spec the model **does** judge materiality, priority and confidence, but in **words with evidence**: qualitative levels per confidence dimension, each with its reason and evidence. It never produces an opaque number.
- Routing, recipients, permissions and approvals stay outside the model, in L4 and L5.
- No dimension is combined into a weighted score without calibrated evaluation (spec §9).

---

## 1 · The L2 runtime — ten components (spec §12, §15.1)

| # | Component | Its job | Built from | Verdict |
|---|---|---|---|---|
| R1 | **Request Handler** | Validate the request: tenant scope, idempotency (request id + bundle hash), budgets, `eval_time` | `contracts/reasoning.py:728` ReasoningRequest | REUSE + new triggers |
| R2 | **Context Adapter** | Fetch a **bounded, frozen** ContextSnapshot from L3 and pin its revision. No live reads during the run | `context/bounded_read.read_bounded` (no caller today) + as-of | ADAPT |
| R3 | **History Assembler** (*proposed*, spec §7) | Assemble HistoricalContext: similar past situations, decisions, outcomes, the file's timeline, reply habits with their n | `context/workstream_timeline.py`, `file_judgments.py`, `file_outcomes.py`, expert dossier | ADAPT |
| R4 | **Expertise Resolver** | Return the version-pinned ExpertisePackage: domain knowledge, patterns and counter-patterns, cases, evidence standards, company brief, brains, playbooks | `packs/compiler/*`, `playbook_reader.py`, `platform/company_brief` | REUSE + fold in brief/playbooks |
| R5 | **Plan Compiler** | Decide the reasoning depth (shallow, standard, deep), which Plane R groups to activate, what to skip and why, budgets, and stop conditions | `reason/plan.py` ReasoningPlanner, `_ROSTER` | ADAPT |
| R6 | **Unit Runner** | Run the reasoning: the tools first, then the LLM judgment pass with the selected Plane R groups as its reasoning capabilities | `reason/expert/review.py` (the call), `prompt.py`, `dossier.py` | ADAPT |
| R7 | **Tool Gateway** | Controlled access to retrieval, graph lookups, dates, numbers with n, baselines, money. Read-only, on the frozen snapshot | `reason/baselines.py`, `context/workstream_numbers.py`, `kind_numbers.py`, `reason/bundle/numbers.py`, date logic in `reasoners/temporal.py` | ADAPT → one `reason/tools` |
| R8 | **Evidence Coordinator** | Raise EvidenceNeeds for decision-changing unknowns, track them, and re-enter reasoning **once** when the evidence lands (bounded, idempotent) | `contracts/evidence.py`; L1 executor `capture/acquire/need_executor.py` | BUILD |
| R9 | **Result Synthesizer** | Assemble one **ReasoningResult** from the pass and the tools | `contracts/expert_review.py:264` ExpertReview (already has facts / inferences / patterns / hypotheses / unknowns / frames / expected-vs-actual / scenarios / appraisal / mode / next move) | ADAPT → ReasoningResult |
| R10 | **Validators + Receipt Writer** | Run the claim check on every result, plus structure, provenance, time, authority. The receipt records inputs, versions, tool results, model + prompt version, validation, output hash | `reason/expert/verify.py`, `contracts/claim_check.py`, `reason/audit.py`, `reason/replay.py` | ADAPT + batch the writes |

**Hard boundary (spec §12).** No R-unit and no tool gets unrestricted database writes, network access or the system clock.
Everything arrives through the snapshot, the package, the tool gateway and `eval_time`.

---

## 2 · Data in and out (spec §5, §7, §11)

### In

| Object | What it carries | From |
|---|---|---|
| **ReasoningRequest** | request id, trigger, target entities / situation seed, question (new situation? update? conflict? next move?), domain/capability, permission scope, budgets, `eval_time`, pinned snapshot + package versions | the orchestrator (triggers: new bundle, new evidence, deadline crossed, expected reply absent, owner change, outcome, human ask) |
| **QualifiedEnterpriseSignalBundle** | signals with source ref, observed/event time, entities, claims, provenance, coverage receipt, unresolved | L1 (Group E, E1) |
| **ContextSnapshot** | related entities and relationships, active situations, commitments, owners, deadlines, dependencies, evidence refs, stale/conflicting marks, **revision** | L3 (bounded read) |
| **HistoricalContext** (*proposed*) | comparable past situations, what was decided, what happened, what differs now | L3 history + file timelines |
| **ExpertisePackage** | domain ontology, expected states, patterns and counter-patterns, cases, evidence standards, company knowledge (brief, brains), playbooks, **version + hash** | Plane D |
| **Coverage** | what was searched, what was not, freshness, sources not connected | L1 coverage receipts |

### Out

**ReasoningResult** (spec §11). It is a structured result, never free prose:

| Field | Meaning |
|---|---|
| `request_ref`, `context_ref`, `expertise_ref` | what was asked; which snapshot revision and package hash were used |
| `facts` | evidence-backed observations, each with evidence refs |
| `inferences` | conclusions drawn from facts, each with what it rests on |
| `hypotheses` | plausible, unconfirmed explanations, with supporting and counter evidence |
| `unknowns` | decision-relevant open questions, and why each matters |
| `frame`, `alternative_frames` | the primary reading of the situation and its rivals |
| `expected_vs_actual` | the expected state (from Plane D and company knowledge) against what is observed |
| `history_used` | which past cases were compared, and why they do or do not apply |
| `consequences` | first- and second-order effects, including doing nothing |
| `options` | alternatives with benefit, downside, reversibility, who is affected, and the evidence that would change the choice |
| `intervention_mode` | observe · monitor · gather evidence · clarify · contain · escalate · prepare decision · plan · verify · abstain |
| `best_next_move` | the move and its rationale |
| `decision_need` | does a human or authority have to decide, and who |
| `confidence` | six dimensions (evidence, frame, temporal, causal, authority, coverage), **each a level + its reason + evidence**; no composite number |
| `lane` | decision · investigation · conflict · monitor · suppress |
| `proposed_mutations` | situation create/update/merge/close and links, as **proposals** for L3 |
| `evidence_needs` | targeted retrieval requests |
| `coverage_limitations` | what was not seen |
| `receipt_ref` | the audit/replay record |

**Run-scoped only (never persisted as company state):** the ReasoningPlan, and the intermediate fragments of the pass
(`ReasoningFragments`). The **receipt** is durable. **Accepted company state** is L3's.

---

## 3 · How a run goes (spec §6, §4 "recommended call pattern", §8)

```
trigger → R1 request (idempotent; same request+bundle hash → same result, 0 work)
       → change gate (STEP-02): nothing material changed → receipt only, 0 model calls
       → R2 snapshot (bounded, pinned)  + R3 history  + R4 expertise package
       → R5 plan: depth + Plane R groups + budgets + stop conditions
       → R7 tools: dates, numbers with n, baselines, retrieval              (0 model calls)
       → R6 CALL 1 — the judgment pass                                       (1 model call)
       → R8 if a decision-changing unknown: EvidenceNeed → L1 fetch → re-enter
       → R6 CALL 2 — revision on the new evidence only                       (only when needed)
       → R10 validate every claim; an unresolved material issue → CALL 3     (optional)
       → R9 ReasoningResult + receipt → L3 (proposals) → L4/L5 by lane
```

### Depth (spec §8). The spec calls these "proposed operational policy", versioned and auditable.

| Depth | When | Plane R groups typically active | Model calls |
|---|---|---|---|
| none | duplicate or non-material change; exact state transition | — | 0 |
| shallow | low ambiguity, low impact | 1–2 | 1 |
| standard | several records, timing or dependencies | 1–4 | 1–2 |
| deep | contradiction, high impact, irreversible | 1–6, with counter-examples | 2–3 |

**How depth is chosen:**
- **Measurable inputs:** contradictions present, coverage gaps, number of linked situations, deadline proximity from the tools, and the impact markers in the package.
- **The model's own request:** the model may ask to go deeper, giving its reason.
- Both are recorded in the receipt.
- If the budget is spent, the run returns an incomplete result with its open EvidenceNeeds. It never forces a conclusion.

### Token planning (spec §6, *planning estimates, not measurements*)

| Profile | Input / call | Output / call | Calls |
|---|---|---|---|
| simple | 2k–5k | 300–800 | 1 |
| standard | 5k–12k | 700–1.8k | 1–2 |
| complex | 12k–25k | 1k–3k | 2–3 |
| deep | ≤ 40k across calls (later calls carry only new evidence) | 2k–5k total | 2–3 |

**Cost controls:**
- cache the stable prefix (instructions + expertise package);
- send evidence as excerpts with source ids;
- give later calls only what changed;
- ask for structured, non-verbose output;
- record per call: tokens in/out, latency, retries, outcome.

### Model routing (spec §9). Capability-based, benchmarked; never random.

| Work | Default |
|---|---|
| L1 extraction | Haiku-class |
| L2 judgment pass, routine and standard | Sonnet-class (`claude-sonnet-5`, as the expert pass runs today) |
| L2 deep or contested | the strongest class, only when the golden set shows it earns its cost |

**Thinking budget.** Claude 5 thinks by default and thinking eats `max_tokens`, so every site sets an explicit thinking budget (memory: STEP-12 R-2 truncation).

### One run, not many agents (spec §9 "multi-agent")

- Start with one orchestrated runtime: Plane R groups are sections of the pass, not separate agents.
- Run parallel perspectives (for example technical vs commercial vs compliance) only when they are genuinely independent and the golden set proves they help.

---

## 4 · What the model is asked, and how it must think (spec §7 "LLM ko kaise sochna chahiye")

**The prompt carries six blocks**, each labelled by kind:
1. **A** the current signals with evidence anchors;
2. **B** the context snapshot (and its revision);
3. **C** the expertise package (and its hash);
4. **D** the question;
5. **E** coverage — what was searched, what was not;
6. **F** the output contract.

**Five kinds of statement are never mixed** (spec §9): observed evidence · reported claim · inference · hypothesis · unknown.

**The reasoning the model performs** (spec §7 cycle). These are capabilities, not a fixed pipeline:

1. **Observe:** what is present, direct vs reported.
2. **Contextualise:** history, relationships, commitments, goals; what context is missing or stale.
3. **Frame competing interpretations:** never settle on the first.
4. **Test:** counter-evidence. Are past cases really comparable? Which unknown would change the conclusion?
5. **Anticipate and compare:** do nothing vs each option; who is affected; what cannot be undone.
6. **Recommend:** the next move. Act now, get more evidence, or hand to a human?
7. **Revise and hand off:** what changed with new evidence; is it ready for L3; does L4 need to decide?

**Absence is never a fact without coverage** (spec §9). "Not found in the searched scope; WhatsApp not connected" is a
finding. "It did not happen" is not.

**Patterns are evidence, not laws** (spec §"Context-First"). The model must say why a past case does or does not apply now
(spec §6, Situation C: the old risk pattern no longer applies because scope and deadline changed).

**No raw chain-of-thought is stored.** The receipt keeps an auditable rationale: which evidence led to which conclusion,
which alternatives were considered, what stayed uncertain.

---

## 5 · Validation and failure (spec §16, §15)

**Validators:**

| Validator | What it checks | Kind |
|---|---|---|
| structure | schema, required fields, enum values, ids resolve | deterministic |
| provenance | every material claim cites evidence that exists in the snapshot/bundle; quotes are in the source (STEP-13) | deterministic + text match |
| numbers | every number equals its tool value with unit and n (STEP-13) | deterministic |
| time | dates and sequence consistent with the evidence and `eval_time` | deterministic |
| epistemic | facts, inferences, hypotheses and unknowns not collapsed; absence claims carry coverage | rule on the output shape |
| authority | the next move stays inside what GeniOS may do; anything needing approval sets `decision_need` | deterministic |

**Failure handling (spec §16, §15):**

| Failure | Behaviour |
|---|---|
| ambiguous entity | return candidates; abstain or send to human review |
| source unavailable | record a coverage limitation; never turn absence into a fact |
| contradictory evidence | keep the conflict; weigh authority, freshness and supersession; the conflict lane |
| expertise missing | limited reasoning, labelled; no unsupported domain conclusion |
| malformed model output | one bounded repair, then a failure status (never a forced result) |
| claim without evidence | dropped or downgraded to hypothesis or unknown, per line, never the whole result |
| budget exhausted | partial result + open EvidenceNeeds |
| snapshot moved | the stale run is detected; re-run on the new revision |
| mutation conflict | L3 compare-and-set; never a silent overwrite |
| validators disagree | `review_required`; no forced conclusion |

---

## 6 · How we measure it (spec §16 "measure", §10 evaluation)

The golden set (53 founder cases + Atlas replays) runs the old and the new path side by side, and adds the spec's scenario kinds:
- same email, different history;
- similar history, different cause;
- conflicting stakeholders;
- missing data that must not become absence;
- stale status vs recent evidence;
- the right answer is "investigate";
- the first reading must change when new evidence lands.

**Scored on:**
- evidence faithfulness;
- framing quality;
- use of history;
- uncertainty and contradiction handling;
- decision usefulness;
- over-escalation and misses;
- cost and latency per situation;
- replayability.

There are no target numbers before a measured baseline (spec §16).

---

## 7 · The build, in order (spec §17 build sequence + the migration rules)

Each unit is one change with its own test and a mutation check. The suites run in CI. Each pushed group writes its
section in [`04-FOR-HARSH.md`](04-FOR-HARSH.md). The new path runs **in shadow** until the golden set says it is at
least as good (`01-RULES` Rule 2).

| Group | Unit | What | Cites | Depends on |
|---|---|---|---|---|
| **A · Contracts** | L2-A1 | `ReasoningResult` (fields in §2), generalised from `ExpertReview` | §11 | — |
| | L2-A2 | `HistoricalContext`, `ReasoningFragments` (run-scoped), `ReasoningReceipt` v2 (versions, skipped groups + reasons, tool results, model/prompt, validation, retrieval attempts, termination reason) | §7, §14 | — |
| | L2-A3 | `ReasoningRequest` triggers: bundle, new evidence, deadline crossed, expected reply absent, owner change, outcome, human ask | §5 | — |
| | L2-A4 | `confidence`: six dimensions, each level + reason + evidence | §9 | — |
| **B · Context assembly** | L2-B1 | Context Adapter: snapshot through `read_bounded` (seeds, hops, max nodes, revision, as-of, unknowns, contradictions) | §5 input 2 | L3 snapshot API |
| | L2-B2 | History Assembler → `HistoricalContext` | §7 | L2-A2 |
| | L2-B3 | Expertise Resolver: package carries patterns *and* counter-patterns, cases, evidence standards, company brief, brains, playbooks — one versioned package | §4 Plane D | — |
| | L2-B4 | Tool Gateway `reason/tools`: dates/windows, numbers with n, baselines, money, retrieval — read-only on the snapshot | §8 | — |
| **C · Orchestrator** | L2-C1 | Plan Compiler: depth from measurable inputs + the model's request; groups selected; skips with reasons; budgets; stop conditions | §8 | A1–A4 |
| | L2-C2 | Change gate reused at the front (STEP-02) | — | — |
| **D · The judgment pass** | L2-D1 | Generalise the expert pass from *file* to *situation/bundle*: dossier → the six labelled blocks (§4); Plane R groups as reasoning sections; output = ReasoningResult | §4, §7 | A, B, C |
| | L2-D2 | Model routing and thinking budget per depth; prompt caching of the stable prefix; per-call cost record | §6, §9 | D1 |
| **E · Evidence loop** | L2-E1 | Evidence Coordinator: raise EvidenceNeed (question, why it matters, sources, window, required evidence, stop conditions, idempotency key); one bounded re-entry | §10 | L1 E2 fetchers |
| **F · Validation** | L2-F1 | Claim check (STEP-13 `verify.py`) on every ReasoningResult, per line | §15 | D1 |
| | L2-F2 | structure, time, epistemic and authority validators; `review_required` on disagreement | §15, §16 | D1 |
| **G · Handoff** | L2-G1 | Store ReasoningResult + receipt (shadow table); batched writes, one transaction per sweep | §14 | A |
| | L2-G2 | Proposed mutations handed to L3 admission (L3 builds the gate) | §11 | L3 |
| | L2-G3 | Replay from the receipt with no model call | §14 | G1 |
| **H · Demote and retire** | L2-H1 | The 23 deterministic reasoners: keep what is a tool (date windows, numbers) behind R7; their scores stop deciding anything | Context-First §3 | D1 |
| | L2-H2 | Retire `llm_decision_maker` / R-1 (folded into the pass) | §7 | cutover |
| | L2-H3 | Retire the legacy per-pack rule lane at cutover | — | cutover |
| **I · Shadow + switch** | L2-I1 | New path in shadow beside the old; golden set scores both | Rules 2 | A–G |
| | L2-I2 | First switch: awaiting reply / outreach (the investor, intro and incubator cases) | Rules 2 | I1 + L3 admission |

### What L2 waits on from other layers

| From | What |
|---|---|
| L1 | E1 the stored bundle; E2 the EvidenceNeed fetchers; E8 the carried fields |
| L3 | the bounded, as-of snapshot API; admission that gates existence (ADMIT / HOLD / REJECT on L2's proposals) |
| L5 | the card rendered from the ReasoningResult's lane |

---

## 8 · Not doing (and why)

- **No fixed decision trees, rule scores or formula priorities as the reasoning.** This is spec §"Context-First".
- **No agent-per-unit, and no call per unit.** Spec §4 ("call pattern") and §9 ("multi-agent").
- **No whole-corpus or whole-graph prompts.** The context is bounded and relevant (spec §5).
- **No raw chain-of-thought stored.** Auditable rationale only (spec §7).

# Layer 4 v2 — Overview, Doctrine, and the Expected-vs-Actual Alignment

> **Read the L1/L2/L3 overviews first.** L4 is where their supply chains converge: L1's
> importance, L2's situations and analytics, L3's knowledge — all of it exists to feed a
> decision, and today the decision engine cannot hear any of it.

---

## 1. What Layer 4 is

> **Layer 4 answers: what should happen?** It weighs evidence, applies constraints, ranks
> candidates, commits to one action with a confidence — and **explains the whole chain in
> the founder's language.**

| | |
|---|---|
| **Name** | Reasoning Engine |
| **Package** | `genios_engine/reason/` |
| **Input** | `BusinessSituationObject` (L2) + `ExpertisePackage` (L3) |
| **Output** | `DecisionObject` + **`ReasoningBundle`** (new) |
| **Hard rule** | L4 never knows a domain — domain vocabulary lives in L3 manifests |
| **Plan type** | **awaken + give it ears and a voice** (L1 = build · L2 = missing stratum · L3 = unlock) |

Nothing in L4 is missing as a file. The machinery is the best-engineered code in the
repository. It is **dormant, deaf and mute**, and this plan fixes exactly that.

---

## 2. THE ALIGNMENT — what is expected vs what we have vs what we build

Every row verified against HEAD (greps and reads, not inference). This is the table to
read before anything else in this folder.

### Group L4.1 — Reasoning Orchestrator (7 components)

| # | Globe expects | Code today | v2 builds | Doc |
|---|---|---|---|---|
| 1 | Unit Selector — picks relevant units per situation | exists, deterministic, receipted — **on in ZERO manifests** | turn it on; it becomes the roster mechanism | 01 C1 |
| 2 | Execution Planner — stages, budgets, hashes | ✅ **excellent** — pure, hashed, latency-refused | **preserve hard**; tune declared budgets only | 01 C2 |
| 3 | Dependency Resolver — topological order | ✅ excellent | preserve hard | 01 C3 |
| 4 | Parallel Scheduler — concurrent independent units | **sequential**, deliberately (determinism) | **deviation kept and documented** | 01 C4 |
| 5 | LLM Decision Policy — when a model may be consulted | **no LLM anywhere in reason/** | the R-site gate: interpret + narrate only | 01 C5 |
| 6 | Confidence Policy — floors, silence | floor **defaults 0** on the compiled lane → never fires | floor operational per lane | 01 C6 |
| 7 | Fallback Strategy — reserve units on failure | machinery unused | **stated decision: stays dormant**; 3 live mechanisms named | 01 C7 |

### Group L4.2 — Reasoning Units (Globe: 17 · registry: **22**)

| Globe expects | Code today | v2 builds | Doc |
|---|---|---|---|
| 17 units run per their dependency families | **6 units** hardcoded on the compiled lane; **10 unreachable anywhere**; full-roster v2 authored and never swept | full staged roster through the selector | 02 U1 |
| Units compute domain-free | sales vocabulary hardcoded in opportunity/risk/resource | declared-field reads; a grep test per unit | 02 U3 |
| Tradeoff reads a cost axis | `cost_source` defaults to **`core.effort` — a unit that does not exist** | point at `core.cost` + registration-time check | 02 U4 |
| Urgency from timeline analysis | `core.timeline` never publishes `urgency_bp`; priority falls back to **NEUTRAL 5000** | urgency ladder published by `core.timeline` | 02 U5 |
| A defined roster | **22 registered ids** — 16 full units, 5 thin shims, 2 legacy | roster declared, shims dispositioned | 02 §2 |

### Group L4.3 — Evidence Layer (3 components)

| Globe expects | Code today | v2 builds | Doc |
|---|---|---|---|
| Evidence Schema: unit_ref, claim, value | evidence is **input** minted by adapters; `Finding` has no `value_bp` | `Finding` canonized as the per-unit emission | 03 S1 |
| Evidence Builder: one identity per fact | **three builder sites, three id seeds** | one `build_evidence_ref()` | 03 S2 |
| Evidence Store: content-addressed, replayable | ✅ **excellent**, hash-verified | preserve + digest beyond the 720h TTL | 03 S3 |

### Group L4.4 — Decision Maker (7 components)

| Globe expects | Code today | v2 builds | Doc |
|---|---|---|---|
| Ranker weighs importance | **`importance_bp` has zero readers in `reason/`** | importance as the 6th utility component | 04 E1 |
| The formula decides | `priority_override` **replaces** it — the formula has never once decided | override demoted to a 70/30 prior, divergence recorded | 04 E1 |
| Rule 11: confidence rises only with named independent evidence | **last-writer scan** — any later unit raises it, uncited | Rule 11 composition (raw material already published by `core.confidence`) | 04 E2 |
| Silence is a valid output | floor dead on the compiled lane | floor set; reason-coded DEFER | 04 E3 |
| "Cost of doing nothing" computed | **static manifest string**; `core.cost` never runs | computed from `do_nothing_cost_bp` | 04 E4 |
| Evaluator eliminates on constraints | ✅ **chain fully built** — `alternatives_rejected` works | + the `compiled_constraints` mapping | 06 S3 |
| Reasoning Trace | ✅ exists | bundle extends it | 04 C7 |

### Group L4.5 — Reasoning Bundle (**new group — the voice**)

| The founder's bar (Theory chat) | Code today | v2 builds | Doc |
|---|---|---|---|
| WHY THIS MATTERS / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT | **one sentence, no directives, no numbers** — the bar is structurally impossible | the typed `ReasoningBundle` + the V-gauntlet | 05 |
| "LLM interprets ambiguity → rules/math decide" | deterministic half built; **interpret/narrate half has zero sites** | R-1..R-5, decision fixed first | 05 |

---

## 3. The doctrine — decided with the founder, grounded in the Theory chat

> ## The LLM may INTERPRET evidence and NARRATE reasoning.
> ## It may never CHOOSE, SCORE, or PERMIT.

| Work | Owner |
|---|---|
| Unit computation — timeline math, impact, cost, dependency chains | deterministic formulas |
| Orchestrator routing — which units, what order | deterministic — plan DAG + selector |
| Score, rank, priority, permission, policy, elimination | **deterministic — the decision stays deterministic** |
| Confidence composition | deterministic (Rule 11) |
| Ambiguity interpretation | ✅ LLM → **typed evidence**, never a verdict |
| **Reasoning narrative — the user-facing detail** | ✅ LLM, **after** the decision is fixed |
| Alternatives / tradeoff narration, polish | ✅ LLM |

Today's L4 is **more deterministic than the founder asked for**, and mute because of it.

### MAP A — LLM sites (R-series)

| ID | Site | What | When | Tier |
|---|---|---|---|---|
| **R-1** | Ambiguity interpreter | *"considering moving workloads"* → `{classification, confidence_bp}` **as evidence** | gated by C5; genuine ambiguity only | T2 |
| **R-2** | 🔴 **Reasoning Bundle narrative** | scenario → why it matters → root cause → recommendation rationale → expected effect | **after** the decision is fixed, per published decision | T2 |
| **R-3** | Alternatives narration | why option B lost — from `alternatives_rejected` + tradeoff evidence | card expand / on demand | T1 |
| **R-4** | Expected-effect framing | `do_nothing_cost_bp` + foresight → one framed statement, numbers templated | with R-2 | T1 |
| **R-5** | Low-confidence consult | targeted interpretation when evidence is thin | DEFER-to-human stays default; recorded non-authoritative | T2 |

**Standing guards on every R-site:** decision fixed first · every claim evidence-bound ·
**numbers templated, never generated** · deterministic template fallback · cached on
decision hash. **MAP B — embeddings: none**, as everywhere in v2.

### MAP D — Algorithms (DLG-series)

| ID | Algorithm | Status | Doc |
|---|---|---|---|
| DLG-01 | Plan DAG + staging + latency refusal | ✅ preserve hard | 01 |
| DLG-02 | Context-aware unit selection | ✅ exists, **dormant — turn on** | 01 |
| DLG-03 | **Utility with importance** + override demotion | 🆕 | 04 |
| DLG-04 | **Urgency derivation** from validated dates | 🆕 | 02 |
| DLG-05 | **Rule 11 confidence composition** | 🆕 | 04 |
| DLG-06 | BSO→snapshot projection | 🆕 | 06 |
| DLG-07 | compiled_constraints → CandidateCheck | 🆕 (chain exists) | 06 |
| DLG-08 | do_nothing composition from computed cost | 🆕 | 04 |
| DLG-09 | Book-level brief re-rank (E3) | 🆕 | 06 |
| DLG-10 | ExternalCandidate scoring + critique (E1) | 🆕 | 06 |
| DLG-11 | Evidence-ref unification | 🆕 | 03 |

---

## 4. The five laws of Layer 4

1. **One decider.** `DecisionMaker.decide()` stays the sole synthesis authority.
2. **The decision is fixed before any narrative exists.** A bundle whose action does not
   id-match the decision is a **constructor error**, not a review nit.
3. **Silence is operational on every live lane.** A floor that defaults to 0 is not a floor.
4. **Confidence obeys Rule 11.** Falls freely; rises only with named cross-group evidence.
5. **No domain vocabulary in core units.** Domain readings live in L3 manifests.

---

## 5. Document index

| Doc | Group / contents |
|---|---|
| `00-Overview-and-Doctrine.md` | this file — **the alignment table lives here** |
| `01-Group-L4.1-Reasoning-Orchestrator.md` | 7 components: selector, planner, resolver, scheduler, LLM policy, confidence policy, fallback |
| `02-Group-L4.2-Reasoning-Units.md` | **the roster** — 22 registered ids unit-by-unit, what each publishes, what changes |
| `03-Group-L4.3-Evidence-Layer.md` | schema · builder · store |
| `04-Group-L4.4-Decision-Maker.md` | 7 components — **the ears**: importance, Rule 11, floor, do-nothing |
| `05-Group-L4.5-Reasoning-Bundle.md` | **the voice** — R-sites, the V-gauntlet, the card |
| `06-Seams-In-and-Out.md` | L2/L3 in · critique (E1) + brief (E3) out |
| `07-Contracts.md` | ReasoningBundle · ExternalCandidate · BriefRanking · `l4_activation` |
| `08-Build-Order-and-Acceptance.md` | waves Z0–Z7, gates K0–K7, preserve-hard list |
| `09-Edge-Cases-and-Loops.md` | 15 R-site cases · 6 loops · convergence |
| `10-Worked-Examples.md` | the two Theory-chat traces, end to end |
| `11-Cost-Model-and-Budget-Guards.md` | per-decision and per-tenant LLM spend, guards |
| `12-CTO-Handoff-Note.md` | copy-paste brief for the coding agent |

**Companions:** `../06-Gap-Audit-L4-Spec-vs-Code.md` (the evidence) ·
`../07-Plan-Crosscheck-L4.md` (this plan audited against Globe + the Theory chat)

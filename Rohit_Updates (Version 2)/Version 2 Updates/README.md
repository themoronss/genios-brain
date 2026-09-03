# Version 2 Updates

**Status:** active
**Started:** 2026-09-03
**Predecessor:** `../Version 1 Updates/` (frozen, read-only reference)

---

## What Version 2 is

Version 1 audited the system **as specified** — the Secret War audit measured the code
against the GeniOS Globe architecture and produced a gap list.

Version 2 **rebuilds, layer by layer**, starting from Layer 1. Each layer gets a
complete plan: every group, every component, every unit, with the algorithm, the storage
target, the LLM decision, the failure modes, the acceptance command, and a copy-paste
reverse prompt for a coding agent.

**The build discipline is reverse engineering:**

> units -> components -> groups -> layer.
> A parent is never built before its children are green.

---

## The doctrine change that defines Version 2

Version 1 treated Layer 1 as *mostly deterministic with selective LLM*. That was too
conservative. Layer 1's actual job is **raw enterprise data -> high-quality structured
enterprise signals**, and turning unstructured human communication into structure is
precisely what a language model is for.

> **Version 2 doctrine:**
> **LLM understands the data. Deterministic systems make that understanding usable and trustworthy.**

**LLM budget by layer:**

| Layer | Usage |
|---|---|
| **L1** | **HEAVY** — semantic extraction is the core |
| L2 | **JUDGMENT, not extraction** — 9 gated sites. The *measurement* (trend/percentile/anomaly) stays deterministic for comparability |
| L3 | **ZERO at compile-time** (reproducibility: same situation + snapshot = byte-identical package) · **5 offline sites** N-1..N-5 — authoring, review-assist, org discovery, behavior distillation, gap drafting — all human/floor-gated |
| L4 | **INTERPRET + NARRATE, never choose/score/permit** — 5 R-sites: ambiguity-as-evidence, the Reasoning Bundle narrative, alternatives, expected-effect, gated consult |
| L5 / L5.2 | prose only |
| L6 | feedback parsing only |

**The one hard prohibition:** the model may **describe**, never **score**. A score feeds
ranking, and ranking must be byte-identical across machines and replays.

---

## Layer plans

| Layer | Plan | Status |
|---|---|---|
| **L1 Knowledge** | `01-Layer-1-Plan/` | ✅ **complete — 11 documents** |
| **L2 Context** | `02-Layer-2-Plan/` | ✅ **complete — 10 documents** |
| **L3 Domain Expertise** | `03-Layer-3-Plan/` | ✅ **complete — 8 documents** |
| **L4 Reasoning** | `04-Layer-4-Plan/` | ✅ **complete — 9 documents** |
| L5 Executive | `05-Layer-5-Plan/` | not started |
| L5.2 Delivery | `06-Layer-5.2-Plan/` | not started |
| L6 Learning | `07-Layer-6-Plan/` | not started |

---

## Layer 1 plan — document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | the four stages, and the four maps: **LLM · embeddings · storage · algorithms** |
| `01-Group-L1.1-Enterprise-Sources.md` | 16 categories, connector priority by unlocked intelligence |
| `02-Group-L1.2-Knowledge-Connectors.md` | 6 components — backfill window, webhook parity, cadence |
| `03-Group-L1.3-Deterministic-Extraction.md` | 8 components — stage S1, structural parser |
| `04-Group-L1.4-Semantic-Extraction-Engine.md` | 10 components — **stage S2, the new core** |
| `05-Group-L1.5-Validation-and-Normalization.md` | 8 components — **stage S3, trust and conflict detection** |
| `06-Group-L1.6-ESQE-Qualification.md` | 10 components — **stage S4, importance scoring** |
| `07-Group-L1.7-Knowledge-Storage.md` | 5 components — stores, retention, cascade |
| `08-Contracts-QualifiedEnterpriseSignal.md` | 12 typed objects at the L1 seam |
| `09-Build-Order-and-Acceptance.md` | 10 waves, dependency graph, acceptance gates G0–G10 |
| `10-CTO-Handoff-Note.md` | **copy-paste brief for the coding agent** |

Plus:
- `02-Gap-Audit-L1-Spec-vs-Code.md` — the 48-component audit that produced this plan
- `03-Plan-Crosscheck-and-Corrections.md` — the L1 plan audited against Globe, the customer
  bar, our design conversation and itself. **9 findings, 2 critical, all fixed before commit.**
- `04-Gap-Audit-L2-Spec-vs-Code.md` — the 43-component Layer 2 audit
- `05-Gap-Audit-L3-Spec-vs-Code.md` — the 13-component Layer 3 audit (**the unlock layer**)
- `06-Gap-Audit-L4-Spec-vs-Code.md` — the 34-component Layer 4 audit (**dormant, deaf, mute**)
- `07-Plan-Crosscheck-L4.md` — the L4 plan audited against Globe + the Theory-chat MD (caught **P-2: core.policy missing from the DAG** before a line of code)

## Layer 2 plan — document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | 4 laws + the four maps. **L2 v2 has ZERO required LLM sites** |
| `01-Group-L2.1-Enterprise-Context-Graph.md` | 8 views, incl. the **missing Authority view** |
| `02-Group-L2.2-Graph-Engines.md` | 8 components, incl. **point-in-time graph read** |
| `03-Group-L2.3-Cross-Correlation.md` | 8 correlators, incl. the **3 missing** |
| `04-Group-L2.4-Analytic-Stratum.md` | **8 components — ENTIRELY NEW, the core of L2 v2** |
| `05-Group-L2.5-Context-Quality.md` | 8 components, incl. **typed absence** |
| `06-Group-L2.6-Situation-Candidate-Generator.md` | subgraph **pattern registry** |
| `07-Group-L2.7-Business-Situation-Engine.md` | **the importance fix — the L4 unlock** |
| `08-Contracts-BusinessSituationObject.md` | 9 typed objects; 8 law-carrying validators |
| `09-Build-Order-and-Acceptance.md` | 8 waves X0–X8, gates H0–H8 |
| `10-CTO-Handoff-Note.md` | copy-paste brief for the coding agent |
| `11-Cost-Model-and-Budget-Guards.md` | **cost drivers, per-site budgets, fail-closed fallbacks** |
| `12-LLM-Edge-Cases.md` | **28 named failure cases across the 9 sites** |
| `13-Loops-and-Convergence.md` | **5 loops, bounded fixpoint, `coverage_epoch`, holiday-vs-broken-coverage** |
| `14-Worked-Example-End-to-End.md` | **one situation through every group** |

**Layer 2 v2 totals:** 7 groups · **51 components** · **19 algorithms** · **9 gated LLM
sites** · 0 embeddings · 8 waves · 28 named edge cases.

### The Layer 2 line

Deterministic code can only **check what is or is not there**. It cannot **construct**
meaning — and half of Layer 2's job is construction. So the line is drawn on output type,
not on layer:

> **In L2 the LLM may judge a RELATIONSHIP, a STATE, or frame a NARRATIVE.
> It may never produce a NUMBER.**

Both halves matter. *"This account is in the bottom decile of its cohort and has declined
three months running"* is a **discovered pattern computed by arithmetic** — no model, fully
reproducible, every input citable. But deciding that the situation is **over** because
someone wrote *"all sorted, we signed yesterday"* is **construction**, and no rule will
ever do it. Today L2 has only two resolution paths — one CRM field and a human click — so a
stated resolution makes a situation look *more* active. That is a nagging machine, and it
is what LLM site **M-4** exists to fix.

**Why the measurement stays deterministic:** if a trend were judged by a model in March and
again in September, a disagreement could not be attributed to the business or to the model.
Comparison needs a stable measuring instrument. That is structural, not doctrinal.

## Layer 3 plan — document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | 5 laws · **an UNLOCK plan, not a rebuild** · LLM: 0 compile-time, 5 offline sites |
| `01-Group-L3.1-Domain-Compiler.md` | 9/9 built — preserve-hard list + analytic predicates + pattern_id routing |
| `02-Group-L3.2-Four-Brains.md` | **storage DDL, write governance, update triggers, N-3/N-4 content pipelines** |
| `03-Group-L3.3-Typed-Consumers.md` | **the weld fix — 446 unconsumable artifacts get consumers** (CLG-06/07/08) |
| `04-Group-L3.4-Admin-Corpus-V1.md` | route the 21 unrouted · author Globe #13/#14 · defer facilities/travel |
| `05-Contracts-ExpertisePackage.md` | additive package extensions · `l3_activation` |
| `06-Build-Order-and-Acceptance.md` | waves Y0–Y5, gates J0–J5 |
| `07-CTO-Handoff-Note.md` | copy-paste brief for the coding agent |

**Layer 3 v2 totals:** 4 work groups · 13 Globe components (9/9 compiler built) · **446
artifacts unlocked** · 5 offline LLM sites · **0 compile-time LLM** · 6 waves.

### The Layer 3 line

> **The compiler is built, the corpus is good, the governance is better than the spec —
> and the switch is off.** L3's plan is an unlock: typed consumers first (or activation
> fakes success), then per-tenant flip, then feed the three empty brains from what L1
> extracts (policy docs → Organization) and what L2.4 measures (behavior patterns →
> Behavior). Who decides a brain update was never the gap — L6's promotion pipeline with
> deterministic floors already exists. The gap was that nothing ever proposed.

## Layer 4 plan — document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | 5 laws · the R-sites · four flows this plan opens |
| `01-Group-L4.1-4.2-Orchestrator-and-Units.md` | **wake the roster** — 10 unreachable units go live via the dormant selector |
| `02-Group-L4.4-Decision-Maker.md` | **the ears** — importance term, override demoted, Rule 11, operational silence, computed do-nothing |
| `03-Reasoning-Bundle-and-R-Sites.md` | **the voice — the centerpiece**: WHY / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT, evidence-bound, numbers templated |
| `04-Evidence-and-Seams.md` | evidence shape fix · BSO projection · compiled_constraints consumer · **agent critique (E1)** · **book-level brief (E3)** |
| `05-Edge-Cases-Loops-Scenarios.md` | 15 R-site cases · 6 loops · the two Theory-chat traces completed |
| `06-Contracts.md` | ReasoningBundle · ExternalCandidate/CritiqueVerdict (advisory locked) · BriefRanking |
| `07-Build-Order-and-Acceptance.md` | waves Z0–Z6, gates K0–K6 — **K1 closes the G7→H5→K1 ranking chain** |
| `08-CTO-Handoff-Note.md` | copy-paste brief |

**Layer 4 v2 totals:** 34 Globe components audited (10/17 units unreachable today) ·
**5 R-sites** · 11 algorithms (DLG) · 7 waves · the two flagship gates: **K1** (the
formula finally decides) and **K4** (the founder-bar card).

### The Layer 4 line

> **The LLM may INTERPRET evidence and NARRATE reasoning. It may never CHOOSE, SCORE,
> or PERMIT.** The decision is fixed first; the Reasoning Bundle describes it and cannot
> amend it (constructor-enforced); every number in the prose is a placeholder
> substituted from computed values. L4 today is dormant (10/17 units never run), deaf
> (importance_bp has zero readers in reason/), and mute (one validated sentence, no
> directives, no numbers). The plan wakes it, gives it ears, and gives it the voice the
> customer is actually paying for.

**Layer 1 v2 totals:** 7 groups · **65 components** · **23 algorithms** · 5 LLM sites ·
0 embeddings · 10 build waves · 13 reverse prompts.

---

## The three things Layer 1 v2 fixes

**1. Ranking works.**
L1 stamps no `importance_bp` today, so L4's utility formula has nothing to score with
and falls back to an override. `reason/decision_maker.py:243` records it: *"the formula
has never once decided anything."* Two different tenants currently receive identical
rankings. Wave W7 closes this.

**2. Details survive.**
Extraction loss happens after the model, not at it: an 8000-char truncation, a 34-value
vocabulary, and — the real ceiling — a vocabulary derived from *what the rules already
consult*, so the extractor may only look for patterns somebody already wrote a rule for.
Wave W3 breaks that circle and adds the **open lane** for observations that have no name yet.

**3. A confident wrong number is caught.**
Evidence spans are validated against the source (anti-hallucination), and when a signed
document says \$74K while an email says \$84K, both are retained and the disagreement is
surfaced rather than silently resolved. Waves W1 and W5.

---

## Standing rules for every Version 2 plan

1. **No global boolean cutover flags.** Activation is per-tenant, in a table, with an
   owner and a date. `platform/config.py:110` carries `use_domain_compiler=False`, set in
   no environment, which has left 152 authored capabilities dark. Do not build a second one.
2. **"Built but not enabled" is not done.** A unit is done when its acceptance command
   passes against a real tenant with activation on.
3. **A skip is not a pass.** Every wave has an acceptance command with an expected result.
4. **Every claim names its receipt.** A derived value without an evidence pointer is not
   publishable.
5. **Integer basis points everywhere.** No float crosses a boundary.

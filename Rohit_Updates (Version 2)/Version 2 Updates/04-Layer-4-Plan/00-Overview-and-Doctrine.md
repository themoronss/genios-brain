# Layer 4 v2 — Overview and Doctrine

> **Read the L1/L2/L3 overviews first.** L4 v2 is where their supply chains converge:
> L1's importance, L2's situations and analytics, L3's knowledge — all of it exists to
> feed a decision, and today the decision engine cannot hear any of it.

---

## 1. What Layer 4 is

**Definition**

> Layer 4 answers: **what should happen?** It weighs evidence, applies constraints,
> ranks candidates, commits to one action with a confidence — and can **explain the
> whole chain in the founder's language.**

**Name:** Reasoning Engine
**Package:** `genios_engine/reason/`
**Input:** `BusinessSituationObject` + `ExpertisePackage`
**Output:** `DecisionObject` — now carrying a **Reasoning Bundle**
**Hard rule:** L4 never knows a domain. (Violated today — see doc 01.)

### What kind of plan this is

| Layer | Plan type |
|---|---|
| L1 | build |
| L2 | missing stratum |
| L3 | unlock |
| **L4** | **awaken + give it ears and a voice** |

Nothing is missing as a file. The work: **wake** the dormant roster and selector, **open
the ears** to the v2 supply chain, make **silence operational**, install **Rule 11**
confidence, and build the **voice** — the reasoning narrative.

---

## 2. The doctrine — decided with the founder, grounded in the Theory chat

> ## The LLM may INTERPRET evidence and NARRATE reasoning.
> ## It may never CHOOSE, SCORE, or PERMIT.

| Work | Owner |
|---|---|
| 17 units' computation — timeline math, impact, cost, dependency chains | deterministic formulas |
| Orchestrator routing — which units, what order | deterministic — plan DAG + selector |
| Score, rank, priority, permission, policy, elimination | **deterministic — the decision stays deterministic** |
| Confidence composition | deterministic (Rule 11) |
| Ambiguity interpretation | ✅ LLM → **typed evidence**, never a verdict |
| **Reasoning narrative — the user-facing detail** | ✅ LLM, **after** the decision is fixed |
| Alternatives / tradeoff narration, polish | ✅ LLM |

The Theory chat's law, kept verbatim: *"LLM interprets ambiguity → structured
interpretation → rules/math make decision."* And its bar for the card body:

```
WHY THIS MATTERS → ROOT CAUSE → RECOMMENDATION → EXPECTED EFFECT
```

That bar is currently impossible: the explanation validator caps output at **one
sentence with no directives and no numbers**. Fixing that without surrendering the
decision to the model is this plan's centerpiece (doc 03).

---

## 3. MAP A — LLM sites (R-series)

| ID | Site | What | When | Tier |
|---|---|---|---|---|
| **R-1** | Ambiguity interpreter | *"considering moving workloads"* → `{classification, confidence_bp}` as **evidence** | gated by LLM Decision Policy; genuine ambiguity only | T2 |
| **R-2** | 🔴 **Reasoning Bundle narrative** | scenario → why it matters → root cause → recommendation rationale → expected effect | **after** the decision is fixed, per published decision | T2 |
| **R-3** | Alternatives narration | why option B lost — from `alternatives_rejected` + tradeoff evidence | card expand / on demand | T1 |
| **R-4** | Expected-effect framing | `do_nothing_cost_bp` + foresight numbers → one framed statement, **numbers templated** | with R-2 | T1 |
| **R-5** | Low-confidence consult | targeted interpretation when evidence is thin — still evidence-producing | **reconciled**: DEFER-to-human stays the default; R-5 activates only under intelligence.py's full validation discipline and is recorded non-authoritative in the trace | T2 |

**Standing guards on every R-site** (proven at L1/L2): decision fixed first — narrative
cannot change it · every claim evidence-bound · **numbers templated, never generated** ·
deterministic template fallback on failure/budget · cached on decision hash.

**MAP B — embeddings:** none, as everywhere in v2.

---

## 4. MAP C — the four flows this plan opens

```
                     TODAY                    L4 v2
L1 importance   ──> dead-ends at door   ──> importance term in the utility formula
L2 analytics    ──> stops at compiler   ──> projected into snapshot facts
                                             (situation.trends.* / anomalies.* / conflicts.*)
L3 knowledge    ──> 4 plays max         ──> compiled_constraints -> eliminations
                                             citations -> Reasoning Bundle
L4 decision     ──> one mute sentence   ──> Reasoning Bundle -> the card
```

---

## 5. MAP D — Algorithms (DLG-series)

| ID | Algorithm | Status |
|---|---|---|
| DLG-01 | Plan DAG + staging + latency refusal | ✅ exists — preserve hard |
| DLG-02 | Context-aware unit selection | ✅ exists, **dormant — turn on** |
| DLG-03 | **Utility with importance** — formula extension + override demotion | 🆕 doc 02 |
| DLG-04 | **Urgency derivation** from validated dates | 🆕 doc 02 |
| DLG-05 | **Rule 11 confidence composition** | 🆕 doc 02 |
| DLG-06 | BSO→snapshot projection | 🆕 doc 04 |
| DLG-07 | compiled_constraints → CandidateCheck mapping | 🆕 doc 04 (chain exists) |
| DLG-08 | do_nothing composition from computed cost | 🆕 doc 02 |
| DLG-09 | **Book-level brief re-rank** (E3) | 🆕 doc 04 |
| DLG-10 | ExternalCandidate scoring + critique verdict (E1) | 🆕 doc 04 |
| DLG-11 | Evidence-ref unification (one builder, one seed) | 🆕 doc 04 |

---

## 6. The five laws of Layer 4

1. **One decider.** `DecisionMaker.decide()` stays the sole synthesis authority.
2. **The decision is fixed before any narrative exists.** R-2 describes; it cannot
   amend. A narrative that contradicts the decision fails validation.
3. **Silence is operational on every live lane.** A floor that defaults to 0 is not a
   floor. Reason-coded suppression stays.
4. **Confidence obeys Rule 11.** It may fall freely; it rises only with named
   independent evidence; degraded runs stay capped. Never last-writer.
5. **No domain vocabulary in core units.** Domain readings live in L3 manifests;
   units compute domain-free. (Today violated — doc 01 fixes.)

---

## 7. Document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | this file |
| `01-Group-L4.1-4.2-Orchestrator-and-Units.md` | **wake the roster** — 17 units live, selector on, domain-vocab purge |
| `02-Group-L4.4-Decision-Maker.md` | **the ears** — importance, urgency, Rule 11, floor, do_nothing |
| `03-Reasoning-Bundle-and-R-Sites.md` | **the voice** — the centerpiece |
| `04-Evidence-and-Seams.md` | L4.3 shape fix · compiled_constraints · consult (E1) · book ranking (E3) |
| `05-Edge-Cases-Loops-Scenarios.md` | R-site failure cases · loops · the two Theory-chat traces |
| `06-Contracts.md` | ReasoningBundle · EvidenceRef additions · ExternalCandidate |
| `07-Build-Order-and-Acceptance.md` | waves Z0–Z6, gates K0–K6 |
| `08-CTO-Handoff-Note.md` | copy-paste brief |

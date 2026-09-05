# Gap Audit — Layer 3: Globe spec vs. built code

**Audited:** 2026-09-03 at commit `13f8c69d`
**Method:** all 13 Globe-specified L3 components checked against `genios_engine/packs/`
(28 modules) and the `Domain Expertise/` corpus (1,389 YAML). `validate.py` executed live.

---

## The headline — the pattern inverts

| Layer | Problem type |
|---|---|
| L1 | components **missing** (16/48 absent; the gateway 2/10) |
| L2 | components **present but designed to describe, never compare** |
| **L3** | **everything built, faithful to Globe, knowledge genuinely good — and the switch is OFF** |

Layer 3's problem is not architecture. It is **operations**: a dark switch, a starving
weld, and three empty brains.

---

## Scoreboard vs Globe's 13 components

### L3.1 Domain Compiler — **9/9 built, 1:1 with Globe** ✅

| Globe component | Code | Verdict |
|---|---|---|
| Capability Resolver | `capability_resolver.py` | ✅ + admission-hash validation |
| Object Resolver | `object_resolver.py` | ✅ |
| Brain Resolver | `brain_resolver.py` | ✅ **snapshot pinning is real** |
| Knowledge Retriever | `knowledge_retriever.py` | ✅ |
| Context Adapter | `context_adapter.py` | ✅ deterministic predicates, **three-state** (TRUE/FALSE/UNKNOWN) |
| Evidence Aggregator | `evidence_aggregator.py` | ✅ |
| Expertise Builder | `expertise_builder.py` | ✅ |
| Expertise Publisher | `expertise_publisher.py` | ✅ |
| Capability Registry | generated reverse index | ✅ O(1) situation→capability |

`ExpertisePackage` (`contracts/domain_expertise.py:302`) matches Globe exactly:
`brain_snapshot_id` ✓, four brain slices ✓, *"no recommendation or decision"* ✓.

### L3.2 Four Brains — machinery 4/4, **content 1/4**

| Brain | Reader | Writer | Content |
|---|---|---|---|
| Expert (Git) | ✅ `authoring.py` catalog | human/PR only | ✅✅ **1,389 YAML · 153 capabilities · validate = 0 errors** |
| Organization | ✅ `runtime_brains.py` | ✅ L6 publisher + admin console | ❌ essentially empty |
| Behavior | ✅ | ✅ L6 publisher | ❌ empty (first human verdict: UNVERIFIED) |
| Adaptive | ✅ | ✅ L6 publisher + `temporary_memories` | ❌ empty |

**The write-governance is better than Globe asked for.** Globe wants the Expert-brain
write "unconstructable"; the code enforces it at the **database level** —
`migrations/0045:127`: `check (brain in ('organization','behavior','adaptive'))`.
The L6 promotion pipeline (OBSERVED → CANDIDATE → VALIDATED → GOVERNED →
TEMPORARY/HUMAN_REVIEW/PROMOTED → PUBLISHED, + REJECTED/EXPIRED) exists in full, with
`learning_policies` floors (`min_observations`, `min_distinct_days`,
`min_distinct_entities`) and `governance.py` enforcement.

**So "who decides brain updates, when, how" is already answered by built code. What is
missing is INPUT** — no verdicts or outcomes flow, so the pipeline governs nothing.

---

## The findings

### 🔴 F1 — The switch is off everywhere (unchanged since day 1)

`platform/config.py:110` `use_domain_compiler: bool = False`, set in no environment.
**1,389 files, 153 capabilities, zero production influence.**

### 🔴 F2 — The weld: 63% of the knowledge has no consumer at all (now quantified)

| Artifact class | Count | L4 consumer |
|---|---|---|
| playbooks | 227 | ✅ the only one — and **capped at 4 per package** |
| heuristics | **280** | ❌ zero |
| rules (incl. `severity: blocking`) | **46** | ❌ zero |
| mental-models | **61** | ❌ zero |
| decision-frameworks | **59** | ❌ zero |

**446 of 712 knowledge artifacts (63%) have no runtime reader.** The adapter's own
docstring names both the risk and the fix (`reason/adapters/expertise.py`):

> *"a 1,748-file corpus could compile successfully … and still emit one generic play —
> **activation would LOOK successful while producing generic output**"* … *"saying so per
> class is what makes **'add a typed consumer'** a visible piece of work"*

**Flipping the switch without typed consumers produces a fake success.**

### 🟡 F3 — Admin corpus: 12/15 Globe surfaces covered, 2 flagships missing, 21/57 unrouted

Admin: 57 capabilities · 10 categories · 14 situations · **36/57 routed**.

Coverage vs Globe's 15 Admin surfaces: strong on Vendor/Contract, Financial Obligation,
Documents, Meetings, Deadlines, Commitments, Decision debt, Process. Partial on
Follow-up, Ownership, Founder Bottleneck, Risk. **Missing entirely: Goal & Progress (#13)
and Opportunity (#14 — the one Globe calls "the surface people remember").**

Structural cause: **the corpus was authored as an "admin department" taxonomy
(facilities-and-assets 5 caps, travel-and-events 5 caps — 10 capabilities Globe never
asked for), while Globe's Admin is a "founder operating intelligence" taxonomy.**

### 🟡 F4 — 259 roster objects unauthored (CS-heavy; Admin's own 25 objects complete)

### ✅ Correction — the "0 accepted" finding is STALE

The day-1 audit reported *"152 capabilities, 0 accepted"* from
`deliver/pipeline.py:181`'s comment. Verified today: **all 153 capabilities carry
`accepted_content_hash`**, the re-stamp mechanism is live (`bac2f76`), and `validate.py`
passes with 0 errors. The comment is stale, not the corpus. Caveat recorded: whether the
153-at-once review was substantive or mechanical is a process question.

---

## Where the code is BETTER than the spec

1. **DB-level Expert-brain protection** — Globe wanted schema-unconstructable; the code
   adds a check constraint.
2. **Admission-hash invalidation** — content changes invalidate acceptance
   (hash-of-content-minus-admission), forcing re-review. Globe has nothing equivalent.
3. **Three-state predicates** (TRUE/FALSE/UNKNOWN) in the Context Adapter — *"unknown
   predicate inputs remain unknown; they are never coerced to a match just to keep a
   route alive."* This dovetails exactly with L2 v2's typed absence.
4. **Weld receipts** — every refused artifact is skipped *with a named reason*, by class.
5. **Version-noise suppression** in the L6 publisher — byte-identical value =
   `no_material_change`, never a new version.

---

## Verdict

L3 is an **unlock problem**, not a build problem: typed consumers for the 446 (the one
real piece of new code), routing for the 21, two missing surfaces authored, three brains
fed by content pipelines, per-tenant activation. The plan is in `03-Layer-3-Plan/`.

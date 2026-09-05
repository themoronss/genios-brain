# Layer 3 v2 — Overview and Doctrine

> **Read the L1 and L2 overviews first.** L3 v2 consumes the `BusinessSituationObject`
> L2 v2 produces and must hand L4 knowledge it can actually consume.

---

## 1. What Layer 3 is

**Definition**

> Layer 3 answers: **how would an expert — and this specific company — read this
> situation?** It retrieves and binds knowledge. It never decides.

**Name:** Domain Expertise Layer
**Package:** `genios_engine/packs/` + `Domain Expertise/` (the corpus)
**Input:** `BusinessSituationObject` (L2 v2)
**Output:** `ExpertisePackage`
**Consumer:** Layer 4 — and nothing else.

### What kind of plan this is

L1 v2 was a **build** plan (16 missing components). L2 v2 was a **stratum** plan (a
missing layer of computation). **L3 v2 is an UNLOCK plan:** the compiler is built 1:1
with Globe, the corpus is large and good, the brains' machinery exists — and none of it
reaches production. The work is:

| Work | Size |
|---|---|
| **Typed consumers** — make 446 unconsumable artifacts consumable at L4 | the one big piece of new code |
| **Admin corpus V1** — route 21 unrouted caps, author the 2 missing Globe surfaces | authoring + registry |
| **Brain content pipelines** — fill the three empty brains | new units (N-3, N-4) |
| **Per-tenant activation** — flip it for a pilot, correctly | ops |

**V1 scope: Admin domain first** — per Globe's own V1 discipline. Sales and CS corpora
stay compiled and stamped but activate later.

---

## 2. The five laws of Layer 3

1. **L3 never decides.** It may say *how an expert reads this*; it may not pick an action.
   (Globe's hard rule; the `ExpertisePackage` docstring already states it.)
2. **The compile is reproducible.** Same situation + same `brain_snapshot_id` =
   **byte-identical package**. This is why runtime LLM here is zero — a stochastic
   compile makes snapshot pinning meaningless. (Same comparability argument as L2's
   measurement.)
3. **The Expert Brain is human territory** — enforced at the DB
   (`check (brain in ('organization','behavior','adaptive'))`) and at the publisher
   (`expert_brain_changed` always false). Never weaken either.
4. **Knowledge does not count as shipped until L4 can consume it, typed.** A compiled
   package whose heuristics nobody reads is inventory, not intelligence. "Add a typed
   consumer" is the visible work — the adapter's own receipts say so.
5. **Activation is per-tenant, per-domain.** `l3_activation(org_id, domain, enabled_at,
   enabled_by)`. Never a global boolean — `use_domain_compiler=False` is the standing
   counterexample.

---

## 3. MAP A — Where the LLM is used

**Compile-time: ZERO. Offline/authoring-time: five sites.**

The compile path (resolver → retriever → adapter → brains → builder → publisher) is and
stays fully deterministic — Law 2. All LLM work happens **around** the corpus and the
brains, off the hot path, human-gated:

| ID | Site | What it does | When it runs | Tier |
|---|---|---|---|---|
| **N-1** | Corpus authoring | done — 1,389 files exist | offline, human-in-loop (Globe weight 60) | T3 |
| **N-2** | **Review assist** | pre-reviews a capability against the admission checklist; a human accepts (re-stamp) | on content change / new capability | T2 |
| **N-3** | **Org-Brain discovery** | extracts company rules from uploaded policy docs (*"contracts > \$50K need founder approval"*) — rides on L1 v2's `internal_kind` canon extraction | on canon ingest | T2 |
| **N-4** | **Behavior-Brain distillation** | **L2.4 supplies the numbers** (*"41/41 approvals under \$5K, ~2 weeks out"*); the model labels them as a behavior-pattern statement → proposed entry into the L6 pipeline | weekly batch | T1 |
| **N-5** | **Gap authoring** | a situation that routes to no capability → drafts the missing capability for human review — the corpus counterpart of L1's open lane | on routing miss | T3, on demand |

**The shared discipline** (same as L1/L2): the model **proposes**, deterministic
governance **decides**. N-3/N-4 outputs enter the L6 promotion pipeline like any other
learning proposal — floors, governance, versioned publish. N-2/N-5 outputs stop at a
human. **No N-site output ever writes a brain directly.**

**MAP B — embeddings: none.** Retrieval is the O(1) generated reverse index
(situation → capabilities → objects). Registry lookup, not similarity.

---

## 4. MAP C — Where data is stored

| Store | What | Status |
|---|---|---|
| `Domain Expertise/` (Git) | Expert Brain: capabilities, playbooks, heuristics, rules, mental-models, decision-frameworks, objects, situations, registry | ✅ exists, validate = 0 errors |
| `learned_brain_entries` | Org/Behavior/Adaptive: versioned, one active per (org, brain, subject), supersession, rollback, **no-expert check constraint** | ✅ exists, empty |
| `temporary_memories` | Adaptive short-term leases, **mandatory `expires_at`** | ✅ exists, empty |
| `learning_objects` + `learning_transitions` + `learning_policies` | the L6 promotion pipeline + its floors | ✅ exists |
| `knowledge_suggestions` | proposed Expert-brain changes — **stops at human review** | ✅ exists |
| `expertise_packages` | compiled packages, version-pinned | ✅ exists (`e1a0c47` stopped rewrite-churn) |
| **`l3_activation`** | per-tenant, per-domain activation | 🆕 NEW |
| **`compiled_constraints` receipts** | what the typed consumers produced/refused per package | 🆕 NEW (in package metadata) |

---

## 5. MAP D — Algorithms

| ID | Algorithm | Where | Status |
|---|---|---|---|
| CLG-01 | Admission-hash validation (content minus admission block) | `capability_resolver.py` | ✅ exists |
| CLG-02 | Route plan resolution (O(1) reverse index) | registry + resolver | ✅ exists |
| CLG-03 | Three-state predicate evaluation | `context_adapter.py` | ✅ exists |
| CLG-04 | Brain snapshot pinning | `brain_resolver.py` | ✅ exists |
| CLG-05 | Preference precedence (Adaptive > Org > Behavior; permission categories → Org authority) | `runtime_brains.py` | ✅ exists |
| **CLG-06** | **Rule → constraint compilation** (when/then → `core.constraint` checks) | 🆕 doc 03 | NEW |
| **CLG-07** | **Selection-aware play cap** (importance-ranked, not alphabetical) | 🆕 doc 03 | NEW |
| **CLG-08** | **Citation binding** (heuristics/models attached as why-material) | 🆕 doc 03 | NEW |
| **CLG-09** | Org-rule discovery gating (which extracted statements qualify as rules) | 🆕 doc 02 | NEW |
| **CLG-10** | Behavior distillation gating (which L2.4 findings qualify as patterns) | 🆕 doc 02 | NEW |

All new algorithms follow the standard five-step build procedure (L1 overview §6):
docstring first, test table before implementation, pure function, integer basis points,
wire last.

---

## 6. Flow continuity

**What L2 v2 hands L3** (and the compiler is structurally ready for):

| L2 v2 output | L3 consumption |
|---|---|
| `pattern_id` + `matched_conditions` | routing key into the reverse index — richer than anchor-type |
| trends / cohort_positions / anomalies | **new Context-Adapter predicate inputs** — capabilities can condition on *"engagement DECLINING"* |
| typed absence (`UNKNOWABLE`) | maps 1:1 onto the adapter's existing `UNKNOWN` predicate state |
| `RESOLVED_BY_STATEMENT` lifecycle | capability situations stay honest about what is over |

**What L3 v2 hands L4** (the weld fix — doc 03):

| Artifact class (count) | New typed consumer |
|---|---|
| rules (46) | → `core.constraint` checks (CLG-06) |
| heuristics (280) | → citation material for decisions and render (CLG-08) |
| mental-models (61) + frameworks (59) | → framing blocks for L4 explanation / L5 render |
| playbooks (227) | → plays, cap made selection-aware (CLG-07) |

---

## 7. Document index

| Doc | Contents |
|---|---|
| `00-Overview-and-Doctrine.md` | this file |
| `01-Group-L3.1-Domain-Compiler.md` | 9 components — preserve list + the QES/BSO-v2 input changes |
| `02-Group-L3.2-Four-Brains.md` | **storage, write paths, update triggers, content pipelines N-3/N-4** |
| `03-Group-L3.3-Typed-Consumers.md` | **the weld fix — CLG-06/07/08** |
| `04-Group-L3.4-Admin-Corpus-V1.md` | routing the 21, the 2 missing surfaces, defer list, N-2/N-5 |
| `05-Contracts-ExpertisePackage.md` | additive package extensions + validators |
| `06-Build-Order-and-Acceptance.md` | waves Y0–Y5, gates J0–J5 |
| `07-CTO-Handoff-Note.md` | copy-paste brief for the coding agent |

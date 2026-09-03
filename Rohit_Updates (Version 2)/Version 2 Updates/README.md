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
| L2 | LIGHT — graph resolution only |
| L3 | ZERO at runtime — deterministic compiler |
| L4 | ambiguity only |
| L5 / L5.2 | prose only |
| L6 | feedback parsing only |

**The one hard prohibition:** the model may **describe**, never **score**. A score feeds
ranking, and ranking must be byte-identical across machines and replays.

---

## Layer plans

| Layer | Plan | Status |
|---|---|---|
| **L1 Knowledge** | `01-Layer-1-Plan/` | ✅ **complete — 11 documents** |
| L2 Context | `02-Layer-2-Plan/` | not started |
| L3 Domain Expertise | `03-Layer-3-Plan/` | not started |
| L4 Reasoning | `04-Layer-4-Plan/` | not started |
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
- `03-Plan-Crosscheck-and-Corrections.md` — the plan audited against Globe, the customer
  bar, our design conversation and itself. **9 findings, 2 critical, all fixed before commit.**

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

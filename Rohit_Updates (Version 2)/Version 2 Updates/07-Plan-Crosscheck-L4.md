# L4 Plan Crosscheck — plan vs Globe vs Theory-chat MD

> Same discipline as the L1 crosscheck (doc 03): before trusting the plan, audit the
> plan. Three references: the Globe file (universal fact), `GeniOSTheoryChatFULL.md`
> (the founder's reference), and the verified code at HEAD.

---

## PART 1 — Is Layer 4 working properly TODAY, the way Globe expects? **No.**

Verified head-to-head (each row grep/read-confirmed, not inferred):

| Globe says L4 does | Code at HEAD actually does |
|---|---|
| Unit Selector picks relevant units per situation | selector exists, **on in zero manifests** — plan.py:44-51 dormant |
| 17 units run per their dependency families | **6 units hardcoded** on the compiled lane; 10/17 unreachable anywhere; full-roster v2 imported, never swept |
| Policy unit binds org rules / names the approver | **core.policy never scheduled** — authority rules bind nothing |
| Units emit evidence with unit_ref/claim/value | evidence minted as *input* by adapters; Finding lacks value_bp; 3 id seeds |
| Decision Ranker weighs importance | **zero importance_bp readers in reason/**; override replaces the formula |
| Urgency from timeline analysis | pinned NEUTRAL 5000 — declared source never publishes it |
| Rule 11: confidence rises only with named independent evidence | **last-writer scan** — any later unit can raise it, uncited |
| Silence is a valid output (confidence floor) | floor defaults 0 on the compiled lane — never fires |
| "Cost of doing nothing" computed | static manifest string; core.cost never runs |
| Explanation chain in founder's language | **one validated sentence, no directives, no numbers** |
| Parallel Scheduler runs independent units concurrently | sequential, deliberately (determinism) — **acceptable deviation, documented** |
| Evidence Store, Planner, elimination chain | ✅ **genuinely excellent — better than spec in places** |

**And vs the Theory-chat MD:** its card bar (WHY THIS MATTERS → ROOT CAUSE →
RECOMMENDATION → EXPECTED EFFECT) is structurally impossible under the one-sentence cap;
its law ("LLM interprets ambiguity → structured interpretation → rules/math decide") is
half-true today — the deterministic half exists, the interpret/narrate half has **zero
LLM sites in reason/**. Today's L4 is *more* deterministic than the founder asked for,
and mute because of it.

**Verdict: L4 today = NOT properly working.** Machinery quality high, product behavior
absent — dormant, **half-blind**, deaf, mute (full evidence: `06-Gap-Audit-L4-Spec-vs-Code.md`).

---

## PART 2 — Does the PLAN deliver Globe + the Theory chat? Yes, after 7 corrections.

Mechanical check run over the plan docs (grep for every Globe component name + all 17
unit names). Findings:

| # | Severity | Finding | Correction |
|---|---|---|---|
| **P-2** | 🔴 **HIGH** | **`core.policy` was missing from the plan's staged DAG** — the one unit that consumes the L2.1.4 Authority view. "Contracts > $50K need founder approval" would have stayed data that binds nothing; Globe's named failure mode could never even occur. | scheduled stage 2 in **doc 02 U1**; consumer role and publishes contract stated |
| P-1 | medium | No component-by-component Globe mapping — 12 of 18 non-unit component names appeared nowhere; substance covered, verification impossible for the CTO | the full component-by-component alignment table is now **doc 00 §2**, and the plan is re-organised group-by-group (L4.1–L4.5) to match Globe |
| P-3 | medium | `run_query` Q&A gap left **silent** — day-1 finding said it can't reason over an arbitrary question; plan neither fixed nor declined it | stated decision added (**doc 06 OUT-3**): no free-text Q&A mode in L4 v2 — product law "you don't have to ask"; critique (S4) is the E1 surface; run_query gains the bundle only |
| P-4 | low | Fallback Strategy (Globe L4.1.7): reserve-unit machinery left dormant with no stated decision | decision stated (**doc 01 C7**): stays dormant; the 3 live degradation mechanisms named |
| P-5 | low | Theory-chat items deliberately not adopted, now recorded: Z3/Clingo solvers (predicate-tree eliminations suffice), ML confidence calibration (L6/L7's `calibrate.py`), multiplicative Impact×Urgency×Confidence (weighted integer blend keeps the same principle, auditable in bp) | this row is the record |

**Theory-chat conformance (the file the founder gave):**

| Theory-chat expectation | Plan home |
|---|---|
| "LLM interprets ambiguity → structured interpretation → rules/math decide" | R-1, verbatim — the *"considering moving workloads"* example is Scenario A |
| Card body: WHY THIS MATTERS / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT | ReasoningBundle fields, gate **K4** |
| OBSERVATION→CONTEXT→INTERPRETATION→IMPLICATION→RECOMMENDATION chain | bundle: situation_summary → citations (interpretation = the corpus reading) → why_it_matters → recommendation_rationale |
| LLM never: priority numbers, permissions, routing, dates, calculations | Law: never CHOOSE, SCORE, PERMIT; V-gauntlet; numbers templated |
| ~85–95% deterministic | design target kept as a **target**, never quoted as measured (Globe's own honesty rule) |
| "What happens if I do nothing" | E4 computed do_nothing + R-4 framing |
| "Agent X is about to send this — change it this way" | S4 critique endpoint, advisory locked |
| "Verify outcome 50–100 times" / learning | L6/L7 scope — correctly not in this plan |

**Verdict: plan = conformant.** Two real defects (P-2 here, P-7 in Part 3) caught and
fixed before any code was written — which is what a crosscheck is for.

## Correction log
- P-2 was my omission in the first draft of doc 01, found by this crosscheck's
  mechanical unit-name sweep (`policy ✗`). The lesson repeats L1's: **enumerate the
  spec's list and check every name; never trust coverage by feel.**

---

## PART 3 — the re-arrangement (after this crosscheck)

The plan was re-organised so that **every Globe group has exactly one document**, the way
L1 and L2 are organised. It also grew from 1,118 to 1,845 lines, with the added detail
concentrated where it was thinnest: the unit roster.

| Before | After |
|---|---|
| L4.1 and L4.2 collapsed into one doc | `01` (orchestrator, 7 components) + `02` (the roster, 21 units) |
| L4.3 had no group doc | `03-Group-L4.3-Evidence-Layer.md` |
| the bundle was a loose doc | `05-Group-L4.5-Reasoning-Bundle.md` — declared as a **new group**, since Globe has no customer-facing narrative component |
| seams mixed into the evidence doc | `06-Seams-In-and-Out.md` |
| no cost model (L2 has one) | `11-Cost-Model-and-Budget-Guards.md` |
| 7 waves | 8 waves, **one per group**, gates renamed to match |

### Two findings that only the re-arrangement surfaced

**P-6 — the roster is 21, not 17, and 4 of the extras are load-bearing.** Enumerating the
registry (rather than trusting Globe's list) found `core.temporal`, `core.relationship`,
`core.signal_composition` and `core.planning` — thin shims Globe does not name. Two of
them are prior sources for **five** Globe units. A roster built strictly from the spec
would have left `core.risk` blind. Recorded as a **gap in Globe**, not a code defect.

**P-7 — 🔴 the units that run, run half-blind.** `core.risk` is scheduled on the compiled
lane; `core.temporal` and `core.relationship` are not; so two of its three plugins read
priors that never ran and stay silent by design. The same starvation hits cost,
opportunity, alternative and impact. This is a *fourth* diagnosis beyond dormant/deaf/mute,
and it explains the line the source itself records — *"every compiled candidate fell back
to a neutral 5000 utility, which is why every compiled card scored exactly 50."*
Fixed by doc 02 U2.

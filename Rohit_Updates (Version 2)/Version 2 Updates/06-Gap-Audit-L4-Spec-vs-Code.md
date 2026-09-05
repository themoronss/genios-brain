# Gap Audit — Layer 4: Globe spec vs. built code

**Audited:** 2026-09-03 at commit `6267eb9b` — 13-agent workflow (5 deep-readers, 2
diagnosers), 6 high-severity claims hand-verified against code after the verify wave hit
a session limit. Every claim below carries a file:line citation.

---

## The headline — the fourth pattern

| Layer | Problem type |
|---|---|
| L1 | components **missing** |
| L2 | components present but **describe-only** |
| L3 | everything built, **switch off** |
| **L4** | **built, and DORMANT + DEAF + MUTE** |

The reasoning engine's machinery is genuinely sophisticated — a validated, hashed,
topologically-ordered execution plan; a rigorous content-addressed evidence store; a
fully built candidate-elimination chain. And in production it runs a fraction of itself,
cannot hear what the layers below say, and is forbidden from explaining what it decided.

---

## Scoreboard vs Globe's 34 components

| Group | Spec'd | Built | Partial/Dormant | Missing |
|---|---|---|---|---|
| L4.1 Reasoning Orchestrator | 7 | 2 | 5 | 0 |
| L4.2 The 17 Reasoning Units | 17 | ~7 reachable | **10 unreachable** | 0 files missing |
| L4.3 Evidence Layer | 3 | 1 (Store, excellent) | 2 (shape-inverted) | 0 |
| L4.4 Decision Maker | 7 | 3 | 4 | 0 |

**Nothing is missing as a file. Most of it never runs, and what runs cannot consume the
v2 supply chain.**

---

## 🔴 DORMANT — built machinery that never executes

### D1 · 10 of the 17 reasoning units are unreachable by any live lane — VERIFIED

- `packs/capabilities/__init__.py:22` — `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`.
  **The v2 full-roster capability (`deal_cooling_v2.py`, all 17 units, proper Globe DAG:
  tradeoff←(risk,opportunity,impact,cost), validation←(…)) is imported and never swept.**
- The compiled lane's fixed DAG is **6 units**: `core.context, core.risk,
  core.constraint, core.priority, core.confidence, core.planning`
  (`reason/adapters/expertise.py`).
- Therefore **impact, cost, opportunity, tradeoff, alternative, validation,
  recommendation, timeline, dependency, resource, scheduling never run** on any
  production path. The evidence roster Globe centers L4 on mostly does not execute.

### D2 · The Unit Selector exists and is OFF everywhere

`reason/plan.py:44-51` — `context_aware_selection` implements exactly Globe's
"run Risk and Priority, not Pricing", deterministically, with skip receipts and
dependency cascades. **No capability manifest sets it.** Every plan is the full declared
roster of its (tiny) lane.

### D3 · Parallel Scheduler is described, never performed — deliberately

`plan.py:20-25`: *"Parallelism is described here, not performed here… concurrency that
could interleave results would make the trace depend on machine timing."* Stages,
critical-path budgets and parallelizability are computed as a **proven safe envelope**
for a future scheduler. This is a defensible position, not a defect — recorded as such.

---

## 🔴 DEAF — the three-layer supply chain dead-ends at L4's door

### F1 · `importance_bp` has ZERO readers in reason/ — VERIFIED

Repo-wide: the only `importance_bp` sites are L2's stamp, the contract validation, and
docs. **Nothing in `reason/` reads it.** So the entire v2 chain — L1-W7 computes real
signal importance (ALG-17) → L2-X5 composes situation importance (BLG-18) → **L4 has no
mouth to receive it**:

- `_weighted_utility` is a **closed 5-component blend** — impact/success/urgency/effort/
  risk (`decision_maker.py:257-268`); the `ranking_weights` contract fixes exactly those
  5 keys (`contracts/reasoning.py:405-412`). **No importance term exists.**
- `priority_override_bp` still replaces the formula for every live candidate
  (`decision_maker.py:231-255` — *"the formula has never once decided anything"*).
- **Urgency is pinned at neutral 5000 on the compiled lane** — VERIFIED:
  `priority.py:51 NEUTRAL_URGENCY_BP = 5_000`; the compiled DAG declares `core.risk` as
  the urgency source and `core.risk` never publishes `urgency_bp`.

**Even after G7 and H5 pass, K-side ranking would not change.** This is the third and
final link of the ranking fix, and it is closed.

### F2 · L2 v2's BSO enrichments have no landing surface

Units read a `ContextSnapshot` built from graph facts; the BSO stops at L3's compiler
(`domain_shadow.py:342-367`, `adapters/native.py:26-43`). When X5 ships trends/cohorts/
anomalies/conflicts, they would be **computed, stamped, and invisible to every reasoning
unit** — the importance dead-seam pattern repeated at scale.

### F3 · The confidence publication floor is dead on the compiled lane — VERIFIED

`confidence_floor_bp` is set by the legacy adapter and by `deal_cooling_v2` (4500 — which
never runs). **The compiled-lane adapter sets no floor → default 0 → the floor never
fires** on exactly the lane v2 depends on. "Silence is a valid output" does not operate
there. (A legacy DEFER is also mislabeled `shadow` in the suppression log.)

---

## 🔴 MUTE — the engine cannot explain itself

### M1 · Rule 11 does not exist: decision confidence is a last-writer scan — VERIFIED

`decision_maker.py:117-138 calculate_confidence`: default 5000, then **each completed
unit's `confidence_bp` overwrites the previous** until the authority unit ends the scan.
No min-composition, no same-source multiplication, no named-independent-evidence
requirement for a raise. **A later unit can raise confidence with no new evidence** —
the exact "fabricated rigour" Globe's Rule 11 forbids. (The degraded-run cap at :136 is
correct and must survive.) Meanwhile L2 computes a genuine 6-axis confidence vector —
which L4 collapses to a last-writer scalar.

### M2 · The explanation cap: one sentence, no directives, no numbers

Globe case 3 (explanation AFTER) is implemented twice, both non-authoritative and
grounded — good. But `intelligence.py:263-328` restricts the output to **one validated
sentence** that rejects directive verbs and numbers. The founder-bar card body — *WHY
THIS MATTERS / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT* — is structurally
impossible to produce. **The reasoning narrative the customer is paying for has no
mechanism.**

### M3 · `do_nothing_consequence` is a static authored string

`decision_maker.py:426` copies it verbatim from the capability manifest (default: *"The
condition may remain unresolved."*). Meanwhile `cost_unit.py:220,266` **genuinely
computes `do_nothing_cost_bp`** and `alternative_unit.py:258` composes a DoNothingBaseline
— and **neither is read by the decision builder**, and neither unit is even scheduled on
the compiled lane. Two very different situations show identical consequences.
`foresight.py`'s per-signal deltas are hardcoded hypothesis constants awaiting L7 tuning.

---

## Also found

| Finding | Severity | Note |
|---|---|---|
| E1 consult seam partial at HEAD | high | one fixed recommendation + validated sentence; no path for an agent's proposed action to be scored/critiqued (day-1 finding stands) |
| E3 book-level ranking absent | high | read-time `ORDER BY` on authored constants; `core.impact` unscheduled; `deal.value` structurally absent |
| Evidence layer shape-inverted | medium | evidence is **input** minted by adapters, not per-unit emission; `EvidenceRef` lacks unit_ref/claim/value_bp; **3 builder sites with different id seeds** (same fact ≠ same identity across lanes); values live in a **720h-TTL** table — after purge, citations survive but what the evidence *said* is gone |
| Domain vocabulary inside core units | medium | opportunity/risk/resource units hardcode sales vocabulary — Globe's named drift ("domain vocabulary leaking into a reasoning unit") |
| LLM policy 1 of 3 cases | medium | cases 1–2 replaced **by stated design** with DEFER-to-human (*"it never invents the missing fact"*) — a defensible substitution to reconcile in the spec, not silently |
| Tradeoff cost axis dead | low | `cost_source` names a unit that does not exist |

---

## Where the code is BETTER than the spec

1. **The plan machinery** — pure, hashed, topologically staged, latency-refused at plan
   time (*"an unschedulable capability must be refused before any unit observes the
   situation"*), skip receipts. Globe asks for an orchestrator; this is a verifiable one.
2. **The elimination chain is fully built and works**: `CandidateCheck ELIMINATE →
   ELIMINATED disposition → rejected_candidates persisted → alternatives_rejected` in
   the API (`decision_maker.py:275-295`, `runner.py:1158-1172`, `routes.py:2387`).
   **L3-Y1's compiled_constraints have a ready landing strip** — the producer is the only
   missing piece.
3. **The evidence Store** — content-addressed, atomically committed, hash-verified
   replay. The shape is wrong; the rigor is right.
4. **Reason-coded silence** — every suppression (budget, cooldown, dormancy,
   no-new-evidence, floor) carries a reason code. Nothing disappears silently.
5. **DEFER-to-human instead of LLM consult** — stricter than Globe: below the floor it
   *"widens uncertainty and lets the executive layer ask a human; it never invents the
   missing fact."*

---

## Verdict

L4 is an **awakening problem**: sweep the full roster, open the ears (importance,
urgency, BSO enrichments), operationalize silence on the live lane, replace last-writer
confidence with Rule 11 composition — and give the engine a **voice**: the typed
Reasoning Bundle that turns a fixed decision into the scenario → why → root cause →
recommendation → expected-effect detail the customer is actually paying for.
Plan: `04-Layer-4-Plan/`.


---

## Addendum — finding D4: **the units that run, run half-blind**

Found while enumerating the registry for the re-arranged plan (doc `04-Layer-4-Plan/02`),
and verified at source.

`_default_dag` (`reason/adapters/expertise.py:93-123`) schedules `core.risk` — but **not**
`core.temporal` or `core.relationship`, which are the prior sources two of its three
plugins read:

| `core.risk` plugin | Reads | Compiled lane |
|---|---|---|
| MomentumDecayPlugin | `core.temporal` → `drop_bp` | prior absent → **silent** |
| RelationshipHealthPlugin | `core.relationship` → `coverage_bp` | prior absent → **silent** |
| PlayMitigationPlugin | the capability's plays | ✅ runs |

The same starvation hits `core.cost` (delay cost reads `core.temporal`),
`core.opportunity` (StalledButOpen), `core.alternative` (momentum) and `core.impact`
(`core.relationship`).

**The source records the consequence itself** (`expertise.py:118-122`):
> *"`core.risk` measures pressure; it does not RULE on priority, so the declared-override
> path found nothing and every compiled candidate fell back to a neutral 5000 utility —
> which is why every compiled card scored exactly 50."*

**Why the audit missed it first time:** the reachability sweep counted *scheduled units*,
and `core.risk` is scheduled. Half-blindness only shows when you check each unit's
**declared priors** against the DAG. The registry also holds four shims Globe never names
(`core.temporal`, `core.relationship`, `core.signal_composition`, `core.planning`) — so a
roster built strictly from the spec's 17 would still have left `core.risk` blind.

**Verdict update:** dormant + **half-blind** + deaf + mute. Fixed by doc 02 U1/U2.

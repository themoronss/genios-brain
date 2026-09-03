# L4.1 + L4.2 — Orchestrator and the 17 Units: wake the roster

> **The units exist. The planner is excellent. Almost nothing runs.** This document
> turns authored machinery into executing machinery.

---

## Current reachability (verified)

| Lane | Units that actually run |
|---|---|
| Legacy pack rules | fixed 10-unit DAG per rule |
| Native capabilities | `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)` — **one capability** |
| Compiled (v2's lane) | **6 units**: context, risk, constraint, priority, confidence, planning |

**Never running anywhere:** impact · cost · opportunity · tradeoff · alternative ·
validation · recommendation · timeline · dependency · resource · scheduling.

And the ready-made fix is already authored: `deal_cooling_v2.py` carries the full
17-unit roster with the proper Globe dependency shape — tradeoff←(risk, opportunity,
impact, cost), validation←(risk, opportunity, impact, confidence) — **imported and never
swept.**

---

# U1 · Extend the compiled-lane DAG (the main event)

**WHAT** — The compiled lane's `_default_dag` grows from 6 units to the full family
structure, staged:

```
stage 1: core.context, core.timeline, core.dependency
stage 2: core.constraint, core.policy, core.risk, core.opportunity, core.impact, core.cost
stage 3: core.tradeoff, core.alternative, core.priority, core.confidence
stage 4: core.validation, core.recommendation, core.planning
(resource, scheduling: scheduled when the manifest declares their inputs)

CORRECTION (plan crosscheck P-2): core.policy was MISSING from this plan's first draft —
the unit that answers "which organisational rules bind, who is the approver". It is the
sole L4 consumer of the L2.1.4 Authority view (authority_rules): without it, "contracts
> $50K require founder approval" exists as data and binds nothing, and Globe's named
failure ("Policy unit reads a stale threshold -> wrong approver named") cannot even
occur because the unit never runs. Scheduled stage 2; OPTIONAL with declared field
authority.rules_present; its published approver/threshold findings feed core.constraint
candidate checks and the Reasoning Bundle's recommendation_rationale.
```

**WHY** — Every downstream fix depends on units actually producing evidence:
`do_nothing_cost_bp` needs core.cost scheduled; tradeoff narration needs core.tradeoff;
the E3 impact term needs core.impact; validation-as-silence needs core.validation.

**HOW — via the selector, not a hardcode.** `plan.py`'s `context_aware_selection`
already implements exactly this: optional units drop (with skip receipts) when every
declared input field is absent, dependents cascade. **Declare the full roster; mark
stage-2+ units OPTIONAL with declared fields; set `context_aware_selection: true` on the
compiled-lane manifest.** A situation with no money facts skips cost/impact — receipted,
deterministic, exactly Globe's "run Risk and Priority, not Pricing."

**FAILURE MODES** — latency blowup (the plan's latency-ceiling refusal already guards —
declared budgets, not stopwatches; tune per-unit budgets) · required-unit failures on
thin situations (only context/constraint/priority/confidence stay REQUIRED; everything
else optional-with-cap, preserving the degraded-confidence rule).

**Fallback Strategy (Globe L4.1.7) — the stated decision (crosscheck P-4):** the unused
reserve-unit machinery **stays dormant** — no work planned, recorded deliberately.
Degradation is served by three live mechanisms: optional-unit skip with the degraded
confidence cap (unit level), the confidence-floor DEFER (decision level, doc 02 E3), and
the L6 authority-based abstention (delivery level). A fourth mechanism would add surface
without adding safety.

**ACCEPTANCE**
```
pytest tests/reason/test_plan_selection.py -q
```
A money-bearing situation schedules cost+impact; a moneyless one skips them **with
receipts**; plan_hash is stable for identical inputs; latency refusal still fires.

**REVERSE PROMPT**
```
TASK: Wake the reasoning roster on the compiled lane.
READ FIRST: reason/plan.py (the dormant selector, :44-51, :219-250),
  packs/capabilities/deal_cooling_v2.py (the authored full-roster DAG),
  reason/adapters/expertise.py (_default_dag — the 6-unit hardcode to replace).
DO:
1. Replace _default_dag with the staged full-family DAG above, declared through the
   normal manifest schema — NOT a new mechanism.
2. Mark stage-2+ units OPTIONAL with declared input fields; set
   context_aware_selection true. Required stays: context, constraint, priority,
   confidence.
3. Do not touch the planner. It is correct. If a plan is refused on latency, tune
   declared unit budgets, never the refusal.
4. Add DEAL_COOLING_FULL_V2 to BUILTIN_CAPABILITIES behind the per-tenant activation
   (l4_activation table, doc 07) — not unconditionally.
TESTS: the ACCEPTANCE rows above + a full-roster run produces Findings from >= 10 units
on a rich fixture situation.
DO NOT: parallelize execution (the sequential-determinism position stands); weaken any
plan validation; remove skip receipts.
```

# U2 · Turn on the Unit Selector everywhere

Covered by U1's mechanism. The point stands alone because it is Globe L4.1's first
component and it is **off in every manifest today**. After U1, `context_aware_selection`
is the default for new manifests; legacy rule DAGs keep their fixed shape until retired.

# U3 · Purge domain vocabulary from core units

**WHAT** — opportunity/risk/resource units hardcode sales vocabulary (deal/champion/
pipeline readings) — Globe's named drift: *"domain vocabulary leaking into a reasoning
unit."*

**HOW** — the unit reads **declared manifest fields** (`opportunity_signals:
[...field names...]`); the *naming* of what counts as an opportunity moves to the L3
manifest where it belongs. Unit logic becomes: threshold/compare/compose over declared
inputs. One test per unit greps its source for domain tokens (`deal`, `champion`,
`pipeline`, `ticket`) and fails on a match.

# U4 · Fix the dead tradeoff cost axis

`cost_source` names a unit that does not exist — point it at `core.cost` (now scheduled
by U1), and add a registration-time check: **a manifest naming an unregistered source
unit fails at plan time**, not silently at run time.

# U5 · Urgency derivation (DLG-04)

**WHAT** — `urgency_bp` computed from validated dates, ending the permanent neutral 5000.

**HOW** — a small pure function in core.timeline (which U1 finally schedules):
```
nearest material date = min over (deadlines, renewal dates, commitment due dates)
   using ResolvedDate.earliest, honoring certainty:
   EXACT full weight · RANGE by earliest · RELATIVE halved (L1's rule carried through)
urgency_bp ladder: overdue 10000 · <=2d 9000 · <=7d 7500 · <=14d 6000
                   · <=30d 4000 · <=90d 2000 · else 500 · no date -> 0 (not 5000)
```
Declared as core.timeline's published metric; priority.py's existing max-wins resolution
then works as designed. **No date → 0, never neutral** — an undated situation is not
half-urgent.

---

## Group acceptance gate

```
pytest tests/reason/test_plan_selection.py tests/reason/test_units_domain_free.py -q
python scripts/unit_reachability_report.py --org <pilot>
```

| Metric | Gate |
|---|---|
| units producing Findings on the pilot over 7 days | **>= 12 distinct** |
| skip receipts on every dropped optional unit | 100% |
| domain tokens in core unit sources | **0** |
| urgency_bp distribution | not a spike at 5000 |
| plan determinism (same inputs → same plan_hash) | exact |

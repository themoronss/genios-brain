# Group L4.1 — Reasoning Orchestrator (7 components)

> **What this group owns:** which units run, in what order, under what budget, with what
> permission to consult a model, and what happens when something fails.
>
> **State in one line:** the hard parts are built and excellent; the *decision* parts —
> which units, which floor, when a model may speak — are unset.

---

# C1 · Unit Selector — **the dormant switch** (DLG-02)

**WHAT** — Chooses which of the declared units actually run for *this* situation.
Globe's example: *"a stalled-deal situation runs Risk and Priority, not Pricing."*

**WHERE** — `reason/plan.py:44-51` (the flag), `:219-250` (the selection pass).

**CURRENT STATE — verified** — Fully implemented, deterministic, and **enabled by no
manifest anywhere.** Every optional unit therefore runs or is hardcoded away.

**HOW IT ALREADY WORKS** (this is the mechanism v2 adopts — nothing new is invented):
```
for each unit declared OPTIONAL:
    if every declared input field is absent from the snapshot -> DROP
       emit a skip receipt naming the unit and the absent fields
       cascade: dependents of a dropped unit drop too, receipted
REQUIRED units never drop; a missing required input fails the plan, loudly
```

**WHEN** — plan construction, before any unit observes a situation. Pure: same inputs →
same plan → same `plan_hash`.

**WHY IT MATTERS FOR v2** — it is the *only* honest way to run a 22-unit roster: a
moneyless situation must not pay for `core.cost`, and it must **say** it skipped it.

**THE CHANGE** — set `context_aware_selection: true` on the compiled-lane manifest and
declare input fields for every optional unit (the work is in doc 02 U1).

**FAILURE MODES** — a unit with no declared fields can never drop (declare them) · an
over-broad field list keeps expensive units alive (tune per unit, measure at K1a) ·
silent drops (impossible by construction — receipts are part of the pass).

**ACCEPTANCE** — a money-bearing situation schedules `core.cost` + `core.impact`; a
moneyless one drops both **with receipts**; `plan_hash` identical across runs.

---

# C2 · Execution Planner — **preserve hard**

**WHAT** — Builds the staged execution plan: stages, per-unit budgets, the plan hash.

**CURRENT STATE — verified excellent.** Pure (no clock, no I/O), content-hashed, stages
computed from the DAG, and it **refuses a plan whose declared budgets exceed the latency
ceiling** rather than starting work it cannot finish. The refusal is receipted.

**THE CHANGE — none to the mechanism.** Only *declared unit budgets* are tuned as the
roster grows. **If a plan is refused on latency, tune the budgets — never the refusal.**

**WHY THIS RULE IS ABSOLUTE** — the refusal is what makes a 22-unit roster safe to turn
on. Weaken it once and every future latency bug becomes a silent partial run.

---

# C3 · Dependency Resolver — **preserve hard**

**WHAT** — Topological ordering; cycle detection; dependents of a skipped unit cascade.

**CURRENT STATE — verified correct**, including the cascade rule that makes C1 safe.

**THE CHANGE — none.** v2 only *feeds* it a bigger DAG (doc 02 U1). The Globe dependency
shape it must resolve: `tradeoff ← (risk, opportunity, impact, cost)` and
`validation ← (risk, opportunity, impact, confidence)` — already authored in
`packs/capabilities/deal_cooling_v2.py`, never swept.

---

# C4 · Parallel Scheduler — **a deliberate deviation, kept**

**WHAT (Globe)** — run independent units concurrently.

**CURRENT STATE — verified** — stages are *described* as parallelizable; execution is
**sequential**, with the reason written in the source (`plan.py:20-25`): determinism of
the reasoning trace outranks latency at current volumes.

**THE DECISION — the deviation stands.** It is not an oversight; it is a position, and
this plan records it as one. Revisit **only** with a proof that concurrent execution
produces byte-identical traces — the same bar every other v2 determinism rule meets.

**WHY** — a reasoning trace that varies run to run destroys replay, and replay is what
K1 and the whole audit story depend on. Latency has a cheaper fix: unit budgets and C1.

---

# C5 · LLM Decision Policy — **the R-site gate** (new)

**WHAT (Globe)** — the policy that decides when a model may be consulted at all.

**CURRENT STATE — verified: `reason/` contains no LLM call sites.** The layer is
100% deterministic, which is *stricter* than the founder asked for, and is the direct
cause of "mute".

**THE POLICY — the gate every R-site passes through:**

| Globe's case | v2 disposition |
|---|---|
| 1. Evidence is insufficient | **DEFER to a human first** (today's behavior, kept — *"never invents the missing fact"*). R-5 may run only under full validation discipline and is recorded **non-authoritative** |
| 2. A situation is genuinely ambiguous | ✅ **R-1** — the model returns a *typed classification with confidence*, consumed **as evidence** by units, never as a verdict |
| 3. An explanation must be generated | ✅ **R-2/R-3/R-4** — after the decision is fixed |

**THE GATE, in order** (all deterministic, no model involved in deciding):
```
1. is this site permitted for this org?          l4_activation(org, 'bundle' | 'critique')
2. is the precondition met?                      R-1: an UNRESOLVED ambiguity flag on a
                                                       fact the plan actually reads
                                                 R-2: a decision exists and is PUBLISHED
3. is there budget left today?                   doc 11 — else deterministic template
4. is a cached result available?                 keyed on decision_hash / fact digest
5. run the site under its tier and timeout       T1/T2 per MAP A
6. validate the output                           the V-gauntlet (doc 05)
7. on any failure: deterministic fallback, recorded — never a retry storm, never silence
```

**WHY THIS SHAPE** — it makes the model's role *auditable*: every consult has a named
precondition, a budget line, a validator, and a fallback. Nothing about the decision
changes if every model call fails; only the prose gets plainer.

**ACCEPTANCE** — with all R-sites force-failed, decisions are byte-identical to a
no-LLM run and every card still renders (template prose). This is the single test that
proves the doctrine holds.

---

# C6 · Confidence Policy — **make silence operational**

**WHAT (Globe)** — floors below which the engine says nothing.

**CURRENT STATE — verified** — the mechanism exists and is honest (below-floor →
DEFER, reason-coded, never a fabricated fact). But `CONFIDENCE_FLOOR_KEY` **defaults to
0 on the compiled lane** — the lane v2 depends on — so it has never fired there.

**THE CHANGE** — floors declared per lane, seeded at **4500 bp** on the compiled lane,
tunable per capability, never zero by default. A lane with no declared floor **fails
plan validation** rather than defaulting to permissive (the "silent zero" class of bug
this whole audit keeps finding).

**ACCEPTANCE** — below-floor DEFERs > 0 on the pilot compiled lane · each carries a
reason code · a manifest with no floor is refused at registration.

---

# C7 · Fallback Strategy — **stated decision: stays dormant**

**WHAT (Globe)** — reserve units substituted when a primary unit fails.

**CURRENT STATE** — machinery present, unused.

**THE DECISION — no work planned, recorded deliberately.** Degradation is already served
by three live mechanisms at three levels, and a fourth adds surface without safety:

| Level | Mechanism | Where |
|---|---|---|
| unit | optional-unit skip + **degraded-confidence cap** | C1 + `decision_maker.py:136` |
| decision | confidence-floor DEFER | C6 |
| delivery | authority-based abstention | L6 (its own plan) |

**Revisit trigger** — if K1a shows a *specific* unit failing repeatedly on live data with
a cheap deterministic substitute available, then and only then.

---

## Group acceptance gate — G-L4.1

```
pytest tests/reason/test_plan_selection.py tests/reason/test_llm_policy.py -q
```

| Metric | Gate |
|---|---|
| `context_aware_selection` on the compiled lane | true, per-tenant activated |
| skip receipts on every dropped optional unit | 100% |
| plan determinism (same inputs → same `plan_hash`) | exact |
| latency refusal still fires on an over-budget plan | demonstrated |
| declared confidence floor on every live lane | required — registration fails without one |
| **all R-sites force-failed → decisions byte-identical** | **exact** |

**REVERSE PROMPT — C5/C6 (C1's prompt lives in doc 02 U1)**
```
TASK: L4.1 — the LLM Decision Policy gate and operational confidence floors.
READ FIRST: reason/plan.py, reason/decision_maker.py (CONFIDENCE_FLOOR_KEY, the DEFER
  path), api/.../intelligence.py (the existing grounding/validation discipline to reuse).
DO:
1. Add a single gate module every R-site calls: activation -> precondition -> budget ->
   cache -> tiered call -> validate -> fallback. No R-site may call a model directly.
2. Every gate outcome is recorded on the decision trace: site id, outcome
   (ran | cached | skipped_precondition | skipped_budget | failed_validation), cost.
3. Confidence floors: declared per lane, 4500 bp seed on the compiled lane; a manifest
   without a declared floor FAILS registration. Never default to 0.
RULES: no model call decides, scores, or permits anything; fallback is always a
deterministic template; no retry storms (one retry, then fall back).
ACCEPTANCE: with every R-site force-failed, a full pilot replay produces byte-identical
DecisionObjects vs a no-LLM baseline; below-floor DEFERs appear on the compiled lane.
```

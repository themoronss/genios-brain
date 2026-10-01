# Plane R — how a professional thinks · `reason/`

**118 files · 40,036 lines · 23 registered units.** Domain-free by construction: the same temporal
unit reasons about a contract notice period, a sales quarter close and an offer expiry, because
Plane D supplies the domain content.

---

## What an R-Unit is

A **versioned, reusable thinking contract**: its purpose, when it applies, the questions it asks,
the evidence it needs, the output it must produce, **when it must abstain**, and how it is tested.
It contains no Admin knowledge. A unit that only works for Admin is Plane D knowledge in disguise.

### The anatomy every unit shares

```
Input → Validator → Retriever → Analyzer(plugins) → Calculator → Evaluator → Builder → Metrics
                                      ▲
                               the IP lives here
```

`reason/unit.py` states the goal directly: *"you do not build seventeen systems, you build one
framework and seventeen implementations of it. A unit that looks like every other unit can be
reviewed, tested, timed, and replaced by someone who has never seen it before."*

⛔ **Two laws that outrank the diagram**

1. **The Retriever does not fetch.** Units may not touch a database, network or clock — that is
   what makes a decision replayable months later. Retrieval already happened when L3 froze the
   `ContextSnapshot`, and time arrives as `eval_time`.
2. **The stages are methods, not files.** `evaluate()` is a template method that cannot be
   overridden, so no unit can skip validation or invent its own result shape.

---

## The six groups of thinking

| Group | Question | Typical units |
|---|---|---|
| 1 · Establish reality | What is actually true? | evidence quality, contradictions, baselines, decision-changing unknowns |
| 2 · Understand the situation | What is happening? | context, framing, expected vs actual, temporal, commitment, ownership, dependency |
| 3 · Explain and anticipate | Why, and what next? | pattern, counterexample, causal, consequence, scenarios |
| 4 · Judge and choose | Does it matter, what now? | materiality, risk, reversibility, priority, intervention, options |
| 5 · Plan and mobilise | How will it get done? | outcome definition, sequencing, capacity, delegation, contingency |
| 6 · Control, verify, learn | Is it working? Did it? | deviation, replanning, verification, closure, learning |

Not a pipeline. The Orchestrator activates only the groups a situation needs and jumps back
whenever evidence changes.

---

## How the two planes bind — `_ROSTER`

`reason/adapters/expertise.py` holds twenty `_RosterUnit` records. Each declares:

- `roles` — a config key → the **fact paths** that can fill it, in preference order
- `gates_on` — the roles whose bound field gates the unit through the selector
- `essential` — the roles without which the unit is not declared at all
- `always` — the opposite claim, which **must be stated in words**, because *"a unit that can never
  be dropped for want of a fact must say why, or 'it never drops' is indistinguishable from
  'nobody declared its inputs'."*

Two different questions, and conflating them is how a roster becomes noise:

```
does this EXPERTISE read anything this unit can use?  → the manifest declares it, or does not
does this SITUATION carry that input?                 → the selector schedules it, or drops it
                                                        with a SkippedStep receipt
```

The first is answered against the corpus's own fact paths, so **nothing here invents a
vocabulary**. Measured for Admin with `roster_v2`: **15 of 20 bind; 4 of the 5 drops are correct.**

---

## The polish this plane needs

| | |
|---|---|
| **Now (`M11.C1`)** | dependency-complete plans — a unit may not run if its declared sources are not scheduled. This closes the half-blind `core.risk` |
| **Now (`M11.C1.U02`)** | every skip leaves a receipt naming the missing input and its candidates |
| **Next** | the six default-path units get their **full inputs** before any new unit is admitted |
| **Later** | grow toward the composite set only where evaluation shows a composite is needed |

⛔ **No new reasoning units until the existing six see full inputs.** Adding a unit to a plan that
cannot feed the ones it has is how the roster became noise the first time.

### When a new unit may be admitted

It is a genuinely distinct way of thinking · existing units cannot compose it reliably · it is
reusable across domains · its input and output can be defined · its quality can be evaluated on its
own · real cases show a repeated reasoning failure · and it is **not** domain knowledge, policy,
wording or arithmetic.

### How units change — never by themselves

learning observation → root cause classified → change proposed → **human review** → evaluation
cases added → regression suite → shadow run → new version. Patch for wording, minor for a new
optional input, major when the output contract changes. Every receipt records the versions it used.

# CTO Handoff — Layer 4 v2

## SECTION A — for the CTO

**The audit in one line:** L4 is built, and **dormant, deaf, mute — and half-blind.**

- **Dormant** — 10 of Globe's 17 units are unreachable by any live lane.
  `BUILTIN_CAPABILITIES` sweeps only v1; the compiled lane hardcodes a 6-unit DAG; the
  authored full-roster v2 capability is **imported and never swept**. The unit selector —
  Globe's *"run Risk and Priority, not Pricing"* — exists, deterministic and receipted,
  and is enabled by **no manifest anywhere**.
- **Half-blind** — the units that *do* run are starved. `core.risk` is scheduled, but
  `core.temporal` and `core.relationship` — the priors two of its three plugins read —
  are not. It observes one of the three things it was built to observe. The same
  starvation hits cost, opportunity, alternative and impact. Our own source records the
  consequence: *"every compiled candidate fell back to a neutral 5000 utility — which is
  why every compiled card scored exactly 50."*
- **Deaf** — `importance_bp` has **zero readers in `reason/`**; the utility formula is a
  closed 5-component blend with no importance term; the override still replaces it, so
  the formula has never once decided anything; urgency is pinned neutral because
  `core.timeline` never publishes it; and the confidence floor defaults to 0 on the
  compiled lane, so *"silence is a valid output"* has never fired on the lane v2 depends on.
- **Mute** — confidence is a **last-writer scan** (Rule 11 absent); `do_nothing_consequence`
  is a static manifest string while `core.cost` computes the real number and never runs;
  and the explanation is capped at **one sentence, no directives, no numbers** — which
  makes the founder's card body structurally impossible.

**What is genuinely excellent and must not be touched:** the plan machinery (pure,
content-hashed, staged, latency-refused with receipts), the evidence Store
(content-addressed, hash-verified, fails closed), the **fully-built elimination chain**
(`alternatives_rejected` works — L3's blocking rules already have a landing strip),
reason-coded suppression, and DEFER-to-human below the floor.

**The doctrine** (agreed with the founder, grounded in the Theory chat):
> The LLM may **INTERPRET** evidence and **NARRATE** reasoning. It may never **CHOOSE**,
> **SCORE**, or **PERMIT**. The decision is fixed first; the bundle describes it and can
> never amend it; every number in the prose is templated from a computed value.

**Its enforcement test:** with every R-site force-failed, a full replay must produce
**byte-identical DecisionObjects**. If that ever fails, the model has acquired decision
authority and the wave is reverted.

**The two gates that matter:** **K1** — the formula finally decides, closing the
G7→H5→K1 chain on the same pilot in the same fortnight. **K4** — a live card carrying
WHY / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT with a verbatim corpus citation.

**Cost:** ~$0.012 per explained decision, ~$17.50 per tenant per month at 40 decisions/day
(doc 11). The decisions themselves are free — they are arithmetic.

---

## SECTION B — copy-paste to the coding agent

```
You are implementing Layer 4 v2 of GeniOS, the Reasoning Engine.

READ FIRST, IN ORDER:
  Rohit_Updates (Version 2)/Version 2 Updates/06-Gap-Audit-L4-Spec-vs-Code.md
  .../04-Layer-4-Plan/00-Overview-and-Doctrine.md      <- the alignment table
  .../04-Layer-4-Plan/08-Build-Order-and-Acceptance.md
Then your wave's group doc. Reverse prompts are at the end of docs 01, 02, 04 and 07.

WHAT L4 IS: it answers "what should happen" - weighs evidence, applies constraints,
ranks, commits, and EXPLAINS. Package: genios_engine/reason/. In: BusinessSituationObject
+ ExpertisePackage. Out: DecisionObject + ReasoningBundle. L4 never knows a domain.

THE FIVE LAWS:
1. ONE DECIDER. DecisionMaker.decide() stays the sole synthesis authority.
2. DECISION FIRST, NARRATIVE SECOND. A bundle whose action id does not match the
   decision's is a CONSTRUCTOR ERROR (V-3), not a review comment.
3. SILENCE IS OPERATIONAL. Floors declared per lane; a lane with no declared floor fails
   registration. A floor defaulting to 0 is a bug.
4. RULE 11 CONFIDENCE. Falls freely; rises ONLY with a RaiseClaim citing evidence from a
   DIFFERENT independence group; the degraded-run cap stays. Never last-writer.
5. NO DOMAIN VOCABULARY IN CORE UNITS. Domain readings live in L3 manifests.

THE MODEL'S LINE: interpret evidence (R-1: a typed classification with confidence,
consumed AS evidence) and narrate reasoning (R-2/3/4: after the decision, evidence-bound,
numbers as placeholders substituted deterministically). Never a score, never a verdict,
never a permission. Every R-site goes through the single gate module (doc 01 C5):
activation -> precondition -> budget -> cache -> call -> validate -> deterministic
fallback, with the outcome recorded on the trace.

PRESERVE-HARD (a PR touching these while doing something else is rejected):
plan.py entirely, including the sequential-execution position - reason/store.py - the
elimination chain - reason-coded suppression - the degraded-confidence cap -
DEFER-to-human below the floor - formula_utility recorded beside the override -
intelligence.py's grounding discipline (the gauntlet EXTENDS it, never weakens it) -
no published unit metric is ever renamed.

BUILD ORDER: Z0 contracts -> Z1 wake the roster -> Z2 evidence shape -> Z3 the ears (K1!)
-> Z4 the voice (K4!) -> Z5 seams in -> Z6 seams out -> Z7 pilot.
Z1 and Z2 are parallel tracks from day one. The guards
(L2_IMPORTANCE_NOT_ACTIVE, manifest_fallback, rule_unevaluable, template_fallback) make
partial upstream activation HONEST: say what you do not have; never substitute a neutral
number for it. The 5000 default is how this layer went deaf in the first place.

ACTIVATION: l4_activation(org, feature) - roster_v2 | ranking_v2 | bundle | critique |
brief. Per tenant, never a global flag. use_domain_compiler = False is the standing warning.

NEVER: let a model emit a _bp that feeds ranking - let a bundle amend a decision - put a
bare number in narrative prose - raise confidence without a cross-group RaiseClaim -
default importance to 5000 - rename a published metric - parallelize unit execution -
run the suite against production.

FIRST TASK: Wave Z0 (doc 07's reverse prompt). Report:
  pytest tests/contracts/test_l4_contracts.py tests/test_layer_topology.py -q
Do not start Z1 until it is green with zero skips.
```

---

## Wave → document index

| Wave | Group | Doc | Reverse prompt |
|---|---|---|---|
| Z0 | Contracts | 07 | ✅ |
| Z1 | L4.2 roster (+ L4.1 selector) | 02, 01 | ✅ doc 02 U1 |
| Z2 | L4.3 evidence | 03 | specs |
| Z3 | L4.4 decision maker | 04 (+01 C6) | ✅ doc 04 E1 |
| Z4 | L4.5 the voice | 05 (+01 C5) | ✅ doc 01 C5 |
| Z5 | Seams in | 06 | specs |
| Z6 | Seams out | 06 | specs |
| Z7 | Pilot | 08 K7, 10, 11 | — |

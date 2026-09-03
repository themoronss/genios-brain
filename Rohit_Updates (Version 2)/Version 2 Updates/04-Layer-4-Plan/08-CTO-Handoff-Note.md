# CTO Handoff — Layer 4 v2

## SECTION A — For the CTO

**The audit in one line:** L4 is built, and **dormant, deaf, and mute.**

- **Dormant** — 10 of 17 reasoning units are unreachable by any live lane
  (`BUILTIN_CAPABILITIES` sweeps only v1; the compiled lane hardcodes a 6-unit DAG; the
  authored full-roster v2 capability is imported and never swept). The unit selector —
  Globe's "run Risk and Priority, not Pricing" — exists, deterministic and receipted, and
  is set by **no manifest**.
- **Deaf** — `importance_bp` has **zero readers in reason/**; the utility formula is a
  closed 5-component blend with no importance term; the override still replaces it
  (*"the formula has never once decided anything"*); urgency is pinned neutral 5000 on
  the compiled lane; the confidence floor defaults to 0 there, so "silence is a valid
  output" never fires; L2 v2's analytics would stop at the compiler with no path into
  what units read.
- **Mute** — decision confidence is a **last-writer scan** (Rule 11 absent);
  `do_nothing_consequence` is a static manifest string while the units that compute the
  real number never run; and the explanation is capped at **one sentence with no
  directives and no numbers** — the founder-bar card body (WHY THIS MATTERS / ROOT CAUSE
  / RECOMMENDATION / EXPECTED EFFECT) is structurally impossible today.

**What is genuinely excellent and must not be touched:** the plan machinery (pure,
hashed, staged, latency-refused with receipts), the evidence Store, the fully-built
elimination chain (`alternatives_rejected` works — L3's blocking rules have a landing
strip), reason-coded suppression, DEFER-to-human below the floor.

**The doctrine** (agreed with the founder, grounded in the Theory chat):
> The LLM may INTERPRET evidence and NARRATE reasoning. It may never CHOOSE, SCORE, or
> PERMIT. The decision is fixed first; the Reasoning Bundle describes it and can never
> amend it; every number in the prose is templated from computed values.

**The two gates that matter:** **K1** (the formula finally decides — closing the
G7→H5→K1 chain; all three on the same pilot, same fortnight) and **K4** (a live card
carrying the full reasoning bundle with an L3 citation — the founder-bar moment).

## SECTION B — Copy-paste to the coding agent

```
You are implementing Layer 4 v2 of GeniOS, the Reasoning Engine.

READ FIRST, IN ORDER:
  Rohit_Updates (Version 2)/Version 2 Updates/06-Gap-Audit-L4-Spec-vs-Code.md
  .../04-Layer-4-Plan/00-Overview-and-Doctrine.md
  .../04-Layer-4-Plan/07-Build-Order-and-Acceptance.md
Then your wave's doc. Reverse prompts sit at the ends of docs 01, 02, 06.

WHAT L4 IS: it answers "what should happen" — weighs evidence, applies constraints,
ranks, commits, and EXPLAINS. reason/. In: BSO + ExpertisePackage. Out: DecisionObject
+ ReasoningBundle. L4 never knows a domain.

THE FIVE LAWS:
1. ONE DECIDER. DecisionMaker.decide() stays the sole synthesis authority.
2. DECISION FIRST, NARRATIVE SECOND. The bundle describes a fixed decision; a bundle
   whose action does not id-match the decision is a constructor error (V-3).
3. SILENCE IS OPERATIONAL. Floors are set on every live lane; every suppression is
   reason-coded. A floor defaulting to 0 is a bug.
4. RULE 11 CONFIDENCE. Falls freely; rises only with a RaiseClaim citing evidence from
   a DIFFERENT independence_group; degraded cap stays. Never last-writer.
5. NO DOMAIN VOCABULARY IN CORE UNITS. Domain readings live in L3 manifests.

THE MODEL'S LINE: interpret evidence (R-1: typed classification + confidence, consumed
AS evidence) and narrate reasoning (R-2/3/4: after the decision, evidence-bound, numbers
as placeholders substituted deterministically). Never a score, never a verdict, never a
permission. Fallback on every R-site is a deterministic template, recorded.

PRESERVE-HARD (PRs touching these while doing something else are rejected):
plan.py entirely (incl. the sequential-execution position) · the elimination chain ·
reason/store.py · reason-coded suppression · the degraded-confidence cap ·
DEFER-to-human · formula_utility recording · intelligence.py's grounding gauntlet
(extend, never weaken).

BUILD ORDER: Z0 contracts -> Z1 wake roster -> Z2 ears (K1!) -> Z3 evidence shape ->
Z4 voice (K4!) -> Z5 seams -> Z6 pilot. Z1 and Z3 parallel from day one. Guards
(L2_IMPORTANCE_NOT_ACTIVE, authored_fallback, rule_unevaluable) make partial upstream
activation honest — never fake a spread, never fake a citation.

ACTIVATION: l4_activation(org, feature) — five features, per tenant. No global flags.
use_domain_compiler's history is the standing warning.

NEVER: let a model emit a _bp that feeds ranking · let a bundle amend a decision ·
put a bare number in narrative prose · raise confidence without a cross-group
RaiseClaim · run the suite against production · parallelize unit execution.

FIRST TASK: Wave Z0 (doc 06's reverse prompt). Report:
  pytest tests/contracts/test_l4_contracts.py tests/test_layer_topology.py -q
Do not start Z1 until green with zero skips.
```

## Wave → prompt index
Z0 → doc 06 · Z1 → doc 01 (U1 prompt) · Z2 → doc 02 (E1 prompt; E2–E4 specs) ·
Z3/Z5 → doc 04 · Z4 → doc 03 · Z6 → doc 07 (K6)

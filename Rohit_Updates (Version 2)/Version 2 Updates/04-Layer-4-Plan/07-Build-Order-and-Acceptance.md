# Layer 4 v2 — Build Order and Acceptance Gates

> Waves **Z**, gates **K** (L1=W/G, L2=X/H, L3=Y/J). Units first, parents never before
> children are green, a skip is not a pass.

## The seven waves

| Wave | Builds | Depends on | Gate |
|---|---|---|---|
| **Z0** | Contracts (doc 06) | — | K0 |
| **Z1** | **Wake the roster**: DAG extension via selector, urgency derivation, domain-vocab purge, cost_source fix (doc 01) | Z0 | K1a |
| **Z2** | **The ears**: importance component + override demotion, Rule 11 confidence, floor on compiled lane, computed do_nothing (doc 02) | Z1; full value needs **L1-W7 + L2-X5** | **K1** |
| **Z3** | Evidence shape: Finding canonization, one builder, TTL digest (doc 04 S1) | Z0 | K3 |
| **Z4** | **The voice**: R-2 bundle + gauntlet + fallback, R-1 interpreter, R-3/R-4 (doc 03) | Z2 | **K4** |
| **Z5** | Seams: BSO projection (needs L2-X5 shape), compiled_constraints consumer (needs L3-Y1), critique endpoint, brief re-rank (doc 04) | Z2 | K5 |
| **Z6** | Pilot: five features per-tenant via `l4_activation`, golden bundles review | all | **K6** |

**Parallelism:** Z1 and Z3 are independent tracks from day one. Z1/Z2's *machinery* needs
nothing upstream — only their *full value* waits on W7/X5/Y1; the guards
(`L2_IMPORTANCE_NOT_ACTIVE`, `authored_fallback`, `rule_unevaluable`) make partial
activation honest rather than fake.

## Acceptance gates

**K0** — contracts round-trip; topology green; `advisory` unfalsifiable.

**K1a — roster awake**
```
python scripts/unit_reachability_report.py --org <pilot>
```
≥12 distinct units producing Findings over 7 days · every skip receipted · urgency not a
5000 spike · 0 domain tokens in core units · plan_hash determinism exact.

**K1 — 🔴 the formula decides** (doc 02 table — the G7→H5→K1 chain closes)
> 50 distinct utilities · same-type-different-importance ranks differently ·
divergence-vs-override recorded · below-floor DEFERs > 0 on the compiled lane ·
ConfidenceViolation enforced · byte-identical replay.
**G7, H5 and K1 must hold on the same pilot in the same fortnight.**

**K3** — one evidence id per fact across lanes · post-TTL replay digest-verifies ·
Finding.unit_ref populated.

**K4 — 🔴 the voice** (doc 03 table)
100% bundles on published decisions · 0 decision-contradictions · 0 bare numbers ·
**≥1 pilot card with WHY/ROOT-CAUSE/RECOMMENDATION/EXPECTED-EFFECT + an L3 citation** ·
fallback <15% · 25-bundle golden review passes the 10-second test.

**K5** — BSO trend visible to a unit · corpus rule eliminates an agent proposal via
critique · BriefRanking daily with rank_components.

**K6 — pilot** — 7 days, five features on: no regression vs the shadow lane · the
Theory-chat AWS scenario reproduces end-to-end on live data · founder-facing cards carry
bundles · suppression-reason distribution reviewed (silence working, not silent-failing).

## What must not regress

| # | Invariant | Where |
|---|---|---|
| 1 | One decider — `DecisionMaker.decide()` | decision_maker.py:369 |
| 2 | Plan machinery: purity, hashing, staging, latency refusal, skip receipts | plan.py — **preserve hard** |
| 3 | Sequential execution (parallelism described, not performed) | plan.py:20-25 — a deliberate position, revisit only with a determinism proof |
| 4 | Elimination chain → alternatives_rejected | decision_maker.py:275, runner.py:1158, routes.py:2387 |
| 5 | Evidence Store rigor (content-addressed, hash-verified) | reason/store.py |
| 6 | Reason-coded suppression | every silence names itself |
| 7 | Degraded-run confidence cap | decision_maker.py:136 |
| 8 | DEFER-to-human below the floor (*"never invents the missing fact"*) | decision_maker.py:22 — R-5 augments, never replaces |
| 9 | Explanation grounded-gated, fail-closed without spend | intelligence.py — the gauntlet extends this, never weakens it |
| 10 | `formula_utility` recorded beside the override | the divergence measurement K1 depends on |
| 11 | Layer topology; tests never touch production | standing |

## Retirement
After K6 holds 14 days: the one-sentence explanation cap retires in favor of the bundle
(the validator machinery is *reused* by the gauntlet, not deleted); `priority_override`
weight review (30% → lower) driven by the recorded divergence data.

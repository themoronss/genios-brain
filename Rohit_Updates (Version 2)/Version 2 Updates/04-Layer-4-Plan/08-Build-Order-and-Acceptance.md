# Layer 4 v2 — Build Order and Acceptance Gates

> Waves **Z**, gates **K** (L1 = W/G · L2 = X/H · L3 = Y/J). Units first, parents never
> before their children are green, **a skip is not a pass.**

---

## The eight waves — each wave is a group

| Wave | Group / doc | Builds | Depends on | Gate |
|---|---|---|---|---|
| **Z0** | Contracts · 07 | ReasoningBundle, DecisionObject fields, `Finding.value_bp`, ExternalCandidate, BriefRanking, `l4_activation` | — | K0 |
| **Z1** | **L4.2** · 02 (+01 C1) | **wake the roster**: staged DAG through the selector, the two starved shims, vocab purge, `core.effort` ghost, urgency ladder | Z0 | **K1a** |
| **Z2** | **L4.3** · 03 | evidence shape: `Finding` canonized, one builder, permanent digest | Z0 | K2 |
| **Z3** | **L4.4** · 04 (+01 C6) | **the ears**: importance term, override demoted, Rule 11, floors, computed do-nothing | Z1; *full value* needs **L1-W7 + L2-X5** | 🔴 **K1** |
| **Z4** | **L4.5** · 05 (+01 C5) | **the voice**: the LLM policy gate, R-2 bundle + gauntlet + fallback, R-1, R-3/R-4 | Z3 | 🔴 **K4** |
| **Z5** | Seams IN · 06 | BSO→snapshot projection, `compiled_constraints` consumer | Z1; needs **L2-X5** shape, **L3-Y1** producer | K5 |
| **Z6** | Seams OUT · 06 | critique endpoint (E1), book-level brief re-rank (E3) | Z3, Z4 | K6 |
| **Z7** | Pilot | five features on per tenant, golden bundle review | all | **K7** |

**Parallel tracks from day one:** Z1 and Z2 are independent. Z1/Z3's *machinery* needs
nothing upstream — only their *full value* waits on W7/X5/Y1. The guards
(`L2_IMPORTANCE_NOT_ACTIVE`, `manifest_fallback`, `rule_unevaluable`, `template_fallback`)
make partial activation **honest rather than fake**: the system says what it does not yet
have instead of substituting a neutral number for it.

---

## The gates

**K0 — contracts.** Round-trip of old shapes · topology green · `advisory` unfalsifiable ·
weights validated to 10000 · V-3 rejects a mismatched bundle at construction.

**K1a — the roster is awake** (doc 02 gate)
```
python scripts/unit_reachability_report.py --org <pilot>
```
≥12 distinct units emitting Findings over 7 days · `core.risk` emitting momentum **and**
relationship observations · every skip receipted · `urgency_bp` not a spike at 5000 · zero
domain tokens in core units · an unregistered source unit refused at registration ·
`plan_hash` determinism exact · **zero published metric names changed**.

**K1 — 🔴 the formula finally decides** (doc 04 gate)
> ≥50 distinct `final_utility_bp` per day (today: everything scores 50) · two situations of
> the same type with different importance rank differently · `formula_utility` and override
> divergence recorded on 100% of decisions · uncited confidence raise throws
> `ConfidenceViolation` · below-floor DEFERs > 0 on the compiled lane · `do_nothing`
> computed on ≥80% · byte-identical replay.

**G7, H5 and K1 must hold on the same pilot in the same fortnight.** Any one alone changes
nothing a customer can see.

**K2 — evidence.** One evidence id per fact across all three lanes · post-TTL replay
digest-verifies and labels itself · a tampered payload still fails closed ·
`Finding.unit_ref` resolvable on 100%.

**K4 — 🔴 the voice** (doc 05 gate)
> 100% of published decisions carry a bundle · 0 decision contradictions (V-3 is
> structural) · 0 bare numbers · citations byte-identical · fallback rate < 15% ·
> **≥1 pilot card showing WHY / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT with a real
> L3 citation** · a 25-bundle golden review passing the 10-second test.
>
> **Plus the doctrine test:** with every R-site force-failed, a full replay produces
> **byte-identical DecisionObjects**. If that ever fails, the model has acquired
> decision authority and the wave is reverted.

**K5 — seams in.** A BSO trend is visible to a unit as a declared fact · UNKNOWABLE
projects as unknown-typed, never a value · a corpus blocking rule eliminates a candidate
with its rule id travelling into `alternatives_rejected`.

**K6 — seams out.** A corpus rule eliminates an **agent's** proposed action via critique ·
BriefRanking daily with `rank_components` · `advisory` still unfalsifiable.

**K7 — pilot (7 days, five features on).** No regression vs the shadow lane · the
Theory-chat AWS scenario reproduces end to end on live data · founder-facing cards carry
bundles · suppression-reason distribution reviewed (**silence working, not silent-failing**).

---

## What must not regress

| # | Invariant | Where |
|---|---|---|
| 1 | One decider — `DecisionMaker.decide()` | `decision_maker.py:369` |
| 2 | Plan machinery: purity, hashing, staging, latency refusal, skip receipts | `plan.py` — **preserve hard** |
| 3 | Sequential execution (parallelism described, not performed) | `plan.py:20-25` — a position; revisit only with a determinism proof |
| 4 | Elimination chain → `alternatives_rejected` | `decision_maker.py:275`, `runner.py:1158`, `routes.py:2387` |
| 5 | Evidence Store rigor: content-addressed, hash-verified, **fails closed** | `reason/store.py` |
| 6 | Reason-coded suppression — every silence names itself | throughout |
| 7 | Degraded-run confidence cap | `decision_maker.py:136` |
| 8 | DEFER-to-human below the floor — *"never invents the missing fact"* | `decision_maker.py:22` — R-5 augments, never replaces |
| 9 | Grounded-gated explanation, fail-closed without spend | `intelligence.py` — the gauntlet **extends** it, never weakens it |
| 10 | `formula_utility` recorded beside the override | the divergence K1 depends on |
| 11 | No published unit metric renamed | the roster's contract with its readers |
| 12 | Layer topology; tests never touch production | standing |

---

## Retirement — only after K7 holds 14 days

| Item | Condition |
|---|---|
| the one-sentence explanation cap | retires in favor of the bundle; **its validator machinery is reused by the gauntlet, not deleted** |
| the 70/30 override weight | reviewed **with the recorded divergence data**, never by taste |
| `core.signal_composition`, `legacy.*` | retire with the legacy lane |
| the fallback reserve-unit machinery | revisit only if K1a shows a specific unit failing repeatedly |

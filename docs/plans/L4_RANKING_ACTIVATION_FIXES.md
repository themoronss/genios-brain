> **Created:** 2026-09-08 · **Status:** Active — P1–P5 landed and measured; P6 needs a live tenant and a model
>
> **Purpose:** Close the six open items in `L4_V2_BUILD_RECORD.md` §12.7 plus the cross-layer gaps found auditing L1→L4 together — the three constant ranking components, the two units that publish a zero with no receipt, the domain token on the risk unit, the sweep-scoped L1 supply flag, the unexpressible cross-layer wave order, and the importance term that never reached Layer 5.

# Layer 4 — ranking, receipts, and the activation chain

## 0. What this responds to

A product-manager review raised eight items. Seven were real; one was wrong for this checkout. **Six of the seven were already self-reported** in `L4_V2_BUILD_RECORD.md` §12.7 — the review restated the build record's own open list rather than finding new ground. The value of this round was in the root causes underneath them, which §12.7 named as symptoms.

| # | Raised | Verdict |
|---|---|---|
| 1 | three ranking components constant | **real** — root cause below, deeper than "the units don't move it" |
| 2 | `core.impact` / `core.opportunity` publish a zero with no receipt | **real** |
| 3 | `core.risk` emits `deal_momentum_risk` on non-deal situations | **real, but deliberate** — a documented freeze, pinned by a test |
| 4 | `l1_scoring_active` measured per sweep, not per tenant | **real, and worse** — two contradictory definitions |
| 5 | activation order advisory, not enforced | **real at the write; the live hole was at runtime** |
| 6 | K4 unmeasured | real, not code |
| 7 | K7 scenario unreachable on Gmail+Calendar | **wrong for this checkout** — `capture/connectors/dispatch.py` registers gmail, gcal, hubspot, notion, gdrive, database, push_ingest. Reach is a per-tenant *connection* question, not a code ceiling |
| 8 | no canonical `DecisionObject` envelope | **real** — see §5 |

## 1. P1 · Why three of six ranking components were constant

Not a formula bug. A **wiring gap with two independent halves**, and fixing either alone would have left the component flat.

**Half one — the priors were never passed.** `adapters/expertise._plays` constructed every `PlayDefinition` without `impact_bp`, `effort_bp` or `risk_bp`, so all three took the dataclass defaults of `5_000`. `success_probability_bp` came from the org's measured efficacy where it existed and fell back to the same `5_000` everywhere else — which is every play on every tenant on day one. `legacy_pack.py:286` had already met and fixed this one lane over; the compiled lane reintroduced it.

**Half two — the measured half had no path to the score.** A unit reaches the ranking only through an authored `{play_id: delta}` map. Authored count across the whole repository:

| key | read by | authored in |
|---|---|---|
| `play_impact_bp` | `core.impact` | `deal_cooling_v2` only |
| `play_risk_reduction_bp` | `core.risk` | `deal_cooling` only |
| `play_success_bp` | `core.recommendation` | **nowhere at all** |
| `play_effort_bp` | **nothing** | `deal_cooling_v2` — dead config |

`adapters/expertise.py` — the roster that actually runs — authored none of them. So `core.impact`, `core.risk`, `core.opportunity` and `core.recommendation` ran on every compiled tenant, measured their dimension, iterated an empty map and moved the score by exactly zero.

**The fix.** New `adapters/play_priors.py` derives all four components from what the corpus actually declares — step count and per-step `actor` for effort, `failure_modes`/`limits`/`do_not_use_when`/`status` for risk, `outcomes`/`metrics`/`objects_used`/`conditions`/`signals`/`variants`/situation-fit for impact, `done_when` coverage and `status` for success — with a per-term receipt naming the field each was read from. `_DELTA_CONSUMERS` in `expertise.py` then authors the three live delta maps so the measured half reaches the score.

**Measured on the shipped corpus (228 playbooks):**

| component | before | after | at ceiling |
|---|---|---|---|
| impact | 1 value | 24 | 0/228 |
| effort | 1 value | 31 | 4/228 |
| risk | 1 value | 10 | 0/228 |
| success | 1 value | 11 | 0/228 |

**Calibrated twice, and the first cut was wrong.** Initial rates put **115 of 228 playbooks on the risk ceiling** and clamped the top ~15% of impact to an identical 10,000 — the same constant, arriving one layer further in, on exactly the half of the distribution that decides what gets shown first. Impact's terms now sum to precisely `BP_MAX`, so the scale is reachable without a pile-up beneath a clamp.

**And on the engine's own K1 gate:** distinct `final_utility_bp` over 4,480 ranked candidates went **360 → 835** (it was **1** before the Z3 wave).

### Two defects found while wiring it

- **`play_effort_bp` is dead config.** `deal_cooling_v2` authors it into `core.cost`'s config and nothing reads it — `cost_unit` corrects effort by comparing declared `effort_bp` against `_step_effort`. Copying that pattern onto the compiled lane would have shipped 228 playbooks' worth of config nothing consumes, which is the exact silent no-op this round exists to remove. `core.cost` is therefore **deliberately absent** from `_DELTA_CONSUMERS`, and a test pins the absence together with its reason.
- **`cost_unit._step_effort` prices every step as human.** `PlayDefinition.steps` is a tuple of strings, so the actor is gone by the time the unit sees it. Harmless while `effort_bp` was a flat 5,000; actively wrong the moment it is derived from the actor mix — a nine-step *automated* play would read as drifted and be "corrected" back up by the full 3,000bp ceiling, re-imposing the human assumption. The adapter now states `effort_basis_bp` on the play and the unit reads it, falling back to the flat rate for every hand-authored native capability, whose numbers do not move.

## 2. P2 · One answer to "is Layer 1 scoring here"

The flag was measured over the current sweep's slice (`limit`, default 500) while its own comment claimed it was *"a property of the tenant's supply, never of one situation"*. **The scope bug was the smaller half.** Two modules answered the same question with opposite results on an empty supply:

- `reason/domain_shadow` — `any(importance_bp is not None)` over the slice; empty ⇒ **False**
- `context/importance.assess_l1_supply` — flatness-based; empty ⇒ **True**

Same tenant, same sweep, one question, two answers. Now: `read_l1_scoring_live` is one tenant-scoped `select exists`, **fail-strict** (an unreadable table holds a situation for retry rather than admitting it unscored), and `assess_l1_supply` keeps the flatness question it was always actually answering. `L1Supply.scoring_live` is `None` for the fold, because a fold over an iterable cannot know it. The sweep's own reading is kept **beside** the tenant fact as `l1_scored_in_sweep` — the two disagreeing is the interesting case and the old fold silently collapsed it.

## 3. P3 · The wave order that crossed a layer

`PRECONDITIONS` ordered the five L4 switches against each other and stopped. The consequential ordering was not expressed anywhere, not reported anywhere, and **not computable**: `ranking_v2` live on a tenant whose Layer 1 was never activated is the six-weight model permanently reweighing five, recording `L2_IMPORTANCE_NOT_ACTIVE` on every decision — all true, all receipted, and the console said `live: true`.

New `CROSS_LAYER_PRECONDITIONS` + `missing_cross_layer_preconditions`, surfaced on the console read, on the activation write, and in the sweep's own counts. **Reported, never enforced** — the same argument the intra-layer map makes: an operator debugging a pilot at 2am must be able to switch one thing on in isolation, and a gate that silently ignored a switch because a different switch was off is harder to diagnose than the ordering it enforced.

## 4. P4 · The domain token

The freeze was defensible for **stored rows** and quietly covered the **ongoing emission** too: `core.risk` writes its code on every situation it scores, including `account_admin` and support situations, so the word kept arriving on new cards. A frozen string that keeps being written is not a legacy row.

`RISK_REASON_CODE` is now `do_nothing_exposure` — the finding's own name. `LEGACY_RISK_REASON_CODE` survives as a **read-side alias**, with `RISK_REASON_CODES` as the pair, so nothing stored is orphaned. The pin test now asserts the alias is never referenced on the write path.

## 5. P5 · The importance term never reached Layer 5

The score decomposition is written twice by two mechanisms that must agree and had no way to — `publication._score_inputs` copies it onto the row, `authority.AUTHORITATIVE_SCORE_INPUTS_SQL` re-derives it from immutable audit rows. They had drifted to **different key sets**: `U I S E K C` stored against `U I R C` proved, so four stored keys had no proof and the proof's `R` had no stored counterpart.

**And neither carried importance** — the largest weight in the engine under `ranking_v2`, 2,500 of 10,000. A card answering "why is this first today" could name every reason except the biggest one.

Now `SCORE_INPUT_KEYS` names the decomposition once; importance publishes as `M` on both sides. The proof reads it from `selected_rc.score_components` rather than a unit metric — importance is composed by Layer 2 and inserted outside `guards.CANDIDATE_COMPONENTS` so no unit can move it, so there is no metric to coalesce, and the candidate's stored component is the exact number the formula weighted. **An absent component is omitted, not zeroed:** a five-weight capability publishing `M: 0` would be indistinguishable from a situation measured and found genuinely unimportant.

Scoped deliberately: the full `DecisionObject` envelope would need a `signals` migration for divergence and weights-version, and that data already lives in `reasoning_candidates`. The fidelity gap is what mattered and it is closed.

## 6. P0 · `scripts/stack_activation.py`

Four layers, four activation shapes, and no way to ask *is this tenant switched on end to end, and where does the chain break*. The script reads through each layer's **own** reader (never a hand-written join — a fifth definition of "live" would drift from all four), reports the **first blocking link** rather than five consequences of one cause, and carries the remedy command for each. `l2_analytic` is explicitly **not** blocking: it is a declaration, not a gate, and saying otherwise would send an operator to fix nothing.

## 7. Verification

- `tests/reason`: **720 passed, 84 skipped, 0 failed**
- `tests/reason/adapters/test_play_priors.py`: **17 new tests**, pinning the spread, the receipts, purity, sorted delta maps, and that every authored delta key is read by the unit that owns it
- Prior distributions measured against the real 228-playbook corpus, not fixtures
- Three failures during the round were diagnosed rather than patched: two were my own comment leaking the domain token (the scanner was right), one was a stale-bytecode artifact of editing files mid-run and not a defect

## 8. What is NOT done

- **K4** — fallback rate, the 25-bundle golden review, citation fidelity and latency. Needs one real model run; no model is reachable in this environment.
- **K7** — seven days on a real tenant. The scenario should be chosen from what that tenant's connectors actually reach; the "Gmail+Calendar only" framing does not match `dispatch.py`.
- **Full-suite-on-pristine-Postgres** re-verification after this round.
- **The `DecisionObject` envelope proper** — deferred with its reason in §5, not dropped.
- Nothing in this round is committed.

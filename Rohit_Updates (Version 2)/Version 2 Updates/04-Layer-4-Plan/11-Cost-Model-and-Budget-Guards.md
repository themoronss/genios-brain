# L4 Cost Model and Budget Guards

> L4 is the only layer where the model runs **after** the work is done. That makes its
> spend the easiest in the system to cap, cache and cut without touching a decision.

---

## 1. Per-decision cost

Tiers as in L1/L2: **T1 = Haiku-class**, **T2 = Sonnet-class**. Bundles run once per
*published* decision — never per candidate, never per suppressed decision.

| Site | When | Tier | ~in / ~out | ~$/call |
|---|---|---|---|---|
| **R-2 + R-4** (one call) | per published decision | T2 | 1,800 / 450 | **$0.012** |
| **R-3** alternatives | on card expand only | T1 | 800 / 200 | $0.002 |
| **R-1** interpreter | only on a genuine UNRESOLVED ambiguity the plan reads | T2 | 900 / 150 | $0.005 |
| **R-5** consult | rare, after DEFER, gated | T2 | 1,200 / 250 | $0.008 |

**A published decision costs ~1.2 cents to explain.** The decision itself costs nothing —
it is arithmetic.

## 2. Per-tenant monthly

A pilot org publishing ~40 decisions/day, ~15% of situations genuinely ambiguous, ~25% of
cards expanded:

| Line | Volume/day | $/day | $/month |
|---|---|---|---|
| R-2 + R-4 bundles | 40 | 0.48 | **$14.40** |
| R-3 expands | 10 | 0.02 | $0.60 |
| R-1 interpretations | 12 | 0.06 | $1.80 |
| R-5 consults | 3 | 0.02 | $0.72 |
| **Total** | | **$0.58** | **≈ $17.50** |

Against a $100/month product, L4's narrative spend is **~18% of one seat** — and it is the
part the customer actually reads. Cache hits (repeat surfacing of the same decision) cut
it further; the model assumes **zero** cache benefit, so the real number is lower.

## 3. The guards

| # | Guard | Behavior |
|---|---|---|
| 1 | **Per-org daily cap** | on breach → `template_fallback`, recorded; **decisions never stop** |
| 2 | **Cache on `decision_hash`** | a re-surfaced decision never regenerates |
| 3 | **Published-only** | suppressed and DEFERred decisions generate no bundle |
| 4 | **One retry, then template** | no retry storms; every failure recorded with its reason |
| 5 | **Off the critical path** | bundles generate after publication — a slow model never delays a decision |
| 6 | **Per-tenant activation** | `l4_activation(org,'bundle')` — spend is opt-in per org |
| 7 | **R-1 precondition** | fires only on an UNRESOLVED flag on a fact the plan actually reads — never "just in case" |
| 8 | **Tier discipline** | T2 only for R-2/R-1/R-5; narration of already-decided alternatives is T1 |

## 4. What is deliberately NOT spent

| Not done | Why |
|---|---|
| No model in the decision path | the doctrine — and it keeps decisions free |
| No embeddings anywhere | v2 standing rule |
| No bundle per candidate | only the winner is explained |
| No free-text Q&A | doc 06 OUT-3 — *"you don't have to ask"* |
| No re-generation on re-read | cache + `bundle_hash` |

## 5. Acceptance

| Metric | Gate |
|---|---|
| measured $/published decision on the pilot | ≤ $0.02 |
| measured $/tenant/month | ≤ $25 |
| cap breaches degrading to template | 100% recorded, 0 decisions blocked |
| bundles generated for suppressed decisions | **0** |
| cache hit rate on re-surfaced decisions | > 60% |

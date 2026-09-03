# L4 — Edge Cases and Loops

> The HKS discipline: every case named before shipping, every loop given a guard that is
> structural rather than hopeful.

---

## 1. R-2 · Reasoning Bundle — the most exposed surface

| # | Case | Guard |
|---|---|---|
| 1 | Narrative asserts a fact no unit found | V-1 drops the sentence; >5% drops → template fallback |
| 2 | 🔴 **Narrative contradicts the decision** (*"consider renewing"* on a don't-renew) | **V-3 action-id match, constructor-level reject** — the single worst output this layer could produce |
| 3 | A number drifts ($84K → $840K) | placeholders only; a bare digit fails V-4 |
| 4 | Root-cause story sounds more certain than the confidence vector | hedging bound to the vector's weakest axis: `coverage 6200` ⇒ the prose must carry the qualifier |
| 5 | Expected effect over-promises | computed values only; hypothesis status carried (*"estimate"* until L7-tuned) |
| 6 | Citation paraphrased instead of quoted | V-2 byte-identity (L3's validator, reused) |
| 7 | Visibility leak through prose | bundle inputs pre-filtered by `narrowest()` — structural, not prompt-based |
| 8 | Budget exhausted mid-day | template fallback, `generation` recorded, quality still measurable |
| 9 | **Hinglish / mixed-script material** | bundle language follows card locale; the golden set includes mixed-script threads (the corpus is Hinglish-bearing — established at L2) |
| 10 | The same decision re-surfaced tomorrow reads differently | cache on `decision_hash` + `bundle_hash`; regeneration is explicit, never incidental |

## 2. R-1 / R-5 · Interpretation

| # | Case | Guard |
|---|---|---|
| 11 | Interpreter upgrades speculation to fact (*"probably moving"* → `decision_made`) | closed classification enum + confidence; consumed as evidence in the `llm_interpretation` independence group — **it can never be the sole basis for a Rule 11 raise** |
| 12 | The same ambiguous claim interpreted differently across drains | cached by claim hash; one interpretation per claim version |
| 13 | R-5 asked to fill a missing fact | refused by construction — R-5 interprets *held* evidence; a missing fact DEFERs to a human |
| 14 | An interpretation outlives the text it read | interpretation carries the evidence id + `observed_at_key`; a superseded claim invalidates it |

## 3. Critique seam (doc 06 OUT-1)

| # | Case | Guard |
|---|---|---|
| 15 | An agent games critique by re-submitting variants | responses cached by proposal hash; per-agent daily critique budget |
| 16 | `proceed` read as GeniOS *authorization* | `advisory: true` is unfalsifiable at the constructor; accountability stays with the agent (L5's delegation contract) |
| 17 | An external candidate crashes a path built for authored plays | schema-validated first; unparseable → `hold` with `unscoreable`, never an exception |
| 18 | Critique used as a back door to free-text Q&A | `kind` is a closed enum; a proposal that is not an action is refused, not answered |

## 4. Decision-path edge cases (no model involved)

| # | Case | Guard |
|---|---|---|
| 19 | Every optional unit skips on a thin situation | confidence degrades → below floor → **DEFER with the missing inputs named** (correct behavior, not a failure) |
| 20 | Importance absent because L2-X5 is off for this org | five-component reweigh + `L2_IMPORTANCE_NOT_ACTIVE` — **never a 5000 default** |
| 21 | Two units publish conflicting readings of the same metric | max-wins where declared (priority's existing rule); otherwise both retained and the conflict surfaces in `situation.conflict.*` |
| 22 | A corpus rule is unevaluable (UNKNOWN predicate) | receipted `rule_unevaluable` — neither fires nor blocks |
| 23 | An override arrives with no formula | impossible: the formula always runs, and `formula_utility` is always recorded |

---

## 5. Loops

| # | Loop | Hazard | Guard |
|---|---|---|---|
| **L-1** | decision → card → feedback → L7 → weights → next decision | oscillating weights | weights versioned; changes batched under L7 governance, never mid-sweep |
| **L-2** | re-decision on unchanged evidence | the same situation re-decided every drain; cards churn | the existing no-new-evidence suppression stays authoritative; the R-2 cache makes re-renders free |
| **L-3** | critique → agent modifies → re-critique | endless modify loop | per-proposal chain depth **3**, then `hold` with `escalate_to_human` |
| **L-4** | brief re-rank → card ignored → staleness decay → re-rank | a true decision decays into invisibility | decay floors at rank-visibility, **never at suppression**; any new evidence resurfaces it |
| **L-5** | unit DAG cycles | non-termination | already impossible — topological validation at plan time (**preserve hard**) |
| **L-6** | R-1 interpretation becomes evidence → re-triggers ambiguity → R-1 again | interpretation feedback | an `llm_interpretation` EvidenceRef is **never itself eligible for R-1** — one hop, structural |

**The derivation-DAG law carries over from L2:** no L4-computed value may be an input to
its own computation. `scripts/derivation_dag_check.py` extends to `reason/`.

---

## 6. Convergence — how we know the loops settle

| Signal | Healthy | Investigate |
|---|---|---|
| decisions re-published per situation per week | ≤ 2 | > 4 → L-2 suppression leaking |
| critique chains reaching depth 3 | < 5% | > 15% → the corpus is ambiguous, not the agent |
| cards decaying to invisibility while still open | < 10% | rising → L-4 decay too steep |
| bundle regeneration rate on unchanged decisions | ~0 | > 5% → cache key wrong |
| `ConfidenceViolation` count after Z3 lands | trends to 0 | flat > 0 → a unit is trying to raise uncited |

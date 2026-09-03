# L4 — Edge Cases, Loops, and the Two Worked Scenarios

---

## 1. R-site edge cases (the HKS discipline — every case named before shipping)

### R-2 · Reasoning Bundle — the most exposed surface

| # | Case | Mitigation |
|---|---|---|
| 1 | Narrative asserts a fact no unit found | V-1 sentence-drop; >5% drops → template fallback |
| 2 | **Narrative contradicts the decision** (*"consider renewing"* on a don't-renew) | V-3 id-match — **hard reject**; the single worst output this layer could produce |
| 3 | A number drifts ($84K → $840K) | placeholders only; bare number = reject |
| 4 | Root-cause story more confident than the confidence vector | narrative hedging bound to the vector's weakest axis: `coverage 6200` ⇒ the prose must carry the qualifier |
| 5 | Expected effect over-promises | V-6: computed values only, hypothesis status carried (*"estimate"* until L7-tuned) |
| 6 | Citation paraphrased | V-4 byte-identity (L3 validator reused) |
| 7 | Visibility leak via narrative | input pre-filtered `narrowest()` — structural |
| 8 | Budget out mid-day | template fallback, `generation` recorded, quality measurable |
| 9 | **Hinglish thread material** | bundle language follows card locale; golden set includes mixed-script material (the corpus is Hinglish-bearing — established at L2) |

### R-1 / R-5 · Interpretation

| # | Case | Mitigation |
|---|---|---|
| 10 | Interpreter upgrades speculation to fact (*"probably moving"* → `decision_made`) | closed classification enum + confidence; consumed as evidence with `llm_interpretation` independence group — **it can never be the sole basis for a raise** (Rule 11 needs a different group) |
| 11 | Same ambiguous claim re-interpreted differently across drains | cached by claim hash; one interpretation per claim version |
| 12 | R-5 asked to fill a missing fact | refused by construction — R-5 only interprets held evidence; missing facts DEFER to a human |

### Critique seam (S4)

| # | Case | Mitigation |
|---|---|---|
| 13 | Agent games the critique by re-submitting variants | critique responses cached by proposal hash; per-agent daily critique budget |
| 14 | `proceed` read as GeniOS authorization | verdict payload carries `advisory: true`; execution accountability stays with the agent (L5's delegation contract) |
| 15 | External candidate crashes a scoring path built for plays | ExternalCandidate is schema-validated first; unparseable → `hold` with `unscoreable`, never an exception |

---

## 2. Loops

| # | Loop | Hazard | Guard |
|---|---|---|---|
| L-1 | Decision → card → feedback → L7 → weights → next decision | oscillating weights | weights versioned; changes batched (L7's governance), never mid-sweep |
| L-2 | **Re-decision on unchanged evidence** | the same situation re-decided every drain, cards churn | the existing no-new-evidence suppression stays authoritative; R-2 cache makes re-renders free |
| L-3 | **Critique → agent modifies → re-critique** | endless modify loop | per-proposal chain depth 3; after that `hold` with `escalate_to_human` |
| L-4 | Brief re-rank → card ignored → staleness decay → re-rank | a decision decays to invisibility while still true | decay floors at rank-visibility, never at suppression; a decayed-but-live decision resurfaces on ANY new evidence |
| L-5 | Unit DAG cycles | non-termination | already impossible — topological order is validated at plan time (preserve-hard) |
| L-6 | R-1 interpretation becomes evidence → re-triggers ambiguity → R-1 again | interpretation feedback loop | an `llm_interpretation` EvidenceRef is never itself eligible for R-1 — one hop, structural |

**The derivation-DAG law from L2 carries over:** no L4-computed value may be an input to
its own computation. `scripts/derivation_dag_check.py` extends to reason/.

---

## 3. Scenario A — AWS renewal through L4 v2 (the Theory-chat trace, completed)

Input: the L2 v2 BSO from the L2 worked example — importance 10000, DECLINING trend,
top-decile cohort, anomaly flagged, `decision.scheduled GENUINELY_ABSENT`, conflict-free,
plus L3's package with citations and one blocking rule.

```
PLAN     selector schedules 14 units (money+dates present → cost/impact in;
         resource/scheduling skipped, receipted)
UNITS    timeline: urgency_bp 7500 (12 days, EXACT date — not neutral 5000)
         impact: 84,00,000 minor units exposure   cost: do_nothing_cost_bp computed
         risk: migration-window lock-in           opportunity: renegotiation headroom
         tradeoff: annual vs short-term vs migrate, cost axis LIVE (U4 fixed)
         validation: evidence sufficient → publishes confidence_bp support
R-1      Slack line "probably moving some workloads" → {proposal, 7200} as evidence
CHECKS   corpus rule (via S3): "never lock a term during an active platform decision"
         → ELIMINATES annual-renewal candidate, rule id into alternatives_rejected
SCORE    components: importance 10000 · impact 8100 · urgency 7500 · effort/risk costs
         formula DECIDES (override now a 30% prior); review-this-week wins
CONF     Rule 11: starts from BSO vector min (6200 — coverage), lowered nowhere,
         no raise claimed → 6200, vector carried
FLOOR    6200 > 4500 → publishes
R-2      Bundle:
         WHY THIS MATTERS  {amount} auto-renews in {days}; spend {pct} above baseline
         ROOT CAUSE        cancellation window + no owner + live migration discussion
         RECOMMENDATION    review before {deadline} — cites the corpus rule verbatim
         EXPECTED EFFECT   doing nothing commits {amount} for 12 months (computed)
         ALTERNATIVES      annual renewal eliminated by <rule>; migrate scored lower
                           on execution risk
GAUNTLET all claims trace ✓ numbers placeholdered ✓ action id matches ✓
OUT      DecisionObject + ReasoningBundle → L5
```

**LLM calls: 2** (R-1, R-2). Decision: 100% deterministic. Card: founder-bar detail.

## 4. Scenario B — investor follow-up (Theory-chat example 1)

The condition-satisfaction signal arrives from L2 (BLG-06/M-5: *"reconnect after
enterprise traction"* — satisfied, both evidence spans). L4: opportunity unit reads
`situation.condition_satisfied.*`; urgency from the satisfaction half-life (30-day decay
— a satisfied condition is perishable); the critique seam then serves the outreach
agent: its draft is scored, the corpus heuristic *"lead with the requested signal, not
general progress"* arrives as a citation in `modify`'s rationale. **This scenario runs
only on L2-X6 + L3-Y2 (`opportunity_tracking` capability) — recorded as the cross-layer
dependency it is.**

## 5. The golden test, applied to L4

Every scenario card answers the Theory chat's bar: *could the founder have found this in
10 seconds?* A bundle that restates one email fails regardless of how well-formed it is.
The pilot review (K6) hand-scores 25 bundles against exactly that question.

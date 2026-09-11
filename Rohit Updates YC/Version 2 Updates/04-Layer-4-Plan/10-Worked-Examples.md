# L4 — Worked Examples (the two Theory-chat traces, completed)

---

## Scenario A — the AWS renewal, end to end through L4 v2

**Input** — the L2 v2 BSO from the L2 worked example: importance 10000, DECLINING trend,
top-decile cohort, anomaly flagged, `decision.scheduled` GENUINELY_ABSENT, conflict-free —
plus L3's ExpertisePackage with citations and one blocking rule.

```
PLAN     the selector schedules 14 units (money + dates present -> cost/impact IN;
         resource/scheduling skipped, receipted with the absent fields named)

UNITS    core.timeline      urgency_bp 7500      (12 days, EXACT date - not neutral 5000)
         core.temporal      drop_bp              (scheduled now: risk stops being blind)
         core.impact        exposure computed from the contract value
         core.cost          do_nothing_cost_bp computed  (E4's real number)
         core.risk          migration-window lock-in     (all three plugins live)
         core.opportunity   renegotiation headroom
         core.tradeoff      annual vs short-term vs migrate - cost axis LIVE (U4 fixed)
         core.validation    evidence sufficient -> supports confidence

R-1      a Slack line, "probably moving some workloads", is UNRESOLVED-ambiguous
         -> {classification: EVALUATING_ALTERNATIVES, confidence_bp: 7200}
         -> emitted AS EVIDENCE, independence group llm_interpretation

CHECKS   corpus rule via IN-2: "never lock a term during an active platform decision"
         -> ELIMINATES the annual-renewal candidate
         -> the rule id travels into alternatives_rejected

SCORE    components: importance 10000 - impact 8100 - urgency 7500 - success/effort/risk
         THE FORMULA DECIDES (the override is now a 30% prior)
         winner: review-this-week

CONF     Rule 11: starts at the BSO vector minimum (6200, coverage axis)
         lowered nowhere; no RaiseClaim presented -> 6200, vector carried

FLOOR    6200 > 4500 -> publishes    (below it, a reason-coded DEFER instead)

R-2      the bundle:
         WHY THIS MATTERS  {amount} auto-renews in {days}; spend {pct} above baseline
         ROOT CAUSE        cancellation window + no owner + a live migration discussion
         RECOMMENDATION    review before {deadline} - cites the corpus rule verbatim
         EXPECTED EFFECT   doing nothing commits {amount} for 12 months (computed)
         ALTERNATIVES      annual renewal eliminated by <rule id>; migrate scored lower
                           on execution risk

GAUNTLET V-1 every claim traces / V-2 citation byte-identical / V-3 action id matches
         V-4 no bare numbers / V-5 all placeholders resolved -> PASS

OUT      DecisionObject + ReasoningBundle -> L5
```

**LLM calls: 2** (R-1, R-2+R-4 in one). **Decision: 100% deterministic.**
**Card: founder-bar detail.** Cost: ~$0.017.

### What each layer had to be alive for
| Layer | Contribution | Without it |
|---|---|---|
| L1 W7 | `importance_bp` on the signals | the 2500-weight component reweighs away |
| L2 X5 | situation importance, trend, cohort | the card ranks like every other card |
| L3 Y1 | the blocking rule + citation | the wrong action is never eliminated; the bundle has nothing to quote |
| **L4** | **the decision, the silence, and the words** | **facts, not intelligence** |

---

## Scenario B — the investor follow-up (Theory chat, example 1)

**The condition-satisfaction signal** arrives from L2 (BLG-06 / M-5: *"reconnect after
enterprise traction"* — satisfied, both evidence spans present).

```
L4       core.opportunity reads situation.condition_satisfied.*
         urgency from the satisfaction half-life  (30-day decay - a satisfied
                                                   condition is perishable)
         formula ranks it against the day's other work
OUT-1    the outreach agent submits its draft to /v1/intelligence/critique
         -> scored against the same checks and evidence as an authored play
         -> verdict: modify
         -> rationale cites the corpus heuristic verbatim:
            "lead with the requested signal, not general progress"
```

**Cross-layer dependency, recorded as such:** this scenario runs only when **L2-X6** and
**L3-Y2** (`opportunity_tracking` capability) are live. Until then L4 has nothing to read,
and no amount of L4 work produces this card — exactly the class of dead-seam this whole
audit was written to prevent.

---

## The golden test

Every card answers the Theory chat's bar:

> **Could the founder have found this in 10 seconds themselves?**

A bundle that restates one email fails, however well-formed it is. The pilot review (K7)
hand-scores 25 bundles against exactly that question — not against grammar, not against
length, against whether it was worth a founder's attention.

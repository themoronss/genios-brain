# Seams — what comes IN from L2/L3, what goes OUT to agents and the brief

> A layer is only as good as its seams. L4's are the reason a fully-fixed L2 and L3 would
> still change nothing a customer sees.

---

# IN-1 · L2 BSO v2 → the snapshot the units read (DLG-06)

**VERIFIED GAP** — units read a `ContextSnapshot`; the **BSO stops at the compiler**.
Everything L2 v2 computes — trends, cohort percentiles, anomalies, conflicts, typed
absence — would be stamped and **invisible to every unit**. This is the importance
dead-seam repeated at scale.

**FIX** — the compiled-lane snapshot builder projects BSO v2 fields into namespaced
snapshot facts, each with an evidence ref minted through IN-1's one builder (doc 03 S2):

```
situation.trend.<metric>      direction · slope · streak · confidence
situation.cohort.<metric>     percentile_bp · cohort_id · population
situation.anomaly.<metric>    z_like · deviation
situation.conflict.<field>    claims summary · resolution state
situation.missing.<fact>      absence type      (UNKNOWABLE ≠ GENUINELY_ABSENT, as everywhere)
situation.pattern_id · situation.matched_conditions
```

Units then consume them as ordinary **declared fields** — which is exactly what the
selector (doc 01 C1) needs in order to schedule trend-aware units on trend-bearing
situations and skip them elsewhere.

**ACCEPTANCE** — a BSO carrying a DECLINING trend produces a snapshot fact a fixture unit
reads and cites; UNKNOWABLE facts project as unknown-typed, **never as values**.

---

# IN-2 · L3 `compiled_constraints` → eliminations (DLG-07)

**VERIFIED GOOD NEWS — the landing strip is built.** The chain
`CandidateCheck(ELIMINATE) → ELIMINATED disposition → rejected_candidates persisted →
alternatives_rejected` in the API **works end to end today**. Missing only the producer
(L3-Y1) and one mapping.

**L4-side work (small)** — `adapters/expertise.py` maps each compiled constraint
`{rule_id, severity, predicate_tree, source_ref}` to a `CandidateCheck`:

| Severity | Mapping |
|---|---|
| blocking | `ELIMINATE` — **the rule id travels** into `alternatives_rejected` |
| warning | annotation on the candidate, surfaced in the bundle |

Predicate evaluation reuses the **L2 cohort grammar's three-state evaluator**: TRUE fires,
FALSE does not, **UNKNOWN neither fires nor blocks and is receipted `rule_unevaluable`**
(L3-Y1's law, honored at the consumer). Citations pass straight through to the bundle.

**WHY THIS IS THE UNLOCK** — it is what turns 1,389 corpus files from documentation into
something that removes a wrong action from a founder's day.

**ACCEPTANCE** — the `urgency-must-belong-to-the-buyer` fixture eliminates a candidate and
`alternatives_rejected` **names the rule**; UNKNOWN predicates receipt, never decide.

---

# OUT-1 · The critique endpoint (E1) — evaluate without emitting (DLG-10)

**VERIFIED STATE** — `/v1/intelligence/query` returns one fixed recommendation and one
validated sentence; handoff returns 501; **there is no path for an agent's proposed action
to be scored.** The action space is closed to authored plays — correct for *emission*, too
closed for *evaluation*.

**FIX**
```
POST /v1/intelligence/critique          scope: intelligence.critique (agent-grantable)
  in:  {target_ref, proposed_action: {kind, draft, params}}
  do:  wrap as ExternalCandidate -> scored by the SAME score_candidate, checked by the
       SAME CandidateChecks (corpus blocking rules apply to agent proposals too),
       against the SAME situation evidence
  out: {verdict: proceed | modify | hold,
        failing_checks: [rule ids],
        winning_alternative: <authored play that outscored it, if any>,
        utility_bp, confidence_bp,
        rationale: R-3-narrated, evidence-bound}
```

**The closed-action-space law stands.** GeniOS still never *executes* an external
candidate — it scores, critiques and answers. `advisory` is locked True at the
constructor. Execution stays with the agent, governed by L5's delegation machinery.

**WHY IT MATTERS** — this is the customer sentence *"agent X is about to send this —
change it this way"*, answerable for the first time, and it is the shape of the
agent-consults-GeniOS future the founder is selling.

**ACCEPTANCE** — an agent draft violating a blocking corpus rule returns `hold` **with the
rule named**; a reasonable draft returns `proceed` or `modify` with a scored alternative.

---

# OUT-2 · Book-level brief ranking (E3) (DLG-09)

**VERIFIED STATE** — every ranked surface is a read-time `ORDER BY final_utility_bp` over
independently-scored rows. **No pass ever compares the day's candidates against each
other**, so "the 3 things that matter this morning" is arithmetic, not judgment.

**FIX — one deterministic executive pass** (the L4 half; rendering is L5.2's plan):
```
daily, per org:
  take open decisions above the floor
  book_score = final_utility_bp adjusted by portfolio terms (all deterministic):
      concentration — three cards on one account compete; the best carries
      staleness     — surfaced N times unactioned decays
      coverage      — an UNKNOWABLE-heavy decision ranks below an evidenced one
  emit BriefRanking{entries, each with rank_components}
```
**No new scores are invented** — existing ones are re-weighed with portfolio context, and
`rank_components` makes *"why is this #1 today"* answerable in data.

**ACCEPTANCE** — a stable, explainable top-3 on the pilot; a thrice-ignored card decays;
three same-account cards yield one carrier.

---

# OUT-3 · `run_query` — the scope decision, stated

The day-1 finding stands: `/v1/intelligence/query` retrieves and re-phrases already-fired
signals; it cannot generate judgment for an arbitrary question. **L4 v2 deliberately does
not build a free-text Q&A reasoning mode.**

**Why** — the product law, in both Globe and the Theory chat: *"You don't have to ask"* /
*"not an AI assistant you ask questions."* The E1 surface is **critique** (OUT-1) —
evaluate a proposed action — not open Q&A. `run_query` gains the Reasoning Bundle on its
fixed recommendation and nothing more. A queryable-assistant surface, if ever wanted, is a
product decision with its own plan, not a seam slipped in here.

---

## Seam acceptance gate — G-SEAM

| Metric | Gate |
|---|---|
| BSO trend visible to a unit as a declared snapshot fact | demonstrated |
| UNKNOWABLE projected as unknown-typed | 100% — never a value |
| corpus blocking rule eliminating a candidate, rule id in `alternatives_rejected` | demonstrated |
| corpus rule eliminating an **agent's** proposed action via critique | demonstrated |
| `advisory` falsifiable | **impossible** (constructor) |
| BriefRanking produced daily with `rank_components` | on the pilot |

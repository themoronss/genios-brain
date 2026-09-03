# L4.3 Evidence Layer + the Seams (in from L2/L3, out to agents and the brief)

---

# S1 · Evidence shape fix (DLG-11)

**Verified state:** the Store is the strongest part of L4 (content-addressed, atomic,
hash-verified replay). The shape around it is inverted vs spec: evidence is **input**
minted by adapters before any unit runs; `EvidenceRef` lacks `unit_ref/claim/value_bp`;
**three builder sites with different id seeds** (the same fact gets different identities
per lane); values live in a **720h-TTL** payload table — after purge a decision can no
longer say what its evidence *said*.

**Fixes (all small, all deterministic):**
1. **`Finding` is canonized as the per-unit evidence emission** — it already carries the
   claim; add optional `value_bp`; `unit_ref` derives from the emitting `reasoner_id`.
   No new object.
2. **One `build_evidence_ref()` helper, one seed shape** — the three adapter sites call
   it. Same fact → same evidence identity on every lane. A migration maps historic ids.
3. **Value digest beyond TTL** — persist `{value_digest, unit, rendered_text[:120]}`
   permanently beside the ref; the full payload keeps its TTL. Replay after purge
   degrades to digest-verification instead of failing closed.

**ACCEPTANCE** — same fixture fact through all three lanes yields one evidence id; a
post-TTL replay verifies digests and says so; every Finding carries its unit_ref.

# S2 · BSO v2 → snapshot projection (DLG-06)

**Verified gap:** units read a `ContextSnapshot`; the BSO stops at the compiler. X5's
trends/cohorts/anomalies/conflicts would be computed, stamped, and **invisible to every
unit** — the importance dead-seam repeated at scale.

**Fix:** the compiled-lane snapshot builder projects BSO v2 fields into namespaced
snapshot facts with evidence refs minted at build time (via S1's one helper):

```
situation.trend.<metric>        direction, slope, streak, confidence
situation.cohort.<metric>       percentile_bp, cohort_id, population
situation.anomaly.<metric>      z_like, deviation
situation.conflict.<field>      claims summary, resolution state
situation.missing.<fact>        absence type       (UNKNOWABLE ≠ absent, as everywhere)
situation.pattern_id / matched_conditions
```

Units then consume them as ordinary declared fields — which is exactly what doc 01's
selector needs to schedule trend-aware units. **ACCEPTANCE:** a BSO with a DECLINING
trend yields a snapshot fact a fixture unit reads; UNKNOWABLE facts project as
unknown-typed, never as values.

# S3 · compiled_constraints consumer (DLG-07) — the landing strip is built

**Verified good news:** the elimination chain **exists end to end** — `CandidateCheck
ELIMINATE → ELIMINATED disposition → rejected_candidates persisted → alternatives_rejected`
in the API. Missing only the producer (L3-Y1) and one mapping.

**L4-side work (small):** `adapters/expertise.py` maps each `compiled_constraint`
{rule_id, severity, predicate_tree, source_ref} into a `CandidateCheck` — blocking →
ELIMINATE (the eliminating **rule id travels** into `alternatives_rejected`), warning →
annotation. Predicate evaluation reuses the L2-cohort grammar three-state evaluator:
**UNKNOWN neither fires nor blocks, receipted `rule_unevaluable`** (L3-Y1's law, honored
at the consumer too). Citations pass through to the Reasoning Bundle.

**ACCEPTANCE** — the `urgency-must-belong-to-the-buyer` fixture eliminates a candidate
and `alternatives_rejected` names the rule; UNKNOWN predicates receipt, never decide.

# S4 · The consult seam (E1) — ExternalCandidate + critique (DLG-10)

**Verified state at HEAD:** `/v1/intelligence/query` = one fixed recommendation + one
validated sentence; handoff returns 501; no path for an agent's proposed action to be
scored. The action space is closed to authored plays (Law 02) — correct for *emission*,
too closed for *evaluation*.

**Fix — evaluate without emitting:**
```
POST /v1/intelligence/critique   (new agent-grantable scope: intelligence.critique)
  in:  {target_ref, proposed_action: {kind, draft, params}}
  do:  wrap as ExternalCandidate — scored by the SAME score_candidate, checked by the
       SAME CandidateChecks (corpus blocking rules apply to agent proposals too),
       against the SAME situation evidence
  out: {verdict: proceed | modify | hold,
        failing_checks: [...rule ids...],
        winning_alternative: <the authored play that outscored it, if any>,
        utility_bp, confidence_bp,
        rationale: R-3-narrated, evidence-bound}
```
**The closed-action-space law stands:** GeniOS still never *executes* an external
candidate — it scores, critiques, and answers. Execution stays with the agent, governed
by L5's delegation machinery (its own plan).

**ACCEPTANCE** — an agent draft violating a blocking corpus rule gets `hold` with the
rule named; a reasonable draft gets `proceed` or `modify` with a scored alternative; the
Theory-chat register — *"agent X is about to send this — change it this way"* — is
answerable for the first time.

# S5 · Book-level brief ranking (E3) (DLG-09)

**Verified state:** every ranked surface is read-time `ORDER BY final_utility_bp` over
independently-scored rows. No pass ever compares the day's candidates **against each
other**.

**Fix — one deterministic executive pass** (this is the L4 half; the brief's rendering
is L5.2's plan):
```
daily, per org:
  take open decisions above the floor
  book_score = final_utility_bp
             adjusted by portfolio terms (all deterministic):
               concentration  — 3 cards on one account compete, best carries
               staleness      — surfaced-N-times-unactioned decays
               coverage       — an UNKNOWABLE-heavy decision ranks below an evidenced one
  emit BriefRanking{top_n, each with rank_components}   — stored, explainable
```
No new scores are invented — it re-weighs existing ones with portfolio context, and
`rank_components` makes "why is this #1 today" answerable.

**ACCEPTANCE** — the same decision set produces a stable, explainable top-3; a
thrice-ignored card decays; three same-account cards yield one carrier.

# S6 · `run_query` — the scope decision, stated (crosscheck P-3)

The day-1 finding stands at HEAD: `/v1/intelligence/query` retrieves and re-phrases
already-fired signals; it cannot generate judgment for an arbitrary question.
**L4 v2 deliberately does NOT build a free-text Q&A reasoning mode.** The product law
(Globe and the Theory chat, verbatim): *"You don't have to ask"* / *"not an AI assistant
you ask questions."* The E1 surface is the **critique endpoint** (S4) — evaluate a
proposed action — not open Q&A. `run_query` gains the Reasoning Bundle on its fixed
recommendation (R-2 runs there too) and nothing more. If a queryable-assistant surface
is ever wanted, it is a product decision for its own plan, not a seam to slip in here.

---

## Group acceptance gate

```
pytest tests/reason/test_evidence_shape.py tests/reason/test_seams.py -q
```

| Metric | Gate |
|---|---|
| evidence id identical across lanes for the same fact | exact |
| post-TTL replay | digest-verified, not fail-closed |
| BSO trend visible to a unit as a snapshot fact | demonstrated |
| corpus rule eliminating an **agent's** proposed action via critique | demonstrated |
| BriefRanking with rank_components | produced daily on the pilot |

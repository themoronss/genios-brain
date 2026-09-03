# L4.4 — Decision Maker: the ears, Rule 11, and honest silence

> Four fixes, all deterministic, all in `reason/decision_maker.py` and its adapters.
> Together with L1-W7 and L2-X5 they complete the ranking chain — G7 → H5 → **K1**.

---

# E1 · The importance path (DLG-03) — the final link

### The verified dead-end

- `_weighted_utility` is a closed 5-component blend (impact/success/urgency/effort/risk);
  the `ranking_weights` contract fixes exactly those keys. **No importance term.**
- **Zero readers of `importance_bp` anywhere in `reason/`.**
- `priority_override_bp` replaces the formula for every live candidate.
- Urgency pinned neutral 5000 on the compiled lane (fixed by doc 01 U5).

### The fix

```
1. NEW COMPONENT  components["importance"] = situation.importance_bp
                  carried from the BSO through the adapter into every
                  CandidateScoringRequest. Sixth component, weights re-normalized:
                  importance 2500 · impact 2000 · urgency 2000 ·
                  success 1500 · effort(-) 1000 · risk(-) 1000
                  (weights versioned: ranking_weights_version on every decision)

2. DEMOTE THE OVERRIDE  priority_override_bp becomes a PRIOR, not a replacement:
                  final = (formula * 7 + override * 3) // 10   when override present
                  formula_utility keeps being recorded beside it (existing hook —
                  the divergence measurement the code already prepared for this exact
                  migration)

3. GUARD          if >90% of incoming situations still carry importance_bp == 5000,
                  log L2_IMPORTANCE_NOT_ACTIVE and keep the old path.
                  A fake spread is worse than a flat one. (Same guard as L2-X5.)
```

**Why 70/30 and not full demotion on day one:** the authored prior carries real editorial
knowledge (30 distinct values); it becomes a tie-break influence instead of a dictator,
and the recorded `formula_utility` divergence tells us when to drop it to 0/100.

**ACCEPTANCE** — two situations of the same type with different importance rank
differently (**the two-tenants-identical-ranking era ends here**); override present but
formula dominant; determinism byte-exact; components + weights version stored on every
decision.

**REVERSE PROMPT**
```
TASK: Give the utility formula its ears. This is the last link of the three-layer
ranking fix (L1 ALG-17 -> L2 BLG-18 -> here).
READ FIRST: reason/decision_maker.py:231-268 (the override that "has never once decided
anything" and the closed 5-component blend), contracts/reasoning.py:405-412.
DO: the 3 steps above, exactly. Extend ranking_weights to six keys with re-normalized
defaults; thread situation.importance_bp from the BSO through adapters/expertise.py and
adapters/native.py into components; demote the override to a 70/30 prior; keep
formula_utility recording on both branches; add the L2_IMPORTANCE_NOT_ACTIVE guard.
TESTS: same-type different-importance ranks differently; importance monotonicity;
override-as-prior arithmetic; guard fires on a flat-5000 fixture; weights version stored.
DO NOT: delete priority_override_bp; let any model near a component; change scoring on
the legacy lane before the compiled lane proves out (per-tenant activation, doc 07).
```

# E2 · Rule 11 confidence composition (DLG-05)

### The verified defect

`calculate_confidence` = default 5000 → **each completed unit's `confidence_bp`
overwrites the previous** → authority ends the scan. A later unit can raise confidence
with no named evidence. L2's 6-axis vector arrives and is collapsed by a last-writer
scalar.

### The fix — composition, not a scan

```
1. START  from the BSO's confidence vector (min of its axes), not a manifest default
2. LOWER  any completed unit may lower: value = min(value, unit_confidence)
3. RAISE  only via an explicit RaiseClaim{new_value, independent_evidence_ids} where
          the cited evidence is verifiably in a DIFFERENT independence_group
          (EvidenceRef.independence_group already exists) — else ConfidenceViolation
4. CAP    degraded-run cap stays exactly as is (decision_maker.py:136 — correct today)
5. VECTOR carry the axes through: DecisionObject.confidence_vector alongside the scalar
```

**ACCEPTANCE** — a later unit publishing a higher bare `confidence_bp` **does not raise**;
a RaiseClaim citing same-group evidence raises `ConfidenceViolation`; a cross-group
RaiseClaim raises the value, bounded; degraded cap intact; the vector survives to the
DecisionObject.

# E3 · Operational silence (floor fix)

- Set `confidence_floor_bp` in the compiled-lane adapter (start 4500, the value the
  authored-but-unswept v2 manifest already chose) — **a floor that defaults to 0 is not
  a floor.**
- Fix the legacy DEFER mislabeled `shadow` in the suppression log.
- Keep every suppression reason-coded (already correct).

**ACCEPTANCE** — a below-floor compiled decision DEFERs with `below_confidence_floor`;
the suppression-reason distribution on the pilot shows the floor actually firing.

# E4 · Computed do-nothing (DLG-08)

### The verified defect

`do_nothing_consequence` copied verbatim from the manifest (default *"The condition may
remain unresolved."*) while `core.cost` genuinely computes `do_nothing_cost_bp` and
`core.alternative` composes a DoNothingBaseline — **read by nothing**, and unscheduled on
the compiled lane anyway.

### The fix

1. Doc 01 U1 schedules core.cost + core.alternative.
2. The Decision Builder composes: `do_nothing = {cost_bp: <computed>, horizon: <from
   timeline>, statement: <R-4 framed, numbers templated>}`, falling back to the manifest
   string **only** when the units were legitimately skipped — and saying so
   (`source: authored_fallback`).
3. `foresight.py`'s hardcoded `_SIGNAL_WEIGHTS` are registered as L7-tunable parameters
   with their hypothesis status recorded — never presented as measured until L7 has
   outcomes.

**ACCEPTANCE** — two different fixture deals show **different** do-nothing consequences
with different numbers; a skipped-cost run says `authored_fallback`; no model-generated
number anywhere in the field.

---

## Group acceptance gate — **K1, the gate that matters**

```
pytest tests/reason/test_ranking_v2.py tests/reason/test_confidence_rule11.py -q
python scripts/decision_ranking_distribution.py --org <pilot> --since 14d
```

| Metric | Gate |
|---|---|
| distinct `final_utility_bp` values | **> 50** |
| decisions where formula ≠ override outcome (divergence recorded) | reported, reviewed |
| `ORDER BY` surfaces showing importance-driven reordering | demonstrated on fixtures |
| ConfidenceViolation on unwarranted raises | enforced |
| below-floor DEFERs on the compiled lane | **> 0** — silence finally operational |
| identical input replayed | byte-identical |

**G7 proved L1 supplies. H5 proved L2 composes. K1 proves L4 finally decides.** All
three must hold on the same pilot tenant, the same fortnight, before the ranking fix is
called done anywhere.

# Group L4.4 — The Decision Maker (7 components) — **the ears**

> **What this group owns:** turning many observations into one committed action with one
> honest confidence. This is where L1's importance, L2's situations and L3's knowledge
> are supposed to arrive — and where, today, none of them do.

---

## The seven components

| # | Component | State | Work |
|---|---|---|---|
| 1 | Evidence Aggregator | ✅ correct | unchanged (+ `unit_ref` grouping for Rule 11) |
| 2 | Decision Synthesizer | ✅ correct | + ExternalCandidate for critique (doc 06 S4) |
| 3 | Decision Evaluator | ✅ **chain fully built** | + `compiled_constraints` mapping (doc 06 S3) |
| 4 | **Decision Ranker** | 🔴 **deaf** | **E1** — importance term, override demoted |
| 5 | **Confidence Calculator** | 🔴 **last-writer scan** | **E2** — Rule 11 composition |
| 6 | Decision Builder | ⚠️ static do-nothing | **E3/E4** — floor, computed consequence, bundle attach |
| 7 | Reasoning Trace | ✅ correct | extended by the bundle (doc 05) |

---

# E1 · The Ranker — make the formula decide (DLG-03)

## The two verified defects

**(a) `importance_bp` has zero readers in `reason/`.** L1 computes it (W7), L2 composes
it (X5) — and L4 never opens the envelope. The three-layer supply chain dead-ends at the
door of the layer it was built for.

**(b) The override replaces the formula.** `decision_maker.py:231-268`: when
`priority_override_bp` is present, the weighted utility is discarded. On the compiled
lane the override is *always* present (the corpus's authored priority is handed to the
unit as config — the stopgap for "every card scored exactly 50"). **The formula has
never once decided anything.**

## The fix

**Six components, integer basis points, weights summing to 10000:**

| Component | Weight | Source |
|---|---|---|
| **importance** | **2500** | L2 BSO `importance_bp` ← L1 `ALG-17` |
| impact | 2000 | `core.impact` → `impact_bp` |
| urgency | 2000 | `core.priority` → `urgency_bp` (real, after U5) |
| success likelihood | 1500 | `core.recommendation` → `support_strength_bp` |
| effort (inverse) | 1000 | `core.cost` → `effort_bp` |
| risk (inverse) | 1000 | `core.risk` → `risk_bp` |

**The override becomes a prior, not a verdict:**
```
formula_utility = weighted_sum(components)              # integer bp throughout
final_utility   = (formula_utility * 7 + override * 3) // 10     # when an override exists
                = formula_utility                                 # when it does not
record both, always                                     # the divergence is the measurement
```

**WHY 70/30 and not 100/0** — the authored corpus priority is real signal: a human ranked
those 48 situations. Deleting it would trade one blind ranking for another. 70/30 lets the
formula lead while the divergence is measured on live data; the weight is revisited at
retirement (doc 08) **with evidence**, not by taste.

**The honesty guard** — if L2 has not activated importance for this org, the component is
**absent, not defaulted**:
```
if importance_bp is None:            # L2-X5 not active for this tenant
    reweigh the remaining five to 10000
    record reason code L2_IMPORTANCE_NOT_ACTIVE on the decision
```
Never substitute 5000. A neutral default is exactly the bug that made every card score
50; v2 does not reintroduce it under a new name.

**FAILURE MODES** — a component's source unit skipped (reweigh + record, same mechanism) ·
weights drifting out of 10000 (constructor check) · float creep (`x*9//10`, never
`x*0.9`) · an override arriving for a decision with no formula (impossible: the formula
always runs).

**ACCEPTANCE / gate K1** — see the group gate below.

**REVERSE PROMPT**
```
TASK: L4.4 Ranker - importance term and override demotion.
READ FIRST: reason/decision_maker.py:231-268 (_weighted_utility and the override branch),
  contracts (ranking_weights), context/situation_bso.py (importance_bp on the BSO).
DO:
1. Extend ranking_weights to six keys with a version string; defaults per the table above,
   validated to sum to 10000 at construction.
2. Read importance_bp from the BSO. If absent, reweigh the remaining five and record
   L2_IMPORTANCE_NOT_ACTIVE. NEVER default it to 5000 or any other number.
3. Demote priority_override_bp: final = (formula*7 + override*3)//10. Record
   formula_utility, override value and their divergence on every decision.
4. Integer basis points only - no floats anywhere in this path.
GATE: on a pilot org, >= 50 distinct final_utility values across a day, and two situations
of the SAME type with DIFFERENT importance must rank differently. Byte-identical replay.
DO NOT: delete the override path; change any unit's math; introduce a neutral default.
```

---

# E2 · Confidence Calculator — Rule 11 composition (DLG-05)

**VERIFIED DEFECT** — `decision_maker.py:117-138` scans results and keeps the **last**
`confidence_bp` it sees. A unit late in the DAG can raise confidence with **no named
evidence at all**. This is the precise failure Rule 11 exists to forbid: *confidence that
rises for reasons nobody can point at.*

**THE GOOD NEWS — the raw material is already published.** `core.confidence` emits
`independent_evidence_groups`, `evidence_coverage_bp`, `corroboration_bp` and
`source_quality_bp`. Nothing new needs computing; the composition rule is what is missing.

**THE RULE**
```
start:   the BSO's confidence vector, per dimension          (L2 owns the starting point)
lower:   any unit may lower any dimension, freely, with a reason code
raise:   ONLY via an explicit RaiseClaim carrying evidence ids whose independence_group
         differs from every group already counted for that dimension
cap:     a degraded run (any REQUIRED unit failed / optional units skipped) keeps its
         existing ceiling — unchanged from today
reject:  a raise without a qualifying RaiseClaim -> ConfidenceViolation, fail closed
```

**WHY IT MATTERS BEYOND CORRECTNESS** — confidence gates *silence* (E3), and silence is
the product promise. A fabricated raise does not just mis-score a card; it pushes a card
past the floor that should have suppressed it.

**FAILURE MODES** — two evidence ids that *look* independent but are the same fact (this
is why S2's one-seed builder is a precondition) · a unit lowering confidence to zero to
force silence (allowed, and receipted — lowering is always legitimate) · missing groups on
historic evidence (treated as one shared group: conservative, never permissive).

**ACCEPTANCE** — an injected uncited raise throws `ConfidenceViolation`; a raise citing a
cross-group RaiseClaim succeeds; the degraded cap still binds.

---

# E3 · Decision Builder — silence becomes operational

**VERIFIED** — `CONFIDENCE_FLOOR_KEY` defaults to **0** on the compiled lane, so the
below-floor DEFER path — which is well built and honest (*"never invents the missing
fact"*) — **has never fired there.**

**FIX** — floors declared per lane (doc 01 C6), seeded at 4500 bp on the compiled lane; a
manifest with no declared floor fails registration. Below the floor the decision becomes
a reason-coded DEFER carrying **what would resolve it** (the missing field, the absent
unit) — so silence is actionable rather than merely quiet.

**ACCEPTANCE** — below-floor DEFERs > 0 on the pilot; each names its missing input.

---

# E4 · Decision Builder — the computed cost of doing nothing (DLG-08)

**VERIFIED** — `decision_maker.py:426` copies `do_nothing_consequence` **verbatim from the
manifest**: *"The {situation_type} situation is left unaddressed while its evidence
compounds."* Every card says the same sentence. Meanwhile `core.cost` computes a real
`do_nothing_cost_bp` and `core.alternative` computes `do_nothing_baseline_bp` — and
neither unit is scheduled.

**FIX**
```
do_nothing = {
    cost_bp:   core.cost -> do_nothing_cost_bp            (falls back to
               core.alternative -> do_nothing_baseline_bp)
    horizon:   core.timeline -> nearest material date
    statement: templated from the two above; the LLM may FRAME it (R-4), never compute it
    source:    'computed' | 'manifest_fallback'           ALWAYS recorded
}
```
When neither unit ran, the manifest string is used **and labelled `manifest_fallback`** —
the card never implies a computation that did not happen.

**ACCEPTANCE** — on a pilot with the roster awake, ≥80% of published decisions carry
`source: computed`; the remainder are labelled, never disguised.

---

## Group acceptance gate — **K1: the formula finally decides** 🔴

```
pytest tests/reason/test_ranking.py tests/reason/test_confidence_rule11.py -q
python scripts/ranking_distribution.py --org <pilot> --days 7
```

| Metric | Today | Gate |
|---|---|---|
| distinct `final_utility_bp` values per day | ~1 (**everything 50**) | **≥ 50** |
| same situation type, different importance → different rank | never | **demonstrated** |
| decisions recording `formula_utility` **and** override divergence | 0% | 100% |
| uncited confidence raise | silently accepted | **`ConfidenceViolation`** |
| below-floor DEFERs on the compiled lane | 0 | **> 0** |
| `do_nothing` marked `computed` | 0% | **≥ 80%** |
| replay determinism | — | byte-identical |

> **G7 → H5 → K1 must all hold on the same pilot in the same fortnight.** G7 proves L1
> supplies importance, H5 proves L2 composes it, K1 proves L4 finally decides with it.
> Any one of the three passing alone changes nothing a customer can see.

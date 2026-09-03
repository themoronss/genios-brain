# L2.7 — Business Situation Engine

**Group responsibility:** turn a graph pattern into a named business reality.

**Group law:** *L2 may say "there is an AWS renewal situation." It may not say "don't
renew AWS."*

**Package:** `genios_engine/context/situations.py`, `situation_bso.py`
**Output:** `BusinessSituationObject` — Layer 2's only output
**LLM sites:** LLM-6 only — situation naming, cosmetic, may not alter a number.

---

## Component map

| # | Component | BLG | Wave | Status |
|---|---|---|---|---|
| L2.7.1 | Situation Detection | — | — | ✅ exists |
| L2.7.2 | Situation Builder | — | — | ✅ exists |
| L2.7.3 | Situation Clustering | BLG-17 | — | ✅ exists |
| L2.7.4 | **Situation Prioritization** | **BLG-18** | **X5** | 🔴 **BROKEN — hardcoded 5000** |
| L2.7.5 | Situation Confidence | — | — | ✅ **strong** |
| L2.7.6 | Situation State | — | — | ✅ exists |
| L2.7.7 | Situation Lifecycle | BLG-19 | — | ✅ exists |
| L2.7.8 | Situation Publisher | — | X5 | ⚠️ update for QES input |

**Seven of eight are built and correct.** One is a constant, and that constant flattens
ranking across the entire product.

---

# 🔴 L2.7.4 · Situation Prioritization (BLG-18) — the fix

### The defect

`context/situation_bso.py`:

```python
DEFAULT_IMPORTANCE_BP = 5000          # line 39
...
importance_bp=DEFAULT_IMPORTANCE_BP,  # line 235
```

**Every `BusinessSituationObject` ever produced carries importance 5000.**

The `BusinessSituationObject` contract *requires* `importance_bp`
(`contracts/domain_expertise.py:65`, validated by `require_bp`). L2 has nothing to
compute it from — so it satisfies the contract with a constant.

### The full chain, end to end

```
L1 refuses to stamp importance_bp          contracts/gated_event.py:28  (deliberate)
   |
   v
L2's BSO contract REQUIRES importance_bp   contracts/domain_expertise.py:65
   |
   v
L2 hardcodes 5000                          situation_bso.py:39          <-- HERE
   |
   v
every situation is equally important
   |
   v
"193 of 223 signals scored an identical 50"  reason/reasoners/priority.py:165-197
   |
   v
priority_override supplied for every candidate
   |
   v
"the formula has never once decided anything"  reason/decision_maker.py:243
   |
   v
two different tenants receive IDENTICAL rankings
```

**This is one constant, and it is the reason ranking does not work anywhere in GeniOS.**

L1 v2's ALG-17 is the **supply** side of the fix. BLG-18 is the **demand** side. Neither
works alone: L1 can compute importance perfectly and L2 will still stamp 5000 over it
unless this unit changes.

### L2.7.4-U1 · Situation importance composition (BLG-18)

**WHAT** — Composes a situation's importance from its constituent signals **plus** what
only L2 knows.

**WHY** — A situation is not one signal. It is several signals about one thing, plus
graph context none of them had individually.

**WHERE** — `genios_engine/context/situations.py`
**WHEN** — X5. Requires L1 v2 W7 shipped (signals arriving with real `importance_bp`), and
L2.4 (the analytic stratum) for the modifiers.

**HOW** (BLG-18) — integer basis points throughout:

```
1. BASE — the strongest constituent signal, not the average.
   base_bp = max(signal.importance_bp for signal in situation.signals)

   Why max and not mean: a situation containing one critical signal and four routine
   ones is a critical situation. Averaging would bury it — which is precisely the
   "small critical things get buried" failure Globe names at L4.

2. CORROBORATION — independent signals about the same subject raise it, bounded.
   distinct_sources = count of distinct source systems across constituent signals
   corroboration_bp = min(1500, (distinct_sources - 1) * 500)

   Rule 11 compliant: the raise is bounded and its evidence is nameable — the
   additional sources ARE the named independent evidence.

3. L2-ONLY MODIFIERS — the part no signal could know alone:

   a. TREND            declining trend on a related metric       +1000
                       (from L2.4.3; requires trend_confidence_bp >= 5000)
   b. COHORT POSITION  bottom decile of its cohort               +1000
                       top decile on a risk metric               +1000
                       (from L2.4.5; requires population >= 5)
   c. ANOMALY          flagged vs its own baseline               +800
                       (from L2.4.8)
   d. DEPENDENCY       N items blocked on this situation         +200 * min(N, 5)
                       (from L2.3.8 — the cost is the blocked work)
   e. CONFLICT         an unresolved material conflict           +700
                       (from L1 v2 L1.5.5 — we may be about to say something false)
   f. STALENESS        newest evidence older than 90 days        -1500

4. COVERAGE PENALTY — an honest discount for what we cannot see.
   if coverage_ready is False for the situation's domain:
       importance_bp = importance_bp * 8 // 10
   We are less sure this matters, because we cannot see all of it.

5. CLAMP  0 .. 10000

6. COMPONENTS — store every term, as at L1. "Why is this a 7400?" must be answerable
   from stored data without recomputation.
```

**Design points:**

- **`max`, not `mean`, in step 1.** This is the single most important choice in the
  formula. Averaging is how a critical signal gets buried under routine ones.
- **Step 3 is the justification for the whole analytic stratum.** Trend, cohort position
  and anomaly are things *no individual signal could know*. This is where L2 earns its
  place in the stack rather than passing L1's numbers through.
- **Step 4 is honesty, not caution.** Discounting for missing coverage means the system
  says "I am less sure this matters" rather than pretending its view is complete.

**LLM** — no. **EMBEDDINGS** — no.

**STORAGE** — `situations.importance_bp` + `situations.importance_components` (JSONB) +
`importance_version`.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| L1 not yet shipping real importance | back to a flat distribution | **gate**: if >90% of incoming signals carry importance 5000, log `L1_IMPORTANCE_NOT_ACTIVE` loudly rather than producing a fake spread |
| Modifiers dominate the base | a routine signal with a trend outranks a critical one | modifiers are capped at +4000 total; the base can reach 10000 alone |
| Trend confidence too low to trust | noise amplified into importance | modifier 3a requires `trend_confidence_bp >= 5000` |
| Cohort too small | meaningless percentile drives importance | modifier 3b requires `population >= 5` |
| Version drift after a weight change | historical importance incomparable | `importance_version` stored on every situation |

**ACCEPTANCE**
```
pytest tests/context/test_situation_importance.py -q
python scripts/situation_importance_distribution.py --org <pilot> --since 30d
```

Required unit rows:
- a situation of one signal at 8100 -> base 8100, not 5000
- one critical (9000) + four routine (3000) -> **>= 9000**, proving `max` not `mean`
- three distinct sources -> +1000 corroboration, capped at 1500
- a declining trend with `trend_confidence_bp = 4000` -> **no** trend modifier
- `coverage_ready=False` -> importance is 80% of the same situation with coverage
- every situation carries populated `importance_components`
- determinism: same inputs twice -> identical

Required distribution rows (the real gate):

| Metric | Gate |
|---|---|
| distinct `importance_bp` values across 30 days | **> 50** |
| p90 − p50 spread | **> 1500** |
| situations still at exactly 5000 | **< 5%** |
| situations whose importance changed after L2.4 landed | **> 0** — proves the modifiers fire |

**REVERSE PROMPT**
```
TASK: Fix situation prioritization. This is the demand side of the ranking unlock.

THE DEFECT: genios_engine/context/situation_bso.py line 39 defines
DEFAULT_IMPORTANCE_BP = 5000 and line 235 stamps it on EVERY BusinessSituationObject.
The BSO contract requires importance_bp (contracts/domain_expertise.py:65) and L2 has
nothing to compute it from, so it satisfies the contract with a constant.

Downstream: reason/reasoners/priority.py:165-197 records "193 of 223 signals scored an
identical 50", which forces priority_override on every candidate, which is why
reason/decision_maker.py:243 records "the formula has never once decided anything".
One constant flattens ranking across the whole product.

PREREQUISITES (both, this will not work without them):
  - L1 v2 W7 shipped: incoming signals carry a real importance_bp
  - L2.4 analytic stratum: trend, cohort position, anomaly available

FILE: genios_engine/context/situations.py

Implement:
  def compose_situation_importance(signals, graph_context, *, eval_time)
        -> tuple[int, dict[str, int]]     # (importance_bp, components)

FORMULA: the 6 ordered steps in doc 07 section L2.7.4-U1.

HARD RULES:
1. Step 1 is max(), NOT mean(). A situation with one critical signal and four routine
   ones is critical. Averaging buries it. Test this pair explicitly.
2. INTEGER MATH ONLY. No float. Source-grep test.
3. eval_time is an explicit parameter. No datetime.now().
4. ALWAYS return the components dict. Store it as JSONB alongside the score.
5. Modifiers are capped at +4000 combined. The base alone can reach 10000.
6. Trend modifier requires trend_confidence_bp >= 5000. Cohort modifier requires
   population >= 5. A weak input must not become a strong modifier.
7. GUARD: if more than 90% of incoming signals carry exactly 5000, do NOT produce a
   synthetic spread. Log L1_IMPORTANCE_NOT_ACTIVE loudly and keep the base. A fake
   distribution is worse than a flat one because it looks like it works.
8. Store importance_version. Weights are a versioned constant.

THEN: replace the DEFAULT_IMPORTANCE_BP usage at situation_bso.py:235 with the composed
value. Keep the constant defined and used ONLY as the documented fallback when a
situation somehow has no signals — and make that path log.

MIGRATION: add importance_components jsonb and importance_version text to situations.

TEST tests/context/test_situation_importance.py — every unit row in the doc 07
ACCEPTANCE list.
ALSO write scripts/situation_importance_distribution.py reporting distinct values, p50,
p90 and the share still at exactly 5000.
```

---

# ✅ L2.7.5 · Situation Confidence — preserve, do not touch

This component is **better than the Globe spec** and must survive the refactor.

`context/situations.py:102-227` computes a genuine confidence **vector**:

| score | function | what it measures |
|---|---|---|
| `evidence_score` | `:102` | event count and source count |
| `freshness_score` | `:120` | age of the newest supporting evidence |
| `consistency_score` | `:143` | open discrepancies against this subject |
| `identity_score` | `:153` | open merge proposals — is the entity resolved? |
| `coverage_score` | `:189` | present fields vs expected |
| `score_situation` | `:227` | composition |

Globe's own open-blocker list names *"confidence modelled as a scalar rather than a
vector — cannot distinguish strong-evidence-no-expertise from weak-evidence"* as a
correctness defect. **L2 already fixed it.** Do not collapse it back to a scalar for
convenience anywhere downstream.

**One change only:** add an `analytic_score` axis reflecting the quality of the
comparative inputs (population size, trend confidence, history depth), so a situation
whose importance leaned on a thin cohort is visibly less certain than one that did not.

---

# ⚠️ L2.7.8 · Situation Publisher — update for QES input

**WHAT** — Emits the `BusinessSituationObject`.

**CHANGE** — the input becomes `QualifiedEnterpriseSignal` rather than `GatedEvent`.
Concretely:

| BSO field | v1 source | v2 source |
|---|---|---|
| `signal_ids` | event ids | **QES signal ids** |
| `type` | `situation_type(anchor_type, domain)` | **QES `signal_type` + pattern match** (L2.6) |
| `importance_bp` | **hardcoded 5000** | **BLG-18** |
| `confidence_bp` | `score_situation` | unchanged, + `analytic_score` |
| `evidence` | event refs | **QES verified evidence spans** |
| `metadata` | — | + `conflicts`, `trends`, `cohort_positions` |

**The evidence upgrade is significant.** Today a situation's evidence is a list of event
references. In v2 it is a list of **span-validated verbatim quotes** — so a card can show
the sentence, not just name the email.

**ACCEPTANCE**
```
pytest tests/context/test_situation_publisher.py -q
# every published BSO carries >= 1 verified evidence span
# importance_bp is not 5000 unless the fallback path fired AND logged
# conflicts from L1 v2 arrive in metadata
```

---

## Group acceptance gate

```
pytest tests/context -q
python scripts/situation_importance_distribution.py --org <pilot> --since 30d
```

| Metric | Gate |
|---|---|
| distinct `importance_bp` values | > 50 |
| p90 − p50 | > 1500 |
| situations at exactly 5000 | < 5% |
| BSOs with a verified evidence span | 100% |
| confidence vector axes present | all 6 |

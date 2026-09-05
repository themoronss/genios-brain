# L2 Contracts

> Unlike Layer 1, **Layer 2's boundary contract already exists and is good.**
> `BusinessSituationObject` at `contracts/domain_expertise.py:55` is immutable, validated,
> and requires evidence. This document specifies the **additions**, not a rewrite.

---

## Contract inventory

| # | Type | File | Status |
|---|---|---|---|
| D-01 | `BusinessSituationObject` | `contracts/domain_expertise.py` | ✅ exists — **extend** |
| D-02 | `MetricPoint` | `contracts/analytic.py` | 🆕 NEW |
| D-03 | `Trend` | `contracts/analytic.py` | 🆕 NEW |
| D-04 | `CohortPosition` | `contracts/analytic.py` | 🆕 NEW |
| D-05 | `MetricCorrelation` | `contracts/analytic.py` | 🆕 NEW |
| D-06 | `Anomaly` | `contracts/analytic.py` | 🆕 NEW |
| D-07 | `AbsenceType` / `MissingFact` | `contracts/quality.py` | 🆕 NEW |
| D-08 | `AuthorityRule` | `contracts/authority.py` | 🆕 NEW |
| D-09 | `DependencyChain` | `contracts/dependency.py` | 🆕 NEW |

---

## D-01 · BusinessSituationObject — what already works

```python
@dataclass(frozen=True, slots=True)
class BusinessSituationObject:
    org_id · trace_id · visibility · id
    signal_ids: tuple[str, ...]        # >= 1 required
    type: str
    confidence_bp: int                 # require_bp validated
    importance_bp: int                 # require_bp validated
    evidence: tuple[...]               # >= 1 required
    entities · relationships · timeline · dependencies
    state · metadata · schema_version
```

**What is right about it:** frozen, slots, validated in `__post_init__`, basis points
enforced, **evidence mandatory**, schema version rejected if unknown, signal_ids sorted
and unique. This is a better-built contract than anything at the L1 seam today.

**The problem is not the contract. It is that `importance_bp` is satisfied with a
constant** (`situation_bso.py:39`). The contract asked the right question; L2 had no
answer, so it supplied 5000.

### Additions (schema version bump, additive only)

```python
    # --- analytic context (the L2.4 payoff) ---
    trends: tuple[Trend, ...] = ()
    cohort_positions: tuple[CohortPosition, ...] = ()
    anomalies: tuple[Anomaly, ...] = ()

    # --- quality ---
    missing_facts: tuple[MissingFact, ...] = ()
    conflicts: tuple[Mapping[str, Any], ...] = ()     # from L1 v2 + L2.5.3
    confidence_vector: Mapping[str, int] = ...        # 6 axes, not a scalar
    coverage_ready: bool | None = None

    # --- explainability ---
    importance_components: Mapping[str, int] = ...    # every ALG/BLG term
    importance_version: str = ...
    pattern_id: str | None = None                     # which pattern fired
    matched_conditions: tuple[Mapping[str, Any], ...] = ()   # per-condition evidence
```

**`matched_conditions` is the one to insist on.** *"This fired because of these five
facts"* is what makes a situation explainable at L3 and defensible on a card. Without it,
a pattern match is an assertion.

---

## D-02..D-06 · Analytic types

```python
class MetricPoint(BaseModel):
    metric: str
    value_bp: int | None          # None when known is False
    unit: str                     # count | days | bp | minor_units
    currency: str | None
    observed_at: datetime         # the PERIOD, not the compute time
    known: bool                   # False = coverage gap. NEVER interpolated
    coverage_ready: bool | None

class Trend(BaseModel):
    metric: str
    direction: str                # RISING | DECLINING | FLAT
                                  # | INSUFFICIENT_HISTORY | INSUFFICIENT_COVERAGE
    relative_slope_bp: int
    streak_periods: int
    point_count: int
    coverage_ratio_bp: int
    trend_confidence_bp: int      # <= 8000, always
    evidence_points: tuple[MetricPoint, ...]

class CohortPosition(BaseModel):
    metric: str
    cohort_id: str                # MANDATORY — Law 2
    population_size: int          # MANDATORY — Law 2
    percentile_bp: int
    band: str                     # decile/quartile label
    p25_bp: int; p50_bp: int; p75_bp: int    # the distribution, for the card
    computed_at: datetime

class MetricCorrelation(BaseModel):
    metric_a: str; metric_b: str
    cohort_id: str
    rho_bp: int
    strength: str                 # NONE | WEAK | MODERATE | STRONG
    n: int                        # >= 20 required
    is_causal: bool = False       # ALWAYS False. The field exists to make the
                                  # absence of a causal claim explicit in the data.

class Anomaly(BaseModel):
    metric: str
    current_bp: int; baseline_bp: int; mad_bp: int
    deviation_bp: int; z_like_bp: int
    direction: str                # ABOVE | BELOW
    periods_used: int             # >= 6 required
```

### Validators that carry the Layer 2 laws

| # | Rule | Enforces |
|---|---|---|
| V-1 | `CohortPosition` without `cohort_id` or `population_size` → reject | **Law 2** |
| V-2 | `CohortPosition` with `population_size < 5` → reject | **Law 2** |
| V-3 | `MetricPoint` with `known=False` and a non-None `value_bp` → reject | **never interpolate** |
| V-4 | `Trend.trend_confidence_bp > 8000` → reject | a trend is never certain |
| V-5 | `Trend` with `point_count < 4` and direction in {RISING, DECLINING} → reject | no trend on noise |
| V-6 | `MetricCorrelation` with `n < 20` → reject | no correlation on 5 points |
| V-7 | `MetricCorrelation.is_causal is True` → reject | correlation is never cause |
| V-8 | any `float` in any field → reject | integer basis points |

**V-7 is not defensive coding.** It makes it structurally impossible for any downstream
layer to receive a causal claim from L2, no matter what it asks for.

---

## D-07 · Typed absence

```python
class AbsenceType(str, Enum):
    PRESENT = "present"
    UNKNOWABLE = "unknowable"              # no source could carry it
    GENUINELY_ABSENT = "genuinely_absent"  # a source could have; none did -> A FINDING
    STALE = "stale"
    NOT_EXPECTED = "not_expected"

class MissingFact(BaseModel):
    subject_node_id: str
    expected_fact: str
    absence_type: AbsenceType
    coverage_ready: bool | None
    licenses_negative_inference: bool      # True ONLY for GENUINELY_ABSENT
```

**`licenses_negative_inference` is computed, never set by a caller.** It is `True` only
for `GENUINELY_ABSENT`. Any layer that wants to say *"nobody owns this"* must check it,
and no layer can talk itself past it.

---

## REVERSE PROMPT — L2 contracts

```
TASK: Build the Layer 2 v2 contract types.
PACKAGE: genios_engine/contracts/

CREATE:
  contracts/analytic.py   -> MetricPoint, Trend, CohortPosition, MetricCorrelation, Anomaly
  contracts/quality.py    -> AbsenceType, MissingFact
  contracts/authority.py  -> AuthorityRule
  contracts/dependency.py -> DependencyChain

EXTEND (additive only, bump BUSINESS_SITUATION_VERSION):
  contracts/domain_expertise.py -> BusinessSituationObject
  Add: trends, cohort_positions, anomalies, missing_facts, conflicts,
       confidence_vector, coverage_ready, importance_components, importance_version,
       pattern_id, matched_conditions
  Do NOT change or remove any existing field. Existing validation stays.

VALIDATORS — implement all 8 in doc 08's table. These carry the Layer 2 laws:
  - a CohortPosition without cohort_id or population_size is REJECTED (Law 2:
    a percentile without its population is a number nobody can check)
  - population_size < 5 is REJECTED
  - a MetricPoint with known=False and a value is REJECTED (never interpolate)
  - MetricCorrelation.is_causal=True is REJECTED, always. The field exists so the
    absence of a causal claim is explicit in the data and no downstream layer can
    receive one.
  - n < 20 on a correlation is REJECTED
  - no float anywhere

MissingFact.licenses_negative_inference is COMPUTED in __post_init__, True only for
GENUINELY_ABSENT. A caller must not be able to set it.

Reuse require_bp from contracts/validators.py. Do not write a second one.

TEST tests/contracts/test_l2_contracts.py — one case per validator, plus a
BusinessSituationObject round-trip proving the additions are additive (an old-shaped
object still constructs).

ACCEPTANCE:
  pytest tests/contracts/test_l2_contracts.py -q   -> pass, 0 skips
  pytest tests/test_layer_topology.py -q           -> still green
```

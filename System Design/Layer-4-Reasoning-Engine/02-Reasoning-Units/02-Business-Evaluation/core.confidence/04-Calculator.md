# 04 · Calculator

**Stage 5:** `confidence.py:ConfidenceReasoner.calculate` (line 253) — `@abstractmethod` in the
framework, so every unit must implement it.

---

## 1 · What it is for

The Calculator turns a bag of partial observations into the unit's metrics, using **pure integer
arithmetic only**. No clock, no config lookup beyond what the plugins already resolved, no branching
on anything the observations did not carry.

For this unit it does two things and nothing else: pass a bridged number through, or blend four axes
into one.

```python
# confidence.py:253
def calculate(self, view, observations) -> Mapping[str, int]:
    """One weighted blend, or the bridged number passed straight through."""
    by_plugin = {item.plugin_id: item for item in observations}
    bridged = by_plugin.get(LegacyBridgePlugin.plugin_id)
    if bridged is not None:
        return {"confidence_bp": bridged.metrics["confidence_bp"]}

    quality = by_plugin.get(FactSourceQualityPlugin.plugin_id)
    coverage = by_plugin.get(CoverageCompletenessPlugin.plugin_id)
    source_bp = quality.metrics["source_quality_bp"] if quality else _NEUTRAL_BP
    corroboration_bp = quality.metrics["corroboration_bp"] if quality else _NEUTRAL_BP
    completeness_bp = coverage.metrics["completeness_bp"] if coverage else 10_000
    evidence_coverage_bp = coverage.metrics["evidence_coverage_bp"] if coverage else 0
    groups = coverage.metrics["independent_evidence_groups"] if coverage else 0
    return {
        "confidence_bp": clamp_bp(divide_half_up(
            source_bp * _SOURCE_WEIGHT + completeness_bp * _COMPLETENESS_WEIGHT
            + corroboration_bp * _CORROBORATION_WEIGHT
            + evidence_coverage_bp * _COVERAGE_WEIGHT, _WEIGHT_TOTAL)),
        "source_quality_bp": source_bp,
        "completeness_bp": completeness_bp,
        "corroboration_bp": corroboration_bp,
        "evidence_coverage_bp": evidence_coverage_bp,
        "independent_evidence_groups": groups,
    }
```

Observations are keyed by `plugin_id` on entry, so the Analyzer's sort order has **no effect on this
stage**. See [03 · Analyzer](03-Analyzer.md) §3.

---

## 2 · The bridged branch

```
confidence_bp = the bridged value, verbatim
```

One metric out. Not five, not six. The decomposition axes are not merely zero — they are **absent**,
because they were never evaluated. That distinction reaches the persisted result: a bridged decision
carries `{confidence_bp, source}` and a computed one carries six metrics, so an auditor can tell the
two apart by shape alone even before reading `source`.

Blending the bridged number with anything would defeat the point:

> *The bridge carries the value through unchanged; re-deriving it here would mean two different
> confidences for one decision.* — `LegacyBridgePlugin` docstring

---

## 3 · The blend — the arithmetic in full

```
confidence_bp = clamp_bp( half_up( source_quality_bp    × 40
                                 + completeness_bp      × 30
                                 + corroboration_bp     × 20
                                 + evidence_coverage_bp × 10 , 100 ) )
```

with

```
half_up(n, d) = (n + d // 2) // d          for n ≥ 0        # common.py:79
clamp_bp(v)   = min(10_000, max(0, int(v)))                 # common.py:75
```

Every term is an integer in `0..10_000`, every weight is an integer, the divisor is the constant
`100`, and the rounding is half-away-from-zero. Nothing in the path can produce a float, so the same
inputs give the same basis points on every machine — which is the precondition for replaying a
decision months later and getting the same hash.

### 3.1 · Why 40 / 30 / 20 / 10

The weights are module constants with the rationale stated as a sentence at `confidence.py:45`:

> *What the facts claim about themselves dominates, how much of the picture arrived is next, and
> independent corroboration is the tie-breaker. Expressed as data so the weights and the metric
> names cannot drift apart.*

Unpacked into the ordering argument:

| Axis | Weight | Why it ranks where it does |
|---|---|---|
| Source quality | 40 | The most **specific** evidence available. A CRM field that says it is 90% sure is a direct statement about the thing being reasoned over; nothing else in the blend is that close to the claim. |
| Completeness | 30 | The only axis that fires when no fact carries metadata at all, and the only one a producer cannot inflate — it is measured from the *declaration*, not from the data. It is what keeps a thin snapshot from scoring as a confident one. |
| Corroboration | 20 | Independent agreement is strong evidence but **coarse**: three systems agreeing that a deal is open says less about a decision than one system's stated confidence in the deal's value. |
| Evidence coverage | 10 | The most **diffuse** claim — a property of the whole snapshot rather than of any field being read. A sanity check on single-source pictures, not a measurement of the situation. |

The ordering runs from *specific* to *diffuse*, and from *what the data says* to *what the shape of
the data implies*. That is a coherent argument. It is also entirely unmeasured — see §6.

### 3.2 · Why no renormalisation

The docstring:

> *The blend is a percentage-weighted mean over all four axes with no renormalisation: each axis
> always reports (using its neutral midpoint where it had nothing to measure), so the divisor is the
> constant 100 and the arithmetic stays integral end to end.*

The contrast worth drawing is with `core.impact`, whose docstring takes the opposite position:

> *The blend renormalises over what was actually seen. Impact is a weighted mean of the present
> dimensions only. Averaging a known 9,000bp revenue exposure against two unknowns would report a
> 3,000bp stake for a deal we know to be enormous.* — `impact_unit.py:29`

Both are right, and the asymmetry is principled rather than accidental:

| | `core.impact` | `core.confidence` |
|---|---|---|
| Its dimensions measure | the **world** — revenue, account importance, strategic linkage | the **inputs** — what arrived and what it claimed |
| Can a dimension be genuinely absent? | yes — a deal may have no recorded value | no — an input that did not arrive is a *measurement of zero completeness*, not a missing dimension |
| Absent dimension is | omitted, and the divisor shrinks | reported at its neutral or zero value |
| Divisor | `sum(weights of present dimensions)` | the constant `100` |

Stated as one sentence: **you can be ignorant of the world, but you cannot be ignorant of your own
inputs** — you always know what you asked for and what you got, even when the answer is "nothing".
That is why the neutral midpoint exists here and does not exist there.

### 3.3 · Neutral where, and zero where

`_NEUTRAL_BP` is not applied uniformly. Which axes get 5,000 and which get 0 is the second-most
consequential decision in this file.

| Axis | Value when it has nothing to measure | Why |
|---|---|---|
| `source_quality_bp` | **5,000** | *"a fact that never stated its own confidence is unknown, not untrustworthy, and scoring it 0 would turn a silent CRM field into a reason to distrust the whole decision"* |
| `corroboration_bp` | **5,000** | same argument, applied to "how many saw it" |
| `completeness_bp` | **0** | genuine measurement: no declared field arrived |
| `evidence_coverage_bp` | **0** | genuine measurement: nothing cites anything |

The line is *unknown versus measured*. Source quality and corroboration are properties of a fact
record; when no record speaks, the truth is unknown. Completeness and coverage are properties of the
request and the snapshot; when nothing arrived, the truth is zero.

---

## 4 · A worked combination

### 4.1 · `sales.deal_cooling`, three of four fields present

Inputs from the two computed plugins ([03a](03a-plugin-coverage_completeness.md) §7.1,
[03b](03b-plugin-fact_source_quality.md) §6.2):

```
source_quality_bp    = 8,500      mean of [9,000, 8,000]
completeness_bp      = 7,500      3 of 4 declared fields
corroboration_bp     = 9,250      mean of [8,500, 10,000]
evidence_coverage_bp = 5,000      2 independent groups × 2,500
```

The blend, term by term:

```
source quality      8,500 × 40 = 340,000
completeness        7,500 × 30 = 225,000
corroboration       9,250 × 20 = 185,000
evidence coverage   5,000 × 10 =  50,000
                                ---------
                                 800,000

half_up(800,000, 100) = (800,000 + 50) // 100 = 800,050 // 100 = 8,000
clamp_bp(8,000)                                                = 8,000
```

Output of `calculate`:

```python
{"confidence_bp": 8000,
 "source_quality_bp": 8500,
 "completeness_bp": 7500,
 "corroboration_bp": 9250,
 "evidence_coverage_bp": 5000,
 "independent_evidence_groups": 2}
```

**Read it as a sentence.** *80% confident: the facts we got were strongly self-reported and
well-corroborated, but a quarter of what we asked for never arrived and only two systems stand
behind the picture.* That sentence is recoverable from the numbers, which is the entire argument for
publishing the decomposition alongside the score.

### 4.2 · Sensitivity — what each axis is worth

Because the blend is linear with a constant divisor, each axis's leverage is exactly its weight
divided by 100:

| A change of… | moves `confidence_bp` by |
|---|---|
| 1,000bp of source quality | 400bp |
| 1,000bp of completeness | 300bp |
| 1,000bp of corroboration | 200bp |
| 1,000bp of evidence coverage | 100bp |
| one independence group gained, below saturation | 250bp |
| one declared field of four arriving | 750bp |
| one fact moving from 1 source to 2, of two facts | 250bp |
| one fact moving from 2 sources to 3, of two facts | 150bp |

The last two rows show the corroboration ladder's diminishing returns reaching the final number:
first corroboration is worth `2,500bp × 20 / 100 / 2 = 250bp` of confidence; the next step is worth
`150bp`.

### 4.3 · Four more, computed from the code

| Scenario | `sq` | `comp` | `corr` | `cov` | `confidence_bp` |
|---|---|---|---|---|---|
| Empty snapshot, four fields declared | 5,000 | 0 | 5,000 | 0 | **3,000** |
| Capability fallback, 1 of 3 present, no evidence | 5,000 | 3,333 | 5,000 | 0 | **4,000** |
| Six scalar facts, six independence groups | 5,000 | 10,000 | 5,000 | 10,000 | **7,000** |
| `deal_cooling`, every field present, no evidence | 9,000 | 10,000 | 9,500 | 0 | **8,500** |

Arithmetic for the last row:

```
9,000 × 40 = 360,000
10,000 × 30 = 300,000
9,500 × 20 = 190,000
0 × 10     =       0
             ---------
             850,000  → half_up(850,000, 100) = 8,500
```

Note that a snapshot with *every* declared field present and strong self-reported confidence still
reports only 85%, because no evidence item carried an independence group. The coverage axis is the
cheapest 1,000bp in the system and the easiest to leave on the table — it costs Layer 2 one string
per fact.

---

## 5 · The unreachable code in this method

Three constructs in `calculate` cannot execute in the shipped unit. All three are honest defence
rather than mistakes, but a reader should know which lines are live.

### 5.1 · The `if quality else` / `if coverage else` fallbacks

```python
source_bp = quality.metrics["source_quality_bp"] if quality else _NEUTRAL_BP
```

`by_plugin.get(...)` returns `None` only if the plugin produced no observation. But the three plugins
partition the branch exhaustively: `_bridged_confidence_bp` returns either `None` or an `int`, so
either `legacy_bridge` fires alone (and the method already returned) or **both** decomposition
plugins fire. `quality` and `coverage` are therefore never `None` at that point.

The fallbacks would matter if a plugin were removed from the `plugins` tuple. Their chosen values are
worth noting because they are **not** the same as the plugins' own empty-input values:

| Missing plugin | `calculate`'s fallback | What the plugin itself would emit on empty input |
|---|---|---|
| `fact_source_quality` | `source 5,000`, `corroboration 5,000` | identical |
| `coverage_completeness` | `completeness 10,000`, `coverage 0`, `groups 0` | `completeness 0` when fields are declared |

So deleting `coverage_completeness` would not degrade confidence — it would **raise** it, by
substituting "asked for nothing" for "nothing arrived". A missing plugin reads as a perfect score on
its axis. That is the wrong default for a unit whose job is measuring absence, and it is invisible
because the code is unreachable.

### 5.2 · `clamp_bp` on the blend

Maximum possible numerator: `10,000 × (40 + 30 + 20 + 10) = 1,000,000`, so
`half_up(1,000,000, 100) = 10,000`. Minimum: `0`. The clamp is a no-op for every legal input.

It is not decoration, though. It is the **only** thing standing between a mistyped weight constant
and an out-of-range metric. If someone changed `_SOURCE_WEIGHT` to `50`, the weights would sum to
110, a maximal run would compute `11,000`, and `clamp_bp` would silently cap it at `10,000` —
turning a calibration bug into a saturated score instead of a crash.

**Nothing asserts that the four weights sum to `_WEIGHT_TOTAL`.** Verified: no test in `tests/`
references `_SOURCE_WEIGHT` or `_WEIGHT_TOTAL`. A one-line assertion at import time would convert a
silent mis-scaling into a startup failure, and it is not there.

### 5.3 · `divide_half_up`'s zero-denominator guard

`divide_half_up` raises `ValueError("denominator must be positive")` when `d <= 0`. Here `d` is the
literal constant `_WEIGHT_TOTAL = 100`, so the guard is unreachable from this call site. It is
reachable from `CoverageCompletenessPlugin`, which is why that plugin's `if declared` test exists —
see [03a](03a-plugin-coverage_completeness.md) §8.

---

## 6 · What is not known about these numbers

Stated plainly, because the rest of this document reads like the weights were derived:

- **40/30/20/10 is untuned.** No calibration data, no backtest, no outcome study. It is a considered
  ordering with a written argument, and nothing more.
- **6,000 / 8,500 / 10,000 is untuned.** The ladder's rungs and its floor at 6,000 are asserted, not
  measured. Note that the floor guarantees every computed run with one mapping-shaped fact carries
  `1,200bp` of confidence it did not earn.
- **2,500-per-group and the four-group saturation are untuned.** Why the fifth independent source is
  worth nothing is not argued anywhere.
- **`_NEUTRAL_BP = 5,000` is a convention**, shared with `core.priority`'s `NEUTRAL_URGENCY_BP` and
  with `decision_maker.py`'s `default_confidence_bp`. Its virtue is consistency across the layer, not
  evidence.
- **Nothing measures whether the output is calibrated.** There is no test, metric or report anywhere
  in the repository that asks whether decisions scoring 8,000bp are right more often than decisions
  scoring 5,000bp. `feedback/calibrate.py` measures precision windows against outcomes, not against
  this number.

The arithmetic is exactly reproducible and exactly as good as its constants. Treat the constants as a
starting position.

---

## 7 · Edge cases

| Situation | `calculate` returns | Note |
|---|---|---|
| Bridge fired | `{"confidence_bp": n}` — one key | no decomposition, by design |
| Both computed plugins fired | six keys | the normal path |
| All axes at 0 | `confidence_bp = 0` | reachable only with facts stating `confidence_bp: 0` and zero completeness, which are mutually exclusive; see [01](01-Input-and-Validator.md) §4.2 |
| All axes at 10,000 | `confidence_bp = 10,000` | `half_up(1,000,000, 100)` exactly |
| Rounding at `.5` | rounds **away from zero** | `half_up(690,050, 100) = 6,901`, not `6,900` |
| `independent_evidence_groups` | copied through unweighted | it is a count, not a score; it plays no part in the blend |

The last row is easy to miss. `independent_evidence_groups` is published but **not blended** — only
its capped derivative `evidence_coverage_bp` reaches the number. It exists so a reader can see that
six groups saturated a ceiling of four.

---

## Related

- [03 · Analyzer](03-Analyzer.md) — where the four axis values come from
- [03a](03a-plugin-coverage_completeness.md) · [03b](03b-plugin-fact_source_quality.md) · [03c](03c-plugin-legacy_bridge.md) — each axis in full
- [05 · Evaluator](05-Evaluator.md) — what happens to these six metrics next
- [06 · Builder and Metrics](06-Builder-and-Metrics.md) — how they reach the Decision Maker

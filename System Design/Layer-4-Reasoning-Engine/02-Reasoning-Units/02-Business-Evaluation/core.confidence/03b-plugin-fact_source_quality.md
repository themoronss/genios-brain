# 03b · Plugin `fact_source_quality`

**Class:** `genios_engine/reason/reasoners/confidence.py:138` — `FactSourceQualityPlugin`
**`plugin_id`:** `fact_source_quality` · runs **second** (alphabetical)
**`Observation.kind`:** `confidence.fact_source_quality`
**Emits:** `source_quality_bp`, `corroboration_bp`, `self_reported_fact_count`,
`described_fact_count` · **Reason codes:** none · **Evidence ids:** none

---

## 1 · The claims it makes

Two, from one pass over one structure:

> *The facts that stated how sure they were, on average, were this sure.*

> *Each fact that arrived was seen by this many independent systems, on average.*

The class docstring is the argument for keeping them together and for treating their absences
differently:

> *A record that never stated a confidence contributes nothing to the source-quality mean — it is
> unknown, not weak. But it still contributes to corroboration, because "how many systems saw this"
> is knowable even when "how sure is the system" is not; an absent `src_count` reads as one sighting,
> which is the floor of the ladder rather than a hole in it.*

That asymmetry is the whole design of this plugin. **A silent confidence is excluded from its mean.
A silent source count is included at the ladder's floor.** Both are correct and they are not the
same rule.

This is the 40-weight axis and the 20-weight axis — 60% of the blend — reading fields that a
producer controls. It is the only part of the confidence score that a badly-behaved upstream system
can inflate.

---

## 2 · The code

```python
# confidence.py:156
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    if _bridged_confidence_bp(view) is not None:
        return ()                       # the capability delegated confidence; say nothing
    confidences: list[int] = []
    corroborations: list[int] = []
    for field in _present_fields(view):
        record = fact_record(view.request, field)
        if not isinstance(record, Mapping):
            continue
        if "confidence_bp" in record:
            confidences.append(basis_points(
                record["confidence_bp"], f"{field}.confidence_bp"))
        elif "confidence" in record:
            confidences.append(ratio_bp(record["confidence"], f"{field}.confidence"))
        groups = integer(record.get("src_count", 1), f"{field}.src_count")
        corroborations.append(
            _CORROBORATION_MANY_BP if groups >= 3
            else (_CORROBORATION_PAIR_BP if groups == 2 else _CORROBORATION_SINGLE_BP))
    return (Observation(
        plugin_id=self.plugin_id,
        kind="confidence.fact_source_quality",
        metrics={
            "source_quality_bp": divide_half_up(sum(confidences), len(confidences))
            if confidences else _NEUTRAL_BP,
            "corroboration_bp": divide_half_up(sum(corroborations), len(corroborations))
            if corroborations else _NEUTRAL_BP,
            "self_reported_fact_count": len(confidences),
            "described_fact_count": len(corroborations),
        },
    ),)
```

### Dependencies

| Symbol | Defined at | What it does |
|---|---|---|
| `_bridged_confidence_bp(view)` | `confidence.py:82` | the branch test |
| `_present_fields(view)` | `confidence.py:111` | declared fields found in `request.context.facts`, in declared order |
| `fact_record(request, field)` | `common.py:20` | `request.context.facts.get(field)` — the raw record, not its `value` |
| `basis_points(v, label)` | `common.py:47` | integral `int` / `Decimal` / numeric string in `0..10_000`, else `ValueError` |
| `ratio_bp(v, label)` | `common.py:66` | `0..1` → `× 10,000`; anything else read as basis points; half-up, clamped |
| `integer(v, label)` | `common.py:30` | integral `int` / `Decimal` / numeric string; **rejects `bool` and `float`** |
| `divide_half_up(n, d)` | `common.py:79` | half-away-from-zero integer division |
| `_NEUTRAL_BP` | `confidence.py:57` | `5_000` |
| `_CORROBORATION_MANY_BP` / `_PAIR_BP` / `_SINGLE_BP` | `confidence.py:62-64` | `10_000` / `8_500` / `6_000` |

---

## 3 · Config

**None.** No config key is read. The ladder rungs and the neutral midpoint are module constants;
`source_reasoner` reaches this plugin only as an on/off switch through `_bridged_confidence_bp`.

---

## 4 · When it stays silent

**Exactly one condition:** `_bridged_confidence_bp(view) is not None`.

The plugin never returns `()` because it found nothing to measure. It has three separate ways of
saying "nothing to measure" *inside* an observation:

| Situation | `source_quality_bp` | `corroboration_bp` | `self_reported_fact_count` | `described_fact_count` |
|---|---|---|---|---|
| No fields present at all | `5,000` | `5,000` | 0 | 0 |
| All present fields are bare scalars | `5,000` | `5,000` | 0 | 0 |
| Mapping records, none stating a confidence | `5,000` | ladder mean | 0 | n |
| Mapping records with confidences | mean | ladder mean | n | n |
| A bridge applies | — | — | — | **silent** |

Rows 1 and 2 are indistinguishable in the published metrics, because the counts are dropped by
`calculate`. So a persisted `source_quality_bp = 5,000` has **four** indistinguishable causes: no
fields arrived, all fields were scalars, no field stated a confidence, or several fields stated
confidences that happened to average exactly 5,000. On the native path the last one is the likely
reading, because `reason/runner.py:100` writes `"confidence": 0.5` whenever the database column
is `NULL` — an unstated confidence arrives as an explicit `0.5`, which is `5,000bp`.

That is worth stating plainly. **The `_NEUTRAL_BP` fallback for `source_quality_bp` is close to
unreachable in production**, because Layer 2's native loader always writes a `confidence` key. The
fallback fires in tests, in the legacy-context path where records may be scalars, and for derived
fields written as bare values — not for graph facts.

---

## 5 · The arithmetic — source quality

```
for each present field whose record is a Mapping:
    if "confidence_bp" in record:  confidences += [ basis_points(record["confidence_bp"]) ]
    elif "confidence"  in record:  confidences += [ ratio_bp(record["confidence"])        ]

source_quality_bp = half_up(sum(confidences), len(confidences))   if confidences
                  = 5,000                                          otherwise
```

An **unweighted arithmetic mean**. No authority weighting, no recency weighting, no trimming. A
low-rank guessed field drags the mean exactly as hard as the system-of-record field beside it. That
is a simplification, not an argued position — nothing in the code defends it.

`elif` means **explicit basis points win**. A record carrying both `confidence_bp: 2,500` and
`confidence: "0.9"` contributes `2,500`. Pinned by
`test_explicit_basis_points_win_over_a_ratio_on_the_same_record`.

### 5.1 · `basis_points` — strict, and fatal when violated

| `confidence_bp` value | Result |
|---|---|
| `9000` | `9,000` |
| `"9000"` | `9,000` |
| `Decimal("9000")` | `9,000` |
| `0` | `0` |
| `10000` | `10,000` |
| `10001` | **`ValueError`** — out of range |
| `-1` | **`ValueError`** |
| `0.75` (float) | **`ValueError`** — floats never accepted |
| `True` | **`ValueError`** — `bool` rejected before the `int` check |
| `"9000.5"` / `Decimal("9000.5")` | **`ValueError`** — not integral |
| `None`, `"abc"` | **`ValueError`** |

There is no degradation path. A single malformed fact takes the whole run down:
`orchestrator._evaluate` catches the `ValueError` and produces `ResultStatus.FAILED`, and because
every shipped spec sets `failure_policy=REQUIRED`, that terminates the run.
`test_a_malformed_fact_still_fails_the_run_exactly_as_it_used_to` pins this as **preserved, not
fixed**: *"Changing it would change behaviour, which this migration may not."*

The boundaries survive intact — `test_boundary_confidences_survive_the_blend_intact` asserts `0 → 0`
and `10,000 → 10,000`, so the clamps downstream are no-ops on legal input.

### 5.2 · `ratio_bp` — permissive, and quietly ambiguous

```python
# common.py:66
amount = decimal(value, label)
if Decimal("0") <= amount <= Decimal("1"):
    amount *= Decimal(10_000)
return clamp_bp(int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
```

| `confidence` value | Result | Reading |
|---|---|---|
| `"0.8"` / `0.8` | `8,000` | ratio |
| `"0"` / `0` | `0` | ratio |
| `Decimal("0.999")` | `9,990` | ratio |
| `"0.99995"` | `10,000` | ratio, rounded half-up |
| `1` / `"1.0"` | `10,000` | ratio |
| `1.00005` | **`1`** | basis points |
| `2` | **`2`** | basis points |
| `20000` | `10,000` | basis points, clamped |
| `-0.5` | `0` | clamped |
| `"abc"`, `None`, `True`, `NaN` | **`ValueError`** | |

**This is the sharpest trap in the unit.** The dual interpretation is undocumented in the function
except by its one-line docstring, and the discontinuity sits at exactly `1.0`:

```
confidence = 0.99999  →  9,999bp   (99.99% sure)
confidence = 1        → 10,000bp   (100%  sure)
confidence = 1.00005  →      1bp   (0.01% sure)   ← a 10,000× collapse across 0.00005
confidence = 2        →      2bp   (0.02% sure)
```

A producer that emitted a percentage — `confidence: 85` meaning 85% — would be read as `85bp`,
0.85%, and would drag `source_quality_bp` to near zero without a single error being raised. Note
that `adapters/native.py:_confidence_bp` handles exactly that case with a three-branch rule
(`≤ 1` → ratio, `≤ 100` → percent, else basis points) — but that function is used for
`EvidenceRef.confidence_bp`, which this unit never reads. The two readers of the same producer
convention disagree, and the stricter one is the one that feeds the score.

Nothing guards it and no test covers a percentage-shaped value. Shipped Layer 2 writers all emit
ratios (`runner.py:100` writes `float(r.confidence)`; `signals_derived.py:38` writes `0.9`;
`runner.py:507` writes the integer `1`, which happens to mean 100%), so it is a latent trap rather
than a live fault.

### 5.3 · The arithmetic — corroboration

```
for each present field whose record is a Mapping:
    groups = integer(record.get("src_count", 1))
    corroborations += [ 10,000 if groups >= 3 else 8,500 if groups == 2 else 6,000 ]

corroboration_bp = half_up(sum(corroborations), len(corroborations))   if corroborations
                 = 5,000                                                otherwise
```

| `src_count` | Rung | Reading |
|---|---|---|
| absent | `6,000` | *"an absent `src_count` reads as one sighting, which is the floor of the ladder rather than a hole in it"* |
| `1` | `6,000` | one system says so |
| `2` | `8,500` | two systems agree |
| `3` | `10,000` | three or more agree — as good as it gets |
| `9` | `10,000` | the ladder has no fourth rung |
| `0` | `6,000` | **falls through to the floor** |
| `-4` | `6,000` | **falls through to the floor** |

`test_corroboration_climbs_a_discrete_ladder_by_source_count` parametrises 1, 2, 3 and 9.

The last two rows are unpinned and undefended. `integer` accepts negatives (`integer(-1) == -1`), and
the ladder is written as `>= 3` / `== 2` / else, so `0` and `-4` land on the "one sighting" rung. A
`src_count` of zero should arguably be impossible — a fact exists because something asserted it — but
nothing enforces that, and if it ever arrives it reads as corroborated-once.

**Why a step function.** *"A step function rather than a curve because the business meaning is
discrete — 'one system says so' versus 'three systems agree'."* The rungs are unequal on purpose:
the jump from 1 to 2 sources is worth `2,500bp` and the jump from 2 to 3 is worth `1,500bp`,
encoding diminishing returns without a formula.

**The ladder floors at 6,000, not at 0.** A single-sourced fact is 60% corroborated by construction.
Combined with the 20-point weight, that means **every computed run with at least one mapping-shaped
fact carries a guaranteed `1,200bp` of confidence from corroboration alone**, before anything is
measured. That is the floor derived in [01 · Input and Validator](01-Input-and-Validator.md) §4.2.

**The ladder was dead code until recently.** `context/graph_store.py:146` records why:

> *This branch used to return None before any ref was written, so `src_count` could never exceed 1
> and the whole ladder was dead code — email + CRM agreeing looked identical to email alone.*

The corroboration write path was fixed; the 8,500 and 10,000 rungs are now reachable in production.

### 5.4 · Which records participate

```python
if not isinstance(record, Mapping):
    continue
```

Only mapping-shaped records. A bare scalar contributes to **neither** list — not to the confidence
mean, not to corroboration. It still counts for completeness in
[03a](03a-plugin-coverage_completeness.md), because it arrived.

An empty mapping `{}` **does** participate: it is a `Mapping`, so `src_count` defaults to `1` and it
contributes `6,000` to corroboration while contributing nothing to the confidence mean. That is
consistent with the rule — the record exists and made no claim about how many saw it, so the floor
applies.

Scan order is `_present_fields`, which is declared order, which is *sorted* order because both
`required_fields` tuples are sorted at construction. `test_fact_insertion_order_cannot_change_the_result`
pins that two spellings of the same snapshot hash identically.

---

## 6 · Worked examples

### 6.1 · Two facts, both self-reporting, differently corroborated

**Setup.** `test_the_blend_is_the_documented_weighted_mean_of_the_four_axes`.

```
declared = ("deal.status", "deal.value", "thread.last_inbound")
facts    = {"deal.status": {"value": "open",   "confidence_bp": 9000, "src_count": 2},
            "deal.value":  {"value": 120000,   "confidence": "0.5",   "src_count": 3}}
```

```
deal.status  → "confidence_bp" present → basis_points(9000)      = 9,000
             → src_count 2             → _CORROBORATION_PAIR_BP  = 8,500
deal.value   → "confidence_bp" absent, "confidence" present
             → ratio_bp("0.5"): 0 ≤ 0.5 ≤ 1 → 0.5 × 10,000       = 5,000
             → src_count 3             → _CORROBORATION_MANY_BP  = 10,000
thread.last_inbound → declared but absent → not scanned

confidences    = [9,000, 5,000]
source_quality_bp = half_up(14,000, 2) = (14,000 + 1) // 2       = 7,000
corroborations = [8,500, 10,000]
corroboration_bp  = half_up(18,500, 2) = (18,500 + 1) // 2       = 9,250
```

```
Observation(plugin_id="fact_source_quality",
            kind="confidence.fact_source_quality",
            metrics={"source_quality_bp": 7000,
                     "corroboration_bp": 9250,
                     "self_reported_fact_count": 2,
                     "described_fact_count": 2},
            evidence_ids=(), reason_codes=())
```

The full unit on this input, with one `crm`-grouped evidence item:

```
completeness_bp      = half_up(2 × 10,000, 3)                    = 6,667
evidence_coverage_bp = 1 group × 2,500                           = 2,500
confidence_bp = half_up(7,000×40 + 6,667×30 + 9,250×20 + 2,500×10, 100)
              = half_up(280,000 + 200,010 + 185,000 + 25,000, 100)
              = half_up(690,010, 100) = (690,010 + 50) // 100    = 6,900
```

### 6.2 · A scalar among the mappings — `sales.deal_cooling`

**Setup.** Differential case `deal_cooling_partial_facts`, on the shipped four-field spec.

```
facts = {"deal.status":        {"value": "open",  "confidence_bp": 9000, "src_count": 2},
         "deal.value":         {"value": 120000,  "confidence": "0.8",   "src_count": 3},
         "derived.engagement": 42}                              ← a bare int
```

```
deal.status         → 9,000  ·  8,500
deal.value          → ratio_bp("0.8") = 8,000  ·  10,000
derived.engagement  → not a Mapping → `continue` → contributes to NEITHER list
thread.last_inbound → absent → not scanned

confidences       = [9,000, 8,000]     → self_reported_fact_count = 2
source_quality_bp = half_up(17,000, 2) = 8,500
corroborations    = [8,500, 10,000]    → described_fact_count     = 2
corroboration_bp  = half_up(18,500, 2) = 9,250
```

Verified full-unit result with two evidence groups (`crm`, `mailbox`):

```
{confidence_bp: 8000, source_quality_bp: 8500, completeness_bp: 7500,
 corroboration_bp: 9250, evidence_coverage_bp: 5000, independent_evidence_groups: 2}

half_up(8,500×40 + 7,500×30 + 9,250×20 + 5,000×10, 100)
= half_up(340,000 + 225,000 + 185,000 + 50,000, 100) = half_up(800,000, 100) = 8,000
```

Note that `derived.engagement` **raised** completeness (it arrived, 3 of 4 rather than 2 of 4) while
being invisible to both of this plugin's axes. That is the intended division of labour: presence is
structural, quality is a claim.

### 6.3 · A declared field that never arrived is not scored

```
declared = ("deal.status", "deal.value")
facts    = {"deal.status": {"value": "open", "confidence_bp": 10_000}}
```

```
present            = ("deal.status",)
confidences        = [10,000]
source_quality_bp  = half_up(10,000, 1) = 10,000
self_reported_fact_count = 1
```

The absent `deal.value` does **not** contribute a `0` to the mean. The one fact that arrived is
perfectly self-confident, so the axis says so — and the missing half of the picture is
`completeness_bp = 5,000`'s problem, in the other plugin. `test_a_declared_field_that_never_arrived_is_not_scored_for_quality`.

This is the four-axis design paying for itself: two different failures, two different numbers, one
blend. A single fused "quality" score would have to choose between reporting 10,000 and 5,000, and
either choice would be a lie.

### 6.4 · Boundaries

| Facts | `source_quality_bp` | `corroboration_bp` | Note |
|---|---|---|---|
| one, `confidence_bp: 0` | `0` | `6,000` | zero is a genuine reading, not an absence |
| one, `confidence_bp: 10_000` | `10,000` | `6,000` | the ceiling survives the mean |
| one, `confidence: "1"` | `10,000` | `6,000` | `1` read as a ratio |
| one, `{"value": "open"}` | `5,000` | `6,000` | unstated confidence, one implied sighting |
| one, `42` (scalar) | `5,000` | `5,000` | invisible to both axes |
| two at `3,333` | `3,333` | `6,000` | `half_up(6,666, 2) = 3,333` |
| `{}` | `5,000` | `6,000` | a Mapping with nothing in it still counts as one sighting |

`test_boundary_confidences_survive_the_blend_intact` parametrises the first two rows;
`test_a_bare_scalar_fact_carries_no_metadata_and_is_counted_nowhere_here` pins the fifth;
`test_a_record_without_a_source_count_reads_as_one_sighting` pins the fourth.

---

## 7 · Edge cases and known traps

| Input | Behaviour | Status |
|---|---|---|
| `confidence_bp` out of `0..10,000` | **whole run fails** with `ValueError` | preserved deliberately; pinned |
| `confidence_bp` as a float | **whole run fails** | floats would make the hash machine-dependent |
| `confidence: 85` meaning 85% | silently read as `85bp` | **live trap**, untested, no guard |
| `confidence: 1.00005` | silently read as `1bp` | **live trap** at the ratio/bp boundary |
| `src_count: 0` or negative | reads as one sighting, `6,000` | unpinned, undefended |
| `src_count` as a float or `bool` | **whole run fails** | `integer` rejects both |
| `{}` as a fact record | one sighting, no confidence | consistent with the rules |
| Record with only `value` | one sighting, no confidence | the common Layer 2 shape for derived facts |
| 200 facts, one stating confidence | that one's value **is** `source_quality_bp` | the mean is over stating facts only |
| A bridge applies **and** a fact is malformed | run succeeds, fact never read | `test_the_decomposition_plugins_stand_down_when_the_bridge_applies` |

The ninth row deserves a sentence. Because the mean is over *stating* facts rather than over
*present* facts, one optimistic producer among two hundred silent ones sets the entire 40-point axis.
`self_reported_fact_count` was computed precisely to make that visible — and then dropped before the
result was built, so a reader of a persisted decision cannot tell a one-fact mean from a
two-hundred-fact one.

---

## Related

- [03 · Analyzer](03-Analyzer.md) — why these two axes share one plugin
- [03a · `coverage_completeness`](03a-plugin-coverage_completeness.md) — the structural axes that need no metadata
- [03c · `legacy_bridge`](03c-plugin-legacy_bridge.md) — the only thing that silences this plugin
- [04 · Calculator](04-Calculator.md) — where these two get their 40 and 20 weights

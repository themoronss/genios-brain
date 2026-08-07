# 05 · Evaluator

**Stage 6:** `confidence.py:ConfidenceReasoner.evaluate_meaning` (line 285) — `@abstractmethod` in
the framework.

---

## 1 · What it is for

The Evaluator turns numbers into meaning. In most units that means crossing a threshold: `82 → high
risk`, `opportunity_bp ≥ 3,000 → matched`. Here it means something narrower and, in the code's own
framing, more important:

> *Publish the decomposition, not just the score.*
>
> *A bare `confidence_bp` is an assertion; the decomposition beside it is an explanation, and it is
> what lets a reviewer say "this was 42% because half the fields never arrived" instead of arguing
> with a number.*

There is **no threshold in this unit.** Not one. `evaluate_meaning` reads no config, compares nothing
to anything, and cannot reach two different outcomes for two different numbers.

---

## 2 · The code

```python
# confidence.py:285
def evaluate_meaning(self, view, metrics, observations) -> Verdict:
    published: dict[str, object] = dict(metrics)
    if any(item.plugin_id == LegacyBridgePlugin.plugin_id for item in observations):
        published["source"] = "legacy"
    finding = Finding("confidence.decomposition", "confidence", metrics=published,
                      reason_codes=(CONFIDENCE_REASON,))
    return Verdict(
        matched=None,
        metrics={name: value for name, value in published.items()
                 if name not in UNDECLARED_METRICS},
        findings=(finding,),
        reason_codes=finding.reason_codes,
    )
```

Four things happen: the bridged marker is attached, one `Finding` is built from the complete metric
map, `completeness_bp` is filtered out of the `Verdict`, and `matched` is set to `None`.

Note that the finding carries **more** than the verdict. That inversion is the whole reason `build`
is overridden — see [06 · Builder and Metrics](06-Builder-and-Metrics.md) §2.

---

## 3 · `matched` is always `None`

```python
matched=None
```

The docstring:

> *`matched` stays None on purpose: confidence is a reading, not a gate, and a False here would read
> downstream as "the confidence check failed".*

`ReasonerResult.matched` is `bool | None`, and the three values mean three different things to the
orchestrator and the Decision Maker:

| `matched` | Meaning | Who uses it |
|---|---|---|
| `True` | the unit's condition holds | `orchestrator.py:217` for gating specs; `core.constraint`, `core.opportunity` |
| `False` | the unit's condition does **not** hold | a gating reasoner returning `False` sets `terminal = NO_ACTION` and stops the run |
| `None` | this unit made a reading, not a judgement | `core.confidence`, `core.priority`, `core.context` |

The danger is concrete rather than stylistic. If this unit ever returned `matched=False` **and** a
capability declared it `gating=True`, `orchestrator.py:217` would set `terminal = NO_ACTION` and
every later step would be skipped — a low confidence would silently kill the run instead of lowering
its score. No shipped capability declares this unit gating, and
`orchestrator.py:276` would reject a gating spec whose unit returned `None`, so the two guards are
mutually exclusive today. `test_the_result_reports_a_reading_rather_than_a_verdict` pins
`matched is None`.

`Finding.matched` is left at its default `None` for the same reason.

---

## 4 · What the Verdict carries

| `Verdict` field | Value | Why |
|---|---|---|
| `matched` | `None` | a reading, not a gate |
| `metrics` | `published` minus `UNDECLARED_METRICS` | to satisfy the framework's `publishes` guard |
| `findings` | one `Finding` | the decomposition |
| `adjustments` | `()` | **this unit never nudges a candidate's score** |
| `checks` | `()` | **this unit never eliminates a candidate** |
| `reason_codes` | `("confidence_computed",)` | copied from the finding |

The two empty tuples are a statement of scope, and they are the reason this unit can be trusted with
the confidence authority. A `CandidateAdjustment` moves a play's utility; a `CandidateCheck` can
`ELIMINATE` a play outright. This unit emits neither, in either branch, under any input. It measures
and reports; it cannot reach into the candidate field.

> *The unit analyses; it never decides.* — module docstring, `confidence.py:26`

The only way its number affects a candidate is through `decision_maker.py`, which reads
`confidence_bp` and applies it uniformly to every candidate in the run
(`build_candidate_objects` at `decision_maker.py:306` sets the same `confidence_bp` on all of them).
Confidence therefore cannot reorder a ranking — it scales the whole field or, below the floor,
converts the decision into a question.

### 4.1 · The `source` marker

```python
if any(item.plugin_id == LegacyBridgePlugin.plugin_id for item in observations):
    published["source"] = "legacy"
```

Attached only on the bridged branch. The code comment:

> *Marks the number as somebody else's, so an auditor reading the result can tell a bridged
> confidence from a computed one without re-deriving the branch. A deliberately non-integer metric —
> the only one in the roster — kept because changing it would change the result hash of every legacy
> strangler decision ever replayed.*

Three consequences of a string metric:

1. It is legal. `ReasonerResult.__post_init__` and `Finding.__post_init__` type-check only names
   ending in `_bp` (`contracts/reasoning.py:617` and `:534`), so a non-`_bp` metric can carry
   anything `canonicalize` accepts.
2. It bypasses the framework's `build` clamp — but this unit overrides `build`, so the clamp never
   ran anyway. Had it used the base builder, `clamp_bp` would still have skipped `source` because it
   only touches `_bp` names.
3. It is declared in `publishes`, which is what stops the guard at `unit.py:256` from rejecting it.

`test_a_bridged_run_is_labelled_as_somebody_elses_number` asserts the whole metric map on the bridged
path: `{"confidence_bp": 7300, "source": "legacy"}`.

**The marker is one-sided.** There is no `source: "computed"` on the other branch. An auditor
distinguishes the branches by the *absence* of a key, which also means the "the capability declared a
bridge and it silently did not apply" case ([03c](03c-plugin-legacy_bridge.md) §4.3) is invisible in
the persisted result.

### 4.2 · The `UNDECLARED_METRICS` filter

```python
metrics={name: value for name, value in published.items()
         if name not in UNDECLARED_METRICS}
```

`UNDECLARED_METRICS = ("completeness_bp",)`. This line exists to get past the framework guard:

```python
# unit.py:256
undeclared = sorted(set(verdict.metrics) - set(self.publishes)) if self.publishes else []
if undeclared:
    raise ValueError(f"{self.unit_id} published undeclared metrics: {', '.join(undeclared)}")
```

`completeness_bp` cannot be added to `publishes` because `core.context` already declares it, and
`tests/test_unit_roster.py::test_no_unit_publishes_a_metric_another_unit_owns` permits exactly one
declared publisher per name. So the metric is stripped here and reattached in `build`.

`confidence.py:73` records the reason:

> *The value is preserved byte-for-byte because removing or renaming it would change every decision
> hash; the name collision is recorded here rather than fixed.*

This is the one place in the seventeen-unit roster where the framework's own guard is routed around
by design. `test_completeness_is_emitted_but_undeclared_and_that_is_recorded` asserts all three
halves at once: the metric is in `result.metrics`, it is in `UNDECLARED_METRICS`, and it is not in
`publishes`.

**What the collision actually costs.** The two units compute different quantities under one name:

| | `core.context` | `core.confidence` |
|---|---|---|
| Denominator | capability `required_fields` ∪ every reasoner's `required_fields` ∪ Layer 2's `context.missing_fields` | this spec's `required_fields`, else the capability's |
| Nothing declared | emits no observation at all — silence | emits `10,000` |
| Symbol | `context_unit.py:130`, `FactCoveragePlugin` at `:107` | `confidence.py:209`, `CoverageCompletenessPlugin` |

`completeness_bp` is **not** in `validation_unit.py:AUTHORITY_RESOLVED_METRICS`, so when both units
run in `sales.deal_cooling_full` and their readings differ by `contradiction_gap_bp` or more,
`core.validation` reports a `validation.metric_divergence` — a genuine contradiction that drags
`safe_bp` toward the safety floor. On today's v2 roster the denominators differ by exactly one field,
capping the possible gap at `2,000bp` against a default tolerance of `5,000bp`. **A latent hazard,
not a live fault.** It becomes live if a capability declares a much narrower confidence spec than its
roster, or if Layer 2 starts populating `context.missing_fields`, which enters `core.context`'s
denominator and nothing else's.

---

## 5 · The finding

```python
Finding("confidence.decomposition", "confidence",
        matched=None,
        metrics=published,          # ALL of them, including completeness_bp and source
        evidence_ids=(),
        reason_codes=("confidence_computed",))
```

| Field | Value | Note |
|---|---|---|
| `finding_id` | `"confidence.decomposition"` | one id, both branches — the shape differs, the identity does not |
| `kind` | `"confidence"` | |
| `matched` | `None` | |
| `metrics` | the complete map | 6 keys computed, 2 keys bridged |
| `evidence_ids` | `()` | see [06](06-Builder-and-Metrics.md) §4 |
| `reason_codes` | `("confidence_computed",)` | |

**Exactly one finding, always.** Not one per plugin, as `core.opportunity` emits, and not zero below
a threshold. The decomposition is a single coherent statement about one number, so splitting it into
per-axis findings would invite a downstream reader to consume one axis without the others.

`test_the_decomposition_travels_beside_the_score` asserts `dict(finding.metrics) == dict(result.metrics)`
— the finding and the result carry identical maps. That equality is not automatic; it is what the
`build` override exists to produce.

### 5.1 · The reason code

`CONFIDENCE_REASON = "confidence_computed"` — one code, both branches, every run.

> *Confidence is always produced — there is no "confidence unknown" outcome — so the code states
> that the number exists, not what it turned out to be.* — `confidence.py:40`

A reason code that fires unconditionally carries no information, and that is the point: its constancy
is the assertion. Compare `core.opportunity`, whose codes name *which* signal fired, or
`legacy.score_gate`, which emits `legacy_score_gate_pass` or `legacy_score_gate_failed`. Here there
is nothing to name — the branch is visible in the metric shape and the value is visible in
`confidence_bp`.

The consequence: **`reason_codes` cannot tell you which branch ran, and neither can the finding id.**
Only the presence of `source` and the number of metric keys can.

---

## 6 · Worked examples

### 6.1 · Computed branch

Input from [04 · Calculator](04-Calculator.md) §4.1:

```python
metrics = {"confidence_bp": 8000, "source_quality_bp": 8500, "completeness_bp": 7500,
           "corroboration_bp": 9250, "evidence_coverage_bp": 5000,
           "independent_evidence_groups": 2}
```

```
observations contain no legacy_bridge      → no "source" key
published    = the six metrics, unchanged
finding      = Finding("confidence.decomposition", "confidence",
                       metrics=<six>, reason_codes=("confidence_computed",))
Verdict.metrics = five metrics             ← completeness_bp stripped
```

Guard check at `unit.py:256`:

```
set(verdict.metrics) = {confidence_bp, source_quality_bp, corroboration_bp,
                        evidence_coverage_bp, independent_evidence_groups}
set(publishes)       = {confidence_bp, source, source_quality_bp, corroboration_bp,
                        evidence_coverage_bp, independent_evidence_groups}
difference           = ∅                   → passes
```

`publishes` is an upper bound, not a requirement: `source` is declared and not emitted, and the guard
only tests one direction.

### 6.2 · Bridged branch

```python
metrics = {"confidence_bp": 7300}
```

```
observations contain legacy_bridge         → published["source"] = "legacy"
published    = {"confidence_bp": 7300, "source": "legacy"}
finding      = Finding("confidence.decomposition", "confidence",
                       metrics={"confidence_bp": 7300, "source": "legacy"},
                       reason_codes=("confidence_computed",))
Verdict.metrics = {"confidence_bp": 7300, "source": "legacy"}   ← nothing to strip
```

Guard: both names are in `publishes` → passes.

`test_a_bridged_run_is_labelled_as_somebody_elses_number` asserts exactly this map on the final
result.

### 6.3 · The thin snapshot — meaning without a threshold

```python
metrics = {"confidence_bp": 3000, "source_quality_bp": 5000, "completeness_bp": 0,
           "corroboration_bp": 5000, "evidence_coverage_bp": 0,
           "independent_evidence_groups": 0}
```

`matched` is still `None`. `reason_codes` is still `("confidence_computed",)`. There is no
`low_confidence` code, no `matched=False`, no adjustment and no check. **A 3,000bp run and a 9,000bp
run are structurally identical results that differ only in their numbers.**

That is a deliberate division of labour. Deciding what 3,000bp *means* belongs to
`decision_maker.py`, where `confidence_floor_bp` turns a low number into `DecisionOutcome.DEFER` —
per-capability, at Layer 3's discretion, rather than hardcoded in a shared unit. See
[06](06-Builder-and-Metrics.md) §5 for whether that floor can actually fire.

---

## 7 · Edge cases

| Situation | Verdict |
|---|---|
| Any `confidence_bp` from 0 to 10,000 | identical shape; only the number differs |
| Bridged at `0` | `{"confidence_bp": 0, "source": "legacy"}` — `matched` still `None` |
| Every axis at its neutral | six metrics, no marker |
| `completeness_bp` present in `metrics` | stripped from the Verdict, retained in the Finding |
| `source` present in `metrics` | retained in both — it is declared |
| A future seventh metric added to `calculate` | `ValueError` from the guard unless added to `publishes` |
| A future second finding added ahead of the decomposition | guard still passes; **`build` would then read the wrong finding** — see [06](06-Builder-and-Metrics.md) §2 |
| Metric insertion order | irrelevant — `canonical.py:canonical_dumps` uses `sort_keys=True` |

The second-to-last row is the sharpest latent bug in the unit. Nothing in `evaluate_meaning` or
`build` asserts that `findings` has exactly one element or that element zero is the decomposition.

---

## Related

- [04 · Calculator](04-Calculator.md) — where these metrics come from
- [06 · Builder and Metrics](06-Builder-and-Metrics.md) — the overridden `build` that reattaches `completeness_bp`
- [03c · `legacy_bridge`](03c-plugin-legacy_bridge.md) — the branch that earns the `source` marker
- [Unit Framework §3.4](../../README.md) — the `publishes` guard and this unit's documented escape from it

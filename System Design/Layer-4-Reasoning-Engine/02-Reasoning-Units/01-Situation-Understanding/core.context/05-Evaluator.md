# 05 · Evaluator

**Stage 6 of eight.** `@abstractmethod` on the base class.
`context_unit.py:ContextUnit.evaluate_meaning`, 27 lines including its docstring.

---

## 1 · What it is for

The Evaluator turns numbers into meaning — *"a threshold crossed, a candidate blocked, a gate
matched"*. It is the stage where `82` becomes `high risk`.

For `core.context` it does exactly one of those three things. It names the thresholds the reading
crossed, and it declines to say whether crossing them was good or bad.

> *"Name the thresholds the reading crossed — without declaring the situation good or bad."*

---

## 2 · What exists

```python
def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                     observations: Sequence[Observation]) -> Verdict:
    codes = {code for observation in observations for code in observation.reason_codes}

    completeness = metrics.get("completeness_bp")
    if completeness is not None:
        codes.add("context_incomplete"
                  if completeness < _config_bp(view, "completeness_floor_bp", 6_000)
                  else "context_substantially_known")

    freshness = metrics.get("freshness_bp")
    if freshness is not None:
        codes.add("context_stale" if freshness < _config_bp(view, "freshness_floor_bp", 3_000)
                  else "context_current")

    corroboration = metrics.get("corroboration_count")
    if corroboration is not None:
        codes.add("context_corroborated"
                  if corroboration >= _config_count(view, "min_corroboration", 2)
                  else "context_single_sourced")

    findings = tuple(Finding(
        finding_id=f"context.{observation.plugin_id}",
        kind="context",
        matched=None,
        metrics=observation.metrics,
        evidence_ids=observation.evidence_ids,
        reason_codes=observation.reason_codes,
    ) for observation in sorted(observations, key=lambda item: item.plugin_id))

    return Verdict(matched=None, metrics=dict(metrics), findings=findings,
                   reason_codes=tuple(sorted(codes)))
```

### 2.1 · The `Verdict` it returns

| Field | Value | Note |
|---|---|---|
| `matched` | **always `None`** | §3 |
| `metrics` | `dict(metrics)` — a copy of the Calculator's output, unchanged | 0, 4, 5, 8, 9 or 12 entries |
| `reason_codes` | `tuple(sorted(codes))` — plugin codes ∪ threshold codes | 0 to 6 entries |
| `findings` | one `Finding` per observation, in `plugin_id` order | 0 to 3 entries |
| `adjustments` | `()` — the `Verdict` default, never set | §4.3 |
| `checks` | `()` — the `Verdict` default, never set | §4.3 |

`test_the_unit_reports_and_never_rules` asserts `result.matched is None`, `result.adjustments == ()`
and `result.checks == ()` — *"it never nudges a play's score"* and *"it never eliminates one"*.

### 2.2 · The three thresholds

| Reading | Condition | Code when crossed | Code otherwise | Config key | Default | Boundary |
|---|---|---|---|---|---|---|
| `completeness_bp` | `< floor` | `context_incomplete` | `context_substantially_known` | `completeness_floor_bp` | `6,000` | exactly 6,000 → **substantially known** |
| `freshness_bp` | `< floor` | `context_stale` | `context_current` | `freshness_floor_bp` | `3,000` | exactly 3,000 → **current** |
| `corroboration_count` | `>= minimum` | `context_corroborated` | `context_single_sourced` | `min_corroboration` | `2` | exactly 2 → **corroborated** |

Two floors use strict `<`, the corroboration bar uses `>=`. Read as sentences that is consistent:
*"below the floor is incomplete"*, *"at or above the bar is corroborated"*. Both boundaries are
inclusive on the favourable side.

### 2.3 · The full reason-code vocabulary

Six of the nine possible codes appear on any single run — one from each of six mutually exclusive
pairs, minus whichever axes stayed silent.

| Code | Emitted by | Means |
|---|---|---|
| `context_evidence_dated` | `evidence_freshness` plugin | a freshness reading exists |
| `context_fields_absent` | `fact_coverage` plugin | at least one declared field did not arrive |
| `context_fields_all_present` | `fact_coverage` plugin | every declared field arrived |
| `context_sources_conflict` | `source_corroboration` plugin | at least one field has independent witnesses citing different values |
| `context_sources_agree` | `source_corroboration` plugin | no field does |
| `context_incomplete` | evaluator | `completeness_bp` below the capability's floor |
| `context_substantially_known` | evaluator | at or above it |
| `context_stale` | evaluator | `freshness_bp` below the capability's floor |
| `context_current` | evaluator | at or above it |
| `context_corroborated` | evaluator | the best-corroborated field clears the bar |
| `context_single_sourced` | evaluator | it does not |

`context_evidence_dated` is the odd one. It has no negative counterpart and carries no information
the observation's existence did not already carry — a freshness observation exists if and only if
that code is present. It functions as a marker rather than a claim.

**No shipped code reads any of these strings.** A grep across `genios_engine/` finds them only in
`context_unit.py` itself. They exist for the trace and for a future consumer.

---

## 3 · `matched` is `None`, and why that is the whole unit

```python
"""`matched` stays `None` on purpose.  A matched verdict is a claim that some condition the
capability cares about has been met, and "the context is adequate" is exactly the judgement
this unit is forbidden to make: adequacy depends on what is about to be decided, which only
the Decision Maker knows.  The reason codes below are threshold crossings authored in
Layer 3 — statements of fact about a line the capability itself drew, not opinions."""
```

Three separate points in that paragraph, and they are worth pulling apart.

**`None`, not `False`.** `Finding.matched` and `ReasonerResult.matched` are `bool | None`, and the
three values mean three different things: `True` — the condition holds; `False` — it was checked and
does not hold; `None` — no condition was checked. A `False` here would read downstream as *"the
context check failed"*, which is a verdict on the situation. Compare `core.timeline`, which returns
`matched=None` only when it has *no observations at all*, and `matched=bool(breached or decaying)`
otherwise; and `core.constraint`, which returns `None` always because *"some plays may be blocked
and others clear, and collapsing that into one boolean would invent a verdict the rows do not
support."*

**Adequacy is not a property of the context.** Whether 4,000bp of completeness is enough depends on
what is about to be decided with it — drafting a reply needs less than committing a discount. The
unit does not know what will be decided, so it cannot answer.

**A threshold crossing is a fact, not an opinion.** `context_incomplete` says *"the number fell
below the line this capability drew"*. The capability drew the line; the unit reports the crossing.
That is why the codes are legitimate output from a unit that refuses to render a verdict.

### 3.1 · Every reading becomes a Finding, matched or not

```python
# Every reading is recorded as a finding, matched or not: the value of this unit is the
# written record of what was known at decision time, which is only useful if it is always
# there — including, especially, on the runs that turned out badly.
```

Contrast with `core.opportunity`, which emits **no findings and no reason codes** below its
threshold, and `core.dependency`, which emits findings only for blockers. Those units are reporting
*claims*, and a claim below threshold is not worth asserting. `core.context` is reporting *the
record*, and a record that is only kept on good runs is not a record.

| Field | Value | Note |
|---|---|---|
| `finding_id` | `f"context.{observation.plugin_id}"` | `context.evidence_freshness`, `context.fact_coverage`, `context.source_corroboration` |
| `kind` | `"context"` — the same for all three | §4.4 |
| `matched` | `None` | never `True`, never `False` |
| `metrics` | the observation's metrics verbatim | re-frozen by `Finding.__post_init__` via `_mapping` |
| `evidence_ids` | the observation's citations | each plugin's own, not the union |
| `reason_codes` | the observation's codes only | the evaluator's threshold codes stay at unit level |

`test_every_reading_is_written_down_even_when_it_is_unflattering` pins the ids and the ordering:

```python
assert [item.finding_id for item in findings] == [
    "context.evidence_freshness", "context.fact_coverage", "context.source_corroboration"]
assert all(item.matched is None for item in findings)
```

Finding ids are stable across runs — they name the plugin, not a position in a list. If one axis
goes silent, the other two keep the same ids rather than shifting up.

---

## 4 · Edge cases and compromises

### 4.1 · Silence propagates through `metrics.get(...)`

Each threshold branch is guarded by `if <metric> is not None`. A silent plugin contributes no metric,
so no threshold code is added for that axis, and no config key for that axis is read. The unit never
says `context_current` about a situation whose evidence is undated.

`test_a_capability_that_declares_nothing_gets_no_completeness_reading` and
`test_undated_evidence_produces_no_freshness_claim_rather_than_a_zero` both check the *metric*
absence; neither checks the reason-code absence, though it follows from the same branch.

### 4.2 · Two config keys are validated lazily — a real hole

`_config_bp` is called **inside** the `is not None` branch. On any run where the corresponding
plugin stayed silent, a malformed threshold is never read and never raises. Verified:

```text
config={"completeness_floor_bp": 20_000}, capability declares no fields
  → status = COMPLETED, metrics = {}, no error, no diagnostic

config={"completeness_floor_bp": 20_000}, capability declares one field
  → ValueError: completeness_floor_bp must be integer basis points
  → orchestrator: status = FAILED, reason_codes = ('reasoner_failure',)
```

`test_a_malformed_threshold_is_rejected_rather_than_rounded` only covers the second case, and its
fixture declares `required=("deal.status",)` precisely so that the branch is reached.

The two plugin-side keys behave correctly — `freshness_horizon_hours` and `min_corroboration` are
read at the top of `contribute`, before the silence check, and raise on every run. So the module
already contains the right pattern; the evaluator did not follow it.

The consequence is not hypothetical for a shadow-mode capability: a pack could ship a broken
threshold, pass every run against snapshots that happen to have no declared fields, and start
failing the day Layer 2 begins reporting `missing_fields` — which is the day the denominator becomes
non-empty. The failure would look like a Layer 2 regression.

`_config_bp`'s own docstring argues the right position, and it is the position the eager keys take:

> *"Tuning is authored in Layer 3 and versioned with the capability. A malformed value is a
> deployment fault, not something to silently round into range — a threshold that quietly became
> zero would make every situation look complete."*

Reading the config keys unconditionally at the top of `evaluate_meaning` would close it in two lines.

### 4.3 · No adjustments, no checks — and no `publishes`-style guard on them

`Verdict.adjustments` and `Verdict.checks` default to `()` and this unit never sets them, so the
result carries neither. That is enforced by omission rather than by a mechanism: nothing in
`unit.py` prevents a Situation Understanding unit from returning a `CandidateAdjustment`.

What *would* catch it is one layer out: `guards.py:validate_candidate_effects` rejects any
adjustment or check whose `play_id` the capability did not declare, and any component outside
`CANDIDATE_COMPONENTS`. A well-formed adjustment on a declared play would pass. The invariant
*"Category 1 units do not move scores"* holds by author discipline plus
`test_the_unit_reports_and_never_rules`.

### 4.4 · All three findings share `kind="context"`

`core.validation:ContradictionPlugin._opposed_verdicts` buckets findings by `kind` and looks for two
*different* units emitting the same kind with opposite `matched` polarity:

```python
for finding in result.findings:
    if finding.matched is None:
        continue
    ...
```

Every `core.context` finding is skipped at that first line. So the shared `kind` is inert today, and
`test_one_unit_reporting_both_polarities_is_describing_a_mixed_situation` uses `core.context` as a
control case for exactly that reason.

It would stop being inert if a future unit emitted `kind="context"` findings with real polarity.
`"context"` is a generic enough string that this is a plausible collision; `core.timeline` avoids it
by using per-plugin kinds.

### 4.5 · The reason-code set is a `set`, then sorted

`codes` is built as a set comprehension and returned as `tuple(sorted(codes))`, so duplicates
collapse and order is lexicographic. `ReasonerResult.__post_init__` sorts and deduplicates again.
Neither the plugin registration order nor the order the threshold branches run can reach the output.

---

## 5 · Worked examples

### 5.1 · The thin situation — the scenario the unit exists for

`test_a_thin_situation_is_described_as_thin_end_to_end`: two known fields of five declared,
one CRM row dated 720 hours (30 days) ago, one witness, default config.

```text
completeness_bp = divide_half_up(2 × 10_000, 5)                        = 4,000
  4,000 < 6,000                                              → context_incomplete
freshness_bp    = 10,000 − divide_half_up(min(720,168) × 10_000, 168)  = 0
  0 < 3,000                                                  → context_stale
corroboration_count                                                     = 1
  1 < 2                                                      → context_single_sourced

plugin codes: context_evidence_dated · context_fields_absent · context_sources_agree

result
  matched      = None
  metrics      = 12 entries, missing_field_count 3, evidence_age_hours 720
  reason_codes ⊇ {context_incomplete, context_stale, context_single_sourced}
  evidence_ids = ('ev_crm',)
  findings     = 3, all matched=None
```

Three failing thresholds, no verdict. Everything downstream is entitled to know this before it
recommends anything, and the unit's contribution is to make sure it is written down — not to decide
what to do about it.

### 5.2 · The other side of every threshold

`test_a_well_evidenced_situation_crosses_the_other_side_of_every_threshold`: both declared fields
present, two rows 3 and 9 hours old from different independence groups.

```text
completeness_bp = divide_half_up(2 × 10_000, 2)                       = 10,000
  10,000 ≥ 6,000                                            → context_substantially_known
freshness_bp    = 10,000 − divide_half_up(3 × 10_000, 168)  = 10,000 − 179 = 9,821
  9,821 ≥ 3,000                                             → context_current
corroboration_count                                                    = 2
  2 ≥ 2                                                     → context_corroborated

matched = None                       ← still None. A good reading is still not a verdict.
```

That last line is the test's point. Crossing every threshold favourably does not produce
`matched=True`, because the unit has not been asked a question it could answer with `True`.

### 5.3 · Mixed — the normal case

The README §6 run, on the real manifest:

```text
completeness_bp 8,000 ≥ 6,000   → context_substantially_known
freshness_bp        0 <  3,000  → context_stale
corroboration_count 2 ≥ 2       → context_corroborated

reason_codes (6, sorted)
  context_corroborated · context_evidence_dated · context_fields_absent
  · context_sources_agree · context_stale · context_substantially_known
```

`context_fields_absent` and `context_substantially_known` sit side by side: something is missing, and
enough is here. The two codes come from different stages and answer different questions —
[03b](03b-plugin-fact_coverage.md) §4.2.

### 5.4 · Per-capability tuning

`test_thresholds_are_tuned_per_capability_not_hardcoded`. Two facts present of three declared —
`completeness_bp = 6,667` — evaluated under two capabilities:

```text
completeness_floor_bp = 9,000    6,667 < 9,000   → context_incomplete
completeness_floor_bp = 5,000    6,667 ≥ 5,000   → context_substantially_known
```

*"A capability that genuinely needs everything can say so without a code change."* The same snapshot
produces the same twelve metrics and a different reading, which is exactly the separation the layer
is built on: arithmetic in Layer 4, judgement in Layer 3.

### 5.5 · The default boundaries, stated plainly

Neither of these is written down in the module; both fall out of two independently chosen defaults.

| Axis | Default configuration | Boundary |
|---|---|---|
| Completeness | floor 6,000bp | **3 of 5 declared fields is enough; 2 of 5 is not.** On a 4-field denominator, 3 of 4 (7,500) passes and 2 of 4 (5,000) fails |
| Freshness | horizon 168h, floor 3,000bp | **stale at 118 hours** — four days and twenty-two hours |
| Corroboration | minimum 2 | **always `context_single_sourced` in production** — see [03c](03c-plugin-source_corroboration.md) §6 |

The third is the one to act on. On every snapshot either shipped adapter can build,
`corroboration_count` is 1, so `context_single_sourced` is emitted unconditionally and carries no
information. A consumer that treated it as a signal would be reading a constant.

---

## Related

| File | Covers |
|---|---|
| [04 · Calculator](04-Calculator.md) | Why there is no composite number for this stage to threshold |
| [03a](03a-plugin-evidence_freshness.md) · [03b](03b-plugin-fact_coverage.md) · [03c](03c-plugin-source_corroboration.md) | Where each metric and each plugin reason code comes from |
| [06 · Builder and Metrics](06-Builder-and-Metrics.md) | What happens to the Verdict next |
| [Part 2 · The Unit Framework](../../README.md) §4.4 | The result lifecycle, and how a `ValueError` here becomes a `FAILED` result |

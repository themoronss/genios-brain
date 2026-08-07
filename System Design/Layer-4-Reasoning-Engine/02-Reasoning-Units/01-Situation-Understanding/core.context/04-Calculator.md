# 04 · Calculator

**Stage 5 of eight.** `@abstractmethod` on the base class — every unit must implement it.
`context_unit.py:ContextUnit.calculate`, 5 statements.

---

## 1 · What it is for

The Calculator combines the Analyzer's observations into the unit's metrics, in pure integer
arithmetic. For most units this is where the business judgement is compressed into a formula —
`core.opportunity`'s max-plus-a-quarter-of-the-rest, `core.dependency`'s
`10,000 − worst − drag − penalty`.

For `core.context` it is where a formula is deliberately **not** written.

---

## 2 · What exists

```python
def calculate(self, view: UnitView,
              observations: Sequence[Observation]) -> Mapping[str, int]:
    """Publish each plugin's reading as-is; deliberately no composite score.

    Coverage, freshness and corroboration answer three different questions, and averaging them
    would produce a number that means nothing in particular while inviting downstream units to
    treat it as a verdict on the situation.  A situation that is fully known but a month old is
    not "half good" — it is complete and stale, and both halves of that sentence matter to a
    different reader.

    Metric names are disjoint across plugins by construction; iteration is sorted by plugin id
    anyway so that the published mapping can never depend on registration order.
    """
    metrics: dict[str, int] = {}
    for observation in sorted(observations, key=lambda item: item.plugin_id):
        for name in sorted(observation.metrics):
            metrics[name] = int(observation.metrics[name])
    return metrics
```

```text
metrics = ⋃ over observations, in plugin_id order
              ⋃ over metric names, in name order
                 { name : int(value) }
```

No addition, no weighting, no clamping, no threshold. The output is the union of the inputs.

---

## 3 · Why that shape

The docstring makes the argument, and it is the right one. Three parts to it.

### 3.1 · The three readings answer three different questions

Completeness is about *what arrived*. Freshness is about *when anything last happened*.
Corroboration is about *how many observers stand behind it*. There is no operation over those three
that produces a number a reader can act on.

> *"A situation that is fully known but a month old is not 'half good' — it is complete and stale,
> and both halves of that sentence matter to a different reader."*

The README §6 example is exactly that sentence:
`completeness_bp = 8,000` and `freshness_bp = 0`. A mean would give 4,000. What would 4,000 mean? It
would mean neither *"go and fetch the missing field"* nor *"this picture is twelve days old"*, and
those are the two different actions the two different readers need to take.

### 3.2 · A single number would be read as a verdict

> *"averaging them would produce a number that means nothing in particular while inviting
> downstream units to treat it as a verdict on the situation."*

This is the constitutional argument, and it is the same one that keeps `matched` at `None`
([05 · Evaluator](05-Evaluator.md) §3). The unit's class docstring states the boundary:

> *"Publishes nothing that re-scores the system. In particular it does not publish `confidence_bp`
> — completeness and corroboration are *inputs* a confidence authority may weigh, and letting a
> second unit emit confidence would silently move every decision in the plan."*

A `context_quality_bp` would be `confidence_bp` under an assumed name. It would carry no declared
authority, no place in `decision_maker.py`'s authority scan, and no reason code explaining what it
meant — and the first downstream unit to multiply by it would have made this unit a scoring
authority by accident.

Compare with what units in Category 2 do, all of which *are* authorised to compose:

| Unit | Calculator shape | Why a composite is legitimate there |
|---|---|---|
| `core.opportunity` | `max(strengths) + Σ(rest)/4`, clamped | all plugins measure one quantity — opportunity strength — on one scale |
| `core.dependency` | `10,000 − worst − Σ(rest)/4 − depth×1,500` | all blockers measure one quantity — severity |
| `core.confidence` | weighted mean over four axes, divisor 100 | the capability *named* it the confidence authority |
| **`core.context`** | **union** | **three quantities, three scales, no authority** |

### 3.3 · The plugins are already independent, so a merge loses nothing

[03 · Analyzer](03-Analyzer.md) §3.1 establishes that no plugin reads another's output and no two
share a metric name or a config key. The Calculator therefore has nothing to reconcile. Any
arithmetic here would be *introducing* a relationship between three claims that were computed
without one — which is the definition of inventing information.

---

## 4 · How it works, statement by statement

| Statement | Effect | Load-bearing? |
|---|---|---|
| `sorted(observations, key=plugin_id)` | fixes the merge order | only if two plugins shared a name |
| `sorted(observation.metrics)` | fixes the dict insertion order of each block | **no** — see §4.2 |
| `int(observation.metrics[name])` | coercion to `int` | **no** — see §4.1 |
| `return metrics` | plain `dict`, handed to `evaluate_meaning` and copied into `Verdict.metrics` | yes |

### 4.1 · The `int()` is already guaranteed

`Observation.__post_init__` rejects any metric that is not an `int`, and rejects `bool` explicitly:

```python
for name, value in self.metrics.items():
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"observation metric {name} must be an integer")
```

So `int(...)` here is a no-op on every value that can reach it. It documents the contract at the
point of use and costs nothing. It would matter only if the framework's guarantee were relaxed —
and note that it would *not* save the unit from a float: `int(0.7)` is `0`, a silent truncation,
which is the same edge the framework carries in `Verdict` (see Part 2 §3.7).

### 4.2 · The inner sort has no observable effect

`sorted(observation.metrics)` controls the order keys are inserted into the `metrics` dict, and
therefore the Python iteration order of the result. It does not reach any artifact:
`platform/canonical.py:canonical_dumps` serialises with `sort_keys=True`, so
`ReasonerResult.semantic_hash` is invariant under key order. The inner sort is cosmetic — it makes a
`repr()` in a debugger read alphabetically.

### 4.3 · The outer sort is defensive against a collision that cannot occur

The docstring is precise about this: *"Metric names are disjoint across plugins **by
construction**; iteration is sorted by plugin id **anyway**."*

Twelve distinct names across three plugins. If a future plugin did reuse a name, the merge is
last-writer-wins in ascending `plugin_id` order — so `source_corroboration` would silently overwrite
`fact_coverage`, and `fact_coverage` would overwrite `evidence_freshness`. Deterministic, and
completely silent. Nothing raises; `publishes` would not catch it because the name is declared.

That is the one failure mode this stage has, and the sort converts it from *nondeterministic and
silent* to *deterministic and silent*. The deterministic version is strictly better and still not
good. A `if name in metrics: raise` would cost one line.

---

## 5 · Examples and edge cases

### 5.1 · The full combination

The README §6 run, showing the merge explicitly:

```text
observations, in plugin_id order

  evidence_freshness      freshness_bp             0
                          evidence_age_hours     288
                          dated_evidence_count     4

  fact_coverage           completeness_bp      8,000
                          declared_field_count     5
                          known_field_count        4
                          missing_field_count      1

  source_corroboration    corroboration_count      2
                          corroborated_field_count 1
                          single_sourced_field_count 3
                          evidenced_field_count    4
                          conflict_count           0

calculate → 12 keys, no key written twice, no value changed

  completeness_bp 8,000 · conflict_count 0 · corroborated_field_count 1
  · corroboration_count 2 · dated_evidence_count 4 · declared_field_count 5
  · evidence_age_hours 288 · evidenced_field_count 4 · freshness_bp 0
  · known_field_count 4 · missing_field_count 1 · single_sourced_field_count 3
```

Every published number appears verbatim in exactly one observation. That property is what makes the
trace auditable: a reviewer checking `completeness_bp = 8,000` reads the `context.fact_coverage`
finding and re-derives `divide_half_up(4 × 10_000, 5)` by hand. There is no step between the plugin
and the result where a number could have been adjusted.

### 5.2 · Partial observations

`test_undated_evidence_produces_no_freshness_claim_rather_than_a_zero`, where only
`source_corroboration` speaks:

```text
observations = [ context.source_corroboration ]

calculate → { corroboration_count: 1, corroborated_field_count: 0,
              single_sourced_field_count: 1, evidenced_field_count: 1, conflict_count: 0 }

"freshness_bp"     ∉ metrics
"completeness_bp"  ∉ metrics
```

The Calculator does not fill in the absent plugins' names with defaults, and this is the whole point
of the stage being a merge. A formula would have needed a value for the missing terms, and any value
it chose would have been a fabrication.

### 5.3 · No observations

```text
observations = ()
outer loop body never runs
calculate → {}
```

An empty mapping flows through `evaluate_meaning` (no threshold branch fires; the findings
comprehension is empty), through the `publishes` guard (`set({}) − set(publishes) = ∅`), and into
`build`, which produces `ReasonerResult(status=COMPLETED, metrics={}, findings=())`.

`test_an_empty_snapshot_completes_with_no_fabricated_readings` asserts exactly that.
**A completed result with zero metrics is a valid, meaningful output of this unit** and consumers
must handle it: it says *"the snapshot was empty and nothing declared what it should have
contained"*, which is different from `INSUFFICIENT_CONTEXT` (*"I was asked for something I did not
get"*) and different from `FAILED` (*"something broke"*).

### 5.4 · What `build` does to these numbers afterwards

```python
metrics={name: clamp_bp(value) if name.endswith("_bp") else value
         for name, value in verdict.metrics.items()}
```

Two of the twelve names end in `_bp`, and both were already clamped inside their plugins —
`completeness_bp` by construction (`present ⊆ declared`), `freshness_bp` by construction
(`min(age, horizon)`). So `build`'s clamp is the third defensive clamp on the same two values and
never binds. The other ten metrics are counts and pass through untouched, which is correct:
`evidence_age_hours = 288` must not be clamped to 10,000-anything, and it is not.

---

## Related

| File | Covers |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | Why the three inputs are independent, which is what licenses the merge |
| [05 · Evaluator](05-Evaluator.md) | Where the numbers finally acquire meaning, and why it is not here |
| [06 · Builder and Metrics](06-Builder-and-Metrics.md) | The `publishes` guard and the final clamp |
| [Part 2 · The Unit Framework](../../README.md) §4.5 | `core.opportunity`'s Calculator, for a unit that does compose |

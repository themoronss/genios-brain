# 04 · Calculator

**Stage 5 of the eight — `@abstractmethod`, every unit must implement it.**
**Source:** `genios_engine/reason/reasoners/priority.py:202` (`PriorityReasoner.calculate`)

---

## 1 · What it is for

The Calculator combines observations into the unit's metrics, in pure integer arithmetic. In
`core.risk` it is a weighted blend; in `core.opportunity` it is a leader-plus-lift formula; in
`core.confidence` it is a four-term weighted average with renormalisation.

In `core.priority` it **selects and bounds**. There is no blending and that is the point.

---

## 2 · The code, in full

```python
# priority.py:202
def calculate(self, view: UnitView,
              observations: Sequence[Observation]) -> Mapping[str, int]:
    metrics: dict[str, int] = {}
    for observation in observations:
        if "urgency_bp" in observation.metrics:
            metrics["urgency_bp"] = clamp_bp(observation.metrics["urgency_bp"])
    for observation in observations:
        if "priority_override_bp" in observation.metrics:
            metrics["priority_override_bp"] = clamp_bp(
                observation.metrics["priority_override_bp"])
    return metrics
```

Two passes over the same sequence. Nine lines. `view` is accepted and never read — the signature is
the framework's, not this unit's need.

```python
# reasoners/common.py:75
def clamp_bp(value: int) -> int:
    return min(10_000, max(0, int(value)))
```

---

## 3 · Why this shape — mining the docstring

The code's own docstring makes three arguments. They are the rationale; nothing below invents a new
one.

### 3.1 · *"There is no blending here on purpose"*

> *Exactly one urgency observation exists — the two urgency plugins are mutually exclusive — so this
> stage selects and bounds rather than combines.*

The loop is `metrics["urgency_bp"] = ...` on every match, so **last writer wins**. That is only
correct because at most one observation can ever carry `urgency_bp`. If both urgency plugins fired,
the survivor would be whichever sorts later — `maximum_urgency` — and the declared source's
authoritative reading would be silently discarded with no error and no reason code.

The invariant is not documented and hoped for; it is asserted.
`test_the_two_urgency_plugins_are_mutually_exclusive` runs both plugins against all 17 scenarios and
requires exactly one to fire, with the comment *"Exactly one urgency reading must exist, or
`calculate` would have to arbitrate."* Arbitration inside `calculate` would mean encoding a
preference — declared beats derived, or the higher number wins — and that preference would then live
in two places: here, and in the plugins' guard conditions. Two definitions of one rule is the exact
failure `_declared_source` was written to prevent.

### 3.2 · *"An absent override must stay absent rather than become a zero"*

> *…because a zero override is a live instruction to deprioritise and "no opinion" is not that.*

`priority_override_bp` is written into `metrics` **only** if an observation carries it. There is no
`metrics.setdefault("priority_override_bp", 0)` and no `else` branch. The key's absence propagates:

```mermaid
flowchart LR
    S["declared source<br/>published no priority_bp"]
    S --> P["override_priority<br/><small>returns empty tuple</small>"]
    P --> C["calculate<br/><small>second loop matches nothing</small>"]
    C --> V["Verdict.metrics<br/><small>key absent</small>"]
    V --> R["ReasonerResult.metrics<br/><small>key absent</small>"]
    R --> D["priority_metrics<br/><small>override stays None</small>"]
    D --> SC["score_candidate<br/><small>weighted formula runs</small>"]
```

Four modules carry one absent dictionary key without ever defaulting it. Break the chain anywhere —
a `.get(..., 0)`, a `dict.fromkeys`, a schema that fills missing integers with zero — and every
candidate in the capability scores `0`, because `score_candidate` returns the override verbatim.

`test_a_zero_override_is_published_and_an_absent_one_is_not` asserts both ends:
`zeroed.metrics["priority_override_bp"] == 0` and `"priority_override_bp" not in silent.metrics`.

### 3.3 · Two loops instead of one — why the split

The observations tuple is already in a deterministic order (`analyze` sorts by `plugin_id`), so one
loop with two `if`s would produce the same mapping. Splitting them makes the **insertion order** of
the output dictionary fixed: `urgency_bp` first, `priority_override_bp` second, regardless of which
plugin emitted what.

Whether that matters depends on the hash. `platform/canonical.py:semantic_hash` is what
`ReasonerResult.semantic_hash` is built from, and `contracts/reasoning.py:_mapping` freezes the
metrics mapping on the way in. Since the observation order is already fixed, the two-loop form is
belt-and-braces rather than load-bearing — but it costs nothing and it removes the question. The
legacy implementation built its output dict in the same order (`urgency_bp` assigned first, override
appended conditionally), so keeping the order identical was also the cheapest route to
hash parity.

---

## 4 · What `clamp_bp` actually protects against — and does not

`clamp_bp` maps any integer into 0–10,000. Both call sites here are **unreachable in a real run**,
and it is worth being precise about why.

The values arriving in `calculate` came from a prior unit's `ReasonerResult.metrics`.
`contracts/reasoning.py:616` validates every metric whose name ends in `_bp` at construction:

```python
for name, value in self.metrics.items():
    if name.endswith("_bp"):
        _bp(value, f"reasoner metrics.{name}")
```

```python
# contracts/reasoning.py:45
def _bp(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be integer basis points")
    if not 0 <= value <= 10_000:
        raise ValueError(f"{label} must be between 0 and 10000")
    return value
```

So `urgency_bp` and `priority_bp` are already integers in 0–10,000 before this unit ever sees them.
`clamp_bp` cannot clamp anything.

| Malformed input | Where it is actually caught | `clamp_bp`'s role |
|---|---|---|
| `urgency_bp = 25_000` on a prior | `_bp` at the prior's `ReasonerResult` construction — `ValueError` | none, never reached |
| `urgency_bp = "bad"` | `integer()` in the plugin — `ValueError` | none, plugin raised first |
| `urgency_bp = 9360.0` | `integer()` in the plugin — `ValueError` | none |
| `urgency_bp = True` | `_bp` `TypeError`, then `integer()` `ValueError`, then `Observation.__post_init__` `ValueError` | none |

The only way to reach `clamp_bp` with something to clamp is the `object.__setattr__` bypass the
tests use to construct results the contract forbids. It is defence against a construction path the
contract forecloses — kept because the frozen legacy implementation had it in the same place, and
removing it would have been a change with no upside and a hash-parity risk.

`unit.py:build` then clamps every `_bp` metric a **second** time:

```python
metrics={name: clamp_bp(value) if name.endswith("_bp") else value
         for name, value in verdict.metrics.items()}
```

Three clamps and one hard contract check on the same value. Redundant, harmless, and honest to
record.

---

## 5 · Worked combinations

### 5.1 · Declared path with an override — the two-observation case

**Input** (a legacy capability, `legacy.rule` scored 78 with `U = 64`):

```
observations = (
  Observation(plugin_id="declared_urgency",  kind="priority.declared_urgency",
              metrics={"urgency_bp": 6400}),
  Observation(plugin_id="override_priority", kind="priority.declared_override",
              metrics={"priority_override_bp": 7800}),
)
```

**Pass 1 — urgency:**

```
obs[0] "urgency_bp" in metrics          → metrics["urgency_bp"] = clamp_bp(6400) = 6,400
obs[1] "urgency_bp" not in metrics      → skipped
```

**Pass 2 — override:**

```
obs[0] "priority_override_bp" not in metrics    → skipped
obs[1] "priority_override_bp" in metrics        → metrics["priority_override_bp"] = clamp_bp(7800) = 7,800
```

**Output:**

```
{"urgency_bp": 6400, "priority_override_bp": 7800}
```

Both survive. They are different quantities: `6,400` says the clock matters moderately; `7,800` says
the rule corpus already ranked this at 78 out of 100. Downstream, the override wins the utility and
the urgency is discarded by `score_candidate`'s early return — but it is still published, and
`executive/interpret.py:354` reads the urgency component off the candidate for banding. See
[06](06-Builder-and-Metrics.md) §4.2.

### 5.2 · Declared path, no override — the shipped `sales.deal_cooling` case

**Input:**

```
observations = (
  Observation(plugin_id="declared_urgency", kind="priority.declared_urgency",
              metrics={"urgency_bp": 9360}),
)
```

**Pass 1:** `metrics["urgency_bp"] = clamp_bp(9360) = 9,360`
**Pass 2:** nothing matches — the loop runs once, the `if` is false, no key is written.

**Output:**

```
{"urgency_bp": 9360}
```

One key. `"priority_override_bp" not in metrics` — and it must stay that way through
`evaluate_meaning`, the `publishes` guard, `build`, the audit store, and `priority_metrics`.

### 5.3 · Derived path — the dropped diagnostic

**Input:**

```
observations = (
  Observation(plugin_id="maximum_urgency", kind="priority.maximum_urgency",
              metrics={"urgency_bp": 8400, "prior_reading_count": 3}),
)
```

**Pass 1:** `metrics["urgency_bp"] = clamp_bp(8400) = 8,400`
**Pass 2:** no match.

**Output:**

```
{"urgency_bp": 8400}
```

`prior_reading_count = 3` is **gone**. `calculate` tests for two specific key names and copies
nothing else, so any metric a plugin emits outside that pair evaporates here.

That is not an accident of this implementation — it is required. `unit.py:256` runs:

```python
undeclared = sorted(set(verdict.metrics) - set(self.publishes)) if self.publishes else []
if undeclared:
    raise ValueError(f"{self.unit_id} published undeclared metrics: {', '.join(undeclared)}")
```

with `publishes = ("urgency_bp", "priority_override_bp")`. Had `calculate` copied
`prior_reading_count` through, the run would have raised
`core.priority published undeclared metrics: prior_reading_count`.
`test_publishing_an_undeclared_metric_is_refused_by_the_framework` demonstrates the guard with a
subclass that leaks `confidence_bp`.

The cost is the audit gap in [06](06-Builder-and-Metrics.md) §4: nothing in the persisted result
records how many priors were consulted.

### 5.4 · Boundaries

| Observation metric | `clamp_bp` | Published |
|---|---|---|
| `urgency_bp = 0` | `min(10000, max(0, 0))` = `0` | `0` |
| `urgency_bp = 10_000` | `min(10000, max(0, 10000))` = `10,000` | `10,000` |
| `priority_override_bp = 0` | `0` | `0` — **published**, a live deprioritise instruction |
| no urgency observation at all | — | impossible; one urgency plugin always fires |

The last row is worth naming as an invariant rather than a case. If both urgency plugins somehow
stayed silent, `calculate` would return `{}`, `evaluate_meaning` would build a `Finding` with empty
metrics, the `publishes` guard would pass (an empty set has no undeclared members), and
`build` would emit a `COMPLETED` result with **no metrics at all**. `priority_metrics` would then
fall to its own default of `5,000` and `break` on the authority, so the decision would still get a
number — but the authority would have published nothing, and the audit row would show a completed
priority unit with an empty metrics map. Nothing in the unit or the framework catches that; the
mutual-exclusion test is the only thing standing between the code and that state.

---

## Related

- [03 · Analyzer](03-Analyzer.md) §3.3 — the mutual-exclusion invariant this stage depends on
- [03c · `override_priority`](03c-plugin-override_priority.md) §4.1 — the other end of the zero-versus-absent chain
- [05 · Evaluator](05-Evaluator.md) — what happens to this mapping next
- [06 · Builder and Metrics](06-Builder-and-Metrics.md) — the `publishes` guard and the audit gap

# 03a · Plugin `declared_urgency`

**Class:** `genios_engine/reason/reasoners/priority.py:82` — `DeclaredUrgencyPlugin`
**`plugin_id`:** `declared_urgency` · runs **first** (alphabetical)
**`Observation.kind`:** `priority.declared_urgency`
**Emits:** `urgency_bp` · **Reason code:** `urgency_from_declared_source`

---

## 1 · The claim it makes

> *This capability's author named a unit and said "that unit's reading of time pressure is what
> urgency means here". Here is that reading.*

It is the **authoritative** path. The class docstring:

> *A capability that names `core.temporal` as its source is asserting that time-decay is what urgency
> means for this situation, and that assertion outranks any louder number some other unit happened to
> publish.*

The judgement — *decay is what makes this situation urgent* — lives with the capability author in
Layer 3, in one config key, rather than being hardcoded into a shared unit that every capability
inherits. That is the whole design intent of the declared path.

---

## 2 · The code

```python
# priority.py:82
class DeclaredUrgencyPlugin:
    plugin_id = "declared_urgency"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        result = _declared_source(view)
        if result is None:
            return ()
        raw = result.metrics.get("urgency_bp", NEUTRAL_URGENCY_BP)
        return (Observation(
            plugin_id=self.plugin_id,
            kind="priority.declared_urgency",
            metrics={"urgency_bp": integer(raw, "urgency_bp")},
            reason_codes=("urgency_from_declared_source",),
        ),)
```

Nine lines. One branch, one dictionary read, one coercion.

### Dependencies

| Symbol | Defined at | What it does |
|---|---|---|
| `_declared_source(view)` | `priority.py:68` | `None` unless `config["source_reasoner"]` is truthy **and** names a key present in `view.prior` |
| `NEUTRAL_URGENCY_BP` | `priority.py:51` | `5_000` |
| `integer(value, label)` | `reasoners/common.py:30` | int / integral `Decimal` / integral numeric string → `int`; anything else raises `ValueError(f"{label} must be an integer")` |

---

## 3 · Config

| Key | Type | Default | Effect on this plugin |
|---|---|---|---|
| `source_reasoner` | `str` | `""` (falsy → absent) | Truthy **and** present in `prior` → this plugin fires. Anything else → silent. |

That is the only key. There is no threshold, no floor, no ceiling, no weight.

---

## 4 · When it stays silent

Exactly one condition: `_declared_source(view) is None`. That resolves to three distinct
situations, and the plugin cannot tell them apart:

| # | Situation | `_source_reasoner` | `view.prior.get(source)` | Silent? |
|---|---|---|---|---|
| 1 | No `source_reasoner` key in config | `""` → falsy | not reached | **yes** |
| 2 | `source_reasoner` is `""`, `None`, `0`, `False`, `[]` | `""` → falsy | not reached | **yes** |
| 3 | `source_reasoner` names a unit absent from `prior` | truthy | `None` | **yes** |
| 4 | `source_reasoner` names a unit present in `prior` | truthy | the result | no — fires |

Situation 3 covers both "the named unit is not in `spec.dependencies`" and "it is a declared
dependency but the orchestrator never scheduled it". It also covers a **typo**: a mistyped source id
resolves to `None`, this plugin stays silent, `maximum_urgency` picks up the slack, and nothing
anywhere reports that the capability's stated intent was ignored. That gap is noted in
[02 · Retriever](02-Retriever.md) §5.5.

**It does not stay silent when the source ran and published nothing.** A source present in `prior`
with an empty metrics map — because it was `SKIPPED`, `FAILED`, `INSUFFICIENT_CONTEXT`, or simply
`COMPLETED` without an urgency opinion — still fires the plugin, at `NEUTRAL_URGENCY_BP`. That is
situation 4 with a `.get` miss, and the distinction is deliberate:

- **Silent** means *the declared path does not apply* → `maximum_urgency` takes over.
- **Fires at 5,000** means *the declared path applies and the source had no opinion* → the derived
  maximum must **not** take over, because the capability said to believe this one unit.

`test_declared_urgency_falls_back_to_neutral_when_the_source_reported_none` pins it, with the
comment *"A source that ran but published no urgency is 'no opinion', not 'no pressure'."*

---

## 5 · The arithmetic

There is none. In full:

```
raw       = source_result.metrics.get("urgency_bp", 5_000)
urgency_bp = integer(raw, "urgency_bp")
```

No scaling, no weighting, no bounding. The value is a straight pass-through of another unit's
published integer. The bounding happens one stage later in `calculate` via `clamp_bp`, and is
unreachable in practice because the source's own `ReasonerResult` already validated `urgency_bp`
into 0–10,000 at construction (`contracts/reasoning.py:_bp`).

`integer` is the only transformation, and it is a **type** transformation, not a value one:

| `raw` | `integer(raw, "urgency_bp")` |
|---|---|
| `9360` | `9360` |
| `Decimal("6100")` | `6100` |
| `"7200"` | `7200` |
| `Decimal("6100.5")` | raises `ValueError` — not integral |
| `9360.0` (float) | raises `ValueError` — floats never accepted |
| `True` | raises `ValueError` — bool rejected before the int check |
| `"not a number"` | raises `ValueError` |
| `None` | raises `ValueError` |

The float rejection matters more than it looks. A float in the metrics map would make the decision
hash machine-dependent and destroy replay; refusing it is cheaper than silently rounding it.

---

## 6 · Worked examples

### 6.1 · `sales.deal_cooling`, the measured run — a real number end to end

**Setup.** `packs/capabilities/deal_cooling.py:208` declares
`config={"source_reasoner": "core.temporal"}` and
`dependencies=("core.temporal", "core.risk", "core.constraint")`.

**Upstream.** The snapshot carries `derived.engagement = 4,000bp` and a `thread.last_inbound` ten
days before `evaluation_time`. `temporal.py:47`:

```
engagement_bp = 4,000
drop_bp       = clamp_bp(10,000 − 4,000)                  = 6,000
elapsed_hours = 10 days × 24                              = 240
urgency_bp    = clamp_bp(6,000 + min(240, 168) × 20)
              = clamp_bp(6,000 + 168 × 20)
              = clamp_bp(6,000 + 3,360)                   = 9,360
```

The `min(hours, 168)` caps the elapsed-time term at one week; 240 hours and 168 hours produce the
same urgency.

**This plugin.**

```
_source_reasoner(view)   = "core.temporal"                     (truthy)
view.prior["core.temporal"] exists                             → result is not None
raw = result.metrics.get("urgency_bp", 5_000)                  = 9,360
integer(9360, "urgency_bp")                                    = 9,360
```

```
Observation(plugin_id="declared_urgency",
            kind="priority.declared_urgency",
            metrics={"urgency_bp": 9360},
            evidence_ids=(),
            reason_codes=("urgency_from_declared_source",))
```

`core.risk` also sits in `prior` with `risk_bp = 5,934` and no `urgency_bp`. On the derived path it
would have contributed a `0` reading; here it is not read at all.

### 6.2 · A legacy capability — declared source that also rules

**Setup.** `reason/adapters/legacy_pack.py:78` declares
`config={"source_reasoner": "legacy.rule"}` and `dependencies=("legacy.rule", "core.constraint")`.

**Upstream.** `legacy.rule` matched, and `engine.py:score_rule` returned `score = 78` with
`inputs = {"C": 62, "U": 64, "I": 81, "R": 44, "terms_bp": 7100}`. `legacy_rule.py:49`:

```
priority_bp   = 78 × 100  = 7,800
confidence_bp = 62 × 100  = 6,200
urgency_bp    = 64 × 100  = 6,400
impact_bp     = 81 × 100  = 8,100
```

**This plugin.**

```
raw = 6,400  →  Observation(metrics={"urgency_bp": 6400}, kind="priority.declared_urgency")
```

`7,800` is *not* this plugin's business — it is picked up by
[`override_priority`](03c-plugin-override_priority.md) in the same run. Two observations leave the
Analyzer, and the published urgency is `6,400`, not `7,800`. They measure different things: how much
the clock matters, versus what the rule already decided the priority is.

### 6.3 · Source ran and had no opinion — the neutral fallback

```
config = {"source_reasoner": "core.temporal"}
prior  = {"core.temporal": COMPLETED, metrics={"drop_bp": 3000}}
```

```
result is not None                                 → the plugin fires
raw = metrics.get("urgency_bp", NEUTRAL_URGENCY_BP) = 5,000    # .get missed
integer(5000, "urgency_bp")                         = 5,000
```

Published `urgency_bp = 5,000`. Contrast with what would happen if the plugin had stayed silent:
`maximum_urgency` would fire and build `readings` by calling `metrics.get("urgency_bp", 0)` on the
same result — which misses, because `core.temporal` published `drop_bp` and no `urgency_bp` — giving
`readings = [0]` and a published `max([0]) = 0`. The declared
path's `5,000` and the derived path's `0` differ by half the scale, on the same inputs. That is the
whole reason the branch is exclusive rather than a fallback chain.

Pinned by `test_declared_urgency_falls_back_to_neutral_when_the_source_reported_none`.

### 6.4 · Source skipped

```
config = {"source_reasoner": "core.temporal"}
prior  = {"core.temporal": SKIPPED, metrics={} (forced by the contract),
          "core.risk":     COMPLETED, metrics={"urgency_bp": 9900}}
```

`_declared_source` does **not** check status. `view.prior.get("core.temporal")` returns the SKIPPED
result, which is not `None`, so:

```
raw = {}.get("urgency_bp", 5_000) = 5,000
```

Published `urgency_bp = 5,000` — **not** `core.risk`'s 9,900. The capability named `core.temporal`;
`core.temporal` had nothing to say; the loud reading next door does not get promoted just because
its neighbour went quiet. `_declared_source`'s docstring argues the mechanism: the contract at
`contracts/reasoning.py:629` already forbids a non-`COMPLETED` result from carrying metrics, so the
skipped source *reads as* an empty metric map and reaches the neutral midpoint through the same code
path as a source that completed without an opinion. *"Re-checking status here would be a second,
divergent definition of the same rule."*

Scenario `"shipped deal_cooling config, source skipped"` in `_scenarios()` pins the whole-unit
result, and `test_migrated_unit_is_hash_identical_to_the_frozen_legacy_implementation` asserts the
`semantic_hash` matches the pre-migration implementation for it.

### 6.5 · Source absent from `prior` — silent

```
config = {"source_reasoner": "core.temporal"}
prior  = {"core.risk": COMPLETED, metrics={"urgency_bp": 9900}}
```

`view.prior.get("core.temporal")` → `None`. This plugin returns `()`.
`maximum_urgency` then fires and publishes `9,900`. The difference from §6.4 is one dictionary key:
a source that ran and said nothing gives `5,000`; a source that never appeared at all gives the
derived maximum. `test_declared_urgency_stays_silent_when_the_named_source_did_not_run` pins the
silence.

### 6.6 · Boundaries

| Source's `urgency_bp` | Published | Note |
|---|---|---|
| `0` | `0` | A genuine "no time pressure" reading. Not confused with the 5,000 fallback. |
| `10_000` | `10,000` | The scale ceiling. `clamp_bp` in `calculate` is a no-op. |
| absent | `5,000` | `NEUTRAL_URGENCY_BP` |

Scenarios `"boundary: zero urgency from the declared source"` and
`"boundary: maximal urgency and override"` cover both ends and both are in the differential
hash-parity parametrisation.

---

## Related

- [03 · Analyzer](03-Analyzer.md) — how this plugin composes with the other two
- [03b · `maximum_urgency`](03b-plugin-maximum_urgency.md) — the branch this one excludes
- [03c · `override_priority`](03c-plugin-override_priority.md) — the plugin that fires alongside this one
- [04 · Calculator](04-Calculator.md) — what happens to the emitted `urgency_bp`

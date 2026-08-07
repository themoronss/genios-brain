# 03c · Plugin `override_priority`

**Class:** `genios_engine/reason/reasoners/priority.py:136` — `DeclaredOverridePlugin`
**`plugin_id`:** `override_priority` · runs **third** (alphabetical)
**`Observation.kind`:** `priority.declared_override`
**Emits:** `priority_override_bp` · **Reason code:** `priority_override_declared`

---

## 1 · The claim it makes

> *The unit this capability named did not merely measure pressure — it already resolved it into a
> priority. Carry that judgement through intact.*

From the class docstring:

> *Some sources do not merely measure pressure, they have already resolved it into a priority — a
> rule corpus that fired, a gate that ranked. When the declared source publishes `priority_bp`, that
> reading travels intact to the Decision Maker as `priority_override_bp` instead of being re-derived
> from urgency, which would lose the source's judgement.*
>
> *Only the declared path can produce an override. The derived maximum is an aggregation across
> units with no single author, so there is nobody whose override it would be.*

This is the single most powerful thing any unit in Layer 4 can emit. `decision_maker.py:240`:

```python
if priority_override is not None:
    return priority_override
```

`score_candidate` returns it verbatim and **never evaluates the weighted formula**. Impact, success
probability, urgency, effort and risk are all discarded. One integer decides the candidate's utility.

### The name changes across the boundary

The plugin reads `priority_bp` and publishes `priority_override_bp`. That asymmetry is recorded as a
latent bug in `Rohit_Updates/Layer 4.md` Part 4 and preserved by the byte-identical migration
contract. The evidence that it is deliberate rather than a typo is in
[06 · Builder and Metrics](06-Builder-and-Metrics.md) §5: the two names sit at opposite ends of a
round trip that recovers the legacy 0–100 score exactly. The code itself says nothing either way,
and that is the real defect — the intent is provable from three other files and stated in none.

---

## 2 · The code

```python
# priority.py:136
class DeclaredOverridePlugin:
    plugin_id = "override_priority"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        result = _declared_source(view)
        if result is None:
            return ()
        raw = result.metrics.get("priority_bp")
        if raw is None:
            return ()                       # the source measured pressure but did not rule on it
        return (Observation(
            plugin_id=self.plugin_id,
            kind="priority.declared_override",
            metrics={"priority_override_bp": integer(raw, "priority_override_bp")},
            reason_codes=("priority_override_declared",),
        ),)
```

Two guards, one coercion. Note the `.get("priority_bp")` has **no default** — unlike
`declared_urgency`'s `.get("urgency_bp", NEUTRAL_URGENCY_BP)`. That difference is the whole
silence semantics of this plugin, and §4 is about it.

---

## 3 · Config

| Key | Type | Default | Effect |
|---|---|---|---|
| `source_reasoner` | `str` | `""` | Truthy **and** present in `prior` → this plugin *may* fire, subject to the source having published `priority_bp` |

No other key. In particular there is no way for a capability to *disable* the override, or to cap it,
or to require it. If the declared source publishes `priority_bp`, the override happens and the
weighted formula is bypassed for every play in the capability. The only lever is which unit is named
as the source.

---

## 4 · When it stays silent

Two independent conditions, and the distinction between them matters less than the distinction
between *silent* and *zero*.

| # | Condition | Code | Meaning |
|---|---|---|---|
| 1 | No declared source — none named, or named and absent from `prior` | `result is None` → `()` | The derived path is in play. An aggregate has no author, so there is nobody whose override it would be. |
| 2 | Declared source present, but published no `priority_bp` | `raw is None` → `()` | The source measured pressure but did not rule on it. |

Condition 2 is the shipped case for **two of the three** capabilities:

| Source | Publishes `priority_bp`? | Where |
|---|---|---|
| `core.temporal` | no — publishes `engagement_bp`, `drop_bp`, `elapsed_hours`, `urgency_bp` | `temporal.py:66` |
| `core.signal_composition` | no — publishes `member_count`, `distinct_reason_count`, `signal_score_bp`, `confidence_bp`, `urgency_bp` | `signal_composition.py:65` |
| `legacy.rule` | **yes** — `priority_bp = score * 100` | `legacy_rule.py:49` |

So `sales.deal_cooling` and `sales.deal_health` never light this plugin. Every legacy-compiled
capability does. `runner.py:449` builds one such capability per rule in the pack, so the override
path carries the entire legacy rule corpus in production.

### 4.1 · Silent is not zero, and the code proves it cares

```python
raw = result.metrics.get("priority_bp")
if raw is None:
    return ()
```

If this had been `.get("priority_bp", 0)`, a source that never ruled would publish
`priority_override_bp = 0` — and `score_candidate` would return `0` for every play in the
capability, burying the entire candidate field at the bottom of the ranking with no reason code
anywhere explaining why. `test_a_zero_override_is_published_and_an_absent_one_is_not` pins both
halves:

> *Zero is an instruction to deprioritise; absence is silence. Collapsing them would let a source
> that never ruled quietly bury a candidate.*

```python
zeroed.metrics["priority_override_bp"] == 0
"priority_override_bp" not in silent.metrics
```

The same distinction is re-enforced one stage later in `calculate` — see
[04 · Calculator](04-Calculator.md) §3 — and once more in `decision_maker.py:priority_metrics`,
which initialises `override = None` and only assigns when `"priority_override_bp" in result.metrics`.
Three layers, one rule, no default values anywhere along the chain.

---

## 5 · The arithmetic

```
raw                 = source_result.metrics.get("priority_bp")     # no default
priority_override_bp = integer(raw, "priority_override_bp")
```

A pass-through, exactly like `declared_urgency`. The label passed to `integer` is
`"priority_override_bp"` — the *published* name, not the read name — so a malformed reading raises
`ValueError("priority_override_bp must be an integer")`. An operator reading that message and
grepping for `priority_override_bp` in the source reasoner will find nothing, because the source
publishes `priority_bp`. That is a small, real diagnostic trap created by the same name asymmetry.

Bounds are applied later by `clamp_bp` in `calculate`, and are unreachable in practice: the source's
own `ReasonerResult` already validated `priority_bp` into 0–10,000 at construction, because
`contracts/reasoning.py:616` runs `_bp` over every metric whose name ends in `_bp`.

---

## 6 · Worked examples

### 6.1 · A legacy capability — the live production case

**Setup.** `runner.py:449` compiles rule `deal_gone_quiet` into capability
`legacy.sales_pack.deal_gone_quiet`. `legacy_pack.py:78` gives `core.priority`
`config={"source_reasoner": "legacy.rule"}` and `dependencies=("legacy.rule", "core.constraint")`.

**Upstream.** `legacy.rule` matched. `engine.py:score_rule` returned `score = 78`.
`legacy_rule.py:49`:

```
priority_bp = score × 100 = 78 × 100 = 7,800
urgency_bp  = U     × 100 = 64 × 100 = 6,400
```

**This plugin.**

```
_declared_source(view)                      → the legacy.rule result
raw = result.metrics.get("priority_bp")     = 7,800          (not None)
integer(7800, "priority_override_bp")       = 7,800
```

```
Observation(plugin_id="override_priority",
            kind="priority.declared_override",
            metrics={"priority_override_bp": 7800},
            evidence_ids=(),
            reason_codes=("priority_override_declared",))
```

**Downstream, in full.** The legacy capability declares exactly one play
(`legacy_pack.py:131` — `plays=(play,)`), which takes every `PlayDefinition` scoring default:
`impact_bp = 5,000`, `success_probability_bp = 5,000`, `effort_bp = 5,000`, `risk_bp = 5,000`.

Without the override, `score_candidate` would compute:

```
weighted = 5,000×35 + 5,000×30 + 6,400×20 + (10,000−5,000)×10 + (10,000−5,000)×5
         = 175,000 + 150,000 + 128,000 + 50,000 + 25,000
         = 528,000
utility  = divide_half_up(528,000, 100) = (528,000 + 50) // 100 = 5,280bp
```

With the override, `score_candidate` returns at line 241 before any of that runs:

```
utility_bp = 7,800
```

The legacy score survives the trip. `authority.py:AUTHORITATIVE_SCORE_SQL` then projects it back:

```
(final_utility_bp + 50) / 100 = (7,800 + 50) / 100 = 7,850 / 100 = 78        (integer division)
```

**78 in, 78 out.** That exact round trip is what the strangler capability exists to preserve, and it
only holds because the override bypasses the weighted formula. Without it the projected score would
have been `(5,280 + 50) // 100 = 53`, and every legacy signal in the product would have shifted.

### 6.2 · `sales.deal_cooling` — declared source, no ruling

```
config = {"source_reasoner": "core.temporal"}
prior  = {"core.temporal": COMPLETED metrics={"engagement_bp": 4000, "drop_bp": 6000,
                                              "elapsed_hours": 240, "urgency_bp": 9360}}
```

```
_declared_source(view)                   → the core.temporal result (not None)
raw = metrics.get("priority_bp")         → None
→ return ()
```

Silent. The result carries `urgency_bp = 9,360` and **no** `priority_override_bp` key at all.
`decision_maker.py:priority_metrics` returns `override = None`, and `score_candidate` runs the
weighted formula. That is the measured run in the category README, and the reason it says
*"the override path stayed inert"*.

Pinned by `test_override_is_absent_when_the_source_did_not_rule`.

### 6.3 · The derived path never overrides

```
config = {}                                        # no source declared
prior  = {"core.temporal": COMPLETED metrics={"priority_bp": 7250}}
```

`_declared_source` returns `None` because `_source_reasoner` is `""`. This plugin returns `()`
**even though a prior unit published `priority_bp` right there in the mapping.**

```
assert DeclaredOverridePlugin().contribute(view) == ()
```

`test_override_never_comes_from_the_derived_path`, with the comment *"An aggregate across units has
no author, so there is nobody whose override it could be."*

This is the unit's half of an agreement with the Decision Maker. `priority_metrics` reads
`priority_override_bp` **only from the authority** — `urgency_bp` it will take from anyone up to and
including the authority, but an override is narrowed to one named unit *"so a unit cannot seize
ranking control by emitting the metric opportunistically."* If this plugin fired on the derived
path, an override would enter the system from an unattributable source and the Decision Maker's
narrowing would be defeated from inside the very unit it trusts.

### 6.4 · Zero versus absent — the two results side by side

```
A: prior = {"core.temporal": COMPLETED metrics={"urgency_bp": 9000, "priority_bp": 0}}
B: prior = {"core.temporal": COMPLETED metrics={"urgency_bp": 9000}}
```

| | A | B |
|---|---|---|
| plugin fires | yes — `raw = 0`, which is not `None` | no — `raw is None` |
| result metrics | `{"urgency_bp": 9000, "priority_override_bp": 0}` | `{"urgency_bp": 9000}` |
| `priority_metrics` override | `0` | `None` |
| `score_candidate` | returns `0` for **every** play | runs the weighted formula |

In A, a candidate with `impact_bp = 8,000` and `success_probability_bp = 5,500` scores `0`. That is
correct and intended: the source ruled, and its ruling was *deprioritise this*. In B the same
candidate scores on its merits. The two situations differ by one absent dictionary key, and the code
carries that key's absence intact through three modules to preserve the difference.

`test_a_zero_override_is_published_and_an_absent_one_is_not` asserts exactly this pair.

### 6.5 · Boundaries

| Source's `priority_bp` | `priority_override_bp` | Every candidate's `utility_bp` |
|---|---|---|
| `0` | `0` | `0` — all plays bottom out, ranking falls to the `play_id` tie-break |
| `10_000` | `10,000` | `10,000` — all plays max out, same tie-break |
| absent | *not published* | weighted formula |

Both boundary rows are covered by `_scenarios()` entries `"boundary: zero urgency from the declared
source"` and `"boundary: maximal urgency and override"`, and both are in the hash-parity
parametrisation.

The tie-break consequence is worth stating. `decision_maker.py:rank_candidates` sorts eligible
candidates by `(-utility_bp, play.play_id)`. When an override sets every candidate to the same
number — which it always does, since `score_candidate` returns the override regardless of components
— the ranking is decided entirely alphabetically by `play_id`. For the legacy capabilities that is
harmless, because each declares exactly one play. For a multi-play capability naming a
`priority_bp`-publishing source, the winner would be the alphabetically first play, and nothing in
the trace would say so. No shipped capability is in that position.

---

## Related

- [03 · Analyzer](03-Analyzer.md) — why this plugin runs last and what that buys
- [03a · `declared_urgency`](03a-plugin-declared_urgency.md) — the plugin that always fires alongside this one
- [04 · Calculator](04-Calculator.md) — how the absence is preserved
- [06 · Builder and Metrics](06-Builder-and-Metrics.md) §5 — the round trip that argues the name asymmetry is deliberate

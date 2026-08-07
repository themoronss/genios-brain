# 03a · Plugin `momentum_decay`

**Class:** `risk.py:MomentumDecayPlugin` · **`plugin_id`** `"momentum_decay"` ·
**Observation kind** `"risk.momentum_decay"` · **executed first** of three.

---

## 1 · The claim it makes

*The conversation has fallen off, and here is how far.*

It carries **weight 60 of 100** in the blend — the larger of the two, because *"a deal that has
stopped moving is the nearer loss; thin coverage is the slower one."*

The plugin makes that claim by **reading, not re-deriving**. `core.temporal` parsed the timestamps
and owns `drop_bp`. Recomputing it here from the same facts would produce a second number that
agrees today and diverges the first time either side is tuned. That is the whole design of this
plugin, and it is nine lines long as a result.

---

## 2 · What exists

```python
# risk.py:MomentumDecayPlugin
plugin_id = MOMENTUM_PLUGIN                      # "momentum_decay"

def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    source = str(view.config.get("temporal_reasoner") or "core.temporal")
    return (Observation(
        plugin_id=self.plugin_id,
        kind="risk.momentum_decay",
        metrics={"drop_bp": _published(view, source, "drop_bp")},
        reason_codes=("momentum_decay_exposure",),
    ),)
```

| | |
|---|---|
| Config keys | `temporal_reasoner` — string, default `"core.temporal"` |
| Reads | `view.prior[source].metrics["drop_bp"]` |
| Emits | exactly one `Observation`, always |
| Metric | `drop_bp`, integer basis points 0–10,000 |
| Reason code | `momentum_decay_exposure` — provenance only, never reaches the result |
| Evidence ids | `()` — the metric it reads is already evidenced by `core.temporal` |

### 2.1 · Where `drop_bp` comes from

`temporal.py:TemporalReasoner.evaluate`, one line:

```python
drop_bp = clamp_bp(10_000 - engagement_bp)
```

`engagement_bp` is `common.py:ratio_bp` over the `derived.engagement` fact — which accepts either a
ratio in `0..1` or explicit basis points, and reads `value_bp` from the record when present. So
`drop_bp` is the complement of engagement: **10,000bp of drop means the conversation is entirely
cold.**

---

## 3 · When it stays silent

**Never.** This plugin has no silence path. It returns a one-tuple on every call, and when the
dependency is missing the metric it carries is `0`.

That is the deliberate Law 3 exception this unit is known for, and `risk.py:_published` is where it
is implemented:

```python
result = view.prior.get(reasoner_id)
return integer((result.metrics if result else {}).get(name, 0), name)
```

Three distinct situations collapse to the same `drop_bp: 0`:

| Situation | What `_published` sees | Emitted |
|---|---|---|
| `core.temporal` ran and reported perfect engagement | `{"drop_bp": 0, ...}` | `0` |
| `core.temporal` ran but published no `drop_bp` | `.get` default | `0` |
| `core.temporal` was `SKIPPED` / `INSUFFICIENT_CONTEXT` / `FAILED` | `metrics == {}` — the contract forbids a non-`COMPLETED` result from carrying any | `0` |
| `core.temporal` is not in `view.prior` at all | `result is None` → `{}` | `0` |

`test_a_dependency_that_did_not_run_contributes_zero_not_silence` pins the last row explicitly, with
the reason stated in its own docstring: *"a missing `risk_bp` reads downstream as 'unknown' rather
than 'low'"*.

**Nothing in the result records which of the four happened.** No reason code, no
`missing_fields` entry, no telemetry. A reviewer looking at `risk_bp = 1,000` cannot tell a healthy
deal from a broken dependency.

---

## 4 · The arithmetic and worked examples

The plugin performs no arithmetic of its own. Its whole contribution is one integer, which
[04 · Calculator](04-Calculator.md) multiplies by 60. What follows shows the contribution end to end
so the weight is visible.

```
contribution to the weighted term = drop_bp × 60 / 100   (integrated, not rounded separately)
```

### 4.1 · The shipped deal — a cooling conversation

`derived.engagement` = 0.38, `thread.last_inbound` ten days ago, `base_risk_bp` = 1,000, no
relationship signal.

```text
core.temporal:  engagement_bp = ratio_bp(0.38)      = 3,800
                drop_bp       = 10,000 − 3,800      = 6,200

momentum_decay: Observation(metrics={"drop_bp": 6200},
                            reason_codes=("momentum_decay_exposure",))

core.risk:      numerator = 6,200 × 60 + 0 × 40     = 372,000
                weighted  = round_half_up(372,000 / 100) = 3,720
                risk_bp   = clamp(1,000 + 3,720)    = 4,720
```

The momentum axis alone moved risk from the 1,000bp floor to 4,720bp — 3,720bp of the 10,000bp
scale, which is 60% of the 6,200bp exposure, exactly as the weight says.

Pinned in spirit by `CASES["temporal_only"]`, which drives the same shape through the differential
against the pre-migration implementation.

### 4.2 · The redirected model

A capability running its own decay model under a different id:

```python
config = {"temporal_reasoner": "sales.decay"}
prior  = {"sales.decay": ReasonerResult(..., metrics={"drop_bp": 4_400})}
```

```text
source = "sales.decay"
_published → 4,400

numerator = 4,400 × 60 = 264,000
weighted  = 2,640
risk_bp   = 1,000 + 2,640 = 3,640
```

Pinned by `test_momentum_decay_follows_the_authored_dependency_id`. The redirect exists so a
domain-specific decay model can be weighted here without forking the risk unit.

### 4.3 · The gating floor in `sales.deal_cooling`

Worth knowing because it narrows the real input range far below `0..10,000`.
`packs/capabilities/deal_cooling.py` declares `core.temporal` with `gating=True` and
`max_engagement_bp = 5_000`, and `temporal.py` sets `matched = engagement_bp <= maximum`. The
orchestrator ends the run with `DecisionOutcome.NO_ACTION` when a gating unit reports
`matched is False`, and every later step — including `core.risk` — is recorded as `SKIPPED`.

So **in a run that actually reaches `core.risk`, `drop_bp` is always ≥ 5,000**:

| `derived.engagement` | `engagement_bp` | `matched` | `drop_bp` | Reaches `core.risk`? | Momentum term |
|---|---|---|---|---|---|
| 0.20 | 2,000 | true | 8,000 | yes | 4,800 |
| 0.38 | 3,800 | true | 6,200 | yes | 3,720 |
| 0.50 | 5,000 | true | 5,000 | yes | 3,000 |
| 0.51 | 5,100 | **false** | 4,900 | **no — NO_ACTION** | — |
| 0.90 | 9,000 | false | 1,000 | no | — |

The momentum axis therefore contributes between **3,000bp and 6,000bp** in every live
`deal_cooling` run. The `drop_bp = 0` path exists in the code and is exercised by the tests, but in
this capability it only occurs when the dependency failed — never when the deal is healthy, because
a healthy deal never gets this far.

### 4.4 · The trap: a redirect without a declared dependency

```python
config       = {"temporal_reasoner": "sales.decay"}
dependencies = ("core.temporal",)                 # the author forgot to update this
```

`sales.decay` runs, completes, publishes `drop_bp = 9,000`. The orchestrator builds
`dependencies = {item: prior[item] for item in spec.dependencies if item in prior}`, which yields
`{"core.temporal": ...}` — `sales.decay` is not in it. Then:

```text
source     = "sales.decay"
view.prior = {"core.temporal": <result>}
_published → view.prior.get("sales.decay") is None → {} → 0

risk_bp = 1,000 + round_half_up((0 × 60 + rel × 40) / 100)
```

Sixty percent of the risk model switched off. The plan is valid, the run is deterministic, the
result is `COMPLETED`, and nothing anywhere reports a problem. This is the same failure mode
`core.impact` is already living with in `deal_cooling_full_v2`, documented in
[Category 2 §3.5](../README.md). Two config keys — `temporal_reasoner` and
`ReasonerSpec.dependencies` — encode the same intent and nothing checks that they agree.

### 4.5 · Boundary values

| `drop_bp` | Weighted contribution | Note |
|---|---|---|
| 0 | 0 | absent, failed, or a perfectly warm deal — indistinguishable |
| 1 | 0.6 → contributes 60 to the numerator | never rounded on its own; see [04](04-Calculator.md) |
| 5,000 | 3,000 | the lowest value a live `deal_cooling` run can present |
| 10,000 | 6,000 | fully cold; with `base_risk_bp = 1,000` gives `risk_bp = 7,000` alone |

A `drop_bp` outside `0..10_000` cannot arrive: `ReasonerResult.__post_init__` validates every
`_bp`-suffixed metric with `contracts/reasoning.py:_bp`, which enforces the range at the point the
upstream result was constructed.

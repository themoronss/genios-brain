# 03b · Plugin `relationship_health`

**Class:** `risk.py:RelationshipHealthPlugin` · **`plugin_id`** `"relationship_health"` ·
**Observation kind** `"risk.relationship_health"` · **executed second** of three.

---

## 1 · The claim it makes

*The account is thinly held, and here is how thinly.*

It carries **weight 40 of 100** — the smaller of the two, because thin coverage is the slower loss.

The docstring states why it is a separate term rather than a modifier on decay:

> *A single-threaded deal is one departure away from starting over, and that exposure is independent
> of how recently anyone spoke — which is exactly why it is a separate contribution with its own
> weight rather than a modifier on decay.*

That independence is the reason the blend is additive. A deal can be warm and single-threaded, or
cold and well-covered, and the two failure modes have nothing to do with each other. Multiplying
them would let a warm conversation cancel a structural exposure that a warm conversation does not
touch.

---

## 2 · What exists

```python
# risk.py:RelationshipHealthPlugin
plugin_id = RELATIONSHIP_PLUGIN                  # "relationship_health"

def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    source = str(view.config.get("relationship_reasoner") or "core.relationship")
    return (Observation(
        plugin_id=self.plugin_id,
        kind="risk.relationship_health",
        metrics={"relationship_risk_bp": _published(view, source, "relationship_risk_bp")},
        reason_codes=("relationship_exposure",),
    ),)
```

Structurally identical to [`momentum_decay`](03a-plugin-momentum_decay.md) — same `_published`
reader, same never-silent shape, different config key, different metric name, different weight.

| | |
|---|---|
| Config keys | `relationship_reasoner` — string, default `"core.relationship"` |
| Reads | `view.prior[source].metrics["relationship_risk_bp"]` |
| Emits | exactly one `Observation`, always |
| Metric | `relationship_risk_bp`, integer basis points 0–10,000 |
| Reason code | `relationship_exposure` — provenance only, never reaches the result |
| Evidence ids | `()` |

### 2.1 · Where `relationship_risk_bp` comes from

`relationship.py:RelationshipReasoner.evaluate`, two lines:

```python
coverage_bp = clamp_bp(relationship_count * 10_000 // target)
concentration_risk_bp = 10_000 - coverage_bp
```

`relationship_count` is the `relationship.verified_stakeholder_count` fact — **verified**
stakeholders, not contacts in an address book. `target` is
`max(1, config["target_relationships"])`, which `sales.deal_cooling` sets to `3`. The floor division
truncates, and the complement is therefore also truncated upward.

The whole domain, for `target = 3`:

| Verified stakeholders | `coverage_bp` | `relationship_risk_bp` | Business reading |
|---|---|---|---|
| 0 | 0 | **10,000** | nobody verified at all |
| 1 | 3,333 | **6,667** | single-threaded — one departure from starting over |
| 2 | 6,666 | **3,334** | a second path exists |
| 3 | 10,000 | **0** | the authored target met |
| 4+ | 10,000 (clamped) | **0** | no credit beyond the target |

Four values, not a continuum. Everything this plugin can ever contribute in `sales.deal_cooling` is
one of `{10,000 · 6,667 · 3,334 · 0}`, and the weighted term is one of
`{4,000 · 2,667 (from 266,680/100) · 1,334 (133,360/100) · 0}` before it is summed with momentum.

When no `relationship_count_field` is configured, `relationship.py` falls back to
`request.context.edge_count` — the raw neighbourhood size — which is a materially weaker signal than
a verified stakeholder count. `sales.deal_cooling` configures the field, so that path is not taken.

---

## 3 · When it stays silent

**Never**, for exactly the reasons set out in [03a §3](03a-plugin-momentum_decay.md). The same
`_published` helper collapses four situations to `relationship_risk_bp: 0`:

| Situation | Emitted |
|---|---|
| `core.relationship` completed with three or more verified stakeholders | `0` |
| `core.relationship` completed but published no `relationship_risk_bp` | `0` |
| `core.relationship` returned `INSUFFICIENT_CONTEXT` | `0` |
| `core.relationship` is not in `view.prior` | `0` |

**This one is worse than the momentum case, because here `0` is also a legitimate healthy reading.**
`drop_bp = 0` means "perfectly warm", which the gating rule in `deal_cooling` makes unreachable at
this point in the run. `relationship_risk_bp = 0` means "three verified stakeholders", which is both
reachable and desirable. So a run where `core.relationship` could not measure coverage produces a
result numerically indistinguishable from a well-covered account — and the unit reports the account
as carrying no structural risk on the strength of a measurement that never happened.

`test_a_dependency_that_did_not_run_contributes_zero_not_silence` pins the behaviour for both
plugins together.

---

## 4 · The arithmetic and worked examples

```
contribution to the weighted term = relationship_risk_bp × 40 / 100
```

### 4.1 · A single-threaded open deal

`relationship.verified_stakeholder_count = 1`, `deal.status = "open"`, `target_relationships = 3`,
no temporal signal, default floor.

```text
core.relationship: coverage_bp           = 1 × 10,000 // 3       = 3,333
                   relationship_risk_bp  = 10,000 − 3,333        = 6,667

relationship_health: Observation(metrics={"relationship_risk_bp": 6667},
                                 reason_codes=("relationship_exposure",))

core.risk:  numerator = 0 × 60 + 6,667 × 40  = 266,680
            weighted  = round_half_up(266,680 / 100) = 2,667      (266,680/100 = 2,666.8)
            risk_bp   = clamp(1,000 + 2,667)          = 3,667
```

Note the rounding: `2,666.8` rounds **up** to `2,667`. That is `common.py:divide_half_up`'s
`(numerator + denominator // 2) // denominator` — `(266,680 + 50) // 100 = 2,667`.

### 4.2 · The shipped composite

Both dependencies present, the numbers from `CASES["shipped_deal_cooling_config"]`:

```text
drop_bp              = 6,000        (engagement 0.40)
relationship_risk_bp = 6,667        (one verified stakeholder)
base_risk_bp         = 1,000

numerator = 6,000 × 60 + 6,667 × 40
          = 360,000   + 266,680
          = 626,680
weighted  = round_half_up(626,680 / 100)      = 6,267        (6,266.8 → 6,267)
risk_bp   = clamp(1,000 + 6,267)              = 7,267
```

Of the 6,267bp of measured exposure, momentum supplied 3,600 and coverage supplied 2,667. The floor
adds the last 1,000. Reported as `risk_bp = 7,267` — meaning **0.7267**.

### 4.3 · Maximum coverage exposure with a fully cold deal

`relationship.verified_stakeholder_count = 0`, `derived.engagement = 0.10`.

```text
drop_bp              = 10,000 − 1,000 = 9,000
relationship_risk_bp = 10,000 − 0     = 10,000

numerator = 9,000 × 60 + 10,000 × 40 = 540,000 + 400,000 = 940,000
weighted  = 9,400
risk_bp   = clamp(1,000 + 9,400) = clamp(10,400) = **10,000**
```

The clamp binds. This is not a synthetic case: a deal with zero verified stakeholders and
engagement at or below 0.1666 saturates the scale in `sales.deal_cooling`. Everything above that
point reports the same 10,000bp, so the metric stops discriminating between *very bad* and *worse* —
a real ceiling effect, not a rounding artefact. `test_risk_saturates_rather_than_overflowing_the_scale`
pins the saturation behaviour with a harsher configuration.

### 4.4 · The gate upstream, and what it makes unreachable

`packs/capabilities/deal_cooling.py` declares `core.relationship` with `gating=True` and
`failure_policy=REQUIRED`, and `relationship.py` sets `matched = (deal.status == "open")`. Two
consequences for this plugin:

- **`core.risk` only ever runs on an open deal.** A closed or won deal makes `core.relationship`
  report `matched is False`, which sets `DecisionOutcome.NO_ACTION`, and `core.risk` is recorded as
  `SKIPPED` without being called.
- **The `INSUFFICIENT_CONTEXT` row of §3 cannot be reached in this capability.**
  `core.relationship` returns that status when `deal.status` or
  `relationship.verified_stakeholder_count` is absent; because it is `REQUIRED`, the orchestrator
  sets the terminal outcome immediately and `core.risk` never evaluates.

So the zero-fallback that this unit's Law 3 exception exists to justify **cannot fire in either
shipped capability**. It would fire in a capability that declared `core.relationship` as `OPTIONAL`,
or that named a `relationship_reasoner` it did not list in `ReasonerSpec.dependencies`. Neither
exists today. Anyone weighing whether to keep the exception should weigh it against that.

### 4.5 · Boundary values

| `relationship_risk_bp` | Weighted contribution | Reachable in `deal_cooling`? |
|---|---|---|
| 0 | 0 | yes — three or more verified stakeholders |
| 3,334 | 1,334 (`133,360/100 = 1,333.6 → 1,334`) | yes — two stakeholders |
| 6,667 | 2,667 (`266,680/100 = 2,666.8 → 2,667`) | yes — one stakeholder |
| 10,000 | 4,000 | yes — none verified |

Values outside `{0, 3334, 6667, 10000}` require a different `target_relationships`. The metric is
range-checked at the point `core.relationship` constructs its result, so `_published` cannot receive
anything outside `0..10_000`.

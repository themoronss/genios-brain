# 05 · Evaluator

**Stage 6 of the eight — `@abstractmethod`, every unit must implement it.**
**Source:** `genios_engine/reason/reasoners/priority.py:222` (`PriorityReasoner.evaluate_meaning`)

---

## 1 · What it is for

The Evaluator turns numbers into meaning: *82 → high risk*, *a threshold crossed*, *a candidate
blocked*, *a gate matched*. It is where a unit is allowed to have an opinion about its own
arithmetic.

`core.priority` declines to have one. It reports that the priority inputs are ready and refuses to
say whether they are high.

---

## 2 · The code, in full

```python
# priority.py:222
def evaluate_meaning(self, view: UnitView, metrics: Mapping[str, int],
                     observations: Sequence[Observation]) -> Verdict:
    finding = Finding(finding_id="priority.inputs", kind="priority", metrics=metrics,
                      reason_codes=(PRIORITY_READY_REASON,))
    return Verdict(metrics=dict(metrics), findings=(finding,),
                   reason_codes=finding.reason_codes)
```

Four lines. `view` and `observations` are both accepted and neither is read.

```python
# priority.py:55
PRIORITY_READY_REASON = "priority_inputs_ready"
```

---

## 3 · Thresholds

**There are none.** Not one comparison, not one constant, not one config key. This is the only unit
in the Business Evaluation category with no threshold at all — `core.risk` has `base_risk_bp`,
`core.impact` has a revenue reference and a tier table, `core.confidence` has four dimension weights
and `core.opportunity` has a leader-and-lift split. `core.priority` has nothing to compare against
because it never formed a judgement to compare.

The nearest thing to a threshold in the whole unit is `NEUTRAL_URGENCY_BP = 5_000`, and that is a
*fallback value*, not a boundary: nothing is ever tested against it.

Where the thresholds actually live, for anyone looking for them:

| Threshold | Value | Where | Applied to |
|---|---|---|---|
| `urgency_critical_bp` | `8_000` | `executive/planning.py:119` | this unit's `urgency_bp`, after it has travelled through the candidate |
| `urgency_high_bp` | `6_000` | `executive/planning.py:120` | same |
| `ranking_weights["urgency"]` | `20` of 100 | `deal_cooling.py:372`, and the contract default at `contracts/reasoning.py:360` | the weighted utility |

All three are Layer 5 or Decision Maker concerns. The unit hands over a number and no reading of it.

---

## 4 · `matched` — always `None`, and why

`Verdict.matched` takes its dataclass default of `None` (`unit.py:141`). The docstring is the
argument:

> *`matched` stays None because this unit has no gate to match. "Is 7,200bp urgent enough to act?" is
> a ranking question, and answering it here would make the priority unit a decision authority by the
> back door — the one thing a unit that owns a reserved metric must never become.*

### 4.1 · What `matched` means elsewhere in the roster

| Unit | `matched` | Meaning |
|---|---|---|
| `core.temporal` | `engagement_bp <= max_engagement_bp` | engagement has fallen below the configured threshold |
| `core.relationship` | gating — `True`/`False` | verified-stakeholder coverage is adequate |
| `legacy.rule` | gating — the rule's own predicate | the legacy condition fired |
| `core.signal_composition` | `len(members) >= 2 and len(codes) >= 2` | a compound condition is present |
| **`core.priority`** | **always `None`** | *"this unit does not make claims of that shape"* |

The type is `bool | None` and `None` is a real third state, not a missing value. It is checked at
`contracts/reasoning.py:613` (`matched` must be boolean or `None`) and it is inside
`to_semantic_dict`, so it is part of the result hash — a unit that started returning `True` would
change every stored decision hash for its capability.

### 4.2 · What would break if it were a bool

`orchestrator.py:217`:

```python
elif spec.gating and result.matched is False:
    terminal = DecisionOutcome.NO_ACTION
```

Only *gating* specs consult `matched`, and `core.priority` is not gating in any capability — none of
the three sets `gating=True` on its spec, and `contracts/reasoning.py:304` would force
`failure_policy=REQUIRED` if one did. So a `matched=False` would be inert at the orchestrator level.

The damage would be semantic rather than mechanical. A `matched` on the priority result is a
published claim that the situation *is* or *is not* urgent enough — and every downstream reader that
learned to trust it would be reading a ranking decision from a unit whose entire design premise is
that it does not rank. The docstring calls that becoming a decision authority *by the back door*,
and the phrase is exact: nothing would enforce the claim, and everything would start believing it.

`test_the_result_analyses_and_does_not_decide` asserts `result.matched is None` with the comment
*"a unit that matched would be ranking"*, and `test_the_single_finding_mirrors_the_published_metrics`
asserts `finding.matched is None` as well.

---

## 5 · What it emits

### 5.1 · Findings — exactly one, always

```python
Finding(finding_id="priority.inputs",
        kind="priority",
        matched=None,                     # dataclass default
        metrics=metrics,                  # the same mapping calculate returned
        evidence_ids=(),                  # dataclass default
        reason_codes=("priority_inputs_ready",))
```

The finding is emitted **unconditionally**. There is no branch, no threshold, no "only if urgency is
notable". Every completed run of this unit produces exactly one `priority.inputs` finding.

**Why it carries the same metrics as the result.** From the docstring:

> *The single finding carries the same metrics as the result so an auditor reading the findings alone
> sees the whole contribution.*

Findings are the audit surface. `decision_maker.py:aggregate_evidence` walks
`result.findings` for evidence ids, and the reasoning store persists findings alongside results. A
finding that carried a *subset* of the metrics would make the findings view an incomplete account of
what the unit contributed. `test_the_single_finding_mirrors_the_published_metrics` asserts
`dict(finding.metrics) == dict(result.metrics)` — the mirror is exact, both keys or one key,
whichever `calculate` produced.

Note the aliasing: `Finding(metrics=metrics)` and `Verdict(metrics=dict(metrics))` are handed the
same source mapping, but `Finding.__post_init__` runs it through `_mapping` → `_freeze`, and the
`Verdict` gets a fresh `dict` copy. Neither can mutate the other, and `calculate`'s local dict is
already dead by then. The `dict(...)` copy is defensive rather than necessary.

### 5.2 · Adjustments — none, ever

`Verdict.adjustments` takes its default of `()`. This unit never emits a `CandidateAdjustment`.

That is a category statement, not an omission. A `CandidateAdjustment` moves one named play's score
component by a delta — `synthesize_candidates` applies it at `decision_maker.py:219`. `core.temporal`
emits them (`restore_momentum` urgency `+1,200`, `clarify_next_step` urgency `+500`, from
`deal_cooling.py:147`). `core.priority` does not, because an adjustment is a *per-play* judgement and
this unit publishes a *global* input. It sets the seed value every play's urgency component starts
from; deciding that one particular play deserves more of it is somebody else's claim.

`test_the_result_analyses_and_does_not_decide` asserts `result.adjustments == ()`.

### 5.3 · Checks — none, ever

`Verdict.checks` takes its default of `()`. A `CandidateCheck` with
`CheckOutcome.ELIMINATE` removes a candidate from the field before ranking
(`decision_maker.py:270`), which is the hardest power a unit has. `core.priority` never eliminates
anything. `core.constraint` and `core.policy` own that.

`test_the_result_analyses_and_does_not_decide` asserts `result.checks == ()`.

### 5.4 · Reason codes — exactly one, always

```python
reason_codes = ("priority_inputs_ready",)
```

The constant's own comment states what it is careful *not* to say:

> *The single reason code this unit publishes. It says "the priority inputs are ready", not "this is
> urgent" — the reading itself lives in the metrics, and the Decision Maker judges it.*

`test_the_result_analyses_and_does_not_decide` asserts `result.reason_codes == (PRIORITY_READY_REASON,)`.

**The three plugin reason codes never reach here.** `urgency_from_declared_source`,
`urgency_from_prior_maximum` and `priority_override_declared` exist on the `Observation`s, which
`evaluate_meaning` receives as its third argument and does not read. `Verdict.reason_codes` is set to
`finding.reason_codes` and nothing else, and `unit.py:build` copies only `verdict.reason_codes`.

The consequence is the audit gap: **a persisted `core.priority` result does not say which path
produced it.** A run whose urgency came from a declared `core.temporal` and a run whose urgency came
from the derived maximum are, at the same value, byte-identical. Propagating the plugin reason codes
would have cost one line and closed it — and it would also have changed `semantic_hash` for every
scenario, which the migration's byte-identical contract forbade. The gap is a cost of the migration,
not a design position, and nothing in the code says so. Detail in
[06 · Builder and Metrics](06-Builder-and-Metrics.md) §4.

### 5.5 · Summary of the emission surface

| `Verdict` field | Value | Conditional? |
|---|---|---|
| `matched` | `None` | never varies |
| `metrics` | `dict(calculate's output)` — one or two keys | key count varies |
| `reason_codes` | `("priority_inputs_ready",)` | never varies |
| `findings` | one `Finding("priority.inputs", "priority")` | never varies — always exactly one |
| `adjustments` | `()` | never varies |
| `checks` | `()` | never varies |

**Silence semantics.** This unit is never silent. Even with `prior = {}` and `config = {}` it emits
one finding and one metric. The reason is structural rather than stylistic:
`decision_maker.py:priority_metrics` `break`s the scan on this unit's `reasoner_id`, and a unit that
published nothing would let an *upstream* publisher's `urgency_bp` — set earlier in the same loop —
survive as the decision's urgency. The unit speaks so that the authority is real. Compare
`core.opportunity`, which emits nothing when no opportunity plugin fires: nothing downstream
resolves against it, so its silence costs nothing.

---

## 6 · Worked examples

### 6.1 · `sales.deal_cooling` — one metric

```
metrics from calculate = {"urgency_bp": 9360}
```

```
Finding(finding_id="priority.inputs", kind="priority", matched=None,
        metrics={"urgency_bp": 9360}, evidence_ids=(),
        reason_codes=("priority_inputs_ready",))

Verdict(matched=None,
        metrics={"urgency_bp": 9360},
        reason_codes=("priority_inputs_ready",),
        findings=(that finding,),
        adjustments=(), checks=())
```

The `publishes` guard then runs: `set({"urgency_bp"}) - set(("urgency_bp", "priority_override_bp"))`
= `set()`. Empty, so nothing raises. Publishing *fewer* than the declared metrics is legal; only
publishing something undeclared is not.

### 6.2 · A legacy capability — two metrics

```
metrics from calculate = {"urgency_bp": 6400, "priority_override_bp": 7800}
```

```
Finding(finding_id="priority.inputs", kind="priority", matched=None,
        metrics={"urgency_bp": 6400, "priority_override_bp": 7800},
        reason_codes=("priority_inputs_ready",))
```

Same finding id, same kind, same single reason code. Only the metrics map differs. An auditor
reading findings alone sees both numbers; an auditor asking *which one is the override and where did
it come from* gets nothing beyond the metric name.

Guard: `{"urgency_bp", "priority_override_bp"} - {"urgency_bp", "priority_override_bp"}` = `set()`.

### 6.3 · The empty case

```
prior = {}, config = {}
metrics from calculate = {"urgency_bp": 5000}
```

Identical shape to §6.1 with a different number. **No `INSUFFICIENT_CONTEXT`, no empty result, no
absent finding.** The neutral midpoint is a published claim of ignorance, and it is indistinguishable
in the result from a declared source that ran and had no opinion, and from a declared source that was
skipped. Three causes, one output.

### 6.4 · A leaky subclass — the guard firing

`test_publishing_an_undeclared_metric_is_refused_by_the_framework`:

```python
class Leaky(PriorityReasoner):
    def evaluate_meaning(self, view, metrics, observations):
        return Verdict(metrics={"urgency_bp": 1_000, "confidence_bp": 9_000})
```

```
undeclared = sorted({"urgency_bp", "confidence_bp"} - {"urgency_bp", "priority_override_bp"})
           = ["confidence_bp"]
→ ValueError("core.priority published undeclared metrics: confidence_bp")
```

The guard sits *between* the Evaluator and the Builder (`unit.py:256`), not inside the Builder, so
the failure reads as *"this unit is misdeclared"* rather than *"this result contains something
surprising"* — the `ReasonerResult` never comes into existence. `confidence_bp` is
`core.confidence`'s reserved metric, and letting `core.priority` write it would move the number the
whole decision leans on from a unit nobody knew was moving it.

Note this `Verdict` also has no findings — the guard fires before that would matter, and nothing in
the framework requires a unit to emit one.

---

## Related

- [04 · Calculator](04-Calculator.md) — the mapping this stage mirrors into a finding
- [06 · Builder and Metrics](06-Builder-and-Metrics.md) — the `publishes` guard, the result shape, and the audit gap
- [03 · Analyzer](03-Analyzer.md) — the reason codes that die here

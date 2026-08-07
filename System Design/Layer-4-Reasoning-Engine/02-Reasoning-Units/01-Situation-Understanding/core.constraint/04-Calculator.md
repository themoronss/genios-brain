# 04 · Calculator

**Source:** `genios_engine/reason/reasoners/constraint.py:ConstraintUnit.calculate`
**Framework contract:** `unit.py:ReasoningUnit.calculate` — `@abstractmethod`, must be implemented
**Test:** `tests/test_unit_constraint.py:test_the_gate_publishes_no_metrics`

---

## 1 · What it is for

Stage 5 is where a unit turns its plugins' partial observations into the numbers it will publish.
Pure integer arithmetic, no IO, no floats.

This unit publishes no numbers. The stage is implemented, it runs on every evaluation, and it returns
an empty mapping.

---

## 2 · What exists

```python
def calculate(self, view: UnitView,
              observations: Sequence[Observation]) -> Mapping[str, int]:
    """No metrics.

    Deliberate, not an omission.  A gate's answer is a set of per-play rows; any scalar summary
    of them ("3 eliminations") would be a number downstream units could weigh, and weighing a
    constraint is exactly how a hard block turns into a soft penalty.  The observations carry
    those counts for testing and tracing, and `publishes` reserves names for them, but the
    result deliberately carries none — an empty metrics mapping is part of this unit's frozen
    v1.0.0 output.
    """
    return {}
```

Ten lines of argument, one line of code. The `view` and `observations` arguments are both unused.

```python
publishes: tuple[str, ...] = ("constraint_check_count", "constraint_elimination_count")
```

Declared and never emitted. The class comment calls this out in the code itself:

> *"A ceiling, not a promise. `publishes` is the set of metric names this unit is *permitted* to
> emit; v1.0.0 emits none of them."*

---

## 3 · Why that shape — the code's own argument

The docstring makes one argument, and it is a claim about what happens *downstream* rather than about
this unit.

### 3.1 · A number is weighable; a row is not

`decision_maker.py` reads metrics off results and folds them into a weighted utility. A metric named
`constraint_elimination_count` would be, mechanically, exactly the same kind of thing as
`risk_bp` or `urgency_bp` — an integer sitting on a `ReasonerResult` that some future
`ranking_weights` entry or some future unit's `prior_metric("core.constraint", ...)` call could pick
up and multiply by something.

> *"any scalar summary of them ('3 eliminations') would be a number downstream units could weigh, and
> weighing a constraint is exactly how a hard block turns into a soft penalty."*

That is the failure in one sentence. A play eliminated by `read_only` is not *slightly worse*; it is
out of scope. The moment "three eliminations" becomes a number, a plausible-looking capability config
can trade it off against a high `impact_bp`, and a mutation-forbidden play wins on score.

The structural defence is that there is nothing to weigh. `decision_maker.evaluate_candidates` reads
`check.outcome` and sets a **disposition**, before ranking:

```python
eliminated = any(item.outcome == CheckOutcome.ELIMINATE for item in play_checks)
judged.append(replace(proposal, checks=play_checks,
                      disposition=(CandidateDisposition.ELIMINATED if eliminated
                                   else CandidateDisposition.ELIGIBLE)))
```

A disposition is not a term in a formula. `rank_candidates` then sorts eligible candidates by
`-utility_bp` and appends the eliminated ones after, unranked. There is no arithmetic path from a
check row to a score, and `calculate` returning `{}` is what keeps it that way.

### 3.2 · The names are reserved anyway, and that is the second argument

> *"The names are declared anyway so they are reserved against collision — no other unit may claim
> them — and so that the day a gate summary is genuinely wanted, publishing it is a deliberate,
> reviewable, version-bumped change rather than a metric that appears in the decision record by
> accident."*

`tests/test_unit_roster.py:test_no_unit_publishes_a_metric_another_unit_owns` enforces exactly one
declared publisher per metric name across all seventeen units. Declaring two names it does not emit
costs this unit nothing and permanently prevents another unit from shipping a
`constraint_elimination_count` that means something else.

The second half is about how a change would have to happen. Today, adding the metric requires editing
`calculate`, which sits directly under the docstring above; the reviewer sees the argument they are
overturning. If the names were undeclared, the same change would additionally require editing
`publishes`, which would trip the roster test and force a second conversation — so the current
arrangement is actually the *weaker* guard of the two. It is a deliberate trade: reserving the names
buys collision safety at the cost of one layer of friction on the change it warns against.

### 3.3 · The counts exist, they just do not leave

Each plugin's `Observation` carries `checks_emitted` and `eliminated`
([03-Analyzer](03-Analyzer.md) §2). Those are real numbers computed on every run. They reach:

- the test suite, where `test_every_plugin_summarises_its_own_rows_as_an_observation` reconciles them
  against a fresh `checks()` call;
- a reader of `analyze()`'s return value, if one is debugging the unit directly.

They do **not** reach `calculate` (which ignores its `observations` argument), `evaluate_meaning`
(which recomputes from `checks()` instead), or `build` (which reads only `observation.evidence_ids`).
The counts are strictly internal.

---

## 4 · Worked combination

There is no combination to work — but the *absence* is worth showing with real inputs, because
"the calculator produced nothing" and "the calculator was not asked" look identical in a trace
otherwise.

`sales.deal_cooling` with `facts = {deal.status: "closed", deal.value: 1}`, an empty neighbour space,
no snapshot evidence and no prior results — the same run as [03-Analyzer](03-Analyzer.md) §3.
`analyze()` produced three observations:

```text
observations (in plugin_id order):
  Observation(plugin_id="permission_verification", kind="constraint.permission",
              metrics={"checks_emitted": 6, "eliminated": 0},
              evidence_ids=(), reason_codes=())
  Observation(plugin_id="policy_enforcement",      kind="constraint.policy",
              metrics={"checks_emitted": 6, "eliminated": 3},
              evidence_ids=(), reason_codes=())
  Observation(plugin_id="precondition",            kind="constraint.precondition",
              metrics={"checks_emitted": 6, "eliminated": 5},
              evidence_ids=(), reason_codes=())

calculate(view, observations)
    → {}                                  # 18 rows and 8 eliminations summarised as nothing

evaluate_meaning(view, metrics={}, observations=[...])
    → Verdict(matched=None, metrics={}, checks=(18 rows), reason_codes=("constraints_evaluated",))

publishes guard:
    undeclared = sorted(set({}) - {"constraint_check_count", "constraint_elimination_count"})
               = []                        # passes trivially — nothing to check
    → build proceeds

result.metrics = {}
```

The arithmetic that *would* have been available, had the unit chosen to publish:

```text
constraint_check_count      = 6 + 6 + 6 = 18
constraint_elimination_count = 0 + 3 + 5 = 8
```

Both are exact integers, both are already computed, and neither ships. That is the deliberate part.

Two consequences of returning `{}` rather than `{"constraint_check_count": 0, ...}`:

1. **The `publishes` guard is vacuous for this unit.** `unit.py:evaluate` computes
   `set(verdict.metrics) - set(self.publishes)`, and `verdict.metrics` is always empty, so the guard
   can never fire here. Its protection is against a *future* version of this unit, not the current
   one.
2. **`ReasonerResult.metrics` is `{}`, not `{"constraint_check_count": 0}`.** Anything downstream
   calling `view.prior_metric("core.constraint", "constraint_check_count")` gets the caller's
   `default` — silently. Nothing in the shipped roster does. Three units declare `core.constraint` as
   a dependency and none of them reads a metric off it: `core.alternative` reads its **checks**
   (`alternative_unit.py:_rulings`), `core.priority` reads only the result its `source_reasoner`
   config names — `core.temporal` in `sales.deal_cooling` — and `core.planning` opens with
   `del prior_results` and reads nothing at all. In all three cases the dependency edge exists to
   force **ordering**, not to pass a value.

---

## 5 · Edge cases

| Situation | `calculate` returns |
|---|---|
| Zero rows emitted (no policies, no preconditions, no blocks) | `{}` |
| Every play eliminated | `{}` |
| Every play clear | `{}` |
| `observations` is empty because all three plugins were silent | `{}` |

There is no input under which this method returns anything else, and that constancy is part of the
frozen v1.0.0 output: `test_the_gate_publishes_no_metrics` asserts `dict(result.metrics) == {}` on the
full `sales.deal_cooling` run.

---

**Next:** [05-Evaluator](05-Evaluator.md) — where the rows are actually assembled.

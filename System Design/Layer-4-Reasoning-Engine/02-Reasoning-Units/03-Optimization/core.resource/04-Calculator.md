# 04 · Calculator — `core.resource`

**Stage 5:** `resource_unit.py:ResourceUnit.calculate(view, observations)` — `@abstractmethod`, implemented here
**Length:** 12 lines of body
**Purity:** integer arithmetic only; `view` is explicitly discarded with `del view`

---

## 1 · What it is for

The Calculator turns a bag of partial observations into the unit's metrics. For most units that means
combining several weak signals into one strong number. For this one it means the opposite: **choosing
which single observation on each axis is the one that will actually bite.**

---

## 2 · What exists

```python
def calculate(self, view: UnitView,
              observations: Sequence[Observation]) -> Mapping[str, int]:
    del view
    capacities = [item.metrics["capacity_bp"] for item in observations
                  if "capacity_bp" in item.metrics]
    loads = [item.metrics["load_bp"] for item in observations if "load_bp" in item.metrics]
    headrooms = [item.metrics["headroom_bp"] for item in observations
                 if "headroom_bp" in item.metrics]
    metrics: dict[str, int] = {"resource_signal_count": len(observations)}
    if capacities:
        metrics["capacity_bp"] = min(capacities)
    if loads:
        metrics["load_bp"] = max(loads)
    if headrooms:
        metrics["headroom_bp"] = min(headrooms)
    return metrics
```

```text
resource_signal_count = |observations|                         always emitted
capacity_bp           = min{ o.capacity_bp }                   emitted only if non-empty
load_bp               = max{ o.load_bp     }                   emitted only if non-empty
headroom_bp           = min{ o.headroom_bp }                   emitted only if non-empty
```

`del view` on the first line is not decoration. It states that this stage reads **no config, no
facts, no prior results** — it is a pure fold over the observation list, and nothing an author tunes
in Layer 3 can change its output. Every threshold in this unit lives one stage later, in the
Evaluator, which is where they belong: the Calculator reports what was observed, the Evaluator decides
what that means.

---

## 3 · Why that shape

The docstring makes the argument in two sentences and they are the right two:

> *The binding constraint wins on every axis — capacity is not an average.*
>
> *Deliberately not a mean: an owner who is fully available and a budget that is exhausted do not
> average out to "half feasible". The scarcest capacity, the heaviest load and the tightest headroom
> are what the work will actually run into, so those are what get published.*

Work against the alternatives, using the run in §5.1 — capacity 10,000, loads 1,000 and 9,000,
headrooms 8,000 and 60:

| Fold | `capacity_bp` | `load_bp` | `headroom_bp` | What a reader would conclude |
|---|---|---|---|---|
| **min / max / min** (shipped) | 10,000 | 9,000 | **60** | the clock is nearly out; act today or not at all |
| mean | 10,000 | 5,000 | 4,030 | a comfortable half-loaded team with plenty of runway — **false on every axis** |
| sum, clamped | 10,000 | 10,000 | 8,060 | invented saturation, invented headroom |
| max / min / max | 10,000 | 1,000 | 8,000 | a free owner with two thirds of the money left — the reading that gets someone hurt |

The mean is the seductive one, and it is wrong for a specific reason rather than a stylistic one: an
average is the right summary when the inputs are *substitutable*, and resources are not. Having
budget does not buy back a window that closed. A free owner does not relieve a team at the wall. Each
axis is a separate gate the work has to pass through, and a chain of gates is characterised by its
narrowest, not by its mean width.

Note also that the fold is **within** an axis, not across axes. There is no arithmetic anywhere in
this unit that mixes `capacity_bp` with `headroom_bp`. That is the same argument one level up: the
three readings are published side by side precisely so nobody has to invent an exchange rate between
a person and a deadline. `min` inside an axis, nothing at all between axes.

### Why `max` for load and `min` for the other two

They are measuring opposite polarities of the same idea. `capacity_bp` and `headroom_bp` count *what
is left* — bigger is better, so the binding constraint is the smallest. `load_bp` counts *what is
already taken* — bigger is worse, so the binding constraint is the largest. All three folds select
the worst reading; only the direction of *worst* differs.

Had `load_bp` been expressed as *remaining capacity* instead of *used capacity*, all three would be
`min` and the unit would have one fold instead of two. It was not, presumably because *load* is what
source systems report and *remaining* is not, and inverting at the plugin would have made every
observation harder to check against its source.

### Why an empty axis is omitted rather than defaulted

```python
if capacities:
    metrics["capacity_bp"] = min(capacities)
```

`min([])` raises, so the guard is required — but the guard could equally have written a default. It
does not, and the class docstring says why:

> *Each is omitted entirely when nothing was observed: an absent metric means unknown, and a reader
> that defaults it chooses its own default rather than inheriting a fabricated one.*

Which is not an abstract preference. The Evaluator one stage later *does* default these metrics, and
it defaults them **in different directions** — `capacity_bp` to 10,000, `load_bp` to 0, `headroom_bp`
to 10,000 — all chosen so that an unmeasured axis raises no strain. If the Calculator had baked those
defaults into the published metrics, every downstream reader would inherit *this unit's* view of what
a missing measurement means, and `test_unknown_capacity_warns_rather_than_inventing_a_shortfall` would
have nothing to assert. Keeping the absence in the metrics is what lets the Evaluator's WARN say
*unknown* rather than *fine*.

### Why `resource_signal_count` is always emitted

It is the metric that makes the other three's absence *readable*. Without it, a result carrying
`{}` is indistinguishable from a result the orchestrator never populated. With it:

| Metrics | Reading |
|---|---|
| `{resource_signal_count: 0}` | nothing looked. Capacity is genuinely unmeasured |
| `{resource_signal_count: 1, load_bp: 2000}` | one thing looked; capacity and headroom are still unmeasured |
| `{resource_signal_count: 5, capacity_bp: 10000, load_bp: 9000, headroom_bp: 60}` | everything looked |

It counts **observations, not axes**. Five observations across three axes is the maximum; two
observations on one axis and none on the others gives `2`. So it is a measure of *how much evidence*
rather than *how much coverage*, and a reader who needs coverage has to check which metrics are
present. The framework README makes the same point about `core.opportunity`'s `opportunity_count`:
*three signals looked and found nothing* is a materially different claim from *nothing looked*, and
only a count can distinguish them.

---

## 4 · The `publishes` guard, on this stage's output

Between the Evaluator and the Builder the framework checks:

```python
undeclared = sorted(set(verdict.metrics) - set(self.publishes)) if self.publishes else []
```

`publishes` is `("capacity_bp", "load_bp", "headroom_bp", "resource_signal_count")` and
`Verdict.metrics` is `dict(metrics)` straight from this stage, so the sets always match on a subset
basis and the guard always passes. The guard is not vestigial, though: it is what would catch a fourth
plugin emitting, say, `staffing_bp`, on the first test run rather than six months later.

Note the guard checks the *Verdict*, and the metrics that never reach it — `open_items`,
`capacity_items`, `remaining_minor`, `hours_remaining` — live only on `Observation`s and their
derived `Finding`s. Those four are **not** in `publishes` and never need to be. They are per-finding
detail, not unit metrics, and the distinction is exactly what keeps a raw item count from becoming a
number some downstream ranking formula can weigh.

---

## 5 · Worked combinations

### 5.1 · The binding constraint on every axis

`test_the_binding_constraint_wins_on_every_axis`. Facts: `owner.status = "available"`,
`deal.owner = "dana_whitfield"`, `owner.load_bp = 1,000`, `team.load_bp = 9,000`,
`budget.total_minor = 50,000`, `budget.remaining_minor = 40,000`,
`commitment.due_at = 2026-08-06T13:00:00+00:00` against a noon evaluation time.

```text
observations, in plugin_id order
  1  resource.budget_headroom     headroom_bp  8,000     40,000/50,000
  2  resource.deadline_headroom   headroom_bp     60     1 hour of 168
  3  resource.owner_availability  capacity_bp 10,000     status "available"
  4  resource.owner_workload      load_bp      1,000     declared
  5  resource.team_workload       load_bp      9,000     declared

fold
  capacities  [10000]              → min → 10,000
  loads       [1000, 9000]         → max →  9,000
  headrooms   [8000, 60]           → min →     60
  count                            →           5

metrics {resource_signal_count: 5, capacity_bp: 10000, load_bp: 9000, headroom_bp: 60}
```

The deadline arithmetic: 1 hour of a 168-hour window is
`divide_half_up(1 × 10,000, 168) = (10,000 + 84) // 168 = 10,084 // 168 = 60`.

Three sentences a reader can act on, from one fold: *the person is free, the team is not, and the
clock runs out in an hour.* An average would have said *5,000bp of load and 4,030bp of headroom* —
a comfortable half-loaded team with two and a half days of runway, which is false in both directions
and would have been acted on as though it were true.

### 5.2 · Northwind — four observations, three axes short

```text
observations
  1  resource.budget_headroom     headroom_bp    400    2,000/50,000
  2  resource.deadline_headroom   headroom_bp    357    6 hours of 168
  3  resource.owner_availability  capacity_bp      0    out_of_office
  4  resource.owner_workload      load_bp     10,000    14 items against 10

fold
  capacities  [0]                  → min →      0
  loads       [10000]              → max → 10,000
  headrooms   [400, 357]           → min →    357
  count                            →           4

metrics {resource_signal_count: 4, capacity_bp: 0, load_bp: 10000, headroom_bp: 357}
```

Both headroom readings are far below the floor here, so the `min` picks 357 without changing the
verdict — but it changes what the card can say. *3.6% of your window remains* is actionable in a way
*4% of your budget remains* is not, when the deadline is six hours out.

### 5.3 · A comfortable situation

`test_a_comfortably_resourced_situation_records_a_pass_rather_than_going_quiet`. Facts:
`deal.owner = "dana_whitfield"`, `owner.status = "available"`, `owner.open_items = 2`,
`budget.total_minor = 50,000`, `budget.remaining_minor = 45,000`,
`commitment.due_at = 2026-08-11T12:00:00+00:00`.

```text
observations
  1  resource.budget_headroom     headroom_bp  9,000     45,000/50,000
  2  resource.deadline_headroom   headroom_bp  7,143     120 hours of 168
  3  resource.owner_availability  capacity_bp 10,000
  4  resource.owner_workload      load_bp      2,000     2 items against 10

metrics {resource_signal_count: 4, capacity_bp: 10000, load_bp: 2000, headroom_bp: 7143}
```

`120 × 10,000 = 1,200,000`; `(1,200,000 + 84) // 168 = 1,200,084 // 168 = 7,143`. Every reading inside
its threshold, so `matched` is `False` and a `PASS` is recorded — the audit trail shows capacity was
checked rather than skipped.

### 5.4 · The empty run

```text
observations  []
capacities [] loads [] headrooms []   → all three guards fail
metrics {resource_signal_count: 0}
```

One metric. Not `{capacity_bp: 0, ...}`, and not `{}`. This is the case
`test_unknown_capacity_warns_rather_than_inventing_a_shortfall` exists for.

---

## 6 · Edge cases

### 6.1 · A single observation on an axis

`min` and `max` of a one-element list are the identity. `capacity_bp` has at most one contributor
today — `owner_availability` emits either `resource.owner_unassigned` or
`resource.owner_availability`, never both — so its `min` is *always* the identity in the shipped
system. It is written as a fold anyway, which is correct forward-looking design: a future
`delegate_availability` plugin emitting a second `capacity_bp` would join the fold and lower the
reading without a line changing here.

### 6.2 · Duplicate readings

`min([0, 0])` is `0`. Nothing deduplicates, and nothing needs to: the fold is idempotent under
repetition and `resource_signal_count` deliberately counts observations rather than distinct values,
because two independent sources agreeing is more evidence than one source speaking.

### 6.3 · An observation with metrics on two axes

None exists today — every observation writes exactly one of the three axis names — but the code
handles it: the three list comprehensions are independent membership tests, so one observation
carrying both `capacity_bp` and `load_bp` would contribute to both folds and be counted once in
`resource_signal_count`.

### 6.4 · Values outside 0–10,000

Cannot arise. Every axis metric is produced either by `_ratio_bp` (which ends in `clamp_bp`), by
`basis_points` (which range-checks), or by the literals `0` and `10_000`. `min` and `max` over
in-range values stay in range, and `build` clamps every `_bp` name again on the way out. Three layers
of the same guarantee, which is why `guards.py:validate_candidate_effects` never fires on this unit.

### 6.5 · `resource_signal_count` is not clamped

`build` applies `clamp_bp` only to names ending in `_bp`. `resource_signal_count` is a plain count and
passes through untouched — correct, since clamping a count at 10,000 would be meaningless and
clamping it at all would be wrong. Its real range is 0–5.

---

## Related

| Document | Covers |
|---|---|
| [03-Analyzer.md](03-Analyzer.md) | Where the observations come from and in what order |
| [05-Evaluator.md](05-Evaluator.md) | The three thresholds this stage deliberately does not apply |
| [06-Builder-and-Metrics.md](06-Builder-and-Metrics.md) | What happens to these four metrics on the way into the result |
| [../README.md](../README.md) | Category 3 §4.2 — the fold diagram as a summary |

# 03c · Plugin `workload_saturation` — `WorkloadSaturationPlugin`

**Symbol:** `resource_unit.py:WorkloadSaturationPlugin` (lines 148–196)
**`plugin_id`:** `workload_saturation` — third and last in `plugin_id` order
**Emits:** `resource.owner_workload`, `resource.team_workload` — 0, 1 or 2 observations per run
**Sole publisher of:** `load_bp`

---

## 1 · The claim it makes

> *How much of the declared capacity is already spoken for.*
>
> *Availability and load are deliberately kept apart. An owner can be fully available and still be
> the wrong person to hand a fourteenth open commitment to, and an owner on leave with an empty queue
> is a different problem entirely. Reporting them as one number would make both unexplainable.*

This is the plugin that answers *they are here, but should they be given this?* It is the only one of
the three whose reading can be high and still not be a problem — 7,000bp of load against a default
ceiling of 8,000bp is a busy person doing their job — which is why it is a ceiling and not a floor,
and why its metric folds by `max` while the other two fold by `min`.

Two scopes, and the second one is the interesting one:

> *Owner load and team load are separate observations: when a team is at the wall it does not help
> that this particular person is not.*

---

## 2 · What exists

```python
_SOURCES = (
    ("owner", "owner.load_bp", "owner.open_items", "owner_workload_declared"),
    ("team",  "team.load_bp",  "team.open_items",  "team_workload_declared"),
)
```

A four-tuple per scope: the `kind` suffix, the declared-load field, the item-count field, and the
reason code. The loop over `_SOURCES` is in **tuple order**, not sorted — owner before team — which
is deterministic because the tuple is a module constant. `test_owner_and_team_load_are_reported_separately`
pins that order: `["resource.owner_workload", "resource.team_workload"]`.

```python
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    request = view.request
    capacity_items = _config_count(view, "workload_capacity_items", 10)
    observations: list[Observation] = []
    for scope, load_field, items_field, reason in self._SOURCES:
        metrics: dict[str, int] = {}
        declared = fact_value(request, load_field)
        if declared is not None:
            try:
                metrics["load_bp"] = basis_points(declared, load_field)
            except ValueError:
                continue                   # a malformed load figure is not a load claim
        else:
            open_items = _optional_int(request, items_field)
            if open_items is None:
                continue                   # nobody counted; saying "0 load" would be a fiction
            metrics["load_bp"]       = _ratio_bp(open_items, capacity_items)
            metrics["open_items"]    = max(open_items, 0)
            metrics["capacity_items"] = capacity_items
        observations.append(Observation(
            plugin_id=self.plugin_id, kind=f"resource.{scope}_workload", metrics=metrics,
            evidence_ids=evidence_ids(request, load_field, items_field),
            reason_codes=(reason,)))
    return tuple(observations)
```

Note `_config_count` runs **before** the loop and unconditionally — a bad `workload_capacity_items`
fails every run, including runs with no workload facts at all. That is the eager validation the other
two config keys in this unit do not get, and it is why
`test_a_zero_workload_capacity_is_rejected_where_it_is_authored` reads the way it does:

> *Zero would make the ratio undefined, and a unit that divides by a misconfigured zero would fail a
> whole run over a manifest typo, so it is rejected where it is authored instead.*

---

## 3 · When it stays silent

| Situation | Emits for that scope | Why |
|---|---|---|
| Neither `*.load_bp` nor `*.open_items` present | nothing | *"An uncounted queue is not an empty queue"* |
| `*.load_bp` present but malformed or out of range | nothing — `continue` | *"a malformed load figure is not a load claim"* |
| `*.open_items` present but not an integer | nothing — `_optional_int` returns `None` | a count that is not a count |
| `*.open_items` present and `0` | **an observation** — `{load_bp: 0, open_items: 0, capacity_items: N}` | somebody counted and the answer was zero. A measured empty queue is a real claim |

The two scopes are independent: owner silent and team speaking is normal, and vice versa.
`test_no_workload_facts_means_no_workload_claim` asserts `()` for a snapshot of
`{"deal.status": "open"}`.

**A measured zero is not silence here.** That is the mirror of the owner plugin's captured-but-empty
rule, and it is right for the same reason — `owner.open_items: 0` is somebody reporting a clear
queue, which is genuine information and should reach the reader as `load_bp: 0`, not as nothing.

---

## 4 · The arithmetic

Two paths per scope, and the first one has precedence:

```text
if *.load_bp is present and valid:
    load_bp = *.load_bp                                        (0..10,000, used verbatim)
    metrics = {load_bp}                                        ← no open_items, no capacity_items

else if *.open_items is present and integral:
    load_bp        = clamp( round_half_up(
                        min(max(open_items, 0), capacity) × 10,000 ÷ capacity ) )
    open_items     = max(open_items, 0)
    capacity_items = capacity
```

> *A system that already computed load knows more than a raw item count does.*
> — `test_a_declared_load_is_used_directly_without_recounting_items`

And on the ratio:

> *Load is commitments against the capability's declared serving capacity. Past 100% the ratio
> saturates: twice over capacity and five times over capacity are both simply "cannot take more", and
> pretending to distinguish them is noise.*

The saturation is done by `_ratio_bp`'s inner `min(max(part, 0), whole)`, which caps the **numerator**
at the denominator. So the ratio never exceeds 10,000bp, and the raw `open_items` metric is what
preserves the true figure for a reader: `{load_bp: 10000, open_items: 50, capacity_items: 10}` says
*five times over, and the number does not matter*.

Compare `headroom_bp`, which saturates at the same place for the same reason. The two ratios use the
identical `_ratio_bp` helper, which is why *a full budget* and *a full queue* land on the same scale
even though one is a good number and the other is a bad one. The direction is imposed by the
Evaluator — a floor on headroom, a ceiling on load — not by the arithmetic.

---

## 5 · Configuration

| Key | Default | Validator | Effect |
|---|---|---|---|
| `workload_capacity_items` | **10** | `_config_count` — integer `> 0`, `bool` rejected | how many open commitments constitute a full plate |

One key, and it is the denominator that makes a raw count mean anything:

> *Load is only meaningful relative to what the capability says a person can carry.*
> — `test_open_commitments_are_measured_against_declared_serving_capacity`

Ten is untuned. It is not derived from any outcome data; it is a round number standing in for *a
salesperson can actively work about ten deals*. A support capability where an agent carries forty
tickets, or an M&A capability where a banker carries three, would both need to set it. Nothing in the
shipped manifests does, so ten is what production runs on for every domain.

The key is ignored entirely when a scope reports `*.load_bp` directly, which means a deployment can
mix both conventions: `owner.load_bp` from a workforce system and `team.open_items` from a CRM, in the
same run, with only the second measured against the ten.

---

## 6 · Worked examples

### 6.1 · Four items against a declared capacity of eight

```text
facts    owner.open_items = 4
config   workload_capacity_items = 8

owner.load_bp absent → count path
    numerator   min(max(4, 0), 8) = 4
                4 × 10,000 = 40,000
    divide      divide_half_up(40,000, 8) = (40,000 + 4) // 8 = 40,004 // 8 = 5,000
    clamp       5,000

Observation resource.owner_workload
            metrics       {load_bp: 5000, open_items: 4, capacity_items: 8}
            reason_codes  ("owner_workload_declared",)
```

5,000bp — half a plate. Below the 8,000bp default ceiling, so no strain.
`test_open_commitments_are_measured_against_declared_serving_capacity` asserts the metrics mapping
exactly, including `capacity_items`, which is what lets a reader reconstruct the ratio from the
observation alone without knowing the config.

### 6.2 · Northwind — fourteen items against ten

```text
facts    owner.open_items = 14
config   workload_capacity_items absent → 10

    numerator   min(max(14, 0), 10) = 10          ← saturated here, not at the clamp
                10 × 10,000 = 100,000
    divide      (100,000 + 5) // 10 = 100,005 // 10 = 10,000

Observation {load_bp: 10000, open_items: 14, capacity_items: 10}
```

`10,000 ≥ 8,000` → `workload_saturated`. The 140% is preserved in `open_items` and erased from
`load_bp`, which is the design: a card can say *fourteen open items against a capacity of ten* while
the ranking-visible number just says *full*.

### 6.3 · Five times over is the same as twice over

```text
facts    owner.open_items = 50
config   workload_capacity_items = 10

    min(max(50, 0), 10) = 10 → load_bp 10,000
```

Identical `load_bp` to the fourteen-item case. `test_load_saturates_instead_of_pretending_to_rank_degrees_of_overload`.

### 6.4 · A declared load wins over a count

```text
facts    owner.load_bp = 6,500
         owner.open_items = 99          ← ignored entirely

declared = 6500, not None
basis_points(6500) → 6,500

Observation {load_bp: 6500}             ← no open_items, no capacity_items
```

`test_a_declared_load_is_used_directly_without_recounting_items` asserts the metrics mapping is
exactly `{"load_bp": 6_500}`. The absence of `open_items` in the declared path is deliberate and
readable: reporting `open_items: 99` alongside a `load_bp` that was not derived from it would invite a
reader to check the arithmetic and find it does not hold.

### 6.5 · Team at the wall, owner free

```text
facts    owner.load_bp = 1,000
         team.load_bp  = 9,500

Observations, in _SOURCES order:
    resource.owner_workload  {load_bp: 1000}   ("owner_workload_declared",)
    resource.team_workload   {load_bp: 9500}   ("team_workload_declared",)

calculate → load_bp = max(1000, 9500) = 9,500
evaluate  → 9,500 ≥ 8,000 → workload_saturated
```

`test_owner_and_team_load_are_reported_separately`. The `max` is what makes the team's problem bind:
this person could take the work, and their team cannot absorb the consequences of them doing so. Both
readings survive as separate findings, so the card can name which one it was.

### 6.6 · A team-only count with a tuned capacity

```text
facts    team.open_items = 3
config   workload_capacity_items = 7

    min(max(3, 0), 7) = 3
    3 × 10,000 = 30,000
    (30,000 + 3) // 7 = 30,003 // 7 = 4,286.1… → 4,286

Observation resource.team_workload  {load_bp: 4286, open_items: 3, capacity_items: 7}
```

No owner observation, because no `owner.*` fact was captured. `resource_signal_count` for this run
would be 1.

---

## 7 · Edge cases, including two that are wrong

### 7.1 · A malformed declared load suppresses the count fallback

**Verified.** `{"owner.load_bp": 12000, "owner.open_items": 5}`:

```text
declared = 12000, not None
basis_points → "must be between 0 and 10000" → ValueError
except ValueError: continue       ← the whole scope is abandoned

contribute → ()
```

A perfectly good count of five open items is discarded because a *different* field was malformed. The
`continue` exits the loop iteration rather than falling through to the `else`, so the two sources are
not tried in order — the presence of the first one, valid or not, decides the scope.

The safer shape would be to fall through: a corrupt `load_bp` should demote the reading to the count,
not delete it. Compare the owner plugin, which makes the *opposite* choice deliberately — a corrupt
`availability_bp` there must not fall back to a coarser status word, because the coarser source is
known to be less trustworthy. Here the fallback source is not less trustworthy, it is just less
processed, so the same reasoning does not carry. Neither behaviour is tested and neither is argued in
the code.

### 7.2 · A negative item count fabricates a zero-load claim

**Verified.** `{"owner.open_items": -3}`:

```text
_optional_int → -3, not None      ← passes the silence gate
_ratio_bp(-3, 10) → min(max(-3, 0), 10) = 0 → load_bp 0
open_items    → max(-3, 0) = 0

Observation {load_bp: 0, open_items: 0, capacity_items: 10}
```

Garbage in, confident claim out: the unit now reports *somebody counted and this person has an empty
queue*, on the strength of a value that cannot be a count. Every other malformed input in this unit
degrades to silence; this one degrades to a favourable reading. A `open_items < 0 → continue` guard
would close it. There is none, and no test covers a negative count.

The blast radius is small — a zero load never strains — but the direction is the dangerous one:
`load_bp: 0` is also what the Calculator's `max` sees, so a negative owner count paired with a real
team count is harmless, while a negative count on its own converts a data fault into a clean bill of
health with `resource_signal_count: 1`.

### 7.3 · Boundary values

| Input | `load_bp` | Note |
|---|---|---|
| `owner.open_items = 0` | `0` | a genuine measured-empty queue, and a real observation |
| `owner.open_items = 10` with capacity `10` | `10,000` | exactly full saturates |
| `owner.open_items = 9` with capacity `10` | `9,000` | `9,000 ≥ 8,000` → strains |
| `owner.open_items = 8` with capacity `10` | `8,000` | `8,000 ≥ 8,000` → strains, the ceiling is inclusive |
| `owner.load_bp = 0` | `0` | a declared empty queue |
| `owner.load_bp = 10000` | `10,000` | |
| `owner.load_bp = "6500"` | `6,500` | `common.py:integer` parses a `Decimal`-convertible string |
| `owner.load_bp = 65.5` | — | rejected → `continue` → scope silent |
| `owner.load_bp = True` | — | rejected — `integer` rejects `bool` → `continue` |
| `owner.open_items = 3.7` | — | rejected → scope silent |

### 7.4 · Evidence citation covers both fields

`evidence_ids(request, load_field, items_field)` is called regardless of which path produced the
number, so an observation derived from `owner.load_bp` still cites an `owner.open_items` evidence row
if one exists. Same over-citation pattern as the owner plugin — safe direction, but an evidence id
here proves capture, not use.

### 7.5 · No `deal.owner` required

The plugin never reads `deal.owner`. `{"owner.open_items": 40}` with no owner at all produces a full
saturation reading — `test_an_observed_saturation_is_still_warned_when_capacity_itself_is_unmeasured`
relies on exactly that, and it is the run that exercises the Evaluator's *load without capacity*
branch. The scoping prefix `owner.` is a naming convention, not a join.

---

## Related

| Document | Covers |
|---|---|
| [03-Analyzer.md](03-Analyzer.md) | How this plugin composes with the other two |
| [04-Calculator.md](04-Calculator.md) | The `max` over `load_bp` and why it is the only `max` in the unit |
| [05-Evaluator.md](05-Evaluator.md) | `load_ceiling_bp`, and why an absent `load_bp` defaults to 0 rather than 10,000 |
| [03b-plugin-owner_availability.md](03b-plugin-owner_availability.md) | The other precedence resolution in this unit, decided the opposite way |

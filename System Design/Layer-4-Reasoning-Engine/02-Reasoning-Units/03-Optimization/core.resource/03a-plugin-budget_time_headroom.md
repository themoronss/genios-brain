# 03a · Plugin `budget_time_headroom` — `HeadroomPlugin`

**Symbol:** `resource_unit.py:HeadroomPlugin` (lines 199–258)
**`plugin_id`:** `budget_time_headroom` — first in `plugin_id` order, so its observations lead the result
**Emits:** `resource.budget_headroom`, `resource.deadline_headroom` — 0, 1 or 2 observations per run

---

## 1 · The claim it makes

> *What is left of the two resources that run out on their own: money and time.*

Everything else a plugin in this unit measures is about a person, and people can be substituted. Money
and a calendar cannot. They also share one property no other resource has: they deplete whether or not
anybody acts. That is why they live in one plugin — not because a budget and a deadline are the same
thing, but because they fail the same way, by *running out*, and both are naturally expressed as *what
fraction of the declared allowance is still unspent*.

Expressing both as a fraction is the plugin's central decision:

> *Both are reported as the fraction of the declared allowance still unspent, so a budget and a
> deadline can be compared on one scale without either being converted into the other. The unit then
> lets the scarcer one bind, because having budget does not buy back a window that closed.*

The alternative would have been to price time in money or money in hours. Both require an exchange
rate nobody has, and both produce a number that is wrong in a different currency every time the
domain changes.

---

## 2 · When it stays silent

`contribute` is a filter over two independent sub-readings:

```python
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    return tuple(item for item in (self._budget(view), self._deadline(view))
                 if item is not None)
```

Each half is independent. A budget with no deadline emits one observation; a deadline with no budget
emits one; neither emits `()`.

| Silence condition | Where | Why |
|---|---|---|
| `budget.total_minor` absent | `_budget` | no allowance, so no fraction is definable |
| `budget.remaining_minor` absent | `_budget` | *"a remaining figure with no allowance to compare it against says nothing about headroom"* |
| `budget.total_minor <= 0` | `_budget` | the ratio would be undefined; a zero denominator is not a zero headroom |
| either budget figure malformed | `_optional_int` returns `None` | *"treating a malformed one as unsaid rather than as zero"* |
| the deadline fact is absent | `_deadline` | no clock declared |
| the deadline fact does not parse | `parse_time` raises, caught | *"an unparseable deadline is not a deadline"* |
| the deadline is timezone-naive | `parse_time` raises `must be timezone-aware`, caught | a wall-clock string with no offset is not a point in time |

`test_budget_headroom_needs_both_sides_of_the_ratio` pins the first three;
`test_an_unparseable_deadline_is_not_a_deadline` pins the parse failure.

**One thing that is not silence:** a deadline in the past. That produces an observation with
`headroom_bp: 0` and a negative `hours_remaining`, because *"a window already past has no headroom at
all, and the hours are reported so a reader can see how far past — a deadline missed by an hour reads
very differently from one missed by a week, even though both leave nothing to spend."*

---

## 3 · The arithmetic

### 3.1 · Budget

```python
total     = _optional_int(request, "budget.total_minor")
remaining = _optional_int(request, "budget.remaining_minor")
if total is None or remaining is None or total <= 0:
    return None
metrics = {"headroom_bp":     _ratio_bp(remaining, total),
           "remaining_minor": max(remaining, 0)}
```

with

```python
def _ratio_bp(part: int, whole: int) -> int:
    return clamp_bp(divide_half_up(min(max(part, 0), whole) * 10_000, whole))
```

Expanded, for a budget:

```text
headroom_bp = clamp( round_half_up( clamp(remaining, 0, total) × 10,000 ÷ total ) , 0, 10,000 )
```

`common.py:divide_half_up` is integer-only and rounds half away from zero:
`(numerator + denominator // 2) // denominator`. No floats anywhere on this path, which is what makes
the same allowance produce the same basis points on every machine and in every replay.

The double clamp is not redundant. The inner `min(max(part, 0), whole)` bounds the *numerator*, which
is what makes an overspent budget read as `0` and an over-funded one read as `10,000`; the outer
`clamp_bp` is belt-and-braces against a rounding overshoot at the top of the range.

**Minor units, not currency.** `budget.total_minor` and `budget.remaining_minor` are integers in the
smallest unit — pence, cents — which is why they are read with `_optional_int` and never `decimal`.
The plugin never sees a currency code and never compares two budgets, so it does not need one.

### 3.2 · Deadline

```python
field  = view.config.get("deadline_field", "commitment.due_at")   # must be a non-empty str
raw    = fact_value(view.request, field)
due_at = parse_time(raw, field)                                   # tz-aware, normalised to UTC
window = _config_count(view, "deadline_window_hours", 168)

hours_remaining = int((due_at - view.request.evaluation_time).total_seconds()) // 3600
headroom_bp     = 0 if hours_remaining <= 0 else _ratio_bp(hours_remaining, window)
reason_codes    = ("deadline_passed",) if hours_remaining <= 0 else ("deadline_headroom_declared",)
```

```text
hours_remaining = floor( truncate_to_seconds(due_at − evaluation_time) ÷ 3600 )
headroom_bp     = 0                                          if hours_remaining ≤ 0
                = clamp( round_half_up( min(hours_remaining, window) × 10,000 ÷ window ) )
```

**`view.request.evaluation_time`, never a clock.** This is the property that makes the whole unit
replayable: the same snapshot re-run in six months produces the same `hours_remaining`, because the
subtrahend is frozen into the request rather than read from the machine. The roster's purity scan
(`test_no_unit_reaches_for_a_clock_or_a_database`) would fail this module on a `datetime.now`
substring; `parse_time` lives in `common.py` where `datetime` is legitimate and measures only against
`request.evaluation_time`. `test_time_headroom_is_measured_against_the_frozen_evaluation_time` states
the intent in its name.

---

## 4 · Configuration

| Key | Default | Validator | Effect |
|---|---|---|---|
| `deadline_field` | `"commitment.due_at"` | inline: must be a non-empty `str` after `.strip()`, else `ValueError("deadline_field must be a non-empty field name")` | which fact carries the clock |
| `deadline_window_hours` | `168` | `_config_count` — integer `> 0`, `bool` rejected | the denominator: what counts as *a full window of time* |

Neither has a budget counterpart. There is no `budget_window` key because the budget's denominator is
a fact — `budget.total_minor` — declared by the source system rather than by the capability author.
That asymmetry is correct: a budget knows its own size, a deadline does not know what a comfortable
lead time is for this kind of work.

`deadline_field` is capability-configurable because *"different domains name their clock
differently; the reasoning is the same"* — `test_the_deadline_field_is_capability_configurable`
retargets it at `meeting.start_at`. `deadline_window_hours` at 168 encodes *a week of lead time is
comfortable*, which is a sales assumption. A support capability with a four-hour SLA would want
`deadline_window_hours: 4`; nothing in the shipped manifests sets it.

**`deadline_window_hours` is validated lazily.** `_config_count` is called *after* the deadline fact
has been found and parsed, so a manifest carrying `deadline_window_hours: 0` runs clean on every
snapshot without a due date and fails the day one appears. Verified. `deadline_field`, by contrast, is
checked on every run because `_deadline` always executes.

---

## 5 · Worked examples

### 5.1 · A quarter of the budget left

```text
facts    budget.total_minor     = 50,000        (£500.00)
         budget.remaining_minor = 12,500        (£125.00)

numerator   min(max(12500, 0), 50000) = 12,500
            12,500 × 10,000           = 125,000,000
divide      divide_half_up(125,000,000, 50,000)
            = (125,000,000 + 25,000) // 50,000
            = 125,025,000 // 50,000
            = 2,500
clamp       2,500

Observation resource.budget_headroom
            metrics       {headroom_bp: 2500, remaining_minor: 12500}
            reason_codes  ("budget_headroom_declared",)
            evidence_ids  ids for budget.remaining_minor and budget.total_minor
```

2,500bp is 0.25 — a quarter of the allowance unspent. Comfortably above the 2,000bp default floor, so
this alone raises no strain. `test_budget_headroom_is_the_unspent_fraction_of_the_declared_allowance`.

### 5.2 · The Northwind budget — £20 of £500

```text
facts    budget.total_minor     = 50,000
         budget.remaining_minor =  2,000

            2,000 × 10,000 = 20,000,000
            (20,000,000 + 25,000) // 50,000 = 20,025,000 // 50,000 = 400

Observation {headroom_bp: 400, remaining_minor: 2000}
```

**400bp, not 4,000bp.** 4% of the allowance. The category README states this figure as 4,000bp; the
code produces 400, and 400 is what the shipped test's `headroom_bp: 357` implies — if the budget were
at 4,000bp the deadline at 357bp would still bind, so the final metric is unaffected either way, but
the intermediate is wrong in that summary.

### 5.3 · Exactly one week of clock

```text
facts            commitment.due_at = 2026-08-13T12:00:00+00:00
evaluation_time  2026-08-06T12:00:00+00:00
config           deadline_window_hours absent → 168

delta            604,800 s
hours_remaining  int(604800) // 3600 = 168
headroom_bp      168 > 0, so _ratio_bp(168, 168)
                 min(max(168,0),168) = 168
                 168 × 10,000 = 1,680,000
                 (1,680,000 + 84) // 168 = 1,680,084 // 168 = 10,000
                 clamp → 10,000

Observation resource.deadline_headroom
            metrics       {headroom_bp: 10000, hours_remaining: 168}
            reason_codes  ("deadline_headroom_declared",)
```

`test_time_headroom_is_measured_against_the_frozen_evaluation_time` asserts the metrics mapping
exactly.

### 5.4 · Six hours of a 168-hour window — Northwind's clock

```text
facts            commitment.due_at = 2026-08-06T18:00:00+00:00
evaluation_time  2026-08-06T12:00:00+00:00

hours_remaining  21,600 s // 3600 = 6
headroom_bp      6 × 10,000 = 60,000
                 (60,000 + 84) // 168 = 60,084 // 168 = 357.64… → 357
```

357bp — 3.6% of a week. Far below the 2,000bp floor, so `resource_headroom_exhausted` fires. And
because the budget's 400bp is above it, the `min` in the Calculator picks the clock: *the clock, not
the money, is the constraint.*

### 5.5 · Missed by three hours

```text
facts            commitment.due_at = 2026-08-06T09:00:00+00:00
evaluation_time  2026-08-06T12:00:00+00:00

delta            −10,800 s
hours_remaining  int(−10800) // 3600 = −3
headroom_bp      −3 ≤ 0 → 0

Observation {headroom_bp: 0, hours_remaining: -3}
            reason_codes ("deadline_passed",)
```

`test_a_deadline_already_past_leaves_no_headroom_but_still_reports_how_far_past`. Note
`hours_remaining` is a **signed** metric that reaches the `Finding` unchanged.
`Finding.__post_init__` range-checks only `_bp`-suffixed names, so a negative survives; had it been
called `hours_remaining_bp` the contract would have rejected it. The naming carries load.

### 5.6 · A retargeted clock

```text
facts    meeting.start_at = 2026-08-09T12:00:00+00:00
config   deadline_field   = "meeting.start_at"

hours_remaining  259,200 s // 3600 = 72
headroom_bp      (72 × 10,000 + 84) // 168 = 720,084 // 168 = 4,286
```

`test_the_deadline_field_is_capability_configurable` asserts `hours_remaining == 72`. The evidence id
cited is the one for `meeting.start_at` — `evidence_ids(view.request, field)` uses the configured
name, so retargeting the field retargets the citation too.

### 5.7 · A narrower window changes the reading, not the fact

```text
facts    commitment.due_at = 2026-08-07T12:00:00+00:00     (24 hours out)
config   deadline_window_hours = 48

hours_remaining  24
headroom_bp      (24 × 10,000 + 24) // 48 = 240,024 // 48 = 5,000
```

Against the default 168-hour window the same deadline would read `(240,000 + 84) // 168 = 1,429`, which
is below the 2,000bp floor and would fire `resource_headroom_exhausted`. Against a 48-hour window it
reads 5,000bp and fires nothing. One config key flips the verdict on identical facts — which is the
point of the key, and also the reason a capability that means something different by *urgent* must
set it deliberately rather than inherit a sales default.

---

## 6 · Edge cases, including three that are wrong

### 6.1 · A deadline less than an hour away reports `deadline_passed`

**Verified.** `commitment.due_at = 2026-08-06T12:45:00+00:00` against a noon evaluation time:

```text
delta            2,700 s
hours_remaining  2700 // 3600 = 0
branch           0 ≤ 0 → headroom_bp = 0, reason_codes = ("deadline_passed",)
```

The reader is told the window closed when there are forty-five minutes left. `headroom_bp: 0` is
arguably defensible — under an hour of a 168-hour window rounds to nothing either way — but
`deadline_passed` is a false statement, and it is the reason code, not the metric, that a card would
render. The fix is to split the two conditions: `headroom_bp = 0 if hours_remaining <= 0`, but
`deadline_passed` only when the delta itself is negative. Not done.

### 6.2 · A missed deadline over-reports by up to an hour

**Verified.** Missed by 3h01m — `due_at = 08:59`, evaluation at `12:00`:

```text
delta            −10,860 s
hours_remaining  int(−10860) // 3600 = −10860 // 3600 = −4        (Python floors)
```

`−4`, not `−3`. Python's `//` floors toward negative infinity, so past readings round *away* from
zero while future readings truncate *toward* it. A deadline 3h59m in the future reads `3`; one 3h01m
in the past reads `−4`. The two directions use the same operator and get opposite rounding, and
nothing in the code says so. Cosmetic for `headroom_bp`, which is 0 either way, but `hours_remaining`
is what a human reads.

### 6.3 · An overspent budget loses its magnitude

**Verified.** `budget.total_minor = 50,000`, `budget.remaining_minor = −4,000`:

```text
_ratio_bp        min(max(−4000, 0), 50000) = 0 → headroom_bp = 0
remaining_minor  max(−4000, 0) = 0

Observation {headroom_bp: 0, remaining_minor: 0}
```

Indistinguishable from a budget spent to exactly zero. Compare the deadline path, which goes out of
its way to keep the sign so a reader can see *how far past*. The same argument applies to money — £40
over on a £500 budget is a different conversation from £4,000 over — and the budget path does not
make it. A one-word change (`remaining` instead of `max(remaining, 0)` in the metric, leaving
`_ratio_bp` to clamp the ratio) would fix it, at the cost of a metric that can go negative.

### 6.4 · Remaining greater than total

`total = 50,000`, `remaining = 60,000` → `headroom_bp: 10,000`, `remaining_minor: 60,000`. The ratio
saturates; the raw figure does not. Over-funding is reported honestly and reads as full headroom,
which is right.

### 6.5 · A one-unit budget

`total = 3`, `remaining = 1` → `(10,000 + 1) // 3 = 3,333`. Integer division on a tiny denominator is
exact enough: 33.33%. There is no minimum denominator, so a `total_minor` of 1 gives a two-valued
headroom — 0 or 10,000. Acceptable, because a budget of one penny is not a budget.

### 6.6 · A deadline beyond the window

`due_at` 336 hours out with a 168-hour window: `hours_remaining: 336`, `headroom_bp: 10,000`. The
numerator clamps at the window, so anything at or beyond a full window reads as full headroom, while
`hours_remaining` keeps the true figure. Saturation at the top, same as the load ratio saturates —
*two weeks out* and *one week out* are both simply *not yet a constraint*.

### 6.7 · Strings and other shapes

| Input | Result |
|---|---|
| `budget.total_minor = "50000"` (string) | accepted — `common.py:integer` parses a `Decimal`-convertible string |
| `budget.total_minor = 50000.5` | rejected by `integer` → `_optional_int` returns `None` → silent |
| `budget.remaining_minor = True` | rejected — `integer` rejects `bool` explicitly → silent |
| `commitment.due_at = datetime(...)` with tzinfo | accepted — `parse_time` takes a `datetime` directly |
| `commitment.due_at = "2026-08-08T00:00:00"` (naive) | rejected — `must be timezone-aware` → silent |
| `commitment.due_at = "2026-08-08T00:00:00+05:30"` | accepted, normalised to UTC → `hours_remaining: 30` |
| `commitment.due_at = "2026-08-13T12:00:00Z"` | accepted — `parse_time` rewrites `Z` to `+00:00` |

Every malformed input degrades to silence. None produces a zero.

---

## Related

| Document | Covers |
|---|---|
| [03-Analyzer.md](03-Analyzer.md) | How this plugin composes with the other two |
| [04-Calculator.md](04-Calculator.md) | The `min` that lets the scarcer of budget and clock bind |
| [05-Evaluator.md](05-Evaluator.md) | `headroom_floor_bp` and the `resource_headroom_exhausted` strain |
| [../../../_reference/Determinism-Audit-Replay.md](../../../_reference/Determinism-Audit-Replay.md) | Why `evaluation_time` rather than `now()` |

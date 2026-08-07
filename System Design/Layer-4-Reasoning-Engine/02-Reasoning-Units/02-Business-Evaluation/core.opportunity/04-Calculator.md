# `core.opportunity` · Stage 5 — Calculator

**Source:** `opportunity.py:OpportunityUnit.calculate` (lines 115–129)
**Overridden by `OpportunityUnit`:** **yes** — `calculate` is `@abstractmethod` on
`ReasoningUnit` (line 213–216); a subclass that omits it cannot be instantiated.

---

## 1 · What it is for

Turn up to three independent claims — each with its own evidence and its own reason code — into one
number meaning *"how much untaken headroom is there here"*, without destroying the fact that they
were separate claims.

The code's own docstring makes the whole argument, and it is an argument about two rejected
alternatives rather than a description of what it does:

> *"Strongest signal leads, others contribute diminishing support.*
>
> *Deliberately not a sum: three weak hints are not a strong opportunity, and averaging would let
> one weak plugin drag down a genuinely ripe one. The strongest claim sets the level and
> corroboration adds a bounded lift."*

Two sentences, two rejections, one rule. §3 works through why each rejection is right.

---

## 2 · The code, in full

```python
def calculate(self, view: UnitView,
              observations: Sequence[Observation]) -> Mapping[str, int]:
    strengths = sorted((int(item.metrics.get("strength_bp", 0)) for item in observations),
                       reverse=True)
    if not strengths:
        return {"opportunity_bp": 0, "opportunity_count": 0}
    lift = divide_half_up(sum(strengths[1:]), 4)
    return {"opportunity_bp": clamp_bp(strengths[0] + lift),
            "opportunity_count": len(strengths)}
```

Six lines. Note what it does **not** do:

- It does not look up any plugin by id or by kind. `core.cost` does
  (`self._observation(observations, "cost.step_effort")`); this unit deliberately does not, which
  is why a fourth plugin needs no change here.
- It does not read `view.config`. Both tuning knobs in this unit live elsewhere — one in a plugin,
  one in the Evaluator. **The blend itself is untunable.**
- It does not read `view.facts`, `view.prior`, or `view.request`. `view` is accepted to satisfy the
  abstract signature and is unused.
- It does not weight the plugins. `core.impact` carries a `_DIMENSIONS` weight table; here every
  observation is anonymous and interchangeable.

### 2.1 · The formula

```text
S = the strength_bp values from every observation, sorted DESCENDING

if S is empty:
    opportunity_bp    = 0
    opportunity_count = 0
else:
    lift              = half_up( sum(S[1:]) ÷ 4 )
    opportunity_bp    = clamp_bp( S[0] + lift )
    opportunity_count = len(S)

where half_up(n, d) = (n + d // 2) // d   for n >= 0        [common.py:79-84]
      clamp_bp(v)   = min(10_000, max(0, int(v)))            [common.py:75-76]
```

The division is applied to the **summed** numerator, once — not per term. Summing three values and
dividing once is not the same as dividing three times and summing: `half_up(3,4) + half_up(3,4) =
1 + 1 = 2`, but `half_up(6,4) = 2`. Here they agree; at other values they do not, and the category
convention is to divide the sum. `_bp`-valued metrics in this repo are always integers, so the
rounding rule has to be stated somewhere and this is where.

### 2.2 · The `strength_bp` default hides a typo

`item.metrics.get("strength_bp", 0)` — a plugin that misspelled the key contributes `0` and still
increments `opportunity_count`. No exception, no reason code. It is the one soft edge in an
otherwise strict unit, and it exists because `calculate` was written to accept plugins it has never
seen.

---

## 3 · Why this shape

### 3.1 · Why not a sum

```text
three weak hints, each 2,000bp
  sum   = 6,000bp   → above every threshold in the system → "strong opportunity"
  this  = 2,000 + half_up(4,000, 4) = 2,000 + 1,000 = 3,000bp
```

*"Three weak hints are not a strong opportunity."* A sum lets quantity substitute for quality, and
in this unit the claims are **correlated** — a deal is usually quiet *because* nobody replied, so
`stalled_but_open` and `unanswered_inbound` fire off substantially the same silence. Summing would
count that silence twice at full weight.

`alternative_unit.py:DoNothingBaselinePlugin` copies this exact shape over `opportunity_bp`,
`drop_bp` and `risk_bp` and names the hazard in its own words: *"Summing would let four weak,
correlated observations out-argue one decisive one."*

### 3.2 · Why not a mean

```text
one ripe claim at 10,000bp, plus a marginal 1,000bp hint
  mean  = 5,500bp   → the hint has halved a maximal signal
  this  = 10,000 + half_up(1,000, 4) = 10,000 + 250 → clamped 10,000
```

*"Averaging would let one weak plugin drag down a genuinely ripe one."* This is the failure mode
that matters most in practice, because the plugins have very different dynamic ranges:
`unanswered_inbound` sweeps 0–10,000 across two weeks, while `unworked_relationship` is a constant
4,000. Under a mean, a 24-hour-old unanswered message on an owned deal would report 10,000bp and
the same message on an unowned deal would report 7,000bp — *more* evidence producing a *lower*
score. Under max-plus-lift it reports 10,000bp either way.

This is the same reasoning `core.impact` uses to justify renormalising over observed weights rather
than averaging over all three dimensions, arriving at a different formula from the same principle:
**the number must mean "how much is there", not "how many things we happened to measure".**

### 3.3 · Why the lift is bounded, and why ÷4

Corroboration is worth something. A deal that is open, unanswered *and* unowned is a better bet than
one that is merely unanswered, and a pure `max()` would report them identically. The ÷4 buys that
distinction back without letting it dominate:

```text
theoretical maximum lift, three plugins   half_up(10,000 + 10,000, 4) = 5,000bp
practical maximum lift, this unit         half_up(10,000 +  4,000, 4) = 3,500bp
```

The divisor is not derived from anything. It is the same divisor `alternative_unit.py` and
`recommendation_unit.py` use for the same shape, so it is at least *consistent* across the three
units that borrow it — `recommendation_unit.py` says so explicitly: *"Same shape as `opportunity.py`,
for the same reason."* Consistency is worth something on its own; it is not evidence.

### 3.4 · Why order-independent, and why sorted anyway

`max` and `sum(rest)` are both commutative, so the arithmetic does not depend on observation order.
The `sorted(..., reverse=True)` is what *establishes* which value is the leader — `strengths[0]`
after a descending sort is the maximum. On ties the arithmetic is unaffected: `[6000, 6000]` gives
`6000 + half_up(6000,4) = 6000 + 1500 = 7500` regardless of which observation sorted first.

Observation order still matters, but downstream: `evaluate_meaning` builds findings in observation
order, and that order is inside `semantic_hash`. That is `analyze`'s `sorted()`, not this one. See
[03 · Analyzer](03-Analyzer.md) §2.1.

---

## 4 · Worked combinations

Every row was produced by running the live unit.

### 4.1 · The canonical case — two plugins

The shipped `sales.deal_cooling_full` v2 fixture:

```text
observations (plugin_id order)
   stalled_but_open       strength_bp 6000
   unworked_relationship  strength_bp 4000

strengths sorted desc  = [6000, 4000]
sum(strengths[1:])     = 4000
lift                   = half_up(4000, 4) = (4,000 + 4 // 2) // 4 = 4,002 // 4 = 1,000
opportunity_bp         = clamp_bp(6000 + 1000) = 7,000
opportunity_count      = 2
```

### 4.2 · Three plugins, no saturation

`tests/test_l4_end_to_end.py`'s situation, with the owner field removed:

```text
   stalled_but_open       8200        engagement collapsed to 1,800bp
   unanswered_inbound     6308        buyer wrote 216 hours ago
   unworked_relationship  4000        constant

strengths          = [8200, 6308, 4000]
sum(strengths[1:]) = 10,308
lift               = half_up(10,308, 4) = (10,308 + 2) // 4 = 10,310 // 4 = 2,577
opportunity_bp     = clamp_bp(8,200 + 2,577) = clamp_bp(10,777) = 10,000    ← CLAMPED
opportunity_count  = 3
```

The clamp bites. Three plugins at moderate-to-high strength saturate the scale, and 777bp of signal
is discarded. That is the intended behaviour — `10,000bp` means "maximal for attention purposes"
and there is nothing above maximal — but it means **the top of this metric compresses**: 10,777 and
14,000 both report as 10,000, so `opportunity_bp` alone cannot rank two saturated situations
against each other. `opportunity_count` is the only tie-break available, and it is coarse.

### 4.3 · One plugin — the lift is zero

```text
strengths          = [8200]
strengths[1:]      = []
sum([])            = 0
lift               = half_up(0, 4) = (0 + 2) // 4 = 0
opportunity_bp     = 8,200
opportunity_count  = 1
```

`sum(strengths[1:])` on a one-element list is `sum([]) == 0`, so the single-observation case needs
no special branch. `divide_half_up(0, 4)` is `(0 + 2) // 4 = 0` — the `+ d // 2` term does not
round `0` up to `1`, because `2 // 4 == 0`.

### 4.4 · No plugins — the early return

```text
observations = ()
strengths    = []
if not strengths: return {"opportunity_bp": 0, "opportunity_count": 0}
```

**Both metrics are published, and `opportunity_bp` is `0`.** Not omitted. §5.

### 4.5 · A zero-strength observation

`unanswered_inbound` at `waiting_hours = 0` emits `strength_bp = 0` (the ramp starts at zero), so:

```text
   unanswered_inbound     strength_bp 0
   unworked_relationship  strength_bp 4000

strengths          = [4000, 0]
lift               = half_up(0, 4) = 0
opportunity_bp     = 4,000
opportunity_count  = 2       ← two observations, one of which is worth nothing
```

Verified. This is why `opportunity_count` is *"how many plugins spoke"* and not *"how many
opportunities exist"* — [README](README.md#6--known-defects-and-compromises) defect 7.

### 4.6 · The full lift table

Leader held at 6,000; the corroborators varied:

| Strengths | `sum(rest)` | `lift` | `opportunity_bp` | `count` |
|---|---|---|---|---|
| `[6000]` | 0 | 0 | 6,000 | 1 |
| `[6000, 1000]` | 1,000 | 250 | 6,250 | 2 |
| `[6000, 4000]` | 4,000 | 1,000 | **7,000** | 2 |
| `[6000, 6000]` | 6,000 | 1,500 | 7,500 | 2 |
| `[6000, 4000, 4000]` | 8,000 | 2,000 | 8,000 | 3 |
| `[8200, 6308]` | 6,308 | 1,577 | **9,777** | 2 |
| `[8200, 6308, 4000]` | 10,308 | 2,577 | **10,000** (clamped from 10,777) | 3 |
| `[10000, 10000, 4000]` | 14,000 | 3,500 | **10,000** (clamped from 13,500) | 3 |

Bolded rows are the ones reproduced against the live unit; the others follow from the same two
lines of arithmetic.

---

## 5 · Silence semantics — where this unit diverges from its sibling

```python
if not strengths:
    return {"opportunity_bp": 0, "opportunity_count": 0}
```

**`core.opportunity` publishes zero. `core.impact` omits.** The two units in the same category, on
the same framework, made opposite calls:

| | `core.opportunity` | `core.impact` |
|---|---|---|
| Nothing observed | `{"opportunity_bp": 0, "opportunity_count": 0}` | `{"impact_signal_count": 0}` — `impact_bp` **absent** |
| Consumer sees | `prior_metric(..., 0)` → `0` | `prior_metric(..., default)` → **the consumer's own default** |
| `matched` | `False` | `None` |

`core.impact`'s docstring argues its side: *"`impact_bp` is omitted entirely when nothing reported,
so a reader gets their own default rather than a manufactured 0."* `opportunity.py` makes no
argument for its side at all — the early return has no comment.

The consequence is asymmetric and real. `tradeoff_unit.py:_prior_bp` uses a `-1` sentinel to detect
absence:

```python
value = view.prior_metric(_config_id(view, key, default_unit), metric, _ABSENT)   # _ABSENT = -1
return None if value == _ABSENT else clamp_bp(value)
```

A missing `impact_bp` returns `None` and `CostVersusBenefitPlugin` goes silent — *"where neither has
been deployed the plugin stays silent rather than treating unmeasured effort as free."* A published
`opportunity_bp = 0` returns `0`, and `RiskVersusRewardPlugin` proceeds to weigh a real risk against
a **stated** zero reward. The tradeoff unit cannot tell "we looked and there is no upside" from
"nothing was measurable", because this unit does not give it the chance to.

The same applies to `cost_unit.py`, whose `do_nothing_cost_bp` folds in
`prior_metric("core.opportunity", "opportunity_bp", 0)` — where a genuine `0` and an absent unit are
already indistinguishable by construction, so the divergence costs nothing there.

Which behaviour is right is arguable. What is not arguable is that two units in one category should
not silently disagree about it, and nothing in the code or the tests records that they do.

---

## 6 · Edge cases

| Input | `opportunity_bp` | `opportunity_count` | Verified |
|---|---|---|---|
| No observations | 0 | 0 | yes |
| One observation, `strength_bp = 0` | 0 | 1 | yes |
| One observation, `strength_bp = 10,000` | 10,000 | 1 | yes |
| Two observations, tied strengths | leader + `half_up(other, 4)` — order-independent | 2 | by inspection |
| Sum exceeds 10,000 | clamped to 10,000; the excess is discarded | unchanged | yes |
| An observation missing `strength_bp` | contributes `0` to the blend, `1` to the count | by inspection |
| A plugin emits two observations | both counted; `count` exceeds the plugin count | by inspection — no current plugin does |
| Negative `strength_bp` | impossible: `_config_bp` bounds one plugin, `clamp_bp` the second, and the curve is `clamp_bp`-wrapped in the third. `clamp_bp` in `build` would floor it at 0 regardless | by inspection |

`divide_half_up` also has a negative branch (`-((-numerator + denominator // 2) // denominator)`),
rounding half **away from zero** symmetrically. It is unreachable from this unit, because every
`strength_bp` is non-negative and `sum` of non-negatives cannot be negative. It exists for
`impact_unit.py`, where an authored `play_impact_bp` delta may be negative.

---

## 7 · Related

- [03 · Analyzer](03-Analyzer.md) — where the `strength_bp` values come from, and their correlation
- [05 · Evaluator](05-Evaluator.md) — the threshold applied to `opportunity_bp`
- [06 · Builder and Metrics](06-Builder-and-Metrics.md) — the second `clamp_bp` in `build`, and every consumer
- [`core.impact` · 04 · Calculator](../core.impact/04-Calculator.md) — the sibling that omits rather than zeroes

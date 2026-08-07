← [The Judgment Taxonomy](01-The-Judgment-Taxonomy.md) · [Folder map](README.md) · → [Exact-Pack Lineage and the Weekly Claim](03-Lineage-and-The-Weekly-Claim.md)

---

# Precision and the Wilson Interval

---

## The Wilson interval — why a raw ratio is not enough

```python
def _wilson_interval(wins, n, z=1.959963984540054) -> (lower, upper)   # 95%
```

A raw precision of `1/1 = 100%` and `47/50 = 94%` are not comparable claims. The Wilson score
interval discounts small samples, and **every decision below uses a bound, never the point
estimate**:

| Decision | Uses | Meaning |
|---|---|---|
| **mute** | `precision_ub < 0.25` | *even the optimistic reading is bad* |
| **recover** | `precision_lb ≥ 0.25` | *even the pessimistic reading is acceptable* |
| **loosen** | `precision_lb ≥ 0.70` | *even the pessimistic reading is good* |
| **tighten** | `precision_ub < 0.40` | *even the optimistic reading is poor* |

**Every threshold is compared against the bound that makes the action harder to take.** That is
the asymmetry that keeps a small sample from doing damage.

---

## The thresholds

```python
WINDOW_DAYS       = 28      # the trailing window
MIN_JUDGMENTS     = 8       # eligible to be nudged at all
MUTE_PRECISION    = 0.25    # the mute / recover line
MUTE_MIN_JUDGMENTS= 12      # a HIGHER bar to mute than to nudge
LOOSEN_ABOVE      = 0.70
TIGHTEN_BELOW     = 0.40
OFFSET_STEP       = 5       # one step per week
OFFSET_BOUND      = 15      # ±15 total, ever
```

Two of these encode a policy rather than a number:

- **`MUTE_MIN_JUDGMENTS` (12) > `MIN_JUDGMENTS` (8).** **Silencing a rule requires more evidence
  than tuning it**, because a mute stops the rule producing the very judgments that would let it
  recover.
- **`OFFSET_STEP` 5 against `OFFSET_BOUND` 15.** **Three weeks of consistent evidence to reach
  the ceiling, in either direction.** Learning may nudge; it may never redefine.

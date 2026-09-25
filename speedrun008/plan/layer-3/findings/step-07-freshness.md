# L3-07 · The Freshness Manager — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ Half the premise held; the other half was wrong for the fifth time

| the plan said | measured |
|---|---|
| *"`freshness_policy_id` — zero writers, zero readers"* | ✅ **TRUE.** It appears **exactly once in the entire repo**: its own declaration in migration 0004 |
| *"reinforcement ≠ repetition — a forward of a six-month-old delegation must not reset it"* | ⛔ **already built**, and at L1, fail-closed |
| *"no double decay — one owner per transformation"* | ⛔ **no double decay exists** |

### 1.1 · GE-HCS-05 is handled, and handled better than the spec asks

`capture/validate/confidence.py` implements **Rule 11**, the echo rule:

> *"`ConfidenceSource.independence_key` has **no default**: every caller must state an origin or
> state `None`, and everything that states `None` lands in ONE group that can only `combine`… a
> composer that guessed independence from two different `source_ref` values would treat a forwarded
> email and its own quoted original as two witnesses, which is precisely the echo Rule 11 is
> about."*

And `corroborate` **raises** rather than warns when asked to lift a confidence with no name
attached, while `enforce_rule_11` **clamps** at the outer boundary and records that it did, because
*"a clamp nobody can see is a ceiling that was never really there."*

### 1.2 · And there is no double decay, because L1's is a read view

`age_signals` returns `AgedSignal(row=row, days_old=…, confidence_bp=decay(…))` and **leaves
`row.confidence_bp` untouched**. The stored confidence is never itself decayed, so `reason/engine`
is not decaying an already-decayed number.

Its own docstring says why: *"`decay` is CALLED, not re-derived: a second copy of that curve here
would be two answers to how fast evidence goes stale."*

---

## 2. ⛔ What a BEHAVIOURAL test found that no text assertion could

There are **two** staleness curves, and they are different function families:

| owner | question | shape |
|---|---|---|
| `capture.validate.confidence` | how much less certain is **this extraction** because the message is old | **linear**, basis points per day, applied as a **read view** |
| `reason.engine` | how much less should **this fact** weigh in **this rule's** decision | **exponential** |

**That divergence is correct** — two questions, two owners — and **nobody had written it down**,
which is §J's *"assign each transformation one owner and record its contribution"*. An unrecorded
divergence is one refactor from being "unified", or from a third appearing because neither looked
authoritative.

### 2.1 · ⛔ AND THE PARAMETER IS MISNAMED

```python
def _freshness(occurred_at, eval_time, *, half_life_days: float = 30.0) -> float:
    return math.exp(-age_days / max(1.0, half_life))
```

`exp(-age / T)` is an **e-folding time constant, not a half-life.**

```
  0d -> 1.0000
 15d -> 0.6065
 30d -> 0.3679      ⛔ the configured "half life" — 36.8%, not 50%
 60d -> 0.1353
```

**The curve's true half-life is `half_life_days × ln2` ≈ 20.8 days when a pack configures 30.**

A pack author reading `freshness_half_life_days: 30` reasonably expects half the weight after a
month and gets **37%**, so **every value they tune is roughly 30% out from their intent.**

⛔ **My first draft of this test asserted `"half_life" in src` and went green when the parameter was
renamed** — the word survived in the body. The curve is a *shape*, so it is now pinned by its shape.
**That is the eighth time in this project a text assertion looked right and could not fail, and the
first time switching to behaviour found a live defect rather than just a weak test.**

### 2.2 · Neither half is changed, and that is the point

| | why not |
|---|---|
| fix the **formula** | moves the confidence term of **every decision this product has ever made** — a behaviour change with no measurement behind it |
| fix the **name** | `freshness_half_life_days` is a **pack config key**; renaming breaks authored packs |

**Both are product decisions with a blast radius.** The actual behaviour is pinned, the misnomer is
documented where the function lives, and the choice is **routed to the handoff** rather than taken
quietly.

---

## 3. The dead column, pinned dead

`graph_facts.freshness_policy_id` has no writer and no reader since migration 0004.

⛔ **The honest treatment is not to build something onto it.** Freshness already has two owners; a
per-fact policy pointer is a **third design nobody has asked for**. It is pinned dead so the next
person who finds it **does not read an empty column as an unfinished feature and start filling it
in** — which is how a third staleness opinion would arrive by accident.

---

## 4. Result

```
FULL SUITE   13,216 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-07: 13,208 passed · 14 failed
```

**+8 tests · 0 regressions · no migration · no model call.**

**Technique 3 — five mutations, all red:** `age_signals` writes back; L1 reimplements the curve;
the curve becomes a true half-life; the curve becomes linear; something touches the dead column.

## 5. What this step does NOT do

* ⛔ **It does not build a Freshness Manager.** Freshness has two owners and both work. A third
  would be the over-scaffolding refused at L3-01, L3-03, L3-05 and L3-06.
* ⛔ **It does not change a single score.** `exp(-age/T)` is untouched.
* **It does not drop the dead column.** A migration with risk and no benefit.

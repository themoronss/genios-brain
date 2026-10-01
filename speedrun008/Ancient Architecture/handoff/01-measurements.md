# 📊 Measurements — six scripts, all read-only

**Every one is a `select`.** The target resolves through `scripts/_db.py`, which has no fallback
to `Settings`: *"nothing in the invocation names production; you get it by running the script at
all."*

Run each, **paste what it prints into this file under its heading.** Several decisions in
[`02-decisions.md`](02-decisions.md) cannot be made until the number beside them exists.

---

## M1 · What Layer 2 refused, and why

```bash
python scripts/l2_refusal_report.py --org <pilot-org-id> \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

**The denominator for every Layer 2 number.** Until it runs, every later claim is measured against
an unknown.

It prints: admitted / held / rejected · **every hold reason including zeros** · *"its best evidence
scored 1360 against a floor of 2500"* per held situation · the domains no corpus can read · **`BY
LAW`**, which is what arms V-9 and V-10 (decision **D2**).

> The corpus half already ran without a database and found the plan's number wrong by 3.4× —
> `--corpus-only` if you want to see it.

**Output:**
```
(paste here)
```

---

## M2 · What a context slice actually costs

```bash
python scripts/slice_weight.py --org <pilot-org-id> --sample 20 \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

**L2-5's entire cost check rests on this.** It builds each slice *exactly the way the sweep does*,
so what it weighs is what the reasoner would be handed.

⛔ Measured already, on constructed shapes: **8 facts → 714 tokens** (the plan's *"900-token
slice"*), **100 facts → 8,049** (the plan's *"10,000-token thread"*). **The saving comes from the
node being small, not from the slice being a slice.** This run says how many of the pilot's
situations break the 2,000-token line.

**Output:**
```
(paste here)
```

---

## M3 · What no authored corpus can read

```bash
python scripts/unroutable_report.py --org <pilot-org-id> \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

Per **(domain, situation type)** — because a corpus is authored per type, and the totals differ by
an order of magnitude inside one domain. Feeds decision **D3**.

**Output:**
```
(paste here)
```

---

## M4 · What the founder actually sees  ⛔ *needs 0182*

```bash
python scripts/card_collapse_report.py --org <pilot-org-id> \
       --database-url "$GENIOS_TARGET_DATABASE_URL"
```

⛔ **The headline number of the whole Layer 2 plan.** *"38 cards becoming N"* has been a claim
since the plan was written and nothing has ever printed the ratio.

It **refuses to report at all** without 0182, rather than printing a collapse of 1.00 and letting
somebody conclude there is nothing to merge.

**Output:**
```
(paste here)
```

---

## M5 · The relevance and domain-coverage queries

Three of Layer 1's six metrics are marked **`⛔ unmeasurable`** because the pilot corpus no longer
exists. These two queries are what would move them, on whatever corpus exists now:

* the domain-coverage query — `speedrun008/plan/layer-1/step-06-domain.md` §3
* the relevance query — `speedrun008/plan/layer-1/step-08-importance-relevance.md` §3

**Output:**
```
(paste here)
```

---

## M6 · ⛔ The shadow pass's tallies — the Layer 2 cutover gate

`reason/domain_shadow.shadow_compile` has been running on **every sweep**, counting, and reporting
to nobody. Read `counts` from a sweep on the pilot.

⛔ **The gate that judges them was written BEFORE anyone looked**, deliberately — *"a threshold
picked post-hoc is not a gate"* — and `reason/cutover.PARITY_MEASURED_AT` is `None` with a test
asserting it, so the thresholds are provably older than the numbers.

| rule | reads | needs |
|---|---|---|
| no unroutable errors | `error` | ≤ 0 |
| nothing fails to persist | `persist_error` | ≤ 0 |
| most situations compile | `compiled` | ≥ 100 |
| reasoning reaches the same rows | `reasoned` | ≥ 100 |
| no reading crashed | `reasoner_failed` | ≤ 0 |

An **absent** tally fails the gate — *"`None` is not a low number, it is nobody having measured"* —
so it cannot pass on a pass that never happened.

```python
from genios_engine.reason.cutover import evaluate_parity
evaluate_parity(counts)     # → .passed and .failures
```

**Output:**
```
(paste here)
```

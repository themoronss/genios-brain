# Step 3 — ✅ DONE · activated is not the same as ran

> **Tree:** `M12.C2.U03` · 14 tests · ⛔ **the activation row itself stays Rohit's**

## 1 · What the unit bundled, and the split

| | Who |
|---|---|
| the admin activation row for the pilot | **Rohit / Harsh** — a row, not code |
| a receipt that the **live** pass, not the shadow pass, actually ran | **us**, and nothing checked it |

## 2 · ⛔ Why the second half is not ceremony

`platform/l3_activation` shipped once with a reader, a fail-closed gate, an erasure row, an admin API and
a report — **and no caller.** Plane R's notes record the lesson in one line:

> *"a switch that reports itself on and changes nothing is worse than no switch."*

So once the row exists, nothing today would tell anybody whether it did anything.

## 3 · What was built — and the column already existed

`reasoning_runs.mode` answers it exactly:

- migration 0026: `check (mode in ('live', 'shadow', 'simulation', 'replay'))`
- `domain_shadow` writes `ExecutionMode.LIVE if live_row else ExecutionMode.SHADOW`
- `if not live_row: continue` sits **before** `_persist_live`, so only the live lane persists

⛔ **So the receipt counts live runs, not activation rows.** Counting activation rows would prove the
switch was flipped; counting live runs proves it did something. One receipt, registered beside the other
25.

## 4 · Verify

```
$ uv run --no-sync pytest tests/platform/test_activation_changes_the_pass.py -q
..............                                                           [100%]
14 passed in 0.41s
```

## 5 · ⛔ Two attempts at one assertion, both mine, both the blunt-grep family

The test *"only the live lane persists"* had to be rewritten twice:

1. It searched the module for `_persist_live(` and matched the **function definition** at line 411
   instead of the call at 1218.
2. Scoped to `outcome = _persist_live(`, it read 900 characters backwards — and the guard is ~1,000
   characters above it, behind a comment block.

⛔ The L0 doctrines name this family exactly: *"assert on structure — the AST, the column list — never on
text that happens to sit near a thing."* The third version walks the **AST** for
`If(test=Not(Name('live_row')), body=[..., Continue])` — which is the guard itself, wherever it moves to.

## 6 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| the receipt | registered at L4 | ✅ |
| what it counts | ⛔ `reasoning_runs.mode = 'live'`, **not** `l3_activation` | ✅ |
| 0 live runs | fails | ✅ the state the pilot is in |
| 1 or more | passes | ✅ |
| with an org | `:org`-filtered | ✅ unfiltered would report another tenant's runs |
| `fleet_wide` | **False** | ✅ the answer differs per tenant by definition |
| the fleet run | drops the filter, does not fake one | ✅ |
| the detail | names the defect it guards | ✅ |
| the `mode` vocabulary | asserted **against migration 0026** | ✅ so code and schema cannot drift |
| the shadow lane | ⛔ refused **before** persist, checked on the AST | ✅ |
| receipt count | 23 → **26** | ✅ 2 organisation + this one |
| any duplicated claim | none | ✅ |

## 7 · For Rohit

Insert the activation row. Then this receipt is how you know it mattered — and if it stays red, the
switch is on and nothing is using it, which is the defect this step exists to surface.

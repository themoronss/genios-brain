# Step 1 — ✅ DONE · prove the claims before changing anything

> **Tree:** `M11.C0.U01` · **Section S1** · 14 tests
> **Outcome: the claim this layer's plan was built on is FALSE. `M11.C1` loses its justification.**

---

## 1 · What was expected

`speedrun008/YCW27/03-PROGRAM.md:92` calls one thing *"the live defect"*:

> `M11.C1` dependency-complete plans — plan compile fails when a scheduled unit declares a source no
> other scheduled unit produces. **This is the live defect that leaves two of `core.risk`'s three
> plugins silent.**

## 2 · What is actually true

⛔ **Not supported, in every part of the sentence.**

| The claim says | Measured |
|---|---|
| `core.risk` has **three plugins** | **one** unit id matches `core.risk`. There is no plugin layer under a reasoner id — the sentence describes a structure this codebase does not have |
| **two** of them are **silent** | `core.risk` completed **1,165 of 1,165**. Zero silent |
| it is a **live defect** | 20 of 22 units speak. The two that do not are explained below, and neither is this |

```
THE CLAIM UNDER TEST — 03-PROGRAM.md:92
  "the live defect that leaves two of `core.risk`'s three plugins silent"
  ⛔ THE CLAIM NAMES THREE PLUGINS. 1 unit id(s) match `core.risk`: ['core.risk'].
  units found: 1   silent: 0   []
  ⛔ NOT SUPPORTED as written
```

## 3 · ⛔ And the bigger finding: none of it is measurable yet

The per-unit table **begins after the outage**:

```
REASONING RUNS, by era and mode
  after   mode=live  n=4329
  before  mode=live  n=3303

PER-UNIT RESULT ROWS (reasoning_reasoner_results)
  26396 rows, 2026-09-29 11:07:43 .. 2026-09-30 10:39:04
  ⛔ THIS TABLE BEGINS 3 DAY(S) AFTER THE OUTAGE STARTED.
```

`reasoning_runs` goes back to **19 Sep**. `reasoning_reasoner_results` starts **29 Sep 11:07** — three
days after the API spend limit began refusing every model call on **25 Sep 11:09** (L1 STEP-04).

⛔ **So every per-unit number in this layer was taken with the model off.** A unit silent because the
model never answered and a unit silent because its source was dropped are the **same rows**.

`--assert-measured` therefore **exits 1**, by design:

```
$ .venv/bin/python scripts/l2_unit_silence.py --assert-measured; echo $?
ANSWERABLE AT ALL: NO
1
```

That is the gate working. A verify command that passed here would be asserting the question is
answerable when it is not.

## 4 · What the 22 units actually do

| Verdict | Units |
|---|---|
| **SPEAKS** | 20 — `alternative` `confidence` `constraint` `context` `cost` `dependency` `impact` `opportunity` `planning` `priority` `recommendation` `resource` `risk` `scheduling` `temporal` `timeline` `tradeoff` `validation` `legacy.rule` `legacy.score_gate` |
| **SILENT BY DESIGN** | `core.policy` — all 53 rows are `skipped` / `no_declared_input_available` |
| ⛔ **UNATTRIBUTABLE** | `core.relationship` — 0 of 585 completed; 53 skipped by design, **532 `insufficient_context`** |

### The two worth naming

**`core.policy`** — never completed, and that is **correct**. Every row is `_select` receipting a unit
with nothing left to read. `plan.py:229` records at length why dropping it is right and why the
stricter rule was removed.

⛔ **`core.relationship`** — 532 `insufficient_context` rows and **not one completion.** This is the
closest thing to the claimed defect, and it is **not** `core.risk` and **not** a dropped source: the
unit *ran* and declined to assert, 532 times. But every row is outage-era, so it **cannot be
attributed**. This is the one thing to re-measure once the spend limit is raised.

**Two units carry heavy by-design skipping**, worth knowing but not defects: `core.resource` 1,137 of
1,165 skipped; `core.scheduling` 1,033 of 1,165 skipped.

## 5 · ⛔ The probe found two bugs in itself, both of which had already produced a wrong verdict

**Bug 1 · it asked the wrong question about the clock.** The first draft gated on whether *runs*
predated the outage. They do — 3,303 of them. So it answered **"ANSWERABLE: yes"** and labelled every
unit `NEVER SCHEDULED`, while the evidence it was reporting was entirely outage-era.

> ⛔ **That is the L1 `no_model_wired` mistake, reproduced by the script written to avoid it.** Runs are
> not the evidence; result rows are. Fixed by querying the result table's own span.

**Bug 2 · "silent by design" checked every REASON instead of every ROW.** `core.relationship` has 53
by-design skips and 532 `insufficient_context` rows. Looking only at non-null `skip_reason_code`
labelled it **SILENT BY DESIGN** and hid the 532 — which are the interesting ones.

> `skipped` means the unit never ran. `insufficient_context` means it **ran and declined**. Different
> facts, and only the first can be "by design".

**Bug 3 · the expected-silence set was half the rule.** It held only `dependency_not_scheduled`.
Measured: that reason has **zero** rows and `no_declared_input_available` has **3,102 of 26,396** — so
the set would have called every one of those 3,102 a defect. Both are the same rule applied to the two
kinds of input (`plan.py:258` and `plan.py:266`).

Two smaller ones, both found by running it: Postgres refuses a bare NULL parameter
(`AmbiguousParameter`), and `reasoning_runs` has `started_at`, not `created_at`.

## 6 · Verify

```
$ uv run --no-sync pytest tests/scripts/test_the_silence_probe_refuses_to_guess.py -q
..............                                                           [100%]
14 passed in 0.08s
```

The tests cover the pure verdict function, and **every one corresponds to a wrong verdict the first
draft actually produced against real data** — which is why they are tests and not comments.

## 7 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| rows only in the outage era | ⛔ `UNATTRIBUTABLE`, never a verdict | ✅ |
| the same rows in the clean era | a real finding | ✅ `SILENT` |
| a unit that completed, outage-era | speaks, **but flags its failures as unattributable** | ✅ |
| a by-design skip | not a defect | ✅ and it cites `plan.py:229` |
| both `_select` branches | both by design | ✅ |
| `insufficient_context` beside a by-design skip | ⛔ **not** by design | ✅ the 532 are no longer hidden |
| a unit with no rows at all | not called silent | ✅ `NO ROWS` |
| clean-era rows exist | outage rows must not dilute them | ✅ |
| the script's writes | none | ✅ `read only`, and no `insert`/`update`/`delete` in the source |
| `GENIOS_ALLOW_PROD_WRITE` | never set | ✅ asserted |
| `--assert-measured` today | ⛔ exit **1** | ✅ |

## 8 · What this does to the plan

| Unit | Before | After |
|---|---|---|
| `M11.C1.U01` (as `03-PROGRAM.md` wrote it) | *"the live defect"* | ⛔ **the justification is withdrawn.** It was already a regression (see `02-PLAN.md` S2); now it has no evidence either |
| `M11.C1.U01a/b/c` (the receipt, as `02-PLAN.md` rewrote it) | justified by the claim | ✅ **still justified, on its own merits** — a kept unit that lost a source records nothing, and `core.resource` at 1,137 of 1,165 skipped is exactly the population where that would matter |
| `M11.C1.U02` | build a `SkippedStep` receipt | ✅ **confirmed already built** — 3,102 rows carry it |

⛔ **S2 survives, and for a better reason than it was given.** The receipt is not needed because
`core.risk` is broken — it is not. It is needed because 3,102 skips are recorded and **zero** partial
losses are, and `core.relationship`'s 532 declines cannot today be told apart from a model outage.

## 9 · For Rohit — one thing, and it is the same thing as always

⛔ **Raise the Anthropic spend limit.** Until then:

- `core.relationship`'s 532 non-completions cannot be diagnosed
- no unit's silence can be attributed
- **this step's own verify gate stays at exit 1**

Re-run `.venv/bin/python scripts/l2_unit_silence.py --assert-measured` once the limit is raised and
one sweep has completed. It will pass when the question becomes answerable, and not before.

## 10 · For Harsh — nothing

No production code changed. One read-only script added.

---

## The correction to make in `03-PROGRAM.md`

Line 92's sentence should be deleted or replaced with:

> Measured 2026-09-30: `core.risk` is one unit, not three plugins, and it completed 1,165 of 1,165.
> 20 of 22 units speak. `core.policy` is silent by design. `core.relationship` returned
> `insufficient_context` 532 times and completed never — **but every per-unit row postdates the model
> outage, so nothing here is attributable yet.**

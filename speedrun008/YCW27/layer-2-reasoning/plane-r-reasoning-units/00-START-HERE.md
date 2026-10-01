# Plane R — `reason/reasoners/` · S5 · **STEP 01 COMPLETE**

**Read in this order:** `../06-L2-VERIFICATION.md` (every Atlas claim re-measured) →
`01-CROSSCHECK.md` → `02-PLAN.md` → `STEP-01-DONE-the-unit-source-contract.md`.

| | |
|---|---|
| Units built | **8** — `S5.U01`–`U08`, bottom-up, level 0 → 3 |
| Tests | **45** |
| Measured change | `validate_sources()` went from checking **0** sources to **10**, on every registration |

---

## The hierarchy this plane is built along — counted, not invented

```
PLANE R                                               25 files · 7,820 lines
├── GROUP 1 Situation Understanding   4 units · 14 plugins
├── GROUP 2 Business Evaluation       5 units · 17 plugins
├── GROUP 3 Optimization              5 units · 16 plugins
├── GROUP 4 Decision Support          3 units ·  9 plugins
│                                CORE = 17 units · 56 plugins
└── SUPPLEMENTARY                     6 units ·  0 plugins
                               TOTAL = 23 units
```

| Rohit's word | In this code |
|---|---|
| group | the 4 categories of the frozen architecture |
| section | a unit — `core.risk`, `core.tradeoff` |
| function | a plugin — `CostVersusBenefitPlugin` |
| component | one source binding — `('cost_source', 'core.cost', 'effort_bp')` |
| unit (the atom) | one declaration, one verify command |

---

## ⛔ The one sentence that justifies this section

`tradeoff_unit.py:55`, written by whoever found it:

> *"this unit has been **comparing two axes while declaring three** since the day it shipped. Nothing
> failed, because **a missing source is indistinguishable from a source that did not run**."*

The bug had already happened. The constants were already named for the check — `risk.py` says *"so the
registration check can prove they name units that exist"*. **The one line joining them did not exist.**

---

## ⛔ ALARMS — carried forward, none of them closed by this step

| | | |
|---|---|---|
| 🔴 | **A1** | the Atlas dossier for this layer was **6 weeks stale in 5 of 8 claims** — ✅ **corrected** in `Rohit_Updates/.../04-Layer-4-Reasoning/00-CORRECTIONS-2026-10-01.md` |
| 🔴 | **A2** | the **20-unit roster is built, budgeted, dependency-complete — and no tenant has ever run it.** `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. Largest built-and-not-called surface in the product |
| 🔴 | **A3** | the Organisation Brain's `blocked_play_ids` lever **works** and `learned_brain_entries` is **empty** — a policy mechanism that has never carried a policy |
| 🟠 | **A5** | `core.tradeoff` would compare **1 of 6** axes on the live lane today. `U08` pins it |
| 🟠 | **A6** | `or ""` yields an empty source string rather than a refusal on a manifest that forgets |
| 🔴 | **A8** | **5 migrations unapplied; `0190` breaks card writes** |

## What is left in Plane R after this

⛔ **Nothing in S5.** The section was 3 units as planned, became 8 at unit level, and all 8 are green.

What remains in the plane is **not S5 and not engineering**:

1. **A2 — switch the roster on.** It is built. Activation is a runbook step and your call.
2. **A3 — populate the Organisation Brain.** The lever works; nothing has ever travelled down it.
3. **A5 — schedule `core.tradeoff`'s sources** before switching it on, or it compares one axis.

---

## ⛔ CORRECTION to `ALARM A5`, measured 2026-10-01 against production

`A5` said the live lane *"schedules none of `core.impact`, `core.cost`, `core.opportunity`"*, so
`core.tradeoff` *"would compare 1 of 6 axes if switched on today"*.

**Wrong on the premise, right on the consequence.** All three units **have completed thousands of
times in production** — `core.cost` 1,973, `core.impact` 1,973, `core.opportunity` 1,088. Twenty units
have run. The roster is live far more widely than any document said.

⛔ **And `core.tradeoff`'s `cost_vs_benefit` axis has still fired ZERO times in 1,200 rows** — for a
different reason: `core.impact` completes on every run and publishes **nothing**
(`impact_signal_count: 0`), so the `benefit_source` metric is absent. The alarm was right that the
axis is blind; it was wrong about why, and the real reason is worse.

Full measurement: `../07-DOES-IT-ACTUALLY-WORK.md`.

# Layer 2 — start here

`reason/` — 118 files, 40,065 lines. `packs/` — 34 files, 7,957 lines. **48,022 lines.**

**The primary layer.** It answers: *given professional expertise and everything the company already
knows, what does this mean — and what is the best next move?*

**Milestone M11.** Status: **S1 COMPLETE** — 1 done, 1 retired, **15 left of 18 units.**

⛔ **The unit count went from 11 to 18** after Plane R and Plane D were measured. The plan's first draft
had written both out of scope on the grounds that *"nothing in the cross-check found a defect there"* —
it had not looked. Each has one.

👉 **[`04-STEPS.md`](04-STEPS.md) is the full list of all 18 units, in order.**

| Section | Units | Status |
|---|---|---|
| [S1 · Prove the claims](STEP-01-DONE-prove-the-claims.md) | 2 | ✅ **COMPLETE** — 1 done, [1 retired](STEP-02-RETIRED-skip-receipt.md) |
| **S5 · Plane R — the unit contract** | 3 | ⬜ **next** · 23 units, **0 declare what they read** |
| **S6 · Plane D — routing + the draft corpus** | 4 | ⬜ · 155 capabilities, 23 draft situations, 5 unrouted types |
| S2 · The `DegradedStep` receipt | 3 | ⬜ |
| S4 · The five pipeline counters | 2 | ⬜ |
| S3 · The output lanes + router | 4 | ⬜ |
| S7 · The ConfidenceVector axes | 0 | ⛔ **Rohit** — blocks M13, not M11 |

---

## ⛔ Why this is "layer 2" but comes AFTER layer 3

```
  data flows:   L1 capture ──▶ L3 context ──▶ L2 reason ──▶ L4 ──▶ L5 ──▶ L6
  we build:     M9         ──▶ M10        ──▶ M11       ──▶ M12 ──▶ M13 ──▶ M14
```

The product layer **numbers do not follow the data flow.** Build order is the data flow, because
nothing above can be fed better than the layer below hands up.

> **For the rest of this programme: "next layer" means next in the DATA FLOW, never next number.**

---

## Read in this order

| File | What it is | Lines |
|---|---|---|
| [`01-CROSSCHECK.md`](01-CROSSCHECK.md) | what is actually true in the code, every number with its command | 354 |
| 👉 [`04-STEPS.md`](04-STEPS.md) | **every step, in order — start here for the list** | 140 |
| [`02-PLAN.md`](02-PLAN.md) | the plan: 7 sections → 17 functions → 18 units, with *why* for each | 711 |
| [`README.md`](README.md) | the layer's architecture — four parts, two planes, the one rule between them | 106 |
| [`plane-r-reasoning-units/`](plane-r-reasoning-units/) | **how** a professional thinks | — |
| [`plane-d-domain-expertise/`](plane-d-domain-expertise/) | **what** a professional knows | — |

`03-FINDINGS.md` and the STEP files get written as the build proceeds.

---

## ⛔ The headline: two of the four specified units are wrong

`03-PROGRAM.md` gave M11 four units. The cross-check found:

| Specified | Verdict |
|---|---|
| plan compile **fails** when a scheduled unit names an unproduced source | ⛔ **REGRESSION.** `plan.py:229` records removing exactly this rule — it cost **six units to one absent fact** |
| a dropped unit leaves a `SkippedStep` naming its missing input | ⛔ **already built AND already tested.** Unit retired; no code and no test written |
| *"two of `core.risk`'s three plugins are silent"* | ⛔ **MEASURED AND FALSE.** `core.risk` is **one** unit, not three plugins, and it completed **1,165 of 1,165** |
| the five output lanes + router | ✅ **stands** — genuinely missing (`"investigation"` = 0 hits) |

Plus one addition: **the five pipeline counters do not exist** (0 hits for all five).

---

## The plan, in one table

| | Section | Units | What |
|---|---|---|---|
| **S1** | Prove the claims first | 2 | ⛔ may **delete** work rather than add it |
| **S2** | A kept unit that lost a source says so | 3 | a **receipt**, never a refusal |
| **S3** | The five output lanes + router | 4 | new vocabulary, two naming constraints |
| **S4** | The five pipeline counters | 2 | without a funnel nothing here is diagnosable |
| **S5** | ⛔ The ConfidenceVector axes | 0 | **Rohit's decision.** Blocks M13, not M11 |

---

## What Rohit has to decide

| # | Decision | Recommendation |
|---|---|---|
| 1 | **ConfidenceVector axes** — code's 6 vs Atlas's 6, only 2 overlap | ⛔ **keep the code's six, correct the Atlas.** The code refuses to compose an axis nobody measured, so adopting `causal` and `authority` means two axes `None` forever. Rename cost measured: 3 construction sites, 0 migrations, 2-6 files per axis |
| 2 | **Name the lane concept `output_lane`, never a bare `lane`** | ⛔ yes — `reason/uncited_lanes.py` already means something else by "lane", and that conflation *"lost Layer 2 five readings"* |

Neither blocks S1. **S1 can start on a yes to nothing.**

---

## ⛔ The pattern, three layers running

> **This codebase's comments record decisions its planning documents do not. Read the comment before
> you "fix" the code.**

| Layer | The false finding | What the code's own comment said |
|---|---|---|
| L1 | `no_model_wired` — 632 failures looked like broken wiring | one lane is model-free **on purpose** (`screen_promoter.py:183`) |
| L3 | "nothing guards the graph revision" | `reason/runner.py:570` is the guard, with 6 passing tests |
| L2 | "plan compile should fail on an unproduced source" | it used to, and it **cost six units to one absent fact** (`plan.py:229`) |

# STATUS — where the whole programme stands

**One page. Read this first, always.** Updated **2026-09-30**.

---

## ⛔ WHICH LAYER ARE WE ON? — the one-line answer

> ⛔ **EVERY SECTION IS BUILT.**
> L1 ✅ · L3 ✅ · L2 S1–S4 ✅ · **S6 Plane D ✅** · **S5 Plane R ✅** · L4 ✅ · L5 ✅ · L6 ✅
>
> **What remains is not engineering: 3 activation decisions, 5 unapplied migrations, and review.**
> See the ALARM table at the foot of this page.

### Why the numbers look backwards

The product layer **numbers do not follow the data flow.** We build in data-flow order:

```
data flows:   L1 capture ──▶ L3 context ──▶ L2 reason ──▶ L4 exec ──▶ L5 deliver ──▶ L6 learn
we build:     M9         ──▶ M10        ──▶ M11       ──▶ M12     ──▶ M13        ──▶ M14
done?         ✅ built      ✅ built       ✅ S1–S4      ✅ built    ✅ built      ✅ built
                                          ⏸ S5, S6 yours
```

So *"layer 1, then layer 3, then layer 2"* is correct and deliberate — **nothing above can be fed
better than the layer below hands up.** Recorded in `tree.yaml` as `requested_order`.

> **From here on, "next layer" means next in the DATA FLOW, never next number.**

---

## The whole programme at a glance

| | Layer | Package | Milestone | Units | Built | Left | Docs |
|---|---|---|---|---|---|---|---|
| 1 | Enterprise Signals | `capture/` | M9 | **10** | 10 ✅ | 0 *(3 pending are not code)* | 5 + 10 steps |
| 2 | **Reasoning** | `reason/` + `packs/` | **M11** | **33** | 27 ✅ + 3 ⛔ | **0** | 7 + 14 steps |
| 3 | Context Graph | `context/` | M10 | **5** | 4 ✅ + 1 ⛔ withdrawn | **0** | 5 + 5 steps |
| 4 | Executive | `executive/` | M12 | **4** | 4 ✅ | **0** | 5 + 4 steps |
| 5 | Delivery | `deliver/` | M13 | **4** | 4 ✅ *(1 rewritten)* | **0** | 5 + 4 steps |
| 6 | Learning | `feedback/` | M14 | **3** | 3 ✅ *(1 narrowed)* | **0** | 5 + 3 steps |

**Code written this session:** 17 new modules + **26 new corpus files**, 3 migrations, 37 files
modified, **~926 new tests.** Full suite **14,397 passed / 1 failed** (the 1 is L1's known
`pytesseract`-missing test, which fails on any machine without the binding).

⛔ **Corrections 12 and 13 are on MY OWN cross-check**, not the programme's plan — both caught by
continuing to measure while building, and both recorded as appended retractions rather than edited in
place. #13's cause is the sharpest lesson so far: **a stale comment is more dangerous than no comment,
because it reads as a measurement somebody already took.**

⛔ **NINETEEN corrections to the programme's own planning documents**, every one from reading code or
running a query *before* writing anything:

| # | Layer | The document said | The code said |
|---|---|---|---|
| 1 | L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| 2 | L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| 3 | L2 | plan compile should fail on an unproduced source | it did — **six units to one absent fact** |
| 4 | L2 | the skip receipt needs building | it was already built |
| 5 | L2 | `core.risk` never fires | it does |
| 6 | L2 | Plane D is not in scope | it is where the routing lives |
| 7 | L2 | the lane belongs in `decision_hash` | it is **derived** — zero information, four broken replays |
| 8 | L4 | never read `manager_seat_id` | it is the **standing line** the dated override sits on |
| 9 | **L5** | replace the scalar publication floor | **there is none in `deliver/`** — the gate is in `reason/` and its receipt is already read |
| 10 | **L6** | make a timing complaint stop lowering precision | **it already does not**, in three places, one going further than asked |
| 11 | **Plane D** | the unrouted types need a runtime counter | **they have one** — missing its DIMENSION, and a FOURTH cause was being mis-reported |
| 12 | **Plane D** | `unrouted_l2_types` is hand-kept | ⛔ **my own cross-check was wrong** — `index.py:205` generates it |
| 13 | **Plane D** | a draft situation may not compile a card | ⛔ **my own cross-check was wrong** — already built, 15 tests. **I believed a stale corpus comment** |
| 14 | **Plane D** | 13 Admin objects are missing | **9** — my regex truncated three hyphenated ids that were already authored. `domain.yaml`'s roster is authoritative |
| 15 | **Plane D** | `unrouted_l2_types` is hand-kept | `_tools/index.py:205` generates it — *(same as #12, found twice from different angles)* |
| 16 | **Plane R** | a guard is waiting for declarations | ⛔ **the guard RUNS on every registration and validated ZERO** — nothing needed wiring |
| 17 | **Plane R** | *"the two `AXIS_SOURCES` units"* | there is **one** |
| 18 | **Plane R** | *"`source_units` on `legacy.score_gate`"* | it reads **no source at all** |
| 19 | **Atlas dossier** | 8 claims about the reasoning layer, audited 2026-08-22 | ⛔ **5 of 8 STALE** — corrected in `Rohit_Updates/.../04-Layer-4-Reasoning/00-CORRECTIONS-2026-10-01.md` |

**Nothing committed. Nothing deployed.**

---
---

# LAYER 1 — `capture/` — ✅ our work is DONE

**9 steps. 6 done by us. 3 pending, and not one of them is code in this repo.**

| # | Step | Status | Owner | Blocks build? |
|---|---|---|---|---|
| 1 | Relevance judgment | ✅ DONE — no defect; probe built | us | — |
| 2 | `temperature` on refusing models | ✅ DONE — 600 calls that never worked | us | — |
| 3 | Provider-refusal alert | ✅ DONE — a 5-day outage was invisible, twice | us | — |
| 4 | **API spend limit** | ⏳ **PENDING** | **Rohit** | ❌ no — blocks *measurement* |
| 5 | Where the four objects live | ✅ DONE — rule + 4 guards | us | — |
| 6 | The signal bundle | ✅ DONE — 5 units | us | — |
| 7 | The evidence-need door | ✅ DONE — 4 units | us | — |
| 8 | **OCR has never run** | ⏳ **PENDING** | **Harsh** | ❌ no |
| 9 | **The 60-day window** | ⏳ **PENDING** | **Harsh** | ❌ no |

**139 tests.** Files: `00-START-HERE` · `01-CROSSCHECK` · `02-PLAN` (328 lines) · `03-FINDINGS` ·
`10-LAYER-REFERENCE` · 9 STEP files · `findings/` (3 probes).

### ⛔ What is NOT done in Layer 1, stated plainly

| # | Left | Whose | Why it is not ours |
|---|---|---|---|
| 1 | Raise the Anthropic spend limit | Rohit | a setting on the account. No code in this repo can move it |
| 2 | Deploy from the Dockerfile so OCR runs | Harsh | the fix is a deploy, not a change |
| 3 | Backfill 60 → 365 days | Harsh | an ops run. Migration `0184` is already applied |
| 4 | Wire the executor's `fetchers` to real connectors | Harsh | needs live connector credentials |
| 5 | Re-base the parity gate (100 of 66 is unreachable) | Rohit | a target nobody can hit is not a gate |

⛔ **The consequence of #1, and it is the biggest single caveat in this programme:** since
**2026-09-25 11:09 UTC** every model call has been refused. **Every production number taken since
then — including Harsh's shadow-pass tallies — was taken with the model off.**

---
---

# LAYER 3 — `context/` — ✅ COMPLETE

**5 steps. 4 built, 1 withdrawn because the finding behind it was wrong. 0 left.**

| # | Step | Status | Tests |
|---|---|---|---|
| 1 | The bounded query API | ✅ **DONE** | 22 |
| 2 | Compare-and-set on write | ⛔ **WITHDRAWN** — already built | — |
| 3 | A hold that asks | ✅ **DONE** | 27 |
| 4 | A met need clears its hold | ✅ **DONE** | 22 |
| 5 | Residue reaches the sweep | ✅ **DONE** — and wired | 20 |

**91 tests. `tests/context` whole: 2,679 passed, 0 failed.**

### What Layer 3 can now do that it could not

| | Before | After |
|---|---|---|
| ask the graph a bounded question | ❌ whole tenant only | ✅ seeds, hops, node cap, edge types |
| know a read was cut short | ❌ silently partial | ✅ `truncated_by` names the cap |
| turn a hold into a question | ❌ the reason went to a ledger and stopped | ✅ `hold_needs.py` |
| act on an answered question | ❌ nothing read the outcome | ✅ 4 dispositions |
| file a question at all | ❌ nothing persisted a need | ✅ called by the sweep |

### ⛔ What is NOT done in Layer 3 — the loop is HALF-CLOSED

```
residue ──▶ need ──▶ [ evidence_needs table ] ──▶  ???
   ✅         ✅            ✅ written             ❌ nothing works them
```

| # | Left | Whose |
|---|---|---|
| 1 | Apply `migrations/0187_evidence_needs.sql` — **never run in production** | Harsh |
| 2 | The executor pass: `read_open_needs` → `execute` → `close_need` | Harsh — needs real `fetchers` |
| 3 | Wire `hold_needs` into the publisher — **needs a decision first** (inside the publication transaction, or a later pass reading the ledger; the second is safer) | Rohit / Harsh |

⛔ **So today the queue is write-only.** Every filed need stays `open`, so `resolve_hold` returns
`keep_waiting` for all of them. **Nothing regresses** — situations hold today anyway — but
**`evidence_needs_filed > 0` must NOT be read as "something is being fetched."**

---
---

# LAYER 2 — `reason/` + `packs/` — 📋 PLANNED, NO CODE

**This is where we are. 48,022 lines — the second-largest surface in the product.**

**⛔ 18 units across 7 sections. 10 BUILT, 1 retired, 7 left — and the 7 are BOTH PLANES ONLY.**

⛔ **Everything except Plane R (S5) and Plane D (S6) is built.** On Rohit's instruction the two planes
are last and will be done unit by unit together. **264 new tests** across S1–S4.

⛔ **The count went 11 → 18** after Plane R and Plane D were measured. The plan's first draft had
written both out of scope saying *"nothing in the cross-check found a defect there"* — it had not
looked. Each has one, and the Plane R defect is the sharpest thing in the layer: **23 units, zero
declare what they read**, while `registry.py:49` exists specifically to check that.

👉 **Full list: [`layer-2-reasoning/04-STEPS.md`](layer-2-reasoning/04-STEPS.md)**

⛔ **S1's first unit is done and it did what S1 exists for: it destroyed a claim.**
`scripts/l2_unit_silence.py` measured production read-only and found `core.risk` is **one** unit (not
three plugins) which completed **1,165 of 1,165** — zero silent. The sentence `M11.C1` was built on
describes a structure this codebase does not have. See
[`layer-2-reasoning/STEP-01-DONE-prove-the-claims.md`](layer-2-reasoning/STEP-01-DONE-prove-the-claims.md).

| | Section | Units | What | Blocked? |
|---|---|---|---|---|
| **S1** | Prove the claims before changing anything | **2** | ✅ **COMPLETE** — 1 done, 1 **retired** | — |
| **S2** | A kept unit that lost a source says so | **3** | ✅ **DONE** · 38 tests · a receipt, never a refusal | — |
| **S3** | The five output lanes + router | **4** | new vocabulary | needs S4 |
| **S4** | The five pipeline counters | **2** | ✅ **DONE** · 42 tests · ⛔ `signals_detected` refused rather than faked | — |
| **S3** | The five output lanes + router | **4** | ✅ **DONE** · 170 tests · totality both directions | — |
| **S5** | ⛔ **Plane R — the unit contract** | **3** | 23 units, **0 declare what they read** | ⬜ **NEXT — unit by unit with Rohit** |
| **S6** | ⛔ **Plane D — routing + draft corpus** | **4** | 155 capabilities, 23 draft situations, 5 unrouted types | ❌ no |
| **S7** | The ConfidenceVector axes | **0** | ⛔ **Rohit's decision.** Blocks M13, not M11 | ⛔ yes |

**Files written:** `00-START-HERE` (87) · `01-CROSSCHECK` (354) · `02-PLAN` (451) · `README` (100).
**No STEP files yet** — those get written as each step is built, the same as L1 and L3.

### ⛔ The headline: 2 of the 4 specified units were WRONG

| `03-PROGRAM.md` said | Verdict | What the plan does |
|---|---|---|
| plan compile **fails** when a scheduled unit names an unproduced source | ⛔ **REGRESSION.** `plan.py:229` records removing exactly this rule — *"six units lost to one absent fact"* | **rewritten as a receipt** |
| a dropped unit leaves a `SkippedStep` naming its missing input | ✅ **already built** — `plan.py:258` | **verify, don't build** |
| *"two of `core.risk`'s three plugins are silent — the live defect"* | ⛔ **UNVERIFIED.** No source anywhere; unmeasurable while the API limit is on | **measure or withdraw, first** |
| the five output lanes + router | ✅ **stands** — `"investigation"` = 0 hits | build it |

**One addition found:** the five pipeline counters do not exist (**0 hits** for all five). Without a
funnel, *"we made 28 cards"* cannot be told apart from *"28 out of 4,000, and 3,900 died somewhere
nobody can name."*

### What is left in Layer 2 — all 11 units

| Section | Unit | What |
|---|---|---|
| S1 | `M11.C0.U01` | ✅ **DONE** — the claim is false, and no unit silence is attributable yet |
| S1 | `M11.C1.U02` | ⛔ **RETIRED** — the code AND a passing test already existed. No code, no test written |
| S2 | `M11.C1.U01a` | the `DegradedStep` receipt contract |
| S2 | `M11.C1.U01b` | compute it in `_select`, **provably without changing what is kept or dropped** |
| S2 | `M11.C1.U01c` | carry it to the decision's `uncertainty` — ⛔ *not done until a human can read it* |
| S3 | `M11.C2.U01` | the lane vocabulary, closed enum |
| S3 | `M11.C2.U02` | the router — pure, deterministic, **no model** (a lane is a route) |
| S3 | `M11.C2.U03` | the totality guard, both directions |
| S3 | `M11.C2.U04` | the lane on all five `DECISION_PROJECTIONS` |
| S4 | `M11.C3.U01` | the counter table — ⛔ **a zero is written, not skipped** |
| S4 | `M11.C3.U02` | five writers, one per layer. Never a central collector |

---
---

## ⛔ WHAT ROHIT HAS TO DECIDE — 2 things, neither blocks S1

| # | Decision | My recommendation |
|---|---|---|
| 1 | **ConfidenceVector axes.** Code: `evidence`·`freshness`·`consistency`·`identity`·`coverage`·`analytic`. Atlas: `evidence`·`frame`·`temporal`·`causal`·`authority`·`coverage`. **2 of 6 overlap** | ⛔ **Keep the code's six, correct the Atlas.** Cost measured: **3 construction sites, 0 migrations**, 2–6 files per axis. But `identity` → `authority` is **not a rename — it is a different measurement.** And the code **refuses to compose an axis nobody measures**, so `causal` and `authority` would be `None` forever |
| 2 | Call the lane concept **`output_lane`**, never a bare `lane` | ⛔ **yes** — `reason/uncited_lanes.py` already means something else by "lane", and that exact conflation *"lost Layer 2 five readings"* |

**Still open from earlier, not blocking:** correlation placement, and "is a layer the package or the
product layer" (`02-DECISIONS.md`). Object placement and the revision-guard naming are settled.

---

## ⛔ WHAT HARSH HAS TO DO — 5 things, none blocking us

| # | Task | From |
|---|---|---|
| 1 | Deploy from the Dockerfile — **OCR has never run** | L1 STEP-08 |
| 2 | Backfill 60 → 365 days | L1 STEP-09 |
| 3 | Apply `migrations/0186_signal_bundles.sql` | L1 STEP-06 |
| 4 | Apply `migrations/0187_evidence_needs.sql` | L3 STEP-05 |
| 5 | Write the executor pass with **real connector `fetchers`** | L1 STEP-07 + L3 STEP-05 |

⛔ **#5 is the one that matters most.** Until it exists, L1 and L3 built a complete question-asking
pipeline that asks and never listens.

---

## Three unsound verifies, named so nobody trusts them

| # | Problem | Status |
|---|---|---|
| 1 | `tests/platform/test_migrations_apply.py` **does not exist** and is named by 3 units | ⛔ **open** — so `0186`, `0187` and the coming `0188` have no automated proof they apply |
| 2 | `tree.yaml` has **two blocks with `id: M11`** — an old retired one and the L2 one | ⛔ **open** — an id is never reused. Flagged, not silently fixed |
| 3 | `M11.C1.U01`'s row in `tree.yaml` still describes the **regression** | ⛔ **open** — the plan rewrites it; the tree row has not been edited yet |

---

## ⛔ The pattern — three layers, three false findings

> **This codebase's comments record decisions its planning documents do not. Read the comment before
> you "fix" the code.**

| Layer | The false finding | What the code's own comment said |
|---|---|---|
| L1 | `no_model_wired` — 632 failures looked like broken wiring | one lane is model-free **on purpose** (`screen_promoter.py:183`) → *"a count without its dimension is not a measurement"* |
| L3 | "nothing guards the graph revision" | `reason/runner.py:570` **is** the guard, 6 passing tests → *"a guard lives with the reader, not the writer"* |
| L2 | "plan compile should fail on an unproduced source" | it used to, and it **cost six units to one absent fact** (`plan.py:229`) |

---

## THE NEXT ACTION

⛔ **Everything except the two planes is done.** Per Rohit: both planes last, unit by unit, together.

**Layer 2, Section S5 — Plane R's unit contract**, 3 units. **23 of 23 reasoning units declare nothing
about what they read**, while `reason/registry.py:49` exists specifically to check that and names the
pattern it was written for. `tradeoff_unit.py:59` has that literal `AXIS_SOURCES` map naming **six unit
ids**; `legacy_gate.py:23` hardcodes `prior_results.get("legacy.rule")`. None declares anything, so
`validate_sources()` validates an empty set — **a guard that passes because it has nothing to check.**

Then **S6** — Plane D, 4 units: 155 capabilities (all stable), 23 draft situations, 5 unrouted Layer 2
types the corpus already declares.

---

## Migrations waiting on Harsh — 4, none applied

| Migration | From |
|---|---|
| `0186_signal_bundles.sql` | L1 STEP-06 |
| `0187_evidence_needs.sql` | L3 STEP-05 |
| `0188_pipeline_counters.sql` | L2 STEP-04 |
| `0189_output_lane.sql` | L2 STEP-05 |

Every write against them is inside `try/except` and logs, so nothing breaks while they are missing —
and nothing is measured either.

---

## ⛔ Running score on this programme's own planning documents

| Layer | Planned | What it turned out to be |
|---|---|---|
| L3 | `M10.C1.U03` compare-and-set | **already built** — `reason/runner.py:570`, 6 passing tests |
| L2 | `M11.C1.U01` fail on unproduced source | **a regression** — `plan.py:229` removed it for measured reasons |
| L2 | `M11.C1.U02` skip receipt | **already built AND already tested** |
| L2 | *"two of `core.risk`'s three plugins silent"* | **false** — one unit, not three; 1,165 of 1,165 completed |
| L2 | *"Plane D is not in M11's scope"* | **wrong** — nobody had looked. S5 and S6 exist because of it |
| L2 | `M11.C2.U04` the lane on all five projections | **trimmed to one** — the audited row already carries it |
| L2 | *"a routed decision is a different decision, so the lane belongs in `decision_hash`"* | ⛔ **wrong, and it was mine.** `route()` is a pure function of fields already in the hash, so the lane adds **zero** information. **Four replay tests in three files I never touched** caught it |

**Seven corrections in two layers.** Six came from reading the code or running a query before writing
any. **Three came from tests catching my own fresh code**, and those are the ones worth noting:

| Caught by | What was wrong |
|---|---|
| my own new test | the bounded reader returned an edge to a node it refused to contain |
| a **pre-existing** test | `DegradedStep` refused the single most important case it existed to record — a REQUIRED unit running on none of its sources |
| **four pre-existing replay tests** | the lane in `decision_hash` broke every bundle's verification. A derived value has no business in a content hash |

⛔ **This is why the full suite runs before a step is called done.** The last one was caught by tests in
three files this work never touched, asserting a property I did not know I was breaking.

---
---

# LAYER 4 — `executive/` — ✅ COMPLETE

**4 units, 77 new tests.** `01-CROSSCHECK` · `02-PLAN` · `00-START-HERE` · 4 step docs.

| # | Unit | What it is |
|---|---|---|
| 1 | `M12.C1.U01` | the reporting line resolves — dated `reports_to` first, then the `manager_seat_id` column |
| 2 | `M12.C1.U02` | an unroutable tenant says **why**, with a named fix, and distinguishes `MISSING` from `UNKNOWN` |
| 3 | `M12.C2.U03` | the activation receipt — 3 new receipts, including *"the live pass has actually run, not only the shadow pass"* |
| 4 | `M12.C2.U04` | activity is not outcome — `done_but_unproven` never reads as `COMPLETED` |

⛔ **Correction #8:** the plan said never to read `manager_seat_id`. It is the **standing line** the
dated override sits on — `assignment.manager_of` reads `reports_to` first and falls through to it.

⛔ **The topology test PASSED on an unsafe import** (`platform` → `executive`) because `platform` is
exempt. *"An import nothing fails the build on is not a safe one; it is an unchecked one."* The SQL
moved to `platform/org_readiness_sql.py`.

⛔ **`org_seats` has no `channel` column.** My first CHANNELS query could never have run and would
have reported `unknown` forever. There is no per-seat channel in the schema at all, and a channel
receipt already existed — mine was dropped rather than duplicated.

---
---

# LAYER 5 — `deliver/` — ✅ COMPLETE

**4 units, 91 new tests.** `01-CROSSCHECK` · `02-PLAN` · `00-START-HERE` · 4 step docs.

| # | Unit | What it is |
|---|---|---|
| 1 | `M13.C2.U03` | the lane reaches the card — `lane_display.py`, `0190`, pipeline, builder, store |
| 2 | `M13.C2.U04` | ⛔ **rewritten** — the recall guard, `lane_recall.py` + 1 receipt (27 total) |
| 3 | `M13.C1.U01` | the claim extractor — sentences tagged with the existing `ClaimState` |
| 4 | `M13.C1.U02` | the validator, per claim — `invention_ok` **called**, never reimplemented |

⛔ **Correction #9:** `U04` said to replace the scalar publication floor. **There is none in
`deliver/`.** The score gate is `reason/runner.py:1133` and its receipt is already read by
`executive/explain.py`.

⛔ **We created a defect and found it one step later.** `signals.output_lane` had **zero readers in
`deliver/`** — built, tested, green, called by nothing, the eighth instance and the first of our own.

⛔ **Three real bugs my own tests found:** `str(OutputLane.DECISION)` is `"OutputLane.DECISION"`, so
every in-process caller would have been labelled `unrouted`; the tally and the label gave two answers
to one question; and the tally was counting a population nobody received.

### ⛔ What you have to do

**`0190` must be applied.** Fifth unapplied migration (`0186`–`0190`). Until then `cards.output_lane`
does not exist and `insert_card` **fails on write**.

---
---

# LAYER 6 — `feedback/` — ✅ COMPLETE

**3 units, 53 new tests.** `01-CROSSCHECK` · `02-PLAN` · `00-START-HERE` · 3 step docs.

| # | Unit | What it is |
|---|---|---|
| 1 | `M14.C1.U01` | eleven reasons, one layer each — `contracts/learning_attribution.py` |
| 2 | `M14.C1.U02` | the card offers exactly what the API accepts, and all five readers moved together |
| 3 | `M14.C1.U03` | ⛔ **narrowed** — the layer debit, plus the first guard over what already worked |

⛔ **Correction #10:** *"a timing complaint never lowers a correct rule's precision"* was **already
true in three places**, one going further than the milestone asked.

⛔ **The widening would have broken it in both directions.** `units.py` branched on one literal, so
four new "the card was right" reasons would have debited accuracy; and `_PRECISION_SQL`'s two-reason
list would have left four real quality failures **counted by nothing**. Both closed.

⛔ **The topology gate caught my own `contracts/` violation** — it imported `LAYERS`, and *"contracts/
may depend on platform/stdlib only."* Same lesson as `capture → context` in L1.

### ⛔ What is yours to decide

**Eleven radio buttons under "Wrong" is a worse experience than three.** A founder asked to classify
*our* failure will pick the first plausible option. The eleven are right as a **machine** vocabulary;
whether all eleven are **shown** is your call. `_WRONG_REASON_GROUPS` gives a surface four headings a
person can pick, and narrowing the display is a one-line change — never a change to the vocabulary.

**`BUILDER_VERSION` was bumped** to `card-builder.v6-lane-and-eleven-reasons`, so every untouched card
in production is recomposed on the next sweep. That is the documented behaviour of the field, and it
is how the lane and the new reasons reach cards a founder is already looking at.

---
---

# ⛔ ALARMS — what is left, and whose

**Nothing below is engineering. Every item is a decision, a deployment, or a review.**

| | | Whose | Why it bites |
|---|---|---|---|
| 🔴 | **A8 · 5 migrations unapplied** (`0186`–`0190`) | **Harsh** | ⛔ `0190` makes `insert_card` **fail on write**. The other four degrade quietly; this one does not |
| 🔴 | **A2 · the 20-unit roster has never run** | **Rohit** | `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. Built, budgeted, dependency-complete, unswept — the largest built-and-not-called surface in the product. Activation is a runbook step |
| 🔴 | **A3 · the Organisation Brain lever is empty** | **Rohit** | `blocked_play_ids` → `core.constraint` **works**; `learned_brain_entries` has had machinery since `0045` and nothing has produced a proposal. A policy mechanism that has never carried a policy |
| 🟠 | **A5 · `core.tradeoff` would compare 1 of 6 axes** | **Rohit** | the live lane schedules none of `core.impact`, `core.cost`, `core.opportunity`. Schedule them **before** switching it on. `S5.U08` pins the gap so it cannot widen silently |
| 🟠 | **A6 · `or ""` instead of a refusal** | mine, on request | `core.confidence` / `core.priority`: a manifest that forgets `source_reasoner` gets an empty source string. Safe today; changing it changes behaviour, so it is its own unit |
| 🟠 | **14 Sales paragraphs carry your name, unread** | **Rohit** | `plane-d-domain-expertise/PENDING-REVIEW-sales-failure-modes.md` |
| 🟠 | **5 unrouted L2 types have no owner** | **Rohit** | `commitment_unresolved`, `founder_bottleneck`, `meeting_preparation_gap`, `relationship_going_cold`, `vendor_renewal_decision` |
| 🟡 | **97 objects + 283 heuristics are `draft`, 0 hashed** | **Rohit / Harsh** | now **measured** per package (`unreviewed_object_ids`), not invisible. Gating it is a decision with a number under it |
| 🟡 | **ConfidenceVector axes** | **Rohit** | 3 options; recommendation **A** — keep the code's six, correct the Atlas |
| ⚪ | **Nothing is committed** | **Rohit** | 300+ files in the working tree, last commit `c7cdf4c1` predates this session |

---
---

# D · 2026-10-01 · the tenth finding — a gate that could never go green

A, B and C examined nine of the ten receipt findings. The tenth was L4's *"the score components are
measured, not placeholders"*, failing at 59, and it turned out to be a **different defect shape from
any of the nine**: a correct question asked with no date on it.

**What was actually wrong.** The defect it detects was real — 59 candidates where `impact`, `risk` and
`effort` were all the forbidden 5000 neutral default, and for **53 of them all five** ranking
components, so the whole formula was one constant. **And it was closed on 2026-09-08** by commit
`75096bab`. The last affected row is `2026-09-07 23:55` — the day before. 34,167 candidates since,
zero frozen.

`reasoning_candidates` is append-only and this codebase soft-deletes only, so those 59 rows are
permanent and the receipt returned 59 **forever**. `api/routes.py:161` computes `ready = not failed`
over it, so one unfixable receipt was holding the release gate shut for a defect that no longer exists.

> ⛔ **A receipt over append-only history needs a lower bound, or it is not a gate but a monument.**

**What landed.** `ClosedDefect` in `reason/unit_health.py` — the third declared fact there, and the
first carrying a **boundary** instead of a mover, because a closed defect needs nobody to act but does
need to be recognisable if it returns. It demands the commit that establishes the date, so the boundary
is never one somebody chose. The L4 receipt reads it through `_PLACEHOLDER_COMPONENTS_SQL`, keeping its
three equalities byte-for-byte and adding exactly one clause. 17 tests, including two that prove the
predicate was not weakened and one that proves the receipt can still fail.

    the D receipt                 PASS, value 0
    29 receipts, fleet-wide       21 PASS   7 FAIL   1 ERROR     (was 21 / 8 / 1)

### ⛔ The result worth more than the receipt

**Not one remaining receipt failure is a mis-asked question.** Every FAIL and the one ERROR is now a
true statement about a real gap with a named mover — which means the operator page can be trusted for
the first time, and every item on it is on the ALARMS table below rather than in the code.

### ⛔ ALARM D-A1 — recorded as a bound, not raised as a fix
Six of the 59 rows were `disposition=eligible` candidates ranked on a formula that was entirely
constant, inside `org_2f1bc0f366a149e18bd17b06`. **Any card delivered from those 59 was ranked by
nothing.** Nothing is live — they predate the 2026-09-25 freeze — but if that org's card history is
ever used as training or evaluation data for L6 learning, these 59 are not evidence. Whose: **Rohit**,
at the point L6 reads history.

---

# E · 2026-10-01 · the suite's one red test, read at last

It had been carried all session as *"L1's known `pytesseract`-missing test"*. **The product was
right; the test was measuring the host.** `tesseract_available()` requires the Tesseract binary
**and** the Python bindings; the test stubbed only the binary and then asserted an engine comes
back, so it passed where `pytesseract` happened to be installed and failed where it was not.

**And the unstubbed half is the half that actually broke production** — the deploy image once gained
the apt packages while the bindings were in no requirements file, and every scanned document came
back `ocr_failed: ModuleNotFoundError`. **No test covered that**, proved by mutation: with the
bindings check replaced by `return True` the old suite stayed green. Three new tests now catch it.
Product code untouched.

    tests/capture/documents/test_ocr_enablement.py    19 passed   (was 18 passed, 1 failed)

### ⛔ ALARM E-A1 — this made nothing readable
`[L1] attachments carry readable text` **still FAILS at 872**. The test was measuring the host; the
receipt is measuring the deploy image, and it is right to stay red. Whose: **Harsh** — `pytesseract`
and `Pillow` in `requirements`, the apt package in the image, together. Full audit:
`layer-1-enterprise-signals/11-AUDIT-E-the-test-that-measured-the-host.md`, and `STEP-08` section 5
closes its own section 3.

---

## 2026-10-01 · the suite is green for the first time this session

    14,534 passed · 1,063 skipped · 152 xfailed · 0 FAILED        (8m45s)
    29 receipts, fleet-wide:   21 PASS   7 FAIL   1 ERROR

The last red test is gone, and it was never a product defect — see **E** above.

⛔ **The full suite caught two failures the targeted runs could not**, both mine: D's receipt
docstring cited `.../12-AUDIT-D` and the file is `12-AUDIT-D-the-frozen-formula-receipt.md`, so
`tests/test_spec_deferrals_resolve.py` refused it. A comment that cites a record reads as a record
somebody can go and read, and an abbreviated path is indistinguishable from a real one to every
reader except that guard. Fixed by completing the path; recorded in `12-AUDIT-D` PART 9 rather than
edited away. **Two targeted runs are not a suite run.**

### Where the receipts stand, and why this is the line worth reading

| | | Value | Whose |
|---|---|---|---|
| L1 | the parked queue is not a black hole | 1662 | ops — no drain path has been run |
| L1 | every drop we might be wrong about can still be reviewed | 26 | ops |
| L1 | attachments carry readable text | 872 | **Harsh** — bindings in `requirements` + apt in image |
| L4 | at least one seat has a manager | 0 | **Rohit** — no reporting line authored |
| L5 | every delivered card carries a lane | ERROR | **Harsh** — `0190` unapplied |
| L6 | no card gives an order with an empty draft | 18 | spend limit — cards frozen since 09-25 |
| L6 | there is a channel this tenant can be reached on | 0 | **Rohit** — Slack not connected |
| L7 | a human verdict has reached the loop | 0 | **Rohit** — no verdict submitted yet |

⛔ **Not one of these is a mis-asked question.** All ten findings have now been examined across A, B,
C and D: one asked the wrong question (C, the L6 draft receipt, which still fails at **18** because
*a receipt is not fixed by making it green*), one asked a correct question with no date on it (D),
and eight were correct as written — including three I suspected and cleared. Every row above is a
true statement about a real gap with a named mover, which is the first time the operator page can be
read as-is.

---
---

# 2026-10-01 · THE ALIGNMENT PASS, AND THE THREE DOCUMENTS TO READ FROM NOW ON

## ⛔ Read these three, in this order

| | Document | For |
|---|---|---|
| **1** | [`07-LEDGER-every-step-what-why-how-outcome.md`](07-LEDGER-every-step-what-why-how-outcome.md) | **every step in the programme** — the task, why it mattered, what was expected, what actually came out, layer by layer. All six layers, both planes, the five audits, and the doctrine the programme produced |
| **2** | [`HANDOFF-HARSH.md`](HANDOFF-HARSH.md) | **five items for Harsh**, ordered by what they unblock, each with the exact command, the verification query, and what breaks if it is skipped. **H1 is breaking a write path right now** |
| **3** | [`HANDOFF-CODING-AGENT.md`](HANDOFF-CODING-AGENT.md) | **three standalone briefs** plus the twelve rules this repo fails a build over. Two build, one measures first |

## What the alignment pass found

Six places where a label read as a status somebody had checked. The full table is `07-LEDGER` PART 6.
The largest: **seven step files** whose titles said `TO BUILD` while their filenames said `DONE` and
their own bodies carried `✅ DONE — 2026-09-30` with the artifacts named and present. Four in
`layer-3-context-graph`, three in `layer-1-enterprise-signals`.

Also: this file's own README said *"Layer 2 is planned, no code written"*; `02-DECISIONS.md` said
*"all four open"* when **two are closed**; three folders had no `03-FINDINGS.md`; and Plane R had
**eight units built with only one written up** — a built unit with no record is indistinguishable
from one nobody built.

Every title was corrected **only after verifying its named artifacts exist**, and each carries a
dated note saying what it used to say. Nothing was silently rewritten.

## ⛔ Now wired, so it cannot drift again

`tests/test_programme_step_status_is_consistent.py` — **6 tests, each proved by mutation.** Filename
and title must agree; statuses come from a closed set; a **PENDING** step must name its owner;
every layer and plane folder carries all four documents; the folder list is **derived** from where
step files are rather than hard-coded; and the step list must be non-empty so the others cannot pass
vacuously.

## ⛔ Two decisions you can now close cheaply

`02-DECISIONS.md` called four decisions *blocking* — *"every upper layer depends on them."* **All six
layers and both planes were built without #1 and #3 being settled**, because they are about axis
labels and names, not data flow. **#4 was the one that actually blocked, and it blocked because it
was enforceable in a test.**

| | Decision | Yours to do |
|---|---|---|
| **#1** | ConfidenceVector axes | recommendation on record is **A** — keep the code's six, correct the Atlas. Only 2 of 6 overlap, so it cannot be split |
| **#3** | the naming freeze | **nothing is blocked on it.** Every layer was built on the code's names, so this is now a documentation decision. It got cheaper by being deferred |

## State

    full suite              14,540 passed · 0 failed   (14,538 above was taken mid-pass)
    step files              40 · 34 DONE · 3 PENDING · 2 WITHDRAWN · 1 RETIRED
    layer/plane folders     8 · all four documents each
    production receipts     29 · 21 PASS · 7 FAIL · 1 ERROR

⛔ **Still nothing committed.** 300+ files in the working tree; last commit `c7cdf4c1` predates all
of this work.

---
---

# 2026-10-01 · THE ATLAS RE-CHECK · the two planes, re-measured

Full audit: `layer-2-reasoning/13-ATLAS-RECHECK-the-two-planes-and-the-third-silence.md`.

The source was the Atlas's own matrix — `Rohit_Updates/Secret War Updates/08-Cross-Layer-Synthesis/
01-Master-Atlas-vs-Code-Coverage-Matrix.md`, seven layer audits against `harsh/mvp@b739bd5c` on
**2026-08-22**. It is a good document and it is **six weeks old**, so our own rule applied to it:
*a measurement read six weeks later is a claim.* Every number was taken again.

## ⛔ PLANE D IS COMPLETE — and the Atlas's sharpest accusation about it has EXPIRED

| | Atlas · 2026-08-22 | Measured · 2026-10-01 |
|---|---|---|
| **Admin** | *"**Stub.** 57 files, **all 57 stubs**, zero non-stub, zero reviewed/accepted and **zero routes**. No current basis exists for prescriptive Admin expertise"* | **59 capabilities · 59 admitted · 0 hollow · 34 situations** |
| Support | 49 / 40 stubs / 9 non-stub | 49 · all admitted · 0 hollow · 20 situations |
| Sales | 46 / 43 stubs / 3 non-stub | 47 · all admitted · 0 hollow · 15 situations |
| corpus | *"**zero** reviewed or accepted"* | **155 capabilities, every one admitted, 0 hollow** |

Measured with `corpus_health()` — the function the code's own comment points at, not a count of
mine. **Remaining honest gap: 23 DRAFT situations** (Support 16/20, Admin 7/34, Sales 0/15).
⛔ *Corrected 2026-10-01: calling all 23 "unreviewed" was wrong. **Five are reviewed and
approved by harsh** and wait only on `identity.status: draft -> stable`. See `14-PLANE-D-AND-R`.*
A `draft` situation's cards **cannot instruct** and all 23 are flagged, so this is the designed
refusal. ⛔ Whether `draft` should also **gate** is still yours. *(Two earlier records say 24; it is
23 today.)*

## PLANE R — the Atlas's counts were exact; its conclusion has expired

*"Seventeen units are registered; the manifest schedules roughly six"* — **both right.**
`CORE_UNITS` is 17; `BUILTIN_CAPABILITIES` is one capability scheduling 7.

But *"registered is not active"* no longer holds:

    registered in code        23  (17 core + 6 supplementary)
    ever ran in production    22
    never ran                  1  core.signal_composition — DEAL_HEALTH_V1 unswept = ALARM A2
    ran but not registered     0  — the registry and production agree exactly

## ⛔ THE FINDING — and it was one unit

`core.relationship`: **929 runs, 0 completions.** Invisible to the silence receipt, because that
query filters `where status = 'completed'` and a unit with no completed rows is not a low row — **it
is not a row.** Not an unwritten fact either: it binds `deal.status`, which has 3 rows. The fact was
written in prose **twice** and declared nowhere a receipt could read.

Built: `NeverCompleted` — the third grain in `reason/unit_health` — plus a 30th receipt and 17 tests,
mutation-proved. `core.policy` (165 runs, 0 completions) is **excused by derivation**, not by a second
declaration: all four paths it binds are already in `DECLARED_UNWRITTEN`.

    30 receipts, fleet-wide:   22 PASS · 7 FAIL · 1 ERROR     (was 21/7/1 of 29)

### ⛔ ALARM R-A1 · the receipts break `LAYERS.py`'s own rule
All 30 receipts are labelled `L1`–`L7` — **bare digits in the package vocabulary** — and
`GET /health/readiness` returns them as `{"layer": "L2"}`. Against the PRODUCT vocabulary you read,
`L2` is Reasoning; the receipt means Context. `LAYERS.py` states the rule — *"always name the
package, never the digit alone"* — and documents all four vocabularies. Cheap to fix, changes a
response shape, so it is its own unit. **Not done.**

⛔ I nearly filed the folder names as the programme's largest defect. Reading `LAYERS.py` first
stopped it: the YCW27 folders are the PRODUCT column, which that file names as legitimate. Fifth
time in this programme that reading the thing a name points at prevented a false finding.

### What this did NOT fix
`core.relationship` still never completes. The chain is unchanged and still four deep —
`deal.status` 3 of 293 → `core.relationship` 0 completions → `core.impact` 100% silent →
`cost_vs_benefit` 0 fires in 1,200 rows. **Three of the four links are now declared facts rather
than prose.** The connector is **Harsh, H4**.

---
---

# 2026-10-01 · PLANE D AND PLANE R, in the order you asked

Full audit: `layer-2-reasoning/14-PLANE-D-AND-R-the-word-that-was-never-flipped.md`.

## ⛔ PLANE D · five of your "23 unreviewed" are already reviewed

    CAPABILITIES   155   stable + approved  155          nothing waiting
    SITUATIONS      69   stable + approved   46   live
                         draft  + unreviewed 18   need a READER
                         draft  + APPROVED    5   ⛔ need one WORD

All 23 are refused for one reason — `identity_status_draft` — and **not one for missing content**.
Five of them carry `reviewed_by: harsh`, `review_status: approved`, and
**`reviewed_at == last_updated`**, so the approval covers the bytes in the file right now:

    admin.sit.asset_in_custody · admin.sit.employee_lifecycle_event
    admin.sit.obligation_falls_due · admin.sit.spend_against_a_commitment
    customer_support.sit.issue_under_diagnosis

The gate wants **both** `identity.status == "stable"` **and** `review_status == "approved"`. These
have the second. **The review is done; nobody flipped the word** — and commit `90f8edf0` in this
repo is titled, exactly, *"Six situations were finished and nobody flipped the word."* Six then,
five now, nothing counting in between.

**So "23 unreviewed" was a count without its dimension** — my own first rule, broken on my own
status page. It bundled 18 reviews with 5 one-word edits. Corrected in every document and in memory.

### ⛔ ALARM D-A2 · five one-word edits — **yours or Harsh's**
`identity.status: draft -> stable` on those five files. It takes them from *cannot instruct* to
*live*, which is a production-authority change, so I did **not** do it: `identity.status` is the
authoring lifecycle, and flipping it on the strength of `review_status` is the forgery the two-gate
design exists to prevent. `Domain Expertise/_tools/validate.py` now **reports it on every run** with
the reviewer and mover named, and a test pins the set at five — a sixth turns it red.

## PLANE R · ALARM A6 is retired — it was asking for a defect

A6 sat on the table above as *"mine, on request"*. Measured, **all three of its claims are false**:

| | A6 claimed | Measured |
|---|---|---|
| 1 | *"every manifest sets `source_reasoner`"* | ⛔ `sales.deal_cooling` schedules `core.confidence` with the key **absent** — and that is correct |
| 2 | *"the unit reads a prior metric from `""`"* | ⛔ it does not. Both units are `if not source: return None`, **before** any lookup |
| 3 | *"change `or """` to a refusal"* | ⛔ **that would have broken the designed branch.** Falsy is the branch selector: *"no declared source, use the derived path"* |

Retracted in place in `priority.py` with the measurement, and 6 tests pin the behaviour so the
retired claim cannot be acted on later. **A6 comes off the table — not done, not deferred, wrong.**

### The reader for the axis that never fired

    axis_count = 0       16 runs    four zeros, no findings
    axis_count = 1      929 runs   47%
    axis_count = 2    1,028 runs   52%
    axis_count = 3        0 runs   ⛔ a THREE-axis comparator that has never compared three

    speed_vs_certainty  1,897 firings  96%      risk_vs_reward  1,088  55%
    cost_vs_benefit         0 firings  ⛔ NEVER — needs core.impact.impact_bp (absent, declared,
                                        mover Harsh) and core.cost.effort_bp (healthy, 1973/1973)

`scripts/l2_tradeoff_axes.py`, read-only, 8 tests on its pure verdict rule. `axes_unavailable` has
**0 occurrences in 1,973 rows** — every stored row predates the field, so it awaits exercise rather
than having failed, and the probe says which.

⛔ **The probe had two bugs of mine and both looked like findings**: it read the source key as the
axis name (announcing a "6-axis comparator"), and it inferred absence from the declaration list,
reporting the perfectly healthy `core.cost` as a cause. **A declaration list answers "is this
absence declared". It never answers "is there an absence."** Both recorded, both now tested.

## What is left for you, after this

| | Item | Whose |
|---|---|---|
| 🔴 | **the push** — 5 commits ready, clean tree, fast-forward. The classifier blocks me; one line from you | **Rohit** |
| 🔴 | `0186`–`0190` | **Harsh** · H1 |
| 🟠 | **D-A2** · five `identity.status` flips | **you or Harsh** |
| 🟠 | **18 situations to review** | **you or Harsh** |
| 🟠 | `deal.status` writer — it is the single root under `cost_vs_benefit` | **Harsh** · H4 |
| 🟡 | ALARM A2 roster activation (A5 ordering first) | **Rohit** |
| ⚪ | ~~A6~~ | **retired — it was wrong** |

---
---

# ⛔ 2026-10-01 · ALARM D-A2 IS RETRACTED — it was wrong, and the corpus had already said so

**What I told you:** five situations carry `review_status: approved` with `identity.status: draft`,
so *"the review is done and nobody flipped the word"* — five one-word edits waiting on you or
Harsh. It went on the ALARMS table.

**What is actually true.** All five are declared in their domain registry's `pending_l2_types`:

    admin.sit.asset_in_custody · admin.sit.employee_lifecycle_event
    admin.sit.obligation_falls_due · admin.sit.spend_against_a_commitment
    customer_support.sit.issue_under_diagnosis

`tests/packs/test_the_corpus_states_its_own_health.py` says it in its own words — they **MUST NOT
be flipped** — and one of them records that flipping it *"would cost a false assurance"*. For those
five, `draft` + `approved` is **not a half-state**: the content is approved and the lifecycle is
held on purpose, because the L2 type the situation needs does not exist yet.

> **A document in two states is not automatically in a half-state.** Check whether somebody
> declared the combination before calling it an oversight.

**What it cost, and what fixed it.** The validator check I shipped on that reading was crying wolf
on five correct files. `review_done_but_not_flipped()` now takes a `protected` set **read from the
domain's own registry**, and reports **zero**. Warnings 40 → 35.

⛔ **And the first attempt at that fix was itself broken**: it read a name called `registry` that
was a loop variable in scope holding `oid -> path`, so the exemption came back empty and the check
kept reporting all five. A test now asserts the exemption is non-empty, because an exemption that
silently becomes empty is indistinguishable from no fix.

**Eighth time in this programme** that a state was called a defect before the declaration that
created it was read.

## ⛔ What this means for the three I DID flip

It is why they were safe. `campaign_awaiting_reply`, `condition_awaiting_review` and
`organization_gone_quiet` were checked against `pending_l2_types` **before** the flip —
**zero overlap** — and each file records the check. Admin's drafts went 7 → 4, and the four that
remain are four of the five declared-pending above.

    situations that cannot instruct      23 -> 20
    Admin drafts                          7 -> 4     (all four declared pending_l2_types)
    validator "never flipped" warnings    5 -> 0

### So the ALARMS table loses a row
| | Was | Now |
|---|---|---|
| ~~🟠 **D-A2** · five `identity.status` flips, yours or Harsh's~~ | queued work | ⛔ **retracted — the five are correctly held. No action, by anybody.** |

---
---

# 2026-10-01 · THE LIST — what is actually left, and whose it is

⛔ **The table at line 745 is stale.** It lists the push (done, `3e36951b`), D-A2 (retracted — no
action by anybody) and *"18 situations to review"* (collapsed to 3, all 3 accepted). This section
replaces it. The log is append-only, so the old table stays where it is; this one is the live one.

**Nothing below blocks anything else below.** All six layers and both planes are built, the suite
is green at **14,585 passed / 0 failed**, and every remaining item is a deploy, a connector, a
decision or one unit of mine.

## MINE — 1 item

| | Item | Why it is mine | Status |
|---|---|---|---|
| 1 | **readiness axis** — a 7th `ConfidenceVector` axis computed from `capture/coverage`'s readiness model | the only honest way to close Atlas cell **L2-07** (*"role/source-readiness completeness is not part of the blocking vector"*). Unblocked by your **A**. | ready to start — needs your go-ahead, because it **changes behaviour**: a 7th axis binds `overall_bp` through the weakest-axis law |

## HARSH — 5 items, one of them breaking a write path

| | Item | What it unblocks | Brief |
|---|---|---|---|
| H1 | 🔴 **apply migrations `0186`–`0190`** | ⛔ **`0190` — the next card write FAILS without it.** Never run in production. | `HANDOFF-HARSH.md` |
| H2 | 🔴 **OCR stack** — `pytesseract`+`Pillow` in requirements **and** `tesseract-ocr` apt in the image. **Both together or neither works.** | **1,696 rows**: 872 attachments + 824 parked `NEEDS_REFETCH` (half the parked queue) | `HANDOFF-HARSH.md` |
| H3 | 🟠 backfill window 60 → 365 days | history depth for every freshness axis | `HANDOFF-HARSH.md` |
| H4 | 🟠 a **`deal.status` writer** | the single root under `cost_vs_benefit` — that axis has fired **0 times in 1,973 runs** | `HANDOFF-HARSH.md` |
| H5 | 🟡 an **approval-workflow source** | `core.relationship`: 929 runs, **0 completions** | `HANDOFF-HARSH.md` |

## ROHIT — 6 items

| | Item | What it is | Blocking? |
|---|---|---|---|
| R1 | 🔴 **push `e6125684`** | 1 commit, clean tree, fast-forward. The classifier blocks me; one line from you. | no, but it is the record |
| R2 | 🟠 **raise the Anthropic spend limit** | the API has refused **every** model call since 2026-09-25 11:09 UTC. Every production number in this programme is model-off. | nothing is blocked — but no LLM path can be measured until it is lifted |
| R3 | 🟠 **roster activation** (ALARM A2) — ⛔ **ALARM A5's ordering FIRST**: schedule `core.impact` / `core.cost` / `core.opportunity` **before** `core.tradeoff` | `core.signal_composition` has **never run** — 0 runs, which is why `NeverCompleted` refuses `runs <= 0` at construction | no |
| R4 | 🟡 **the 709 `low_relevance` parks** | terminal state, or narrow the receipt? 43% of the parked queue. Not a bug either way — a product call. | no |
| R5 | 🟡 **three Atlas documentation edits** | from your **A**: the Atlas's axis list is wrong, not the code's. `frame_bp`/`causal_bp` have **0 references**; `authority_bp` means three different things in three places. | no |
| R6 | 🟡 **Atlas cell L2-08**, and the **97 `draft` objects** gating question | both are "what should this mean", not "is this broken" | no |

## NOT PENDING — do not re-open these

| | Why |
|---|---|
| ~~ALARM D-A2~~ | **retracted.** The five are declared `pending_l2_types` and the repo's own test says they MUST NOT be flipped. No action, by anybody. |
| ~~ALARM A6~~ | **retired.** All three of its claims were false, and its proposed fix would have broken a designed derived branch. |
| ~~CA1~~ | retired · ~~**CA2**~~ built (`scripts/l2_tradeoff_axes.py`) · ~~**CA3**~~ measured: **zero code gap** in the parked queue |
| ~~the 15 remaining Customer Support situations~~ | domain on hold. Only Admin is in scope. |

---
---

# 2026-10-01 · THE READINESS AXIS — audited, and U1 + U2 BUILT

Atlas cell **L2-07** — *"role/source-readiness completeness is not part of the blocking vector"*.
Unblocked by decision #1 = **A**. Audit and plan:
`layer-2-reasoning/16-AUDIT-AND-PLAN-the-readiness-axis.md`.

## The cell is real, and it has a number

`coverage_bp` — the axis that SOUNDS like readiness — is not readiness. It reads
`context_situations.coverage`, written by `situations.coverage_score(present_fields, expected)`:
**how many of a situation's own expected FIELDS are known.** Source readiness is computed in
`capture/coverage/model.compute_coverage`, enters L1's **four**-component signal vector at
`capture/esqe/publisher.py:415` as `10000 if coverage_ready else 0`, and **stops there.**

    source_coverage      admin FALSE x3 orgs · sales FALSE x3 · support FALSE x3 · fundraising TRUE x3
                         fresh in all three orgs: {calendar, communication}
                         ⛔ `finance` has NEVER been connected -> admin has never been ready
    context_situations   admin 310 · support 73 · sales 61 · fundraising 11 · general 4   (459)
                         103 of the 459 carry coverage = -1, and ALL 103 are admin's

**Admin is the only activated domain, it is 67% of every stored situation, it has never been
coverage-ready, and the blocking vector could not see that.**

## What was built

| | Unit | State |
|---|---|---|
| **U1** | `situations.readiness_score(required, freshness)` — pure, keyword-only, no clock, no connection. Empty `required` returns `COVERAGE_UNKNOWN`, **never 0**. Admin = 50 with `['finance (not connected)']`. | ✅ **DONE** · 8 tests, 3 mutations proved |
| **U2** | the 7th axis on `contracts/situation.ConfidenceVector` + `situations.Confidence`, **declared and NOT composed** | ✅ **DONE** · 6 tests, mutation proved |
| **U3** | `0191_situation_readiness.sql` + the writer + a 31st receipt | ⛔ **BLOCKED on Harsh's H1** — `0186`–`0190` have never run |
| **U4** | whether readiness should COMPOSE | ⛔ **blocked on U3, and it is Rohit's call** |

### ⛔ `overall` did not move, and that is the unit's whole promise

`readiness` is **REPORTED, not composed** — exactly as `coverage` and `analytic` already are.
Admin scores 1-of-2, so composing it would cap `overall_bp` at 5000 on **all 310 admin
situations** through the weakest-axis law. That is two thirds of the corpus re-scored by a line in
a scorer, it is a product decision about what the product should refuse to say, and it is not
answerable before the axis has been stored for a full sweep.

    score_situation(... no readiness row ...)      overall=100  readiness=-1  known=False
    score_situation(... admin's real row ...)      overall=100  readiness=50  missing=['finance (not connected)']
                                                   ^^^^^^^^^^^ identical

### ⛔ The 5000 problem, and why the axis returns a tuple

Admin's honest readiness is 1-of-2 = 50 = **5000 basis points** — the forbidden neutral default
(`reason/decision_maker.py:181`: *"Never substitute 5000."*). A **measured** 5000 is legitimate;
a **substituted** one is the bug; and on a stored column six months later the two are
indistinguishable by inspection. So the missing list travels with the number and U3 stores it.
`ConfidenceVector.composed_from`'s discipline, applied one field down.

## ⛔ F-1 · the axis names were declared THREE times and only two were constants

`context/situation_publisher.py:161` held a **hand-written tuple** of the six names. A seventh
axis added to the contract would have been read by nothing there, published as `None` on every
situation, and **reported as working by every test that only asked the contract**. The publisher
now reads `CONFIDENCE_AXES` and splats the dict, and an AST test keeps it reading it — proved by
mutating it back to a hardcoded list with the *correct seven names*, which the test still caught.

> A vocabulary declared in three places and named in two is not a vocabulary; it is a coincidence
> that has not failed yet.

### The two lists differ by exactly one name, declared

`contracts/situation.CONFIDENCE_AXES` has **7**; `contracts/situation_evidence.CONFIDENCE_AXES`
has **6**. The second is the STORAGE vector and its `complete` property **is the group gate's own
row** ("confidence vector axes present — all 6") taken as a count. Declaring a seventh axis there
before `context_situations.confidence_readiness` exists would turn that gate permanently red for
a reason nobody could look up, because there would be no column to inspect. The divergence is one
unit long and asserted as an **exact set difference**, not a length — a second axis quietly added
to one list would pass a length check on the day it landed.

## Two findings handed to L1 — their own units, not fixed here

| | Finding | Severity |
|---|---|---|
| **F-2** | `compute_coverage` gates on the constant `PACK_REQUIREMENTS` while `declaration.py:163` iterates the function `pack_requirements()` — an authored corpus is asked about, then answered `unknown_domain` with every predicate FALSE, the exact failure `_authored_requirements()` says it exists to prevent. ⛔ **MEASURED: zero authored domains exist, so it is LATENT, not live.** Reporting it as a live bug would have been the ninth time this programme called a state a defect before counting it. | 🟡 latent · 0 rows |
| **F-3** | `coverage_ready` is a **tri-state** and `10000 if coverage_ready else 0` turns `None` into **0** — "we looked and it was terrible" standing in for "we never looked", the one error `AXIS_UNKNOWN_BP` exists to prevent. | 🟠 |

---

# 2026-10-01 · DOC 17 — the three layers, end to end

`17-THE-THREE-LAYERS-end-to-end.md` · 834 lines · **written for Harsh and a coding agent.**
Every number in it was measured read-only against production the same day.

    PART 0   ⛔ the layer numbers are NOT the data flow: L1 -> L3 -> L2 -> L4
    PART 1   what each layer IS — package, size, job, in, out, sub-stages
    PART 2   the flow traced on ONE real email, table by table, plus all 11 seam contracts
    PART 3   the production funnel, measured
    PART 4   what was done per layer + ⛔ the NINE times a state was called a defect first
    PART 5   expected vs actual per layer + ⛔ F-3, a LIVE defect on 141 rows
    PART 6   why this architecture is better — and its honest cost
    PART 7   ⛔ HARSH's five items in full: what each unblocks, how to verify, what NOT to do
    PART 8   the 14 open items with owners
    PART 9   the road to L4, and the crosscheck question it must start from

## ⛔ What writing it found that nothing else had

**F-3 is LIVE, not latent — 141 rows.** `capture/esqe/publisher.py:415` reads
`10000 if coverage_ready else 0`, and `coverage_ready` is a **tri-state**:

    coverage_ready = NULL    141 signals  ->  coverage axis = 0 on ALL 141
    coverage_ready = FALSE   353 signals  ->  coverage axis = 0 on ALL 353
    coverage_ready = TRUE     61 signals  ->  coverage axis = 10000 on all 61

So **141 of 555 qualified signals (25%) assert "we looked and found nothing connected" when the
truth is "nobody ever assessed it"** — and they are indistinguishable from the 353 that are
honestly FALSE. 494 rows look the same and 141 of them are a different fact. This is exactly the
error `AXIS_UNKNOWN_BP = -1` exists to prevent, one layer down, where the sentinel was not used.

**It is mine, it is blocked on nothing, and it is the highest-value small fix left in L1-L3.**

## And two numbers worth knowing before touching the funnel

- **The 552 drops were not borderline.** Average floor **2,500 bp**, average dropped importance
  **1,251 bp** — they scored *half* the floor. Lowering it admits noise; it does not recover signal.
- **150 of 165 cards are expired**, 6 surfaced. ⛔ That is L4's first crosscheck question, not a
  finding: expiry is a window, and a window over a queue starved since the OCR deploy expires
  everything in it. Answerable by measuring expiry dates against the deploy date.

---

# 2026-10-01 · ⛔ L4 RE-CROSSCHECK — the queue is empty for ONE reason, and it is not L4

`layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` · 364 lines · every number
measured read-only against production the same day.

## L4 does not need building

27 files, 6,167 lines, running on every heartbeat tick, 186 executions · 794 actions ·
466 escalations · 186 outcomes. ⛔ And it is the **only** layer that shipped with its own
declared-silence module (`executive/unreached.py`) — every function it built and does not call,
each with a reason **and** a mover. L2 needed nine findings to learn that discipline.

## ⛔ The chain, every link counted

    L1 / L2 / L3 wrote rows 2026-09-30.   L4 stopped 09-25.   L5 stopped 09-25.

    sweep._PLANNABLE_SIGNALS decomposed:  42 open signals survive joins 1-5, then
      join 6 (core.constraint completed on the run)  ->  0     ⛔ ZERO HERE

    two eras of reasoning run:
      2,681 WITH unit results    evaluated 09-29 -> 09-30
      9,489 WITHOUT              evaluated 08-17 -> 09-29
      open signals pointing at the second:  98 = 100%

    the 2,681 new runs:  8,044 candidates, 7,872 'eligible', selected_candidate_id NULL on ALL
      impact 7,351 · risk 1,758 · effort 6,610 · urgency 5,182 · success 6,658
      formula_utility 5,469   ✅ THE DETERMINISTIC SCORER IS HEALTHY
      llm_utility         0   ⛔ zero on all 8,044
      final_utility_bp    0   ⛔ zero on all 8,044
      outcome_kind    defer 2,669 · blocked 12 · decision ZERO   ->  0 signals emitted

    GENIOS_L4_LLM_DECISION_MAKER = true, for every org

## ⛔ And it is NOT a defect — the tenth near-miss

`reason/llm_decision_maker.py:20`: *"**Failure is DEFER, never the formula.** A missing key, an
exhausted budget, a network error... all DEFER with a reason code. Falling back to the formula
would make a test of 'what does the model decide' silently measure the formula."*

The reasoning is sound. **What nobody declared is that the measurement mode is the production
mode.** So the Anthropic spend limit did not merely switch off LLM features — it stopped the card
pipeline, in a way that reads from outside as a delivery defect.

> ⛔ **A deliberate refusal to degrade is still a stop.**

**This is now DECISION #5 in `02-DECISIONS.md`** — three options, recommendation **B now, C as a
unit, A when the budget allows**. It is Rohit's, it is one line, and nothing in `executive/`
changes either way.

## The Atlas got L4 right — 11 claims checked, 1 superseded

Including, exactly: *"Units 6 and 8 have no file and three files carry no number"* — numbered are
1, 2, 2.5, 3, 4, 5, 7, 9, 10; unnumbered are `assignment`, `escalation`, `execution_guard`.
Its one superseded claim is *"the queue is empty because no domain is activated"* — true when
written, and no longer the binding constraint, because L4 produced 165 cards.

## Six units planned · four buildable · two blocked on a product number

| | Unit | State |
|---|---|---|
| **U0** | ⛔ decision #5 — raise, flip, or build the third path | **Rohit's. Nothing produces a card until this is answered** |
| **U1** | a 32nd receipt: *"no reasoning era selects zero candidates"* — ⛔ a **conjunction**, not a count: a high defer rate is healthy (the old era deferred 8,208 times and still made 1,157 decisions); a **100%** defer rate is the defect | buildable |
| **U2** | **G2** `assignment.resolve_approver_seat` reaches a live path — 8 tests already written, `None` stays `None` | buildable · safest |
| **U3** | **G1** `monitor.blocking_action` — escalations name the step they wait on. ⛔ **the only `UNREACHED` entry with no tests**, so tests first | buildable |
| **U4** | **F-4** ⛔ `source_events.occurred_at` max = **2056-04-20** — a date 30 years in the future in production | buildable · L1 |
| **U5** | **F-5** 708 outputs carry no `ranking_weights_version` — the legacy lane cannot say which weights it used | buildable · L2 |
| **U6** | **G3** brief push + **G4** preventive push | ⛔ **blocked**: needs *how many warnings a founder sees a day*. `modes.py` calls preventive *"the vision's USP"* and `deliver/` has **zero** references to it |

## ⛔ F-6 · and one of my own citations was stale

`unreached.py` cites `api/routes.py:1150` for the `run_executive` call. It is at **1195**. The
claim is true, the address is not — the exact shape of *"a comment that cites a record reads as a
record somebody can go and read"*. ⛔ **`tests/test_spec_deferrals_resolve.py` cannot catch it**:
it resolves document paths, not `file.py:line` citations in prose. That generalises, and it is
U-next.

**Five load-bearing citations in the document were opened by hand. One in five was wrong.**

---

# 2026-10-01 · ⛔ BLOCK 2 — STEP-02 was right too, and it cost 124 escalations

The re-crosscheck above found what stops work **entering** L4. It does **not** supersede
`STEP-02-DONE-organisation-readiness.md`. Both were re-measured today, through STEP-02's own
diagnostic:

    org_readiness, all three orgs:    seats 1 ✅   channels 1 ✅   reporting_line 0 ⛔
    manager_of has two sources:       org_seats.manager_seat_id  0 of 3
                                      seat_responsibilities      0 rows

    execution_escalations, 466 rows:
      day 1 notify   owner    175   127 fired   127 targeted   ✅
      day 2 remind   owner      1     1 fired     1 targeted   ✅
      day 3 remind   owner    165    75 fired    75 targeted   ✅
      day 5 escalate manager    1     1 fired     1 targeted   ✅
      day 7 escalate manager  124     0 fired     0 targeted   ⛔⛔

⛔ **124 day-7 manager escalations were scheduled and not one ever fired.** The ladder works to
day 3 and stops. Seats and channels existing is exactly why 186 executions and 165 cards exist at
all — so organisation data is **partial, not absent**, and STEP-02's finding is **narrowed, not
wrong**: its scope is the **ladder**, not the queue's input.

> ⛔ **Two blocks at two places.** Fixing either alone leaves the other.

**Block 2 is not a unit.** `readiness.py:66` has said what to do since STEP-02: *set
`org_seats.manager_seat_id` for the standing line, or file a dated `reports_to` responsibility.*

## ⛔ F8 · and `seat_responsibilities.reports_to` is not a column

`03-FINDINGS.md` F1 and the Atlas both write it as one. The table's columns are `org_id, seat_id,
scope_kind, scope_key, accountability, source, evidence_ref, valid_from, valid_until, created_at`;
`assignment.REPORTS_TO = "reports_to"` is a **value of `accountability`**, and `reports_to` appears
in **no migration**. **The code is right** — `readiness.py:66` names both paths exactly. Two
documents' prose was imprecise, and that is now corrected in both.

---

# 2026-10-01 · EVERY FILE UPDATED THIS ROUND

| File | What changed |
|---|---|
| `layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` | **NEW**, 420 lines — the chain link by link, the two blocks, 11 Atlas claims, 6 units, and the five citations opened by hand |
| `layer-4-executive/00-START-HERE.md` | the two blocks at the top; `05` is now the first read; the six planned units |
| `layer-4-executive/01-CROSSCHECK.md` | its two "why the queue is empty" lines — one confirmed-and-narrowed, one now given a dated reason |
| `layer-4-executive/02-PLAN.md` | **round 2**, six units with the *why* and the *do not* for each |
| `layer-4-executive/03-FINDINGS.md` | **F6–F12** |
| `layer-4-executive/STEP-02-DONE-...md` | narrowed, not wrong — with the 124 |
| `02-DECISIONS.md` | **DECISION #5**, three options, recommendation **B now, C as a unit, A when affordable** |
| `07-LEDGER-...md` | the L4 step — ⛔ **the one with no build in it** — and the five doctrine rules it produced |
| `08-ATLAS-SCORECARD-L1-to-L4.md` | **renamed** from `-L1-L2-L3`, every citation fixed; L4's 11 claims added · **35 total** |
| `17-THE-THREE-LAYERS-end-to-end.md` | PART 9's open question **answered**; PART 8 raises R2 from 🟠 to 🔴 |
| `HANDOFF-HARSH.md` | ⛔ a warning above H1: **H1 and H2 produce no card until decision #5** |
| `HANDOFF-CODING-AGENT.md` | **four new briefs** (A–D) and an explicit **DO NOT BUILD** list |

⛔ **Nothing was built this round, and that is the finding.** L4 needed a cause, not code.

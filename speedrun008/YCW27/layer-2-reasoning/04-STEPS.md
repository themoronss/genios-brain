# L2 · every step, in order — the full list

**18 units · 7 sections · ⛔ 10 done, 1 retired, 7 left — and the 7 are BOTH PLANES ONLY.**

⛔ **Everything except Plane R (S5) and Plane D (S6) is built.** Per Rohit's instruction the two planes
are last and will be done unit by unit together. S1 · S2 · S3 · S4 are complete: **263 new tests.** Detail for each is in
[`02-PLAN.md`](02-PLAN.md); this page is the index and the order.

⛔ **Plane R (S5) and Plane D (S6) were missing from the plan's first draft**, because the cross-check
measured `reason/`'s orchestration and never looked at either plane. Measuring them found a defect in
each, and the Plane R one is the sharpest thing in this layer.

---

## The order, and why

```
S1  prove the claims          ✅ DONE — retired 2 units
S2  the DegradedStep          ✅ DONE — 3 units,  38 tests
S4  the counters              ✅ DONE — 2 units,  42 tests
S3  the lanes + router        ✅ DONE — 4 units, 169 tests
   │
   ├─▶ S5  Plane R contract   ⬜ 3 units  ← NEXT, unit by unit with Rohit
   └─▶ S6  Plane D routing    ✅ DONE — 4 units became 6, of which 4 built,
                                 1 retired, 1 withdrawn · 98 tests

S7  the vector axes           ⛔ Rohit — blocks M13, not M11
```

⛔ **S5 and S6 were held back deliberately**, on Rohit's instruction: *"domain expertise plane aur
reasoning plane in dono ko chhod ke baaki jo-jo cheezein hain, usko fix karo"* — everything else first,
then both planes unit by unit in reverse chronological order.

**S5 and S6 first among the unbuilt.** Both are contained — S5 is declarations on 23 classes with a
guard already waiting for them; S6 is corpus edits with a validator already in place. Neither touches
the orchestrator, so neither can break what is above it.

**S3 last.** It is the only section that adds a vocabulary other layers must consume.

---

## Every unit

| # | Unit | Section | What | Status |
|---|---|---|---|---|
| 1 | `M11.C0.U01` | S1 | read-only probe: is `core.risk` silent? ⛔ **split by the outage clock** | ✅ **DONE** · 14 tests · **claim FALSE** |
| 2 | `M11.C1.U02` | S1 | the skip receipt | ⛔ **RETIRED** · code and test already existed |
| 3 | `M11.C4.U01` | **S5** | `source_units` on the two `AXIS_SOURCES` units, derived not retyped | ⬜ **next** |
| 4 | `M11.C4.U02` | **S5** | `source_units` on `legacy.score_gate` + the 5 dynamic readers | ⬜ |
| 5 | `M11.C4.U03` | **S5** | ⛔ a **source-derived** test, so the guard can never pass trivially again | ⬜ |
| 6 | ~~`M11.C5.U01`~~ | **S6** | ⛔ **RETIRED** — a runtime counter already existed; it was missing its DIMENSION. Split into U05/U06/U07 | ⛔ |
| 6a | `M11.C5.U05` | **S6** | ✅ `NoExpertiseRoute` carries a validated reason — **four**, not three · 19 tests | ✅ |
| 6b | `M11.C5.U06` | **S6** | ✅ refusals counted by **(reason × type)**, with a balance receipt · 19 tests | ✅ |
| 6c | `M11.C5.U07` | **S6** | ✅ the probe reads the **field**, never the message · 13 tests | ✅ |
| 7 | `M11.C5.U02` | **S6** | ⛔ **REWRITTEN** — it IS generated (`index.py:205`). Now: a stale registry is an **ERROR** · 14 tests | ✅ |
| 8 | `M11.C5.U03` | **S6** | ⛔ **WITHDRAWN** — `situation_admission_reason` already does it, with 15 tests. Zero draft situations can instruct | ⛔ |
| 9 | `M11.C5.U04` | **S6** | ✅ Customer Support's `deferrals.yaml` — all seven · 33 tests | ✅ |

### ⛔ S6 is COMPLETE, and two of its four cross-check findings were WRONG

**98 new tests.** Built bottom-up: level 0 → 1 → 2, never a parent before its children were green.
Full detail in `plane-d-domain-expertise/` — `01-CROSSCHECK.md` carries both retractions in full.

| | I wrote | Actually |
|---|---|---|
| `U02` | *"the corpus also stores it by hand"* | `_tools/index.py:205` **generates** it, comment and all. Byte-identical on regeneration |
| `U03` | *"a situation's status gates nothing"* | ⛔ **I believed a corpus comment that was true when written.** `situation_admission_reason` closed it; `admitted = not admission_gaps` |

**What was genuinely wrong:** `domain_not_activated` — an operations fact — was published as
`no_route_type`, an authoring gap, by the one tool routing coverage is read from, because it told four
causes apart with three substring tests and an `else`. And `no_route` had no dimension at all, which is
this layer's own L1 rule reaching its own code.
| 10 | `M11.C1.U01a` | S2 | the `DegradedStep` receipt contract — names what it **kept**, not only what it lost | ✅ **DONE** |
| 11 | `M11.C1.U01b` | S2 | compute it in `_select`, **provably without changing what is kept or dropped** | ✅ **DONE** |
| 12 | `M11.C1.U01c` | S2 | carry it to the decision's `uncertainty` — ⛔ *not done until a human can read it* | ✅ **DONE** |
| 13 | `M11.C3.U01` | S4 | the counter table — ⛔ **a zero is written, not skipped** | ✅ **DONE** |
| 14 | `M11.C3.U02` | S4 | four wired; ⛔ `signals_detected` refused rather than faked | ✅ **DONE** |
| 15 | `M11.C2.U01` | S3 | the lane vocabulary, closed enum — ⛔ **named `output_lane`, never a bare `lane`** | ✅ **DONE** |
| 16 | `M11.C2.U02` | S3 | the router — pure, deterministic, **no model** (a lane is a route) | ✅ **DONE** |
| 17 | `M11.C2.U03` | S3 | the totality guard, **both directions** | ✅ **DONE** |
| 18 | `M11.C2.U04` | S3 | the lane on the flat projection; ⛔ the audited row **trimmed** — it already carries it | ✅ **DONE** |

---

## The two planes, measured

### Plane R · `reason/reasoners/` — 23 files, 7,820 lines

```
CORE_UNITS=17  SUPPLEMENTARY_UNITS=6  total registered=23
units with NO declared source_units: 23
units WITH declared source_units:     0
```

⛔ **`reason/registry.py:49` was written for exactly this**, and names the pattern:

> *`AXIS_SOURCES`-style defaults are a hard dependency on the roster even though no capability ever
> spells them, and this is where a unit states them so they can be checked.*

`tradeoff_unit.py:59` has that literal `AXIS_SOURCES` map naming six unit ids. `resource_unit.py` has
the same pattern. `legacy_gate.py:23` hardcodes `prior_results.get("legacy.rule")`. **None declares
anything**, so `validate_sources()` validates an empty set and its test passes trivially.

And `core.tradeoff` **completed 1,165 of 1,165 runs** — reading six undeclared sources on every one.

### Plane D · `packs/` 7,957 lines + `Domain Expertise/` 1,426 YAML files

```
$ .venv/bin/python "Domain Expertise/_tools/validate.py"
0 error(s), 290 warning(s) — OK
```

| Domain | Capabilities | Situations | Draft |
|---|---|---|---|
| **Admin** *(the only one in scope)* | 59 | 34 | **7** |
| Sales *(on hold)* | 47 | 15 | 0 |
| Customer Support *(on hold)* | 49 | 20 | 16 |
| **total** | **155** | **69** | **23** |

**All 155 capabilities are `stable`.** The corpus is large, validated, and error-free.

Of the 290 warnings, **217 are *"planned but not authored yet"*** — the corpus declaring its own
frontier, which is the declared-silence doctrine working, and **not a defect**. Five are the ones that
cost a live card.

---

## ⛔ What is deliberately NOT in this layer

| Not doing | Why |
|---|---|
| making plan compile **fail** on an unproduced source | reverts a measured decision. `plan.py:229`: *"six units lost to one absent fact"* |
| authoring the 217 unauthored refs | content work, and the declared frontier is not a bug |
| binding the 5 unrouted types | ⛔ authoring, and 3 of 5 are not obviously Admin's. **Visibility is ours; ownership is Rohit's** |
| activating Sales or Customer Support | standing constraint: **Admin only** |
| the 16 Support draft situations | out of scope while Support is on hold |
| scheduling `core.signal_composition` | registered, **zero** production rows. May be correct. ⛔ **Open question, not a unit** |
| aligning `DecisionOutcome` to the 5 lanes | loses five sixths of a vocabulary the contract explicitly defends |
| refactoring the 4 registry validations | thorough and correct. Adjacent, not asked for |
| renaming any confidence axis | ⛔ Rohit's decision, and my recommendation is not to |

---

## What Rohit decides — 2 things, neither blocks S5 or S6

| # | Decision | Recommendation |
|---|---|---|
| 1 | **ConfidenceVector axes** — code's 6 vs Atlas's 6, **2 of 6** overlap | ⛔ **Keep the code's six, correct the Atlas.** Cost measured: 3 construction sites, 0 migrations, 2–6 files per axis. `identity` → `authority` is **not a rename, it is a different measurement**, and the code **refuses to compose an axis nobody measures** |
| 2 | Who owns each of the **5 unrouted Layer 2 types** | 3 of 5 are not obviously Admin's. We make the loss countable either way |

---

## ⛔ The running score on this programme's own planning documents

| Layer | Planned unit | What it turned out to be |
|---|---|---|
| L3 | `M10.C1.U03` compare-and-set | **already built** — `reason/runner.py:570`, 6 passing tests |
| L2 | `M11.C1.U01` fail on unproduced source | **a regression** — `plan.py:229` removed that rule for measured reasons |
| L2 | `M11.C1.U02` skip receipt | **already built AND already tested** |
| L2 | *"two of `core.risk`'s three plugins silent"* | **false** — one unit, not three plugins; 1,165 of 1,165 completed |
| L2 | *"Plane D is not in M11's scope"* | **wrong** — nobody had looked; S5 and S6 exist because of it |

> **Five corrections in two layers.** Every one came from reading the code or running a query before
> writing any. That is what S1 is for, and it is the cheapest section in the programme.

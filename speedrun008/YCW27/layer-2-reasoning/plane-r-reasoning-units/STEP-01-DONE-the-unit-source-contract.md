# Plane R STEP 01 · `S5.U01`–`U08` · the unit source contract · **DONE**

Built **bottom-up, leaf first** — level 0 → 1 → 2 → 3, never a parent before its children were green.
**45 new tests.**

| unit | level | what | tests |
|---|---|---|---|
| `S5.U01` | 0 | `core.impact`'s inline literal becomes `DEFAULT_RELATIONSHIP_SOURCE` | (in U07) |
| `S5.U06` | 0 | `core.confidence` + `core.priority` declare `()` **with the reason** | (in U07) |
| `S5.U02` | 1 | `core.tradeoff` declares **6, derived from `AXIS_SOURCES`** | (in U07) |
| `S5.U03` | 1 | `core.risk` declares 2, from its own constants | (in U07) |
| `S5.U04` | 1 | `core.opportunity` declares 1 | (in U07) |
| `S5.U05` | 1 | `core.impact` declares 1 — honest only because U01 ran | (in U07) |
| `S5.U07` | 2 | the **source-derived** guard | **30** |
| `S5.U08` | 3 | the roster and the unit may not drift | **15** |

```
BEFORE:  23 units · 0 declaring · validate_sources() checked 0 sources
AFTER:   23 units · 4 declaring · validate_sources() checks 10 sources on every registration
```

---

## ⛔ The plan's premise was true and misleading, and that changed the work

`02-PLAN.md` S5 said *"23 units, 0 declare what they read."* Verified: literally true.

**But `validate_sources()` was never unwired.** `registry.py:131` calls it in the constructor;
`registry.py:141` fills `self._sources` from `declared_source_units` on every registration. So the
guard has been **running on every process start since it was written, validating zero.**

> That is a materially different defect from *"a guard waiting to be built"*, and a much easier one to
> close: nothing needed wiring. Twenty-three classes needed to tell the truth.

And `registry.py` had already written the diagnosis:

> *"a unit written before this attribute existed is not a deployment failure — it is simply a unit
> whose defaults are unchecked, **which is where every unit was**."*

---

## ⛔ The bug this prevents had already shipped — in the unit with the most sources

`tradeoff_unit.py:55`, written by whoever found it:

> *"`CostVersusBenefitPlugin` returned no observation, and this unit has been **comparing two axes
> while declaring three** since the day it shipped. **Nothing failed, because a missing source is
> indistinguishable from a source that did not run**, which is exactly the silence a tradeoff is
> supposed to keep. `effort_bp` is published by `core.cost`, and always was."*

**A unit silently comparing 2 of 3 axes for its entire life, and no test able to notice** — because the
silence it produced is the silence it is *supposed* to produce when there is genuinely no tension.

⛔ **And `risk.py` had already named its constants FOR this check:**

> *"enumerated here so the registration check can prove they name units that exist — a source unit that
> was never registered reads exactly like a source unit that did not run."*

**The constants existed. The check existed. The one line joining them did not.**

---

## Two corrections to the plan's unit list

| Plan said | Measured |
|---|---|
| *"the **two** `AXIS_SOURCES` units"* | ⛔ there is **one** `AXIS_SOURCES`, in `core.tradeoff`. The other three defaulting units use plain `DEFAULT_*` constants — a different shape, a different derivation |
| *"`source_units` on **`legacy.score_gate`** + the 5 dynamic readers"* | ⛔ `legacy.score_gate` reads **no source at all**. Declaring one would assert a dependency it does not have |

---

## The four decisions worth defending

⛔ **`core.tradeoff` is DERIVED, one expression, never six strings.**

```python
source_units = tuple(sorted({unit_id for _, unit_id, _ in AXIS_SOURCES}))
```

A retyped list is a second copy of the truth, and a seventh axis added above would leave it behind —
**reproducing, inside the guard, the exact defect the guard exists to prevent.** A test asserts
`AXIS_SOURCES` appears in the assignment line.

⛔ **`core.impact` needed its literal named FIRST, and that is why `U01` is a unit.**
`"core.relationship"` sat inline in a function body at `:191` while its three siblings used module
constants. A literal in a function body cannot be derived from, so `U05` written before `U01` would
have been `("core.relationship",)` — a retyped copy, in the declaration meant to make the first one
checkable. It was also the next silent-rename waiting to happen: rename `core.relationship` and the
three siblings break visibly; this one kept running and read nothing.

⛔ **The two manifest-only units declare an explicit `()`.**
`()` and *absent* are the same value through `getattr` and **opposite facts**. Before this section all
23 read `()` — 21 because nobody had declared, 2 because there is genuinely nothing to declare. The
declaration is the only thing that tells them apart. *Every silent lane carries a reason and a mover.*

⛔ **The six supplementary units declare nothing, deliberately.**
Zero plugins between them, no metric reads. Declaring sources they do not have would be a dependency
asserted to satisfy a checklist — the opposite of this section.

---

## ⛔ The guard is source-derived, and it bites

A test asserting `RiskUnit.source_units == ("core.relationship", "core.temporal")` passes forever and
proves nothing: add `DEFAULT_OWNER_SOURCE`, forget to declare it, stay green. **That is the shape of
every guard this programme has had to rewrite.**

So `U07` walks each module's **AST**, collects every module-level `*_SOURCE` constant and every
`AXIS_SOURCES` entry whose value looks like a unit id, and demands each appear in `source_units`.

**Driven, not asserted:** adding `DEFAULT_OWNER_SOURCE = "core.dependency"` to `risk.py` without
declaring it produced

```
core.risk names {'DEFAULT_OWNER_SOURCE': 'core.dependency'} in a module constant and does not
declare it in source_units.
```

⛔ **AST, not a grep, and the reason is in these files.** Every constant sits under a paragraph that
*names* it and names the unit it points at — `risk.py`'s comment mentions `core.temporal` three times
before the assignment. A regex over the text matches the explanation. **Four tests written earlier in
this programme failed on exactly that.**

---

## ⛔ `U08` pins an alarm rather than hiding it

`core.tradeoff`'s sources now live in three places, and two of them are one value (`U02` guarantees
it). The third — `expertise._ROSTER[...].sources` — is an **independent copy**, and *"two computations
of one fact that are never compared eventually disagree"* is a shape this programme found four times.

So `U08` compares them **both directions**, because they are different bugs:

- a **roster source the unit has no default for** is legal (that is what config keys are for) and is
  checked for being a real, *depended-on* unit — otherwise the plan would schedule a read from
  something that may not have run;
- a **unit default the roster omits** is `ALARM A5`: `core.tradeoff` declares six sources and the live
  legacy lane schedules **none** of `core.impact`, `core.cost`, `core.opportunity`. Switched on today
  it would compare **1 of 6** axes.

`test_the_tradeoff_gap_is_exactly_what_the_alarm_says` pins the current state, so a change has to be
read rather than absorbed.

---

## Found while building, worth keeping

**The six supplementary units have no `unit_id` class attribute.** They *"predate the framework"* and
identify through `spec.reasoner_id` on an instance. A test reaching for `cls.unit_id` failed at
**collection**, not assertion — so the fact lives in one `_id_of()` helper rather than being
rediscovered per assertion.

---

## ⛔ What this does NOT do

| | Why |
|---|---|
| switch the 20-unit roster into the sweep | `ALARM A2` · `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. An activation with a runbook, and Rohit's call |
| fix `or ""` on the two manifest-only units | `ALARM A6` · it changes behaviour. `U06`'s comment names it so it is findable |
| schedule `core.tradeoff`'s missing sources | `ALARM A5` · that is A2, not S5. `U08` makes the gap visible instead of silent |
| touch `AXIS_SOURCES`' metrics | the `(key, unit, metric)` triple is the plugin's business; only the unit ids are the registry's |

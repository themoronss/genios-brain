# Plane R · plan — 8 units, unit level, built in reverse (leaf first)

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Reads with:** `01-CROSSCHECK.md` and `../06-L2-VERIFICATION.md`. Nothing here was written before
those were measured.

---

## The decomposition, all five tiers

Rohit's shape — *group → section → function → component → unit* — mapped onto what the code has:

```
GROUP      Plane R · the unit source contract
 │
 ├─ SECTION A · derive, never retype          the mechanism by which a unit states its defaults
 │    └─ FUNCTION A1 · name what is unnamed
 │         └─ COMPONENT core.impact's inline literal
 │              └─ UNIT S5.U01     DEFAULT_RELATIONSHIP_SOURCE on impact_unit
 │
 ├─ SECTION B · the units declare             one unit per reasoner, derived from its own constant
 │    ├─ FUNCTION B1 · the structured case
 │    │    └─ COMPONENT AXIS_SOURCES (6 bindings, with metrics)
 │    │         └─ UNIT S5.U02     core.tradeoff declares, derived from AXIS_SOURCES
 │    ├─ FUNCTION B2 · the named-constant cases
 │    │    ├─ COMPONENT DEFAULT_TEMPORAL_SOURCE + DEFAULT_RELATIONSHIP_SOURCE
 │    │    │    └─ UNIT S5.U03     core.risk declares (2)
 │    │    ├─ COMPONENT DEFAULT_MOMENTUM_SOURCE
 │    │    │    └─ UNIT S5.U04     core.opportunity declares (1)
 │    │    └─ COMPONENT the constant U01 created
 │    │         └─ UNIT S5.U05     core.impact declares (1)          needs U01
 │    └─ FUNCTION B3 · the empty case, stated rather than omitted
 │         └─ COMPONENT core.confidence + core.priority (no defaults)
 │              └─ UNIT S5.U06     both declare () WITH the reason
 │
 ├─ SECTION C · the guard cannot pass trivially
 │    └─ FUNCTION C1 · source-derived assertion
 │         └─ COMPONENT the AST of each unit's own constants
 │              └─ UNIT S5.U07     every constant-named source appears in source_units
 │
 └─ SECTION D · the two declarations must agree
      └─ FUNCTION D1 · unit versus roster
           └─ COMPONENT expertise._ROSTER[...].sources
                └─ UNIT S5.U08     the roster and the unit are asserted equal
```

## Build order — reverse, leaf first

```
level 0   U01  name core.impact's literal            (no dependencies — a prerequisite)
          U06  the two empty declarations            (no dependencies — smallest real unit)
level 1   U02  core.tradeoff        needs nothing but is the richest, so it goes first of the four
          U03  core.risk
          U04  core.opportunity
          U05  core.impact          needs U01
level 2   U07  the source-derived guard              needs U02–U06
level 3   U08  unit versus roster                    needs U07
```

⛔ **Never a parent before its children are green.** `U07` asserts that every constant-named source is
declared; running it before `U02`–`U06` would fail on five units at once and say nothing useful about
any of them. `U08` compares two declarations, so both must exist.

---
---

# LEVEL 0
---

## `S5.U01` · `core.impact`'s default source becomes a named constant

**Artifact:** `genios_engine/reason/reasoners/impact_unit.py`
**Verify:** `tests/reason/reasoners/test_a_default_source_is_named.py`

### What is there

```python
source = str(view.config.get("relationship_reasoner") or "core.relationship")   # :191
```

Its three siblings name theirs — `DEFAULT_TEMPORAL_SOURCE`, `DEFAULT_RELATIONSHIP_SOURCE`,
`DEFAULT_MOMENTUM_SOURCE`. `core.impact` alone buries it in a function body.

### Why this is a unit and not a tidy-up

⛔ **A literal inside a function cannot be derived from.** `U05` must declare `source_units` from the
unit's own default, and if the default is a literal then the declaration is a **retyped copy** — the
exact thing this section exists to abolish. So naming it is a prerequisite, not housekeeping.

⛔ **And it is the silent-rename hazard.** Rename `core.relationship` and the three siblings break at
import; `core.impact` keeps running and reads nothing, which is
`ALARM A4` in `../06-L2-VERIFICATION.md`.

**Outcome.** One line moves. Four units now state their defaults the same way, so one derivation rule
covers all four.

---

## `S5.U06` · the two units with no default declare `()` — and say why

**Artifact:** `confidence.py`, `priority.py`
**Verify:** `tests/reason/reasoners/test_an_empty_declaration_is_a_statement.py`

### What is there

```python
source = str(view.config.get("source_reasoner") or "")     # confidence.py:139
return str(view.config.get("source_reasoner") or "")       # priority.py:65
```

No default. The manifest must name it, and `validate_capability_sources` **already checks that**.

### Why declare anything at all, then

⛔ **Because `()` and *absent* are the same value through `getattr` and opposite facts.** Today all 23
units read `()` — 21 because nobody declared, 2 because there is genuinely nothing to declare. A
reader cannot tell them apart, and after `U02`–`U05` the 21 becomes 17, still indistinguishable.

An explicit `source_units = ()` with a comment naming *why* — *"this unit reads only what a manifest
names; there is no default to check"* — is the difference between a declared silence and an
undeclared one. **This programme's own doctrine: every silent lane carries a reason and a mover.**

⛔ **AND IT RECORDS A REAL RISK.** `or ""` means a manifest that forgets `source_reasoner` yields an
**empty source string**, not a refusal — `ALARM A6`. The comment names it; fixing it is not this unit
(it changes behaviour), and the note is what makes it findable.

**Outcome.** `()` stops meaning two things.

---
---

# LEVEL 1
---

## `S5.U02` · `core.tradeoff` declares 6, derived from `AXIS_SOURCES`

**Artifact:** `tradeoff_unit.py`
**Verify:** `tests/reason/reasoners/test_the_tradeoff_declares_every_axis.py`

### What is there

```python
AXIS_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("benefit_source",   "core.impact",      "impact_bp"),
    ("certainty_source", "core.confidence",  "confidence_bp"),
    ("cost_source",      "core.cost",        "effort_bp"),
    ("reward_source",    "core.opportunity", "opportunity_bp"),
    ("risk_source",      "core.risk",        "risk_bp"),
    ("speed_source",     "core.temporal",    "urgency_bp"),
)
```

### ⛔ The sentence that justifies this entire section

> *"`CostVersusBenefitPlugin` returned no observation, and this unit has been **comparing two axes
> while declaring three** since the day it shipped. **Nothing failed, because a missing source is
> indistinguishable from a source that did not run**, which is exactly the silence a tradeoff is
> supposed to keep."*

**The bug has already happened, in this unit, and the code says so.**

### What to build

```python
source_units = tuple(sorted({unit for _, unit, _ in AXIS_SOURCES}))
```

⛔ **DERIVED, ONE LINE, NEVER A LIST OF SIX STRINGS.** A retyped list is a second copy of the truth,
and a seventh axis added to `AXIS_SOURCES` would leave it behind — reproducing exactly the defect the
comment describes, in the guard built to prevent it.

⛔ **`sorted` and `set`**, because `declared_source_units` sorts and de-duplicates anyway, and a
declaration that differs from what the registry stores is a diff waiting to confuse somebody.

**Outcome.** `validate_sources` now proves all six axis sources are registered units. Had it existed,
the shipped bug would have been an import-time failure.

---

## `S5.U03` · `core.risk` declares 2 · `S5.U04` · `core.opportunity` declares 1

**Artifacts:** `risk.py`, `opportunity.py`
**Verify:** `tests/reason/reasoners/test_every_default_source_is_declared.py`

```python
# risk.py
source_units = (DEFAULT_RELATIONSHIP_SOURCE, DEFAULT_TEMPORAL_SOURCE)
# opportunity.py
source_units = (DEFAULT_MOMENTUM_SOURCE,)
```

⛔ **`core.risk` is the one with consequences.** `../06-L2-VERIFICATION.md` `ALARM A5` records that
`legacy_pack` schedules `core.temporal` and `core.relationship` — so `core.risk`'s two sources are
live. Its three plugins are the reading the whole lane depends on (`_ROSTER`: *"pressure is the
reading the whole lane already depends on"*), and a rename would have silenced two of the three
exactly as it silenced one of `core.tradeoff`'s.

**Outcome.** Two more units cannot lose a source to a rename.

---

## `S5.U05` · `core.impact` declares 1

**Artifact:** `impact_unit.py` · **needs `U01`**
**Verify:** same file as U03/U04.

```python
source_units = (DEFAULT_RELATIONSHIP_SOURCE,)
```

⛔ **One line, and it is only honest because `U01` ran first.** Written before it, this is
`("core.relationship",)` — a retyped literal, and the unit would then hold its default twice.

---
---

# LEVEL 2
---

## `S5.U07` · the guard cannot pass trivially

**Artifact:** `tests/reason/reasoners/test_a_declared_source_cannot_be_forgotten.py`
**Verify:** itself

### The problem with the obvious test

A test asserting `core.risk.source_units == ("core.relationship", "core.temporal")` passes forever
and proves nothing: add `DEFAULT_OWNER_SOURCE`, forget to declare it, and the test is still green.
**That is the shape of every guard this session has had to rewrite.**

### What to build

⛔ **A SOURCE-DERIVED test.** Walk each unit module's **AST**, collect every module-level assignment
whose name matches `DEFAULT_*_SOURCE` and every entry of `AXIS_SOURCES`, and assert each value appears
in that unit's `source_units`.

⛔ **AST, not a grep, and this is the fifth time this session the distinction has cost something.**
These modules carry the constants inside prose comments explaining them; a regex over the text matches
the comment. Four tests written earlier in this session failed on exactly that and were rewritten.

Plus, in the same file:
- every value in any `source_units` is a **registered unit id** — `validate_sources` proves it at
  import, and asserting it here makes the failure readable
- **no unit declares itself** — `validate_capability_sources` forbids it for a manifest; the class
  attribute has no such check
- the 6 supplementary units declare **nothing**, deliberately: 0 plugins, no metric reads

**Outcome.** Adding a source without declaring it fails the build. That is the whole contract.

---
---

# LEVEL 3
---

## `S5.U08` · the unit's declaration and the roster's must agree

**Artifact:** `tests/reason/adapters/test_the_roster_and_the_unit_agree.py`
**Verify:** itself · **needs `U07`**

### The trap this closes

After `U02`–`U05`, `core.tradeoff`'s sources exist in **three** places:

```
AXIS_SOURCES                tradeoff_unit.py     the plugin binding, with metrics
source_units                tradeoff_unit.py     DERIVED from the above — one truth, two views
_ROSTER[...].sources         expertise.py        the manifest's config, for the plan
```

The first two are one value seen twice (`U02` guarantees it). **The third is an independent copy.**

⛔ **Two computations of one fact that are never compared eventually disagree.** This session found
that shape four times, and `unrouted_l2_types` was exactly it — a generated list and an independently
computed one, agreeing by luck until somebody forgot to regenerate.

### What to build

For every unit the roster declares with `sources`, assert the unit ids equal that unit's
`source_units`. Report **both directions**: a roster source the unit does not declare, and a declared
default the roster omits.

⛔ **Both directions, because they are different bugs.** A roster naming more is a manifest reading
something the unit has no default for — legal, and worth seeing. A unit declaring more than the roster
schedules is `ALARM A5`: `core.tradeoff` would compare **1 of 6** axes on the live lane today.

**Outcome.** The roster and the units can no longer drift apart in silence.

---
---

## What this plan does NOT do

| | Why |
|---|---|
| switch the 20-unit roster into the sweep | `ALARM A2` — `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. That is an **activation with a runbook**, and Rohit's call |
| fix `or ""` on `core.confidence` / `core.priority` | `ALARM A6` — it changes behaviour. `U06` names it so it is findable |
| add sources to the 6 supplementary units | 0 plugins, no metric reads. Declaring sources they do not have is the opposite of this section |
| touch `AXIS_SOURCES`'s metrics | the `(key, unit, metric)` triple is the plugin's business; only the unit ids are the registry's |
| schedule `core.tradeoff` or `core.recommendation` | they are in the staged roster and not on the live lane. Scheduling them is A2, not S5 |
| put a model anywhere | Plane R makes **zero** model calls on the decision path, measured. A source declaration is a dependency, and §4 forbids a model producing one |

## ⛔ ALARMS carried forward from the verification

| | |
|---|---|
| 🔴 **A2** | the 20-unit roster is built, budgeted, dependency-complete — and **no tenant has ever run it**. Largest built-and-not-called surface in the product |
| 🔴 **A3** | the Organisation Brain's `blocked_play_ids` lever works and `learned_brain_entries` is **empty** — a policy mechanism that has never carried a policy |
| 🟠 **A5** | if `core.tradeoff` were switched on today it would compare **1 of 6** axes, because the live lane schedules none of `core.impact`, `core.cost`, `core.opportunity`. `U08` makes that visible instead of silent |
| 🟠 **A6** | `or ""` yields an empty source string rather than a refusal on a manifest that forgets |
| 🔴 **A8** | 5 migrations unapplied; `0190` breaks card writes |

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

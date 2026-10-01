# Plane R · cross-check — what is actually true in `reason/reasoners/`

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01. **No code written yet.**
**Reads with:** `../06-L2-VERIFICATION.md`, which re-measured every Atlas claim first.

`reason/reasoners/` — **25 files, 7,820 lines.** Section **S5**, 3 units as the L2 plan specifies.

---

## 0 · The hierarchy, counted — and this is what Plane R must be built along

Rohit's decomposition — *groups → sections → functions → components → units* — is **already in the
code**, and it was not invented for this plan:

```
PLANE R                                                      reason/reasoners/ · 25 files
│
├── GROUP 1 · Situation Understanding      what is true, in what order, what blocks what
│     ├── core.context          3 plugins      ├── core.timeline        4 plugins
│     └── core.dependency       3 plugins      └── core.constraint      4 plugins
│
├── GROUP 2 · Business Evaluation          what this is worth and what it threatens
│     ├── core.risk             3 plugins      ├── core.opportunity     3 plugins
│     ├── core.impact           3 plugins      ├── core.priority        4 plugins
│     └── core.confidence       4 plugins
│
├── GROUP 3 · Optimization                 among the possible paths, which is best and when
│     ├── core.tradeoff         3 plugins      ├── core.resource        3 plugins
│     ├── core.scheduling       4 plugins      ├── core.cost            3 plugins
│     └── core.policy           3 plugins
│
├── GROUP 4 · Decision Support             prepare the field the Decision Maker judges
│     ├── core.alternative      3 plugins      ├── core.validation      3 plugins
│     └── core.recommendation   3 plugins
│                                                        CORE = 17 units · 56 plugins
└── SUPPLEMENTARY                          the strangler pair + what the taxonomy omits
      legacy.rule · legacy.score_gate · core.temporal · core.relationship ·
      core.signal_composition · core.planning                    6 units · 0 plugins
                                                        TOTAL = 23 units · 56 plugins
```

| Rohit's word | In this code |
|---|---|
| **group** | the 4 categories of the frozen architecture |
| **section** | a unit — `core.risk`, `core.tradeoff` |
| **function** | a plugin inside a unit — `CostVersusBenefitPlugin` |
| **component** | one source binding a plugin reads — `('cost_source', 'core.cost', 'effort_bp')` |
| **unit** (the atom) | one declaration, with one verify command |

⛔ **The 6 supplementary units have zero plugins.** They are single-purpose readers, not plugin hosts.
Treating all 23 alike would produce 6 units of work with nothing in them.

---

## 1 · ⛔ Finding 1 · The plan's premise is literally true and materially misleading

`02-PLAN.md` S5: *"23 units, **0 declare what they read**."*

```
$ grep -rn "source_units" genios_engine/reason/reasoners/     →  0
$ default_registry()._sources                                 →  23 keys, every value ()
```

**True.** And `reason/registry.py` validates sources in **two** ways, of which only one is unwired:

| mechanism | checks | state |
|---|---|---|
| `named_source_units(spec)` → `validate_capability_sources` | `*_source` / `*_reasoner` keys in the **manifest's config** | ✅ **works.** Refuses a source that is not scheduled, not a dependency, or is the unit itself. Called from `plan.py:492` |
| `declared_source_units(reasoner)` → `validate_sources` | the **class attribute** — a unit's OWN defaults, used when the manifest names none | ⛔ **declares nothing** |

### ⛔ And the guard is NOT unwired. It runs, and validates zero

`registry.py:141` — `self._sources[key] = declared_source_units(reasoner)` on every registration.
`registry.py:131` — `self.validate_sources()` in the constructor.

> **So this is not "a guard waiting to be built". It is a guard that runs on every registration,
> every process start, and has nothing to check.** That is a materially different defect from the one
> the plan describes, and a much easier one to close: nothing needs wiring. Twenty-three classes need
> to tell the truth.

`registry.py` already says so, in its own words:

> *"a unit written before this attribute existed is not a deployment failure — it is simply a unit
> whose defaults are unchecked, **which is where every unit was**."*

---

## 2 · ⛔ Finding 2 · The bug this guard prevents has ALREADY SHIPPED, and the code records it

`tradeoff_unit.py:55` — written by whoever found it:

> *"`CostVersusBenefitPlugin` returned no observation, and this unit has been **comparing two axes
> while declaring three** since the day it shipped. **Nothing failed, because a missing source is
> indistinguishable from a source that did not run**, which is exactly the silence a tradeoff is
> supposed to keep. `effort_bp` is published by `core.cost`, and always was."*

⛔ **A unit silently comparing 2 of 3 axes for its entire life, with no test able to notice**, because
the silence it produced is the silence it is supposed to produce when there is genuinely no tension.

**That is a better justification for S5 than the plan's own**, and it is the sentence to put at the
top of every unit built here.

---

## 3 · Finding 3 · Which units actually carry unchecked defaults — counted, not assumed

| unit | default sources | where | shape |
|---|---|---|---|
| `core.tradeoff` | **6** | `AXIS_SOURCES` at `tradeoff_unit.py:59` | ✅ a structured `(key, unit, metric)` tuple — **derivable** |
| `core.risk` | 2 · `core.temporal`, `core.relationship` | `DEFAULT_TEMPORAL_SOURCE`, `DEFAULT_RELATIONSHIP_SOURCE` | ✅ named constants — **derivable** |
| `core.opportunity` | 1 · `core.temporal` | `DEFAULT_MOMENTUM_SOURCE` | ✅ named constant — **derivable** |
| `core.impact` | 1 · `core.relationship` | ⛔ **an inline literal** at `impact_unit.py:191` | ⛔ **not derivable until it is named** |
| `core.confidence` | **none** — reads `source_reasoner`, no default | `confidence.py:139` | manifest-dependent, **already checked** |
| `core.priority` | **none** — reads `source_reasoner`, no default | `priority.py:65` | manifest-dependent, **already checked** |
| `legacy.score_gate` | **none** | — | ⛔ **the plan names it and it reads no source at all** |

⛔ **Two corrections to the plan's unit list:**

1. *"`source_units` on `legacy.score_gate` + the 5 dynamic readers"* — `legacy.score_gate` reads **no
   source**. Grepped: zero `*_source` / `*_reasoner` reads in `legacy_gate.py`. Declaring sources on it
   would be declaring a dependency it does not have.
2. *"the two `AXIS_SOURCES` units"* — there is **one** `AXIS_SOURCES`, in `core.tradeoff`. The other
   three defaulting units use plain `DEFAULT_*` constants, which is a different shape and a different
   derivation.

---

## 4 · ⛔ Finding 4 · `core.impact` is the one that must be fixed before it can be declared

Its three siblings name their defaults:

```python
DEFAULT_TEMPORAL_SOURCE = "core.temporal"          # risk.py:114
DEFAULT_RELATIONSHIP_SOURCE = "core.relationship"  # risk.py:115
DEFAULT_MOMENTUM_SOURCE = "core.temporal"          # opportunity.py:42
```

`core.impact` does not:

```python
source = str(view.config.get("relationship_reasoner") or "core.relationship")   # impact_unit.py:191
```

⛔ **A literal inside a function body cannot be derived from, so a declaration built on it would be a
RETYPED copy** — and a retyped copy of a value is the thing this whole section exists to abolish.
Naming the constant is therefore a **prerequisite unit**, not a tidy-up.

---

## 5 · What is NOT wrong here

| | |
|---|---|
| the guard itself | `validate_sources` runs on every registration, refuses an unregistered source, and its message names the unit and the version |
| the manifest path | `validate_capability_sources` is pure, called from `plan.py`, and refuses a self-reference, an undeclared unit **and** a source that is not a dependency |
| registration | explicit and central, *"because a unit appearing in the runtime because a file happened to be importable is how a decision gets made by something nobody reviewed"* |
| `getattr` rather than the protocol | a unit predating the attribute is not a deployment failure |
| the reachability report | `scripts/unit_reachability_report.py:246` **already consumes** `declared_source_units` — so the moment a unit declares one, an existing report starts showing it |
| the roster's own `sources` | `expertise._ROSTER` declares them per unit as config — the manifest half of the contract is done and checked |

⛔ **That last row matters:** `_ROSTER` already carries `core.tradeoff`'s six sources as manifest
config. So the roster and the unit will hold the same fact in two places. §6 says what to do about it.

---

## 6 · ⛔ The trap to avoid: two declarations of one fact

After S5, `core.tradeoff`'s sources will exist in **three** places:

```
AXIS_SOURCES            tradeoff_unit.py:59        the plugin's own binding, with metrics
source_units            tradeoff_unit (new)        the unit's default, for the registry guard
_ROSTER[...].sources    expertise.py               the manifest's config, for the plan
```

⛔ **This programme has found "two computations of one fact that are never compared" four times, and
the `unrouted_l2_types` case was exactly this shape.** So:

- `source_units` must be **DERIVED from `AXIS_SOURCES`**, never retyped — `tuple(u for _, u, _ in AXIS_SOURCES)`
- the roster's `sources` must be **asserted equal** to the unit's declaration by a test
- and the test must be **source-derived** (parse the constant), or it will pass trivially the day
  somebody adds a seventh axis and forgets both

---

## 7 · What S5 actually is

| Plan unit | Action |
|---|---|
| `U01` *"`source_units` on the two `AXIS_SOURCES` units, derived not retyped"* | ✅ build — but **one** such unit, and *derived not retyped* is the load-bearing half |
| `U02` *"`source_units` on `legacy.score_gate` + the 5 dynamic readers"* | ⛔ **rewrite** — `legacy.score_gate` reads nothing; the real list is `core.risk`, `core.opportunity`, `core.impact`, and an explicit `()` on the two manifest-dependent units |
| `U03` *"a source-derived test, so the guard can never pass trivially"* | ✅ build — and it must also compare the unit's declaration against `_ROSTER` |
| — | ⛔ **NEW prerequisite:** `core.impact`'s inline literal becomes a named constant, or `U02` retypes a value |

---

## 8 · The pattern, eight sections running

| Where | The document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L2 S1 | plan compile should fail on an unproduced source | it did — **six units to one absent fact** |
| L4 | never read `manager_seat_id` | it is the **standing line** |
| L5 | replace the scalar publication floor | there is none in `deliver/` |
| L6 | make a timing complaint stop lowering precision | it already does not, in **three** places |
| Plane D | the unrouted types need a runtime counter | they have one — **missing its dimension** |
| **Plane R** | **a guard is waiting for declarations** | **the guard RUNS, on every registration, and validates zero — and the bug it prevents has already shipped once, in `core.tradeoff`, and the code says so** |


---

## ⛔ 2026-10-01 · *"No code written yet"* at the top of this file was true on the day it was written

**Plane R has since been built: 8 units across STEP-01 and STEP-02-to-08, 59 guard tests.**

This file is a **crosscheck**, so *"no code written yet"* is not an error — it is what a crosscheck
says, and the date beside it is what makes it honest. It is noted here anyway because a reader
scanning for status reads that line as current, and this programme has now paid for that mistake
three separate times: a corpus comment that was true when written sent a whole unit to be specified
before it was withdrawn; seven step files carried `TO BUILD` titles on finished work; and
`02-DECISIONS.md` said *"all four open"* when two were closed.

**Nothing above is retracted.** The findings in this crosscheck are what the build was planned from,
and where one of them turned out to be wrong the retraction is recorded at the point it was found,
not here. For current status read
[`../07-LEDGER-every-step-what-why-how-outcome.md`](../07-LEDGER-every-step-what-why-how-outcome.md)
— or `../../07-LEDGER-...` from a plane folder.

# L2 · Reasoning — `reason/` + `packs/`

**The primary layer.** 118 files / 40,036 lines (`reason/`) + 34 files / 7,957 lines (`packs/`).
Milestone **M11**, 4 units — small, because most of this layer is built and mis-scheduled rather
than missing.

> What does it mean — given professional expertise and everything the company already knows — and
> what is the best next move?

---

## Four parts, and the two that are planes

| Part | Role |
|---|---|
| **Orchestrator** | the controller — loads context, requests expertise, selects units, runs, validates, stops. Not a unit, not a plane |
| **Plane R** · `plane-r-reasoning-units/` | **how** a professional thinks — domain-free thinking contracts |
| **Plane D** · `plane-d-domain-expertise/` | **what** a professional knows — reviewed YAML, compiled |
| **Tools** | exact operations on the frozen snapshot — dates, money, baselines, authority |

⛔ **Naming guard.** *Reasoning Plane* = L1 + L2 + L3 together. *Reasoning Layer* = L2 only.
*Plane R* and *Plane D* are the two libraries inside it. Never write "the reasoning plane" when you
mean Plane R.

⛔ **The one rule between the planes:** an **R-Unit applies reasoning ON selected D-Units, USING the
current signal and context** — never the other way round.

---

## The dependency direction, measured

```
reason  → packs  :  7 files
packs   → reason :  0 files    never
context → packs  :  0 files    cannot — import rule is same-or-lower
context → reason :  0 files    cannot
```

So `context` does **not** call the planes. `reason` calls into `context`'s situations and consults
`packs`. The phrase *"what context reasons with"* is a statement about the architecture, not an
import direction — and the import rule enforces the reverse deliberately, because it is what
*"keeps domain knowledge out of the engine and context out of expertise — a build failure, not a
review nit."*

---

## Measured today

| | |
|---|---|
| Units registered | **23** — 17 core + 6 supplementary |
| On the default path | **6** — context, risk, constraint, priority, confidence, planning |
| `_ROSTER` bindings for Admin (`roster_v2`) | **15 of 20 bind**; of the 5 that drop, **4 drop correctly** — deal-shaped units, and Admin has no deals |
| Model calls on the decision path | **0** |
| Domains activated | **0** — everything compiles in shadow |

⛔ **The live defect.** `core.risk` reads `drop_bp` from `core.temporal` and `coverage_bp` from
`core.relationship`. Neither is scheduled on the default path, so **two of risk's three plugins
have been correctly silent since the day it shipped.** That is a production intelligence defect,
not a documentation one — and it is `M11.C1.U01`.

---

## What changes — M11

### `M11.C1` Dependency-complete plans

| Unit | What |
|---|---|
| `U01` | plan compile **fails** when a scheduled unit declares a source no other scheduled unit produces |
| `U02` | a dropped unit leaves a `SkippedStep` receipt naming the input it lacked and its candidates |

### `M11.C2` The output lanes

| Unit | What |
|---|---|
| `U03` | the five lanes as a closed enum — decision · investigation · conflict · monitor · suppress — with the rule that a lane is chosen, never a card deleted |
| `U04` | the router — confidence axes plus stakes and time state select the lane. **Deterministic; no model call** |

⛔ `U03` is blocked on **decision 1** (the confidence vector's axes). Do not start it before that
is recorded.

---

## The switch that reported "on" and changed nothing

`platform/l3_activation` first shipped with a reader, a fail-closed gate, an erasure row, an admin
API and a report — **and no caller**. So an operator could POST an activation, see it in the
console, and get a shadow pass.

> *"A switch that reports itself as on and changes nothing is worse than no switch, because the
> next person debugging it starts from the belief that Layer 3 was tried."*

`live_domains` is now OR-ed **per situation**, so a tenant with Admin active runs Admin live and
Sales in shadow in the same sweep, from the same read.

## Read these first

`reason/adapters/expertise.py` — the `_ROSTER` block, where the planes actually bind ·
`reason/unit.py` — the unit framework · `reason/domain_shadow.py:554` — the activation switch

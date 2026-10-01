# L2 · the silence receipt — audit, then plan, then execute

> ⛔ **PART 1.3 OF THIS DOCUMENT IS WRONG, and `09-AUDIT-the-lost-axis-receipt.md` corrects it.**
> It refused the lost-axis receipt because adding an output field would *"rehash ~100% of 12,170
> traces"*. **It rewrites nothing.** `ReasoningStore._verify_replay_bundle` hashes the content stored
> inside a bundle against the hash stored beside it and never re-runs a unit, so old runs keep
> verifying. The warning in `contracts/reasoning.py:845` is about changing `to_semantic_dict` — the
> hashing *function* — which is a different operation. **The receipt was built on 2026-10-01 and cost
> no migration, no version bump and no stored row.**
>
> Everything else below stands: the silence declaration, the receipt that watches it, and the reason
> the claim is *"every silent unit is declared"* rather than *"no unit is silent"*.

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Reads with:** `07-DOES-IT-ACTUALLY-WORK.md`, which measured the defect against production.

> Rohit: *"ek execute karo, complete karo, perfectly sab align karo, wire karo"* and *"ek-ek cheez
> likhte jao: kya, kaise, kyun, kis tareeke se."* So: audit first, in full, then build.

---

# PART 1 · THE AUDIT — what, how, why, in what manner

## 1.1 · WHAT the defect is

```
core.impact        1,973 completions   100% silent   output = {"impact_signal_count": 0}
core.opportunity   1,088 completions    94% silent
```

A unit whose status is `completed` and whose output carries **no finding, no check, and no non-zero
metric**. It succeeded. It computed nothing. Every reader downstream treats its absence as *"no signal
here"* rather than *"this unit had nothing to read."*

**The measured consequence:** `core.tradeoff` declares **6** sources and compares **1** axis
(63% of runs) or **2** (37%), never 3. `tradeoff.cost_vs_benefit` has fired **0 times in 1,200 rows**
— while a unit test proves the axis works, by supplying the prior itself.

## 1.2 · HOW it happens — four links, each correct alone

```
core.relationship   never completes · 708 insufficient_context · 221 skipped
                    needs deal.status, which has no writer
        ▼
core.impact         all three plugins need a deal value or core.relationship.coverage_bp
                    ⇒ impact_signal_count: 0, impact_bp correctly OMITTED
        ▼
core.tradeoff       CostVersusBenefitPlugin reads core.impact.impact_bp → absent → returns ()
        ▼
axis_count: 1       the honest signal — published on every run …
        ▼
                    ⛔ … and read by NOBODY. Zero consumers outside tradeoff_unit.py
```

## 1.3 · WHY the obvious fix is wrong, and this is the most important section

**The obvious fix:** have `core.tradeoff` publish which axis it lost. ⛔ **Refused, and the codebase
already explains why** — `contracts/reasoning.py:845`, on a field added earlier:

> *"This method exists solely so that adding a field did not change a single stored hash. Without it
> `canonicalize` walks the dataclass fields, `"value_bp": null` enters the canonical JSON of every
> finding ever emitted, and that propagates through `ReasonerResult.semantic_hash` into
> `StepTrace.output_hash` — so **every trace in `reasoning_runs` would fail replay verification
> against a run that computed the identical result.**"*

The established rule is **conditional inclusion**: a new field is omitted when it has nothing to say,
so an identical computation hashes identically.

⛔ **Here conditional inclusion does not help.** An axis is lost on ~100% of runs, so the receipt would
fire on ~100% and rehash ~100% of 12,170 traces. **The information would be gained and the replay
guarantee lost.**

**And a version bump is worse.** `deal_cooling_v2.py` pins every unit to one shared
`REASONER_VERSION`, so bumping `core.tradeoff` bumps the whole manifest — blast radius of 17 units to
add one receipt.

> ⛔ **So the defect is NOT that the information is missing. `axis_count` is published on every single
> run. The defect is that nothing reads it.** The fix is a **reader**, not a field.

## 1.4 · WHY a plain receipt is also wrong

`api/routes.py:161` — `ready = not failed`. **A failing receipt flips the whole tenant to
`ready: false`**, and it is the same list the release gate runs.

`core.impact` is 100% silent **today**, for an upstream reason (`deal.status` has no writer) that
cannot be fixed at this layer. A receipt asserting *"no unit is silent"* would be **permanently red
for a reason nobody at this layer can clear** — and a gate that is always red is a gate nobody reads.

## 1.5 · WHAT IS BUILT INSTEAD — declared silence

The codebase's own doctrine: *"every silent lane carries a reason **and a mover**."*

So the silence is **declared in code**, with a reason and an owner, and the receipt asks the question
that is **true today and becomes false when things get worse**:

> *"Every unit that completes and says nothing is one we have declared, with a reason and a mover."*

- passes today, because both silent units are declared
- ⛔ **fails the moment a THIRD unit goes silent**, which is the event nobody would otherwise see for
  six weeks
- never permanently red, so the release gate stays meaningful
- no hash change, no version bump, no replay break

## 1.6 · IN WHAT MANNER — one declaration, two readers

⛔ The declaration must live in **code**, not in the probe, because `scripts/l2_unit_said_nothing.py`
already carries its own `KNOWN_SILENT` dict. A receipt with a second copy would be **two declarations
of one fact** — the shape this programme has found five times, most recently `unrouted_l2_types`.

```
genios_engine/reason/unit_health.py      ← the ONE declaration: unit → (reason, mover, share)
        │
        ├── scripts/l2_unit_said_nothing.py    imports it (its local copy is deleted)
        └── platform/receipts.py               imports it (the receipt reads the same list)
```

---

# PART 2 · THE PLAN — 4 units, bottom-up

```
level 0 ·  U01  the declaration           genios_engine/reason/unit_health.py
level 1 ·  U02  the probe reads it        scripts/l2_unit_said_nothing.py  (delete its copy)
           U03  the receipt reads it      genios_engine/platform/receipts.py
level 2 ·  U04  the guard                 one declaration, two readers, never three
```

## `U01` · the declaration — unit, reason, mover, measured share

⛔ **A reason AND a mover, both required, refused if absent.** A declared silence with no named mover
is an undeclared silence with paperwork. And the **measured share** with its date, because *"an audit
is a measurement with a date on it, and a measurement read six weeks later is a claim."*

⛔ **`_is_silent` moves here too.** It currently lives in the probe, and the receipt needs the same
definition — in SQL. Keeping the Python definition beside the declaration is what lets a test prove
the SQL and the Python agree, which is `U04`.

## `U02` · the probe reads the declaration

Its local `KNOWN_SILENT` is **deleted**, not duplicated. A test asserts the probe no longer defines
one.

## `U03` · the receipt

```sql
-- count completions, by unit, that carry no finding, no check and no non-zero metric,
-- EXCLUDING the declared set. The scalar is the number of UNDECLARED silent units.
```

`expect: n == 0`. ⛔ **Passes today** (both are declared) and fails on a third.

⛔ **The SQL must express `_is_silent` exactly.** A receipt that disagrees with the probe would make
one of them wrong and neither obviously so — so `U04` compares them over real rows.

## `U04` · the guard — one declaration, two readers, and they must agree

1. the probe and the receipt read the **same** module — asserted by AST import check
2. no module other than `unit_health` defines a known-silent list
3. ⛔ the receipt's SQL and the Python `_is_silent` **agree on the same production rows** — the only
   way to know two expressions of one rule have not drifted
4. every declared entry has a reason, a mover, and a share

---

# PART 3 · WHAT THIS DOES NOT DO

| | Why |
|---|---|
| ⛔ add a field to `core.tradeoff`'s output | rehashes ~100% of 12,170 traces; `contracts/reasoning.py:845` forbids exactly this |
| bump `REASONER_VERSION` | one shared constant — 17 units bumped to add one receipt |
| make `core.impact` emit a zero | its docstring: *"a fabricated zero silently lies"*. Correct as written |
| fix `core.relationship` | `deal.status` has no writer. Upstream data, `ALARM B3`, Harsh's |
| assert *"no unit is silent"* | permanently red for a reason this layer cannot clear |

---
---

# PART 4 · EXECUTED — 2026-10-01

**4 units, bottom-up. 25 tests. 28 receipts (was 27).**

| unit | what |
|---|---|
| `U01` | `genios_engine/reason/unit_health.py` — the ONE declaration |
| `U02` | the probe's own copies **deleted**, imported instead |
| `U03` | `platform/receipts.py` — the receipt, SQL built from the declaration |
| `U04` | the guard — one declaration, two readers, never three |

## ⛔ Verified against production, read-only

```
undeclared silent units          = 0    →  receipt PASS
units compared, SQL vs Python    = 20
disagreements                    = 0    →  ✅ the two expressions of one rule agree on real rows
silent above threshold, per SQL  = ['core.impact', 'core.opportunity']   ← exactly the declared set
```

⛔ **That middle number is the one that matters.** `SILENT_SQL` and `is_silent` express the same rule in
two languages, and *two expressions of one rule that are never compared eventually disagree* — this
programme has found that shape five times. They were run over the same 12,170 production rows and
agreed on all 20 units.

## What `U01` declares, and what each field costs

```python
DeclaredSilence(reason=…, mover=…, share_pct=…, measured_on=…)
```

All four are **refused if empty**:

| field | why it is mandatory |
|---|---|
| `reason` | the CAUSE, not the symptom. "No findings" is the symptom |
| `mover` | ⛔ **a declared silence with no mover is an undeclared silence with paperwork** |
| `share_pct` | one silent run in a thousand is noise; 90% is a unit that does not work |
| `measured_on` | *an audit is a measurement with a date on it, and a measurement read six weeks later is a claim* |

Both entries name **Harsh — a writer for `deal.status`** as the mover, because that is the single
upstream fact whose absence starves `core.relationship`, and through it `core.impact` and
`core.opportunity`.

## ⛔ Three traps avoided, each one this programme has already paid for

**1 · Not a new output field.** `contracts/reasoning.py:845` states the cost: *"every trace in
`reasoning_runs` would fail replay verification against a run that computed the identical result."* An
axis is lost on ~100% of runs, so conditional inclusion — the established escape — does not help.
**`axis_count` is already published on every run and read by nobody; the fix was a reader.**

**2 · Not `REASONER_VERSION`.** `deal_cooling_v2.py` pins every unit to one shared constant, so bumping
`core.tradeoff` bumps all 17.

**3 · Not *"no unit is silent"*.** `api/routes.py:161` computes `ready = not failed` from this list, and
it is the release gate. That claim would be **permanently red** for a reason this layer cannot clear.
A gate that is always red is a gate nobody reads.

## One honest compromise, stated

⛔ **The declared ids are inlined as SQL literals**, not bound parameters, because `evaluate()` passes
exactly one parameter (`:org`) and a second bound list would change every receipt's signature. That is
only safe because the ids are **module constants of a fixed shape**, and a test asserts
`^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$` on every one. Nothing a caller can influence reaches the query.

## What is still open — unchanged by this work

| | |
|---|---|
| 🔴 **B3** | `core.relationship` has never completed. `deal.status` has no writer. **Harsh** |
| 🔴 **B1/B2** | `core.impact` computes nothing; `cost_vs_benefit` has fired 0 times. Now **declared and watched** rather than invisible — the cause is B3 |
| 🟠 **B4** | `core.policy` has never completed, and it is the unit the Organisation-Brain lever works through |
| 🟠 **B5** | `core.signal_composition` never appears in the table at all |
| 🟡 **B6** | `axis_count` is published on every run and read by nobody. ⛔ **Still true** — the receipt watches the silence, not the lost axis. Closing B6 properly needs the output change this audit refused |

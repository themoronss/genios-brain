# L2 · full verification — every Atlas claim, re-measured

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Against:** `Rohit_Updates/Secret War Updates/04-Layer-4-Reasoning/` — the Atlas dossier for the
reasoning layer, whose own evidence baseline is **`harsh/mvp@b739bd5c`, audited 2026-08-22**.

> Rohit asked for L2 to be verified end to end before Plane R begins, *"kyunki yeh sabse major layer
> banne wala hai"*. Everything below was produced by running something today.

---

## ⛔ The headline: 5 of 8 central Atlas claims are STALE

The dossier is **six weeks old** and the code has moved. Read as current, it would send the next
person to build things that exist and to trust things that were fixed.

| # | Atlas claim (2026-08-22) | Today | |
|---|---|---|---|
| 1 | *"17 registered reasoning units"* | **23 registered** — 17 core in 4 categories + 6 supplementary | ⚠️ count |
| 2 | *"legacy_pack turns a matched rule into one play and a **six-unit** DAG"* | ⛔ **schedules 10** — including `core.alternative` and `core.validation`, which the Atlas says are never scheduled | **STALE** |
| 3 | *"expertise adapter defaults to six; alternative/tradeoff/validation/recommendation omitted"* | ✅ true of `_default_dag` — ⛔ **but a 20-unit `_ROSTER` exists** with every one of them, bound to fact paths, with budgets and dependency edges | **STALE** |
| 4 | *"all four brains are **hash-only**; Organization/Behavior/Adaptive cannot change judgment"* | ⛔ **`WAVE Y1 · THE WELD`** reads `organization_rules` → `blocked_play_ids` → `core.constraint` **eliminates before ranking**; `adaptive_preferences` also read | **STALE** |
| 5 | *"`api/intelligence_routes.py:503-527` maps card score to `confidence_score`"* | ⛔ **FIXED** — `"confidence_score": conf01, # L4's calibrated confidence, or null — never the score`, with a separate `priority_score` and a comment saying *"NOT confidence"* | **FIXED** |
| 6 | *"`api/routes.py:2056-2098` emits `stakes: missing`, `completion: missing`"* | ⛔ **FIXED** — computed from `do_nothing_consequence` / `success_signal` (migration 0065). The code records the old bug: *"These were hardcoded to 'missing' — not absent by accident but written that way"* | **FIXED** |
| 7 | *"the 17-unit candidate is excluded from the manifest sweep"* | ✅ **HOLDS** — `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`; `DEAL_COOLING_FULL_V2` imported, usable, deliberately out, with the activation step named | **HOLDS** |
| 8 | *"`_plays()` stops after a **four-play cap**"* | ⛔ **STALE** — replaced by a cap *"that RANKS instead of sorting by filename"* (CLG-07) | **STALE** |

⛔ **Two of the three claims that still hold are the two that matter most** — see §3.

---

## 1 · The unit roster, counted rather than remembered

`reason/reasoners/__init__.py` — and this is the hierarchy Plane R must be built along:

```
Plane R  ·  reason/reasoners/  ·  25 files · 7,820 lines
│
├─ CATEGORY 1 · Situation Understanding  — what is true, in what order, what blocks what
│    core.context · core.timeline · core.dependency · core.constraint                     (4)
├─ CATEGORY 2 · Business Evaluation      — what this is worth and what it threatens
│    core.risk · core.opportunity · core.impact · core.priority · core.confidence         (5)
├─ CATEGORY 3 · Optimization             — among the possible paths, which is best and when
│    core.tradeoff · core.resource · core.scheduling · core.cost · core.policy            (5)
├─ CATEGORY 4 · Decision Support         — prepare the field the Decision Maker judges
│    core.alternative · core.validation · core.recommendation                             (3)
│                                                                          CORE_UNITS = 17
└─ SUPPLEMENTARY                         — the strangler pair + what the taxonomy omits
     legacy.rule · legacy.score_gate · core.temporal · core.relationship ·
     core.signal_composition · core.planning                                             (6)
                                                                               TOTAL = 23
```

⛔ **Registration is explicit and central.** The module says why: *"a unit appearing in the runtime
because a file happened to be importable is how a decision gets made by something nobody reviewed."*

---

## 2 · What actually runs — three lanes, and they are not the same

| lane | units scheduled | live? |
|---|---|---|
| `legacy_pack` (the authoritative path today) | **10** — `legacy.rule`, `legacy.score_gate`, `core.constraint`, `core.priority`, `core.confidence`, `core.temporal`, `core.relationship`, `core.planning`, `core.alternative`, `core.validation` | ✅ **live** |
| `expertise._default_dag` (compiled fallback) | **6** — context, risk, constraint, priority, confidence, planning | shadow |
| `expertise._ROSTER` (the staged roster) | **20**, with `context_aware_selection` | shadow |

⛔ **So the Atlas's central complaint — *"alternative, trade-off, validation and recommendation are
not part of that default path"* — is now false on the live lane for two of the four.**
`core.alternative` and `core.validation` are scheduled by `legacy_pack`. `core.tradeoff` and
`core.recommendation` are still only in the staged roster.

### And the staged roster is more than a list

`_ROSTER` declares, per unit: `dependencies`, `required`, `latency_budget_ms`, `roles` bound to real
fact paths, `list_roles`, `gates_on`, `essential`, `sources`, `config`, `input_kind`, `output_kind`,
and an `always` sentence for units that can run with no facts at all. Example — `core.tradeoff`:

```python
sources=(('benefit_source', 'core.impact'), ('certainty_source', 'core.confidence'),
         ('cost_source', 'core.cost'), ('reward_source', 'core.opportunity'),
         ('risk_source', 'core.risk'), ('speed_source', 'core.temporal'))
```

⛔ **The roster already declares what each unit reads.** Which changes what S5 is — see §4.

---

## 3 · The two claims that still hold, and they are the load-bearing ones

**⛔ H1 · The 17-unit capability is still out of the sweep.**
`BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)` — the seven-unit baseline, itself shadow-only via
`live_delivery_enabled=False`. `DEAL_COOLING_FULL_V2` is imported and usable and **deliberately not
swept**, with the activation step written down: *"Step 1 of activation adds it here so it runs
alongside v1 in shadow."*

So *"17 units exist"* remains architecture proof, not evidence that any card used 17-unit reasoning.
**That claim is as true today as it was in August.**

**⛔ H2 · Brain influence is now REAL but NARROW.**
The Atlas said hash-only. Today `organization_rules` reach `core.constraint` as `blocked_play_ids`
and eliminate before ranking — the comment calls it *"the Organisation Brain's one hard lever"* and
*"the difference between a policy and a preference."* `adaptive_preferences` are read too.

⛔ **But the three runtime brains are EMPTY** (`learned_brain_entries`, `temporary_memories` — machinery
since migration `0045`, nothing produced proposals). **A lever with nothing on the other end.** The
Atlas's required proof — *hold three brains fixed, mutate the fourth, assert the one intended
semantic delta* — is still unavailable, for a different reason than it was in August: not because the
wire is missing, but because there is nothing to send down it.

---

## 4 · ⛔ What this does to S5 · Plane R — the gap is narrower and sharper than the plan said

`02-PLAN.md`'s S5 says: *"23 units, **0 declare what they read**."* Verified today: **literally true
and materially misleading.**

```
$ grep -rn "source_units" genios_engine/reason/reasoners/   →   0
```

**But `reason/registry.py` validates sources in two different ways, and only one is unwired:**

| mechanism | what it checks | state |
|---|---|---|
| `named_source_units(spec)` | `*_source` / `*_reasoner` keys in the **manifest's config** | ✅ **works** — `validate_capability_sources` refuses a manifest naming a source it does not schedule, is not a dependency, or that is the unit itself |
| `declared_source_units(reasoner)` | the **class attribute** `source_units` — a unit's OWN defaults, used when the manifest names none | ⛔ **0 of 23 declare it** |

And `registry.py` states exactly why the second matters:

> *"`AXIS_SOURCES`-style defaults are a hard dependency on the roster even though no capability ever
> spells them, and this is where a unit states them so they can be checked."*
>
> *"a unit written before this attribute existed is not a deployment failure — it is simply a unit
> whose defaults are unchecked, **which is where every unit was**."*

### The units whose defaults nothing validates — counted, not guessed

| unit | default sources | where it lives |
|---|---|---|
| `core.tradeoff` | **6** | `AXIS_SOURCES` at `tradeoff_unit.py:59` — a structured tuple of `(key, unit, metric)` |
| `core.risk` | 2 — `core.temporal`, `core.relationship` | `DEFAULT_TEMPORAL_SOURCE`, `DEFAULT_RELATIONSHIP_SOURCE` |
| `core.opportunity` | 1 — `core.temporal` | `DEFAULT_MOMENTUM_SOURCE` |
| `core.impact` | 1 — `core.relationship` | an **inline literal** at `impact_unit.py:191` |
| `core.confidence` | none — reads `source_reasoner`, no default | manifest-dependent, therefore **already checked** |
| `core.priority` | none — reads `source_reasoner`, no default | manifest-dependent, therefore **already checked** |

⛔ **And `AXIS_SOURCES` carries the receipt for the exact bug this guard prevents**, written by whoever
found it:

> *"`CostVersusBenefitPlugin` returned no observation, and this unit has been comparing two axes
> while declaring three since the day it shipped. **Nothing failed, because a missing source is
> indistinguishable from a source that did not run**, which is exactly the silence a tradeoff is
> supposed to keep."*

**A unit silently comparing two of three axes for its entire life, with no test able to notice.** That
is what S5 is for, and it is a better justification than the plan's own.

---

## 5 · What is verified GOOD in L2, and should not be touched

| | |
|---|---|
| hard elimination before ranking | `decision_maker` eliminates, then total-orders. The ordering is correct |
| confidence has one authority | below the floor returns `DEFER` with **no selected candidate** |
| the explanation model cannot decide | `reason/intelligence.py` fixes action and confidence first, validates grounding, rejects invention |
| Plane R makes **zero** model calls on the decision path | measured |
| `score` / `confidence` / `priority` are now separate at the surface | claim 5, fixed |
| `stakes` / `completion` are computed, not asserted | claim 6, fixed |
| registration is explicit, never auto-discovery | with the reason written down |
| the roster's `always` field | names the units that can run with no facts, so a thin situation degrades rather than silencing them |
| `_ROSTER`'s one-field rule | *"the orchestrator refuses a unit when ANY declared field is missing, while the selector drops it only when EVERY declared field is missing"* — so declaring three fields buys one drop case and three refusal cases |

---

## 6 · ⛔ ALARMS — what will bite, and when

| | ALARM | Why it bites |
|---|---|---|
| 🔴 **A1** | **The Atlas dossier for this layer is 6 weeks stale in 5 of 8 claims** | Whoever reads it next will rebuild `alternative`/`validation` (already scheduled), re-fix score-as-confidence (already fixed) and re-fix `stakes: missing` (already fixed). **Correcting it is the cheapest work in this document** |
| 🔴 **A2** | **The 20-unit roster exists and is not swept** | `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)`. The roster is real, budgeted, dependency-complete — and **no tenant has ever run it**. This is the largest built-and-not-called surface in the product |
| 🔴 **A3** | **The Organisation Brain lever has nothing on the other end** | `blocked_play_ids` works; `learned_brain_entries` is empty. A policy mechanism that has never carried a policy |
| 🟠 **A4** | **`core.impact`'s default source is an inline literal** | `"core.relationship"` typed at `impact_unit.py:191`, not a named constant like its three siblings. A rename of `core.relationship` breaks it silently |
| 🟠 **A5** | **`core.tradeoff` declares 6 axes and the live lane schedules none of its sources** | `legacy_pack` schedules `core.temporal` and `core.relationship` but not `core.impact`, `core.cost`, `core.opportunity`. If `core.tradeoff` were switched on today it would compare **1 of 6 axes** and say nothing about it |
| 🟠 **A6** | **Two units read `source_reasoner` with NO default** | `core.confidence` and `core.priority`. Safe today because every manifest sets it — and a new manifest that forgets gets an empty source string, not a refusal |
| 🟡 **A7** | **`legacy_pack` schedules 10 units; the dossier says 6** | Anybody measuring "how much of the architecture runs" from the dossier is 40% low |
| 🟡 **A8** | **5 migrations unapplied, `0190` breaks card writes** | Unchanged, and it gates every measurement that needs a card |

---

## 7 · What this verification changes

1. **The dossier gets a correction file** — not an edit, an appended correction naming the date and the
   measurement, because *how* a claim went stale is the part worth keeping.
2. **S5's premise is rewritten**: not *"0 units declare what they read"* but *"a unit's DEFAULT sources
   are unchecked, and `core.tradeoff` has already shipped a silent two-of-three comparison because of
   it."*
3. **A2 becomes the question after S5**: the roster is built. Switching it on is an activation step
   with a runbook, not an engineering task — and it is Rohit's call, not mine.

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

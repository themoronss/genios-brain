# Layer 4 v2 — What Was Built

> **Created:** 2026-09-08 · **Status:** Active

**Purpose:** the unit-by-unit record of what Layer 4 v2 actually is in code — the woken roster,
the ranking formula that finally decides, the Rule 11 confidence composition, the operational
floor, the LLM gate and the Reasoning Bundle — together with the gates that are met, the gates
that are **not**, and the three product defects that had to be fixed before any of it could run
at all.

**Specification of record:** `Rohit_Updates (Version 2)/Version 2 Updates/04-Layer-4-Plan/`
(docs 00–12). That set is the *design*. **This file is the *result*.**

---

## 1. The one-paragraph version

Layer 4 takes a `BusinessSituationObject` from Layer 2 and an `ExpertisePackage` from Layer 3 and
answers *what should happen* — one committed action, one honest confidence, and, new in v2, an
explanation a founder can read. Nothing in Layer 4 was missing as a file; the machinery was the
best-engineered code in the repository and it was **dormant, deaf and mute**. Seven waves fixed
exactly that. Z0 laid the contracts and the per-tenant activation row; Z1 woke the roster — twenty
units through the dormant Unit Selector instead of six hardcoded, every non-runner receipted; Z2
canonized `Finding` as the per-unit emission and gave the evidence store a permanent digest; Z3 is
the wave the whole plan was walking toward — **importance becomes the sixth ranking component, the
authored corpus priority is demoted from verdict to a 70/30 prior, confidence is composed under
Rule 11 instead of last-writer-wins, and the confidence floor stops defaulting to zero**; Z4 opened
the first model call site in `reason/` behind a single gate and built the Reasoning Bundle with its
seven-check validation gauntlet; Z5 projected L2's analytic readings and L3's compiled constraints
into the units; Z6 added the critique and daily-brief seams. **K0, K1a, K1 and K2 are met and
re-measured independently. K4's doctrine test passes and its fallback-rate row is unmeasured. K5
and K6 are met in code but not on a live population. The full suite does NOT pass.**

The decisive number: on a 60-situation pilot built through the production path, **120 distinct
`final_utility_bp` in one day** against a gate of 50, on a lane where every card used to score
exactly the same. And the decisive defect: **the compiled lane was returning nothing at all** —
three separate crashes between L2's new admission gate and L3's compiler, each caught per-situation
and counted as a tally, so the sweep reported a clean `admission_admit: 60` and produced zero
decisions.

---

## 2. Totals

| | |
|---|---|
| Waves | Z0–Z6 (Z7 = the 7-day pilot, not started) |
| New engine modules | **10 Layer 4 modules** (`reason/bundle/` is 11 files of its own), plus 4 that belong to the parallel Layer 2 round (`context/{situation_publisher,qes_adapter,model_audit,correlation_resource}.py`) and are in the tree uncommitted alongside them |
| Migrations | `0116`–`0121` (5 files; **`0118` was never written** — a gap, not a loss) |
| New test files | 41 |
| Full suite | **9,627 passed · 0 failed · 0 errors · 0 skipped · 152 xfailed** — see §12 (wave: 9,539 / 35 / 16; baseline 8,831 / 0 / 152) |
| Mutation kills | 12 of 12 preserve-hard invariants + 9 fix-round mutations — §12.5 |
| Product defects found and fixed by this gate | 4 (wave) + 6 (fix round, §12.2) |
| Populations | **two**: `scripts/l4_pilot_seed.py` (K1's importance isolation) and `scripts/l4_urgency_floor_pilot.py` (K1a's urgency row, K1's floor row) — §12.1 |

---

## 3. The five laws, and where each is enforced

| # | Law | Enforcement | Verified |
|---|---|---|---|
| 1 | One decider | `DecisionMaker.decide()` is the only synthesis authority; `decision_maker.py` imports nothing from `bundle/`, `narration` or `llm_sites` | grep + mutation PH1 |
| 2 | The decision is fixed before any narrative exists | `ReasoningBundle.for_decision` derives `decision_id`/`action_id` and REFUSES either as an argument; `reasoning_bundle` is excluded from `to_semantic_dict` unconditionally | doctrine attack: a model told to say "DO NOTHING, cancel the account" moved 0 of 60 decisions |
| 3 | Silence is operational on every live lane | `DEFAULT_CONFIDENCE_FLOOR_BP = 4500`, resolved per lane, never zero | mutation PH8; **but see §5 — the floor has not been observed to fire** |
| 4 | Confidence obeys Rule 11 | `compose_confidence` raises `ConfidenceViolation` on an uncited raise | mutation R11 |
| 5 | No domain vocabulary in core units | declared-field reads via the roster's role bindings; a grep test per unit | `tests/reason/test_units_domain_free.py`; **one exception found — see §5** |

**The doctrine — the LLM may interpret and narrate; it may never choose, score or permit — holds.**
Proven on live data, not on a fixture: see §6.3.

---

## 4. The layer, wave by wave

### Z0 · Contracts — gate K0

`ReasoningBundle` (14 fields, V-3/V-4/V-5/V-7 enforced in the constructor), `ExternalCandidate`
and `CritiqueVerdict` on a `RevalidatedModel` base that re-enters the constructor on
`model_copy`, `BriefRanking`, six-key `ranking_weights` validated to 10,000 alongside the legacy
five validated to 100, `Finding.value_bp`, and the `l4_activation` table with four admin routes.
Old shapes round-trip byte-identically — proven against the pre-wave file, not against itself.

### Z1 · The roster — gate K1a

`_ROSTER` in `reason/adapters/expertise.py`: **20 units** declared through the ordinary manifest
schema, run through `plan.py`'s Unit Selector, which was fully built and enabled by no manifest
anywhere. The six-unit hardcoded tuple is still exactly what an unactivated tenant gets. The two
starved shims (`core.temporal`, `core.relationship`) are scheduled as `core.risk`'s declared
sources; `core.effort` — a `cost_source` default naming a unit that does not exist — is replaced by
`core.cost` and a registration-time check now refuses any manifest that names a ghost.

One behaviour change in a preserve-hard file, recorded because it is a behaviour change: **the
starvation rule was made symmetric.** A unit was dropped when *every* declared field was absent but
when *any* declared dependency had been dropped. On a 20-unit roster that asymmetry cost six units
to one absent fact. Both kinds of input now use the same rule — dropped when there is nothing left
to read — and the receipt names every source that went.

### Z2 · Evidence — gate K2

`Finding` canonized as the per-unit emission with a signed `value_bp` that is omitted when
unmeasured (so no stored hash moved); one `build_evidence_ref()` replacing three id seeds; and
`reasoning_evidence_digests` (migration 0117), a permanent content-addressed digest that survives
the 720-hour payload TTL and is continuously audited against the full payload while it lives.

### Z3 · The ears — gate K1 🔴

The wave the three layers below were built for.

* **importance is the sixth utility component**, weight 2500 of 10000, read from L2's composed
  `importance_bp` — which appeared exactly once anywhere under `reason/` before this wave, in a
  SQL select. When L2 has not measured it the component is **absent and the remaining five are
  reweighed to 10,000 by largest remainder**, never defaulted to a neutral 5,000.
* **the override is demoted from verdict to prior**: `final = (formula*7 + override*3)//10`, with
  `formula_utility` and the override recorded in `score_components` on every branch.
* **Rule 11 confidence composition** replaces the last-writer scan.
* **the floor stops defaulting to zero**: 4,500 bp on the compiled lane, resolved from the lane
  when the manifest declines to declare one.
* **`do_nothing` is computed** from `core.cost` and labelled `computed` or `manifest_fallback`.

### Z4 · The voice — gate K4 🔴

`reason/bundle/gate.RSiteGate` is the **one** door: no R-site may call a model directly, and
`llm_sites.py` (R-1/R-3/R-4) delegates activation, budget, retry and receipting to it rather than
re-implementing them. Doc 01 C5's seven steps run in order with two deliberate, documented
deviations (cache before budget; budget after the prompt is built). The V-gauntlet runs all seven
checks on the raw generation so every outcome is recorded, then the constructor refuses the same
things again.

### Z5 / Z6 · The seams — gates K5, K6

`situation_projection` projects L2's trends, cohort positions and typed absences into declared
facts a unit can read, with UNKNOWABLE projected as unknown-typed and never as a value; the
compiled-constraint consumer carries a corpus rule id into `alternatives_rejected`; and
`api/l4_seam_routes.py` adds the critique endpoint and the daily brief re-rank.

---

## 5. What is NOT done

> **READ §12 FIRST.** §5.1–§5.5 are the WAVE's findings and are kept verbatim as the record of
> what was true on 2026-09-08 morning. §12 is the fix round's gate, run on 2026-09-08 evening:
> §5.1 is **closed**, §5.2 and §5.4 were **measured on a fixture that could not produce anything
> else** and are met on a population that can, §5.3 goes from 11-of-15 to 3-of-18, and three new
> residuals are opened. Nothing below has been deleted or softened.

### 5.1 The suite does not pass — 35 failures and 16 errors, ONE cause

Baseline is 8,831 passed / 0 skipped / 152 xfailed. The tree now returns **9,539 passed, 35
failed, 152 xfailed, 16 errors**. Every one of the 51 shares a single cause, and it is not
Layer 4's.

A parallel Layer 2 round landed an **unconditional, fail-closed situation admission gate**
(`context/situation_publisher.py`, migration `0122`) directly ahead of the L3 compile and the whole
of L4 in `reason/domain_shadow.shadow_compile`. It HOLDS any situation whose
`importance_source` is not `l1_qualified_signals` or which carries no well-formed **verified**
evidence span. Every L4 fixture predates it and seeds a tenant with neither, so the sweep reports
`admission_hold` and reasons about nothing:

```
{'roster_v2': 1, 'ranking_v2': 1, 'situations': 1, 'admission_hold': 1}    # reasoned: 0
```

`tests/l1_supply.py` (new, in this round) is the remedy: it writes the `qualified_signals` rows a
real tenant's L1 pass would have written, with a spread of importance and a coherent verified span,
and it is what my own K1 population uses. It is deliberately **not** wired into the fixtures,
because at least one of them —
`test_ranking_activation.py::test_this_fixtures_layer_one_never_scored_so_importance_is_absent_and_says_so`
— exists precisely to exercise the absent-importance honesty guard, and a blanket patch would
weaken it. Wiring it in is per-test surgery the owning wave should do:

```bash
# after refresh_situations, before shadow_compile, in each seed that needs an admitted tenant:
from tests.l1_supply import attach_l1_signals
attach_l1_signals(pg_store, org, eval_time=NOW)
```

Affected: `tests/test_l4_seams_out.py` (16 errors), `tests/reason/test_ranking_activation.py`,
`tests/reason/adapters/{test_roster_reaches_the_audit,test_seams_in_reach_a_signal,
test_unit_reachability_report,test_weld_reaches_a_signal,test_l3_pilot_report}.py`,
`tests/test_admin_support_packs.py`, `tests/test_e2e_all_layers.py`,
`tests/context/test_l2_shadow_diff.py` (7), `tests/contracts/test_h0_gate.py`,
`tests/test_l2_reads_what_l1_publishes.py`, `tests/reason/test_store_replay.py`.

**A gate cannot be declared green over 51 red tests.** K1a, K1, K2, K5 and K6 are reported below as
met because I re-measured each on a population I built through the production path — but the suite
that is supposed to hold them is red, and that must be closed before Z7.

### 5.2 `urgency_bp` is still a constant — it moved from 5,000 to 0

K1a's row is *"`urgency_bp` not a spike at 5000"*. On my 60-situation pilot `core.priority`
published `urgency_bp: 0` for **60 of 60** situations. The 5,000 spike is gone and the number is
not neutral any more — but it is not a measurement either, and urgency carries 2,000 of the 10,000
ranking weight, so every candidate is taking the floor on a fifth of the formula. `core.timeline`
produced 60 distinct outputs on the same run, so the ladder is computing something the priority
unit is not picking up. **This row should be read as NOT MET.**

### 5.3 Eleven of fifteen running units emit a byte-identical output for every situation

Measured on the 60-situation pilot, over `reasoning_reasoner_results.output`:

| distinct outputs across 60 situations | units |
|---|---|
| 60 | `core.context`, `core.cost`, `core.timeline` |
| 3 | `core.alternative` |
| **1** | `core.confidence`, `core.constraint`, `core.dependency`, `core.impact`, `core.opportunity`, `core.planning`, `core.priority`, `core.recommendation`, `core.risk`, `core.tradeoff`, `core.validation` |

The roster is awake — 15 units completed, 3 skipped with receipts, 2 declined at the manifest with
receipts, 20 of 20 accounted for. But *awake* is not *listening*. `core.risk` does emit
`risk.momentum_decay` and `risk.relationship_health`, which K1a asks for, and both carry empty
metrics and the reason codes `momentum_unmeasured` / `relationship_unmeasured` — honest, receipted,
and worth nothing to a ranking yet. This is the same shape as the defect the wave fixed one level
up, and it is the next thing to measure on a real tenant rather than on an admin fixture.

### 5.4 The confidence floor has never been observed to fire

`core.confidence` returned **6,250 bp on all 60 decisions** (`evidence_coverage_bp: 2500`,
`independent_evidence_groups: 1` — the same inputs for every situation in the fixture). The floor
is 4,500, so below-floor DEFERs were **0**. K1's row *"below-floor DEFERs > 0 on the compiled
lane"* is **NOT demonstrated**. The floor is operational — mutation PH8 proves a test goes red when
it returns to zero — but operational is not the same as observed, and the reason it never fires
here is §5.3's constant.

Likewise the Rule 11 `ConfidenceViolation`: `core.confidence` is a REQUIRED roster unit and, when a
named authority completes, it OWNS the number and no later unit may move it. The uncited-raise
refusal is therefore reachable in production only on a **degraded** run where that authority failed
or published nothing. That is a defensible and stricter-than-asked design; it is recorded here
because "an uncited raise throws" is a K1 row and its live reachability is narrower than the row
implies.

### 5.5 `do_nothing` is computed, and 40% of the computations are zero

100% of the 60 decisions carry `source: computed` (gate: ≥80%). But the values are
`cost_bp ∈ {0, 400, 800}` with **24 of 60 at exactly 0** and `horizon: null` on every one, so the
customer-facing sentence is *"carries a measured inaction cost of 0 basis points; no material date
was measured."* The label is honest and the arithmetic is real. The row passes; the number is not
yet worth showing.

### 5.6 K4's fallback rate is unmeasured

No model is reachable from this environment, so the only generations that exist are mine. The
gauntlet refused both of my fixtures — which is the correct outcome and a genuinely good result
(§6.3) — and every bundle stored is `template_fallback`. **The `< 15%` fallback-rate row and the
25-bundle golden review both need one real model run.** The doctrine half of K4 passes.

### 5.7 One domain token in a core unit

`core.risk` publishes the reason code `deal_momentum_risk` on an `account_admin` situation. Law 5
says domain readings live in L3 manifests. The roster's role bindings (`deal.status`, `deal.value`,
`commitment.due_at`) are declared in the **adapter**, which is the right place; this is a string
inside the unit and it is the one exception `tests/reason/test_units_domain_free.py` does not catch.

### 5.8 Housekeeping found while gating

* **Four v1-era migrations were sitting in `migrations/`** — `015_lifecycle_state.sql`,
  `016_calendar_integration.sql`, `017_integrations.sql`, `018_conflict_resolution.sql` — untracked
  in every branch, dropped into the tree after all L4 work, and referencing the `contacts`,
  `oauth_tokens` and `agent_sessions` tables that v2 does not create. **They made the migration
  chain unapplicable to a virgin database**, so the full suite could not even collect. They are
  quarantined at
  `<scratch>/quarantined_v1_migrations/` — moved, not deleted. They belong to the same stray
  legacy dump as the untracked `app/`, `_legacy_brain/` and `genios-dashboard/` paths that the
  index still carries as unmerged.
* **`tests/reason/adapters/test_zzdiag.py`** was a debug scratch file with 84 lines, a dozen
  `print()`s and **zero assertions**, running on the Postgres lane. Removed.
* **Migration `0118` does not exist.** `0117` is followed by `0119`. Cosmetic — `apply_migrations`
  walks the files present — but it means a numbered file was reserved and never written.
* The git index carries **pre-existing unmerged paths** (`README.md`, `app/`, `_legacy_brain/`,
  `genios-dashboard/`) with no `MERGE_HEAD`. Untouched by this round; they need resolving before
  anything is committed.

---

## 6. How this was proven

Every number below was measured by the gate, on a population the gate built, through the
production path — never read off an agent's report. The pattern is L1's G7 and L2's H5: seed a
tenant, drive the real entry points, then read the answer out of the tables afterwards.

### 6.1 The four defects that had to be fixed before anything ran

The compiled lane was returning **nothing at all**, and it said so in a way nobody would read as a
failure: `shadow_compile` catches every per-situation exception and increments a tally, so a
totally dead lane reports a clean-looking counter dictionary. Three crashes, one shared root cause
— **L2's admission gate now hands `shadow_compile` the UPGRADED strict `BusinessSituationObject`,
whose fields are typed models where the v1 lane carried mappings, and three downstream readers were
never updated.**

| # | File | Defect | Symptom |
|---|---|---|---|
| 1 | `context/situation_publisher.py` | `semantic_hash(payload)` canonicalizes; the `json.dumps(payload)` on the next line does not, so a `mappingproxy` / `Decimal` / `datetime` in the payload raised `TypeError` | `admission` aborted for every situation; `reasoned: 0` |
| 2 | `packs/compiler/runtime_brains.py` + `context_adapter.py` | `entity.get("id")` — dict access on a frozen `SituationEntity` | `AttributeError` on every ADMITTED situation |
| 3 | `packs/compiler/expertise_builder.py` | `expertise_id(body)` hashed a raw `Visibility` model | `CanonicalizationError: unsupported semantic value: Visibility` |
| 4 | `reason/domain_shadow.py` | `publish_situation(..., record=True)` unconditionally — a **write** on the shadow pass | the K1a gate command, read-only at the server, raised `ReadOnlySqlTransaction` and reported **K1a FAIL with all 20 units unreceipted** on a tenant whose roster was fully awake |

Defect 2 was fixed once, in `packs/compiler/models.entity_fields()`, rather than at each reader —
two call sites coercing the same object their own way is how one idea becomes two vocabularies.
Defect 3 also makes the content address honest: the id is now taken over the same normalized shape
the package holds.

### 6.2 K1 — the formula finally decides, on 60 decisions

`scripts/l4_pilot_seed.py` (written by this gate, kept): 60 admin situations, each its own company, each committed
through `context/pipeline.process_event`, each carrying a `qualified_signals` row with a real
`alg17-v1` importance and a coherent verified span; then `refresh_situations`,
`refresh_situation_importance`, `activate(roster_v2, ranking_v2)`, `shadow_compile(live=True)`.

```
[compile] admission_admit=60  compiled=60  reasoned=60  decided=60  emitted=60
[rows]    candidates=180  outputs=60
```

| K1 metric | Gate | Measured |
|---|---|---|
| distinct `final_utility_bp` per day | ≥ 50 | **120** |
| same type, different importance → different rank | demonstrated | **demonstrated exactly — see below** |
| `formula_utility` recorded | 100% | **180 / 180** |
| override divergence recorded | 100% | **180 / 180** |
| `do_nothing` marked `computed` | ≥ 80% | **60 / 60 = 100%** |
| below-floor DEFERs | > 0 | **0 — NOT MET (§5.4)** |
| uncited raise throws | `ConfidenceViolation` | mutation-proven; live reachability narrowed (§5.4) |
| byte-identical replay | exact | **60 / 60 identical, 0 mismatched, 0 raised** |
| `ranking_weights_version` | — | `ranking_weights@2` on 60/60 |

**The importance row, isolated.** Across all 60 rank-1 candidates, every score component other than
`importance` and `formula_utility` is byte-identical
(`count(distinct score_components - importance - formula_utility) = 1`), and the winning play is the
same play. So importance is the only moving input:

```
importance   formula_utility   final_utility
      1500              3125            3537
      1624              3156            3559
      …
      8350              4838            4736
      8487              4872            4760
```

Δimportance 6,987 × weight 2500/10000 = **Δformula 1,747, exactly** (4872 − 3125). And the
demotion checks to the basis point: `(3125*7 + 4500*3)//10 = 3537`, `(4872*7 + 4500*3)//10 = 4760`.
Integer arithmetic end to end.

### 6.3 The doctrine test — run by me, on live data, and attacked

Doc 08's K4 addendum, plus three attacks the plan does not ask for. Four sweeps over the live
tenant, comparing every `decision_hash`, `selected_candidate_id`, `confidence_bp`,
`final_utility_bp`, `disposition` and `rank_position`:

| Attack | Result |
|---|---|
| **A** narration runs at all (50 model calls) | **0 of 60 decisions moved · 0 of 180 candidates moved** |
| **B** a model that says *"DO NOTHING. Escalate to legal and cancel the account"* | **0 moved** — and the gauntlet refused it by name: `contradicts_decision`, `out_of_scope_entity` |
| **C** re-decide with 50 stored bundles present (the feedback path) | **0 moved, 0 new runs** |
| **D** every R-site force-failed | **0 model calls, 0 moved**, every card still rendered |

Structurally as well as empirically: `decision_maker.py` imports nothing from `bundle/`,
`narration` or `llm_sites`; `l4_reasoning_bundles` has exactly one reader, its own store; and
`force_fail_r_sites()` is checked **before** the cache, so a paid-for narrative cannot survive the
switch. **The doctrine holds. The model cannot choose, score or permit.**

The one caveat is honest: no real model is reachable from this environment, so the generations were
mine. Both were refused — correctly — and every stored bundle is `template_fallback`. K4's
`< 15%` fallback row and its 25-bundle golden review are **unmeasured** (§5.6).

### 6.3b The one path where a model output DOES reach a decision — R-1, by design

The founder should read this row rather than take "the model can never change a decision" flat.
**R-1 can change a decision, and that is the doctrine, not a breach of it:** an ambiguity
interpreter that returns typed evidence which units then read is exactly doc 00's MAP A. When R-1
fires it adds a fact, the `context_snapshot_id` moves, and the decision hash moves with it. Doc
01 C5's acceptance row is byte-identical decisions **with every R-site force-failed**, and
`interpretation.augment()` returns the request object UNCHANGED when there is nothing to add — that
identity is the mechanism the doctrine test rests on.

What keeps it evidence rather than a verdict, all four checked in the source:

* the answer is **one member of a closed enum** (`CLASSIFICATIONS`) plus one integer — the model
  cannot invent a category;
* the integer is **clamped to 2,000–8,000 bp**, so an interpretation can never be certain and can
  never be worthless;
* its evidence is minted in the **`unattributed` independence group**, so under Rule 11 it can
  never be counted as an independent group and therefore **can never raise a confidence**;
* its `source_ref` is `llm_interpretation:<model>`, separate from the measured fact it was derived
  from, so the reading and the fact can never be mistaken for two witnesses to one thing.

**Not measured here.** R-1 never fired on my population — the admin fixture holds no hedged claim
on a field the plan reads, so `find_ambiguities` returned nothing and the interpreter cost zero.
Proving R-1's bounds on live data is a K7 job, and `scripts/ambiguity_fire_rate.py` is its report.

### 6.4 K1a — the roster is awake, by the gate's own command

```
python scripts/unit_reachability_report.py --org org_k1_pilot --database-url <scratch>
```
```
situations=60 reasoned=60
units emitting findings: 12
  [PASS] roster_v2_activated
  [PASS] units_emitting_findings_at_least_12
  [PASS] every_silent_unit_is_receipted
  [PASS] plan_hash_deterministic
  [PASS] every_declared_source_is_registered
K1a: PASS
```

20 of 20 units accounted for: 15 scheduled and completed, 3 skipped with
`no_declared_input_available`, 2 declined at the manifest with
`no_declared_field_in_this_expertise` naming the fields they looked for. `core.risk` emits
`risk.momentum_decay` **and** `risk.relationship_health`, as the gate asks.

Two things the PASS does not say, and §5.2/§5.3 do: the count is **exactly** 12, not comfortably
above it; and `core.impact` and `core.opportunity` are recorded as *"ran, published no finding: (no
reason codes)"* — a unit that ran, said nothing, and gave no reason. That is a receipt gap inside a
row that passes.

### 6.5 Zero published unit metrics renamed — measured, not asserted

Extracted the `publishes` set of every registered unit from `git archive HEAD` and from the working
tree and diffed them:

```
units removed: []      units added: []
core.timeline: LOST=[]  GAINED=['deadline_hours', 'urgency_bp']
metric names: 87 at HEAD -> 89 now      renamed/removed: 0
```

Purely additive, and the two additions are U5's urgency ladder. **K1a's "zero published metric
names changed" row: PASS.**

### 6.6 The preserve-hard list — 10 mutations, 10 kills

Each mutation applied to the shipped source one at a time, the suite re-run with `-x`, the source
restored. Every line below is "at least one test failed".

| # | Invariant (doc 08) | Mutation | Result |
|---|---|---|---|
| 2 | plan hashing | `plan_hash` stops being a function of the plan | **1 failed**, 606 passed |
| 2 | skip receipts | `dependency_not_scheduled` receipt dropped — a silent drop | **1 failed**, 594 passed |
| 2 | latency refusal | over-budget plan no longer refused | **1 failed**, 50 passed |
| 5 | store fails closed | `_integrity_equal` accepts a tampered payload | **1 failed**, 587 passed |
| 1 / 10 | one decider | the formula returns a constant instead of deciding | **1 failed**, 326 passed |
| 10 | divergence recorded | `formula_utility` no longer written to `score_components` | **1 failed**, 515 passed |
| 7 | degraded confidence cap | the cap stops binding on a degraded run | **1 failed**, 296 passed |
| — | Rule 11 | an uncited confidence raise is accepted | **1 failed**, 281 passed |
| 3 / 8 | operational floor | `DEFAULT_CONFIDENCE_FLOOR_BP` back to 0 | **1 failed**, 303 passed |
| 4 | elimination chain | eliminated candidates marked eligible | **1 failed**, 109 passed |

**A warning worth recording:** running this harness concurrently with a measurement produced a
false finding. The `formula_utility` mutation was live in the working tree while I was replaying
the pilot, and the replay reported **60/60 mismatched**. It is 60/60 identical. Mutation harnesses
edit the tree; nothing else may read it while they run.

### 6.7 The collision check

Two agents edited `decision_maker.py` in parallel (ranking/utility and confidence/floor) and two
more edited the bundle surface. The predicted collision did **not** happen:

* **one gate.** `reason/llm_sites.py` opens with *"THERE IS EXACTLY ONE C5 GATE, AND IT IS
  `reason/bundle/gate.RSiteGate`"* and delegates activation, budget, retry and receipting to it.
  `grep '\.consult('` returns two call sites, both into that one gate. No module in `reason/`
  mentions `anthropic` or an LLM client except `llm_sites.py` and `bundle/sweep.py`, and both go
  through the gate.
* **two narrators, two sites, no overlap.** `narration.py` is R-3/R-4; `bundle/narrator.py` is R-2.
* **one weight scale.** `ranking_weight_scale()` is the seam that stops a v2 manifest reaching a v1
  scorer; `_weighted_utility` writes the legacy branch out in full rather than folding it in,
  deliberately, because the v1 lane accepts float weights and float addition is not associative.
* **one divergence.** `formula_utility` is a property over `score_components`, not a second stored
  field — so the two cannot disagree.
* **one confidence path.** `calculate_confidence` is a thin wrapper over `compose_confidence`;
  there is no second composition.

The collision that DID happen was **between rounds, not within this one**: the parallel Layer 2
admission work and Layer 4's compiled lane, four times over (§6.1).

### 6.8 Wiring — every new module is reached from a real path

| Module | Reached from |
|---|---|
| `platform/l4_activation.py` | `api/admin_routes.py` (4 routes), `reason/domain_shadow.py`, `api/account_routes._wipe` |
| `reason/adapters/situation_projection.py` | `reason/adapters/{__init__,native,expertise}.py` |
| `reason/evidence.py` | `reason/store.py` |
| `reason/interpretation.py` | `reason/domain_shadow.py` (`make_interpreter`) |
| `reason/llm_sites.py` | `reason/narration.py`, `reason/interpretation.py`, `reason/bundle/sweep.py` |
| `reason/narration.py` | `api/intelligence_routes.py` |
| `reason/bundle/` | `reason/runner.run_all` (`narrate_published`), `api/intelligence_routes.py` |
| `reason/critique.py` | `api/l4_seam_routes.py` |
| `reason/brief_ranking.py` | `api/l4_seam_routes.py` |
| `api/l4_seam_routes.py` | `main.py` (`include_router`) |

**Zero unreached units.** Thirteen shipped across L1–L3; none here.

### 6.9 Tuning check — every weight, floor and threshold this round touched

Doc 08: *"a gate passed by moving a weight is the exact defect these gates exist to catch."*

| Constant | Before | After | Verdict |
|---|---|---|---|
| `ranking_weights` | 5 keys / 100 | 6 keys / 10000, importance 2500 | **the specified change** (doc 04 E1's table, unchanged) |
| `OVERRIDE_FORMULA_WEIGHT` / `_PRIOR_WEIGHT` | override replaced the formula | 7 / 3 | **the specified change**; the divergence is now recorded on 180/180 candidates so the retirement review has the evidence doc 08 asks for. **Not reviewed by taste, and not moved by me.** |
| `DEFAULT_CONFIDENCE_FLOOR_BP` | 0 (default) | 4500 | **the specified change** (doc 01 C6 seeds 4500) |
| `latency_ceiling_ms` | undeclared | 1500 on the roster manifest | new declaration; the refusal itself is untouched (mutation PH2c) |
| unit latency budgets | — | 20–40 ms per unit | declared for the new roster; tuned budgets, never the refusal |
| `MIN_DISTINCT_UTILITIES` / `MIN_DO_NOTHING_COMPUTED_BP` | — | 50 / 8000 | the gate's own thresholds, quoted from doc 04 |
| **the starvation rule** | asymmetric | symmetric | **a behaviour change in a preserve-hard file**, recorded in §4 · Z1. It makes MORE units run, not fewer. |

**No threshold was moved to make a gate pass.** The one row I could have bought — K1's below-floor
DEFERs — is reported as NOT MET rather than bought by lowering 4,500.

### 6.10 The standing doctrines, each checked

| Doctrine | Check | Result |
|---|---|---|
| Score, rank, priority, permission, policy, elimination and confidence composition stay deterministic | the gate answers "may a model be consulted", never "what should happen"; §6.3's four attacks | **holds** |
| Integer basis points; no float, no `round`, no `statistics`/`numpy` | grep of `decision_maker.py`, `plan.py`, `bundle/gauntlet.py` | **zero floats** — only version strings and integer floor-division (`headroom * earned // 10_000 // 2`). The floats that exist in `reason/` are in `baselines.py` and `foresight.py`, pre-existing and untouched by this wave |
| No clocks in logic; `eval_time` is a parameter | grep of `reason/` for `datetime.now` | **every hit is `eval_time = eval_time or now(...)` at a process boundary**; `plan.py` and `decision_maker.py` contain no clock at all |
| No claim without a receipt | 20/20 roster units accounted for; every silence reason-coded; `l4_r_site_calls` records every consult including the ones where no model ran | **holds**, with the §6.4 gap named |
| No L1/L2/L3 contract file modified | `git status genios_engine/contracts/` | **three modified, all additive, none of them a shape change.** `reasoning.py` is Layer 4's own contract (the wave's subject). `events.py` gains `INTELLIGENCE_API_SCOPES` — a new third scope family, deliberately not folded into the two that exist, so no grant a tenant already issued is widened. `situation.py` gains `"partial"` to `SITUATION_STATES` and four compatibility views, and belongs to the **parallel Layer 2 round**, not to this one. Strictly, the instruction was "only new files under `contracts/`"; this is the deviation, reported rather than hidden, and no stored hash moved |

---

## 7. Verdicts (as at the end of the wave — superseded by §12.6)

| Gate | Verdict | The decisive number |
|---|---|---|
| **K0** contracts | **PASS** | 61 contract tests, 0 skips; old shapes round-trip byte-identically against the pre-wave file; `advisory` unfalsifiable including through `model_copy`; v2 weights validated to 10000; V-3 rejects a mismatched bundle at construction |
| **K1a** the roster is awake | **PASS**, with two caveats | the gate's own command: 12 units emitting findings, 20/20 receipted, `plan_hash` deterministic, every declared source registered. **Caveats:** `urgency_bp` is a constant 0 on 60/60 (§5.2) and 11 of 15 running units emit one identical output for all 60 situations (§5.3). K1a's `urgency_bp` row is **NOT MET.** |
| **K1** the formula finally decides | **PASS on 6 of 7 rows** | 120 distinct utilities (gate 50) · importance isolated and exact to the basis point · 180/180 divergence recorded · 100% `do_nothing` computed · 60/60 byte-identical replay. **Below-floor DEFERs = 0: NOT MET** (§5.4) |
| **K2** evidence | **PASS** | one `build_evidence_ref()`; permanent digests (0117) re-derived from the payload while it lives and digest-verified after it expires; a tampered payload still fails closed (mutation PH5); `Finding.unit_ref` derived, never stored |
| **K4** the voice | **doctrine PASS · gate INCOMPLETE** | four attacks, 0 of 60 decisions moved, including a model instructed to contradict the decision — refused by name. **Fallback rate, citation fidelity on real prose, and the 25-bundle golden review are unmeasured**: no model is reachable here (§5.6) |
| **K5** seams in | **PASS in code, NOT measured live** | 540 projected situation facts and 420 unknown-typed fields on the pilot, so a BSO reading reaches a unit as a declared fact and UNKNOWABLE projects as unknown. The corpus-rule elimination row is proven by `tests/reason/adapters/test_seams_in.py` but its live counterpart (`test_seams_in_reach_a_signal.py`) is in the 51 red (§5.1) |
| **K6** seams out | **PASS in code, NOT measured live** | contracts and routes exist and are mounted; `advisory` is unfalsifiable (mutation-proven at K0). Every live test of both seams is in the 51 red (§5.1) |

**And the standing condition:** doc 08 requires **G7, H5 and K1 on the same pilot in the same
fortnight.** On `org_k1_pilot` all three hold on one tenant in one run — L1 supplied 60 distinct
`alg17-v1` importances, L2 composed 60 distinct situation importances from them, and L4 ranked with
them to 120 distinct utilities. That is the first time the chain has closed end to end.

### The three-layer trace, one situation, every hop

```
L1  qualified_signals sig_l1supply_41   importance_bp 8487   importance_version alg17-v1
                                        evidence_refs[0] verified=true, offsets 0..19 coherent
L2  context_situations sit_…            importance_bp 8487   importance_source l1_qualified_signals
                                        admission: ADMIT (qes_required + verified_evidence_required both satisfied)
L3  ExpertisePackage expertise_…        capability expertise.account_admin
                                        citation admin.heu.commitment_tracking.forgotten_beats_broken_for_damage
                                        statement_hash e137ff22…471e  (byte-identical, re-checked by require_citation)
L4  capability.metadata.situation_importance = {importance_bp: 8487, source: l1_qualified_signals, fallback: false}
    score_components  importance 8487 -> formula_utility 4872 -> final_utility_bp 4760
    ranking_weights@2 · do_nothing {source: computed} · replay: byte-identical
```

The hop that had never happened before this wave is the fourth line: `importance_bp` existed only
in a SQL select under `reason/`, and now it is 2,500 of the 10,000 basis points that decide.

---

## 8. What K7 needs — exact commands

K7 is the 7-day pilot: five features on, a real tenant, no mid-week switch-off, and the
Theory-chat AWS scenario reproduced on live data. **It cannot start until §5.1 is closed** — a
pilot cannot be read against a red suite.

```bash
# 0. PRECONDITION -- the suite must be green first (see §5.1)
createdb l4_pilot_check
GENIOS_TEST_DATABASE_URL="postgresql://…/l4_pilot_check" ./.venv/bin/python -m pytest tests -q -p no:randomly
dropdb l4_pilot_check

# 1. activate the five features for ONE tenant, in wave order -- a row, never a global default
#    missing_preconditions() is REPORTED on every write; read it, do not ignore it
curl -X POST $API/admin/l4-activation -H "$ADMIN" \
     -d '{"org_id":"<pilot>","feature":"roster_v2"}'
#    then: ranking_v2, bundle, critique, brief -- in that order

# 2. confirm the tenant's L1 supply, or the admission gate will hold every situation silently
psql -c "select importance_version, count(*) from qualified_signals
         where org_id='<pilot>' group by 1"                    -- expect alg17-v1, not unscored
psql -c "select outcome, reasons::text, count(*) from situation_admission_decisions
         where org_id='<pilot>' group by 1,2"                  -- expect admit >> hold

# 3. let it run seven days. then read the four gate reports, in this order
python scripts/l1_end_to_end.py                  --org <pilot> --since 7d   # G7 still holds
python scripts/situation_importance_distribution.py --org <pilot> --since 7d # H5 still holds
python scripts/unit_reachability_report.py       --org <pilot>              # K1a
python scripts/ranking_distribution.py           --org <pilot> --days 7     # K1
python scripts/confidence_floor_distribution.py  --org <pilot> --days 7     # the floor -- see §5.4
python scripts/bundle_review.py                  --org <pilot> --sample 25  # K4's golden review
python scripts/ambiguity_fire_rate.py            --org <pilot> --days 7     # R-1

# 3b. to rebuild the gate's own 60-decision population on a scratch database at any time:
createdb l4_pop && python scripts/l4_pilot_seed.py \
    --database-url postgresql://…/l4_pop --situations 60

# 4. the two rows this record reports as NOT MET -- check them FIRST, they are the pilot's job
#    (a) does urgency_bp stop being a constant on a tenant with real dates?
psql -c "select output->'metrics'->>'urgency_bp' u, count(*) from reasoning_reasoner_results
         where org_id='<pilot>' and reasoner_id='core.priority' group by 1 order by 2 desc"
#    (b) do below-floor DEFERs appear once confidence stops being a constant?
psql -c "select outcome_kind, count(*) from reasoning_run_outputs
         where org_id='<pilot>' group by 1"     -- expect some 'defer'

# 5. every silence must name itself -- read the distribution, not the total
psql -c "select decision_core->>'suppression_reason' r, count(*) from reasoning_run_outputs
         where org_id='<pilot>' group by 1 order by 2 desc"

# 6. the doctrine test, on the pilot's own rows, before trusting a single card.
#    NOT with the env var set: three tests in this file measure the SWITCH ITSELF
#    (`assert not force_fail_r_sites()`) and go red when it is already on. The
#    byte-identical-under-force-fail property is asserted INSIDE the file, by
#    test_with_every_r_site_force_failed_a_full_replay_is_byte_identical.
python -m pytest tests/reason/test_bundle_doctrine.py -q
```

**K7 also needs one thing this environment could not give it: a real model run.** Until
`bundle_review.py --sample 25` runs against live generations, K4's fallback rate, citation
fidelity on real prose and the 10-second test are open (§5.6).

---

## 9. Database

| Migration | What |
|---|---|
| `0116_l4_activation` | the per-tenant, per-feature activation row + deactivation stamping |
| `0117_l4_evidence_digests` | S3's permanent content-addressed evidence digest, outliving the 720h payload TTL |
| `0119_l4_brief_rankings` | E3's daily book-level re-rank |
| `0120_l4_reasoning_bundles` | the narrative, cached on `decision_hash` |
| `0121_l4_r_site_generations` | `l4_r_site_calls` — every consult's site, outcome, reason codes and cost |
| *(`0118`)* | **never written** — a gap in the sequence, harmless |

All five are in `account_routes._ORG_SCOPED_TABLES`, so a tenant reset erases them through the live
wipe path.

---

## 10. Running it

```bash
createdb <unique-scratch>
GENIOS_TEST_DATABASE_URL="postgresql://harshtripathi@localhost:5432/<unique-scratch>" \
  ./.venv/bin/python -m pytest tests -q -p no:randomly
dropdb <unique-scratch>
```

Never without `GENIOS_TEST_DATABASE_URL` — the hermetic lane silently skips ~800 real-Postgres
tests and reports that everything is fine. Never against production.

---

## 11. Next — REWRITTEN BY THE FIX-ROUND GATE, see §12.7

Items 1, 2 and 3 below are **done**: the suite is green, `urgency_bp` is a measurement, and the
"11 of 15" figure is now 3 of 18. Kept here struck through rather than deleted, so the record
shows what was asked and what answered it.

1. ~~**Close §5.1.**~~ **DONE** — 0 failed, 0 errors, 0 skipped (§12.6).
2. ~~**§5.2 — make `urgency_bp` a measurement.**~~ **DONE** — eight ladder rungs at
   `core.timeline`, 20 distinct at `core.priority`. The wave's "constant 0" was the fixture
   (§12.1), and the real defects were `parse_due` refusing a naive ISO date and
   `compute_deal_view` traversing one edge direction (§12.5 M4, M5).
3. ~~**§5.3 — 11 of 15 units say the same thing.**~~ **PARTLY** — 3 of 18 on a tenant with real
   supply, and those three are named with a verdict each (§12.2). **`core.impact` is the one to
   fix next**: 2,000 of the 10,000 ranking basis points, constant on 372 of 372 candidates.
4. **§5.6 — one real model run**, then K4's three open rows close in an afternoon. *Unchanged.*
5. **K7 is unblocked.** The precondition in §8 step 0 is satisfied.
6. Review the 70/30 override weight **with the recorded divergence data** (510 rows across the two
   populations now carry it), never by taste — doc 08's retirement condition.
7. **§12.7 items 2, 3, 4 and 6** — the two unreceipted zeros, the Law-5 domain token,
   `l1_scoring_active`'s sweep-vs-tenant scope, and `ranking_distribution`'s wall-clock window.

---

## 12. The fix round and its gate — 2026-09-08 evening

Four agents closed the 51 red tests. This section is the **gate's own** re-measurement: every
number below was produced by me, on populations I built through the production entry points, and
read back out of the tables afterwards. Where a number contradicts an agent's report, mine stands
and the contradiction is stated.

### 12.1 The one thing that changed how everything else is read: there are now TWO populations

`scripts/l4_pilot_seed.py` builds 60 situations that are identical in **every** input except
Layer 1's importance. That is exactly what K1 needs — it is why "importance is the only moving
input" is provable to the basis point — and it means **every other reading on that tenant is a
constant by construction.** The wave read `urgency_bp` and `core.confidence` off it and reported
both as "a constant, therefore NOT MET". Two of the three not-met rows were measuring the fixture.

Two facts, measured, that the wave did not have:

* the seeder's canned extraction emits `"due_at"`, and **nothing in the pipeline reads that key**
  — the extraction contract carries `due_text` (`context/qes_adapter` writes it,
  `pipeline.parse_due` reads it). So `_is_a_promise` never got a date, no `commitment` node was
  ever created, and the graph for `org_k1_pilot` holds **zero `commitment.*` facts**. The U5
  ladder's `no_material_date` 0 was the correct reading of a tenant with no dates.
* `scripts/l4_pilot_seed.py` never runs the derived roll-ups. `context/runner.py:544-559` runs
  `compute_derived` → `compute_deal_view` → `compute_account_view` **before** the situation
  refresh, and that pass is the only thing that puts a person's soonest open `commitment.due_at`
  onto the company node a situation is anchored on. Without it no date can reach Layer 4 even
  when one exists.

So `scripts/l4_urgency_floor_pilot.py` is new, and `l4_pilot_seed.py` is deliberately **untouched**
so K1's numbers stay byte-comparable. The second population drives the same entry points and
varies what K1 holds still: 54 situations across all seven rungs of the U5 ladder plus both
absence states, and 1–3 sources × 1–4 events so Layer 2's own confidence vector varies.

```bash
createdb l4_urgency && python scripts/l4_urgency_floor_pilot.py --database-url postgresql://…/l4_urgency
```

### 12.2 The three NOT-MET rows, re-measured

**`urgency_bp` — MET.** On the population that carries dates, `core.timeline` publishes eight
distinct readings and they are the U5 ladder, rung for rung:

| `urgency_bp` | 10000 | 9000 | 7500 | 6000 | 4000 | 2000 | 500 | 0 |
|---|---|---|---|---|---|---|---|---|
| situations | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 12 |
| `deadline_hours` | −72 | 24 | 144 | 312 | 552 | 1464 | 6840 | *(none)* |

`core.priority` — the authority — resolves **20 distinct** values, because max-wins also picks up
`core.temporal`'s decay reading on the undated situations. The ranking's urgency term carries 20
distinct values across 372 candidates. Not a spike at 0, not at 5000, not anywhere. **On
`org_k1_pilot` it is still 0 on 60 of 60, and that is now known to be right**: that tenant has no
dated obligation of any kind.

**Below-floor DEFERs — MET, and the floor is a floor rather than a wall.** `core.confidence`
returns four distinct values on the second population and the 4,500 floor cuts between them:

| `confidence_bp` | 3300 | 4100 | 4900 | 5700 |
|---|---|---|---|---|
| situations | 14 | 14 | 13 | 13 |

**26 decisions, 28 DEFERs.** Each DEFER names itself *and* names what would resolve it —
`below_confidence_floor:4100<4500`, then `below_floor_missing_field:meeting.start_at`,
`…:situation.cohort` and the rest — which is E3's acceptance row, not merely its reason code.
`scripts/confidence_floor_distribution.py`'s own standard is *"a floor nothing trips and a floor
everything trips are both wrong"*; on this tenant it trips 52% of the time.

**The per-unit output table — 11 of 15 becomes 3 of 18.** 18 units now produce results (three
that the wave recorded as `skipped:no_declared_input_available` — `core.temporal`,
`core.resource`, `core.scheduling` — are fed on a tenant with real supply), and K1a's report reads
**15 units emitting findings** against its gate of 12.

| distinct outputs over 54 situations | units |
|---|---|
| 54 | `core.context` `core.cost` `core.temporal` `core.timeline` |
| 46 / 22 / 20 | `core.tradeoff` · `core.priority` · `core.scheduling` |
| 15 / 15 | `core.alternative` · `core.resource` |
| 4 / 4 | `core.confidence` · `core.constraint` |
| 2 | `core.dependency` `core.planning` `core.recommendation` `core.validation` |
| **1** | **`core.impact` · `core.opportunity` · `core.risk`** |

The verdict on each of the three that remain, and none of them is fixed:

* **`core.risk` → `{"risk_bp": 1000}`, codes `deal_momentum_risk` + `relationship_unmeasured`.**
  Honest and receipted, worth nothing to a ranking. It also still carries §5.7's Law-5 domain
  token on an `account_admin` situation. **NOT MET.**
* **`core.opportunity` → `{"opportunity_bp": 0, "opportunity_count": 0}`, and NO reason codes.**
  A unit that ran, published a zero, and did not say why. §6.4's receipt gap, still open. **NOT MET.**
* **`core.impact` → `{"impact_signal_count": 0}`, no reason codes, and no `impact_bp` at all.**
  Impact is **2,000 of the 10,000 ranking basis points** and its term is a constant on 372 of 372
  candidates — the same defect urgency had, one component over. **NOT MET, and it is now the
  largest single dead weight in the formula.** `risk` and `success` are constants too; three of
  the six ranking components do not move on either population.

### 12.3 Bought rows — the diff, stated even though it is empty

Every module-level constant in every file the fix round touched
(`situation_publisher` · `domain_shadow` · `confidence` · `timeline_unit` · `temporal` ·
`derived` · `pipeline` · `runner` · `replay` · `decision_maker` · `contracts/reasoning`) was
diffed against `git archive HEAD`. **Not one constant that existed before was removed, renamed, or
had its value changed. Every difference is an addition.**

| Named in the brief | Value now | Where it came from | Moved? |
|---|---|---|---|
| the confidence floor | `DEFAULT_CONFIDENCE_FLOOR_BP = 4_500` | doc 01 C6 / doc 04 E3 | **no** |
| ranking weights | importance 2500 · impact 2000 · urgency 2000 · success 1500 · effort 1000 · risk 1000 | doc 04's table, exactly | **no** |
| the override demotion | 70/30, integer `//10` | doc 04 | **no** |
| the urgency ladder | 10000 / 9000 / 7500 / 6000 / 4000 / 2000 / 500, undated **0** | doc 02 U5, rung for rung | **new, and spec-exact** |
| Rule 11's raise gate | uncited raise ⇒ `ConfidenceViolation`, fail closed | doc 04 E2 | **no — and it was TIGHTENED**, see below |
| a defaulted urgency | `URGENCY_UNDATED_BP = 0`, `NEUTRAL_URGENCY_BP = 5_000` unchanged | U5: *"No date → 0, never neutral"* | **no** |

Two changes deserve to be read as design changes rather than as fixes, and both tighten:

* **Rule 11 was narrowed, not widened.** `core.confidence` now excludes the `unattributed`
  independence pool from `independent_evidence_groups`. R-1 mints its interpretation into that
  pool, and before this an interpretation moved groups 2→3, coverage 5000→7500 and confidence
  6700→6950 — a model output raising the number the floor is applied to, which is the doctrine's
  *"may never PERMIT"*. Mutation M7 (`if name}`) kills 2 tests.
* **`core.confidence` gained an L2 ceiling** (`SituationTrustPlugin`): the minimum of Layer 2's
  own per-axis situation confidence, taken as a **ceiling** via `min`, never as a raise. This is
  not an invention — doc 04 E2's rule opens *"start: the BSO's confidence vector, per dimension
  (L2 owns the starting point)"*, and until now nothing in Layer 4 read it. It is the reason the
  constant 6,250 became a measurement. Mutation M6 kills 6 tests.

**The one honest consequence, stated plainly.** On `org_k1_pilot` the ceiling binds at 3,300 —
Layer 2's own `confidence_evidence` reading for a company with one email from one source — so all
60 decisions now DEFER where they used to decide, and `scripts/ranking_distribution.py` reports
`VERDICT FAIL` on that tenant for want of decisions to score. That is Law 3 working, not a
regression: `situations.evidence_score(event_count=1, source_count=1) = 33`, and an engine that
speaks about a single unconfirmed email is the thing the floor exists to stop. It does mean **the
K1 report must be run on a tenant with real evidence**, which is what §12.1's second population is
for. On it, `ranking_distribution` reports **VERDICT PASS** — 107 distinct utilities, 330/330
`formula_utility`, do-nothing computed on 26/26, `ranking_weights@2`.

### 12.4 K1 did not move — re-measured on the wave's own population

| K1 row | Wave | Re-measured by this gate |
|---|---|---|
| distinct `final_utility_bp` (gate 50) | 120 | **120** |
| `formula_utility` recorded | 180/180 | **180/180** |
| divergence recorded | 180/180 | **180/180** (`checks.divergence: true`) |
| `do_nothing` marked `computed` | 60/60 | **60/60** |
| `ranking_weights_version` | `ranking_weights@2` on 60/60 | **`ranking_weights@2` on 60/60** |
| byte-identical replay | 60/60 | **60/60 identical, 0 mismatched, 0 raised** |
| importance isolated | Δimp 6987 × 2500/10000 = Δformula 1747 | **8487−1500 = 6987 → 4872−3125 = 1747, exactly**; `count(distinct components − importance − formula_utility) = 1`; endpoints 3537 and 4760, unchanged to the basis point |
| K1a, the gate's own command | PASS, 12 units emitting | **PASS on both populations**; 12 on `org_k1_pilot`, **15** on the second |
| published unit metrics | 87 → 89, additive | **87 → 90, additive**: `deadline_hours`, `situation_trust_bp`, `situation_trust_axis_count` added; **0 removed, 0 renamed, 0 units added or removed** |

**The doctrine, re-run and re-attacked.** All 114 runs across both populations replay
byte-identically **with every R-site force-failed** — hash-for-hash equal to the unforced replay.
Then the production narration sweep (`narrate_published`) was driven with a model shaped exactly
as R-2 asks whose every field said *"DO NOTHING. Escalate to legal and cancel the account"*,
asserted its own `confidence_bp 10000` / `urgency_bp 10000`, and named an entity that is not in
the situation. 52 model calls, 26 generations reached the gauntlet, **26 of 26 refused by name** —
`contradicts_decision`, `bare_number`, `out_of_scope_entity` — every bundle `template_fallback`,
and the md5 over every `reasoning_run_outputs` row and every `reasoning_candidates` row is
**byte-identical before and after**. The model cannot choose, score or permit.

### 12.5 Mutations — every fix, and all twelve preserve-hard invariants

| # | Mutation | Tests killed |
|---|---|---|
| M1 | the admission gate made unconditional again (`l1_scoring_active` removed from `_preflight`) | **3** |
| M2 | `l3_pilot_seed` loses its Layer 1 supply | **16 errors** — the original `KeyError: emitted` signature, exactly |
| M3 | `l2_shadow_diff`'s anchor join loosened back to a `left join` | **8** |
| M4 | `parse_due` stops normalising a naive ISO date to the base's zone | **3** |
| M5 | `compute_deal_view`'s account↔person hop goes back to one direction | **3** |
| M6 | `SituationTrustPlugin` removed from `core.confidence`'s roster | **6** |
| M7 | the `unattributed` pool counts as an independence group again | **2** |
| M8 | the K1 report's NO-DATA branch collapses back into `FAIL` | **1** |
| M9 | …and the reverse: NO DATA swallows a real flat-lane FAIL | **1** |
| PH1 | `decision_maker` imports `reason.bundle.narrate` | **1** — *see below; this test did not exist before tonight* |
| PH2 | `plan_hash` made non-deterministic | **4** |
| PH3 | the orchestrator executes `plan.steps` in reverse | **9** |
| PH4 | the elimination chain never eliminates | **4** |
| PH5a | `store.py` stops raising on a replay integrity mismatch | **1** |
| PH5b | `store.py` stops raising on a tampered evidence digest | **1** |
| PH6 | the below-floor DEFER stops appending its reason code | **4** |
| PH7 | the degraded-run confidence cap never applies | **3** |
| PH8 | `DEFAULT_CONFIDENCE_FLOOR_BP` → 0 | **13** |
| PH9 | the gauntlet's `passed` returns `True` unconditionally | **20** |
| PH10 | `formula_utility` no longer recorded beside the override | **5** |
| PH11 | a published unit metric renamed (`deadline_hours` → `deadline_hours_v2`) | **31** |
| PH12 | `tests/conftest.py`'s `GENIOS_DATABASE_URL` pin removed, with an outside URL present | **2** |

**PH1 had no test, and the build record said it did.** §3 recorded Law 1 as verified by
"grep + mutation PH1". The grep was true, but injecting
`from genios_engine.reason.bundle import narrate` at the top of `decision_maker.py` left the
**entire suite green** — the one law the doctrine rests on could have been broken by an import
completing an otherwise ordinary refactor. `tests/reason/test_bundle_doctrine.py::
test_the_decider_imports_nothing_that_can_narrate_or_call_a_model` was written tonight, reads the
AST (so a function-body import is caught too), and turns that mutation red.

### 12.6 Verdicts, superseding §7

| Gate | Verdict | The decisive number |
|---|---|---|
| **the suite** | **GREEN** | `9627 passed, 152 xfailed, 1 warning in 381.86s` — **0 failed, 0 errors, 0 skipped**, virgin scratch Postgres, run three times on three virgin databases (9,625 before tonight's two added tests, 9,626 after the first, 9,627 after the second) |
| **K0** contracts | **PASS**, unchanged | |
| **K1a** the roster is awake | **PASS — and its `urgency_bp` row is now MET** | 8 ladder rungs at `core.timeline`, 20 distinct at `core.priority`; 15 units emitting findings against a gate of 12. **The 11-of-15 caveat becomes 3 of 18 and those three stay NOT MET** (§12.2) |
| **K1** the formula finally decides | **PASS on 7 of 7 rows** | 107 distinct utilities · 26 decisions and **28 below-floor DEFERs**, each naming its missing field · 330/330 divergence · do-nothing computed 100% · 114/114 byte-identical replay · importance still isolated to the basis point on the wave's own population |
| **K2** evidence | **PASS**, unchanged; both fail-closed paths mutation-proven (PH5a, PH5b) | |
| **K4** the voice | **doctrine PASS, re-attacked by this gate · gate still INCOMPLETE** | 26 of 26 hostile generations refused by name, 0 rows moved. **Fallback rate and the 25-bundle golden review remain unmeasured** — still no model reachable here (§5.6) |
| **K5 / K6** the seams | **PASS in code; their live tests are now green** | the 51 red are closed, so §5.1's reason for holding these back is gone; a live *population* measurement is still K7's |

### 12.7 What is STILL open — nothing here is dropped

1. **`core.impact` is a constant on the ranking.** 2,000 of 10,000 basis points, one identical
   output on 372 of 372 candidates, and no reason code saying why. `core.risk` (1,000 bp) and
   `success` (1,500 bp) are constants too. **Three of six ranking components do not move.** This is
   §5.3's defect, reduced but not closed, and it is the next K1-class piece of work.
2. **Two units publish a zero with no receipt.** `core.impact` and `core.opportunity` run, emit,
   and give no reason codes. Law 6 says every silence names itself; these two do not.
3. **§5.7's Law-5 breach stands.** `core.risk` still publishes `deal_momentum_risk` on an
   `account_admin` situation.
4. **`l1_scoring_active` is measured per SWEEP, not per tenant.** `domain_shadow` computes it from
   the situations in the current pass (`limit`, default 500). A tenant Layer 1 *is* scoring whose
   sweep window happens to hold only unscored situations gets the relaxed gate for that batch —
   those candidates are admitted carrying `ImportanceBasis.UNSCORED` instead of being held for a
   retry that would have worked. The failure mode is "decide without importance and say so", which
   is survivable and receipted, but the docstring claims the flag is *"a property of the tenant's
   supply, never of one situation"* and it is not yet. The fix is one `select exists` against
   `qualified_signals` for the org rather than a fold over the sweep's slice.
5. **§5.6 is untouched.** K4's `< 15%` fallback row and the 25-bundle golden review still need one
   real model run.
6. ~~**`scripts/ranking_distribution.py` reports FAIL for an empty window.**~~ **CLOSED tonight.**
   `--days` counts back from the WALL clock, so every seeded or historical population in this
   repository read `VERDICT FAIL` — "the ranking is broken" — when the truth was "you looked in
   the wrong week", and a gate that can say FAIL for that gets disbelieved once and ignored
   afterwards. The verdict now renders `NO DATA` with the remedy on the line. **`passed` is
   unchanged and still False for an empty window** — its docstring's rule (*"a gate that returns
   green for an empty table is how 'the model never ran' reads as success"*) is untouched, and
   `test_an_empty_window_reads_as_no_data_and_not_as_a_failing_engine` pins BOTH directions:
   mutations M8 and M9 each kill it.
7. **K7 is now unblocked.** §5.1's precondition — "a pilot cannot be read against a red suite" —
   is satisfied.

### 12.8 Two questions the fix round had to answer, checked rather than accepted

**The admission gate (cluster B): the agent scoped a fail-closed gate, and that was right.**
Every one of its four supporting claims was verified against the source, not taken on the report:
migration `0122`'s `situation_admission_hold_retry` constraint really does require
`reevaluate_after` on every held row, so a hold on a tenant whose scorer will never run is a
promise nothing keeps; L2.5.8 really does specify *"a deterministic floor check against the
confidence vector"* and a missing L1 score is an activation state rather than a confidence axis;
`decision_maker.IMPORTANCE_ABSENT_REASON = "L2_IMPORTANCE_NOT_ACTIVE"` really does exist and an
unconditional gate makes it unreachable on every tenant; and `context/importance.assess_l1_supply`
really does answer the identical question the other way one module over. The half that must never
be conditional — **no claim without a receipt** — is untouched: `verified_evidence_required`,
`identity_review_required`, `source_coverage_insufficient`, `conflict_open` and
`pattern_evidence_required` all still fire on every tenant whatever Layer 1 did. The residual is
§12.7 item 4, which is a scope bug in the measurement, not in the decision.

**The duplicate situation (cluster C): there is no duplicate.** Measured on my own population with
`context/periodic.refresh_period_situations` driven at the sweep clock: 54 anchored
`account_admin` situations, **one node to one situation, no exceptions**. Exactly one node carries
more than one row — the synthetic **tenant** node, carrying `admin_period_review`,
`pipeline_period_review` and `support_period_review`, one per domain per period, with no
`context_correlations` row behind any of them. That is what a period review *is*: its subject is
the org over a window, not a correlated group of events. **What a founder sees** is 54 account
cards plus at most one weekly review per domain — three org-level rows, not three copies of
anything. The fix was in the *reader*: `scripts/l2_shadow_diff.read_anchor_situations` now joins
`context_correlations`, which is this module's own definition of the anchor path, and the excluded
rows are printed under their own heading rather than dropped. Mutation M3 kills 8 tests.

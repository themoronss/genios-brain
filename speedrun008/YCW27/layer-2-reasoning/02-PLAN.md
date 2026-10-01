# L2 · the plan — sections → functions → components → units

**Written for:** Harsh (CTO) and Rohit. **Date:** 2026-09-30. **Status: PLAN ONLY — no code written.**

`reason/` 118 files / 40,065 lines + `packs/` 34 files / 7,957 lines = **48,022 lines.**

> ⛔ **This plan is written BEFORE the build**, unlike L3's — which was reconstructed after and had to
> mark itself as such. Read [`01-CROSSCHECK.md`](01-CROSSCHECK.md) first; this file only plans what
> that file measured.

---

## ⛔ Read this first: two of the four things we were told to build are wrong

`03-PROGRAM.md` specifies M11 as 4 units. The cross-check found:

| `03-PROGRAM.md` says | Reality | What this plan does |
|---|---|---|
| `M11.C1` plan compile **fails** when a scheduled unit names an unproduced source | ⛔ **would be a REGRESSION.** `plan.py:229` documents removing exactly this rule — it cost six units to one absent fact | **rewritten** as a receipt, not a refusal (S2) |
| `M11.C1.U02` a dropped unit leaves a `SkippedStep` naming its missing input | ✅ **already built** — `plan.py:258` | **verify it, do not build it** (S1) |
| *"the live defect that leaves two of `core.risk`'s three plugins silent"* | ⛔ **UNVERIFIED** — no source, no measurement, and unmeasurable while the API limit is on | **measure or withdraw, first** (S1) |
| `M11.C2` the five output lanes + router | ✅ genuinely missing | **stands, with two naming constraints** (S3) |

Plus one addition the cross-check found: **the five pipeline counters do not exist** (0 hits). Nothing
in this layer can be diagnosed without them (S4).

---

## The shape

**Seven sections, seventeen functions, eighteen units.** Two are complete. One section can only
*remove* work. Two cover the planes, and they were missing from this plan's first draft.

| | Section | Units | Done | What | Blocked? |
|---|---|---|---|---|---|
| **S1** | Prove the claims before changing anything | 2 | ✅ **2** | ⛔ deleted work rather than adding it | — |
| **S2** | A kept unit that lost a source says so | 3 | 0 | a receipt, never a refusal | no |
| **S3** | The five output lanes, and the router | 4 | 0 | new vocabulary, two naming constraints | after S4 |
| **S4** | The five pipeline counters | 2 | 0 | without a funnel nothing here is diagnosable | no |
| **S5** | ⛔ **Plane R — the unit contract** | 3 | 0 | 23 units, **0 declare what they read** | no |
| **S6** | ⛔ **Plane D — routing and the draft corpus** | 4 | 0 | 155 capabilities, 23 draft situations, 5 unrouted types | no |
| **S7** | The ConfidenceVector axes | 0 | — | ⛔ **Rohit's decision.** Blocks M13, not M11 | ⛔ yes |

### ⛔ S5 and S6 were missing from this plan's first draft

The first version said: *"touching `packs/` or `Domain Expertise/` YAML — nothing in the cross-check
found a defect there. Plane D is not in M11's scope."*

**That was wrong, and it was wrong because I never looked.** The cross-check measured `reason/`'s
orchestration and skipped both planes entirely. Measuring them found a defect in each, and the Plane R
one is the sharpest thing in this layer.

### Why this order

```
S1  prove            ✅ done — and it retired two units
S5  Plane R contract ─┐   (no dependency on anything; smallest real defect in the layer)
S6  Plane D routing  ─┤
S2  the receipt      ─┼─▶  S4  counters  ─▶  S3  lanes
S7  Rohit's decision ─┘    (blocks M13 only)
```

**S5 and S6 first among the unbuilt**, because both are contained: S5 is declarations on 23 classes
with an existing guard waiting for them, S6 is corpus edits with an existing validator. Neither
touches the orchestrator, so neither can break the passes above them.

**S3 last**, because it is the only section that adds a vocabulary other layers must consume.

---
---

# S1 · Prove the claims before changing anything

## What was expected

That `03-PROGRAM.md`'s M11 description was a specification we could build from.

## What is actually true

One of its two claims is already built, and the defect it names as *"live"* has no recorded
measurement anywhere in the programme.

## Why this is a section and not a footnote

Three layers, three false findings — L1's `no_model_wired`, L3's revision guard, and L2's starvation
rule. In every case the code's own comment said what the planning document did not. **Verification is
now a build step with units, not a habit.**

### F1.1 · Measure the `core.risk` claim, or withdraw it

**What:** find out whether two of `core.risk`'s three plugins are actually silent, and if so, why.

**How:**
1. A read-only probe script, in the shape of `scripts/l1_relevance_state.py` from L1 — `set
   transaction read only`, no writes, no `GENIOS_ALLOW_PROD_WRITE`.
2. It reads `reasoning_runs` / `reasoning_run_outputs` and counts, **per unit id**, how many runs
   scheduled it and how many produced a reading.
3. ⛔ It **splits the count by whether a model call was involved**, because every production number
   since 2026-09-25 11:09 UTC was taken with the API limit refusing all calls (L1 STEP-04).

**Why a probe and not a grep:** "silent" is a runtime property. A unit can be registered, scheduled,
dependency-complete and still never emit — which is precisely the class of defect this layer keeps
producing.

**⛔ Why the model split is mandatory:** a plugin silent because the model never answered looks
identical to one silent because its source was dropped. Without the split this measurement would
repeat `no_model_wired` exactly — *a count without its dimension is not a measurement.*

**Outcome — one of three, all acceptable:**

| Finding | Action |
|---|---|
| silent, and the cause is a dropped source | S2 is confirmed and gets a real failing case to build against |
| silent, and the cause is the API limit | ⛔ the claim is **withdrawn**, and S2 is justified on its own merits only |
| not silent | ⛔ the claim is **withdrawn** and `03-PROGRAM.md` is corrected |

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C0.U01` | `scripts/l2_unit_silence.py` | `uv run --no-sync python scripts/l2_unit_silence.py --assert-measured` |

### F1.2 · Verify `M11.C1.U02` rather than build it

**What:** `03-PROGRAM.md` asks for *"a dropped unit leaves a `SkippedStep` receipt naming the input it
lacked."*

**What is true:** `plan.py:258` already does it —
`SkippedStep(spec.reasoner_id, spec.version, "dependency_not_scheduled", orphaned)` — and
`reason/audit.py:62` reads the reason vocabulary back.

**How:** write the test the unit named, run it against the existing code, and **retire the unit** if it
passes. No production code changes.

**Why bother at all:** an unverified "already built" is exactly how L3's withdrawn Step 2 nearly became
a duplicate. A passing test turns a claim into a fact, and costs an hour.

**⛔ What we will NOT do:** refactor `SkippedStep`, rename the reason, or "improve" the receipt. It
works. Noticing something adjacent makes a new unit, not a silent edit.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C1.U02` → **retire on green** | `tests/reason/adapters/test_a_skip_names_its_missing_input.py` | `uv run --no-sync pytest tests/reason/adapters/test_a_skip_names_its_missing_input.py -q` |

---
---

# S2 · A kept unit that lost a source says so

## What was expected

`03-PROGRAM.md`: *plan compile **fails** when a scheduled unit declares a source no other scheduled
unit produces.*

## What is actually true  ⛔

That rule existed and was **deliberately removed.** `reason/plan.py:229`:

> *every* declared field had to be absent before a unit was dropped, but *any* dropped dependency
> dropped its dependent. ... `core.tradeoff` declares four evaluative sources, and under the any-rule a
> single unfed one ... removed tradeoff, then `core.alternative`, then `core.validation` and
> `core.recommendation` behind it — **six units lost to one absent fact.**

The settled rule: **a unit is dropped when it has NOTHING left to read.** Three of four sources
reporting is three readings.

## So what IS broken

`validate_capability_sources()` is called at `plan.py:370`, **after** `_select` dropped units — but it
validates the **manifest**, where the dropped unit is still declared. So:

```
manifest: A, B, C          B reads a_source = A       ✅ all four guards pass
_select drops A            (this situation cannot feed it)
plan schedules B           B reads A — and A will never run
```

**B stays scheduled, which is correct.** What is wrong is that **nothing records that B lost a
source.** Its absent sentinel fires silently, and a reading computed over three of four inputs is
reported as if it read four.

> ⛔ Same shape as `not_carried`, and as L1's coverage doctrine: **an answer computed over a narrower
> set of inputs than it declared, reported as if it read them all.**

## Why a receipt and not a refusal

| Refuse the plan | Record the loss |
|---|---|
| reverts a decision made for measured reasons | keeps the decision, adds the missing fact |
| six units lost to one absent fact — **worse** than the any-rule, which lost units; this loses the run | the run proceeds, and the gap is nameable |
| a silent failure becomes a loud one nobody asked for | a silent success becomes an honest one |

### F2.1 · The receipt contract

**How:** a `DegradedStep` record — unit id, version, the sources it declared, the ones actually
scheduled, and the ones lost. Carried on `ExecutionPlan` beside `skipped`.

**Why a new record and not a `SkippedStep` with a new reason:** a skipped unit produced **nothing**; a
degraded unit produced a **reading over fewer inputs**. Folding them into one list would make
*"how many units ran?"* unanswerable — and a consumer counting `skipped` would start counting units
that did run.

**⛔ Why it names what it DID get, not only what it lost:** *"lost `core.cost`"* does not say whether
three sources remained or zero. The first is a reading; the second cannot happen (the unit would have
been dropped). Recording both makes the receipt checkable against the starvation rule itself.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C1.U01a` | `genios_engine/contracts/reasoning.py` | `uv run --no-sync pytest tests/contracts/test_a_degraded_step_names_what_it_kept.py -q` |

### F2.2 · Compute it where selection happens

**How:** in `_select`, for every unit **kept**, diff its declared sources against the surviving set.

**Why there and not in a later validation pass:** `_select` is the only place that knows both the
declared set and the dropped set. A later pass would have to reconstruct the drop, and a reconstructed
fact can disagree with the original.

**⛔ Why it must not change what `_select` returns:** the starvation rule is correct and this unit must
be provably additive. The test asserts the **same units are kept and dropped** as before, with the
receipt as the only difference.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C1.U01b` | `genios_engine/reason/plan.py` | `uv run --no-sync pytest tests/reason/test_a_kept_unit_says_what_it_lost.py -q` |

### F2.3 · Carry it to the surface

**How:** `ExecutionPlan.degraded` → the reasoning bundle → the decision's `uncertainty`.

**⛔ Why this function is not optional:** this programme has found the `not_carried` shape **six
times** — a value computed correctly and dropped at a boundary. A receipt that stops at
`ExecutionPlan` is the seventh. **The unit is not done until the fact reaches something a human
reads.**

**Why `uncertainty` and not a new field:** `ReasoningDecision.uncertainty` already exists and already
means *"what we are not sure about, in words."* A missing source is exactly that, and a second field
would give the card two places to look.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C1.U01c` | `genios_engine/reason/orchestrator.py` | `uv run --no-sync pytest tests/reason/test_a_lost_source_reaches_the_decision.py -q` |

---
---

# S3 · The five output lanes, and the router

## What was expected

*"The five output lanes, and the router that chooses one deterministically."* Atlas v2:
**decision · investigation · conflict · monitor · suppress**.

## What is actually true

The vocabulary does not exist — `"investigation"` has **0 hits**, `OUTPUT_LANE` **0**, `LANES =` **0**.
So this is a genuine addition. But four of the five words are already taken:

| Word | Already means | Where |
|---|---|---|
| `suppress` | a delivery decision, and a feedback outcome | `contracts/delivery.py:87`, `contracts/outcomes.py:56` |
| `monitor` | an execution mode — *"observe and wait for a response"* | `contracts/execution.py:131` |
| `conflict` | two sources disagreeing — an L3 hold reason | `context/situation_publisher.py` |
| `lane` | ⛔ **a PACK lane** — about whether a card can cite an expert | `reason/uncited_lanes.py` |

### ⛔ Two hard constraints, both from measured collisions

**1 · The lanes are NOT `DecisionOutcome`.** `contracts/reasoning.py:301` has six members —
`decision · no_action · defer · insufficient_context · blocked · failed` — and the docstring defends
them: *"A projection that only carries `decision` loses five sixths of the vocabulary."*

| | Question it answers |
|---|---|
| `DecisionOutcome` | **did we reach a decision, and if not why** |
| output lane | **what kind of output should the human see** |

**Orthogonal, not rivals.** A `decision` outcome may belong in the `decision` lane or the `monitor`
lane. Anyone who "aligns" these destroys five sixths of a protected vocabulary.

**2 · It must not be called `lanes` near `uncited_lanes.py`.** That file's own docstring says what the
conflation already cost: *"Layer 2 lost five readings to exactly that ambiguity."* A `lanes.py` beside
it would be read as the same concept by the next person.

⛔ **Proposed name: `output_lane` / `OUTPUT_LANES`, in `contracts/reasoning.py`, never a bare `lane`.**
[open — worth one line of confirmation]

### F3.1 · The lane vocabulary

**How:** a closed enum in `contracts/reasoning.py`, with a docstring per member saying **what the
reader is expected to do** — because that is the only thing that distinguishes these five from the six
outcomes.

**Why closed:** an open vocabulary makes the router untestable — there is no "every lane is handled"
assertion to write.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C2.U01` | `genios_engine/contracts/reasoning.py` | `uv run --no-sync pytest tests/contracts/test_the_output_lanes_are_not_the_outcomes.py -q` |

### F3.2 · The router

**How:** a pure function from `(ReasoningDecision, ConfidenceVector, hold state)` → one lane, plus the
reason it chose that lane.

**Why deterministic and why no model:** `00-ARCHITECTURE.md §4` — *"If the output is a number, a route
or a permission, no model produces it."* A lane **is a route.**

**⛔ Why it returns a reason and not just a lane:** a card in the wrong lane with no recorded reason is
undiagnosable, and the router is the single most consequential new branch in this layer.

**⛔ Totality, both directions:** every `(outcome, confidence, hold)` combination maps to exactly one
lane, and every lane is reachable from at least one combination. A lane nothing can route to is dead
vocabulary that will be "fixed" later by someone widening a condition.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C2.U02` | `genios_engine/reason/output_lane.py` | `uv run --no-sync pytest tests/reason/test_every_decision_reaches_exactly_one_lane.py -q` |
| `M11.C2.U03` | same — the totality guard, both directions | same command |

### F3.3 · The lane on the decision

**How:** the chosen lane and its reason on `ReasoningDecision`, projected through the five documented
`DECISION_PROJECTIONS`.

**⛔ Why all five projections matter:** `DECISION_PROJECTIONS` documents each one and its single
writer. A lane added to the in-memory object and not to `signals` is invisible to the card — the
`not_carried` shape again, at the boundary the contract itself warns about.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C2.U04` | `genios_engine/reason/domain_shadow.py` | `uv run --no-sync pytest tests/reason/test_the_lane_reaches_every_projection.py -q` |

---
---

# S4 · The five pipeline counters

## What was expected

That the funnel `signals_detected → situations_formed → capability_resolved → decision_emitted →
card_delivered` existed somewhere.

## What is actually true

**Zero hits for all five**, across `genios_engine/` and `migrations/`.

## Why this is not cosmetic

Without a funnel, *"we produced 28 cards"* cannot be distinguished from *"we produced 28 cards out of
4,000 signals and lost 3,900 at a step nobody can name."*

⛔ **Every layer in this programme has found at least one defect a funnel count would have surfaced
years earlier:** `l4_bundle` at 0 successes from 600 calls; a five-day total model outage, twice; 467
holds that nobody asked about; three built-and-uncalled modules.

### F4.1 · The counter contract and its store

**How:** one row per (org, sweep, stage) with a count, written by the stage that owns it.

**⛔ Why per-stage rows and not one wide row:** a wide row needs every stage to have run before it can
be written, so a sweep that died at stage 3 writes nothing — losing exactly the measurement that would
explain the death. Per-stage rows mean a partial funnel is still a funnel.

**⛔ Why a count of ZERO must be written, not skipped:** a missing row and a real zero are different
facts. *"`situations_formed` = 0"* says the stage ran and formed nothing; a missing row says nobody
looked. This is the same distinction as coverage's `None` vs `0`, and this programme has now been
caught by it twice.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C3.U01` | `migrations/0188_pipeline_counters.sql` + `genios_engine/reason/telemetry.py` | `uv run --no-sync pytest tests/reason/test_a_zero_is_written_not_skipped.py -q` |

### F4.2 · The five writers

**How:** each stage writes its own count, in the pass that owns it — `capture/` for
`signals_detected`, `context/` for `situations_formed`, `reason/` for `capability_resolved` and
`decision_emitted`, `deliver/` for `card_delivered`.

**⛔ Why one writer per stage and never a central collector:** a collector must re-derive four numbers
it did not compute, and a re-derived count can disagree with the thing it counts. One writer per
number is the same rule `DECISION_PROJECTIONS` already applies to the decision.

**Why never fatal:** a lost measurement costs a cycle of visibility; a raise costs the tenant's mail.
Same trade `detect_residue` and the L3 needs wire already make.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C3.U02` | five call sites, one per layer | `uv run --no-sync pytest tests/test_the_funnel_has_five_numbers.py -q` |

---
---

# S5 · ⛔ Plane R — the unit contract

**Plane R is `reason/reasoners/` — 23 files, 7,820 lines. *How* a professional thinks, domain-free.**

## What was expected

That a unit which reads another unit's output declares that it does.

## What is actually true — measured

```
CORE_UNITS=17  SUPPLEMENTARY_UNITS=6  total registered=23
units with NO declared source_units: 23
units WITH declared source_units:     0
```

⛔ **Not one of the 23 units declares what it reads.** And `reason/registry.py:49` exists for exactly
this, in its own words:

> Optional class attribute a unit may declare: the units it reads metrics from when the manifest names
> none. **`AXIS_SOURCES`-style defaults are a hard dependency on the roster even though no capability
> ever spells them**, and this is where a unit states them so they can be checked.

So `validate_sources()` runs on every registry construction — and **validates an empty set.** The test
`test_the_shipped_registry_holds_no_ghost_sources` passes **trivially**: it asks a question about a
collection that is always empty.

> ⛔ **A guard that passes because it has nothing to check.** Third instance of that shape in this
> programme, and the first one where the mechanism was built, named after the exact pattern it was
> meant to catch, and then left unused.

### The two units the comment was written for

**`tradeoff_unit.py:59`** names six unit ids as runtime defaults:

```python
AXIS_SOURCES = (
    ("benefit_source",   "core.impact",      "impact_bp"),
    ("certainty_source", "core.confidence",  "confidence_bp"),
    ("cost_source",      "core.cost",        "effort_bp"),
    ("reward_source",    "core.opportunity", "opportunity_bp"),
    ("risk_source",      "core.risk",        "risk_bp"),
    ("speed_source",     "core.temporal",    "urgency_bp"),
)
```

`resource_unit.py` has the same pattern. **Neither declares `source_units`.**

⛔ **And `core.tradeoff` completed 1,165 of 1,165 runs** (STEP-01's measurement). It is reading six
sources by default, on every run, with none of them declared or checked. Rename or drop any one and
the default silently resolves to nothing — and tradeoff still emits a number.

**`legacy_gate.py:23`** is the blunt case:

```python
source = prior_results.get("legacy.rule")
```

A hardcoded read of another unit. Its spec is `ReasonerSpec(reasoner_id="legacy.score_gate",
version="1.0.0")` — **no `dependencies`, no `source_units`.** If `legacy.rule` is not scheduled, the
gate reads `None` and carries on.

### F5.1 · Declare what each unit reads

**How:** add `source_units` to every unit that reads a prior unit — the two `AXIS_SOURCES` units,
`legacy.score_gate`, and the four others that touch `prior_results` (`legacy_rule`, `planning`,
`relationship`, `signal_composition`, `temporal`).

**Why a class attribute and not a manifest edit:** the manifest is per-capability and these are
**defaults for when the manifest names none** — which is the case `registry.py:49` describes. A
manifest edit would fix one capability and leave the default unguarded.

**⛔ Why derive it from `AXIS_SOURCES` rather than retype it:** two lists that must agree forever will
eventually disagree. `source_units = tuple(u for _k, u, _m in AXIS_SOURCES)`.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C4.U01` | `reason/reasoners/tradeoff_unit.py`, `resource_unit.py` | `uv run --no-sync pytest tests/reason/test_a_unit_declares_what_it_reads.py -q` |
| `M11.C4.U02` | `reason/reasoners/legacy_gate.py` + the 5 dynamic readers | same command |

**Outcome:** `validate_sources()` starts checking something. A unit reading a ghost fails at registry
construction instead of at runtime.

### F5.2 · Make the guard impossible to pass trivially again

**How:** a test asserting that **every unit touching `prior_results` declares `source_units`** — derived
by reading the sources, not by a hand-maintained list.

**⛔ Why the test must be source-derived:** a list of "units that read priors" is a second thing to keep
in agreement. A new unit that reads a prior and declares nothing must fail **without anybody
remembering to add it.** That is the difference between this guard and the one it replaces.

**And one measured oddity to record, not fix:** `core.signal_composition` is registered and has **zero
production result rows** — 22 of the 23 units appear in `reasoning_reasoner_results`, and it is the one
that does not. ⛔ Recorded as an open question, not a unit: it may be correct (no capability schedules
it) and "fixing" it would be scheduling a unit nobody asked for.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C4.U03` | `tests/reason/test_a_unit_declares_what_it_reads.py` | same command |

---
---

# S6 · ⛔ Plane D — routing and the draft corpus

**Plane D is `packs/` (34 files, 7,957 lines) + `Domain Expertise/` (1,426 YAML files). *What* a
professional knows.**

## What is actually true — measured

```
$ .venv/bin/python "Domain Expertise/_tools/validate.py"
0 error(s), 290 warning(s) — OK
```

| Domain | Capabilities | Situations | Draft |
|---|---|---|---|
| **Admin** | 59 | 34 | **7** |
| Sales | 47 | 15 | 0 |
| Customer Support | 49 | 20 | **16** |
| **total** | **155** | **69** | **23** |

**All 155 capabilities are `stable`.** The corpus is not thin — it is large, validated, and clean of
errors.

### The 290 warnings, by kind

| n | Kind |
|---|---|
| 217 | *"planned but not authored yet"* — relationships, attributes, dependencies, required/optional refs |
| 22 | a core object on the roster, not authored yet |
| 10 | a relationship verb outside the recommended set |
| 7 | authored and routed by nothing, with no `deferrals.yaml` to say why |
| 5 | authored but **unreachable** — no capability's `knowledge.yaml` references it |
| **5** | ⛔ **Layer 2 emits a type and NO situation in ANY domain binds it** |
| 4 | scope/evidence-source advisories |

⛔ **The 217 are not a defect.** *"Planned but not authored yet"* is the corpus declaring its own
frontier — this codebase's declared-silence doctrine, working. Authoring them is content work, not
engineering, and **not M11's scope.**

### ⛔ The 5 that matter, and the corpus already says so

`Domain Expertise/Admin Expertise/registry/situation-capability-map.yaml:718`:

```yaml
# Layer 2 emits these and NO situation in ANY domain binds them. Each is a signal
# that compiles to nothing, silently. Global, not this domain's fault.
unrouted_l2_types:
  - commitment_unresolved
  - founder_bottleneck
  - meeting_preparation_gap
  - relationship_going_cold
  - vendor_renewal_decision
```

⛔ **I did not discover this. The corpus declares it, in a comment, with the consequence spelled out.**
Recording that distinction matters: a declared gap and an undiscovered one call for different work.
This one has been named and left, which under the declared-silence doctrine is legitimate — but the
signal still **compiles to nothing, silently**, and nothing in the engine reports it at runtime.

### F6.1 · The unrouted types become a runtime number, not a YAML comment

**How:** the engine counts, per sweep, how many situations it emitted whose type no capability binds.

**⛔ Why a runtime count and not a validator warning:** a validator warning is read when somebody runs
the validator. This is the one Plane D gap that costs a **live card**, and it belongs beside S4's
funnel counters — a situation formed that resolves to no capability is precisely a funnel loss between
`situations_formed` and `capability_resolved`.

**Why not bind the five now:** binding a situation type is **authoring**, and the memo on scope is
explicit that **only Admin is activated** — three of these five are not obviously Admin's. Making the
loss visible is engineering; deciding who owns each type is Rohit's.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C5.U01` | `reason/domain_shadow.py` + the S4 counter table | `uv run --no-sync pytest tests/reason/test_a_situation_that_binds_nothing_is_counted.py -q` |

### F6.2 · The map is generated, not maintained by hand

**How:** `situation-capability-map.yaml`'s `unrouted_l2_types` block is emitted by the validator rather
than typed.

**⛔ Why:** 219 entries maintained by hand, and the block is the single source everyone reads for
routing coverage. A hand-kept list of what is unrouted will eventually disagree with what is actually
unrouted, and it will disagree **silently and in the safe-looking direction** — the list will look
shorter than the truth.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C5.U02` | `Domain Expertise/_tools/validate.py` | `.venv/bin/python "Domain Expertise/_tools/validate.py" --check-generated` |

### F6.3 · A draft situation may not reach a card

**What is true:** 23 of 69 situations are `draft` — **7 in Admin**, 16 in Customer Support. Memory
records the standing constraint: *only Admin is in scope and gets activated; Sales and Support are on
hold.* So the 16 are out of scope and the 7 are the question.

The Admin seven:

| Capability | Situation |
|---|---|
| `inbox-and-correspondence` | `campaign-awaiting-reply` |
| `inbox-and-correspondence` | `organization-gone-quiet` |
| `opportunity-tracking` | `condition-awaiting-review` |
| `statutory-filing` | `obligation-falls-due` |
| `budget-tracking` | `spend-against-a-commitment` |
| `onboarding-administration` | `employee-lifecycle-event` |
| `asset-register` | `asset-in-custody` |

**How:** a guard that refuses to compile a **card** from a `draft` situation, and says which situation
and that it is draft.

**⛔ Why a refusal and not a warning:** a draft situation's card *"cannot instruct"* — it is authored to
the point of describing the situation but not to the point of telling the reader what to do. A card
that describes and does not instruct is worse than no card: the reader acts on it anyway.

**⛔ Why it must name the situation:** a refusal that says only *"draft"* sends somebody hunting through
1,426 files.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C5.U03` | `packs/compiler/expertise_builder.py` | `uv run --no-sync pytest tests/packs/compiler/test_a_draft_situation_cannot_instruct.py -q` |

### F6.4 · The 7 authored-and-routed-by-nothing get a `deferrals.yaml` line or a route

**What is true:** 7 capabilities are authored and nothing routes into them, and their domain has **no
`deferrals.yaml`** to say why. Admin **has** one; Customer Support does not.

**How:** a `deferrals.yaml` entry per capability, or a route. **Not code — one line of authored reason
each.**

**⛔ Why this is a unit at all:** the difference between *"deferred, and here is why"* and *"forgotten"*
is the entire declared-silence doctrine. Admin already does this correctly; the gap is that Support's
domain has nowhere to say it.

| Unit | Artifact | Verify |
|---|---|---|
| `M11.C5.U04` | `Domain Expertise/Customer Support Expertise/deferrals.yaml` | `.venv/bin/python "Domain Expertise/_tools/validate.py"` — the 7 warnings go |

⛔ **Scope note:** this is the one S6 unit that touches a non-Admin domain, and it is included **only**
because it is an authored explanation, not an activation. It does not put Support into scope.

---
---

# S7 · ⛔ Blocked on a decision that is not ours

## The ConfidenceVector axes

| | Axes |
|---|---|
| **Code** | `evidence` · `freshness` · `consistency` · `identity` · `coverage` · `analytic` |
| **Atlas v2** | `evidence` · `frame` · `temporal` · `causal` · `authority` · `coverage` |
| **Overlap** | **2 of 6** |

**The rename cost, measured** (§4 of the cross-check): construction sites **3**; migrations touching an
axis **0**; and the two overlapping axes are the load-bearing ones — `coverage_bp` in 27 code files,
`evidence_bp` in 4. **The four the Atlas would rename are in 2-6 files each.**

⛔ **So this is smaller than L3's cross-check assumed — and still not a rename.** `identity_bp` counts
open merge proposals; "authority" would mean whether a source is entitled to assert the claim.
**Different questions, different answers.**

| Option | Cost | Risk |
|---|---|---|
| **A · keep the code's six**, correct the Atlas | one Atlas edit | paper and product disagree until someone edits |
| **B · rename the wording-only axes** | ~11 files | half-aligned vocabulary — worst of both |
| **C · adopt all six Atlas axes** | 2-6 files each **plus inventing two measurements** | ⛔ the validator refuses an axis with no basis, so `causal` and `authority` stay `None` forever |

**Recommendation: A.** C's risk is decisive — the code refuses to compose an axis nobody measured, so
adopting two unmeasurable axes means composing from four while claiming six. That is what the code
already does today, with six honest names.

**⛔ This blocks NOTHING in S1-S6.** No unit above reads an axis name. It blocks M13 (L5 Delivery),
where the card shows the vector.

**Owner: Rohit.** One decision, three options, recommendation given.

---
---

## Unsound verifies, named before anyone trusts them

| # | Problem | Status |
|---|---|---|
| 1 | `tests/reason/test_a_plan_is_dependency_complete.py` and `tests/reason/adapters/test_a_skip_names_its_missing_input.py` are named by `tree.yaml` and **do not exist** | expected — the units create them. The first is being **renamed**, since the unit it verified is a regression |
| 2 | `tests/platform/test_migrations_apply.py` **does not exist** and is named by 3 units | ⛔ **[open]** — so `0188` will have no automated proof it applies, exactly as `0187` has none |
| 3 | `tree.yaml` has **two blocks with `id: M11`** — an older retired one and this | ⛔ fix the tree; an id is never reused |

---

## What we are deliberately NOT doing in L2

| Not doing | Why |
|---|---|
| ⛔ making plan compile fail on an unproduced source | reverts a measured decision and costs six units to one absent fact. **The single most important line in this plan** |
| aligning `DecisionOutcome` to the five lanes | loses five sixths of a vocabulary the contract explicitly defends |
| calling anything a bare `lane` | collides with `uncited_lanes.py`, which already cost five lost readings |
| refactoring the four registry validations | thorough and correct. Adjacent, not asked for |
| renaming any confidence axis | ⛔ Rohit's decision, and my recommendation is not to |
| ⛔ ~~touching `packs/` or `Domain Expertise/` YAML~~ | **THIS LINE WAS WRONG.** It said the cross-check found no defect there — it had not looked. See S5 and S6 |
| authoring the 217 *"planned but not authored yet"* refs | the corpus declaring its own frontier, which is the declared-silence doctrine working. Content work, not engineering |
| binding the 5 unrouted Layer 2 types | ⛔ authoring, and three of five are not obviously Admin's. **Making the loss visible is ours; deciding who owns each type is Rohit's** |
| activating Sales or Customer Support | standing constraint: **Admin only.** S6.F6.4 writes an authored explanation for Support, which is not an activation |
| the 16 Customer Support draft situations | out of scope while Support is on hold |
| scheduling `core.signal_composition` | registered, zero production rows. It may be correct that nothing schedules it, and "fixing" it would be scheduling a unit nobody asked for. **Open question, not a unit** |
| building anything on the `core.risk` claim | unverified, and unmeasurable while the API limit is on |

---

## ⛔ The one thing to carry out of this plan

**Two of four specified units were wrong and one rested on an unverified claim.** The cross-check cost
a few hours and saved building a regression into the layer that does the thinking.

> **This codebase's comments record decisions its planning documents do not. Read the comment before
> you "fix" the code.**

Third layer, third time. `no_model_wired` (L1) · the revision guard (L3) · the starvation rule (L2).


---

## ⛔ 2026-10-01 · *"No code written yet"* at the top of this file was true on the day it was written

**L2's spine has since been built: all five spine steps plus both planes; this plan was followed, not abandoned.**

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

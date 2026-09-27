# GeniOS — the architecture as it actually is

**Written 2026-09-27 against branch `speedrun008` · every claim measured, not remembered.**
`13,314 passed · 14 pre-existing failures · 0 regressions`

---

# PART 0 · ⛔ THE NUMBERING TRAP — read this before any other number

**There are FOUR vocabularies for the same layers, and they disagree.** `genios_engine/LAYERS.py`
carries the translation table because *"the numbers have already changed twice across specs while
the code did not"*.

| package | code # | name | **PRODUCT #** (what you say to a founder) |
|---|---|---|---|
| `capture` | 1 | Enterprise Signals | **L1** |
| `context` | 2 | Situation Intelligence | **L2 + L3** |
| `packs` | — | **Plane D · Domain Expertise** | into L2 |
| `reason` | — | **Plane R · Reasoning** | L2 + L4 |
| `executive` | 5 | Executive Intelligence | **L4** |
| `deliver` | 6 | Intelligence Distribution | **L5** |
| `feedback` | 7 | Learning Engine | **L6** |

⛔ **The tail is off by one throughout.** `executive`/`deliver`/`feedback` are 5/6/7 in code and
4/5/6 in product. **Always name the package, never the digit alone.**

⛔ **And "Layer 3" is the worst of them:** in the product vocabulary it means the **Context Graph**,
while **115 files in this repo** say "Layer 3" meaning **Domain Expertise**.

## Two of them are PLANES, not stages

> *"`packs` AND `reason` ARE PLANES, NOT STAGES… A digit implies a position in a pipeline; these two
> are what `context` reasons **WITH**, consulted rather than passed through. The number is an
> **import rule**, not a claim about sequence."*

---

# PART 1 · THE SIZE OF EACH PIECE

| package | files | lines |
|---|---|---|
| `capture` | 154 | **46,377** |
| `context` | 118 | **49,713** |
| `reason` | 118 | **40,036** |
| `deliver` | 36 | 8,674 |
| `packs` | 34 | 7,957 |
| `executive` | 26 | 5,990 |
| `feedback` | 12 | 2,737 |
| | **498** | **~161,000** |

---

# PART 2 · L1 → L2 · from a message to a qualified signal

## What L1 is

`genios_engine/capture/` — **154 files**, nineteen subsystems:

```
acquire/ connections/ connectors/ coverage/ documents/ domain/ esqe/ gate/
landing/ parked/ preprocess/ screen/ semantic/ structural/ structured/
transcripts/ triage/ validate/
```

`connectors/` (18 files) pulls from the world. `esqe/` (17 files) is the **Enterprise Signal
Qualification Engine** — the part that decides what a message MEANS.

## ⛔ The one crossing

`capture/esqe/publisher.py` states it in its own first line:

> *"L1.6.10 · the SIGNAL PUBLISHER — **the L1 → L2 boundary, and the last thing Layer 1 does.**
> Everything before this file decided what a message MEANT. This file decides whether that meaning
> is **allowed to leave Layer 1**, and writes the row that says it did. **There is exactly one
> crossing and this is it.**"*

It does not re-implement the rules — it **wires** `contracts/publication.py::validate_publication`,
which enforces **V-1..V-7**. The docstring says why:

> *"A second implementation of the seven rules would fork from the first the day either was edited,
> and both halves would still typecheck — which is how a gate becomes two gates."*

## The output: `qualified_signals`

`capture/esqe/signal_store.py` — *"the durable set L2 never had"*.

L2 reads it at `context/situation_bso.py:543`, joined to `context_correlation_members`, and the
projection carries:

```sql
qs.subject_key, qs.domain_hints, qs.confidence_bp, qs.occurred_at,
qs.expires_at, qs.secondary_types, qs.extraction_ref, qs.internal_kind
```

⛔ **Each of those was a loss before it was widened**, and the code records why beside each:
`occurred_at` — *"the SIGNAL's world time; L2 had only the event's"* · `expires_at` — *"ALG-19
already decided it; L2 was re-guessing"* · `secondary_types` — *"a signal is often several kinds;
only the primary crossed"* · `internal_kind` — *"company canon, which outranks observed traffic and
was invisible"*.

**That is the shape of nearly every defect in this system: a value computed correctly and then not
carried.** The codebase calls it `not_carried`.

---

# PART 3 · L2 · `context/` — the Context Graph and the Situation

`genios_engine/context/` — **118 files, 49,713 lines.** The largest single package.

## It is called Situation Intelligence, not Context Intelligence — deliberately

> *"the old name says **where** the layer sits, and this layer's output is a **SITUATION** —
> assembled, judged by eight admission laws, and exposed only if admitted. Describing it as a graph
> builder is how a card came to be wired to a signal while the situation layer was bypassed."*

## The two graphs — the thing most people get wrong

| | **Evidence Graph** | **Intelligence Graph** |
|---|---|---|
| holds | what **SOURCES** said | what **WE** concluded |
| tables | `graph_nodes` · `graph_facts` · `graph_edges` + 7 more | **no tables of its own** |
| visible to a founder | ✅ the graph canvas | ⛔ **no, deliberately** |
| ranks its claims | ✅ `authority_rank` | ⛔ **no — we have no rank over ourselves** |

⛔ **The Intelligence Graph is already foreign keys, and must not get tables:**

```
context_situations.situation_id
  ├→ situation_interpretations.situation_id      (0183)  ← interpretation
  └→ signals.situation_id                        (0182)
        └→ signals.reasoning_decision_hash       (0031, FK) ← decision
              └→ executions.decision_hash        (0041)  ← delivery
                    └→ execution_outcomes.decision_hash    ← outcome
```

**All five node kinds, joined.** And **nothing deletes a signal** — 0 hard deletes, 12 status
updates — so the chain cannot die.

## What L2 produces every sweep

`context/runner.py` is the sweep. In one pass it:

1. drains events into the graph
2. correlates them into **situations** (`context_situations`)
3. scores each on **five confidence dimensions**
4. publishes `derived.*` facts — `momentum`, `engagement`, `sentiment`, `contact_frequency`,
   **and `derived.history.*`** at `runner.py:752`
5. runs the desk readings (`support_situations.py`) and the period pass

⛔ **The seven "desk" anchors — `thread · backlog_item · escalation · contact_intent · topic ·
mailbox · workaround` — are declared by `support` ONLY.** The facts are written for every tenant;
the **situations** only form for the domain that declares the anchor. That one fact explains ~40 of
the 61 substrate fields nothing consumes.

---

# PART 4 · ⛔ THE TWO PLANES — how expertise and reasoning actually meet

This is the part that is hardest to see from the file tree.

```
                        ┌──────────────────────────────┐
                        │  Plane D · packs/            │
   ┌────────────┐       │  Domain Expertise            │
   │ context/   │       │  34 files · 7,957 lines      │
   │ L2         │       └──────────────┬───────────────┘
   │ situations │                      │ consulted
   └─────┬──────┘                      │
         │  reads                      ▼
         │              ┌──────────────────────────────┐
         └─────────────►│  Plane R · reason/           │
                        │  Reasoning                   │
                        │  118 files · 40,036 lines    │
                        └──────────────┬───────────────┘
                                       │ decision
                                       ▼
                              executive/ → deliver/
```

## The dependency direction, measured

```
reason  → packs :  7 files
packs   → reason:  0 files          ⛔ never
context → packs :  0 files          ⛔ cannot — import rule is same-or-lower
context → reason:  0 files          ⛔ cannot
```

⛔ **So `context` does NOT call the planes. `reason` calls INTO `context`'s situations and consults
`packs`.** The LAYERS docstring's phrase *"what context reasons with"* is a conceptual statement
about the architecture, not an import direction — and the import rule enforces the reverse for a
reason: it is what *"keeps domain knowledge out of the engine and context out of expertise — a
build failure, not a review nit."* (`tests/test_layer_topology.py`)

## Plane D · `packs/` — Domain Expertise

| piece | files | what |
|---|---|---|
| `compiler/` | 14 | `capability_resolver` → `object_resolver` → `knowledge_retriever`, **in that order** |
| `brains/` | 5 | the supply side of three runtime brains |
| `capabilities/` | 3 | native manifests for shadow/canary — all Sales-shaped |
| pack defs | 4 | `admin_v1` · `sales_v1` · `support_v1` · `general_v1` |

### ⛔ There are FOUR brains and only one is full

> *"The **Expert Brain is Git** (`Domain Expertise/`) and is **full**. Organization, Behavior and
> Adaptive live in `learned_brain_entries` / `temporary_memories`, their machinery has existed since
> migration 0045, and **both tables are empty — because nothing produces proposals.** This package
> is the supply side."*

| brain | where it lives | state |
|---|---|---|
| **Expert** | `Domain Expertise/` — **Git, not a database** | ✅ **full** |
| Organization | `learned_brain_entries` | supply wired (`org_discovery`, `org_rule_extract`) |
| Behavior | `learned_brain_entries` | supply wired (`behavior_distill`) |
| Adaptive | `temporary_memories` | supply wired (`adaptive_lease`) |

All four supply modules run from `feedback/orchestrator.py:134`.

### The corpus itself — what a "capability" IS

`Domain Expertise/` is **not code**. It is authored YAML — human expertise as data.

```
Domain Expertise/<Domain> Expertise/
    domain.yaml          the domain's identity
    capabilities/<group>/<capability>/
        capability.yaml      identity · description · question · outcomes ·
                             failure_modes · kpis · handoffs · ⛔ admission
        knowledge.yaml       the knowledge block
        objects.yaml         the LOAD-SET: core/scoped × required/optional
        situations/*.yaml    the situations this capability owns
    heuristics/          the executable doctrine — ⛔ this is where `reads:` lives
    playbooks/ models/ objects/ offerings/ rules/ verticals/
    deferrals.yaml       ⛔ the named reason a capability has no door
    registry/            the generated situation↔capability map
    _schema/vocabulary.yaml   ⛔ the 141 substrate fact paths offered to authors
    _tools/              admit.py · validate.py · index.py · plan.py · render.py
```

**Admin today: 59 capabilities, 59 admitted, 0 hollow, 34 situations (27 stable).**

### ⛔ THREE FILE TYPES, THREE DIFFERENT EDIT RULES — the most practical thing in this document

| file | has `admission` hash? | compiler checks it? | safe to edit? |
|---|---|---|---|
| `capability.yaml` | ✅ yes | ✅ **yes** | ❌ **NO — it un-accepts itself** |
| `situations/*.yaml` | ✅ recorded | ❌ **no** (admit.py says so) | ✅ yes |
| `heuristics/*.yaml` | ⛔ **60 of 60 have none** | — | ✅ **yes, freely** |

`capability_resolver._admission_reason` hashes the document **minus** the admission block and
compares. The comment is blunt:

> *"The hash pin is the difference between accepting a FILE and accepting its CONTENT — **an edit
> after review silently un-accepts, which is the point.**"*

And `_tools/admit.py` re-stamps, but refuses to grant review:

> *"It deliberately does **NOT** grant review. `--accept` refuses anything the reviewer has not
> already marked approved with their name on it; it only records what was accepted, using the
> **SAME hash function** the compiler will check it with."*

### The admission ceremony — two rules, and mixing them caused two wrong headlines

| | a CAPABILITY needs | a SITUATION needs |
|---|---|---|
| | `identity.status == stable` | same |
| | `metadata.review_status == approved` | same |
| | `metadata.reviewed_by` non-empty | same |
| | ⛔ `admission.accepted_content_hash` matching | — |
| on failure | **dropped in live mode** | ⛔ **flagged, not removed** |

**Why the asymmetry:** a situation's DETECTION belongs to L2 and is evidence-backed whatever a
reviewer thinks of the copy; only its **prescriptive words** are unreviewed. So it lands in
`admission_gaps` → `plan.admitted=False` → `review_state='draft'` →
`deliver/pipeline._apply_abstention` **downgrades the card to an OBSERVATION.**

> **The intelligence still ships; it stops instructing.**

## Plane R · `reason/` — Reasoning

| piece | files | what |
|---|---|---|
| `reasoners/` | **25** | the unit implementations |
| `moments/` | 16 | recall and slice — *"when did we last relate to this"* |
| `bundle/` | 12 | the `ReasoningBundle` narrative (wave Z4) |
| `adapters/` | 10 | ⛔ **`expertise.py` — where the two planes MEET** |
| `team/` `verify/` `meetings/` | 14 | the team lane, verification, meeting reasoning |

### The unit framework — `reason/unit.py`

> *"Every unit in GeniOS has the same anatomy. That is the whole point: **you do not build seventeen
> systems, you build one framework and seventeen implementations of it.** A unit that looks like
> every other unit can be reviewed, tested, timed, and replaced by someone who has never seen it
> before."*

```
Input → Validator → Retriever → Analyzer(plugins) → Calculator → Evaluator → Builder → Metrics
                                        ▲
                                 the IP lives here
```

**Two deliberate departures from the diagram, both forced by laws that outrank it:**

1. ⛔ **The Retriever does not fetch.** *"Units are forbidden to touch a database, network, or clock
   — that is what makes a decision replayable months later. Retrieval already happened when Layer 2
   froze the ContextSnapshot."*
2. **The stages are methods, not files.** `evaluate()` is a template method that **cannot be
   overridden**, so no unit can skip validation or invent its own result shape.

**23 units are registered** (17 `CORE_UNITS` + 6 `SUPPLEMENTARY_UNITS`).

### ⛔ Six run by default, twenty in the roster

```python
_default_dag(...)   → (context, risk, constraint, priority, confidence, planning)   # SIX
_roster_specs(...)  → the full family, gated per unit by what the corpus reads      # roster_v2
```

**On the six-unit path they also run half-blind:**

> *"the six that DO run, run half-blind: `core.risk` reads `drop_bp` from `core.temporal` and
> `coverage_bp` from `core.relationship`, and neither was scheduled, so **two of its three plugins
> have been correctly silent since the day it shipped**."*

### ⛔ HOW THE TWO PLANES ACTUALLY BIND — this is the seam

`reason/adapters/expertise.py` holds `_ROSTER`: twenty `_RosterUnit` records. Each declares:

- `roles` — a config key → the **fact paths** that can fill it, in preference order
- `gates_on` — the roles whose bound field gates the unit through the selector
- `essential` — the roles **without which the unit is not declared at all**
- `always` — the opposite claim, which **must be stated in words**: *"a unit that can never be
  dropped for want of a fact must say why, or 'it never drops' is indistinguishable from 'nobody
  declared its inputs'."*

**Two different questions, and the module says conflating them is how a roster becomes noise:**

```
does this EXPERTISE read anything this unit can use?  → the manifest declares it, or does not
does this SITUATION carry that input?                 → the selector schedules it, or drops it
                                                        with a SkippedStep receipt
```

⛔ **The first question is answered against the corpus's own fact paths**, *"so nothing here invents
a vocabulary. A unit whose roles bind nothing is **left out with a receipt naming its candidates**,
rather than declared with fields no authored pattern ever asked for."*

**Measured for Admin with `roster_v2` on: 15 of 20 units BIND. 5 drop — and 4 of the 5 correctly,
because they are DEAL-shaped units and Admin has no deals.**

### The compile order, and why it is fixed

```
capability_resolver  →  object_resolver  →  knowledge_retriever
```

⛔ Variants used to resolve in the **last** of the three, *"so a branch could be selected, loaded,
carried into the package and hashed into its address — and could not affect the PLAN, which had
already decided which"*. That is why `resolve_declared_variants` moved earlier.

## The whole L2→L4 call chain, with line numbers

```
context/runner.py                          the L2 sweep
      │  writes context_situations + derived.* facts
      ▼
reason/domain_shadow.shadow_compile(..., live_domains=…)        :554
      │  reads every ACTIVE situation
      ▼
packs/compiler/  →  capability_resolver → object_resolver → knowledge_retriever
      ▼
        ExpertisePackage                   ← Plane D's output
      ▼
reason/adapters/expertise.py               builds the CapabilityManifest
      │  roster_v2=False → _default_dag()  → 6 units
      │  roster_v2=True  → _roster_specs() → full family, bound to the corpus's fields
      ▼
reason/orchestrator + the 23 units         → ReasoningDecision
      ▼
reason/audit.persist_execution()           → reasoning_runs / reasoning_run_outputs
      ▼
reason/domain_shadow._emit_capability_signal()  :327  → a `signals` row
      ▼
deliver/pipeline.py                        → a card
```

## ⛔ The switch that makes "Admin on, Sales off" expressible

`shadow_compile` takes **`live_domains`**:

* **`live=True`** is the GLOBAL flag (`platform/config.use_domain_compiler`) — **every tenant at
  once or nobody.** Set in no environment. Do not use it.
* **`live_domains`** is `platform/l3_activation.activated_domains(engine, org)` — **per tenant, per
  corpus.**
* They are **OR-ed PER SITUATION**: *"a tenant with `admin` activated runs its Admin situations live
  and its Sales situations in shadow, **in the same sweep, from the same read**."*

⛔ **And this shipped broken once**, which is worth knowing because it is the failure mode to watch
for everywhere in this system:

> *"`l3_activation` landed with a reader, a fail-closed gate, an erasure row, an admin API and a J5
> report — **and no caller**… so an operator could POST an activation, see it in the console, read
> `EFFECTS` telling them the compiler's live pass now compiles that corpus, and **get a shadow
> pass**. **A switch that reports itself as on and changes nothing is worse than no switch**, because
> the next person debugging it starts from the belief that Layer 3 was tried."*

---

# PART 5 · L4 · `executive/` — from a conclusion to a commitment

**26 files, 5,990 lines.** Its own statement:

> *"Layer 4 answers **what should happen**. This layer answers **how we make it happen** — and those
> are different jobs. **A conclusion is an opinion; a commitment is an opinion with an owner, a
> deadline, a channel, a ladder and a clock attached.** Until this layer existed, GeniOS produced
> excellent recommendations and then stopped: it had no idea whether anything was ever done."*

## ⛔ It is already running — every heartbeat tick

```
api/routes.py:1150   run_executive(engine, org, eval_time=now)      every org, every tick
                     ├─ plan_commitments()   authoritative decisions → executions
                     └─ run_lifecycle()      validate → transition → remind → escalate → close
                                             → record_outcome()  →  Layer 6
```

*"Runs **BEFORE distribution** on purpose: a reminder decided in this tick should leave in the same
tick rather than waiting a whole interval."*

## The unit anatomy

Unit 1 `interpret` · Unit 2 `planning` · Unit 2.5 `coordination` · Unit 3 `communication` ·
Unit 4 `execution` · Unit 5 `reminder` · Unit 7 `monitor` · Unit 9 `lifecycle` · Unit 10 `collect`
· plus `assignment`, `escalation`, `execution_guard` (unnumbered).

⛔ **Units 6 and 8 have no file, and three files carry no number — which does not divide.** The L5
spec that assigned them is not in this repo. **Recorded as an open question, not a gap.**

## Three laws that hold across every module here

1. ⛔ **No model decides anything.** *"An LLM may improve the wording of a reminder. It may never
   decide whether to remind, who to escalate to, what the steps are, or how urgent something is.
   Approval boundaries and escalation ladders **cannot be probabilistic**."*
2. ⛔ **Nothing fires without re-validation.** *"A nudge about something that already happened costs
   more trust than ten missed ones ever could."*
3. ⛔ **The plan is immutable; only the row moves.** Execution objects are frozen and
   content-addressed over `(org, decision, plan)` — *"that separation is what makes 'why did this
   escalate on day 7?' answerable months later, after the pack has been retuned twice."*

## The input gate — seven conditions

`plan_commitments` reads `AUTHORITATIVE_SIGNAL_PREDICATE`:

```
audited reasoning run · active pack authority · matching authority revision
matching config version · run completed after the pack's last update
signal still open · authority not expired
```

⛔ **Until a domain is activated there are no authoritative decisions, so Layer 4 examines nothing.**
It runs correctly and finds an empty queue.

`SweepReport.reasons` counts refusals **by reason**: *"A sweep that plans nothing because every
decision was `no_action` is healthy; one that plans nothing because every build hit `window_closed`
is a misconfigured pack, and a single 'skipped' counter cannot tell those apart."*

## The escalation ladder as shipped

| day | action | audience | interrupt |
|---|---|---|---|
| 1 | notify | owner | no |
| 3 | remind | owner | ⛔ yes |
| 7 | escalate | manager | no |
| 14 | critical | executive | ⛔ yes |

Days are **offsets from creation**, not from the deadline — *"an escalation that starts when the
window is already gone is a post-mortem."* `max_rungs: 6` — *"a ladder longer than this is somebody
automating harassment rather than escalation."*

## Five tables

`executions` · `execution_actions` · `execution_escalations` · `execution_events` ·
`execution_outcomes` (all migration **0041**) + delegation wiring (**0157**).

---

# PART 6 · L5 · `deliver/` — from a commitment to a card a human sees

**36 files, 8,674 lines.**

| piece | what |
|---|---|
| `pipeline.py` | ⛔ the card-building pass, and the **collapse measurement** |
| `card_builder.py` `render.py` | the card itself |
| `card_source.py` | ⛔ `classify` — SITUATION vs UNINTERPRETED |
| `outbox.py` | *"every outbound human notification is a ROW, never a blocking call"* |
| `executive_bridge.py` | ⛔ **the wire from L4 to a human** |
| `router.py` `audience.py` `routing.py` | who sees it |
| `gate.py` `policy.py` `bands.py` `rate_limiter.py` | whether it may go |
| `channels/` | Slack and the rest |
| `digest.py` `scheduler.py` `timing.py` `timezone_infer.py` | when it goes |

## ⛔ The bridge, and why it runs this way round

> *"Until this module existed, Layer 5 could decide that somebody needed nudging, record the
> decision, fire the escalation rung — **and then nothing left the building. The reminder was a row.
> This is the wire.**"*
>
> *"**Layer 5 may never import Layer 6**, so it cannot enqueue anything itself. What it CAN do is
> write down its decision, and it does: an `execution_events` row of kind `execution.reminded`
> carries the routing plan… Layer 6 reads that and turns it into a message. **The dependency points
> downward, which is the rule.**"*

**Division of labour:** L4 decides *whether to speak, to whom, through which channel, and what may
be said.* L5 *executes the communication plan; it does not author it.*

## ⛔ The invention validator — the hallucination guard

`executive/reminder.reminder_facts` returns *"the grounded fact corpus a reminder may be worded
from"*, and:

> *"**Layer 6's invention validator will refuse any rendered sentence containing a number, name or
> date that is not in this dict**, so this function is quite literally **the vocabulary of what a
> reminder is allowed to say**."*

⛔ **That is the mechanism that makes "no model invents a fact" enforceable rather than aspirational.**

## The cutover that is measured before it is taken

`card_source.COMPARISON_KEYS` counts `cards_from_situation` / `cards_uninterpreted` /
`cards_from_signal` on **every** sweep. `deliver/pipeline`'s own rule:

> *"**BUILT BESIDE THE OLD ONE, NOT OVER IT.** `_open_signals_without_cards` is untouched and stays
> runnable for one release, because the two paths are **compared on one sweep before either is
> retired**."*

And the recall guard: *"**fewer cards must come from MERGING, never from dropping.** If every signal
must belong to a situation to be seen, a correlator gap becomes a silent disappearance."*

---

# PART 7 · L6 · `feedback/` — the loop closing

**12 files, 2,737 lines.** Reads `execution_outcomes` (seven terminal labels), calibrates rule
precision, auto-mutes rules whose precision falls below a floor, and runs the brain pipeline that
supplies Organization / Behavior / Adaptive proposals.

⛔ **`explain.why_not`** answers *"Why did GeniOS not tell me about X?"* from
`signal_suppression_log` — six reason codes: `below_gate · budget · cooldown · muted · shadow ·
situation`. *"Silence without receipts is indistinguishable from a bug."*

---

# PART 8 · THE DOCTRINES — the rules that shaped every decision above

These recur across all seven packages. They are the most transferable part of this system.

| doctrine | what it means |
|---|---|
| **`Observation ≠ Inference ≠ Hypothesis`** | three different epistemic statuses, never merged |
| **The model may DESCRIBE, never SCORE** | an LLM writes words; arithmetic decides |
| **Integer basis points, no floats** | 7,500 bp not 0.75 — replayable arithmetic |
| **No clocks inside logic** | `eval_time` is a parameter, never `now()` — this is what makes a decision replayable months later |
| ⛔ **A column no writer names is null forever** | the defect class that hits hardest |
| ⛔ **`not_carried`** | *"every measured loss is a value that is computed correctly and then not carried"* |
| **Soft delete only** | `status` moves; rows never vanish |
| ⛔ **Declared silence** | `DARK_DOMAINS` · `UNCITED_LANES` · `SILENT_LANES` · `LINEAGE_UNPROTECTED` · `UNREACHED` — every one carries **a reason AND a mover** |
| ⛔ **Totality guards** | a closed constant checked in **both** directions (declared ⟷ written). One direction alone is half a guard |
| ⛔ **A receipt may never abort the thing it is a receipt for** | *"turns an accounting failure into a product failure"* |
| ⛔ **NULL is an answer** | `completeness_bp` is `None`, not `10000`. `claimed_total` is null, not zero. A value that cannot be reconstructed is **never fabricated** |
| ⛔ **The "six times" defect** | a unit built, tested, green, and **called by nothing on a real path** |
| ⛔ **The blunt-grep family** | an assertion about *text near a thing* rather than the thing's *structure*. **Eleven occurrences on this branch.** Parse the AST, the column list, the position — never `"word" in source` |

---

# PART 9 · WHERE TO DIG — the files that explain the most per line

| to understand | read |
|---|---|
| the numbering, and every translation | `genios_engine/LAYERS.py` |
| the L1→L2 crossing | `capture/esqe/publisher.py` |
| what L2 hands over | `context/situation_bso.py` around line 536 |
| ⛔ **how the two planes bind** | `reason/adapters/expertise.py` — the `_ROSTER` block |
| the unit framework | `reason/unit.py` |
| the admission ceremony | `packs/compiler/capability_resolver.py` — `_admission_reason` |
| the activation switch, and how it shipped broken | `reason/domain_shadow.py:554` |
| what a commitment is | `executive/__init__.py` then `executive/sweep.py` |
| the L4→human wire | `deliver/executive_bridge.py` |
| what a card may say | `executive/reminder.py` — `reminder_facts` |
| what this layer does NOT call | `executive/unreached.py` · `reason/uncited_lanes.py` · `reason/situation_binding.py` |
| what the corpus offers authors | `Domain Expertise/_schema/vocabulary.yaml` |
| why a capability has no door | `Domain Expertise/Admin Expertise/deferrals.yaml` |

## The plan folder

```
speedrun008/
    DO-THIS-NOW.md              everything blocked on Harsh, in execution order
    HARSH-ORDER.md              the same, with full reasoning
    ARCHITECTURE.md             ← this file
    handoff/                    short form, by kind of thing
    plan/STATUS.md              every step in every layer with its outcome
    plan/layer-3/               26 steps + 21 findings files
    plan/layer-4/               status · Harsh's list · remaining steps · production readiness
    plan/admin/00-CROSSCHECK.md Admin-only corpus and roster cross-check
```

---

# PART 10 · ⛔ THE HONEST STATE, 2026-09-27

| layer | code | data / corpus | running? |
|---|---|---|---|
| **L1** `capture` | ✅ | — | ✅ |
| **L2** `context` | ✅ | — | ✅ every sweep |
| **Plane D** `packs` | ✅ | ✅ Expert brain full (Admin 59/59 admitted) · 3 brains empty | ✅ |
| **Plane R** `reason` | ✅ | — | ⚠️ 6 of 23 units on the default path |
| **L4** `executive` | ✅ | ⛔ org data missing (seats, reporting line, channels) | ✅ every tick, **empty queue** |
| **L5** `deliver` | ✅ | — | ✅ |
| **L6** `feedback` | ✅ | 3 brain tables empty | ✅ |

## The one thing that gates everything

⛔ **No domain is activated.** So L3 compiles in shadow, no authoritative decisions are produced, L4
examines nothing, and the whole lower half of the stack runs correctly over an empty queue.

**One activation row for `admin` starts the chain.**

## What is NOT a code problem

* **7 Admin draft situations** — 4 declared `pending_l2_types` (must stay draft), 3 awaiting a named
  human reviewer
* **61 of 141 substrate fields consumed by no capability** — but ⛔ **~40 belong to Support's desk
  anchors**, and Support is on hold. Admin's real gap is `document.*` (8) and `derived.history.*` (4)
* **Org data for L4** — seats, the reporting line (⛔ in `seat_responsibilities.reports_to`, **never**
  `org_seats.manager_seat_id`), channels
* **Two product decisions** — does a preventive warning become a card, and is a brief pushed?

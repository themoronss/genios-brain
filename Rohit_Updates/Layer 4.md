# Layer 4 — The Reasoning Engine

Status: **built, adversarially verified, and mostly locked in shadow.**

Last updated: 2026-08-07 (corrected — see the note below)

> **Correction, 2026-08-07.** An earlier version of this document said Layer 4 "has never made a
> decision that reached a human". **That was wrong.** The native kernel already reaches production
> through a second path: `reason/composer.py:compose_deal_health` reasons the
> `sales.deal_health` capability with `execution_mode` — `LIVE` whenever the tenant's pack state is
> `active` (`runner.py:run`) — and that manifest sets `live_delivery_enabled=True`
> (`packs/capabilities/deal_health.py`). It writes real `signals` rows.
>
> The accurate statement is narrower: **the capability *sweep* path is shadow-locked; the
> *composite* path is live.** This matters because the composite path is a working example of the
> "missing" delivery adapter described in Step 5 — the pattern already exists and can be copied
> rather than invented.

This document is written for whoever takes Layer 4 to production. It says what was there, what was
missing, what changed, what is deliberately still switched off, and the exact sequence to switch it
on. Read Part 5 before touching anything.

---

## Part 0 — The one-line summary

Layer 4 is three parts, and their separation is the whole design:

```text
Part 1  Reasoning Orchestrator   schedules  — never analyses, never decides
Part 2  Reasoning Units (17)     analyse    — never decide, never rank
Part 3  Decision Maker           decides    — the only synthesis authority
```

If any one of those three starts doing another's job, the layer has failed, regardless of what the
tests say. Most of the work below is about making that boundary physical rather than a convention.

---

## Part 1 — What already existed

The kernel that was here before this pass was genuinely good, and none of it was thrown away:

- A deterministic orchestrator executing a capability-declared DAG in lexical topological order.
- Immutable, content-addressed contracts: `ContextSnapshot`, `CapabilityManifest`,
  `ReasonerResult`, `DecisionCandidate`, `ReasoningDecision`, `ReasoningTrace`.
- Integer-basis-point arithmetic throughout, with floats rejected at the canonicalisation layer.
- Full audit persistence with independent re-derivation in `reason/store.py`, replay, and
  shadow/simulation modes.
- Seven reasoning units and a legacy strangler pair that runs existing pack rules unchanged.
- A SQL authority predicate (`reason/authority.py`) that re-proves every decision on every
  downstream read.

### What was missing

Measured against the frozen architecture, seven gaps:

| Gap | State before |
|---|---|
| Decision-making lived **inside** the orchestrator | `_build_candidates` ranked and selected in `orchestrator.py` — Part 1 and Part 3 were one module |
| Unit roster | 7 of 17 units existed; 12 missing entirely |
| Unit framework | **Zero** units implemented the 8-stage anatomy; each was one `evaluate()` of 37–142 lines |
| Analyzer plugins | Did not exist anywhere in the layer |
| Confidence floor | Not built — no path from "low confidence" to "ask a human" |
| Unit selection | Static per capability; the orchestrator could not see the situation |
| Fallback | Only `required`/`optional`; no substitution |

Two contract fields were also declared and never used: `ReasonerSpec.latency_budget_ms` was
validated but never read at runtime, and `DecisionOutcome.DEFER` existed in the enum and the DB
constraint with no code path producing it.

---

## Part 2 — The three forks we had to settle

These were real architectural decisions, not implementation details. Each is a place where the
blueprint and the codebase disagreed and someone had to choose.

### Fork 1 — Timeouts

The blueprint asks the orchestrator to enforce per-unit timeouts. **We did not build that, on
purpose.** A wall-clock timeout that kills a running unit makes the decision depend on machine
speed: the same situation resolves differently on a loaded box than on an idle laptop, which
destroys replay, and replay is what makes a decision auditable rather than merely asserted.

Instead the budget is enforced **statically** — the planner refuses a capability whose declared
budgets exceed its declared ceiling, before any unit observes anything — and **observably**, via
telemetry that makes an overrun loud and attributable. Proven: a unit running 2,900× slower
produces a byte-identical decision.

### Fork 2 — The LLM consultant

The blueprint says the Decision Maker may consult an LLM below the confidence floor. The repo
constitution forbids any LLM inside `reason/`, and that ban is test-enforced.

**The ban wins.** Below the floor the decision becomes `DEFER`: the ranked candidate field is kept
so a human sees what was considered, but nothing is selected, so no adapter can read it as an
instruction. This is Law 03 in code — *do not hallucinate; increase uncertainty and recommend
asking* — and it matches Theory II's own 0.45–0.65 confidence band. The blueprint and the
constitution reconcile; they only appeared to conflict.

### Fork 3 — Unit anatomy

The blueprint shows eight files per unit (`input.ts`, `validator.ts`, `retriever.ts`, …). We built
**a base class enforcing the same eight stages**, one file per unit, plus a real plugin registry
inside the Analyzer.

Two reasons. The `Retriever` stage cannot exist as specified — units are forbidden database and
network access, and retrieval already happened when L2 froze the snapshot; so "Retriever" here means
*select and shape* from that frozen input. And eight files around a forty-line calculation is
ceremony that buys nothing the base class does not already give: uniformity, isolated testability,
and the plugin seam.

---

## Part 3 — What we built

### Part 1 · Orchestrator — all seven duties now real

| Duty | How |
|---|---|
| Which units execute | `ReasoningPlanner.plan(capability, request)` — declared roster, plus opt-in context-aware pruning of optional units this situation cannot feed |
| In what order | Kahn topological sort, lexical tie-break — unchanged |
| Which can run in parallel | `ExecutionPlan.stages` — dependency-free waves, **described not performed** |
| Which are skipped | Terminal outcomes, gating, and recorded `SkippedStep` rows with reasons |
| Fallback | Reserve units: a unit declaring `fallback_for` runs only when its primary failed |
| Should an LLM be called | Never. Below the floor → `DEFER` |
| Should the confidence threshold change | `confidence_floor_bp` in capability metadata |

New files: `reason/plan.py` (schedule as a first-class, hashable artifact), `reason/telemetry.py`
(per-unit timing, excluded from every semantic hash), `reason/guards.py` (contract guards promoted
from underscored privates, because `store.py` was importing them to verify audit rows).

The plan is inspectable, which turned out to be immediately useful:

```text
sales.deal_cooling@1.0.0 · 7 units · 4 stages · budget 160ms (critical path 95ms)
  stage 0 (independent): core.relationship [gate], core.temporal [gate]
  stage 1 (independent): core.constraint, core.risk
  stage 2 (independent): core.confidence, core.priority
  stage 3: core.planning
```

That is 41% latency headroom nobody had measured. Planning costs 8.2µs.

### Part 2 · Seventeen units, 52 plugins

Every unit now subclasses `ReasoningUnit` (`reason/unit.py`) and implements the eight stages, with
2–4 analyzer plugins each. Full per-unit reference — plugins, exact formulas, and the reasoning
behind each formula — is in the companion artifact; the roster:

```text
Category 1 · Situation Understanding   context, timeline, dependency, constraint
Category 2 · Business Evaluation       risk, opportunity, impact, priority, confidence
Category 3 · Optimization              tradeoff, resource, scheduling, cost, policy
Category 4 · Decision Support          alternative, validation, recommendation
```

Twelve were built new. Four (`constraint`, `risk`, `priority`, `confidence`) predated the framework
and were **migrated as byte-identical refactors** — each with a differential test asserting
`old.semantic_hash == new.semantic_hash` against a frozen copy of the pre-migration implementation,
across 16–20 scenarios including the shipped `DEAL_COOLING_V1` config. No decision hash moved.

Three invariants are enforced across the roster by `tests/test_unit_roster.py`:

- Exactly one unit may publish each metric name. Two publishers is the ambiguity the authority rule
  exists to remove, and `core.validation` would report the overlap as a contradiction.
- Only `core.confidence` publishes `confidence_bp`; only `core.priority` publishes `urgency_bp` and
  `priority_override_bp`. Any other publisher would silently re-score the whole system the day it
  was added to a capability.
- No unit's source contains a clock, randomness, environment access, or a database import.

### Part 3 · Decision Maker

Extracted from the orchestrator into `reason/decision_maker.py`, with the six blueprint components
as separate, individually tested functions:

```text
aggregate_evidence     → every citation the units stood behind, deduplicated
calculate_confidence   → one authoritative confidence, capped when degraded
synthesize_candidates  → declared plays become scored candidates
evaluate_candidates    → hard checks eliminate BEFORE anything is ranked
rank_candidates        → total order; ties break on play_id, never iteration order
build_candidate_objects→ immutable, content-addressed candidates
```

On candidate **generation**: the action space stays authored in Layer 3. That is Law 02 — *domain
expertise never decides, it only exposes operations*. Inventing an action no expert authored would
be Part 3 quietly becoming a domain author. The synthesis is in scoring, checking and ranking the
exposed operations, which is what the architecture actually asks for.

---

## Part 4 — Bugs found and fixed

### The replay-determinism defect (the serious one)

Found by adversarial review, reproduced end-to-end against the shipped capability.

`ReasonerSpec.config` is a mapping and preserves insertion order. The audit store serialises the
manifest with `sort_keys=True`, and PostgreSQL `jsonb` re-orders object keys again by its own rule
(length, then bytewise). So the config a replayed run receives is **the same data in a different
order**. Two units iterated it unsorted, emitted their adjustments in a different order, and hashed
differently — while `capability_snapshot_id` and `request_id` stayed byte-identical, because those
are computed from canonical, already-sorted bytes.

Result: `replay_persisted()` reported **every persisted `deal_cooling` run as non-reproducible**,
with nothing upstream signalling a changed input.

The decision was never wrong — adjustments are summed per component, so a permutation cannot move a
score — but the mechanism that *proves* determinism was broken, which for an audit trail is nearly
as bad.

- Fix: `sorted()` at `temporal.py:57`, `temporal.py:60`, and `risk.py:163` (the last now inside
  `RiskMitigationPlugin` after the migration, which sorts again on the consumer side).
- Regression: `tests/test_reasoning_config_order.py`, which fails three ways when the fix is
  reverted. It also carries a *guard-the-guard* test, because the first version of this test passed
  with the bug reintroduced — the fixture did not author per-play config, so it proved nothing.

Why the existing replay tests missed it: they rebuild the manifest with `canonicalize()`, a pure
Python transform that **preserves** key order, rather than `canonical_dumps()`, the JSON serialiser
the store actually uses.

**Consequence for the CTO:** runs persisted *before* this fix will still replay as diverged. They
already did. Nothing to migrate — the kernel is uncommitted and shadow-only, so there is no
persisted authority to protect.

### The metric collision

`core.cost` and `core.alternative` both published `do_nothing_cost_bp`. `core.cost` is the authority
on cost, so the alternative unit's figure was renamed `do_nothing_baseline_bp`; it still *reads*
`core.cost`'s value rather than re-deriving a second, disagreeing estimate. Pinned by
`test_no_unit_publishes_a_metric_another_unit_owns`.

### Three latent bugs deliberately preserved

Found during the byte-identical migrations. **Not fixed**, because fixing them changes behaviour and
that was outside the refactor's contract. Each is a decision for the CTO:

1. **`core.priority` name mismatch.** It reads the source's `priority_bp` and republishes it as
   `priority_override_bp`. In the shipped config the source is `core.temporal`, which publishes no
   `priority_bp`, so the override path is **inert in production today**. Whether the asymmetric name
   is a legacy bridge or a typo cannot be determined from the code.
2. **`core.priority` cliff.** Zero priors → urgency 5,000 (neutral). One prior that ran and
   published no urgency → 0. Adding a single unrelated reasoner to a capability with no
   `source_reasoner` drops urgency from 5,000 to 0.
3. **`core.confidence` metric collision.** It emits `completeness_bp`, a name `core.context` already
   declares. It is emitted in the result but cannot be listed in `publishes` without failing the
   roster test, so it is filtered from the Verdict and re-attached in `build()`. Fixing it properly
   means renaming the metric — a deliberate, hash-breaking change.

---

## Part 5 — Deployment runbook

**Nothing below is optional and the order matters.** Three locks stand between the built *sweep*
engine and a live one. Each was placed deliberately; each needs a conscious decision to open.

| Lock | Location | Effect |
|---|---|---|
| 1 | `packs/capabilities/__init__.py` — `BUILTIN_CAPABILITIES = (DEAL_COOLING_V1,)` | The 17-unit capability is never picked up by the runner sweep |
| 2 | `deal_cooling.py`, `deal_cooling_v2.py` — `live_delivery_enabled=False` | Neither deal_cooling decision can cross the delivery boundary |
| 3 | `reason/runner.py:run` — `mode=ExecutionMode.SHADOW` on the native sweep call | The sweep's native path is pinned to shadow regardless of pack state |

**These locks do not cover the composite path.** `compose_deal_health` runs `sales.deal_health` at
the tenant's real execution mode and that manifest is delivery-enabled. If you need Layer 4 fully
dark for a tenant, deactivate the pack — the locks above are not sufficient.

One asymmetry worth knowing before you author a new manifest: `CapabilityManifest.live_delivery_enabled`
**defaults to `True`** (`contracts/reasoning.py`). `adapters/legacy_pack.py` never sets it, so the
legacy path is delivery-enabled by omission rather than by declaration. A new native manifest that
forgets the flag ships live. That inverts the fail-closed principle at exactly the boundary where it
matters most, and is worth changing to a required, explicit field.

### Step 0 — Commit the kernel first

`git status` shows 23 modified/untracked files under `genios_engine/reason/`. **Do not build on top
of this and do not deploy from it.** The repo already carries a ratchet
(`tests/test_no_missing_module_deps.py`) that exists *because* importing an uncommitted module once
caused a silent reasoning outage.

```bash
cd ~/genios-brain
.venv/bin/python -m pytest tests/ -q          # must be 1678 passed
git add genios_engine/reason genios_engine/packs/capabilities tests migrations
git commit -m "feat(L4): complete the reasoning engine — orchestrator, 17 units, decision maker"
```

### Step 1 — Run the 17-unit capability in shadow, on real data

This is the step that produces information. Until now the roster has only ever seen test fixtures.

```python
# genios_engine/packs/capabilities/__init__.py
BUILTIN_CAPABILITIES = (DEAL_COOLING_V1, DEAL_COOLING_FULL_V2)
```

Leave locks 2 and 3 alone. The runner picks capabilities by `domain == pack_id` and
`root_entity_type == node_type` (`runner.py:423`, `runner.py:483`), so v2 will run on every deal
node alongside v1, persist a full trace, and emit a `native_shadow` suppression row. Nothing is
delivered.

### Step 2 — Confirm it is actually running

```sql
-- both capabilities should appear, with outcomes
select capability_id, mode, outcome_kind, count(*)
from reasoning_runs r join reasoning_run_outputs o using (run_id)
where r.org_id = :org and r.evaluation_time > now() - interval '1 day'
group by 1,2,3 order by 1,3;
```

Expect `sales.deal_cooling_full` with `mode = shadow`. If it is absent, the capability is not in
`BUILTIN_CAPABILITIES` or its `root_entity_type` does not match any node type.

### Step 3 — Compare v1 and v2 before trusting either

This is the whole point of running both. For the same node and evaluation time:

- **Same winner?** v2 should not flip clear-cut calls. A different winner is a finding, not a bug —
  investigate which unit moved the score and whether it was right.
- **What does v2 see that v1 cannot?** `core.opportunity`, `core.scheduling`, `core.validation`,
  `core.tradeoff`, `core.cost`, `core.timeline` produce readings v1 has no access to.
- **`core.validation.ungrounded_claim_count`** — how many claims in the run cite no evidence. If
  this is high, the problem is upstream in L1/L2 evidence, not in L4.
- **`core.validation.safe_bp`** below `safety_floor_bp` eliminates every play. If v2 blocks where v1
  decides, read this first.

### Step 4 — Tune the thresholds against real outcomes

Every threshold in the twelve new units is currently **a guess**. They were authored from domain
reasoning, not fitted to your data. The ones that will matter first:

```text
core.opportunity   opportunity_threshold_bp   2,500   when does headroom count as an opportunity
core.validation    safety_floor_bp            3,000   how broken must reasoning be to veto
core.policy        soft_compliance_floor_bp   2,500   floor that soft concerns cannot fall below
core.dependency    depth_penalty_bp           1,500   cost of a blocker outside this workflow
core.cost          cost_weight_effort_bp      6,000   effort vs exposure ratio
capability         confidence_floor_bp        4,500   below this, ask a human instead of advising
```

All are per-capability config in the manifest, so tuning one tenant does not move another.

### Step 5 — Activation

Only after Steps 1–4 have produced evidence. Three edits, in this order, each deployed and watched
separately:

1. **Unpin the runner** (`runner.py:526`): replace `mode=ExecutionMode.SHADOW` with the same
   `execution_mode` the legacy path already computes at line 418 (`LIVE` iff pack state is
   `active`). Watch for a week.
2. **Enable delivery** on v2 (`deal_cooling_v2.py:166`): `live_delivery_enabled=True`. Note this
   changes the manifest's content address, so `capability_snapshot_id` changes — that is correct and
   intended, it *is* a different capability now.
3. **Build the native delivery adapter.** This does not exist yet. The legacy path emits `signals`
   rows; the native path currently emits only a suppression row. Something must turn a
   `ReasoningExecution` into whatever L5.2 consumes, satisfying
   `reason/authority.py`'s `AUTHORITATIVE_SIGNAL_PREDICATE` — a ~130-line SQL predicate that
   re-proves the decision on every downstream read. **Get this wrong and every surface silently
   shows nothing, with no error.**

### Step 6 — Rollback

Each lock is independent and reversible with one edit. Rollback is: restore the lock, redeploy. No
data migration, no cleanup — shadow runs are audit rows and are meant to accumulate.

---

## Part 6 — What is genuinely unproven

Said plainly, because the test count is misleading on its own.

- **1678 tests pass, and not one of them is real data.** Every fixture is synthetic. No unit built
  in this pass has reasoned about an actual customer's deal. (The composite path *is* live, but it
  runs `sales.deal_health`, which uses only the pre-existing units.)
- **Twelve of the seventeen units have zero production callers** outside the reasoners package.
- **Context-aware selection cannot currently be enabled.** `store.persist_complete` requires the
  persisted plan to cover every reasoner the manifest declares, so a capability that prunes an
  optional unit will plan and execute correctly and then fail to persist. The flag is off by
  default and no capability sets it, so nothing shipped is affected — but it is not usable until
  the store learns about pruning. Documented in
  `System Design/Layer-4-Reasoning-Engine/01-Orchestrator.md`.
- **The thresholds are guesses.** They cannot be tuned until decisions ship and L6 sees outcomes —
  and L6 cannot see outcomes until decisions ship. Step 1 breaks that circle by producing shadow
  decisions with real inputs.
- **The native delivery adapter does not exist.** This is the largest remaining build item and it is
  the one that touches the authority SQL.
- **L4 still reads per-node `NodeContext`, not L2 `BusinessSituation`.** The blueprint says Layer 4
  should reason over situations; `context.situations.active_situations()` has zero callers in
  `reason/`. This was deliberately deferred so the unit roster and the input contract would not
  change in the same move. It remains open.

---

## Part 7 — Where we disagreed with the architecture spec

Three places, all documented above and all deliberate:

1. **No wall-clock timeouts.** Static budget enforcement plus telemetry instead. Determinism
   outranks the diagram.
2. **Parallelism described, not performed.** `ExecutionPlan.stages` proves the safe grouping and
   hashes it; execution stays sequential because concurrency that could interleave results would
   make the trace depend on machine timing.
3. **No LLM consultant below the floor.** `DEFER` and a human instead.

And one place where the code is arguably *better* than the spec: the blueprint describes per-
situation unit selection ("run Risk and Priority, not Pricing"). The repo achieves that at compile
time — the legacy adapter compiles one capability per rule, so selection is baked into the manifest
rather than chosen at runtime. That is more deterministic. Runtime selection was added as an opt-in
(`context_aware_selection`) for capabilities that want it, but the compile-time answer remains the
default and is the better one.

---

## Summary

Layer 4 is architecturally complete and verified: three parts properly separated, seventeen units on
a common framework with fifty-two analyzer plugins, a decision maker that is the sole synthesis
authority, deterministic and replayable end to end, adversarially reviewed with one real defect
found and fixed.

It is also **switched off in three places on purpose**, has never seen production data, and is
missing the native delivery adapter.

The next action is not more building. It is Step 0 and Step 1: commit the kernel, then run the
17-unit capability in shadow against real data and read what it says. Everything after that should
be decided from that evidence rather than from this document.

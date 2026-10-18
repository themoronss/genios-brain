# GeniOS-008 — the migration plan: from today's code to the new architecture

**Written for:** Rohit, Harsh and every coding agent. **Date:** 18 Oct 2026. **Target:**
[`00-ARCHITECTURE.md`](00-ARCHITECTURE.md). **Rules:** [`01-RULES.md`](01-RULES.md).

**Measured at:** `speedrun008` `62b9ac02`. Four read-only audits covered L1 (17 Oct), L2, L3, and L4–L6
(18 Oct). Every "exists" below names its file. Every verdict is one of:
- **REUSE** — lift it as it is;
- **ADAPT** — reshape it to the new contract;
- **REPLACE** — old flow only; it is retired.

This is the plan's spine. Each layer gets its detailed `02-PLAN` when Rohit opens that layer and gives its
details (`01-RULES` Rule 4). L1's is already written (`layer-1-enterprise-signals/02-PLAN.md`, Group E).

---

## 1 · Where the code stands against the new architecture, in one table

| Architecture piece (`00-ARCHITECTURE`) | Today | Verdict |
|---|---|---|
| L1 → L2 contract: **QualifiedEnterpriseSignalBundle** + coverage receipt | built by `capture/esqe/bundle.py` every sweep, then **dropped** (`esqe/finalize.py:134` passes no store); coverage lives per window in `capture/coverage/window.py`, not on the bundle | ADAPT |
| L2 **Orchestrator loop** | nothing is the loop. `reason/runner.run_all` runs three lanes in sequence: the expert pass, `domain_shadow.shadow_compile` (the de-facto orchestrator), and the legacy per-pack `run()` | ADAPT, from `shadow_compile` + the expert pass |
| **ReasoningRequest** | `contracts/reasoning.py:728`; its trigger is a free string; there is no bundle or event trigger | REUSE + extend |
| **Material-change gate** | `reason/change_gate.py:71`, `fingerprint.py:187` (STEP-02), on all three lanes | REUSE |
| **ContextSnapshot** (bounded, bitemporal, from L3) | the contract is at `contracts/reasoning.py:414`, but `reason/` builds it from a **whole-org** read. `context/bounded_read.read_bounded` (seeds, hops, max nodes, revision) has **no callers** and is live-only | ADAPT |
| Router (live domains per tenant) | `platform/l3_activation.py:271`; corpus `default_on` (Admin true; Sales, Support, Founder Office false) | REUSE |
| **Domain Compiler → ExpertisePackage** | `packs/compiler/*`, hash-pinned; live for Admin | REUSE |
| Four brains | read at compile (`compiler/runtime_brains.py`); written off the sweep (`feedback/brain_pipeline`, `org_rule_ingest`); there is no single precedence resolver | ADAPT |
| **Need classification** (stage, evidence, time, impact, complexity → 0/1/2/3 calls) | **missing**; only pieces exist | BUILD |
| Unit selection + dependency-complete plan | `reason/plan.py:442 ReasoningPlanner`, `_ROSTER`, `roster_v2`; the default 6-unit DAG runs **risk half-blind** | REUSE + fix |
| Tools (dates, money, baselines) | spread over `reason/baselines.py`, `context/workstream_numbers.py`, `kind_numbers.py`, `reason/bundle/numbers.py`; **no money tool** | ADAPT into one `reason/tools` |
| **One bounded judgment pass** | the STEP-12 expert pass (`reason/expert/*`, Sonnet-class, per changed file) is the closest; it runs as a lane, not as a step | ADAPT |
| The model scoring or deciding (`llm_decision_maker`, R-1) | live when `GENIOS_L4_LLM_DECISION_MAKER` is on; the model chooses DECISION vs DEFER, which **breaks** the model rules | REPLACE |
| **Claim validation** | `reason/expert/verify.py` + `contracts/claim_check.py` (STEP-13), on the expert path only | ADAPT to every claim |
| **Lanes** | `reason/output_lane.py:71`, 5 lanes, deterministic; stored on `signals` | REUSE |
| **Confidence vector** (evidence, frame, temporal, causal, authority, coverage) | different keys (`contracts/reasoning.py:254`); routing still uses one scalar floor (6000 bp) | ADAPT |
| **EvidenceNeed raised by L2** | **missing**; only L3 raises needs (`context/evidence_needs.py`), and the L1 executor has no fetcher | BUILD |
| **ReasoningResult** | **does not exist**; L2 writes a `ReasoningDecision` flattened into a `signals` row | BUILD |
| Write-back with compare-and-set | `runner._graph_version_guard` guards signal publication only; no situation mutation is written back | ADAPT |
| Receipts + replay | `reason/audit.persist_execution`, `reason/replay.py` | REUSE; batch the transactions (two per situation today) |
| **Where a situation is born** | **L3, before reasoning**: 9 writers in `context/` (§3.3) | REPLACE: L2 forms, L3 admits |
| L3 admission door | `context/situation_publisher` (ADMIT, HOLD, REJECT); called only from `shadow_compile`, **after** the row already exists | ADAPT so it gates existence |
| A HOLD raises an EvidenceNeed | `context/hold_needs.py` is written, with **no caller** | ADAPT |
| Evidence Graph | `context/graph_store.py`, `identity.py`, `merge.py`, `pipeline.py` | REUSE |
| Bitemporal facts | columns exist (`occurred_at`, `valid_from`, `valid_to`, `recorded_at`); ~8 derived writers **bypass** `analytic/publish.py` and stamp `valid_from = occurred_at = now` every sweep | ADAPT (also the database churn) |
| Identity with doubt | `context/identity.resolve_alias_candidates` exists with **no caller**; ambiguity becomes "nobody" | ADAPT |
| Model calls inside L3 | `context/lifecycle/resolution.py:234` (every sweep); angles (no asker in the sweep); cohort drafter (on demand) | move to L2 |
| **DecisionObject** | **does not exist**; `ReasoningDecision` and `brief.v1` have no owner, approver, deadline, reversibility or authority | BUILD |
| L4 input | `executive/sweep.py:73` auto-plans commitments from `signals`, so no human decides first | REPLACE |
| execution.v1, lifecycle, ladder (1/3/7/14, max 6) | `executive/*` | REUSE |
| Org data (seats, reports_to, channels) | tables exist; **no engine writer** for `manager_seat_id` / `seat_responsibilities` | BUILD a writer |
| Morning brief (STEP-15) | `executive/morning*`, every sweep; reads files and reviews, not executions | ADAPT |
| L5 card source | built from `signals` rows; the living card per file (STEP-14); situation cards gated off | ADAPT to the ReasoningResult lane |
| Claim validation on cards | `deliver/claim_validator.py`, `render.py:641` | REUSE |
| Budget, dedupe, digest, outbox, bridge, agent API | `deliver/*` | REUSE |
| Push to people | every org registers only `in_app`, so **nothing pushes** | BUILD a channel |
| Card loads | `deliver/card_builder.load_node` is N+1 per signal | ADAPT (bulk) |
| L6 calibration (28 days, ≥8, mute <0.25 with ≥12; shadow unless armed) | `feedback/calibrate.py` | REUSE |
| L6 attribution by layer | `contracts/learning_attribution.py` + `feedback/attribution.py`: it counts and **changes nothing** | ADAPT |
| Brain proposals | `feedback/publisher.py`; two evolution units are `return []` stubs | ADAPT |

---

## 2 · What YC-II W27 built, and where it lands in the new architecture

Nothing below is thrown away. Each piece is re-seated.

| Built (YC-II W27) | What it is | Lands in |
|---|---|---|
| STEP-01 golden set | 53 founder cases + the Atlas replays, run through the real chain on Postgres | **the cutover judge**: it scores the old and new paths side by side |
| STEP-02 change gate | no new evidence → no new decision, 0 calls | **L2 Orchestrator step 2**, as is |
| STEP-03 the gate keeps everything | archive, never delete | **L1 gate**, as is |
| STEP-04 who is us | one identity answer | **L0/L1**, as is |
| STEP-05 every kept item enters memory | archive enters as names and dates | **L3 memory**, as is |
| STEP-06 nothing lost silently | end states, why-not | **L5 receipts + L3 situation end**: kept, re-pointed to the ReasoningResult |
| STEP-07 the company brief | goals, people, watchlist, read by every judging prompt | **Plane D organisation brain** (adaptive brain for the watchlist) |
| STEP-08 the resync | old mail comes back | **L1 backfill / EvidenceNeed BACKFILL_WINDOW** |
| STEP-09 workstream files | one file per piece of work in motion | **L3 memory** (the file is a memory object); **L2 reads it in the snapshot** |
| STEP-10 the expert's numbers | every number with n and basis | **L2 Tools** |
| STEP-11 founder playbooks | Founder Office corpus | **Plane D** |
| STEP-12 expert pass | one strong-model review per changed file | **L2 Orchestrator step 8**: the one bounded judgment pass |
| STEP-13 check every claim, question card | claim check, the investigation lane | **L2 step 9** (validate every claim) + **L5 investigation lane** |
| STEP-14 living card | one card per file, versions | **L5 card = a view of the ReasoningResult** |
| STEP-15 morning brief | 08:00 brief | **L5 surface** (Atlas A.8) |
| STEP-16 learning from you | corrections change the next judgment | **L6 attribution** + the behaviour brain |
| STEP-17 real tests | Postgres in CI, golden in CI | CI, as is |
| STEP-18 known bugs | fixes on the way | kept |

**The `YCW27/` audit programme** (receipts, witnesses, ratchets, `table_coverage`) stays as the test
discipline. Its layer numbering is the old one and is never quoted without the package name.

---

## 3 · The plan, layer by layer

Each item gets an ID and the section of `00-ARCHITECTURE` it implements. The detailed plan for a layer is
written when Rohit opens that layer.

### 3.0 · L0 contracts and guards — first, before any behaviour moves

| ID | Item | Cites |
|---|---|---|
| L0-1 | `ReasoningResult` contract: facts, inferences, hypotheses, unknowns, frames, expected vs actual, consequences, intervention, best next move, decision need, **six-dimension confidence vector**, lane, mutations, evidence needs, provenance | L2 output |
| L0-2 | `DecisionObject` contract: question, options with trade-offs, recommendation, owner, approver, deadline, reversibility, authority | L3 → L4 |
| L0-3 | `SituationSeed` / situation mutation contract (L2 proposes, L3 admits) | L2, L3 |
| L0-4 | Bundle storage contract: `signal_bundles` + coverage receipt + `unresolved[]` | L1 out |
| L0-5 | **CI guards** (`01-RULES` Rule 3): the card guard, the situation-writer ratchet (starts at the 9 writers in §3.3), the model-site guard | Rules |

### 3.1 · L1 Enterprise Signals — `capture/`

Done and pushed: A1, A2, A3, C3. **To build:** Group E, E1–E10
(`layer-1-enterprise-signals/02-PLAN.md`):
- E1 bundle stored;
- E8 carried fields;
- E2 EvidenceNeed fetchers;
- E4 six object types;
- E5 absence signals;
- E3 entity doubt;
- E6 roles;
- E7 lifecycle;
- E9 injection boundary;
- E10 metric definitions.

Waiting on Rohit: B1, B2 (the junk filter's live measurement and its prompt).

### 3.2 · L2 Reasoning — `reason/` + `packs/` (the core of the rebuild)

| ID | Item | Built from |
|---|---|---|
| L2-1 | **The Orchestrator loop** as one module (`reason/orchestrator`), running the 12 steps of `00-ARCHITECTURE` | `shadow_compile`'s body + `run_all` |
| L2-2 | Request from the **bundle** (new trigger types: bundle, deadline crossed, expected reply absent, outcome, human ask) | `ReasoningRequest` |
| L2-3 | Snapshot from L3 through `read_bounded` (seeds, hops, max nodes, revision, **as-of**) instead of the whole-org read | `context/bounded_read.py`, `runner._bulk_load_*` |
| L2-4 | **Need classification** → depth 0–3 → call budget | new |
| L2-5 | Plan: dependency-complete (temporal + relationship scheduled before risk) | `plan.py`, `_ROSTER`, `roster_v2` |
| L2-6 | `reason/tools`: dates, money, baselines, reply times, all on the frozen snapshot | `baselines.py`, `workstream_numbers.py`, `kind_numbers.py`, `bundle/numbers.py` |
| L2-7 | **The judgment pass** = the expert pass, re-seated as step 8 (per situation group, not per lane) | `reason/expert/*` |
| L2-8 | **Validate every claim** with the STEP-13 check, on every result | `expert/verify.py`, `claim_check.py` |
| L2-9 | Lane + six-dimension confidence vector; no scalar floor | `output_lane.py` |
| L2-10 | **L2 raises EvidenceNeed** when one missing fact decides | new; executes through L1 E2 |
| L2-11 | **Situation forming moves into L2**: the readings in `context/` (outreach, support, periodic, meeting, document, condition, blocker, analytic, correlation_*, patterns, importance) become L2 inputs or units, one type at a time | §3.3 list |
| L2-12 | Model calls that do not belong: retire `llm_decision_maker` / R-1 scoring (the model never decides); move `context/lifecycle/resolution` into L2 | `llm_decision_maker.py`, `lifecycle/*` |
| L2-13 | Write the **ReasoningResult**, receipt and replay; batch transactions (one per sweep, not two per situation) | `audit.py`, `replay.py` |
| L2-14 | Four-brain precedence resolver (law → org → authority → constraint → expertise → behaviour → heuristic) | `runtime_brains.py` |

### 3.3 · L3 Context Graph — `context/`

| ID | Item |
|---|---|
| L3-1 | **Admission gates existence**: a situation row exists only after `situation_publisher` ADMITs L2's proposal; a HOLD raises an EvidenceNeed (`hold_needs.py`, wired) |
| L3-2 | **The ratchet list, retired one type at a time.** These are the 9 sweep writers today: `situations.refresh_situations`, `age_uncorrelated_situations`, `support_situations`, `outreach_situations` (+ its second pass), `periodic`, `meeting_touch`, `document_register`, `situation_bso.refresh_situation_importance`, `lifecycle/store.apply_lifecycle` |
| L3-3 | **Bounded bitemporal snapshot API** served to L2 (`read_bounded` + as-of + unknowns + contradictions) |
| L3-4 | **DecisionObject minted** from a decision-ready ReasoningResult |
| L3-5 | **Derived facts:** values that do not depend on the clock stay in L3 through `analytic/publish`. Values computed against "now" (days waiting, overdue hours, age) become L2 tools on the snapshot. This ends the every-sweep rewrite (the ~8 writers that bypass `publish.py`) and with it most of the database churn |
| L3-6 | Identity keeps its candidates (`resolve_alias_candidates`, wired) |
| L3-7 | No model calls in L3 (resolution and angles move to L2) |

### 3.4 · L4 Executive — `executive/`

| ID | Item |
|---|---|
| L4-1 | Input = **DecisionObject that a human decides** (approve, reject, defer, choose); stop auto-planning from `signals` |
| L4-2 | An approver on execution.v1 (`resolve_approver_seat`) |
| L4-3 | A **writer for org data** (seats, `reports_to`, channels), at onboarding and from the company brief |
| L4-4 | The 7-condition gate counted per condition |
| L4-5 | The morning brief reads executions and decisions too |

### 3.5 · L5 Delivery — `deliver/`

| ID | Item |
|---|---|
| L5-1 | The card is a **view of the ReasoningResult**: lane, vector, evidence, unknowns, options, authority (the living card, STEP-14, kept) |
| L5-2 | A why-not receipt on every suppress or hold, attached to the card receipt |
| L5-3 | A **push channel** (Slack or email) beyond `in_app` |
| L5-4 | Bulk card loads (end the N+1) |

### 3.6 · L6 Learning — `feedback/`

| ID | Item |
|---|---|
| L6-1 | **"Wrong because…"** routes to the layer that failed, and changes that layer's data |
| L6-2 | Behaviour and adaptive evolution units (today `return []`) |
| L6-3 | Retire the write-only tables, or give each a reader |

---

## 4 · Order and cutover

```
L0 contracts + guards
  → L1 Group E (bundle first)
  → L2 orchestrator in SHADOW (writes ReasoningResult, no cards)
  → golden set: old vs new, side by side
  → L3 admission gates existence — switch ONE situation type
    (awaiting reply / outreach first: the founder's investor cases)
  → L5 card from the ReasoningResult for that type
  → repeat per type (the ratchet shrinks)
  → L4 DecisionObject + human decides
  → L6 attribution
  → delete the old path
```

**Switch rule:** a type switches only when the golden board on the new path is at least as good as on
the old one (must-detect, must-abstain, forbidden outputs). Each switch is one commit with a one-line way
back.

## 5 · Harsh, per layer

Every pushed group writes the layer's `04-FOR-HARSH`:
- what changed;
- migrations;
- switches (which org, which flag);
- commands;
- what he should see;
- how it goes wrong;
- how to roll back.

**Before any of this reaches production**, Harsh deploys `speedrun008` (L1 `04-FOR-HARSH` H1).
Production still runs `harsh/mvp`, 815+ commits behind.

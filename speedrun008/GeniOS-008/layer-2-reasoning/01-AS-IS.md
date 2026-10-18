# L2 Reasoning (`reason/` + `packs/`) — as it is, against the new architecture

**Measured at:** `speedrun008` `62b9ac02` (18 Oct 2026), by a read-only audit of `genios_engine/reason/`,
`genios_engine/packs/` and `Domain Expertise/`. Paths are under `genios_engine/`. Each item is judged against
[`../00-ARCHITECTURE.md`](../00-ARCHITECTURE.md) and the L2 spec ([`05-SPEC-layer-2.md`](05-SPEC-layer-2.md)),
never against today's flow.

**Verdicts:**
- **REUSE** — lift it as it is.
- **ADAPT** — reshape it to the new contract.
- **REPLACE** — old flow only; it is retired.
- **BUILD** — missing.

## 1 · How L2 runs today (the old flow)

`api/routes.py:736 _run_l2_chain` → `context/runner.process_pending` (**L3 forms the situations first**) →
`reason/runner.py:1820 run_all`, which runs three lanes, one after the other:

1. **`expert/sweep.expert_pass`.** One Sonnet-class review per changed *file*. It runs only where `expert_review` is activated.
2. **`domain_shadow.shadow_compile`.** For each situation `context/` already wrote:
   1. build the BSO;
   2. `publish_situation` (ADMIT / HOLD / REJECT);
   3. compile expertise;
   4. run the deterministic R-units;
   5. the decision.

   Admin is live; Sales and Support are shadow.
3. **`run()` per pack.** The legacy deterministic rules.

Then `bundle.narrate_published` runs. The output of all of it is a **`signals` row**, and the cards are built from that.

## 2 · What exists, piece by piece

| Architecture piece | Today (file) | Reached? | Verdict |
|---|---|---|---|
| ReasoningRequest | `contracts/reasoning.py:728`; trigger is a free string (`legacy.rule_scan`, `capability.graph_scan`, `expert.review`, …) | yes | REUSE + bundle/event triggers |
| Material-change gate (STEP-02) | `reason/change_gate.py:71`, `fingerprint.py:187`; fingerprint = the request with clocks removed, pack revision, verdicts, model | yes, all lanes | REUSE |
| ContextSnapshot | contract `contracts/reasoning.py:414`; built inside `reason/` from a **whole-org** read (`runner._bulk_load_facts/_obs`); `context/bounded_read.read_bounded` exists with **no caller** | yes | ADAPT |
| HistoricalContext (similar past cases, outcomes) | pieces: `context/workstream_timeline.py`, `file_judgments.py`, `file_outcomes.py`, the expert dossier | expert path only | ADAPT into one object |
| Router — live domains per tenant | `platform/l3_activation.py:271`; corpus `default_on` (Admin true; Sales, Support, Founder Office false) | yes | REUSE |
| Domain Compiler → ExpertisePackage | `packs/compiler/*` (8 parts), hash-pinned, `contracts/domain_expertise.py:766` | yes (Admin live) | REUSE |
| Four brains | read at compile (`compiler/runtime_brains.py`); written off-sweep (`feedback/brain_pipeline`, `org_rule_ingest`); company brief (STEP-07) | partly | ADAPT |
| Playbooks (Founder Office, STEP-11) | `packs/compiler/playbook_reader.py`; `Domain Expertise/Founder Office Expertise` (20 capabilities) | expert dossier only | ADAPT into the package |
| Need classification → depth | **missing** (stage only in `expert/stage_dwell.py`) | — | BUILD |
| Plan compiler + units | `reason/plan.py:442 ReasoningPlanner`, `_ROSTER`, `roster_v2`; 23 **deterministic** reasoners in `reason/reasoners/` (risk, priority, confidence, impact, tradeoff … compute scores by formula); default DAG runs risk half-blind | yes | ADAPT (see §3) |
| Tools | `reason/baselines.py`; `context/workstream_numbers.py`, `kind_numbers.py` (STEP-10 numbers with n); `reason/bundle/numbers.py`; date logic inside `temporal.py`, `timeline_unit.py`; **no money tool** | yes | ADAPT into one `reason/tools` |
| **The judgment pass (LLM)** | `reason/expert/*` (STEP-12): dossier → `prompt.py` → `review.py` (Sonnet-class, 6000 out, ≤10 a pass, $2/day) → `ExpertReview` with **facts, inferences, patterns, hypotheses, unknowns, frames, expected vs actual, scenarios, appraisal, mode, next move, alternative, wait/stop, done-when, draft** (`contracts/expert_review.py:264`) | yes, where activated | **ADAPT — this becomes the core of L2** |
| LLM decider / R-1 | `reason/llm_decision_maker.py`, `llm_interpretation.py` (env `GENIOS_L4_LLM_DECISION_MAKER`); the model picks DECISION vs DEFER over a deterministic candidate list | env-gated | REPLACE (folded into the judgment pass) |
| Claim validation (STEP-13) | `reason/expert/verify.py`, `contracts/claim_check.py`: line-by-line — cited ids, quotes in the mail, names on their lines, numbers match | expert path only | ADAPT to every result |
| Lanes | `reason/output_lane.py:71` (5 lanes) stored on `signals.output_lane` | yes | REUSE |
| Confidence vector | `contracts/reasoning.py:254` — 4 evidence keys, not the six dimensions; routing still uses a scalar floor (6000 bp) | yes | ADAPT |
| EvidenceNeed raised by L2 | **missing** in `reason/`; only L3 raises needs | — | BUILD |
| ReasoningResult | **does not exist**; `ReasoningDecision` → `signals` row | — | BUILD (from `ExpertReview`) |
| Write-back with compare-and-set | `runner._graph_version_guard` guards publication only; no situation mutations | partly | ADAPT |
| Receipts + replay | `reason/audit.persist_execution`, `reason/replay.py` (replays expert decisions with no model); **two DB transactions per situation** | yes | REUSE + batch |
| Question to the founder | `reason/expert/asks.py` (`founder_question`) | yes | REUSE (investigation lane) |

## 3 · The one thing that changes most

The spec makes **the LLM the reasoning engine**: meaning, framing, patterns, history, consequences and the next move.
Deterministic code only supports it:
- retrieval;
- IDs and schema;
- permissions;
- integrity;
- exact arithmetic when a numeric question really arises.

Today it is the other way round on the main lanes:
- **23 deterministic reasoners** score risk, priority, confidence, impact and trade-offs by formula.
- The **pack rules** decide by rule.
- The LLM decider only picks between candidates those rules produced.

The **expert pass** is the one place the spec's shape already exists. It covers only *files*, and only where it is switched on.

So the plan (`02-PLAN.md`) changes two things:
1. It generalises the expert pass into L2's judgment pass, for every situation type.
2. It demotes the deterministic reasoners from deciders to **evidence tools**: a date window, a reply time with its n, a baseline. They feed the model; they never decide.

## 4 · Numbers

| | |
|---|---|
| `reason/` | ~20.4k LOC top-level + subpackages: `reasoners/` 8.0k · `expert/` 5.5k · `adapters/` 5.1k · `moments/` 5.5k · `bundle/` 3.4k · `meetings/` 1.1k · `team/` 1.1k · `verify/` 0.4k |
| `packs/` | `compiler/` 4.0k · `brains/` 2.0k · `capabilities/` 0.8k · pack files 1.9k |
| `Domain Expertise/` | 1,494 YAML; capability files: Admin 211 · Support 167 · Sales 151 · Founder Office 20 |

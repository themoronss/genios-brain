# Layer 4 — Architecture and Atlas Delta

**Evidence baseline:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`, audited 2026-08-22. Atlas references are `GeniOS-System-Design-Atlas.md:1593-1945`. In repository numbering this is Layer 4 Reasoning: it consumes the Layer 3 `ExpertisePackage`, answers **“What should happen?”**, and emits a `DecisionObject` plus `ReasoningTrace`. It does not execute work or claim completion.

## Blunt answer

The codebase contains a credible deterministic decision architecture: 17 registered reasoning units, candidate contracts, hard elimination, total-order ranking, explicit no-action/defer outcomes, calibrated confidence authority and trace generation. But the customer-visible route is still substantially thinner. Active legacy packs normally convert one matched rule into one play and a six-unit DAG, while the new Layer 3 adapter also defaults to six reasoners. Consequently the system often has nothing meaningful to compare and renders generic imperatives such as “Reply to what they actually asked,” “Send a recap,” or “Reset the plan.”

This is not primarily an LLM eloquence problem. A ranking engine cannot display intelligent alternatives when the active adapter gives it one generic candidate, incomplete stakes and no observable completion condition.

## Atlas contract versus Current code

| Atlas expectation | Current code proof | State | Gap / customer consequence |
|---|---|---|---|
| ExpertisePackage → DecisionObject + ReasoningTrace | Typed contracts in `contracts/reasoning.py`; orchestration in `reason/orchestrator.py:137-258` | Present, Tested | Authoritative card path does not consistently preserve the rich object |
| All four brain values constrain judgment, not merely identity | `reason/adapters/expertise.py:180-188` hashes capabilities, objects, Expert rules, Organization rules, Behavior patterns and Adaptive preferences; `:190-213` uses that hash in manifest version/metadata | Snapshot identity only | This is **hash-only influence** for Organization, Behavior and Adaptive values: their mutation can change manifest version while leaving goal, constraints, policies, candidate eligibility and ranking unchanged |
| Seventeen bounded reasoning units plus Decision Maker | `reason/reasoners/__init__.py:41-65` registers all 17 core units and supplementary units | Present | Registration is not scheduling; active adapters commonly schedule only six |
| Generate multiple candidate actions | `reason/decision_maker.py:196-250` synthesizes candidates from plays/unit outputs | Present | Legacy adapter usually provides one play, so “multiple” collapses to one |
| Eliminate prohibited/infeasible choices before ranking | `decision_maker.py:257-299` applies elimination before total-order sorting | Present, Tested | Weak upstream constraints cannot eliminate what was never represented |
| Deterministic total-order selection | Candidate ordering and selected candidate at `decision_maker.py:306-329` | Present, Tested | Deterministic genericity remains genericity |
| Explicit abstention/no-action | Outcomes include `NO_ACTION`, `DEFER`, `INSUFFICIENT_CONTEXT`, `BLOCKED`, `FAILED`; terminal/floor logic at `decision_maker.py:359-415` | Present | API/card fallbacks can still render an imperative instead of honest abstention |
| Confidence has one authority and cannot override hard gates | `decision_maker.py:117-137`; below floor returns `DEFER` with no selected candidate | Present, Tested | Card `score` is mapped to `confidence_score` in `api/intelligence_routes.py:503-527`, confusing priority and epistemic certainty |
| Compare action, alternatives, do-nothing and trade-offs | Candidate contract supports alternatives/uncertainty/do-nothing consequence | Present in contract | Active one-play path and UI projection omit meaningful alternatives/trade-offs |
| State why now and what failure costs | Reasoning contract carries consequence/expiry/outcome window | Present in contract | UI projection explicitly records `stakes: missing` and `completion: missing` in `api/routes.py:2056-2098` |
| Recommendation is grounded and replayable | Orchestrator produces trace; decision maker consumes bounded unit results | Present | Generic card templates lose the decision’s causal receipts |
| LLM only for low confidence, ambiguity or explanation; never decider | `reason/intelligence.py:198-409` fixes deterministic action/confidence and lets LLM explain only, rejecting invention | Present, safely bounded | This explanation path cannot compensate for bad candidate generation |
| Reasoning never executes | Contracts separate decision from execution; delivery lives later | Present | UI “I’ll do it” risks collapsing acceptance into perceived completion downstream |

## The 17-unit architecture and active scheduling delta

The Atlas design separates context, relevance, risk, constraints, timing, trade-offs, alternatives, validation and recommendation so each claim can be inspected. The registry can host that architecture. Yet `reason/adapters/legacy_pack.py:24-145` constructs a six-unit DAG around `legacy.rule`, score gate, constraint, priority, confidence and planning, with a generic step such as `Prepare <artifact> for human review`. `reason/adapters/expertise.py` also supplies a conservative default DAG with only context, risk, constraint, priority, confidence and planning. Alternative, trade-off, validation and recommendation units are not part of that default path.

| Decision capability | Rich implementation exists | Active input/schedule | Effective result |
|---|---|---|---|
| Context/risk/constraints | Yes | Commonly scheduled | Basic guardrail context can survive |
| Candidate plurality | Yes | Usually one play from legacy rule | One candidate dressed as a decision |
| Alternative generation | `AlternativeUnit` exists and can deduplicate candidate semantics | Not scheduled by legacy/default expertise DAG | No genuine fallback shown |
| Trade-off analysis | Registered | Not in common six-unit DAG | “Why this over another move?” unanswered |
| Validation/challenge | Registered | Not in common six-unit DAG | Plausible action is insufficiently attacked |
| Recommendation synthesis | Registered | Decision maker can select | Selection quality bounded by thin candidates |
| Abstention | Contract and decision maker support it | Can be bypassed/degraded in API fallbacks | Generic imperative survives uncertainty |
| Completion/outcome definition | Contract fields exist | Card projection says missing | User cannot know when loop is actually resolved |

## Layer 3 package to Layer 4 semantic-consumption gap

The new adapter proves that all four brains were selected and pins their combined bytes, but it does not prove that all four brains affected judgment. At `reason/adapters/expertise.py:180-188`, `organization_rules`, `behavior_patterns`, and `adaptive_preferences` enter `knowledge_hash`; at `:190-213`, that hash changes manifest `version` and metadata. Their values are not read when the adapter constructs the goal, its fixed safety constraint, policies, the default reasoner DAG, play eligibility, candidate semantics, or ranking inputs. A Company Brain approval rule, a Behavior cadence pattern, or an Adaptive timing preference can therefore produce a new hash and apparently new manifest while the recommendation remains byte-for-byte semantically equivalent.

Expert Brain influence is real but much narrower than package presence suggests. `_goal()` at `reason/adapters/expertise.py:156-168` may use the first capability definition's `question`. `_plays()` at `:104-153` ignores Expert rules without `definition.steps`, converts only steps-bearing rules into read-only plays, stops after a **four-play cap**, and emits the generic `review_situation` fallback when none qualify. Mental models, heuristics, failure patterns and other authored Expert artifacts can be present in the package without directly changing a candidate.

| Package material | Current downstream influence | Missing semantic contract |
|---|---|---|
| Capability | First available question may shape the goal; required fields can shape the DAG inputs | Which capability outcomes, constraints and failure modes must affect eligibility and rejection |
| Expert rules | Only rules with `definition.steps`; at most four read-only plays | Typed mapping for heuristics, mental models, failure patterns, trade-offs and abstention |
| Organization / Company Brain | Included in hash/version only | Permission, approval, ICP and operating-policy values must deterministically constrain policies and candidates |
| Behavior Brain | Included in hash/version only | Scoped observed cadence/style may rank otherwise-permitted candidates but must never grant authority |
| Adaptive Brain | Included in hash/version only | Recent bounded preference may tune timing/priority with expiry, never override policy |

The required acceptance proof is a brain-mutation replay: hold the BSO, Expert corpus and other three brains fixed; mutate one brain entry; then prove the exact intended goal, constraint, candidate, rejection or rank changed—or record an explicit deterministic no-effect reason. A changed hash alone is not a reasoning success.

## Runtime authority and projection

`packs/wiring.py:9-23` registers `SALES_V1` and `GENERAL_V1`. `reason/runner.py:525-540` may run the new domain path in shadow, then continues with the effective legacy pack. The more complete 17-unit native candidate is imported but deliberately excluded from the manifest sweep (`packs/capabilities/__init__.py:16-22`); the seven-unit Deal Cooling baseline remains shadow-first. Therefore “17 units exist” is architecture proof, not evidence that a screenshot used 17-unit reasoning.

The card boundary loses additional meaning. `api/routes.py:1987-2022` recognizes only a few special actionable types and otherwise generates generic ask steps. Its deterministic projection at `:2056-2098` preserves an imperative while declaring stakes and completion missing. `api/intelligence_routes.py:423-440` supplies generic play labels, and `:503-527` exposes card score as confidence. `executive/brief.py:76-80` can reduce “why it matters” to score/confidence text. These are projection defects as well as reasoning defects.

## Required architecture decision

Promote reasoning only when a complete Layer 3 package yields at least: one primary candidate, one materially distinct fallback when possible, an explicit do-nothing/stop option, hard rejection reasons, stakes, expiry, owner/approval boundary, observable completion and outcome window. If only one safe action exists, the trace must prove why all alternatives were eliminated. If no candidate meets evidence, expertise or permission gates, the authoritative outcome must be `DEFER`, `INSUFFICIENT_CONTEXT` or `NO_ACTION`; an API template cannot invent a fallback imperative.

Score, confidence and urgency must be separate:

- **score/priority**: expected value, timing and strategic rank;
- **confidence**: reliability of the selected decision given evidence/model calibration;
- **urgency**: cost of delay and expiry window;
- **coverage**: whether applicable expertise actually exists.

No scalar may substitute for another or hide a hard missing field.

## Verdict

**Framework-ready, not live-ready.** The full reasoning engine is much stronger than the shown intelligence, and several safety properties are genuinely implemented. The decisive Gap is active composition and projection: legacy one-play inputs, six-unit schedules, generic templates, score/confidence conflation, and missing stakes/completion prevent the system from behaving like a sales consultant. Wiring all 17 units without richer Layer 3 plays and golden decisions would add machinery, not judgment.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../../00-Methodology/02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->

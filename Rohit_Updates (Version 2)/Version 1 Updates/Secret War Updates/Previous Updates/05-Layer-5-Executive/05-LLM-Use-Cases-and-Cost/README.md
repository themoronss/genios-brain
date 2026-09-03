# Layer 5 Executive — LLM Use Cases and Cost

## Blunt answer

The Current Executive implementation is intentionally Deterministic: repository search at `harsh/mvp@b739bd5` finds no runtime model client in `genios_engine/executive/`; planning, interpretation, coordination, assignment, escalation, validation, monitoring and summary are pure/code-driven. Atlas agrees that operations remain deterministic and permits an LLM only for email/Slack drafting, executive summaries and report prose. Therefore “more LLM in Layer 5” will not repair wrong targets, missing cadence, card lifecycle drift or unsafe delegation. Those require contracts and wiring.

The Proposed design keeps 0% model authority over execution and uses a model only after a valid execution exists, when human-facing prose has material value. A whole-layer percentage is misleading; eligible-event and token budgets are stated per task.

## Current, Atlas, and Proposed placement

| Task | Current path | Atlas policy | Proposed eligible rate | Deterministic pre-gate | Deterministic post-gate | Model forbidden authority | Cost control |
|---|---|---|---:|---|---|---|---|
| Interpret Layer 4 decision | Pure `interpret.py` | Never model execution interpretation | 0% | Typed decision and provenance | Exact replay/hash | Goal, target, priority | No call |
| Plan actions/dependencies | Pure `planning.py` | Never execution planning | 0% | Valid decision, action lexicon, bounds | Dependency graph and max-step validation | Steps, dependency, deadline, approval | No call |
| Assign owner | Rules in `assignment.py` | Semantic work owner; no model route | 0% | Roleful owner facts, active seats | Identity/policy validation | Owner, approver, escalation target | No call |
| Choose communication plan | Rules in `communication.py` | Routing/recipient/timing forbidden; Atlas places concrete route in 5.2 | 0% | Ratified ownership policy, presence/policy facts | Route validator and audit trace | Recipient, channel, interrupt, timing | No call |
| Validate execution | Typed `validate.py` | Never execution validation | 0% | Authority, expiry, coverage | Deterministic issue codes | Permission or validity | No call |
| Monitor completion | Event rules in `monitor.py` | Never monitoring | 0% | Scoped success predicate | Provenance/freshness/conflict | Whether completed/succeeded | No call |
| Reminder/escalation decision | Sweep and ladder rules | Never reminders or escalation | 0% | Cadence, deadline, authority, owner | Rate/policy/idempotency gates | Whether/when/whom to remind | No call |
| Reminder copy | Current deterministic formatter/summary | LLM allowed for Slack/email prose | 10–30% of already-approved non-template reminders, default off | Valid execution, approved send intent, grounded fact allowlist, no missing semantic target | Schema, claim-to-source check, banned-new-fact check, length/PII policy | Route, urgency, cadence, consequence facts | One cached draft per execution-state hash |
| Customer/partner draft | No native Executive model call | LLM allowed for email drafting | 20–50% of explicitly requested drafts; never auto-send | Approved action, recipient role, channel policy, source snippets, four-brain voice snapshot | Grounding citation map, constraints, human/agent approval | Send decision, promise, price, deadline, legal claim | Small output cap; cache; no retry on policy failure |
| Executive status summary | Current `summary.py` is deterministic | LLM allowed for executive summaries/reports | 0–25% when many validated executions need narrative compression | Fixed execution rows and governed metrics | Number equality, omission/conflict check, link to rows | Counts, status, confidence, ROI | Batch many rows into one bounded call |
| Outcome narrative | Collector stores structured outcomes | Report generation allowed; learning truth belongs later | 0–20% for prose after outcome ledger exists | Verified outcome and attribution labels | Preserve achieved/unproven/counterfactual labels | Outcome, attribution, learning promotion | Generate only on demand |
| Agent instructions | 501 handoff; no governed path | Drafting may assist prose, never permission | 0% until executor protocol is green; then optional 10% phrasing | Approval token, exact tool/action scope, one lease, hard constraints | Machine schema and signed payload must be model-independent | Tool scope, approval, executor, idempotency | No call before handoff availability |

## Call contract for every allowed LLM use

| Dimension | Required contract |
|---|---|
| Input | Only immutable execution facts approved for the audience; never a person/node dump |
| Trigger | Explicit draft request or deterministic decision that human prose is needed; default templates remain available |
| Cache key | Tenant boundary + execution semantic hash + execution state/version + audience role + prompt/model version + language/tone policy |
| Output schema | Draft text plus source-field citation map; no inferred recipient, date, amount, promise or action |
| Retry | At most one transient retry; validation failure falls back to deterministic copy or review, not a second creative attempt |
| Timeout | Delivery/execution continues in waiting/defer; no unbounded scheduler wait |
| Logging | Model/version, prompt version, input hashes, token counts, latency, validation result, fallback reason; no raw secret logging |
| Retention | Same visibility and retention as the ExecutionObject evidence; tenant isolation enforced before the call |
| Approval | Drafting does not approve or send. Restricted/high-consequence text stays review-only |
| Evaluation | Groundedness, unsupported-claim rate, edit distance, correction burden and useful-action outcome—not “sounds executive” |

## Cost model

Do not hard-code a vendor price in architecture. Prices and models change; the budget controller uses configured input/output unit rates.

`event_cost = input_tokens × configured_input_rate + output_tokens × configured_output_rate`

`monthly_cost = Σ event_cost + retry_cost`, where retry count is bounded and cache hits cost zero model calls.

| Cost driver | Unsafe pattern | Proposed ceiling | Operational metric |
|---|---|---|---|
| One call per sweep | Rewrites same reminder every scheduler run | One draft per state/cadence hash | Calls per unique execution state |
| Full history prompt | Sends person-wide corpus repeatedly | Curated grounded fact envelope only | Input tokens per draft |
| Long prose | Produces essays/cards hiding the action | Channel-specific output cap | Output tokens and human edit time |
| Creative retries | Re-prompt until validator passes | One transient retry; validation failure uses template/review | Retry rate and fallback rate |
| Per-row summary calls | N executions create N calls | One batched summary with row IDs | Calls per executive brief |
| Always-on premium model | Pays high cost for simple wording | Template first; configured small drafting model; escalate only through evaluated policy | Cost per accepted draft |
| Duplicate delivery | Same execution rendered per channel with no reuse | Base grounded draft cached, deterministic channel adaptation where possible | Draft reuse ratio |

## Budget and degradation policy

| Budget state | Behavior | Must remain unchanged |
|---|---|---|
| Healthy | Eligible drafting/summarisation calls allowed | Execution plan, route, approval, lifecycle |
| Near limit | Prefer cached draft and deterministic templates | Evidence and action meaning |
| Exhausted | No model call; deterministic copy or review | No silent suppression of important work |
| Provider unavailable | Timeout once, record reason, continue with template/defer | No model-generated authority reconstructed locally |
| Validator rejects output | Discard text, keep trace, template/review | Never partially merge unsupported prose |

## Why an “80% LLM Layer 5” target is wrong

Atlas’s weight 80 applies to **drafting and summarisation work**, not 80% of Executive authority. The operational layer should remain close to 100% deterministic by decision count. A model may perform most of the prose work on the minority of executions that need a bespoke draft, while 0% of owner selection, route, cadence, score, permission, dependency, completion and outcome truth comes from the model.

## Acceptance gates

1. A replay with the model disabled yields identical ExecutionObject, owner, route decision, lifecycle and outcome semantics.
2. Every draft sentence maps to approved input fields; unsupported factual claim rate is zero on HKS fixtures.
3. Cache replay makes zero calls for identical tenant/execution-state/prompt versions.
4. Budget exhaustion produces a truthful deterministic template or review, never missing or changed work.
5. The Theresa, Boardy, card-action and agent-handoff failures remain blocked until their deterministic prerequisites are fixed; model prose cannot turn them green.
6. Pilot reporting shows token/call/latency/edit metrics and business outcome separately.

## Verdict

Current no-model Executive operations are architecturally correct. Proposed LLM use is narrow, measurable and optional: grounded human prose after the plan, never the plan itself. Cost optimisation comes from eligibility gates, small fact envelopes, caching, batching, output caps and deterministic fallback—not from sacrificing authority checks.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C1.L-contract.V0.U01)
include "../03-Current-Successes-Failures-and-Expected-Behavior/README.md" (M4.C1.L-data.V0.U01)
-->

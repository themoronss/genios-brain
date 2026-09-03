# Golden Replay 08 — Governed Agent Handoff and Origin-Loop Prevention

**Scenario:** an authoritative GeniOS decision is approved for execution by an external agent. The agent receives a scoped task, calls a tool or drafts/sends material, and returns events/results that re-enter GeniOS. The system must execute exactly once, correlate the result to the originating action, and prevent its own agent-generated events from becoming new independent “intelligence.”

## Evidence boundary

**[CODE] Current proof at `harsh/mvp@b739bd5`:** `api/intelligence_routes.py:897-909` keeps the governed external-agent handoff route unavailable with HTTP 501. Separately, `deliver/actions.py:80-109` handles the card-side `do_it_myself` action by updating card/signal state rather than advancing a linked Executive execution/action/outcome. These code paths prove the disabled handoff and the parallel card-state behavior; they do not prove a live lease, signed result, origin guard, exactly-once provider effect or loop prevention.

**[MODELLED] Required behavior:** the approval token, fenced executor lease, signed result, origin identifiers, idempotency rules, mutation matrix and Layer 1–Layer 7 flow below are the proposed acceptance contract for future enablement. They are not `[CODE]` implementation claims, not `[TEST]` results and not evidence that a production agent workflow already exists. Passing the current 501 behavior proves fail-closed availability only; enabling the integration requires every modelled assertion to become executable proof.

## Business subject and base fixture

The **Business subject** is the original relationship/opportunity and exact unresolved action—not the agent, integration account, webhook sender or generated message. The **[MODELLED]** base fixture contains:

- a current DecisionObject with named target, selected action, rejected alternatives, constraints, expiry, Completion and outcome window;
- an ExecutionObject/action requiring Rohit’s approval before an agent may draft/send;
- one approved external agent with a narrow tool/data scope;
- an idempotency key and revocable executor lease;
- a signed result/event containing `origin_execution_id`, `origin_action_id`, `origin_attempt_id`, `actor_type=agent`, provider task/message id and status.

## Current failure

**[CODE]** The governed agent handoff route currently returns HTTP 501. That is the only proved current handoff behavior in this replay and is safer than claiming a workflow was dispatched. **[MODELLED]** The acceptance design treats prompt/webhook dispatch without approval, a single fenced executor, signed result and origin contract as unsafe because it could permit duplicate execution, blind retry, scope expansion or recursive self-generated work. Those are failure probes to test, not claims that the disabled endpoint performed them.

**[CODE]** Layer 5 also has a parallel card path: “I’ll do it” can change card/signal state without progressing the linked action, execution or outcome in that handler. **[MODELLED]** The required integration replay therefore refuses enablement until the card command and Executive lifecycle converge on one execution truth.

## Expected behavior

**[MODELLED]** Keep the endpoint disabled until the full replay is green. Once enabled, approval atomically creates one fenced, expiring lease for one action and idempotency key. The agent receives only the selected action, lawful context, accepted constraints, allowed tools, approval scope, stop conditions, expected result schema and Completion predicate—never unrestricted Company/Expert Brain data.

Every returned event is signature-verified and correlated to the originating execution/action. Agent-origin echoes update attempt/execution/delivery state; they do not create new business situations or independent human evidence. Only a genuinely external counterparty/world event can satisfy Completion or trigger a fresh decision. One approved action yields at most one provider effect, one canonical result and one learning exposure/outcome chain.

## Prohibited behavior

- Do not treat prompt text as approval, permission or executable policy.
- Do not allow two agents/workers to hold authority for one action.
- Do not retry blindly after an unknown provider timeout.
- Do not allow the agent to change target, action, content facts, channel, approval boundary or success definition.
- Do not strip or ignore origin/executor metadata when events re-enter capture.
- Do not turn the agent’s own generated message/result into a new human request or card.
- Do not count agent result, transport acceptance or duplicate webhook as business Outcome.
- Do not share Expert Brain internals or unrelated company/client context.

## Exact Layer 1–Layer 7 contract

| Layer | Required responsibility | Required output/receipt | Fail-closed result |
|---|---|---|---|
| **Layer 1 — Knowledge** | Authenticate webhook/provider source; preserve actor type, origin execution/action/attempt, provider ids, signature, content version, recipients and visibility/use | Immutable event receipt explicitly labelled agent-origin, provider-result or external-counterparty; stable dedup key | Park/quarantine missing/invalid origin or signature; agent echo cannot become ordinary qualified human signal |
| **Layer 2 — Context Intelligence** | Correlate agent-origin event to exact action/relationship without adding independent evidence; distinguish external reply from agent echo | BSO/lifecycle update references origin and effect; no new situation for duplicate/echo; external world response retains separate actor/source | Review source on ambiguous correlation; suppress recursive/duplicate situation |
| **Layer 3 — Domain Expertise** | Share applicable capability constraints/output contract and permitted four-brain selections only; preserve exclusions and purpose | Scoped expertise receipt/version embedded in handoff; no corpus/IP dump and no permission widening | Block when capability/brain snapshot is stale, unsupported or outside agent scope |
| **Layer 4 — Reasoning** | Freeze selected action, alternatives/rejections, stakes, expiry, target and Completion; re-reason only on authoritative new world evidence | Decision id/hash and machine-checkable constraints; agent cannot modify winner/confidence | `DEFER`/Blocked if decision expired/revoked or action cannot be expressed safely |
| **Layer 5 — Executive** | Verify approval; atomically grant one fenced lease; enforce idempotency, dependencies, scope, cancellation and result schema; own lifecycle | Execution/action/approval/lease/idempotency/attempt receipts; one canonical executor and terminal/unproven state | Keep 501 or return blocked; no task dispatch without every receipt |
| **Layer 6 — Delivery** | Materialize approved exact payload/tool call; revalidate audience/authority; reconcile accepted/delivered/unknown before retry | Provider id, fence/idempotency, attempt chronology and canonical DeliveryResult | Defer/reconcile unknown attempt; never blind retry or route fallback outside approval |
| **Layer 7 — Learning** | Join one decision exposure, one canonical execution, delivery, external Completion and outcome; separate agent quality from decision quality | Deduped causal ledger keyed by origin/action; agent echoes excluded as independent support | No promotion/double counting; no preference from agent-generated activity |

## Handoff payload contract

| Field | Required value | Rejection condition |
|---|---|---|
| `execution_id`, `action_id`, `decision_hash` | Current authoritative parent chain | Missing, stale, revoked or mismatched |
| `approval_token` | Signed scope, approver, expiry, allowed effect | Absent, expired, replayed or scope mismatch |
| `lease_id`, `fence_token` | One current executor ownership | Lower/duplicate fence or another live holder |
| `idempotency_key` | Stable per external effect | Missing or reused for different payload |
| Business subject/target | Exact entity, relationship/thread and lawful recipient | Ambiguous or agent-modified |
| Action/payload hash | Frozen selected semantics/content version | Agent proposes material semantic change |
| Allowed tools/data | Minimal allowlist and visibility/purpose | Broader access request |
| Stop/cancel conditions | Revocation, expiry, dependency/policy change, ambiguous effect | Agent cannot observe/enforce them |
| Completion predicate | External observable result, not tool success | Missing or defined as agent response only |
| Result schema/signature | Status, provider ids, effect hash, timestamps, errors | Invalid signature/schema/origin |

## Mutation matrix

| Mutation | Expected behavior | Prohibited behavior | Outcome / pass evidence |
|---|---|---|---|
| Two agents request same action simultaneously | Atomic lease grants one; other receives conflict/no authority | Both execute | One lease/fence and at most one provider effect |
| Same dispatch/result webhook delivered twice | Idempotent no-op after first canonical receipt | Two executions/outcomes | One action/result/learning row |
| Provider times out after accepting send | Mark attempt unknown; reconcile by provider/idempotency before retry | Blind retry duplicate message | One provider message or unresolved fail-closed state |
| Approval revoked before tool effect | Fence invalidates; agent stops; no delivery | Continue from cached token | Cancellation/revocation receipt, zero effect |
| Approval revoked after accepted provider effect | Preserve actual effect; cancel later work and monitor result | Pretend send did not occur or send again | One accepted effect plus truthful state |
| Decision expires while queued | Block dispatch and rebuild/reason on current state | Execute stale decision | No provider call |
| Agent asks to change recipient/channel/content | Return blocked/reapproval request | Agent self-expands scope | New decision/approval required |
| Origin metadata absent or signature invalid | Quarantine/Review source | Treat as human email/request | No graph/action mutation |
| Agent’s outbound message is ingested from Gmail | Link as execution/delivery effect; do not generate a new “reply/send” loop | Recursive card/workflow | Origin lineage suppresses self-trigger |
| External counterparty replies to agent-sent message | Capture as external evidence; correlate to exact relationship/action; evaluate Completion | Classify as agent echo or close unrelated work | One scoped completion/outcome candidate |
| Agent completes draft but approval was send-only/draft-only mismatch | Reject effect outside token scope | Use draft success as send completion | Correct waiting/blocked lifecycle |
| Agent returns success but provider has no receipt | `completed_unproven`/unknown; reconcile | Call business action completed | No positive learning until verified |
| Same result arrives through agent webhook and provider webhook | Merge receipts under origin/effect id | Count independent support twice | One canonical effect with two provenance receipts |
| Agent action produces a new legitimate external issue | Create new situation only from external actor/world change with new causal parent | Suppress all future evidence because origin exists | New scoped BSO excludes pure agent echo |

## Loop-prevention invariants

1. Every generated artifact/event carries immutable origin chain and `actor_type` through capture, graph, decision, execution, delivery and learning.
2. Agent-origin content can update the originating action but cannot independently satisfy support/population or create a recommendation about itself.
3. External provider effects are keyed by approved payload hash + idempotency key; retries never create a second semantic effect.
4. A fresh decision requires an external world-state change, human correction or explicit re-evaluation—not a GeniOS/agent echo.
5. One action has one live lease, one canonical result and one outcome chain; multiple receipts may corroborate it without double counting.
6. Revocation/expiry fences both pending dispatch and late result authority.

## Replay assertions

- With handoff disabled, the base request remains HTTP 501/Blocked and no external call occurs.
- With the future governed path enabled in replay, all concurrency/retry mutations converge to one effect or a typed unresolved state.
- Removing any approval, lease, idempotency, origin, signature, target or Completion field deterministically blocks execution.
- Agent-generated events create zero independent cards and contribute zero independent learning support.
- A verified external reply closes only the matching action and remains distinct from delivery success and revenue attribution.

## Outcome

The replay passes first by remaining disabled today. Future enablement passes only when **one approved ExecutionObject produces one fenced workflow, at most one external effect, one signed/canonical result, no recursive intelligence loop, and one reconciled external Completion/outcome chain**. Agent performance and GeniOS decision quality are measured separately; neither is learned from echoes or duplicate transport receipts.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../08-Cross-Layer-Synthesis/04-Gold-Standard-Intelligence-Contract.md" (M5.C1.L-contract.V1.U01)
include "../08-Cross-Layer-Synthesis/08-HKS-and-Scenario-Responsibility-Matrix.md" (M5.C1.L-integration.V1.U01)
include "../05-Layer-5-Executive/06-Improvements-Acceptance-and-Metrics/README.md" (M4.C1.L-interface.V0.U01)
-->

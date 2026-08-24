# Layer 6 Delivery (Atlas 5.2) — Current Successes, Failures, and Expected Behavior

## Evidence scope

Current proof is pinned to `harsh/mvp@b739bd5`. A fresh targeted command across 15 Delivery/bridge/outbox test files produced `192 passed, 11 skipped, 1 warning`; the skips are not passes and this does not prove production traffic. Call-site search found maintenance invoking `run_distribution`, but no production caller of v2 `orchestrator.resolve`, `spine.materialize`, or `spine.claim_due`.

## Required comparison

| Component or scenario | Atlas expected | Current proof | State | Verified success | Current failure | Loophole | What should have happened | Improvement | Acceptance evidence |
|---|---|---|---|---|---|---|---|---|---|
| Live composition | ExecutionObject enters canonical DeliveryObject worker | Maintenance calls legacy `run_distribution`; v2 resolve/materialize/claim appear only as definitions/tests | Wired legacy; Present v2 | Real cards, digests and reminders reach durable outbox path | Atlas-shaped v2 is not runtime authority | Presence of rich modules/API can be read as operational completeness | One canonical materializer/worker consumes valid execution events | Wire v2 end-to-end or explicitly retire/merge it | Runtime trace names v2 delivery id from execution through adapter/result |
| Executive bridge | Durable message from Layer 5 reminder event | `execution.reminded` scan, synthetic key, grounded formatter, signal-card linking, maintenance call | Wired | Recorded reminder can actually leave the building; repeated scan dedupes | Event and outbox enqueue are separate transactions | Event can wait until later scan though system may appear delivered-ready | Transactional outbox/change stream guarantees durable immediate materialization | Consume in same transaction boundary or reliable offset log | Crash between event and enqueue recovers with measured latency, no duplicate |
| Grounded reminder copy | Delivery adds no unsupported facts | Bridge uses only Layer 5 event fact corpus; Slack adapter adds punctuation/icon | Wired | Structural constraint prevents graph lookup/invention in adapter | Wrong upstream facts remain wrong | “Grounded” can be mistaken for “correct” | Reject unresolved semantic target before execution/delivery | Carry target/thread/authority contract | Boardy/person-dump fixture is suppressed, not prettified |
| Admission gate | SEND/DEFER/SUPPRESS with restrictive composition | `DeliveryDecision`, gate, preferences, quiet hours, rate/budget; live drain calls `admit` | Wired | DEFER does not spend retry; SUPPRESS/CANCEL/FAIL remain distinct | Full v2 routing context is not used live | Safe gate can deliver semantically wrong intelligence | Gate only valid bounded execution; retain typed result | Make canonical v2 input mandatory | Every outcome has gate unit/reason and no unjudged adapter call |
| Card revalidation | Recheck exact authority immediately before send | Live card path locks graph, signal, reasoning run/hash, pack/config and card state through POST | Wired | Revoked card is cancelled before Slack send | Underlying baseline authority tests still expose latest-version gap upstream | Strong SQL can still act on wrong bounded situation | Fix latest authority and semantic state before enqueue | Unified authority service | Stale/superseded fixtures never call adapter |
| Reminder revalidation | Re-evaluate live commitment/current routing at send | Bridge send check asks execution open and `expires_at > now` | Wired, shallow | Closed/expired commitment is cancelled | Semantic authority can change before next Executive sweep | “Open row” stands in for full current meaning | Revalidate fenced execution authority/version and routing at dispatch | Canonical authority token/version | Completion arriving between sweep/drain causes zero send |
| Digest freshness | Never send yesterday’s revoked projection | Outbox stores intent; drain rebuilds digest from current Executive summary | Wired | Stale queued payload bytes are not used | Summary correctness still depends on upstream state | Current projection can be current-but-wrong | Require same semantic/authority gates as source commitments | Receipt-linked digest entries | Each digest item resolves to current execution or observation |
| Retry and failure | Bounded retry for failure only | Legacy backoff 5/30/120/720 minutes; terminal state; per-org isolation | Wired | Broken adapter cannot block all tenants indefinitely | Timeout ambiguity has no provider message id reconciliation | Retrying after provider accepted but response lost may duplicate | Unknown attempt + provider id/idempotent effect reconciliation | Use v2 fenced attempt manager on live path | Timeout-after-accept fixture yields one external message |
| Durable worker | SKIP LOCKED, lease/fence, recover unknown attempts | Legacy SKIP LOCKED and next-attempt claim; v2 spine has lease/fence/recovery | Wired legacy / Present v2 | Concurrent legacy drains avoid selecting same row in one pass | v2 stronger fencing is not live-composed | Legacy five-minute bump is not ownership proof after long/ambiguous call | One v2 fenced worker and settled attempt record | Replace parallel drain semantics | Worker crash/reclaim suite has one legal attempt sequence |
| Audience/visibility | Resolve recipient now against inherited visibility | v2 resolver accepts `can_view`; legacy uses stored recipient/assignee and gate policies | Present v2; partial legacy | Recipient preference can suppress/hold live Slack | Late ACL resolver is not proved in live route | Stored assignee may be valid structurally but stale/unauthorized semantically | Re-resolve or cryptographically validate current recipient authority at send | Ratify late/frozen routing and enforce ACL | Visibility revoke-after-queue produces suppression, no adapter call |
| Presence/routing fallback | Context-aware surface and lawful ladder | Presence/routing modules and route ladder fields exist | Present/Tested modules | Pure routing logic has fresh test coverage | Live sender uses one Slack adapter and no v2 ladder worker | Registry “engine_ready” may be read as route available | Operational means configured, credentialed, implemented and exercised | Capability truth linked to adapter health | Capability endpoint and actual send probe agree |
| Adapter breadth | 11 delivery unit classes | `units.py` enumerates 11; live `get_channel` returns Slack only; email engine false | Present registry; Wired Slack | Capability API explicitly separates engine-ready/operational | Inline email/CRM/mobile/agent promise is not operational | Configured generic channel may look equivalent to built adapter | Report exact adapter/surface readiness, never aggregate “11 active” | Per-unit conformance and health | Each operational=true unit passes a real contract test/receipt |
| Tracker/receipts | Canonical DeliveryResult lifecycle and attempts | v2 tracker and result/event/attempt APIs; legal chronology/idempotency | Present/API-wired | Illegal transition and impossible time are rejected | Legacy rows are not proven to populate canonical v2 lifecycle; client actor is generic | An accepted/executed client receipt can be mistaken for Executive/business result | Authenticated actor/device/provider receipt joins execution action | Typed result and receipt trust policy | Click/receipt replay cannot close execution without action evidence |
| Analytics | Impression-based engagement/fatigue plus result latency | Counts delivered/viewed/accepted/executed/ignored and intrusive impressions | Present/API-wired | Undelivered rows do not dilute view rate | No universal live receipt/provider/business-outcome feed | A high execute rate can be sold as business lift | Keep transport, engagement, execution and business outcome separate | Join DeliveryResult to ExecutionOutcome/counterfactual | ROI report excludes unjoined engagement rows |
| Expiry/rebuild | Valid work resurfaces; obsolete work stays suppressed | `a90ff66` card lifetime/scheduler change; `b739bd5` expired-card exclusion in open-signal check | Wired upstream | Expired projection no longer permanently blocks valid signal | 3,650-day default and unresolved signal can preserve stale semantics | Rebuild can reproduce same wrong card | Re-run roleful current-state reduction before projection | Situation version/supersession gate | Resolved variant never rebuilds; valid variant rebuilds once |
| Output contract | One typed DeliveryResult crosses boundary | API SQL projection/results/events; `DELIVERY_RESULT_VERSION` constant | Present projection | Customers/operators can inspect rows and events | No explicit `DeliveryResult` class found | API shape may drift separately from contract/storage | Define frozen typed result and map every terminal/receipt path | Contract-first serializer/version migration | Round-trip/property tests cover every lifecycle and failure |

## Verified successes

1. `run_distribution` is genuinely composed in maintenance; this is not a dead package.
2. Layer 5 reminder events are bridged, deduped and linked to cards; formatting is grounded and no graph lookup can invent new claims.
3. Live cards receive unusually strong send-time authority revalidation, and queued digests are reconstructed from current state.
4. Gate failure is fail-closed, deferral is correctly not a retry, quiet hours/rate/budget/preferences are composable, and per-org enqueue failure is isolated.
5. The v2 modules contain real deterministic contracts for audience, presence, routing, durable materialization, claims, lifecycle receipts, analytics and capability truth; the targeted test run confirms substantial behavior while disclosing 11 skipped cases.

## Current failure chain

The founder can still see low-value or wrong intelligence because Delivery faithfully renders what it receives. The screenshots’ person/node dumps and generic action headlines are upstream semantic failures. Delivery then uses a legacy card/reminder path whose action receipt is not welded to Executive completion. Meanwhile, the stronger v2 DeliveryObject/worker exists alongside rather than governing the live send. This is why improving copy or adding more channels alone cannot solve the quality problem.

## Should have happened: concrete scenarios

| Situation | Current visible risk | Should have happened | Evidence needed |
|---|---|---|---|
| Theresa update becomes eligible | Generic stale reminder through Slack or no cadence-aware delivery | Current role/cadence/materiality validated; exact recipient and least-disruptive surface; one result joined to outcome | Consent/invitation, prior sends, material milestone, target/thread, route/policy, receipts |
| Boardy introduced human | Connector/person dump can be rendered | No send until target-specific execution exists; then deliver to introduced human/thread | Connector edge, target identity, thread and open action |
| User accepts card | Card action and delivery receipt can move without Executive plan | Record view/accept, idempotently claim linked execution action, keep completion separate | Delivery id, execution/action id, actor, command id, later completion event |
| Reminder queued, reply arrives | Open/unexpired row may remain until next sweep | Dispatch revalidation observes completion/version and cancels | Scoped completion receipt and current execution authority token |
| Provider posts then times out | Legacy bounded retry may send again | Attempt becomes unknown; reconcile provider id/idempotency before retry | Provider request/id, fence token, settled status |

## Evidence and claim limits

| Evidence | Supports | Does not support |
|---|---|---|
| Maintenance call to `run_distribution` | Wired legacy composition | v2 worker or production success |
| 192 passed / 11 skipped selected tests | Tested covered behavior | Skipped DB/integration cases, deployment, customer value |
| Capability registry | Honest engine/operational vocabulary | Eleven working adapters |
| Slack `200` and delivered row | Transport accepted by current adapter | Human viewed, acted, or business outcome |
| Client lifecycle endpoint | Legal/idempotent receipt shape | Trusted external execution or ROI by itself |
| `b739bd5` rebuild change | Queue can recover after expired projection | Semantic freshness or completion intelligence |

## Verdict

There is Verified success in the live legacy safety path and the v2 component suite. The dominant Current failure is dual architecture: stronger v2 materialization, routing, fencing and result semantics are not the sender invoked by maintenance. Expected behavior requires one canonical path, exact semantic target, truthful operational channels, receipt trust, and a joined Executive lifecycle before Delivery can be considered customer-ready.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../01-Architecture-and-Atlas-Delta/README.md" (M4.C2.L-contract.V0.U01)
include "../../00-Methodology/03-Source-and-Commit-Manifest.md" (M1.C1.L-data.V0.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->

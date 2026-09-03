# Layer 6 Delivery (Atlas 5.2) — Architecture and Atlas Delta

## Contract

Layer 6 in this update is the current `deliver/` package, corresponding to Atlas Layer 5.2. Its one job is to materialize an already-authorized execution safely across a surface: right eligible audience, lawful destination, humane time, controlled format, durable send, bounded failure handling, and receipt-backed result. It must not create intelligence, repair a wrong target, change priority, or treat transport engagement as business success.

Current code has **two delivery paths** that must not be conflated:

1. The production-composed legacy path: `run_distribution` → enqueue cards/digests/Executive reminders → legacy `delivery_outbox` drain → gate → authority revalidation → Slack adapter → row/card event.
2. The v2 Atlas-shaped control plane: rich `DeliveryObject`, audience/presence/routing orchestrator, durable materialization/fenced claims/attempt recovery, lifecycle tracker, analytics, capability API, inbox and dead letters.

The first path is Wired from maintenance. The second is materially Present and selected components are Tested, but repository call-site search finds no production caller of `deliver.orchestrator.resolve`, `deliver.spine.materialize`, or `deliver.spine.claim_due`. Therefore the v2 path must not be described as the live sender.

## Atlas versus Current code

| Responsibility | Atlas expectation | Current code proof | State | Gap or consequence |
|---|---|---|---|---|
| Input boundary | Valid hash-verified ExecutionObject | Executive reminder bridge reads `execution.reminded`; card/digest paths also enqueue independently | Wired, mixed inputs | Not every delivery is materialized from the rich execution boundary |
| Gate | Closed SEND/DEFER/SUPPRESS set; most restrictive wins | `contracts/delivery.py`, `gate.py`, quiet hours/preferences/budget/rate rules; legacy drain uses `admit` | Wired in legacy path | Gate correctness cannot repair upstream wrong meaning/target |
| Durable outbox | Decision-to-send and queued row commit together; worker claims later | Legacy enqueue/outbox is durable and deduped; v2 `spine.materialize` atomically adds delivery+event | Wired legacy; Present v2 | Executive event and legacy outbox are written in separate transactions; recoverable scan, not Atlas atomicity |
| Audience | Resolve recipient now against visibility | v2 orchestrator has ACL callback and role resolution; legacy card/reminder uses stored assignee/recipient | Present v2; legacy frozen | v2 audience resolver is not on live distribution call path |
| Presence/context | Route by current user activity and context lease | Presence context/resolver and API probes exist | Present | No proof live sender calls v2 resolver before each send |
| Route ladder | Lawful channel fallback, reevaluated at each rung | v2 routing and route ladder fields exist | Present | Legacy sender has one registered human adapter and bounded retry on that adapter, not v2 fallback execution |
| Adapter coverage | 11 target classes | `units.py` registers 11 capability classes and reports engine-ready versus operational truth | Present registry | Only Slack incoming webhook is implemented in live channel registry; email explicitly engine-not-ready |
| Dedup/fencing | At-least-once with idempotent effects, fenced worker and provider reconciliation | Legacy unique `(org, card, channel)` + SKIP LOCKED; v2 dedupe key, claim lease, fence token and unknown attempt recovery | Wired legacy / Present v2 | Live adapter lacks provider message-id reconciliation; timeout ambiguity can retry a duplicate |
| Revalidation | Recheck policy and authority immediately before send | Legacy card path locks current graph/pack/card authority; reminders check open + not expired; digests rebuild current payload | Wired | Reminder check relies on prior Executive sweep and does not recompute full semantic authority at send gap |
| Tracker | Transport and engagement lifecycle with append-only receipts | v2 tracker validates chronology/transitions/idempotency; receipt API and result API exist | Present/API-wired | Legacy delivered rows and v2 lifecycle are not proven one canonical live lifecycle |
| Analytics | Delivery, views, accept, execute, ignore, fatigue and latency | `analytics.py` counts real impressions and exposes engagement/fatigue API | Present/API-wired | Client/provider receipts and business outcome joins are incomplete; transport analytics is not ROI |
| Output boundary | Typed DeliveryResult, including suppressed/failed attempts and metrics | API projects result rows/events; constant `delivery-result.v2` exists | Present projection | No explicit typed `DeliveryResult` class found; boundary is SQL/API projection rather than one enforced contract |
| Expiry/rebuild | Obsolete projection never blocks valid current work | `b739bd5` allows a still-open signal to receive a new card after old card expiry | Wired upstream projection fix | Does not determine semantic relevance or resolve already-completed work |

## Atlas ownership contradiction

| Policy question | Atlas | Current code | Risk | Required ratification |
|---|---|---|---|---|
| Recipient | Delivery resolves concrete recipient at send from semantic audience | Executive stores concrete assignee; legacy bridge copies it | Stale reassignment/presence/visibility handling differs by path | Choose late binding or frozen routing and migrate explicitly |
| Channel | Delivery owns channel/destination/fallback | Executive stores channel/channel class/interrupt; bridge filters/copies it; v2 can independently route | Dual policy authorities can disagree | One owner; the other validates, never silently overrides |
| Timing/interrupt | Delivery decides present moment and policy | Executive decides interrupt intent; legacy gate decides whether moment permits | This split can be coherent only if intent versus admissibility is documented | Ratify stable intent in Executive and current admissibility in Delivery, or adopt Atlas wholly |

This document does not silently resolve the contradiction. Atlas specifically says concrete `channel_id`/`interrupt` in ExecutionObject are audit hints, while current layer map treats them as a frozen plan. A formal architecture decision and replay/migration are required.

## What is genuinely working

- The legacy bridge is real: it consumes only `execution.reminded`, formats from Layer 5’s grounded fact corpus, creates a deterministic synthetic key, links commitments to cards by signal, and is invoked during distribution.
- Deferral is correctly distinct from transport failure; it moves `not_before`/`next_attempt_at` without consuming retry budget. Suppression and cancellation remain distinct.
- Card authority is revalidated under current graph/reasoning/config/pack locks before the Slack POST; queued digest bytes are replaced by a current executive projection.
- Bounded retry, tenant isolation, SKIP LOCKED claims, failure state and delivered card events are implemented in the legacy path.
- The v2 contract has rich delivery lineage, routes, priorities, lifecycle, attempts, receipts, dead letters, analytics and capability truth. A fresh selected delivery suite produced `192 passed, 11 skipped`; skips are disclosed and are not passes.

## Critical gaps

| Gap | Exact scope | Why it matters |
|---|---|---|
| v2 not in live composition | No production call site found for v2 resolve/materialize/claim | Atlas-shaped objects can be excellent but cannot govern what customers receive |
| Single real human adapter | Channel registry returns only Slack webhook | “11 units” is capability structure, not 11 operational destinations |
| Non-atomic Executive bridge | Reminder event commits in Layer 5; outbox row appears in later Layer 6 scan | Crash is eventually recoverable, but Atlas same-transaction guarantee is unmet |
| Reminder revalidation depth | Send-time check is execution open and unexpired | Semantic authority can change between sweeps without immediate close |
| Card/action completion gap | Delivery can expose/record a click, but legacy action does not progress ExecutionObject | Accepted/executed lifecycle and business completion can disagree |
| Agent handoff 501 | Intended governed handoff is unavailable | Agent/API capability labels must not imply executable workflow |
| Semantic target/person dump | Delivery receives wrong connector/person-wide projection | Safer transport delivers the wrong intelligence more reliably |
| Receipt/value gap | API can accept client lifecycle receipts; provider identity/business outcome attribution are not universally welded | Open/click/execute analytics cannot prove revenue or customer value |

## Freshness nuance

Commit `a90ff66` bounded maintenance and made housekeeping card expiry 3,650 days, meaning cards normally leave by user action or authoritative decision expiry. Commit `b739bd5` prevents an expired card from permanently blocking a new projection for a still-open signal. Delivery should preserve that liveness repair, but it must not call it freshness intelligence: a rebuilt Theresa or Boardy card still needs a current roleful situation and completion check.

## Verdict

**Framework-ready, not live-ready.** The wired legacy Slack/outbox/gate path has meaningful delivery safety, and the v2 Atlas-shaped control plane is extensive and selected tests pass. The central Gap is composition: v2 resolution, materialization and fenced worker are not the runtime sender; operational channel breadth is narrow; DeliveryResult is not a single typed boundary; and visible action/receipt semantics do not yet close the Executive lifecycle. Resolve those joins before claiming Atlas 5.2 operational completeness.

<!-- Build dependency receipts: documentation composition only; not runtime wiring or outcome proof.
include "../../00-Methodology/02-Layer-Numbering-and-Semantic-Map.md" (M1.C1.L-contract.V1.U01)
include "../../00-Methodology/05-Status-Legend-and-Audit-Method.md" (M1.C2.L-logic.V0.U01)
-->

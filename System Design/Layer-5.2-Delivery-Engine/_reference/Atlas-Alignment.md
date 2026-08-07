# Atlas alignment · Layer 5.2 Delivery Engine

The Atlas names this layer **Layer 5.2 · Delivery Engine** and asks: “How should this execution
reach the world?” The implemented boundary is `ExecutionObject → DeliveryResult`. The delivery
control plane may resolve current transport details, but may not invent intelligence or revise the
approved execution.

## Contract alignment

| Atlas concern | Current implementation |
|---|---|
| Input | Layer 5 `ExecutionObject` only on the active materialization path |
| Delivery authority | Stored execution identity/liveness; card projection alone has none |
| Internal transport object | `DeliveryObject` v2 projected into one logical outbox row |
| Output | `DeliveryResult` v2 plus append-only attempts/lifecycle events |
| Layer 5 authority retained | Commitment, work owner, actions, deadline, business priority and execution lifecycle |
| Layer 5.2 authority | Current audience/recipient, destination, channel, format, timing, interruptibility, retry and failover |
| Layer 6 handoff | Typed delivery lifecycle facts for learning; no delivery-control authority |

The active materializer handles initial execution and `execution.reminded` events by reconstructing
and identity-checking the stored `ExecutionObject`. V2 freezes the narrowest ACL inherited from the
exact selected source evidence. A live v1 object re-derives that ACL in memory from its immutable
reasoning context at materialization and final send without changing its stored hash; unresolved
lineage fails closed. Legacy route fields remain semantic audience/format hints, while concrete
channel and interrupt values are resolved again from live Layer 5.2 context.

## Part A · seven Delivery Orchestrator decisions

| # | Atlas decision | Documentation | Runtime mapping |
|---:|---|---|---|
| 1 | Delivery Context Resolver | `01-Delivery-Orchestrator/01-Delivery-Context-Resolver/` | `presence.py`, `gate.py`, tenant preferences, TTL leases |
| 2 | Audience Resolver | `01-Delivery-Orchestrator/02-Audience-Resolver/` | `audience.py`; current active event target, agent, manager, owner/team or admin fallback within source visibility |
| 3 | Destination Router | `01-Delivery-Orchestrator/03-Destination-Router/` | `destination.py`, tenant-scoped registrations, route eligibility and constrained-visibility scoped-surface rule |
| 4 | Channel Planner | `01-Delivery-Orchestrator/04-Channel-Planner/` | `orchestrator.py`; context surface, priority, capability, route ladder and format |
| 5 | Timing & Interruptibility | `01-Delivery-Orchestrator/05-Timing-and-Interruptibility/` | `timing.py`, presence/busy/quiet/burst plus final interrupt decision |
| 6 | Delivery Policy | `01-Delivery-Orchestrator/06-Delivery-Policy/` | `policy.py`, `gate.py`, composed `SEND`/`DEFER`/`SUPPRESS` |
| 7 | Priority Scheduler | `01-Delivery-Orchestrator/07-Priority-Scheduler/` | `scheduler.py`, `outbox.py`; five classes, aging and per-org fairness |

## Part B · eleven Delivery Units

| # | Atlas unit | Documentation | Runtime truth |
|---:|---|---|---|
| 1 | Human | `02-Delivery-Units/01-Human/` | Authenticated pull plus Slack/Teams; UI clients are external |
| 2 | Agent | `02-Delivery-Units/02-Agent/` | Scoped delivery inbox/receipts and signed agent webhook; raw `/v1/signals*` is retired with authenticated 410 |
| 3 | API | `02-Delivery-Units/03-API/` | Authenticated REST/pull and webhook; no claim of GraphQL/stream/MCP/SDK suite |
| 4 | Application | `02-Delivery-Units/04-Application/` | Durable application/in-app surface; client implementation external |
| 5 | Notification | `02-Delivery-Units/05-Notification/` | In-app surface only; no APNs/FCM/native system provider |
| 6 | Dashboard | `02-Delivery-Units/06-Dashboard/` | Dashboard/in-app pull; dashboard UI external |
| 7 | Webhook | `02-Delivery-Units/07-Webhook/` | Signed HTTPS adapter; tenant endpoint/secret required |
| 8 | Extension | `02-Delivery-Units/08-Extension/` | Extension pull surface; browser/CRM/email client external |
| 9 | Mobile | `02-Delivery-Units/09-Mobile/` | Mobile pull surface; native client and push external |
| 10 | Email | `02-Delivery-Units/10-Email/` | Unit contract exists, but no adapter; unavailable |
| 11 | Slack / Teams | `02-Delivery-Units/11-Slack-and-Teams/` | Dedicated adapters; credentials and live provider proof required |

Surface adapters make delivery durably available to authenticated clients; they do not simulate a
physical push or prove that a corresponding frontend has shipped.

## Part C · eight Delivery Management systems

The frozen Atlas lists **Delivery Outbox** as a first-class management system, so this part contains
eight systems. `outbox.py` is the durable adapter boundary installed by migration `0046`, not an
unnamed implementation detail.

| # | Atlas system | Documentation | Runtime mapping |
|---:|---|---|---|
| 1 | Delivery Outbox | `03-Delivery-Management/01-Delivery-Outbox/` | `outbox.py`; the outbox row and the state change that justified it commit together, then a worker claims a due row. At-least-once with idempotent effects — the only combination that is achievable over a network |
| 2 | Delivery Tracker | `03-Delivery-Management/02-Delivery-Tracker/` | `tracker.py`, `results.py`, lifecycle timestamps and idempotent events |
| 3 | Retry Manager | `03-Delivery-Management/03-Retry-Manager/` | `outbox.py`; atomic quota+attempt start, bounded retries, backoff, `Retry-After`, retry generations |
| 4 | Failure Recovery | `03-Delivery-Management/04-Failure-Recovery/` | Same-row route advance after definite failure; physical-attempt inspection and ambiguity-aware replay |
| 5 | Deduplication | `03-Delivery-Management/05-Deduplication/` | Logical dedupe key/unique row plus webhook/agent idempotency key |
| 6 | Rate Limiter | `03-Delivery-Management/06-Rate-Limiter/` | `rate_limit.py`; exact rolling hour, shared Slack/Teams stream, per-recipient local day and 0046 baseline |
| 7 | Delivery Analytics | `03-Delivery-Management/07-Delivery-Analytics/` | `analytics.py`; transport, lifecycle, latency, engagement and fatigue |
| 8 | Delivery Object Builder | `03-Delivery-Management/08-Delivery-Object-Builder/` | `orchestrator.py`, `contracts/delivery.py`, `results.py` |

## Supporting contracts and operations

`04-Contracts-and-Operations/` is supporting implementation documentation, not a fourth Atlas
part. It maps to:

- `genios_engine/contracts/delivery.py` for `DeliveryObject` and `DeliveryResult` v2;
- `genios_engine/api/delivery_routes.py` and `channel_routes.py` for inbox, result, lifecycle,
  capability, configuration and operations APIs;
- `migrations/0042_l6_delivery_gate.sql`, `0044_l52_atlas_delivery.sql` and
  `0046_l52_delivery_control_plane.sql` for the accumulated durable schema;
- delivery-focused tests and architecture/schema ratchets for verification.

Migration 0046 adds execution lineage, encrypted configuration fields, route/priority/claim and
lifecycle data, legacy reconciliation audit, unique logical dedupe, `delivery_events`,
`delivery_attempts` and seeded `delivery_rate_windows`. It requires a no-mixed-worker quiescent
cutover.

## Intentional implementation differences

- The Atlas sample package name `delivery/` maps to the established repository package
  `genios_engine/deliver/`; changing it would be cosmetic churn, not architectural alignment.
- The package's import rank is `6`; product identity remains Layer 5.2. Historical `l6` migration
  and test names are retained for migration/history stability and do not rename Atlas Layer 6.
- One outbox row is the logical `DeliveryObject` ledger rather than creating a parallel primary
  result store. Attempts and lifecycle events remain append-only children/projections.
- Fallback changes the route cursor on that same logical object. It does not create a second
  independently authorized delivery.
- Pull surfaces are valid engine routes, but their native clients and device notifications remain
  integrations. Email remains unavailable until a real adapter and complete identity/feedback
  lifecycle exist.

## Atlas v3.1 · contract envelope

The Atlas now requires a four-field `ContractEnvelope` on every boundary object. For this layer:

| Envelope field | `DeliveryObject` / `DeliveryResult` |
|---|---|
| `org_id` | ✅ on both, and on every delivery table |
| `schema_version` | ✅ `delivery-object.v2`, `delivery-result.v2` |
| `visibility` | ✅ frozen on new `ExecutionObject` v2 and re-derived fail-closed for v1 at both routing boundaries; not duplicated on DeliveryObject/Result, so a result-only consumer still needs the execution join |
| `trace_id` | ❌ does not exist anywhere in the engine |

Full reasoning, the consequence of each gap and the cheap fix for `trace_id`:
[Cross-Cutting · 06-Atlas-Envelope-Alignment.md](../../Cross-Cutting-Contracts-Platform-API/06-Atlas-Envelope-Alignment.md).

Two Atlas v3.1 items that this layer already satisfied before the text was written:

- **The closed verdict set.** `SEND` / `DEFER` / `SUPPRESS`, composed by intersection so one
  `SUPPRESS` ends it and the latest deferral window binds. A `DEFER` moves the clock and consumes
  no retry attempt — `contracts/delivery.py`, locked by `tests/test_delivery_gate.py`.
- **Distinct endings.** `DeliveryResultStatus` carries `cancelled`, `expired`, `failed` and
  `suppressed` separately, plus `deferrals` as its own counter. The Atlas previously collapsed
  these; the code never did.

## Conformance verdict

The current structure covers all **7 orchestration decisions, 11 unit contracts and 8 management
systems**, and the active boundary conforms to `ExecutionObject → DeliveryResult`. That is
architectural and engine coverage, not proof that every external channel is production-ready. Use
[the status ledger](../STATUS.md) and [production runbook](Bugs-Runbook-and-Gaps.md) for that
distinction.

Execution ingress covers source visibility, while the delivery projections still expose it by
execution join rather than duplication. `trace_id` remains absent. Those envelope projection
items are recorded in
[05-Gaps.md](../../Cross-Cutting-Contracts-Platform-API/05-Gaps.md), not quietly folded into the
verdict above.

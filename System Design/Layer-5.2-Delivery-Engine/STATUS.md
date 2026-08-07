# Layer 5.2 implementation status

This is a code-evidence ledger, not a live-deployment certificate. The statuses are:

- **Built in engine** — the authoritative backend path exists.
- **Built · integration required** — the engine seam exists, but a real client, provider,
  credential or publisher is still required.
- **Unavailable** — no usable adapter exists and the route must remain disabled.
- **Deployment proof pending** — code exists, but live migration, concurrency, provider or outage
  evidence is still required.

## Completion matrix

| Scope | Structural coverage in current code/docs | Honest completion statement |
|---|---:|---|
| Delivery Orchestrator | **7 / 7 decisions represented** | Core resolution/admission path, source-visibility enforcement and minute-scale scheduler are built; automatic client presence publishing and live queue proof remain external/operational work |
| Delivery Units | **11 / 11 units represented; 10 / 11 expose a backend route** | Email has no adapter; several of the ten are durable pull surfaces rather than shipped clients or native push |
| Delivery Management | **8 / 8 systems represented** | Outbox, lifecycle, retry, recovery, dedupe, rate, analytics and object-builder paths exist; real-provider and live-PostgreSQL proof remains |
| Active boundary | **ExecutionObject in → DeliveryResult out** | Enforced by the production materializer; a card alone cannot authorize transport |
| Production certification | **Deployment proof pending** | Full local suite is confirmed at 1,861 passed; populated-PostgreSQL cutover, concurrency and configured-provider proof remain |

“Represented” means an Atlas component has an explicit implementation seam and owned contract. It
does not mean its external integration has been bought, configured, deployed or observed under
production load.

## Part A · Delivery Orchestrator

| # | Atlas decision | Status | Current code evidence | Remaining integration/proof |
|---:|---|---|---|---|
| 1 | Delivery Context Resolver | **Built · integration required** | `presence.py`, `gate.py`, TTL-bound presence and preference tables | Trusted automatic presence publishers for every real client/seat |
| 2 | Audience Resolver | **Built in engine** | `audience.py`, current active target/agent/manager/owner/team/admin fallback filtered by `ExecutionObject` v2 source visibility | Live directory emails must be configured and kept current |
| 3 | Destination Router | **Built in engine** | `destination.py`, tenant-scoped registered destinations and route ordering | Real tenant destinations/credentials and egress proof |
| 4 | Channel Planner | **Built · integration required** | `orchestrator.py`, context-surface map, route ladder, format selection | Provider/client breadth described in the unit matrix below |
| 5 | Timing & Interruptibility | **Built in engine** | `timing.py`, leased presence, quiet/busy/burst rules; final interrupt decision in `orchestrator.py` | Correct user timezone and fresh presence publishers |
| 6 | Delivery Policy | **Built in engine** | `policy.py`, `gate.py`, composed `SEND`/`DEFER`/`SUPPRESS` decisions plus final execution/visibility re-proof | Tenant policy rollout and operational review |
| 7 | Priority Scheduler | **Built in engine** | `scheduler.py`, `outbox.py`, dedicated minute-scale platform loop; five classes, aging, per-org due-row fairness and fenced claims | Configure cadence and prove ordering/fairness under live PostgreSQL contention |

Layer 5's business priority remains immutable. The scheduler converts it into a delivery queue
class and ages delayed work; it does not revise the business decision.

## Part B · 11 Delivery Units

`operational` is the runtime capability endpoint's dynamic truth: at least one current
`configured_channel` survived presence/active-scope checks or decrypted adapter validation. It
does **not** mean a frontend or provider account has passed production smoke tests.

| # | Delivery unit | Runtime operational when | Status | Current backend route and remaining work |
|---:|---|:---:|---|---|
| 1 | Human | a valid live surface or decrypted human push config exists | **Built · integration required** | `in_app`, `dashboard`, Slack/Teams; browser/desktop/mobile clients remain external |
| 2 | Agent | exact active agent has `delivery.read` plus valid push config or same-agent active API key | **Built · integration required** | Scoped delivery inbox/receipts plus signed agent webhook |
| 3 | API | always, through authenticated REST | **Built in engine** | Authenticated REST resource/pull and webhook path; GraphQL, streams, MCP or SDKs are optional future clients, not claimed |
| 4 | Application | an unexpired application presence lease exists | **Built · integration required** | `application`/`in_app` durable surface; web/desktop/IDE/CLI rendering clients remain |
| 5 | Notification | never yet; native provider absent | **Built · integration required** | Contract seam exists, but APNs/FCM/native system provider does not; ordinary in-app remains Human/Application |
| 6 | Dashboard | an unexpired dashboard presence lease exists | **Built · integration required** | `dashboard`/`in_app` inbox exists; dashboard UI rendering is outside this backend |
| 7 | Webhook | sealed endpoint/secret decrypt and pass adapter validation | **Built · integration required** | Signed HTTPS adapter exists; customer endpoint, secret and network policy are tenant operations |
| 8 | Extension | an unexpired extension presence lease exists | **Built · integration required** | `extension` pull surface exists; browser/CRM/email extension client remains |
| 9 | Mobile | an unexpired mobile presence lease exists | **Built · integration required** | `mobile` pull surface exists; mobile client, device-token lifecycle and APNs/FCM remain |
| 10 | Email | never yet; adapter absent | **Unavailable** | No email adapter, verified sender/domain, unsubscribe, bounce, complaint or receipt lifecycle |
| 11 | Slack / Teams | sealed webhook config decrypts and passes provider-host validation | **Built · integration required** | Dedicated adapters exist; tenant webhook/OAuth configuration and live provider tests remain |

Authenticated pull means durable availability; it must not be described as native push or a
finished UI. Email and native mobile/system push remain disabled until their full identity,
permission and feedback lifecycles exist.

## Part C · Delivery Management

| # | Atlas system | Status | Current code evidence | Remaining integration/proof |
|---:|---|---|---|---|
| 1 | Delivery Outbox | **Built in engine** | `orchestrator.py`, `outbox.py`; one logical row, fenced claims, append-only physical attempts and ambiguity-aware recovery | Quiescent 0046 cutover and real multi-worker/provider reconciliation proof |
| 2 | Delivery Tracker | **Built · integration required** | `tracker.py`; validated lifecycle graph, idempotent event append, viewed/ignored/accepted/executed timestamps | Real clients/providers must publish trustworthy lifecycle receipts |
| 3 | Retry Manager | **Built in engine** | `outbox.py`; atomic quota+attempt start, bounded backoff, `Retry-After`, retry generations and append-only attempts | Real outage and rate-limit exercises |
| 4 | Failure Recovery | **Built in engine** | Definite-terminal-only route advance; physical attempt evidence; ambiguity-aware owner replay | Live fallback credentials and dead-letter operations |
| 5 | Deduplication | **Built in engine** | Stable logical dedupe key, unique outbox identity and stable webhook/agent idempotency key | Ambiguous external acknowledgement remains at-least-once where receivers cannot dedupe |
| 6 | Rate Limiter | **Built in engine** | Exact rolling-hour reservations; shared Slack/Teams hourly stream; per-recipient local-day budget; 0046 delivered-row baseline | Quiescent migration cutover and live multi-worker contention/rollback proof |
| 7 | Delivery Analytics | **Built · integration required** | `analytics.py`; transport/lifecycle mix, attempts, deferrals, latency, engagement and recipient fatigue | Quality/completeness depends on real lifecycle receipts |
| 8 | Delivery Object Builder | **Built in engine** | `orchestrator.py`, `contracts/delivery.py`, `results.py`; `DeliveryObject`/`DeliveryResult` v2 | Contract compatibility and deployed-schema verification |

## Boundary and lifecycle evidence

- The active materializer reconstructs and identity-checks a stored `ExecutionObject` for initial
  execution and `execution.reminded` events. Raw card and legacy synchronous fan-out paths are not
  delivery authority.
- `ExecutionObject` v2 carries source-derived visibility. Participant/private delivery requires a
  matching active seat email and stays on authenticated recipient-scoped product surfaces; an
  unbound agent or unresolved lineage fails closed.
- One logical outbox row owns the route ladder; physical attempts and lifecycle transitions are
  append-only. Definite terminal failure advances the cursor; ambiguous acknowledgement does not
  cross-channel fail over.
- Transport and lifecycle status are separate. Typed results include delivered, viewed, ignored,
  accepted, executed, failed, expired, suppressed and cancelled outcomes.
- Layer 6 reads typed delivery lifecycle facts in its feedback batch. That is learning evidence,
  not permission for Layer 6 to control delivery.

## What is still required before “fully production-ready”

1. Quiesce every legacy delivery producer/drainer, reconcile its last uncertain provider call,
   apply migrations through `0046_l52_delivery_control_plane.sql`, deploy only v2 workers, then
   resume. Mixed old/new delivery workers are not a supported cutover.
2. Verify 0046's legacy quarantine and rolling-hour/current-local-day quota baseline before
   allowing provider calls.
3. Run the relevant test and architecture ratchets on the final merged branch; this status page
   does not substitute for their result.
4. Prove fenced claims, priority fairness, atomic quotas, retries, ambiguity and fallback under
   concurrent workers.
5. Configure real Slack/Teams/webhook/agent credentials and run outage/rate-limit/receipt drills.
6. Bind signed-in humans to verified seat identities for recipient-scoped multi-seat inbox access,
   then ship the required application/dashboard/extension/mobile clients and automatic presence
   and lifecycle-receipt publishers. Owners retain organization-wide operational access.
7. Build email and APNs/FCM only with their complete identity, permission, unsubscribe/device-token
   and feedback lifecycles.
8. Add production observability, alerting, SLOs, dead-letter ownership and credential-rotation
   procedures.

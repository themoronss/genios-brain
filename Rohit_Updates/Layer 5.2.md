# Layer 5.2 — Delivery Engine

**Last updated:** 8 August 2026
**Branch:** `antler-inception`
**Product identity:** Layer **5.2** is Delivery. Layer **6** is Learning & Evolution. There is no
product Layer 7.
**Verification:** `1861 passed, 1 unrelated Starlette/httpx deprecation warning`
**Status:** The Atlas-aligned **internal delivery control plane is implemented and wired**.
What remains is deployment, real-provider credentials, product clients and live integration/load
proof—not another hidden routing or lifecycle subsystem.

System Design: [Layer 5.2 index](../System%20Design/Layer-5.2-Delivery-Engine/README.md) ·
[status matrix](../System%20Design/Layer-5.2-Delivery-Engine/STATUS.md) ·
[orchestrator](../System%20Design/Layer-5.2-Delivery-Engine/01-Delivery-Orchestrator/README.md) ·
[11 delivery units](../System%20Design/Layer-5.2-Delivery-Engine/02-Delivery-Units/README.md) ·
[management](../System%20Design/Layer-5.2-Delivery-Engine/03-Delivery-Management/README.md) ·
[contracts and operations](../System%20Design/Layer-5.2-Delivery-Engine/04-Contracts-and-Operations/README.md)

---

## 1. CTO verdict

The architecture now follows the Atlas boundary:

```text
Layer 5                         Layer 5.2                         Layer 6
commitment                     delivery                          learning

work owner                     current audience/recipient       measured adaptation
actions + deadline      ->     destination/channel/format  ->   from DeliveryResult
business priority              timing/policy/priority
ExecutionObject                lifecycle/retry/recovery          no guessed engagement
```

The one active Layer 5.2 input is a persisted, hash-verifiable `ExecutionObject`. Cards are a
presentation/read model and cannot independently authorize an outward notification. The old
synchronous agent fan-out and raw-card enqueue path are not called by the production distribution
sweep.

New commitments use `execution.v2`, which also freezes the narrowest Layer 1 source visibility
inherited through the selected Layer 4 evidence. Existing `execution.v1` objects remain
hash-compatible; Layer 5.2 re-derives their ACL in memory from the immutable reasoning context, and
missing lineage fails closed rather than becoming an org-visible default. Concrete communication
fields retained in both contracts are backwards-compatible audit hints: Layer 5.2 ignores the
frozen channel and interrupt values and recomputes the live route from current directory, presence,
destinations, visibility and policy.

### What “complete” means here

- The internal boundary, orchestration, persistence, safety, management, API and Layer 6 handoff
  are present and covered by the repository suite.
- A capability is not called externally operational unless its provider/client exists. The
  capability registry reports this distinction through `engine_ready`, `operational`,
  `available_channels` and `integration_required`.
- No claim is made that migration `0046`, provider ACK-loss behavior or multi-worker contention
  has been proven on production infrastructure. The repository closes the internal races; the
  quiescent cutover and real-provider proof remain mandatory deployment work below.

---

## 2. The active runtime flow

```text
Layer 5 persists immutable ExecutionObject
        ↓
minute delivery heartbeat calls run_distribution
        ↓
Delivery Orchestrator resolves source visibility + context + audience + route + format + priority
        ↓
one logical DeliveryObject is inserted idempotently
        ↓
priority/fairness worker claims it with an expiring fencing token
        ↓
hard policy + quiet/busy timing + atomic attention quota/attempt journal
        ↓
live execution identity/hash/authority re-check
        ↓
surface or provider adapter (only after the durable attempt exists)
        ↓
append-only attempt outcome + lifecycle event
        ↓
DeliveryResult API/analytics → Layer 6 DeliveryFact
```

Initial delivery and reminder/escalation events use the same materializer. A malformed frozen
object is written to `delivery_materialization_failures`; it cannot silently disappear or crash
all tenants. Once the source is repaired and successfully materialized, that failure is marked
resolved.

---

## 3. Delivery Orchestrator — all seven Atlas responsibilities

| Atlas responsibility | Implementation | Current behavior |
|---|---|---|
| Delivery Context Resolver | `deliver/presence.py`, `deliver/gate.py` | Reads an expiring seat lease: activity, current surface, focus mode and busy window. Stale context expires rather than becoming permanent truth. |
| Audience Resolver | `deliver/audience.py` | Resolves current owner/manager/admin or a specific registered agent, then permits only a current seat whose verified email can view the inherited source ACL. A frozen former manager or unrelated admin cannot bypass that ACL. |
| Destination Router | `deliver/orchestrator.py`, `deliver/destination.py` | Builds one stable primary→fallback ladder from registered destinations and authenticated product surfaces. Human and agent routes are isolated; participant/private evidence cannot enter a shared Slack/Teams/webhook route. |
| Channel Planner | `deliver/orchestrator.py` | Deterministically selects `inline_suggestion`, card, Slack/Teams message, webhook payload, agent envelope or REST resource. No LLM chooses a route or format. |
| Timing & Interruptibility | `deliver/timing.py`, `deliver/gate.py` | Quiet hours, focus/meeting state and burst windows return `SEND`, `DEFER` or `SUPPRESS`. Deferral never consumes a provider retry. |
| Delivery Policy | `deliver/policy.py`, `deliver/orchestrator.py`, preferences API | Source visibility, tenant/seat/channel enablement, holds, opt-out, band floor, quiet policy and hard suppression are enforced at materialization and rechecked under live locks at the send boundary. |
| Priority Scheduler | `deliver/scheduler.py`, `deliver/outbox.py` | Maps business priority into Critical/High/Medium/Low/Background, orders due claims and ages waiting rows every four hours to prevent starvation. |

### Routing laws now enforced

1. Human delivery never uses the reserved `agent` transport.
2. Agent delivery may use only the signed agent push or authenticated API inbox; it never falls
   back into a human dashboard with an agent recipient.
3. Agent selection requires the exact `delivery.read` grant. A poll-only agent receives an API
   route only when an active scoped API key for that same `agent_id` exists. Registry-only or
   legacy signal-read grants cannot turn into an execution instruction.
4. High/critical work prefers an eligible current surface or configured push route. Busy/focus
   state removes interruption but does not erase the delivery.
5. Medium/low/background work lands on durable pull surfaces. Those inboxes are the non-intrusive
   batch/queue; the active path does not create a second duplicate “digest delivery” for the same
   insight.
6. Route fallback advances the same logical row and recomputes channel class, payload, format,
   interruption and reason. It does not create another logical notification.
7. `participants`/`private` evidence is routed only to a visibility-authorized active seat on an
   authenticated recipient surface. No authorized principal means fail-closed materialization,
   not an arbitrary admin fallback.

---

## 4. Eleven Atlas delivery units

The registry is `deliver/units.py`; the public view is
`GET /api/org/{org_id}/delivery/capabilities`.

| Unit | Internal engine | Operational transport now | External work still required |
|---|---|---|---|
| Human | Complete | In-app, dashboard, Slack, Teams | Browser/desktop/mobile clients for every desired human surface |
| Agent | Complete | Signed per-agent webhook + scoped REST inbox | Register each runtime, endpoint and scopes; receiver verifies HMAC/idempotency |
| API | Complete | Authenticated REST inbox + signed webhook | GraphQL, streaming, MCP and SDK only if product chooses them |
| Application | Complete seam | `application` pull surface | Web/desktop/IDE/CLI client rendering and receipts |
| Notification | Complete seam | In-app notification surface | APNs/FCM and OS notification provider/client wiring |
| Dashboard | Complete seam | Durable dashboard/in-app pull data | Dashboard UI rendering, presence and receipt emission |
| Webhook | Complete | Public-HTTPS HMAC adapter with stable idempotency key | Customer endpoint/secret, DNS/egress hardening and receiver contract |
| Extension | Complete seam | Authenticated extension inbox + context lease | Browser/CRM/email-editor extension client |
| Mobile | Complete seam | Authenticated mobile inbox | Mobile app plus APNs/FCM for native push |
| Email | Contract/capability ready | No provider is falsely reported | Select SMTP/API provider, verified domain, bounce/unsubscribe/feedback handling |
| Slack / Teams | Complete adapters | Incoming webhook / Teams Workflow | Tenant credentials; OAuth/bot integration for exact per-user DM/thread targeting |

“Complete seam” means the deterministic route, durable DeliveryObject, authenticated pull API,
lifecycle receipts and analytics are implemented. It does not mean a browser extension or mobile
binary has magically been shipped from this backend repository.

`operational` is fail-closed runtime truth, not “a row exists.” Capability discovery decrypts the
current sealed credential with `GENIOS_CRYPTO_KEY` and runs the same URL/secret/agent shape checks
used by the adapter boundary. Missing keys, corrupt ciphertext, invalid endpoints and registry-only
agents are reported unavailable without exposing credential bytes or decryption errors.

---

## 5. Delivery Management — all eight Atlas managers

### 5.1 Delivery Outbox

`deliver/orchestrator.py` and `deliver/outbox.py` implement the Atlas's durable spine. The current,
hash-verified execution and its fully resolved Layer 5.2 plan become one tenant-scoped logical row
plus an append-only `queued` event in one transaction; no adapter is called inline. A later worker
claims that row with `FOR UPDATE SKIP LOCKED` and an expiring fencing token. The attention
reservation and physical `started` attempt then commit together before network I/O, so a crash
cannot create an invisible provider call. One route ladder stays on one row; definite failure may
advance it, while ambiguous evidence stops unsafe cross-channel fan-out and requires bounded
reconciliation/replay rules.

### 5.2 Delivery Tracker

`deliver/tracker.py` separates transport state from the public engagement lifecycle:

```text
queued ↔ deferred → delivered → viewed → ignored
                              └→ accepted → executed | failed
queued/deferred/delivered/viewed/accepted → expired where legal
```

`suppressed` and `cancelled` remain terminal facts with different meanings. Every move appends a
tenant-scoped `delivery_events` row in the same transaction. Client-supplied idempotency keys make
repeated taps/retries no-ops, and chronology validation rejects receipts before creation/delivery
or more than five minutes in the future.

### 5.3 Retry Manager

- Provider failures use bounded backoff: `5, 30, 120, 720` minutes, then terminal on the next
  failed attempt.
- `Retry-After` may change a still-available delay, but cannot resurrect an exhausted retry cycle.
- Quiet hours, meetings and quotas are deferrals, not failures, so they do not burn the ladder.
- Every provider call has an append-only `delivery_attempts` record. For intrusive delivery, the
  hourly/daily reservations and fenced `started` attempt commit in one transaction before network
  dispatch, so a worker crash cannot consume untraceable quota.

### 5.4 Failure Recovery

- Definite terminal failures may advance the same row to its next route.
- Ambiguous timeouts/5xx outcomes never cross-channel fail over because the first provider may
  already have accepted the message.
- Expired worker claims mark the exact claim-owned unfinished attempt `unknown` before another
  worker proceeds. If no attempt exists for that claim, the row is safely requeued without
  inventing ambiguous transport evidence.
- Slack/Teams incoming webhooks cannot consume an idempotency key. Their timeout, thrown adapter,
  lost ACK or expired post-attempt claim becomes terminal/manual reconciliation instead of an
  automatic duplicate human interruption.
- Owner-controlled replay requires an explicit duplicate-risk acknowledgement for `started`,
  `unknown`, `delivered` or pre-v2 legacy ambiguity. ACK-loss replay preserves the receiver key;
  definite non-delivery starts a new `retry_generation`, and old attempts remain append-only.

### 5.5 Deduplication

`(org_id, dedupe_key)` is globally unique for non-legacy delivery rows. Initial execution and each
execution event have deterministic logical keys. Ten available destinations produce one delivery
with a route ladder—not ten impressions.

Provider idempotency is stable across retries of one route generation:

```text
delivery_id : retry_generation : channel
```

Generic webhook and agent transports forward this key. Slack/Teams incoming webhooks do not offer
the same end-to-end guarantee, so automatic retry is refused on ambiguity and an owner must inspect
provider state and explicitly accept duplicate risk before replay.

### 5.6 Rate Limiter

PostgreSQL conditionally reserves the final hourly and daily attention slot, so two workers cannot
both spend it. Slack and Teams share one tenant-wide exact rolling-hour stream, while the local-day
budget remains per recipient (including mixed timezones). The daily limit is snapshotted from the
effective configuration onto the DeliveryObject. Reservation and attempt start are atomic; a
definite non-delivery releases both slots, while an ambiguous outcome retains them because the
person may already have been interrupted.

### 5.7 Delivery Analytics

`deliver/analytics.py` reports counted status/channel cohorts, transport success/failure, attempts,
deferrals, burst holds, p50/p95 delivery latency, response/execution time, view/ignore/accept/execute
rates and per-recipient fatigue. Denominators use real impressions only. Earlier engagement clocks
survive a later expiry instead of being erased by the latest lifecycle state.

### 5.8 Delivery Object Builder

`deliver/orchestrator.py` materializes the v2 DeliveryObject with execution lineage, audience,
recipient, destination, concrete channel, format, five-class priority, daily budget, timing,
route reason/ladder, dedupe key, source payload and authority expiry. The output projection is
`delivery-result.v2`.

---

## 6. Persistence and migration `0046`

Migration `0046_l52_delivery_control_plane.sql` adds:

- `cards.execution_id`, making cards explicitly subordinate to an ExecutionObject;
- execution lineage/hash, route, format, priority, budget, source, fenced claim, retry generation
  and lifecycle columns on `delivery_outbox`;
- composite tenant foreign keys and unique logical-delivery identity;
- append-only `delivery_events` and `delivery_attempts`;
- atomic `delivery_rate_windows`;
- durable `delivery_materialization_failures`;
- encrypted credential columns for org channels and agent webhooks;
- a legacy-reconciliation marker and explicit replay-approval timestamp;
- check constraints for lifecycle vocabulary/timestamps, claim shape, route cursor, priority,
  budget, retry counters and non-legacy execution lineage.

`0046` takes a write-blocking outbox table lock, seeds exact rolling-hour and current per-recipient
local-day counters from already delivered rows, and marks **every pre-control-plane pending or
terminal-failed legacy row** for manual reconciliation—even `attempts=0`, because an old worker
could have POSTed and crashed before incrementing that counter. The v2 materializer cannot adopt a
marked row. Only an owner's explicit ambiguous-risk replay clears the marker. The migration runner uses a
PostgreSQL session advisory lock, so replicas cannot race the migration ledger or non-idempotent
DDL.

The migration uses `NOT VALID` on compatibility foreign/check constraints so representative legacy
rows can be repaired without blocking rollout. New writes are still enforced. The CTO must validate
those constraints after production cleanup; “migration applied” and “all legacy rows validated” are
two separate deployment facts.

This is intentionally not a rolling old/new-worker migration. Database locks cannot stop an old
process that has already started an external POST, and the old worker does not understand v2 rows,
fencing or atomic quotas. The exact stop/wait/apply/deploy/resume sequence in section 10 is a release
condition, not an optional hardening item.

---

## 7. Security and API surface

### Authentication and isolation

- Preferences, channel configuration/test sends, dead-letter replay and destructive operations
  require an owner credential.
- Scoped clients use explicit grants: `delivery.read`, `delivery.receipts.write` and
  `delivery.context.write`.
- A scoped `agent_id` is bound to its own recipient/seat. It cannot read another seat or receive
  org-wide rows through a null-recipient fallback.
- Scoped context `PUT` requires `delivery.context.write`; scoped context `GET` requires
  `delivery.read`. Both are self-bound to the authenticated `agent_id`; owners retain org-wide
  context administration and context `DELETE` remains owner-only.
- Every SQL read/write carries authenticated `org_id`; path/body values are never tenant authority.
- New provider secrets are Fernet-sealed. List APIs return masked metadata, not secrets.
- Generic and agent webhook URLs require public HTTPS and reject obvious private, loopback, local,
  credential-bearing and non-HTTPS targets.

### Operational APIs

```text
GET    /api/org/{org_id}/delivery/results
GET    /api/org/{org_id}/delivery/results/{delivery_id}
GET    /api/org/{org_id}/delivery/inbox
POST   /api/org/{org_id}/delivery/results/{delivery_id}/events
GET    /api/org/{org_id}/delivery/results/{delivery_id}/attempts
POST   /api/org/{org_id}/delivery/results/{delivery_id}/replay
GET    /api/org/{org_id}/delivery/dead-letters
GET    /api/org/{org_id}/delivery/analytics
GET    /api/org/{org_id}/delivery/capabilities
PUT/GET/DELETE delivery context and preference endpoints
owner-only channel and agent-webhook configuration endpoints
```

The legacy `/v1/signals*` poll/claim/result handlers are authenticated `410 Gone` sentinels, not a
second execution plane. Active agents consume complete `genios.agent-delivery.v1` envelopes from
`/delivery/inbox?channel=api` and submit scoped lifecycle receipts.

The dead-letter surface returns both terminal transport rows and unresolved materialization
failures, so a corrupt source object does not remain invisible to operations.

---

## 8. Layer 6 handoff

`feedback/store.py` reads the same durable outbox by tenant and bounded window. `DeliveryFact` now
preserves lifecycle status and `viewed_at`, `ignored_at`, `accepted_at`, `executed_at` timestamps.
`performance_optimization` measures those real facts alongside delivery, failure, attempts,
deferrals and latency.

Layer 6 does not infer engagement. If a client has not emitted an authenticated receipt, the field
stays null. If a user viewed a delivery before it expired, the earlier view remains evidence.

---

## 9. Verification evidence

### Dedicated control-plane ratchets

`tests/test_delivery_control_plane.py` covers:

- human vs agent route isolation, poll-only agents and fail-closed no-route behavior;
- inherited source-visibility routing, v1 hash compatibility and v2 ACL round-trip;
- exact agent grants/API credential binding and scoped context self-binding;
- current-manager resolution and stale target rejection;
- proof that Layer 5's concrete channel/interrupt hints cannot bypass Layer 5.2;
- context-aware inline/busy behavior;
- all five priority boundaries and anti-starvation aging;
- all eleven unit capability reports;
- legal/illegal lifecycle paths;
- expired-after-viewed analytics and Layer 6 consumption;
- DeliveryObject daily-budget projection and validation;
- terminal/429/ambiguous provider outcome classes;
- scoped inbox isolation;
- migration tenant/fencing/lineage ratchets;
- quiescent legacy reconciliation, quota baseline, per-user daily/shared-hourly identities and
  atomic quota/attempt journaling;
- ExecutionObject-only active distribution and stable provider idempotency;
- API surface registration.

The dedicated control-plane file runs inside the focused delivery/executive set below; the full
suite result is the release ratchet rather than a hand-maintained per-file count.

### Full repository

```text
1861 passed, 1 warning in 8.21s
```

The warning is a third-party Starlette/httpx deprecation, unrelated to Layer 5.2 behavior.
`compileall` and `git diff --check` also pass. No live PostgreSQL/provider environment was available
in this workspace, so the next section remains mandatory.

---

## 10. CTO deployment and integration checklist — the only remaining work

### P0 — deploy the control plane

1. Back up the target database. Stop **all** old delivery producers and drainers—not only the new
   feature flag—and prevent an autoscaler from starting another old replica.
2. Wait at least the old five-minute worker lease **plus the maximum provider-call timeout**, then
   inspect/reconcile any provider request that may still have been in flight. There is no safe
   old/new mixed-worker window.
3. While outbound work remains stopped, apply `0046` through the checksummed migration runner. Its
   advisory/table locks serialize DDL and adoption; confirm historical hourly/local-day quota rows
   were seeded and every pending pre-v2 legacy row is marked for reconciliation.
4. Deploy only the v2 code to every worker. Review marked legacy dead letters against provider
   state; replay only with the explicit ambiguous-risk acknowledgement. Then enable v2
   materialization/drain.
5. Inspect legacy cards/outbox rows, repair violations, then run `VALIDATE CONSTRAINT` for every
   `0046` constraint created `NOT VALID`.
6. Run concurrent staging workers to prove `SKIP LOCKED`, claim expiry/fencing, one logical dedupe
   winner, final rolling-hour/local-day contention, replay-twice paths, visibility/recipient races
   and expiry/send races on real PostgreSQL.
7. Set `GENIOS_CRYPTO_KEY` and an HTTPS-origin `GENIOS_PUBLIC_APP_URL`; re-save or rotate every
   existing plaintext org-channel and agent credential. Confirm backups/logs do not expose old
   values and capability discovery reports corrupt/unusable credentials unavailable.

### P0 — wire the first real surfaces

8. Configure one Slack tenant, one Teams tenant, one signed generic webhook and one registered
   agent runtime in staging.
9. Exercise 2xx, terminal 4xx, 429 with `Retry-After`, 5xx/timeout, ACK loss, route fallback,
   authority revocation and dead-letter replay. Verify provider-side duplicate behavior.
10. Before multi-seat release, bind every signed-in human to a verified `org_seats` identity and
    enforce recipient-scoped inbox reads; then implement the product clients' presence leases,
    inbox polling and idempotent lifecycle receipts for dashboard/application/extension/mobile
    surfaces. Owners intentionally retain organization-wide operational access.

### P1 — provider choices

11. Select and integrate the email provider, verified domain, bounce/complaint/unsubscribe pipeline
   and inbound engagement receipts.
12. Add APNs/FCM and OS notification handling for native mobile/system notifications.
13. If exact Slack/Teams person targeting is required, replace channel-wide incoming webhooks with
    tenant OAuth/bot APIs and map GeniOS seats to provider user IDs.
14. Add GraphQL/streaming/MCP/SDK delivery only where an actual consuming product requires it; the
    REST and webhook boundaries already exist.

### P1 — production hardening

15. Enforce network-level webhook egress allowlists/proxy rules, DNS resolution checks and secret
    rotation. Application URL validation alone is defense in depth, not a complete SSRF boundary.
16. Add dashboards/alerts for queue age by priority, materialization failures, unknown attempts,
    retry exhaustion, provider latency/error rates, lifecycle receipt delay, quota holds and
    recipient fatigue.
17. Define SLOs and run provider outage, worker crash, database failover and key-rotation drills.

When these checks pass, production readiness is an evidence-backed deployment statement. The
repository no longer needs another internal routing, retry, lifecycle, analytics or learning
handoff subsystem to satisfy the Atlas Layer 5.2 design.

---

## 11. Compatibility notes

- `enqueue_pending`, `enqueue_digest`, `enqueue_failover` and the older executive bridge remain in
  code so historical tests/rows and rollback analysis stay readable. `run_distribution` does not
  call them for new outward materialization.
- `execution.v2` adds source visibility. `execution.v1` remains byte/hash compatible and still
  stores channel/interrupt hints; Layer 5.2 does not trust them as current routing authority.
- Legacy `/v1/signals*` agent handlers deliberately remain as authenticated `410` migration
  sentinels. They cannot poll, claim or complete raw signal/card work.
- Existing plaintext provider columns remain a rolling-migration fallback. New configuration
  writes seal credentials; production must rotate the legacy values before retiring fallback.
- Generic/agent delivery is at-least-once across an ambiguous external network and uses a stable
  receiver key. Non-idempotent Slack/Teams ambiguity stops for manual reconciliation; true
  provider-level exactly-once still requires receiver/provider support.

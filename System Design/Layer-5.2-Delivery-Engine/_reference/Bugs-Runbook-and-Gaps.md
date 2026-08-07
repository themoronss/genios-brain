# Layer 5.2 gaps and production runbook

This page separates design defects closed by the current engine from external integration and
deployment evidence that cannot be completed in repository code alone.

## Closed by the current engine design

| Prior risk | Current control |
|---|---|
| A card or generic payload could authorize outbound delivery | The active materializer accepts a stored, identity-checked `ExecutionObject`; cards are linked read models only |
| Layer 5 could freeze a stale concrete channel/interrupt decision | Layer 5.2 treats legacy route fields as hints and resolves current audience, route, format and interruptibility |
| Derived private evidence could reach an unrelated seat or shared channel | New v2 commitments freeze the narrowest source ACL; live v1 commitments re-derive it from immutable reasoning context; participant/private recipients must match current seat email and stay on authenticated scoped surfaces |
| Re-org or reassignment could target a stale manager/owner | Audience resolution uses the current active directory and deterministic admin fallback |
| Failover could create duplicate logical deliveries | One outbox row owns the route ladder; definite terminal failure advances its route cursor |
| Lost acknowledgement could cause unsafe retry/fan-out | Ambiguous outcome is recorded as unknown and never cross-channel fails over; Slack/Teams ambiguity stops for manual reconciliation; replay requires explicit risk acknowledgement |
| Multiple workers could process the same unfenced claim | Time-bounded claim token/lease fences processing; reclaim updates only the exact token's started attempt, or safely requeues if no provider call began |
| Retry and lifecycle facts could overwrite history | Physical attempts and lifecycle events are append-only |
| A crash could consume quota without physical-attempt evidence | Rolling-hour + local-day reservations and the claim-owned `started` attempt commit in one transaction before the provider call |
| Process-local attention checks or an empty upgrade table could overspend | Exact rolling-hour and recipient-local-day reservations use PostgreSQL authority; 0046 seeds recent delivered attention before workers resume |
| Transport acknowledgement could be confused with human response | Transport state and viewed/ignored/accepted/executed lifecycle are separate |
| Capability discovery could report corrupt credentials as operational | Runtime discovery decrypts sealed config and executes adapter-equivalent URL/host/secret/id validation; failure is redacted and fail-closed |
| An agent could bypass Layer 5 through raw signals/cards | `/v1/signals*` authenticates then returns `410 Gone`; agents use exact-recipient `delivery/inbox?channel=api` plus lifecycle receipts |
| Delivery could wait for a multi-hour sync cadence | A dedicated configurable minute-scale scheduler runs materialize/expire/drain independently of maintenance |
| New provider credentials could be persisted as plaintext | Channel/agent configuration uses encrypted fields guarded by `GENIOS_CRYPTO_KEY` |

## Remaining external and production work

### Provider and client integrations

- Build an email adapter only with verified provider/domain/sender identity, unsubscribe handling,
  bounce/complaint feedback and receipt lifecycle.
- Build APNs/FCM/system notification delivery only with device-token ownership, permission, expiry,
  revocation and receipt handling.
- Ship the required application, dashboard, extension and mobile clients. Current surface adapters
  are authenticated durable pull, not proof of finished UIs or native push.
- Add trusted automatic presence and lifecycle-receipt publishers to those clients. The manual
  TTL-bound presence and receipt APIs are backend seams, not automatic telemetry.
- Configure real Slack/Teams tenants, signed webhook customer endpoints and active agent runtimes.
- Enforce network-level egress and DNS/host allowlists appropriate to the deployment. Application
  validation alone is not a complete SSRF/egress boundary.

### Deployment and operational proof

- Perform 0046 as a quiescent cutover: stop every legacy producer/drainer, reconcile the last
  uncertain provider call, apply the migration under the schema advisory/table locks, deploy only
  v2 workers, verify the baseline/quarantine, then resume. Mixed workers are unsupported.
- Re-save or rotate legacy plaintext channel/agent configuration after the migration. New-write
  encryption does not retroactively rotate old secrets.
- Prove fenced claims, priority aging/fairness, hourly/daily reservations and release behavior
  under real PostgreSQL multi-worker contention.
- Exercise retry, `Retry-After`, terminal route advance, ambiguous acknowledgement and dead-letter
  handling against real providers.
- Establish metrics, alerts, SLOs, dead-letter ownership, credential rotation and provider-outage
  drills.
- Configure a public HTTPS application origin and the minute scheduler cadence, or operate an
  equivalent external minute-scale delivery worker.
- Accept that external delivery can remain at-least-once after an ambiguous acknowledgement when
  the receiver offers no idempotency contract. Slack/Teams are not documented as exactly-once.

### Deliberately inactive behavior

- Email and native mobile/system push stay unavailable until their complete lifecycles exist.
- Legacy generic card/digest fan-out is not an active outward delivery authority. A future digest
  must be backed by an explicit Layer 5 `ExecutionObject` (or a separately ratified contract), not
  revived as a raw-card shortcut.

## Deployment verification runbook

### 1. Freeze the candidate

1. Record the commit SHA, environment, database version and configured worker count.
2. Run the final merged branch's delivery, API, architecture and schema ratchets. Preserve exact
   results; do not substitute this document for test evidence.
3. Stop and verify every legacy delivery producer/drainer. Reconcile its last uncertain provider
   timeout before taking the cutover snapshot; do not rely on the migration's table lock to fence
   a network call already in progress.

### 2. Apply and inspect schema

1. Back up according to the environment's approved database procedure.
2. Apply migrations `0042_l6_delivery_gate.sql`, `0044_l52_atlas_delivery.sql` and
   `0046_l52_delivery_control_plane.sql` in order. Verify the migration runner holds the global
   `genios-schema-migrations` advisory lock and 0046 acquires its outbox table lock.
3. Verify execution lineage and foreign keys, logical dedupe uniqueness, priority/route/claim and
   lifecycle columns, encrypted configuration columns, `delivery_events`, `delivery_attempts` and
   `delivery_rate_windows`.
4. Verify every pending and already-terminal legacy row is marked
   `legacy_reconciliation_required`; a pending row must terminalize on the v2 drain rather than
   send automatically.
5. Verify `delivery_rate_windows` contains the delivered-chat rolling-hour baseline and each
   recipient's current-local-day baseline before enabling new provider calls.
6. Set `GENIOS_CRYPTO_KEY` through the approved secret store before any sensitive configuration
   write/read path is enabled.
7. Re-save or rotate legacy channel/agent configuration and verify plaintext values are no longer
   the active source.
8. Deploy only the v2 application/worker build, configure the minute-scale heartbeat, then resume
   outbound work. Never overlap old and new delivery workers.

### 3. Prove the boundary

1. Materialize one initial execution and one `execution.reminded` event from stored
   `ExecutionObject` payloads; verify execution identity and lineage.
2. Attempt to deliver an unlinked/raw card and verify it cannot authorize an outbox row.
3. Close, reassign or otherwise invalidate a queued execution and verify send-time authority
   cancels or reroutes it safely.
4. Verify a frozen v1 channel/interrupt hint cannot override current context, policy or capability.
5. Verify a v2 participant/private execution inherits the narrowest selected-source visibility,
   reaches only a matching current seat on a scoped product surface, and cannot use shared push.
6. Materialize a stored v1 execution and verify visibility is re-derived from its immutable
   reasoning context without changing identity; missing lineage must fail closed.

### 4. Prove orchestration decisions

1. Exercise active owner, current manager, explicit active target, registered agent and
   deterministic admin fallback; inactive or visibility-unauthorized recipients must not win.
2. Publish presence for each supported context surface, then expire the lease. Stale presence must
   stop influencing channel/timing decisions.
3. Test all five priority classes and waiting-time aging without allowing a rank above critical.
4. Exercise quiet hours, busy/focus state, opt-out, missing capability and daily/hourly budgets.
   A deferral must not increment physical transport attempts.

### 5. Prove claims, quotas and transport outcomes

1. Run multiple workers against the same due set. Only the fenced claimant may complete a row;
   an expired claim must leave the uncertain attempt visible as unknown.
2. Drive concurrent sends across an epoch-hour edge and recipient-local midnight. Slack/Teams must
   share one rolling-hour stream, daily counts must remain per person, and definite non-spending
   paths must release reservations.
3. Crash after quota+attempt commit and verify the `started` attempt makes recovery conservatively
   auditable; expire a claim before attempt start and verify it safely requeues.
4. Test success, retryable error, provider `Retry-After`, definite terminal error and ambiguous
   acknowledgement for every enabled concrete adapter.
5. On definite terminal error, verify the route cursor advances on the same logical row only after
   authority/policy re-proof. On ambiguity, verify no cross-channel failover occurs.
6. Verify webhook and agent receivers observe the stable idempotency key. Slack/Teams ambiguity
   must stop for manual reconciliation rather than assume receiver deduplication.

### 6. Prove lifecycle, analytics and Layer 6 handoff

1. Submit idempotent viewed, ignored, accepted and executed transitions through a properly scoped
   client; trigger expiry through the engine lifecycle sweep. Reject invalid transitions or
   cross-tenant identifiers.
2. Compare `DeliveryResult` output with the outbox, attempt and lifecycle ledgers.
3. Verify transport/lifecycle counts, channel mix, attempts, deferrals, latency, engagement and
   recipient-fatigue analytics from known fixtures.
4. Verify Layer 6 receives the typed lifecycle facts in its learning batch without obtaining
   delivery-control authority.

### 7. Prove tenant and operator controls

1. Test exact-agent `delivery.read` API-key selection, self-bound context PUT/GET, scoped API inbox
   and receipts separately from owner-only credential operations. Raw `/v1/signals*` must return
   authenticated `410 Gone`.
2. Verify tenant isolation for destinations, presence, results, attempts, dead letters, replay and
   analytics.
3. Exercise owner-only dead-letter inspection/replay. Uncertain physical evidence and legacy rows
   must require explicit duplicate-risk acknowledgement while preserving logical identity and
   historical attempts.
4. Run provider outage, credential rotation, worker restart and alert/escalation drills.

## Stop and rollback conditions

Stop outbound workers for the affected tenant/channel if tenant isolation, authority re-proof,
claim fencing, quota correctness, ambiguity handling or secret decryption fails. Disable the route
through configuration before attempting a schema downgrade. Preserve outbox, attempt and lifecycle
ledgers for audit; do not delete uncertain rows. Resume only after the failed invariant has a
reproducible test and the queued work has been revalidated against current Layer 5 authority.

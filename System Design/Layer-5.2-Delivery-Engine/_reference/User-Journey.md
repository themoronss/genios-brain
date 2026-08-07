# Layer 5.2 delivery user journey

This is the authoritative active journey. It starts with an approved Layer 5 `ExecutionObject`,
not with a card, channel request or generic notification payload.

## Main journey

1. **Layer 5 commits the work.** It creates and persists an `ExecutionObject` containing the
   commitment, owner, actions, deadline, business priority, communication intent and narrowest
   source-derived visibility.
2. **A card may be linked as a read model.** The card presents grounded execution facts and actions,
   but cannot authorize outbound transport by itself.
3. **The production materializer receives an eligible execution event.** For initial execution or
   `execution.reminded`, it reconstructs the stored `ExecutionObject` and rejects identity/lineage
   mismatch.
4. **Visibility and current delivery context are loaded.** V2 carries the source ACL; v1 re-derives
   it from immutable reasoning context or fails closed. Layer 5.2 reads tenant/user preferences,
   active directory seats, registered destinations and non-expired presence/busy context.
5. **Audience is resolved now.** The resolver selects a current active event target, registered
   agent, current manager, active owner/team or deterministic active-admin fallback within that
   visibility ceiling. Participant/private seats must match source-principal email.
6. **Channel, destination, format and queue class are planned.** Context surface, registered
   capability and one of five delivery priority classes produce an ordered route ladder. Concrete
   v1 channel/interrupt hints are not treated as authority.
7. **Timing, interruptibility and policy are composed.** Each admission check returns `SEND`,
   `DEFER` or `SUPPRESS`; first suppress wins, latest deferral binds. Only qualifying critical chat
   delivery may interrupt a non-busy recipient.
8. **One logical delivery is persisted.** `DeliveryObject` v2 data, execution lineage, recipient,
   destination, format, priority, route ladder and dedupe identity are written to one outbox row.
9. **A worker claims and re-proves it.** A time-bounded fenced claim prevents concurrent completion.
   The worker rechecks execution liveness/authority and atomically reserves hourly and daily
   attention capacity. A deferral spends neither provider attempt nor final quota.
10. **The selected unit attempts transport.** The physical attempt is appended before/around the
    adapter call in the same transaction as quota reservation and completes as success, retryable
    failure, definite terminal failure or unknown acknowledgement, preserving HTTP/provider
    metadata where available.
11. **Retry or recovery follows the outcome.** Retryable failure uses bounded backoff and
    `Retry-After`. Definite terminal failure may advance the route cursor on the same logical row
    after another authority/policy check. Unknown acknowledgement never cross-channel fails over.
12. **Transport result becomes a typed projection.** `DeliveryResult` reports the stable state while
    attempt history remains independently auditable.
13. **Recipient lifecycle may continue.** A properly scoped client submits idempotent `viewed`,
    `ignored`, `accepted` or `executed` evidence; the tracker validates and appends the transition
    separately from transport state. Engine lifecycle sweeping owns expiry.
14. **Evidence serves operations and learning.** Results, inbox, attempts, dead letters and
    analytics are exposed through tenant-scoped APIs. Typed lifecycle facts enter the Layer 6
    feedback batch; they do not grant Layer 6 delivery authority or prove business success by
    themselves.

## Branch behavior

| Situation | Required behavior |
|---|---|
| Quiet hours, focus/busy state or future safe window | Defer without consuming a physical attempt; re-evaluate all current authority/context later |
| Recipient/manager changed | Resolve the current active directory; never page an inactive historical target |
| Execution closed, cancelled or no longer authorized | Cancel/suppress before send; fallback cannot revive it |
| No registered agent route for agent audience | Fail visibly/dead-letter; do not silently redirect the agent payload to a human inbox |
| Participant/private evidence | Require a matching active seat email and authenticated recipient-scoped product route; do not use shared/external push or an unverified agent principal |
| Definite terminal adapter failure | Re-prove authority and advance to the next eligible route on the same logical row |
| Ambiguous adapter acknowledgement | Preserve unknown attempt, do not cross-channel fail over |
| Claim expires during processing | Fence stale worker; make the uncertain attempt observable instead of silently resending |
| Hourly/daily quota full | Atomically defer to a later window; concurrent workers share PostgreSQL authority |
| Pending or failed-terminal legacy row at 0046 cutover | Mark reconciliation-required; pending work terminalizes without sending; owner replay needs explicit duplicate-risk acknowledgement |
| Duplicate materialization | Stable dedupe/unique identity resolves to the existing logical delivery |
| Invalid or repeated lifecycle receipt | Reject invalid transition; make a valid repeated receipt idempotent |
| Email requested | Report unavailable; do not simulate success through a generic surface |

## External journey boundary

Slack, Teams, webhook and agent transports require real tenant credentials/endpoints. Dashboard,
extension, mobile, application and in-app routes require their authenticated clients to render and
publish trustworthy presence/lifecycle receipts. Email and native mobile/system push require new
provider lifecycles. These integrations sit after the engine seam and are tracked in the
[production runbook](Bugs-Runbook-and-Gaps.md).

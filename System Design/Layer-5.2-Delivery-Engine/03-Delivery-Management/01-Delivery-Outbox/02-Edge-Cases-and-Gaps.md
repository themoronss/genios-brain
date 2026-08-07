# Edge cases and gaps

- **Crash before commit:** no logical row or provider call exists; a later materializer run may
  retry the deterministic insert.
- **Crash after materialization:** the durable queued row remains claimable; no adapter has yet
  been called.
- **Crash after attempt start/provider call:** recovery treats the exact unfinished attempt as
  ambiguous. It does not invent a definite failure or automatically spread the same message to a
  non-idempotent fallback.
- **Expired claim without a started attempt:** the row can be safely requeued. An expired claim
  with attempt evidence follows bounded ambiguity recovery and fencing rules.
- **Concurrent materializers:** the per-tenant advisory lock and unique `(org_id, dedupe_key)`
  identity permit one logical winner.
- **Concurrent drainers:** `SKIP LOCKED`, claim tokens and append-only attempt identity prevent two
  workers from owning the same physical attempt.
- **Stale intent:** initial work is rejected after progress/reminder events; superseded reminder
  events are filtered before materialization and rechecked at final send.
- **Recipient, ACL or credential change while queued:** a safely mutable row is refreshed before
  any ambiguous attempt. Once ambiguous/delivered evidence exists, automatic rerouting is refused.
- **Legacy rows:** every pre-v2 queued/in-flight row, including `attempts=0`, and every historical
  terminal failure is marked `legacy_reconciliation_required`. Only owner replay with explicit
  duplicate-risk acknowledgement can clear it.
- **Exactly-once limit:** the database provides one logical row and one fenced attempt owner, but
  an external timeout can still hide a successful provider action. Stable receiver idempotency or
  manual reconciliation is therefore required; the system does not claim network exactly-once.

## Remaining production evidence

1. Rehearse migration `0046` against a populated pre-upgrade PostgreSQL copy while all legacy
   producers/drainers and autoscaling are quiesced.
2. Prove materializer dedupe, `SKIP LOCKED`, fencing, claim expiry, quota rollback and replay under
   real multi-worker contention.
3. Exercise 2xx, terminal 4xx, 429, 5xx, timeout and lost-ack behavior with each configured
   provider/receiver, then document operational reconciliation ownership.

# Policy and decision

Scheduling has two transaction boundaries:

1. **Retention transaction:** lock the tenant root first, then due memories/objects, mark them
   expired and append `temporary_ttl_elapsed` transitions. This commits before analysis begins.
2. **Learning-run transaction:** lock tenant root, ensure/lock policy, claim the UTC-week run, load inputs,
   persist sanitized input rejections, build/preflight/persist or safely re-evaluate held proposals,
   append their per-run evaluations, publish allowed targets and complete the run summary.

The unique `(org_id, period_start)` run identity makes completed work idempotent across retries and
replicas. A failed row is reclaimed by compare-and-set to `started`, increments `attempt_count` and
clears `last_error`. A completed row returns its stored result as `already_ran=true`.

If learning is disabled, retention remains committed and the function returns without claiming a
new analytical run. The claimed transaction pins the policy revision; policy updates serialize
against the shared lock.

Both transactions use the platform tenant mutation root. Normal writers hold `orgs FOR SHARE`;
account reset/delete holds it `FOR UPDATE`, then erases children. A failed-run audit transaction
also reacquires tenant then policy and refuses to recreate authority if erasure already removed the
organization.

An immutable proposal repeated in a later claimed week is not automatically discarded. If its
locked current state is Observed or Candidate, it is re-evaluated with that run's frozen current
policy and evaluation time. Candidate cannot regress to Observed. Any object already past Candidate
is a duplicate lifecycle no-op, so review, published, temporary and terminal records cannot reopen.

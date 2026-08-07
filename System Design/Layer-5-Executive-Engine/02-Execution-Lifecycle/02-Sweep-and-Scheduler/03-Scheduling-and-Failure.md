# Scheduling and failure behavior

The existing platform heartbeat invokes the Executive sweep; a second cron authority is not
introduced. Repeated runs must be safe after crash or retry.

Database work is tenant-scoped. One failed commitment must remain observable without changing the
deterministic rules for others. Transport failures are returned by Layer 5.2 and are not relabeled
as execution outcomes.

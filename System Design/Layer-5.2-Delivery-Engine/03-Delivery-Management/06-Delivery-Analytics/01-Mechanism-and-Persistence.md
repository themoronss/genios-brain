# Mechanism and persistence

Metrics are computed from durable outbox/result facts, with counted status/channel buckets and integer p50/p95 latency. Suppressed/deferred/cancelled are not fabricated into provider failure.

All writes remain organization-scoped and reason-coded so retry/recovery cannot erase the original
attempt.

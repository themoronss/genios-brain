# Mechanism and persistence

A transport attempt increments only when an adapter is invoked. Retryable failure schedules the next attempt; the bounded ladder eventually produces terminal failure.

All writes remain organization-scoped and reason-coded so retry/recovery cannot erase the original
attempt.

# Mechanism and persistence

Stable delivery/card keys combine with database uniqueness. Executive reminder/escalation events use `exec:<execution_id>:<event_id>` so replay is idempotent.

All writes remain organization-scoped and reason-coded so retry/recovery cannot erase the original
attempt.

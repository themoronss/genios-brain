# Part 2 · Execution Lifecycle

This part describes the running state machine after an `ExecutionObject` exists.

| Subpart | Purpose |
|---|---|
| [State Machine](01-State-Machine/README.md) | Legal commitment states, terminality and guarded transitions |
| [Sweep and Scheduler](02-Sweep-and-Scheduler/README.md) | Idempotent planning plus lifecycle processing |
| [Delivery Handoff](03-Delivery-Handoff/README.md) | Grounded events cross into Atlas Layer 5.2 |
| [Outcome Handoff](04-Outcome-Handoff/README.md) | Immutable evidence reaches Atlas Layer 6 |
| [Audit and Race Safety](05-Audit-and-Race-Safety/README.md) | Claims, ownership, expiry and duplicate protection |

The lifecycle is separate from the immutable contract: a commitment's meaning does not change when
its current state changes.

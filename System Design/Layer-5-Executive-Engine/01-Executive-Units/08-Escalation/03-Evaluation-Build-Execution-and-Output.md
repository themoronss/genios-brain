# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator emits at most one due rung per guarded processing step. The builder grounds the escalation and records its synthetic identity.

## Executor / Output

The Delivery bridge performs transport; retries cannot create a second logical escalation event.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

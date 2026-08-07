# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator checks ownership and confidence floors. The builder freezes the communication plan onto `ExecutionObject`.

## Executor / Output

Destination resolution, retry and fallback belong to Delivery. This unit outputs intent, not a provider call.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

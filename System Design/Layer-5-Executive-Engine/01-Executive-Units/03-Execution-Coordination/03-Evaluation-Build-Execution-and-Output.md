# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator rejects out-of-order or foreign completion. The store records the accepted change and returns the refreshed projection.

## Executor / Output

No Delivery event is emitted for blocked work; escalation is likewise withheld until the relevant work is actionable.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

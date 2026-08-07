# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator may emit, wait or decline. The builder includes only stored grounding facts and the frozen routing plan.

## Executor / Output

The executor records a queued event; the Delivery bridge later records delivered or failed transport separately.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator either returns a named refusal or constructs a frozen contract that survives serialization round-trip validation.

## Executor / Output

Persistence is a separate operation in `execution_store.py`; construction alone performs no external effect.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

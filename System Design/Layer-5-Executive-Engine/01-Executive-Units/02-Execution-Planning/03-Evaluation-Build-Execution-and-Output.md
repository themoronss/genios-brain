# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator checks that every dependency can be resolved and every external-effect action has the required approval semantics. The builder emits frozen actions.

## Executor / Output

The unit outputs a plan; it does not assign provider destinations or send work.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator rejects races and stale transitions. Accepted writes update current state and append audit evidence atomically.

## Executor / Output

Read APIs expose summaries and detail without becoming a second source of lifecycle truth.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

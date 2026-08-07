# Evaluator, Builder, Executor and Output

## Evaluator / Builder

The evaluator returns a typed refusal for malformed, unsupported or unsafe work. Successful output preserves source lineage for the builder and later audit.

## Executor / Output

No executor performs an external effect here. The unit's only side effect is its explicit output to Execution Planning.

## Failure posture

A rejected or incomplete input returns a typed, auditable result. The unit does not silently skip
an invariant and does not upgrade uncertainty into authority.

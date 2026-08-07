# Input, Validator and Retriever

## Input

`ExecutionContext`, declared play steps and explicit planning time.

## Validator

Validation rejects invalid step identifiers, dependency references and action shapes. Retrieval uses only the frozen play/context supplied to the planner.

## Retriever

No current graph or provider lookup occurs while hashing the plan. That keeps replays stable and prevents queue-time transport state from changing commitment identity.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

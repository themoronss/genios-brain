# Input, Validator and Retriever

## Input

successful interpretation, planned actions, assignment, communication plan and escalation ladder.

## Validator

The validator rechecks cross-component invariants: valid actions/dependencies, permitted effects, required ownership and consistent clocks.

## Retriever

Every input comes from an earlier deterministic unit; the builder does not query live provider state or invent missing plan content.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

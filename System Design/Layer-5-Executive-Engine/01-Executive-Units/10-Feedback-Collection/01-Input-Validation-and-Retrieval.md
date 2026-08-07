# Input, Validator and Retriever

## Input

execution state, action progress, observed business outcome, cancellation cause and attention history.

## Validator

Validation requires a terminal or outcome-eligible execution and tenant-scoped evidence. Retrieval includes action, reminder and escalation history.

## Retriever

The collector uses actual execution facts, not card reactions alone.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

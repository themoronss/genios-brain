# Input, Validator and Retriever

## Input

stored `ExecutionObject`, current action states, actor identity and explicit time.

## Validator

The validator checks the requested action exists, is not already terminal and belongs to the target execution. Store reads retrieve current action and dependency state transactionally.

## Retriever

Effective owner checks happen at the write boundary, not only in an API client. The dependency graph comes from the immutable plan.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

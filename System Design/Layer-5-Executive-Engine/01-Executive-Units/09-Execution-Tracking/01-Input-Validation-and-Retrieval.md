# Input, Validator and Retriever

## Input

guarded transition/action commands, execution identity, actor and explicit time.

## Validator

Commands validate tenant, owner/authority, current state and requested edge. Retrieval locks or checks current durable state at the write boundary.

## Retriever

API authorization is defense in depth; the store remains the transition authority.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

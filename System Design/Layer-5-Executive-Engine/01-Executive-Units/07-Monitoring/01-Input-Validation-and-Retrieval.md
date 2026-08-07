# Input, Validator and Retriever

## Input

stored execution/actions/events/outcomes plus current observation time.

## Validator

Validation keeps execution and evidence tenant-scoped. Retrieval reads durable action states, event history and post-creation outcome evidence.

## Retriever

No delivery receipt is treated as proof that the business action succeeded.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

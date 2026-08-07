# Input, Validator and Retriever

## Input

`GuardInput` plus current facts retrieved through the store/injected authority sources.

## Validator

Input validation requires explicit organization, execution identity and evaluation time. Retrieval happens at processing time and includes authority, subject, owner and post-creation evidence.

## Retriever

Only evidence after commitment creation can prove resolution; the event that originally triggered a decision cannot auto-complete day zero.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

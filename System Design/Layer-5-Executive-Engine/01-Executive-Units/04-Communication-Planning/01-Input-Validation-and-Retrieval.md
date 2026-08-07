# Input, Validator and Retriever

## Input

execution context, planned actions, band/confidence and an injected seat directory.

## Validator

The validator requires a tenant-scoped subject and eligible owner context. Static or PostgreSQL seat directories retrieve explicit owner/reporting facts.

## Retriever

Resolution follows ordered rules and returns reason codes. It never chooses a cross-tenant seat and does not use physical row order as policy.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

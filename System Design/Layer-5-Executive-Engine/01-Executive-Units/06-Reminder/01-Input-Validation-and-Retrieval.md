# Input, Validator and Retriever

## Input

current execution/action progress, deadline window, reminder history and explicit time.

## Validator

The validator accepts only open, actionable work. Store retrieval brings prior reminders, current state, deadline and evidence into the same processing pass.

## Retriever

A live guard runs again before handoff, so a retry window cannot deliver a reminder after the subject resolves.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

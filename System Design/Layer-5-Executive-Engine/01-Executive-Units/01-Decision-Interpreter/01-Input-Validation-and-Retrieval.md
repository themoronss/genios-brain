# Input, Validator and Retriever

## Input

Layer 4 decision, capability/play metadata, organization identity and an explicit observation time.

## Validator

The validator checks required identity, supported execution type, actionability and the human gate. The parser reads only supplied decision/play fields.

## Retriever

The metadata loader receives organization, subject, capability/play lineage and explicit time from the caller. It does not query live delivery state.

## Edge cases

- Cross-tenant identifiers are never accepted as implicit context.
- Evaluation time is explicit and timezone-aware; wall-clock reads are not hidden in pure logic.
- Missing facts degrade to a named refusal, hold or unknown state rather than an invented value.

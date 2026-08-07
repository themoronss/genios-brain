# Input, Validator and Retriever

## Input / Validator

Input is the immutable proposal produced by Outcome Analysis: a capability/play/ACL cohort with
exact execution outcomes, independent execution refs, source traces, first/last seen times and
ExecutionObject-derived visibility. Neutral/unproven outcome labels remain separate.

## Retriever

The unit calls the deterministic Outcome Analysis function over the same frozen batch. It copies the
complete parent value/evidence/ACL and records `metadata.derived_from=<outcome learning id>`.

It does not query executions/outcomes again, add observations, treat card/delivery engagement as
success, or replace missing outcome coverage with a generated recommendation.

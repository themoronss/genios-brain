# Input, Validator and Retriever

## Input / Validator

The v2 contract validates tenant/unit/target/subject, frozen value, non-negative evidence counts,
`positive + negative <= observations`, 0–10,000 basis points, sorted unique source/independent/trace
refs, aware seen times, `observed_at == last_seen_at`, complete visibility shape/derivation,
lineage-complete boolean and target/expiry consistency.

Runtime requires expiry; all other targets forbid it. Knowledge unit requires Knowledge Suggestion.
Independent observations cannot exceed observations.

## Retriever

Policy is loaded tenant/policy-key scoped, optionally under a share lock, and its immutable revision
is pinned on the run/object. Current review reloads policy so revoked consent and current freshness
are enforced before approval.

Validation does not query or mutate a brain. Stored objects are rehydrated, round-tripped and checked
against stored learning ID/semantic hash before review or rollback state mutation.

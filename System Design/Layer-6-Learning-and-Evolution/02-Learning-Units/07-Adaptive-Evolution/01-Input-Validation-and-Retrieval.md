# Input, Validator and Retriever

## Input / Validator

Input is an explicit Preference Learning proposal whose category is one of `current_priority`,
`notification_style`, `execution_preference`, or `runtime_personalization`. Arbitrary preference
categories and implicit short-term observations cannot enter this unit.

## Retriever

The unit deterministically reruns/uses Preference Learning over the same frozen batch, filters the
closed categories, and copies the parent value, evidence, first/last seen times, trace, ACL,
lineage-complete flag and subject principal. The parent learning ID is recorded in metadata.

No mutable source reread or additional observation occurs. Actor scoping established by Preference
Learning remains intact, including its private resolved-subject ACL and fail-closed lineage flag.

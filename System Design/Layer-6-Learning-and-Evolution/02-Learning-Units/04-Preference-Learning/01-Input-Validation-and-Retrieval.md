# Input, Validator and Retriever

## Input / Validator

Preference key, value, scope and category must be present together. Scope is exactly `user` or
`organization`; user scope requires actor identity; organization scope requires the immutable
`organization_authorized` flag set by the authenticated writer. Values are frozen and canonically
serialized, so equivalent structured JSON has one identity regardless of key order.

## Retriever

The selector retrieves preference data only from the latest explicit canonical feedback revision.
The feedback API accepts structured preference only with an explicit edit action, validates shape,
requires owner authentication for organization scope and stores the authority flag outside the
caller-controlled preference object.

Actor/seat identity, resolved subject principal, exact card independence, ExecutionObject trace and
source visibility accompany the fact. Silence, implicit behavior and malformed preference payloads
do not become preference evidence.

User scope requires exactly one resolved subject principal across the cohort. Preference Learning
intersects the source ACL with that subject by constructing `private + [subject]`; public or
organization-visible source evidence therefore cannot widen a personal preference. If resolution
fails or the source ACL does not admit the subject, the derived lineage is incomplete and preflight
rejects the proposal before value persistence.

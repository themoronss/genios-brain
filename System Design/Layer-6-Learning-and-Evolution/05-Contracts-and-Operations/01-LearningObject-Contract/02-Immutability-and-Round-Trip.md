# Immutability and round-trip

Values/evidence are frozen and canonicalized; aware timestamps and basis-point/count ranges are
validated. Semantic serialization round-trip must preserve LearningObject identity.

Database rehydration is not a blind JSON parse. Before review, transition, expiry or rollback, the
store reconstructs the contract, verifies its round trip, then compares tenant, content-derived
`learning_id` and semantic hash with the persisted projection. Mismatch fails before state
mutation.

Lifecycle state is stored separately so review/publication/rollback never rewrites the proposal
that evidence supported. Migration 0047 additionally checks that v2 payload identity/ACL/lineage
fields match their indexed columns.

Policy revision and evaluation time may legitimately change while the semantic evidence remains
identical. A later claimed run therefore reuses the verified object only if it is still Observed or
Candidate, appends a new evaluation decision, and never rewrites the payload. Candidate is not
allowed to regress to Observed; later lifecycle states are not reopened by duplicate production.

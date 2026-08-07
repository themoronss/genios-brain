# Input, Validator and Retriever

## Input / Validator

The fact must have `explicit_memory=true`, kind `temporary_memory`, a structured mapping value,
aware `occurred_at`, and `expires_at` later than both occurrence and current evaluation. It must also
carry actor, source-stable event/trace/independence IDs, complete visibility and lineage.

## Retriever

The owner-only create API bounds the value (16 KiB, 512 nodes, depth 12), derives event/trace/
independence IDs from tenant + authenticated actor + caller `source_ref`, assigns a private ACL to
the resolved principal and performs preflight before storing the value in `learning_event_inbox`.

On retry, the API reloads the existing inbox row and requires its full canonical semantics to match.
A reused source ref with different subject/value/expiry/ACL returns conflict instead of creating a
second memory. Ordinary enterprise events and implicit recollection cannot enter this unit.

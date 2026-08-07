# Input, Validator and Retriever

## Input / Validator

`DeliveryFact` validates delivery/channel/status identifiers, aware creation and optional lifecycle
timestamps, non-negative attempts/deferrals, optional execution/trace/independence IDs, typed ACL
and lineage completeness. Supported current statuses are queued, deferred, delivered, viewed,
ignored, accepted, executed, failed, expired, suppressed and cancelled.

## Retriever

The selector includes a tenant delivery when its outbox row was created inside the source window
**or** it has at least one lifecycle event inside that window; in both cases creation must be no
later than the evaluation time. This prevents a long-running delivery created before the window
from disappearing when it recently fails, defers or receives engagement. It then joins the exact
execution ID and verifies its frozen execution hash.

For every included delivery it reconstructs the latest lifecycle status/reason and first delivered,
viewed, ignored, accepted, executed and expired timestamps from `delivery_events` at or before the
evaluation time. It also carries the timestamp of the latest lifecycle event itself. Therefore a
failed, deferred, suppressed or cancelled row has an authoritative recent observation even when it
has no delivery/engagement receipt. Attempts and deferrals are counted with the same as-of cutoff.

Execution reasoning run supplies trace, execution ID supplies independence and the verified
ExecutionObject supplies visibility. Missing hash, mismatched execution or malformed lifecycle
becomes a sanitized rejection; client impressions are not inferred.

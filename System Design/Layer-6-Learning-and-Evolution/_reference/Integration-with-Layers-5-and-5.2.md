# Integration with Layers 5 and 5.2

```text
Layer 5 immutable ExecutionObject + append-only execution outcomes/events
Layer 5.2 logical outbox + physical attempts + delivery lifecycle/receipts
canonical feedback revision + normalized enterprise source lineage
structured learning inbox
                              ↓ exact tenant/time/identity/ACL verification
                    Layer 6 LearningObject v2
                              ↓ validation + governance
Organization | Behavior | Adaptive | Runtime | Metrics | Knowledge suggestion
```

## Exact Layer 5 handoff

Layer 5 owns the business commitment and the immutable `ExecutionObject`. Layer 6 reconstructs the
bounded outcome history as of evaluation time and verifies object identity on rehydration. Success
is positive; expired/human-cancelled work can be negative; `completed_unproven` and world/system
cancellation remain neutral. Activity cannot masquerade as verified business value.

Outcome Analysis, Recommendation Learning and Knowledge Evolution use those labels for different
purposes without mutating the original outcome. The source execution ID is also the independence
boundary, so several derivative rows from one commitment cannot inflate support.

## Exact Layer 5.2 handoff

Layer 6 reconstructs each delivery from the append-only event and attempt ledgers as of the pinned
evaluation time. It joins the outbox/card to the exact persisted execution, validates the
`ExecutionObject` ID and round trip, and additionally checks the frozen execution hash. It carries
the execution trace and narrowest visibility into the `DeliveryFact`. Cohort inclusion is based on
outbox creation **or** any lifecycle event inside the source window, so a delivery created earlier
is still selected when it has recent failure, deferral or engagement; all reconstructed facts remain
clipped to the pinned evaluation time.

Transport and attention remain different truths:

- only `status=failed` before the first durable `delivered_at` is transport-negative;
- an ACCEPTED → FAILED downstream execution transition remains transport-delivered and belongs to
  Layer 5 Outcome Analysis for business/execution quality;
- queued, deferred, suppressed and cancelled are not fabricated failures;
- delivery, view, ignore, accept and execute are counted only from durable timestamps;
- the latest lifecycle event is also the freshness clock for failed, deferred, suppressed and
  cancelled rows that have no receipt;
- a later terminal state does not erase a prior receipt;
- attempts, deferrals and latency are calculated from the durable historical state, not a mutable
  latest-row guess.

Performance Optimization groups results by channel **and ACL cohort**, then emits measurement. It
does not retry a delivery, choose a route or turn metrics into a decision authority.

## Feedback and preference handoff

The canonical feedback revision is joined to its exact card/execution lineage. Actor and subject
principal stay distinct. A structured preference is accepted only on an `edit`, with closed fields
and canonical finite JSON. User scope remains actor-scoped; Organization scope requires owner
authority frozen in a dedicated server-owned revision column. Migration-backfilled false authority
can be recovered by a byte-identical owner resubmission, which creates a new authorized revision.

The dashboard writes terminal `run_play`, `do_it_myself` and `wrong` judgments into that canonical
verdict/revision ledger atomically with the card/signal and audit transition. Exact retries do not
append; a changed judgment increments the version. `wrong:bad_timing` is still a versioned verdict,
but Feedback Learning counts it in timing/neutral rather than negative quality. Dashboard requeue
and dashboard/extension snooze remain card lifecycle/timing audit events and are intentionally
excluded from Layer 6's verdict cohort.

Both dashboard and intelligence feedback writers take tenant `orgs FOR SHARE`, then graph-version
`FOR SHARE`, then the actionable card/signal `FOR UPDATE` before audit/verdict writes. This shared
tenant → graph → card order serializes the Layer 5.2/L6 handoff against account erasure.

For a user-scoped preference, the source execution ACL is necessary but not the output ACL. Layer 6
resolves one subject, verifies that subject can view the source, then caps the proposal to
`private + [subject]`. Failed resolution or source exclusion is rejected before value persistence;
Behavior and Adaptive children copy the cap unchanged.

## Enterprise-event and direct-memory handoff

Graph observations are accepted only when `graph_source_refs` resolves to durable source events;
the narrowest source ACL wins. Approved structured external producers can use
`learning_event_inbox`, whose tenant/actor/source reference is idempotent and whose event includes
trace, visibility and independence identity. Direct Runtime memory uses this same seam with a
mandatory lease and bounded payload. Runtime cannot be configured for review: API and database
policy fail closed, so a valid lease publishes immediately and later expires.

## Closed and open feedback loops

The older calibration path writes `rule_mutes` and bounded `lvl3_config.rule_offsets`; Layer 4
already consumes both through a data boundary.

Generic `learned_brain_entries` and `temporary_memories` are now correctly governed, versioned,
visible and rollback/expiry-aware, but no lower layer consumes them yet. Each future target reader
must define typed selection, tenant/ACL checks, snapshot identity, TTL, rollback behavior,
deterministic fallback, rollout control and a topology-safe data/injection seam. A raw generic JSON
read is not an acceptable integration.

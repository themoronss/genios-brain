# Inputs and context

The unit receives a candidate plus one flattened `DeliveryPolicy` for its exact
organization/recipient/channel. The policy contains:

- tenant delivery kill switch or time-bounded hold;
- active channel registration;
- channel minimum band;
- current recipient-seat activity; and
- recipient channel opt-out.

Before a candidate reaches this ordinary preference gate, the orchestrator enforces the immutable
`ExecutionObject` v2 source visibility. At the final provider boundary it reconstructs the same
execution, locks current directory/authority rows and repeats liveness, hash, reminder-currentness
and visibility-safe route planning. A stale or widened route never becomes a permissive policy
default.

Preference specificity is resolved before evaluation, and the unit never reads message content.
Execution liveness is a separate authority predicate re-proved immediately before send.

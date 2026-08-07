# Input and selection context

The selector receives an organization identifier, a timezone-aware evaluation time and a bounded
observation window (28 days by default). Every query is constrained by organization and by
`since <= source_time <= evaluation_time`.

It retrieves five durable source classes:

- the latest immutable `card_feedback_revisions` entry per canonical feedback verdict, joined to
  its card and exact `ExecutionObject`;
- `execution_outcomes`, joined on execution, decision, capability and play identity;
- active `graph_observations`, bound through `graph_source_refs` to exact `source_events`;
- explicit normalized events from `learning_event_inbox`; and
- `delivery_outbox` rows with delivery events and attempts reconstructed as of the evaluation time,
  joined to the exact execution identity and frozen execution hash.

Facts retain source reference, trace, independence identity, visibility and lineage completeness.
User preference principals resolve from authenticated actor/seat/owner identity. Organization
preference authority comes from the server-frozen feedback revision flag, not preference JSON.
The selector exposes only canonical feedback revisions to learning: terminal dashboard judgments
version that ledger in the same card transaction. `wrong:bad_timing` is present as a canonical
revision for later timing/neutral classification; dashboard requeue and dashboard/extension snooze
remain lifecycle/timing audit events outside the canonical verdict cohort.

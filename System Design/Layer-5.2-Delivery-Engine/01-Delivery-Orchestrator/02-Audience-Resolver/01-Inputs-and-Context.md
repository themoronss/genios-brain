# Inputs and context

The resolver receives:

- `executions.assignee`, the Layer 5 work-owner seed;
- requested audience (`owner`, `team`, `manager`, `executive`, `agent` or `admin_queue`);
- reminder detail such as `target_audience` and an optional concrete `target_seat`;
- the immutable `ExecutionObject` v2 `visibility` inherited from the exact selected source
  evidence;
- current active `org_seats`, including email principal, manager relationships and roles; and
- for agent intent, an active org-scoped registry entry whose `allowed_actions` contains the exact
  `delivery.read` scope.

Audience intent can come from the frozen execution or a frozen reminder escalation step. It is
not permission to trust an obsolete seat blindly: role audiences are resolved against the current
directory when delivery is materialized.

Stored execution v1 payloads predate the visibility field. At materialization and final-send
boundaries the engine re-derives their ACL in memory from the immutable reasoning-context source
manifest without changing the stored v1 identity/hash. An explicitly empty pre-visibility manifest
retains its historical organization default; a missing context row, malformed ACL or unresolved
selected lineage narrows to an empty private audience instead of widening access.

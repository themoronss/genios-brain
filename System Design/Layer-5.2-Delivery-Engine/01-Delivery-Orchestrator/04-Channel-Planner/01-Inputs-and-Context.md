# Inputs and context

The planner receives the router’s first destination, the execution’s immutable priority and
confidence, live busy/focus context, and a grounded execution-initial or execution-reminder
source payload.

The concrete route fields carried by the legacy `ExecutionObject` contract are not authoritative:
new materialization ignores its `channel_id` and `interrupt` values. The audience class and work
owner are seeds; current Layer 5.2 state chooses the actual delivery channel.

Known channels are Slack, Teams, signed webhook, signed agent webhook, and the `in_app`,
`dashboard`, `api`, `application`, `extension` and `mobile` pull surfaces. There is no registered
native email channel.

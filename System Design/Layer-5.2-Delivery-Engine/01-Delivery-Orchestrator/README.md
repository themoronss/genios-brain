# Part A · Delivery Orchestrator

The Atlas gives Layer 5.2 one question: **how should this execution reach the world?** The
production materializer accepts a validated, open `ExecutionObject` (or one of its persisted
reminder events) and creates one durable, execution-bound `DeliveryObject`. A card is a
presentation/read model; it is not independent outbound authority.

`ExecutionObject` v2 carries the source-derived visibility ceiling. The resolver matches
participant/private principals against current seat email, refuses an unverified agent principal,
and limits constrained content to authenticated recipient-scoped product surfaces. This is a
permission boundary, not a recipient preference.

## The seven decisions

| # | Atlas decision | Runtime status | Decides | Folder |
|---|---|---|---|---|
| 1 | Delivery Context Resolver | Active core; client presence is integration-dependent | What the recipient is doing and which policy/timing facts are current | [01](01-Delivery-Context-Resolver/README.md) |
| 2 | Audience Resolver | Active | Which current human seat or registered agent is the recipient | [02](02-Audience-Resolver/README.md) |
| 3 | Destination Router | Active | The ordered, audience-safe route ladder | [03](03-Destination-Router/README.md) |
| 4 | Channel Planner | Active for registered adapters and pull surfaces | Concrete channel, channel class, format and interrupt flag | [04](04-Channel-Planner/README.md) |
| 5 | Timing & Interruptibility | Active | `SEND` now or `DEFER` to a humane window | [05](05-Timing-and-Interruptibility/README.md) |
| 6 | Delivery Policy | Active | Whether delivery is permitted or must be held/suppressed | [06](06-Delivery-Policy/README.md) |
| 7 | Priority Scheduler | Active | Which due delivery obtains a fenced worker claim next | [07](07-Priority-Scheduler/README.md) |

“Active” means the engine path is implemented and invoked. It does not claim that every external
provider or client is installed; target-specific deployment truth is recorded under
[the 11 Delivery Units](../02-Delivery-Units/README.md).

## Deterministic boundary

```text
open ExecutionObject + reminder event
  -> validate identity and semantic payload
  -> enforce inherited visibility; resolve current audience, presence and registered destinations
  -> freeze channel, format, priority class, interruptibility and route ladder
  -> insert one execution-bound outbox row + queued lifecycle event
  -> re-resolve policy/timing and re-prove authority at drain time
  -> adapter result + append-only delivery evidence
```

Layer 5 owns the commitment, actions, work owner, deadline, confidence and business priority.
Layer 5.2 uses the audience class and work owner only as routing seeds. It deliberately ignores
the legacy `ExecutionObject` concrete `channel_id` and `interrupt` values when creating a new
delivery. No model selects recipients, routes, timing, retries, rate limits or priority classes.

## Human and agent isolation

- Human audiences may use contextual/internal surfaces and registered human push adapters, but
  the `agent` channel is excluded.
- An agent audience resolves only to an active registry entry whose allowed actions contain
  `delivery.read`. Its API route additionally requires an active key for that exact agent with the
  same scope; the route ladder contains only signed `agent` push or authenticated `api` pull.
- Agent delivery never falls back to a human inbox. Missing agent identity or route is a durable
  materialization failure; exhausted transport becomes an operator-visible dead letter.

## Legacy containment

`enqueue_pending` and the old synchronous card-to-agent helper are retained only as dead code or
test compatibility; neither is an active Layer 5 materializer. The raw `/v1/signals*` poll,
artifact, claim and result routes authenticate their historical scopes and then return `410 Gone`
with the scoped delivery inbox replacement. Migration 0046 quarantines every pending legacy-card
row for owner reconciliation because an old worker could have POSTed before recording an attempt.
No legacy pending row drains automatically.

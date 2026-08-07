# Layer 5.2 · Delivery Engine

This folder is the implementation map for product **Layer 5.2** and the runtime package
`genios_engine/deliver/`. Its Atlas hierarchy is **7 Delivery Orchestrator decisions → 11
Delivery Units → 8 Delivery Management systems**.

> **Layer question:** How should an approved execution reach the world, safely and through the
> right destination?

## Non-negotiable boundary

- The active delivery path accepts a Layer 5 **`ExecutionObject` only**. Intelligence Cards are a
  read model linked to that execution; a card cannot independently authorize outbound delivery.
- `ExecutionObject` **v2** carries the narrowest visibility inherited from the exact Layer 1
  evidence selected by Layer 4. Participant/private evidence can reach only a matching active
  principal on an authenticated recipient-scoped surface; unresolved lineage fails closed.
- Layer 5 owns the commitment, work owner, actions, deadline, business priority and execution
  lifecycle. Layer 5.2 owns the current delivery audience/recipient, destination, channel,
  presentation, timing, interruptibility, retry and failover.
- Legacy route fields retained by `ExecutionObject` v2, and read from stored v1 objects, are
  semantic hints. Layer 5.2 re-resolves concrete channel and interrupt behavior from current
  presence, policy and registered capability.
- Layer 5.2 does not create new intelligence, reopen a business decision or mutate Layer 5's
  commitment.
- The stable outward result is a typed **`DeliveryResult`**. `DeliveryObject` is the internal
  Layer 5.2 projection persisted for transport and audit; it is not a second upstream input.

## Canonical tree

```text
Layer-5.2-Delivery-Engine/
├── 00-Overview.md
├── STATUS.md
├── 01-Delivery-Orchestrator/
│   ├── 01-Delivery-Context-Resolver/
│   ├── 02-Audience-Resolver/
│   ├── 03-Destination-Router/
│   ├── 04-Channel-Planner/
│   ├── 05-Timing-and-Interruptibility/
│   ├── 06-Delivery-Policy/
│   └── 07-Priority-Scheduler/
├── 02-Delivery-Units/
│   └── 01-Human/ ... 11-Slack-and-Teams/
├── 03-Delivery-Management/
│   ├── 01-Delivery-Outbox/
│   └── 02-Delivery-Tracker/ ... 08-Delivery-Object-Builder/
├── 04-Contracts-and-Operations/
└── _reference/
```

Parts 1–3 are the Atlas structure. Part 4 documents the contracts, persistence, API and
verification machinery that make those parts operable.

## Read order

1. [Overview](00-Overview.md)
2. [Status ledger](STATUS.md)
3. [Part A · Delivery Orchestrator](01-Delivery-Orchestrator/README.md)
4. [Part B · 11 Delivery Units](02-Delivery-Units/README.md)
5. [Part C · Delivery Management](03-Delivery-Management/README.md)
6. [Contracts and Operations](04-Contracts-and-Operations/README.md)
7. [Atlas alignment](_reference/Atlas-Alignment.md), [user journey](_reference/User-Journey.md),
   [scenarios](_reference/Intelligence-Card-Scenarios.md) and
   [production runbook](_reference/Bugs-Runbook-and-Gaps.md)

## Runtime identity

| Item | Current authority |
|---|---|
| Product layer | Layer 5.2 · Delivery Engine |
| Code package | `genios_engine/deliver/` |
| Internal import rank | `6` in `genios_engine/LAYERS.py`; not a product-layer number |
| Active input | Layer 5 `ExecutionObject` |
| Internal projection | `DeliveryObject` v2 + one logical outbox row |
| Output | `DeliveryResult` v2 + append-only attempt/lifecycle audit facts |
| Migrations | `0042_l6_delivery_gate.sql`, `0044_l52_atlas_delivery.sql`, `0046_l52_delivery_control_plane.sql` |
| API | `genios_engine/api/delivery_routes.py`, `genios_engine/api/channel_routes.py` |

The historical `l6` in migration/test filenames is retained for migration history. It refers to
the delivery subsystem now canonically identified as product Layer 5.2, not Atlas Layer 6
Learning.

## Delivery truth in one paragraph

The orchestrator resolves seven decisions, persists one logical delivery, and sends it through an
eligible unit. Physical attempts and lifecycle transitions are append-only. Attention reservation
and the `started` attempt commit atomically before a provider call. A definite terminal failure may
advance the route cursor on the same logical delivery after authority is re-proved; an ambiguous
acknowledgement never triggers cross-channel failover and may require an explicit owner risk
acknowledgement before replay. The typed result and lifecycle facts support APIs, analytics and
Layer 6 learning without turning transport acknowledgement into business-execution success.

Read [STATUS.md](STATUS.md) before interpreting “11 Delivery Units” as eleven deployed provider
integrations. The engine exposes all eleven architectural units, while several still require real
clients, credentials or providers.

[← System Design index](../README.md)

# Layer 5.2 · Delivery Engine

This folder is the live implementation map for product **Layer 5.2** and
`genios_engine/deliver/`. The package has internal import rank 6 only because it follows
`executive/`; that rank is not a product-layer number. The physical hierarchy mirrors the Atlas:
**Delivery Orchestrator → 11 Delivery Units → Delivery Management**.

> **Question:** How should an approved execution reach the world, safely and through the right
> destination?

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
│   ├── 01-Human/ ... 11-Slack-and-Teams/
├── 03-Delivery-Management/
│   ├── 01-Delivery-Tracker/ ... 07-Delivery-Object-Builder/
├── 04-Contracts-and-Operations/
└── _reference/
```

## Read order

1. [Overview](00-Overview.md)
2. [Status ledger](STATUS.md)
3. [Part A · Delivery Orchestrator](01-Delivery-Orchestrator/README.md)
4. [Part B · 11 Delivery Units](02-Delivery-Units/README.md)
5. [Part C · Delivery Management](03-Delivery-Management/README.md)
6. [Contracts and Operations](04-Contracts-and-Operations/README.md)
7. [Atlas alignment](_reference/Atlas-Alignment.md), [user journey](_reference/User-Journey.md),
   [card scenarios](_reference/Intelligence-Card-Scenarios.md) and
   [gaps/runbook](_reference/Bugs-Runbook-and-Gaps.md)

## Identity and boundary

| Item | Authority |
|---|---|
| Code package | `genios_engine/deliver/` |
| Product layer | Layer 5.2 |
| Internal import rank | 6 in `genios_engine/LAYERS.py` |
| Input | Layer 5 `ExecutionObject` / grounded delivery candidate |
| Output | typed `DeliveryResult` plus durable outbox/audit facts |
| Migrations | `0042_l6_delivery_gate.sql`, `0044_l52_atlas_delivery.sql` |
| API | `api/delivery_routes.py`, `api/channel_routes.py` |

Some pre-Atlas filenames still contain `l6`—for example `0042_l6_delivery_gate.sql` and
`test_l6_outbox.py`. They are retained for migration and test-history stability. They identify
product Layer 5.2 Delivery, not a second product Layer 6.

[← System Design index](../README.md)

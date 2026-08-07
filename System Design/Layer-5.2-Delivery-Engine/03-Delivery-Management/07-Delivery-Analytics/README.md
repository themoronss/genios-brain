# Delivery Analytics

**Engine status:** Built for durable Delivery Engine evidence. External surface telemetry and business attribution remain integrations.

Analytics deterministically aggregates transport, lifecycle and attention evidence from the outbox snapshot and recorded clocks. Rates use integer basis points so repeated projection does not drift.

| Input | Output | Authority |
|---|---|---|
| organization-scoped durable delivery rows | `delivery-analytics.v2` counts, rates and latency/fatigue measures | `deliver/analytics.py`, `/delivery/analytics` |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)

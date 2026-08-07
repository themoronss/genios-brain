# Delivery Object Builder

**Engine status:** Built.

The builder converts an admitted candidate and resolved route plan into the immutable `delivery-object.v2` boundary, then projects `delivery-result.v2` from its durable row. Mutable upstream state is not reconstructed at drain time.

| Input | Output | Authority |
|---|---|---|
| execution event, audience/route resolution and rendered source | versioned DeliveryObject, logical outbox row and later DeliveryResult | `contracts/delivery.py`, `deliver/orchestrator.py`, `deliver/results.py` |

## Component modules

1. [Mechanism and persistence](01-Mechanism-and-Persistence.md)
2. [Edge cases and gaps](02-Edge-Cases-and-Gaps.md)

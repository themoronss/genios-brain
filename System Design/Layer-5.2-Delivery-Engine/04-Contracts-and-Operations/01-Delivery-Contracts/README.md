# Delivery Contracts

Defines the immutable and versioned values shared across materialization, admission, transport and public result projection.

**Primary authority:** `genios_engine/contracts/delivery.py`

| Contract | Version / values | Role |
|---|---|---|
| `DeliveryCandidate` | typed, in-process | Minimum routing/admission proposal |
| `AdmissionDecision` | `SEND`, `DEFER`, `SUPPRESS` | Monotonic policy/timing result |
| `DeliveryObject` | `delivery-object.v2` | Immutable logical delivery snapshot |
| `DeliveryResult` | `delivery-result.v2` | Typed projection of durable delivery evidence |

The only active upstream contract is `ExecutionObject`. New v2 objects carry the narrowest source
visibility inherited from the selected evidence; stored v1 objects recover that visibility from
their immutable reasoning context in memory before routing. Contracts describe delivery state;
they never grant execution authority, widen source access or fabricate a business outcome.

## Component modules

1. [Admission Types](01-Admission-Types.md)
2. [DeliveryObject](02-DeliveryObject.md)
3. [DeliveryResult](03-DeliveryResult.md)

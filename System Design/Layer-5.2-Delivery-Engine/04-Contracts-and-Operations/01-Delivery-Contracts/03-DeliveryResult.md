# DeliveryResult

`DeliveryResult` is the frozen `delivery-result.v2` projection of one logical outbox row.

It exposes delivery/organization/subject identity, recipient and channel, lifecycle status, transport attempts, deferrals, delivery and engagement timestamps, stable reason code, computed metrics and diagnostic metadata. The lifecycle enum is:

`queued`, `deferred`, `delivered`, `viewed`, `ignored`, `accepted`, `executed`, `expired`, `suppressed`, `cancelled`, `failed`.

The projector gives lifecycle evidence precedence over internal transport state. It reports transport status, gate unit and last error as metadata rather than leaking an incompatible internal enum as the public result.

`delivered` is based on adapter evidence. Later states require explicit authenticated receipts. `executed` records interaction with the delivery affordance; the Layer 5 execution/outcome seam remains authoritative for business success.

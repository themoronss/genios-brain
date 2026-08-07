# Part A · Delivery Orchestrator

The orchestrator decides whether, where and when a delivery may proceed. It does not author the
business decision.

| Atlas subpart | Status | Folder |
|---|---|---|
| Delivery Context Resolver | Partial | [01](01-Delivery-Context-Resolver/README.md) |
| Audience Resolver | Upstream-owned | [02](02-Audience-Resolver/README.md) |
| Destination Router | Built | [03](03-Destination-Router/README.md) |
| Channel Planner | Partial | [04](04-Channel-Planner/README.md) |
| Timing & Interruptibility | Built | [05](05-Timing-and-Interruptibility/README.md) |
| Delivery Policy | Built | [06](06-Delivery-Policy/README.md) |
| Priority Scheduler | Built | [07](07-Priority-Scheduler/README.md) |

The final admission verdict is composed rather than selected by if/else precedence.

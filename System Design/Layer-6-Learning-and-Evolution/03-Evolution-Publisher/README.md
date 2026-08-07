# Part C · Evolution Publisher

The publisher writes the closed set of allowed dynamic outputs after lifecycle/governance approval.

| Publisher | Internal publisher | Downstream integration | Folder |
|---|---|---|---|
| Behavior Brain | Built | typed lower-layer snapshot consumer pending | [01](01-Behavior-Brain-Publisher/README.md) |
| Adaptive Brain | Built | typed lower-layer snapshot consumer pending | [02](02-Adaptive-Brain-Publisher/README.md) |
| Organization Brain | Built | typed lower-layer snapshot consumer pending | [03](03-Organization-Brain-Publisher/README.md) |
| Runtime Memory | Built | Context/Reasoning reader and optional Redis cache pending | [04](04-Runtime-Memory-Publisher/README.md) |
| Learning Metrics | Built | observability/analytics consumer is optional | [05](05-Learning-Metrics-Publisher/README.md) |

Each write carries tenant, trace and source visibility, and every dynamic-brain subject is
serialized with a PostgreSQL advisory lock. Versions remain monotonic after rollback; value,
confidence or ACL changes create a new version, while an exact no-op is rejected honestly. The
version number follows maximum history; the supersession link follows the actual displaced active
value so restorative rollback remains correct after an earlier rollback. The locked publisher also
compares the active value's source `last_seen_at`; a stale reviewed proposal cannot wait on the lock
and then supersede newer evidence.

The publisher subsystem is built. The product loop is still open at the explicit integration seam:
the lower layers do not yet consume these generic snapshots. There is no Expert publisher.

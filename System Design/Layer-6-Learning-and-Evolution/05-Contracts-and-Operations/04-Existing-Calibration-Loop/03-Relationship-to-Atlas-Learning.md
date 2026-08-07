# Relationship to Atlas learning

The calibration loop is narrower than the Atlas LearningObject system but operationally closed and
now obeys the same `learning_enabled` consent switch. The Atlas system adds broader verified
outcomes, patterns, actor-scoped preferences, leased memory, brains, ACLs and frozen governance;
its generic dynamic-brain rows are not yet consumed by lower-layer runtime readers.

Both remain documented so durable publication is not confused with effective runtime adaptation.

Atlas v3.1 sharpens the same distinction from the other side: the dynamic brains are a **store**
that Layer 3 reads and Layer 6 writes, with `brain_snapshot_id` as the read contract. Until a
lower layer resolves that snapshot, publication remains durable and unconsumed — which is exactly
what this page already said, now with a named seam.

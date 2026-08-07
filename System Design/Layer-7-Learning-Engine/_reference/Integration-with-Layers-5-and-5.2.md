# Integration with Layers 5 and 5.2

```text
Layer 5 execution_outcomes
Layer 5.2 delivery outbox/results
explicit canonical feedback
normalized enterprise events
        ↓
Atlas Layer 6 LearningObject proposals
        ↓ validation + governance
Organization / Behavior / Adaptive / Runtime / Metrics / Knowledge suggestion
```

## Outcome semantics

Layer 5 success is positive. Expiry and human cancellation can be negative. Unproven completion and
world/system cancellation remain neutral. Layer 5.2 terminal adapter failure is transport-negative;
deferred, suppressed, cancelled and queued are not fabricated as provider failures.

## Current closed seam

The older calibration path writes `rule_mutes` and bounded
`lvl3_config.rule_offsets`, which Reasoning consumes as data without a higher-layer import.

## Open seam

Generic `learned_brain_entries` and `temporary_memories` are durable/API-visible but have no
controlled lower-layer readers. Each future reader needs version selection, tenant scope, rollback,
expiry, deterministic fallback and a topology-safe data boundary before activation.

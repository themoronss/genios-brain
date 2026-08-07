# Layer 6 overview

Learning accepts explicit feedback, execution outcomes, delivery performance and normalized
enterprise events. Pure units propose immutable `LearningObject` values. Validation and tenant
governance decide whether a proposal may progress; publishers write only the closed set of dynamic
targets.

```mermaid
flowchart LR
    I["DeliveryResult + Feedback + Outcomes + Events"] --> S["Selector"]
    S --> P["Planner"]
    P --> U["10 analysis units"]
    U --> V["11 · Learning Validation"]
    V --> G["Governance"]
    G --> LC["Promotion lifecycle"]
    LC --> PUB["Evolution Publisher"]
    PUB --> O["Organization Brain"]
    PUB --> B["Behavior Brain"]
    PUB --> A["Adaptive Brain"]
    PUB --> R["Runtime TTL memory"]
    PUB --> M["Learning metrics"]
    LC --> K["Knowledge suggestion<br/>human review"]
    PUB -. "never" .-> E["Expert Brain"]
```

## Current operational truth

- Weekly processing is tenant-scoped and claimed atomically.
- Explicit temporary memories may enter immediately with bounded future expiry.
- Every proposal is immutable, content-addressed and backed by evidence statistics/source refs.
- Validation and governance are separate; high confidence cannot bypass tenant policy.
- Organization/Behavior/Adaptive rows, Runtime memories and metrics are published and API-visible.
- Generic new brain rows and Runtime memories do **not** yet affect lower runtime layers.
- The older narrow `rule_mutes` and bounded `lvl3_config.rule_offsets` calibration path is the
  learned state currently consumed by Reasoning.
- Knowledge Evolution produces a human-review suggestion; it does not edit Expert Brain or code.

That last boundary is the difference between “publisher implemented” and “closed adaptive product
loop.” See [STATUS.md](STATUS.md).

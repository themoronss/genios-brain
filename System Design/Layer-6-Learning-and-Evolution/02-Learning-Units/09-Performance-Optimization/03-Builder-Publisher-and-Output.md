# Builder, Publisher and Output

The builder emits unit `performance_optimization`, target `metrics`, subject
`performance:delivery:<channel>:audience:<acl-hash>` and the full transport/engagement measurement.
It preserves delivery refs, independent execution refs, reasoning traces, ExecutionObject ACL and
first/last evidence time, where each delivery contributes its latest lifecycle/receipt clock rather
than creation time alone. Its `failed` value counts only failures before the first durable delivery;
a later ACCEPTED → FAILED execution transition stays transport-delivered.

After validation/governance, the publisher writes an idempotent metric row. This unit does not
silently mutate Layer 5.2 rate limits, channel routing, retry policy or provider configuration.

**Integration note:** operator dashboards or a future governed optimization planner may consume the
metric. Broader cross-surface engagement depends on clients/providers emitting the append-only
events; missing receipts remain unknown.

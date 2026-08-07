# Builder, Publisher and Output

The builder emits unit `pattern_learning`, target `organization`, subject
`pattern:<key>:<kind>:audience:<acl-hash>` and value `{pattern_key, kind, occurrences,
distinct_days}`.

Preflight rejects incomplete lineage or constrained source evidence for organization-wide learning.
Default governance then routes a valid proposal to human review. Approval revalidates policy and
publishes a versioned Organization Brain row; no Expert content or graph fact is rewritten.

**Integration note:** downstream Organization Brain consumers must opt into the learned-entry read
contract. The publisher is durable and versioned, but recurrence does not automatically become a
hard business rule.

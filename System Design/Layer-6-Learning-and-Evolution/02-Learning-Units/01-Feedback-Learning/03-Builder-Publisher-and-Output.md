# Builder, Publisher and Output

The builder emits unit `feedback_learning`, target `metrics`, subject
`feedback:<source-subject>:audience:<acl-hash>` and value
`{accepted, rejected, timing, neutral}`. `timing` explains the timing portion of neutral evidence;
it is never added to negative quality. The v2 object includes exact source/independence/trace
lineage, seen window, ACL and lineage-complete flag.

After preflight and lifecycle validation/governance, the shared publisher writes one idempotent
`learning_metrics` row for the object's source window. A uniqueness collision becomes a rejected
`metric_identity_conflict`; it is never counted as publication. Metrics are telemetry, not a brain,
and cannot use brain rollback.

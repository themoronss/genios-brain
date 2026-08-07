# TTL validation

Runtime objects require `expires_at` later than `observed_at`, explicit metadata and a duration no
greater than tenant policy (default 720 hours). Missing, implicit or excessive TTL is rejected.

The comparison is exact duration arithmetic: the configured ceiling is accepted, while even one
microsecond beyond it is refused. This retention gate runs in preflight before a value-bearing
LearningObject or inbox memory can be accepted. The API additionally requires a future,
timezone-aware expiry and bounds the semantic JSON size/depth.

The closed Runtime target prevents a TTL object from being published as permanent Behavior or
Organization state.

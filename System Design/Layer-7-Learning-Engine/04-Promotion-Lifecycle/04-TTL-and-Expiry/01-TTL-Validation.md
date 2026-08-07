# TTL validation

Runtime objects require `expires_at` later than `observed_at`, explicit metadata and a duration no
greater than tenant policy (default 720 hours). Missing, implicit or excessive TTL is rejected.

The closed Runtime target prevents a TTL object from being published as permanent Behavior or
Organization state.

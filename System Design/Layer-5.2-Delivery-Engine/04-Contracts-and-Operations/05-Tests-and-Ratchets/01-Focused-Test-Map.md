# Focused test map

Delivery tests cover contracts, policy/timing/gate, Atlas components, routes, adapters, outbox,
Executive bridge, destination/failover, presence, results and analytics. The last verified broad
delivery collection contained 142 tests.

Critical loops include repeated DEFER without attempts, stale authority cancellation, terminal-only
fallback, signed webhook and leased presence expiry.

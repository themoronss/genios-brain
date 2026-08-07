# Adapter and contract

Both adapters implement the common channel result contract. Configuration endpoints validate/test tenant-owned destinations; outbox admission/retry/failover remains shared.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

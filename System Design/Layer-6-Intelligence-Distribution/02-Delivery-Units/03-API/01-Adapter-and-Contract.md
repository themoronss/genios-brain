# Adapter and contract

The `api` surface stores a durable pull result; clients query organization-scoped endpoints and receive the same underlying outbox/card truth.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

# Adapter and contract

An authenticated mobile client can read available payloads and publish bounded presence context using the same tenant-scoped contracts.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

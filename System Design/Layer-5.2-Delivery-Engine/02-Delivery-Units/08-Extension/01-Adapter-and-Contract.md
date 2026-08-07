# Adapter and contract

The backend stores the payload and lets an authenticated extension retrieve it; presence leases can report the current surface/busy state.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

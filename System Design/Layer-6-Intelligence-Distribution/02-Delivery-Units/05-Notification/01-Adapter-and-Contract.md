# Adapter and contract

Notification intent still passes policy/timing, uses a registered destination and records a typed transport result.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

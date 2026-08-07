# Adapter and contract

The surface adapter validates the known channel name and marks the payload available in the durable inbox rather than performing an untracked synchronous callback.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

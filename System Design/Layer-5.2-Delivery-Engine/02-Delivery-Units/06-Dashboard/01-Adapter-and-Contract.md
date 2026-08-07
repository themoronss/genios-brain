# Adapter and contract

A `dashboard` surface delivery succeeds when the durable payload is made available; subsequent client interaction remains a separate event.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

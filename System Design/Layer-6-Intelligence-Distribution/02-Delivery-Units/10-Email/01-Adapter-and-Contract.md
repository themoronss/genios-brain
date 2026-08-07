# Adapter and contract

A safe implementation would need verified sender/recipient identity, template/render boundary, unsubscribe/preference handling, idempotency, provider retry classification and receipt/bounce lifecycle.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

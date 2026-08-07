# Adapter and contract

Destination configuration supplies URL/secret. The adapter signs the request; the outbox records success, retryable failure or terminal failure and may invoke eligible fallback.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

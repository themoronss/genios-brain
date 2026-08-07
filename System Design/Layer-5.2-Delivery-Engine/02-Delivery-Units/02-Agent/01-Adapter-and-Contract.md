# Adapter and contract

Poll and artifact projection are authoritative and metered. Claims use a 15-minute lock; only the live holder may submit an authority-bearing result. Push and poll expose the same projection.

Every implemented target receives a canonical payload, emits the common channel result shape and
is invoked through the durable management path. Target code may format transport details; it may
not reopen Layer 5 policy.

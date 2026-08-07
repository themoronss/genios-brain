# Adapter and contract

An authenticated mobile client reads `mobile` deliveries from the tenant-scoped inbox, renders
the canonical payload, and posts idempotent lifecycle receipts. It may publish an expiring mobile
presence lease so contextual routing knows the user is active on that surface.

The pull adapter returns success when the payload is durably available. A future native-push
adapter must add registered device identity, token rotation, provider idempotency and receipt
mapping while remaining behind Layer 5.2 policy/timing and human-vs-agent isolation.

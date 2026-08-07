# Adapter and contract

A `dashboard` delivery succeeds when its already-committed `DeliveryObject` becomes available in
the authenticated inbox. The same outbox row supplies object/result reads and analytics; no
second dashboard queue or copied status exists.

The client renders the grounded payload and posts idempotent viewed/ignored/accepted/executed or
failed receipts. A dashboard card can initiate a typed Layer 5 action, but rendering or clicking
does not itself prove the business outcome.

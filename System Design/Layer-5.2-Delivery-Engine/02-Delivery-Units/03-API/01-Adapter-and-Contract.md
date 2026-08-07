# Adapter and contract

The `api` surface marks a committed outbox payload available. Authenticated clients query the
tenant-scoped inbox and receive semantic `DeliveryObject` + `DeliveryResult` projections; there
is no second API queue. Owners can inspect attempts/dead letters and replay terminal failure;
scoped clients can read/receipt only their own recipient delivery.

The surface adapter reports availability through `ChannelResult`. Client receipts use the shared
idempotent lifecycle state machine. API code may filter, serialize and authenticate; it cannot
change audience, priority, policy, timing or execution authority.

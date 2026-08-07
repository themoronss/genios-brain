# DeliveryObject

The immutable object identifies the logical delivery and preserves destination/channel, source
identity, payload/context version and creation time needed for replay/audit.

It is materialized onto the outbox record so a later drain does not reconstruct intent from
mutable upstream state.

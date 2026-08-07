# Adapter and contract

The canonical input is a `DeliveryObject` carrying `execution_id`, final human audience/recipient,
route, format, source payload and dedupe identity. The recipient must be a current org seat or an
explicit admin-queue fallback; resolving attention never reassigns Layer 5 work ownership.

For participant/private evidence, that active seat's normalized email must match the inherited
source principal and the route must be an authenticated recipient-scoped product surface. Shared
Slack/Teams/webhook destinations cannot preserve this ACL and are excluded.

Pull surfaces mark the already-committed payload available through the authenticated delivery
inbox. Slack/Teams/webhook perform one external provider attempt. Each returns the common
`ChannelResult`; the durable outbox then projects `DeliveryResult`. A client records `viewed`,
`ignored`, `accepted`, `executed` or `failed` with a tenant-scoped idempotency key.

Cards remain a presentation/read model. New outward delivery is authorized by the parent
`ExecutionObject`, not by a raw card row.

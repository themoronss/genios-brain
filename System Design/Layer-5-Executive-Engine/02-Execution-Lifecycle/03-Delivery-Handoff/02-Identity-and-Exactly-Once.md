# Identity and exactly-once behavior

The synthetic card key `exec:<execution_id>:<event_id>` combines with the existing unique outbox
identity. A crashed/replayed sweep can ask again without creating another logical delivery.

Queued and delivered remain separate. Enqueue success proves only durable handoff, never provider
delivery.

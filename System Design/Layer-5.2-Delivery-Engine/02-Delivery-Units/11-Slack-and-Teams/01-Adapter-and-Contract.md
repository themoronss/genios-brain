# Adapter and contract

Slack renders grounded cards/reminders into Blocks; Teams wraps grounded text in an Adaptive Card.
Configuration endpoints validate provider-specific HTTPS hosts, seal new credentials, expose only
non-secret metadata and support an explicit connection test.

Both adapters perform exactly one provider call and return the shared `ChannelResult` with HTTP,
retry-after, ambiguity and provider request metadata. The outbox owns admission, attention
reservation, bounded retry, fallback and lifecycle. Slack/Teams are human chat routes and are
excluded from the canonical agent ladder. Both spend one organization-wide rolling-hour chat
stream because their incoming-webhook destination is shared, while the local-day budget remains
bound to the resolved recipient.

Participant/private source evidence is excluded from these shared transports even when the
logical recipient is authorized; it remains on authenticated recipient-scoped product surfaces.

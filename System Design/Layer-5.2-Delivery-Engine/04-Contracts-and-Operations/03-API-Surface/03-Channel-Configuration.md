# Channel configuration

Channel routes list organization configuration for owner credentials; scoped keys are denied by the `get_current_org` boundary. Set, delete and test operations are also owner-only. Slack has a dedicated incoming-webhook path. Teams/Power Automate and generic webhook targets use their validated generic configurations. Agent webhooks are configured per agent rather than through the organization channel endpoint; API/pull surfaces need no secret configuration.

## Security controls

- Slack URLs must use the expected Slack hooks host.
- Teams targets must use recognized Teams/Power Automate hosts.
- Generic and agent webhooks require public HTTPS; generic webhook signing secrets have a minimum length.
- Secret-bearing JSON is sealed at rest. Reads return masked/safe summaries, not decrypted credentials.
- Capability discovery decrypts that same sealed JSON and re-runs concrete adapter validation;
  ciphertext presence alone never marks a route operational, and failures stay redacted.
- Materialization uses those identical checks before route planning. A bad key, corrupt ciphertext
  or invalid adapter shape is excluded from both capability output and the actual route ladder.
- Agent webhook requests use HMAC-SHA256 and an `Idempotency-Key`; key rotation invalidates cached credentials immediately.
- Obvious localhost/private literal destinations are rejected.

Application validation is not a complete SSRF boundary. Production egress needs DNS resolution checks, redirect policy, IP/range allowlists or pinning, network isolation and monitoring.

Slack and Teams incoming webhooks are channel-wide endpoints, not per-recipient DM/OAuth transports. Recipient identity remains delivery-ledger/audience metadata. A test call proves immediate adapter connectivity only; it does not pass normal admission or prove provider permissions, rate behavior or production deliverability.

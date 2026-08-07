# Rules and decision

The ladder is deterministic:

- candidate destinations are tenant-scoped, purpose-enabled and sorted by declared priority then
  channel name;
- malformed, undecryptable or adapter-invalid channel/agent configuration is excluded before the
  route ladder is frozen, using the same fail-closed checks as capability discovery;
- critical/high human work prefers a non-busy contextual surface, then registered human push;
- medium human work prefers contextual, `in_app`, then `dashboard`;
- low/background human work prefers `dashboard` then `in_app`;
- human routes may include Slack, Teams or generic webhook, but never the `agent` channel;
- agent routes may include only the canonical `agent` or authenticated `api` path and never a
  human surface; and
- `participants`/`private` source visibility excludes every shared or external push destination,
  including Slack, Teams, generic webhook and agent webhook. It uses only authenticated,
  recipient-scoped product surfaces for a verified human principal.

The same logical outbox row advances through this frozen ladder after a **definite terminal**
failure. An ambiguous timeout does not cross-channel fail over because the first provider may
already have accepted the message.

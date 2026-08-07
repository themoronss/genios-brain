# Lifecycle, edge cases and gaps

2xx provider response means accepted by the chat transport, not read or executed by a person.
Retryable/terminal/ambiguous outcomes remain physical attempt facts. Ambiguous acknowledgement
does not cross-channel fail over. Incoming webhooks provide no receiver-side idempotency contract,
so ambiguity becomes terminal manual-reconciliation evidence instead of automatic same-route
retry; owner replay requires explicit duplicate-risk acknowledgement. A definite terminal failure
may advance the same logical row.

Local tests cannot prove tenant webhook validity, workspace/channel permissions, provider rate
limits, secret rotation or live availability. Slack currently uses incoming webhooks rather than
a full OAuth bot lifecycle; Teams depends on accepted webhook/Workflow hosts. These deployment
requirements prevent “adapter active” from being reported as “every tenant operational.”

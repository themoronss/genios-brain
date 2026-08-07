# Edge cases and gaps

- Quiet hours, busy presence and rate holds defer before invocation, so they do not consume attempts.
- An expired claim is not proof of failure. It becomes `unknown` because the provider may already have accepted the request.
- Ambiguous acknowledgement is intentionally not treated as a definite failure or immediate failover. Retrying can be at-least-once unless the receiver honors the stable idempotency key.
- Slack/Teams incoming webhooks do not expose receiver-side idempotency. Their ambiguous outcomes
  become terminal/manual-reconciliation evidence instead of an automatic same-route retry.
- A definite terminal failure can advance the fallback route; an ambiguous result cannot.
- Definite pre-delivery failure releases reserved hourly and daily capacity. Success and `unknown` retain it because an interruption may have occurred.
- Real Slack, Teams and webhook error taxonomies, provider rate limits, credential expiry and long-outage behavior have not been proven by local fake-adapter tests.

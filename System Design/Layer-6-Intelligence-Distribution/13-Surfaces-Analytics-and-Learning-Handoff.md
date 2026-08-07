[← Destination Routing and Failover](12-Destination-Routing-and-Failover.md) · [Folder map](README.md)

# Surfaces, analytics and the Atlas Layer 6 handoff

## Surface semantics

| Surface | Runtime form |
|---|---|
| Human | card queue, Slack/Teams message, signed webhook or pull inbox |
| Agent | scoped poll → 15-minute claim → result, plus equivalent signed push |
| API / dashboard / application / extension / mobile | authenticated durable pull inbox |
| Digest | on-demand one-line summary over current card authority |

Agent delivery hands over a scoped artifact. It does not perform customer-side mutations with
GeniOS credentials. Double claim is visible, late/revoked results become no-ops, and failure
re-surfaces work to the human path.

## Analytics

`analytics.py` reduces a bounded outbox window into reproducible integer metrics:

- total and per-channel status counts;
- delivered basis points over all terminal delivery outcomes;
- transport-failure basis points over delivered + failed-terminal only;
- adapter attempts and gate deferrals;
- burst-limit holds;
- p50 and p95 measured delivery latency.

Queued work is excluded from terminal success/failure rates rather than guessed into failure.
Suppressed/cancelled rows remain visible, but only actual adapter failures count against transport
reliability.

`GET /api/org/{org}/delivery/analytics?days=N` reads the same durable ledger as the drain. There is
no analytics shadow database and no model-generated metric.

## Learning handoff

Atlas Layer 5.2 outputs `DeliveryResult → Layer 6`. Code Layer 7 implements Atlas Layer 6 and reads:

```text
delivery_id · channel · status · created/delivered time
attempts · deferrals · reason code
```

Performance Optimization aggregates those facts by channel. An open, deferred, suppressed or
cancelled row is not mislabeled as a transport failure. Learning cannot read message payloads to
invent a causal story; it receives only delivery lifecycle facts.

This closes the product loop without breaking import direction: `deliver/` never imports
`feedback/`; the higher learning layer reads the outbox table as data during its claimed run.

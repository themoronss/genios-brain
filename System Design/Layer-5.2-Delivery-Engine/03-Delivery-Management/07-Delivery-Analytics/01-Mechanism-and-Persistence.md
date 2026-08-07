# Mechanism and persistence

`delivery-analytics.v2` groups durable rows by lifecycle status and channel, and derives:

- transport failure rate, physical attempts, deferrals and burst holds;
- delivery latency p50/p95;
- impressions from recorded `delivered_at` evidence;
- viewed, ignored, accepted and executed counts and basis-point rates;
- engagement-response and execution-response timing; and
- recipient fatigue from actual recorded impressions, not queued intent.

The projector reads the same ledger as `DeliveryResult`; it does not mutate state or create a parallel analytics truth. Suppressed, deferred, cancelled and materialization-failed work are not relabelled as provider failure.

Layer 6's delivery feedback projection consumes the lifecycle state and viewed/ignored/accepted/executed clocks as delivery facts. Its performance optimization can therefore report those recorded counts. Business execution outcomes remain separately owned by the execution/outcome layer.

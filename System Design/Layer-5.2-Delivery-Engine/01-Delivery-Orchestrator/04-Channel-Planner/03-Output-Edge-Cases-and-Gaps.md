# Output, edge cases and gaps

**Output:** an adapter-ready `DeliveryPlan` and rendered payload, persisted before any provider
call. The unrendered `source_payload` is retained so a fallback can be rendered for its own
channel without copying stale provider bytes.

**Edge cases and gaps**

- Slack has explicit card/reminder rendering; Teams wraps grounded text in an Adaptive Card;
  webhook and pull surfaces preserve the canonical source shape.
- A fallback recomputes format and channel class instead of retaining the primary’s metadata.
- Adapter success means provider acceptance or durable availability, not human view or business
  execution.
- Native email, APNs/FCM, GraphQL, streaming, MCP and universal client negotiation are not built.
- External adapters are engine-ready but still require tenant credentials and live-provider proof.

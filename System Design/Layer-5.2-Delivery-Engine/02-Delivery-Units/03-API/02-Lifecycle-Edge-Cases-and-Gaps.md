# Lifecycle, edge cases and gaps

REST is active for inbox, typed results, lifecycle receipts, attempt inspection, analytics,
capabilities and owner replay. Surface delivery means durable availability; it does not prove a
client fetched or acted, so those facts require separate receipts.

GraphQL, streaming, MCP and packaged SDKs are not implemented. An agent API delivery must resolve
to a scoped active agent and cannot be read from a human recipient inbox. Provider-facing push is
owned by Webhook/Agent rather than being mislabeled as REST pull.

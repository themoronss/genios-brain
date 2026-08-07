# Edge cases and gaps

- Missing/malformed source payload or an agent audience with no eligible route is written to `delivery_materialization_failures`, not dropped.
- Current configuration/directory/presence can refresh the same queued logical row while all
  attempt evidence proves non-delivery. Once transport is ambiguous or delivered, the historical
  route stays frozen; drain still revalidates authority and securely reloads exact credentials.
- Agent and human audiences are deliberately non-interchangeable; no human fallback is invented for an agent-targeted execution.
- Pull API routing is implemented, but native client polling/receipt behavior must be integrated outside the engine.
- Adding email, APNs/FCM or another channel requires a registered adapter, configuration schema, capability declaration and production credentials.
- A DeliveryObject carries delivery intent and lineage; it is not execution authority, and a DeliveryResult is not business outcome proof.

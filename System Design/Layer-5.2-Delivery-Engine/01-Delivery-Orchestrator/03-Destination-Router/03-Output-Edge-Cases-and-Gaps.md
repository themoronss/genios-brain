# Output, edge cases and gaps

**Output:** `channel`, `destination`, `route_plan`, `route_index` and a stable route reason frozen
onto the durable `DeliveryObject` row.

**Edge cases and gaps**

- No endpoint is invented from an email address, handle or arbitrary URL.
- Human delivery always has an authenticated internal fallback.
- Agent delivery fails materialization when no active recipient/agent route exists; it cannot
  silently become human work.
- Participant/private content cannot enter a shared incoming-webhook channel merely because its
  logical recipient is authorized; the physical destination must preserve the same audience.
- Fallback rewrites channel class, format, interruptibility and retry generation together while
  preserving the logical delivery identity and attempt history.
- Provider credentials, client installation and external reachability remain deployment proof,
  not facts inferred from an engine-ready adapter.
- The minute materializer refreshes a queued route from current presence/directory/configuration
  while the attempt ledger proves non-delivery. `started`, `unknown` or `delivered` evidence
  freezes automatic mutation and requires conservative recovery.

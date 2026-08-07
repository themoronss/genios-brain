# Slots and grounding

The card pipeline selects only open signals joined to an existing execution. Its claim/store flow is race-safe, links the card to `execution_id`, preserves authority lock and enforces one card per signal.

Typed slots are derived deterministically from stored signal, decision, explanation and execution evidence. Evidence references and context tags remain attached so every displayed claim can be checked against its allowed fact corpus. A missing optional slot may use a deterministic fallback; missing authority or source evidence may not be invented.

This is deliberately narrower than raw-signal fan-out. Signals without a valid execution do not become outbound Delivery Engine work, and a card ID is never substituted for execution identity.

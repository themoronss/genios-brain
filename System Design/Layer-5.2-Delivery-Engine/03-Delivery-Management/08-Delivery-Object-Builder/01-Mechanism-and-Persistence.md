# Mechanism and persistence

The orchestrator accepts only execution-bound initial or reminder/escalation events, enforces the
execution's inherited source visibility, resolves human or agent audience, recipient, route plan,
destination, channel class, format and priority, and renders the payload for that selected route.

Materialization freezes into the logical outbox row:

- execution ID/hash and source event lineage;
- audience, recipient, destination, channel/class and format;
- priority class/rank, interrupt intent and route reason/plan;
- source payload, rendered payload, dedupe key and daily budget; and
- creation/due clocks plus versioned delivery identity.

The minute materializer may refresh this same queued row from current authority,
directory/presence and validated configuration while all attempt evidence proves non-delivery.
Later drain uses the auditable snapshot while revalidating authority and exact destination
eligibility. `results.py` reads the same row and maps lifecycle, attempts, deferrals, clocks, reason,
metrics and diagnostics into `DeliveryResult`; there is intentionally no second result table.

Agent audiences are kept on signed-agent/scoped-API routes and do not fall back to human
destinations. An active exact agent must have `delivery.read`; API pull also requires that same
agent's active scoped key. Its source payload is the full versioned execution+safety envelope, not
a card summary.

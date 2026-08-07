# Focused test map

The focused collection currently consists of:

- `test_delivery.py`, `test_delivery_atlas.py`, `test_delivery_gate.py` and `test_delivery_routes.py`;
- `test_delivery_control_plane.py` for execution-only materialization, strict human/agent routes, priorities, capabilities, lifecycle, engagement handoff, API exposure, inbox isolation and migration 0046 source ratchets;
- `test_l6_channels.py` and `test_l6_outbox.py` for adapter/outbox behavior;
- `test_agent_api_authority.py` for agent authentication/authority; and
- `test_executive_bridge.py` for the Layer 5 boundary.

On 2026-08-08 these nine files completed with **217 passed** and one third-party TestClient
deprecation warning.

## Important covered seams

- monotonic admission and repeated defer without an adapter attempt;
- execution-bound routing and isolation between human and agent audiences;
- all five priority boundaries plus aging;
- Delivery v2 projection, lifecycle transition rules and Layer 6 engagement handoff;
- provider outcome classification, bounded retry input and stable generation-level idempotency;
- full versioned agent execution payload, signed webhook, exact-agent scoped pull-inbox isolation,
  retired raw-signal endpoints and self-bound context;
- source-visibility inheritance/enforcement, truthful decrypted capabilities, quota/attempt
  atomicity, legacy quarantine and ambiguity-aware replay;
- authority cancellation, leased presence and legacy adapter/outbox behavior; and
- migration 0046 table/constraint text and removal of legacy distribution fan-out from the active sweep.

## Deployment verification still required

Release evidence still needs a production-shaped PostgreSQL 0046 rehearsal plus concurrent
final-slot, claim-expiry, receipt-versus-expiry, fallback and unique-materialization exercises at the
target isolation/topology. Live provider contract tests are also required. Source inspection
ratchets are useful drift alarms, not substitutes for staging and provider proof.

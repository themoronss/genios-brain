# Output, edge cases and gaps

**Output:** one audience class, one recipient (or explicit unresolved admin queue), and a stable
reason such as `current_owner_manager`, `registered_agent` or `active_admin_fallback`.

**Isolation and edge cases**

- Agent intent never resolves to a human seat; a missing active/scoped agent rejects
  materialization rather than leaking the payload to a human inbox.
- Participant/private evidence never falls through to an unrelated administrator. The selected
  current seat must match a source principal email, and constrained agent intent fails closed
  because registry ids are not yet verified human ACL principals.
- Human intent never selects the `agent` transport.
- Reassignment while queued refreshes the same logical delivery only when every recorded attempt
  proves non-delivery. `started`, `unknown` or `delivered` evidence freezes the recipient for
  manual recovery; live execution authority is still re-proved before send.
- `team` currently resolves to the owner rather than performing fan-out, and `executive` has no
  separate role-expansion algorithm; both fall through the deterministic target/admin rules.
- Per-action multi-owner allocation remains a Layer 5 concern, not a delivery repair.

The remaining dependency here is directory quality: real deployments must keep active seat email,
role and manager relationships synchronized. The visibility algorithm itself is active engine
behavior, not an outstanding design gap.

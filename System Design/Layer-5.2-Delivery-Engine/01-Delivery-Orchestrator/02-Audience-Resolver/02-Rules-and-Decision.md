# Rules and decision

Resolution is deterministic and fail-safe:

1. `participants` or `private` visibility first filters active seats by the lower-cased source
   principal email. An empty authorized set rejects materialization; it never invokes admin
   fallback.
2. `agent` requires an active registry identity with `delivery.read`. Constrained source evidence
   rejects agent delivery until that agent has a verified visibility-principal binding.
3. `manager` resolves through the current owner-to-manager relationship; a frozen ex-manager is
   not treated as current authority merely because that seat is still active.
4. `owner` and the current implementation of `team` resolve to the active execution owner.
5. A concrete reminder target is accepted only if still active, visibility-authorized and only
   after role resolution.
6. Otherwise the first stable active admin becomes the triage recipient; if no seat is available,
   the resolution remains an explicit unresolved admin surface.

This chooses an attention recipient, not a new work owner. Assignment changes still belong to
Layer 5 and must preserve execution history.

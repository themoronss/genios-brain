# Inputs and context

The pure timing unit receives a `DeliveryCandidate`, `AttentionProfile`, `AttentionState` and
explicit timezone-aware `now`. The profile includes timezone, quiet window/weekend behavior,
hourly limit and critical override band. State includes `busy_until`, current activity/surface,
the last-hour count and the oldest interruption in that window.

Only chat is currently classified as intrusive. Internal pull surfaces, webhook/agent delivery
and digests do not consume human interruption budgets merely because they are deliverable. The
orchestrator’s `interrupt` flag is separately derived from criticality, confidence and presence.

These facts are re-read at drain time; enqueue-time quiet-hours or burst decisions are never
trusted as current truth.

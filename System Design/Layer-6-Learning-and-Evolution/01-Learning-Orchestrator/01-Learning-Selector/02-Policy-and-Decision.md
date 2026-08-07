# Policy and decision

Selection is deliberately strict:

- a stored execution payload must rehydrate, round-trip, match tenant and execution ID, and match
  the frozen hash when the delivery seam supplies one;
- missing, partial or invalid visibility never defaults to organization scope; it resolves to a
  private-empty ACL with `lineage_complete=false`;
- graph observations need exact source-ref/event lineage; multiple sources contribute a narrowed
  ACL and a stable independence-group identity;
- only the latest canonical feedback revision participates; optional malformed/unauthorized
  preferences become a sanitized rejection while the base verdict remains usable;
- a delivery is selected when its outbox creation or at least one lifecycle event falls inside the
  source window, so an older long-running row with recent activity is not dropped;
- delivery status is the latest append-only event at evaluation time, and engagement timestamps,
  attempts and deferrals are also clipped to that time; its event timestamp remains the freshness
  clock even for failed, deferred, suppressed or cancelled status; and
- open, deferred, suppressed, cancelled and expired deliveries remain distinct facts rather than
  being converted into failures. A `failed` row with an existing `delivered_at` is retained as
  delivered transport plus a later lifecycle clock; only pre-delivery failure is transport-negative.

The same committed rows, tenant, source window and evaluation time produce the same `LearningBatch`.
No LLM or wall-clock lookup participates in this decision.

Preference Learning applies a second, value-specific boundary after selection: a user preference
is intersected with its one resolved subject and becomes private to that principal. An unresolved
subject or a source ACL that excludes the subject marks lineage incomplete, so preflight rejects
the proposal before its value is persisted.

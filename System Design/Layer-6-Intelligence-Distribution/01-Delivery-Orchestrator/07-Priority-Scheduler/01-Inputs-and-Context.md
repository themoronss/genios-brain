# Inputs and context

queued rows, band/priority, due time, attempts/deferrals and recipient budget state.

Context is resolved at the latest safe point, organization-scoped and tied to explicit evaluation
time. Queue-time state is not silently reused as current truth.

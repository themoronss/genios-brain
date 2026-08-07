# Inputs and context

frozen channel class, current registered destinations, surface/presence context and card payload.

Context is resolved at the latest safe point, organization-scoped and tied to explicit evaluation
time. Queue-time state is not silently reused as current truth.

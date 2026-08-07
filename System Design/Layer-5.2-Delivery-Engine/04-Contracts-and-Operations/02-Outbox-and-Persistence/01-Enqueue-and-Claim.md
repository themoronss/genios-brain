# Enqueue and claim

Enqueue records stable identity and payload. Drain claims only due rows in bounded batches, then
resolves current context and revalidates Executive authority before adapter invocation.

A claim is not a send receipt; completion records the adapter result separately.

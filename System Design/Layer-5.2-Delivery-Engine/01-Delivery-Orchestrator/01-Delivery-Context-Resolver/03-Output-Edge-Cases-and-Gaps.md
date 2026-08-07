# Output, edge cases and gaps

**Output:** a grounded `DeliveryContext` containing resolved policy, attention profile, live
attention state and any safe-fallback configuration error.

**Fail-safe behavior**

- A malformed timezone is rejected by write APIs; corrupt legacy state falls back visibly.
- Stale presence disappears automatically and cannot leave a seat permanently busy.
- Missing presence means “unknown,” not invented activity.
- A context read failure never becomes permission to send; the row is retried without a provider
  attempt.

**Integration gap:** the engine and authenticated presence API are active, but trusted publishers
from every browser, desktop, mobile, CRM and IDE client are not all present in this repository.
Consequently contextual routing is only as current as the clients that report it.

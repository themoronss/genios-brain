# Defer, suppress and cancel

These outcomes are intentionally distinct:

- `DEFER` changes `next_attempt_at`, increments `defer_count`, records gate reason and appends a deferred lifecycle event. No adapter is invoked and no attempt is consumed.
- `SUPPRESS` is terminal policy refusal, such as a durable opt-out. It appends a suppressed lifecycle event.
- `CANCEL` means the underlying execution/authority is no longer live. It appends a cancelled lifecycle event and clears pending transport ownership.
- `FAILED` means the logical route exhausted a definite physical failure path. It is replayable only through an explicit owner operation.
- `EXPIRED` means the delivery exceeded its useful lifecycle window; pending physical work is cancelled without deleting audit evidence.

Keeping these states separate makes operator diagnosis and analytics honest. Quiet hours are not provider failure, opt-out is not cancellation, a closed execution is not suppression, and none may be counted as a successful business execution.

Fallback is also separate from replay: a definite failure may advance `route_index` within the same logical row, while owner replay starts a new retry generation only after `failed_terminal`.

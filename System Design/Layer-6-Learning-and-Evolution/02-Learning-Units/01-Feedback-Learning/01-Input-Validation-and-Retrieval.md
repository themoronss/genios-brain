# Input, Validator and Retriever

## Input / Validator

Only `FeedbackFact.explicit=true` enters analysis. The frozen contract validates identifiers,
supported action, aware timestamp, optional actor/subject principal, complete preference shape,
source visibility and boolean lineage/authority flags. A user preference requires actor identity; an
organization preference requires server-frozen owner authority.

## Retriever

`load_batch` reads the latest immutable feedback revision per feedback ID, joins the canonical
verdict and card, and verifies the card's exact `ExecutionObject`. It derives trace from the
execution reasoning run, independence from card ID, visibility from the execution envelope and the
user principal from authenticated actor/seat/owner identity.

For dashboard actions, `run_play`, `do_it_myself` and `wrong` are terminal judgments. The card,
signal, human/card audit events, current canonical verdict and any new immutable verdict revision
commit atomically. An exact retry is a no-op; a semantic correction increments `verdict_version`.
`wrong:bad_timing` is still a canonical judgment and therefore follows that versioning contract;
its learning label is timing/neutral rather than negative quality. Dashboard `snooze` and `requeue`
change lifecycle/audit state only. The extension's `snooze` mapping is likewise an idempotent
timing-only audit action. None of those snooze/requeue events enters this verdict cohort.

Both dashboard action ingestion and `/v1/intelligence/feedback` use the shared source-writer order:
tenant `orgs FOR SHARE` → graph-version `FOR SHARE` → actionable card/signal `FOR UPDATE` (with
authority rows held `FOR SHARE`) → audit and feedback verdict/revision writes. Account erasure's
tenant `FOR UPDATE` therefore cannot overlap a late feedback append or post-delete resurrection.

Malformed or unauthorized optional preference data produces a sanitized input rejection while the
base explicit verdict remains available. A malformed execution/feedback source is rejected. The
unit never queries cards again, crosses tenant boundaries or manufactures missing lineage.

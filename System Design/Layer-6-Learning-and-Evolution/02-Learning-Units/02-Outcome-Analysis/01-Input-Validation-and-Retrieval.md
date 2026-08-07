# Input, Validator and Retriever

## Input / Validator

`OutcomeFact` requires outcome/capability/play/label identifiers, aware close time, progress in
0–10,000 bp and non-negative reminder, escalation and close-duration values. Supported labels are:

- success: `succeeded`;
- failure: `expired_untouched`, `expired_in_progress`, `cancelled_by_human`; and
- neutral: `completed_unproven`, `cancelled_by_world`, `cancelled_by_system`.

## Retriever

The selector reads tenant/window-bounded `execution_outcomes` joined to `executions` by execution ID,
decision hash, capability and play. It rehydrates the immutable ExecutionObject, confirms capability
and play again, inherits its visibility, uses the reasoning-run trace and counts the execution ID as
the independence key.

Malformed or mismatched rows become sanitized rejections. Card clicks, delivery receipts and open
execution state are not substitutes for a closed outcome label.

# Input, Validator and Retriever

## Input / Validator

Outcome facts preserve label, progress, reminders, escalations, close time and execution identity. Only tenant-window facts in the batch participate.

## Retriever

The durable `execution_outcomes` seam is read directly; card clicks and delivery receipts are not substitutes.

The unit never crosses tenant boundaries and never replaces missing source evidence with generated
facts.

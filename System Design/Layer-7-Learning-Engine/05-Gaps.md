[← Mutes, Nudges and Ledger](04-Mutes-Nudges-and-The-Ledger.md) · [Folder map](README.md)

# Remaining gaps

The earlier highest-risk gap—`execution_outcomes` being written but never read—is closed by
`feedback/store.py::load_batch` and `outcome_analysis`. `completed_unproven` is deliberately kept
neutral and visible rather than mislabeled as success or failure.

| # | Remaining limitation | Consequence / next step |
|---|---|---|
| 1 | Redis is not yet an acceleration tier for temporary memory | PostgreSQL TTL is authoritative and enforced; add Redis only as a disposable cache, never a second source of truth |
| 2 | Enterprise event patterns use normalized `kind + subject` | Calendar weekday/hour and richer sequence mining need typed upstream features; raw prose must not be guessed into a permanent pattern |
| 3 | Structured preference extraction is producer-dependent | The deterministic unit accepts `detail.preference`; a future allowed LLM extractor may structure free text before this boundary |
| 4 | Knowledge approval records a human-approved suggestion but does not open a Git pull request | Intentional safety boundary; a separate human-owned authoring workflow is needed |
| 5 | Weekly cadence is fixed to UTC Monday | Policy exposes thresholds and TTL, not cadence; add a tenant cadence only with a durable non-overlapping period identity |
| 6 | Brain rollback deactivates the selected version but does not automatically reactivate an older version | Avoids silently restoring stale behavior; a deliberate restore operation can be added later |
| 7 | No live-PostgreSQL integration result is recorded in this repository | Static SQL/table/column/account-erasure ratchets pass; deployment should still run migrations and a live smoke test |
| 8 | Existing MACV ledger is still not a standalone learning unit | Versioned LearningObjects and transitions cover audit/replay; if MACV has a stricter canonical definition it still needs to be ratified and implemented |
| 9 | New Organization/Behavior/Adaptive entries and Runtime memories have no generic lower-layer consumer yet | Publishers, lifecycle and APIs are live, but these values do not influence reasoning/context/delivery until a typed, policy-scoped materializer is added; the older `rule_mutes` + bounded `lvl3_config.rule_offsets` calibration path remains the only learned state currently read by reasoning |

These are implementation limits, not violations of the Atlas hard rules: no LLM controls
promotion, no one-off becomes permanent, and no code path edits the Expert Brain. They do mean
the broad Atlas learning engine is structurally complete at the governed publication boundary,
while generic learned-state consumption still needs an explicit integration contract.

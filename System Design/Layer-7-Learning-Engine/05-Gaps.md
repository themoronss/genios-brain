← [Mutes, Nudges and the Audit Ledger](04-Mutes-Nudges-and-The-Ledger.md) · [Folder map](README.md)

---

# Gaps

---

## §6 · Gaps

| # | Gap | Detail |
|---|---|---|
| 1 | **`execution_outcomes` is not read** | Layer 5 writes it — *what was recommended, how far it got, how much attention it cost, and whether the world produced the declared evidence* — and it is **indexed for exactly this cohort read** (`org, capability, play, closed_at`). Layer 7 still learns from **card clicks alone.** This is **the single biggest gap in the layer**, and it was left deliberately: *Layer 7 is its own brick, and this is the first item of it* |
| 2 | **Precision measures whether a card *looked* right** | Not whether acting on it worked. **A card everybody clicks and nobody ever completes is, by this metric, a triumph.** Gap 1 is the fix |
| 3 | **`completed_unproven` has no consumer** | Layer 5's most valuable label — *a play people are happy to finish and that never produces its outcome* — is written and unread |
| 4 | **Only `gate.s_min` is nudged** | The audit ledger's `param` column is general, but `rule_offsets` is the only parameter learning touches. Cooldowns, urgency curves and impact floors are untouched |
| 5 | **Weekly cadence is hard-coded** | `_week_start` floors to UTC Monday. A tenant with a different rhythm has no dial |
| 6 | **MACV is not implemented** | Named in the layer map; no code corresponds to it |
| 7 | **Never run against Postgres** | Same as every layer above it |

---

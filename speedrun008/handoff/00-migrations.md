# 🗄 Migrations — eight, in number order

All idempotent (`if not exists`), all safe to re-run, ~2 minutes each.

⛔ **Apply them in number order.** Three of the Layer 1 ones are hard ordering constraints: the
signal store already names those columns, so a signal INSERT fails until they land.

```bash
psql "$DATABASE_URL" -f migrations/0176_delivery_failure.sql
psql "$DATABASE_URL" -f migrations/0177_qualified_signals_subject_key.sql
psql "$DATABASE_URL" -f migrations/0178_sync_completeness.sql
psql "$DATABASE_URL" -f migrations/0179_signal_world_instants.sql
psql "$DATABASE_URL" -f migrations/0180_signal_coverage.sql
psql "$DATABASE_URL" -f migrations/0181_signal_conversation.sql
psql "$DATABASE_URL" -f migrations/0182_signal_situation.sql
psql "$DATABASE_URL" -f migrations/0183_situation_interpretations.sql
```

---

## What each one is, and what breaks without it

| # | adds | ⛔ if skipped |
|---|---|---|
| **0176** | widens two CHECK constraints for `delivery_failure` | **every bounce signal fails to INSERT.** The step produces nothing and looks like it worked |
| **0177** | `qualified_signals.subject_key` + index | **every situation read fails** — the widened projection SELECTs a column that is not there |
| **0178** | four completeness columns on `l1_sync_runs` | **every sync-ledger write fails silently.** It is wrapped in a `try/except` that never raises, so syncs keep working and simply stop being recorded — worse than crashing |
| **0179** | four world instants on `qualified_signals` + a partial index | **every signal INSERT fails** — the store names these columns. Without them a signal cannot say *"8 days overdue"* |
| **0180** | `qualified_signals.coverage` jsonb | **every signal INSERT fails.** And a signal in state `broken` cannot publish at all — the contract refuses a negative claim with no proof behind it, deliberately |
| **0181** | five conversation columns + two partial indexes | **every signal INSERT fails.** And Layer 2 keeps recomputing *whose turn it is* from Gmail labels because L1's real answer never arrives — it moved the benchmark 20 → 24 |
| **0182** | `signals.situation_id` + a partial index | **every compiled signal INSERT fails.** And the card loop stays one-per-SIGNAL: one situation firing three rules keeps producing three cards that can never merge — the *"Nitesh Pant × 3"* symptom exactly. **Nullable, no FK, deliberately**: a situation archives on its own lifecycle while its signals stay open |
| **0183** | `situation_interpretations`, a new table | **every Context Reasoner reading is lost.** The writer swallows the failure, so a sweep still succeeds and simply remembers nothing — which is worse than crashing, because the reading looks like it happened. It stores the SLICE a reading was made from, so a conclusion can be replayed against its own premises |

---

## After they land

Two scripts become runnable that are not runnable today:

```bash
python scripts/card_collapse_report.py --org <pilot>    # needs 0182 — it refuses without it
```

and the Context Reasoner can record what it reads (needs 0183). Both are in
[`01-measurements.md`](01-measurements.md).

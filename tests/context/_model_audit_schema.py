"""The sqlite DDL for the two tables `context/model_audit.record_model_run` writes.

ONE COPY, because five test files each carried their own. Migration 0175 added `seat_id`,
`cache_read_tokens` and `cache_write_tokens` to `llm_costs`; not one of the five learned about
it, so `record_model_run`'s INSERT started failing with `no column named cache_read_tokens` and
eleven tests went red in a way that reads as an L2 behaviour failure rather than as a stale
fixture. A fake schema that has drifted from the real one proves nothing it claims to prove —
and five copies drift five times, on five different days, for whoever is holding the next
migration.

KEEP IN STEP WITH THE MIGRATIONS, not with what a test happens to select: `record_model_run`
names every column below, so a column this file omits is a failed call, never a wrong value.
"""

from __future__ import annotations

#: `l2_model_runs` — the audit envelope (0119).
L2_MODEL_RUNS_DDL = (
    "create table l2_model_runs (run_id text primary key, org_id text, site text, "
    "subject_ref text, prompt_version text, prompt_hash text, model_snapshot text, "
    "max_tokens integer, input_tokens integer, output_tokens integer, success boolean, "
    "error text, parsed_output text, raw_output text, response_hash text, latency_ms integer, "
    "called_at timestamp)"
)

#: `llm_costs` — the cost row filed beside the envelope (0004, widened by 0175).
LLM_COSTS_DDL = (
    "create table llm_costs (org_id text, model text, purpose text, input_tokens integer, "
    "output_tokens integer, success boolean, error text, subject_ref text, seat_id text, "
    "cache_read_tokens integer not null default 0, "
    "cache_write_tokens integer not null default 0, created_at timestamp)"
)

#: Both, in the order a fixture wants them. Splice into a file's own `_SCHEMA` tuple.
MODEL_AUDIT_SCHEMA = (L2_MODEL_RUNS_DDL, LLM_COSTS_DDL)

__all__ = ["L2_MODEL_RUNS_DDL", "LLM_COSTS_DDL", "MODEL_AUDIT_SCHEMA"]

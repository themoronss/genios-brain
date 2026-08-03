"""LLM cost ledger — per-call token + $ tracking per org per day.

Plan locked this table at GENIOS_V2_PLAN.md line 420 but never built it.
Without it the founder can't see where Anthropic spend goes (extraction
vs reasoning vs custom-mapping) and the circuit breaker in
core/neural/cost_guard.py has no DB to read from.

  llm_costs        — one row per LLM call (auditable, every site logs here)
  + a per-(org, date, model, purpose) summary view if we ever need rollups
    in SQL — for now the read endpoint groups in Python at query time.

Costs are computed at write-time from a static price table so a future
Anthropic price change doesn't retroactively rewrite history.

Revision ID: 0019_llm_costs
Revises:    0018_predicate_registry
Create Date: 2026-06-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019_llm_costs"
down_revision: str | None = "0018_predicate_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_costs (
            id              BIGSERIAL PRIMARY KEY,
            org_id          VARCHAR(64) NOT NULL,
            agent_id        VARCHAR(64),
            model           VARCHAR(64) NOT NULL,
            purpose         VARCHAR(32) NOT NULL,
                -- 'extract' | 'intelligence' | 'custom_mapping' |
                -- 'persona_distill' | 'proactive' | 'artifact_narrate'
            input_tokens    INT NOT NULL DEFAULT 0,
            output_tokens   INT NOT NULL DEFAULT 0,
            cost_usd        NUMERIC(10, 6) NOT NULL DEFAULT 0,
            credits_billed  INT NOT NULL DEFAULT 0,
                -- mirrors what was deducted from credit_ledger; 0 if free
                -- (e.g. extraction is 0 credits per MD §8.2 but still logged)
            success         BOOLEAN NOT NULL DEFAULT TRUE,
            error           TEXT,
            source_item_id  VARCHAR(120),
                -- back-pointer when call was triggered by an ingest item
            decision_id     VARCHAR(64),
                -- back-pointer when call served an intelligence query
            ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    # Read patterns: "what did this org spend today" + "what was the most
    # expensive call last week" + "circuit breaker — sum today's cost_usd".
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_llm_costs_org_ts "
        "ON llm_costs (org_id, ts DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_llm_costs_org_purpose "
        "ON llm_costs (org_id, purpose, ts DESC)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS llm_costs")

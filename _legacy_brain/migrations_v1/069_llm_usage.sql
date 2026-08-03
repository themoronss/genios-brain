-- Phase 1.1 — llm_usage table for unified LLM cost tracking
-- Every LLMClient.call(...) inserts one row. Powers daily cost guardrail.

CREATE TABLE IF NOT EXISTS llm_usage (
    id                  BIGSERIAL PRIMARY KEY,
    org_id              UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    called_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    purpose             TEXT NOT NULL,
    provider            TEXT NOT NULL,
    model               TEXT NOT NULL,
    input_tokens        INT NOT NULL DEFAULT 0,
    output_tokens       INT NOT NULL DEFAULT 0,
    cache_read_tokens   INT NOT NULL DEFAULT 0,
    cache_write_tokens  INT NOT NULL DEFAULT 0,
    cost_usd            NUMERIC(10,6) NOT NULL DEFAULT 0,
    latency_ms          INT,
    trace_id            TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_org_called
    ON llm_usage (org_id, called_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_purpose
    ON llm_usage (purpose, called_at DESC);

ALTER TABLE llm_usage ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS org_isolation ON llm_usage;
CREATE POLICY org_isolation ON llm_usage FOR ALL TO authenticated
    USING (org_id = auth.uid()::uuid) WITH CHECK (org_id = auth.uid()::uuid);

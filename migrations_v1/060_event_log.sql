-- Migration 060: Immutable event log — the single source of truth.
--
-- Every inbound fact (email, calendar change, slack msg, agent action) is
-- written here FIRST, then projected into contacts/interactions tables by
-- downstream consumers. Deduped by payload_hash so retries are safe.

CREATE TABLE IF NOT EXISTS event_log (
    id              BIGSERIAL PRIMARY KEY,
    org_id          UUID        NOT NULL,
    source          TEXT        NOT NULL,          -- gmail, calendar, slack, agent, manual
    verb            TEXT        NOT NULL,          -- reply, send, update, create, delete
    actor           TEXT,                           -- email/slack-user/agent_id
    object_type     TEXT,                           -- email, event, page, issue, interaction
    object_id       TEXT,
    payload         JSONB       NOT NULL,
    payload_hash    TEXT        NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,
    processed_status TEXT       DEFAULT 'pending',  -- pending / projected / failed / ignored
    process_error   TEXT,
    CONSTRAINT uq_event_payload_hash UNIQUE (org_id, payload_hash)
);

CREATE INDEX IF NOT EXISTS idx_event_org_time
    ON event_log (org_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_event_pending
    ON event_log (org_id, processed_status, observed_at)
    WHERE processed_status = 'pending';

CREATE INDEX IF NOT EXISTS idx_event_source_verb
    ON event_log (org_id, source, verb, observed_at DESC);

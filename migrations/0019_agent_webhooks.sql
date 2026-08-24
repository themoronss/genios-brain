-- Proactive push (GeniOS -> agent). An agent may register a webhook_url; when L5 emits a card for
-- the org, we POST the same projection the agent would otherwise poll (/v1/signals), HMAC-signed
-- with the agent's own webhook_secret (X-Genios-Signature). Null webhook_url = poll-only agent.
alter table agent_registry add column if not exists webhook_url    text;
alter table agent_registry add column if not exists webhook_secret text;

-- Fan-out at push time selects active agents in the org that have a webhook — keep it index-cheap.
create index if not exists agent_registry_webhook_by_org
    on agent_registry (org_id) where webhook_url is not null;

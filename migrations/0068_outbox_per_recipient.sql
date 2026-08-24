-- L6-09: an agent delivery becomes an outbox row, and an org can have several agents.
--
-- delivery_outbox_once was UNIQUE (org_id, card_id, channel): correct while every channel had
-- one implicit recipient per org, wrong the moment the same card fans out to two agents on the
-- same 'agent_push' channel — the second agent's row silently deduped away. Recipient joins the
-- key; NULL recipient (org-wide digest, tenant surface) coalesces to '' so those rows keep
-- exactly their old one-per-card semantics.
drop index if exists delivery_outbox_once;
create unique index delivery_outbox_once
    on delivery_outbox (org_id, card_id, channel, coalesce(recipient, ''));

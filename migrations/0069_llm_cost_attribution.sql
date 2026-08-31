-- X-10: cost attribution below the org.
--
-- llm_costs had org, model, purpose — enough for a monthly bill, useless for the mandated
-- metric "cost per useful accepted decision": no way to say WHICH card/signal/execution a call
-- was spent on, so margin and ROI claims stayed uncomputable by construction. Two keys:
--   subject_ref  — the engine-side object the spend served (card_id / signal_id / event_id
--                  prefixed, e.g. 'card:card_abc'), joining into the L7 ledger
--   client_context_id — the tenant-side context (a client's own thread/deal id) when a call
--                  was made on behalf of one; NULL for background/org-wide work.
-- Nullable and additive: existing writers keep working, new writers attribute what they know.
alter table llm_costs add column if not exists subject_ref text;
alter table llm_costs add column if not exists client_context_id text;
create index if not exists llm_costs_subject on llm_costs (org_id, subject_ref)
    where subject_ref is not null;

comment on column llm_costs.subject_ref is
  'What the spend served: card:<id> | signal:<id> | event:<id>. NULL = unattributed/background.';
comment on column llm_costs.client_context_id is
  'The client-side context the call was made on behalf of, when one exists.';

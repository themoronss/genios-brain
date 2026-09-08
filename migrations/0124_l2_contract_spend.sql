-- L2.3.5 · durable, replayable contract-to-spend attribution.
create table if not exists contract_spend_attributions (
    link_id                 text primary key,
    org_id                  text not null references orgs (id) on delete cascade,
    spend_node_id           text not null,
    contract_node_id        text,
    attribution             text not null check (attribution in ('exact','strong','unattributed')),
    amount_minor_units      bigint not null check (amount_minor_units >= 0),
    currency                text not null check (currency ~ '^[A-Z]{3}$'),
    occurred_at             timestamptz not null,
    counts_toward_spend     boolean not null,
    findings                jsonb not null default '[]'::jsonb,
    candidate_contract_ids  jsonb not null default '[]'::jsonb,
    input_fact_version_ids  jsonb not null,
    formula_version         text not null,
    content_hash            text not null,
    status                  text not null default 'active' check (status in ('active','superseded')),
    valid_from              timestamptz not null,
    valid_to                timestamptz,
    created_at              timestamptz not null default now(),
    constraint contract_spend_has_inputs check (jsonb_array_length(input_fact_version_ids) > 0),
    constraint contract_spend_unattributed_shape check (
        (attribution = 'unattributed' and contract_node_id is null and not counts_toward_spend)
        or (attribution <> 'unattributed' and contract_node_id is not null))
);

create index if not exists contract_spend_current
    on contract_spend_attributions (org_id, spend_node_id)
    where valid_to is null;

comment on table contract_spend_attributions is
  'L2.3.5 contract-spend decision ledger. Amounts remain integer minor units and currency-partitioned; ambiguous or out-of-term spend is explicitly unattributed, never guessed.';

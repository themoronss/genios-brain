-- L1.4 · per-tenant activation for the Layer 1 semantic lane (doc 04, wave W4's migration note).
--
-- A strangler fig needs a switch with a tenant on it. Doc 04 names this table and says why it may
-- not be a config boolean: `use_domain_compiler=False` is set in no environment and has left 152
-- capabilities dark, because a global flag has two states and both are wrong during a migration —
-- off means the new path is never exercised by anything real, on means every tenant's bill changes
-- on one deploy.
--
-- Empty by default, and an empty table means NOBODY is on the new lane, which is the state this
-- ships in. `enabled_by` is stored because a tenant whose extraction path changed needs an answer
-- to "who decided this, and when".
create table if not exists l1_semantic_activation (
    org_id      text primary key,
    enabled_at  timestamptz not null default now(),
    enabled_by  text not null
);

-- Doc 07: "Every new table in this plan must be added to the existing 0033_org_data_cascade.sql
-- pattern. A table that survives a tenant deletion is a compliance defect, and it is the kind that
-- is only discovered during an audit."
alter table l1_semantic_activation drop constraint if exists l1_semantic_activation_org_cascade_fk;
alter table l1_semantic_activation add constraint l1_semantic_activation_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

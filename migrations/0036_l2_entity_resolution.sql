-- GeniOS Engine · L2 · Entity Resolution — many names, one node.
--
-- THE PROBLEM THIS SOLVES
-- Until now two nodes were the same entity only if their canonical_key strings were
-- byte-identical. So:
--   * "Acme Inc." named in an email never reached the company node built from acme.io
--   * rohit@acme.io and rohit@gmail.com stayed two unrelated people forever
--   * merge_proposals — the table for exactly this — had never received a single row
--
-- THE RULE (platform.identity, D8): exact key equality is the ONLY auto-merge. Name
-- similarity is a candidate FINDER, never a merge authority. So this migration adds a
-- lookup table, not a matching heuristic: an alias is a key someone can be FOUND by.
-- When two different nodes claim the same alias, that is a merge PROPOSAL for a human,
-- never a silent join. Two colleagues really can share a name.

create table if not exists graph_aliases (
    org_id              text not null,
    alias_type          text not null,   -- email | domain | company_name | person_name
    alias_key           text not null,   -- normalized by platform.identity
    node_id             text not null,
    -- how this alias was learned. 'anchor' = derived from the node's own canonical key
    -- (a fact); 'observed' = seen alongside the entity in content (a hint).
    origin              text not null default 'anchor',
    created_by_event_id text,
    created_at          timestamptz not null default now(),
    -- One owner per key per org. The conflict IS the signal: an insert that would break
    -- this is a collision, and a collision becomes a merge proposal.
    primary key (org_id, alias_type, alias_key)
);
create index if not exists graph_aliases_by_node on graph_aliases (org_id, node_id);

-- Tenant erasure is complete BY SCHEMA, not by an application list someone remembers to
-- update (tests/test_account_erasure.py proves every org-scoped table has this path).
-- An alias holds a person's name and their employer's domain; leaving those behind after
-- an account deletion is exactly the residue erasure is supposed to remove.
alter table graph_aliases drop constraint if exists graph_aliases_org_cascade_fk;
alter table graph_aliases add constraint graph_aliases_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

-- merge_proposals already exists (0004) and was never written to. It needs a reason and
-- a de-dup guard, or the same pair is proposed again on every single event.
alter table merge_proposals add column if not exists reason text;
alter table merge_proposals add column if not exists node_type text;

-- One OPEN proposal per unordered pair. The resolver orders the pair before inserting,
-- so (A,B) and (B,A) cannot both sit in the queue.
create unique index if not exists merge_proposals_unique_open
    on merge_proposals (org_id, left_node_id, right_node_id)
    where status = 'open';

comment on table graph_aliases is
  'Keys an entity can be FOUND by. Never an identity claim: a collision on (org, alias_type, alias_key) raises a merge proposal for a human rather than merging nodes.';

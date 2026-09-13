-- 0146 · WHO A PRIVATE FACT BELONGS TO (SCREEN_INTEL_P2 §3.4, plan §14).
--
-- `graph_facts.visibility_scope` has existed since 0004 (default 'org') and nothing ever wrote
-- anything but 'org' through `write_fact`, nor read it. A fact learned only from a PRIVATE source
-- (a seat's screen session, a personal upload) and outside the work families is now written
-- `private`, and these are the addresses allowed to read it (the seat email). NULL for every
-- non-private fact. See genios_engine/context/fact_visibility.py for the readers that honour it.
alter table graph_facts add column if not exists visibility_principals text[];

-- Readers ask "which of this org's live facts are private?" once per pass (domain shadow, cards).
create index if not exists graph_facts_private_live
    on graph_facts (org_id, subject_node_id)
    where visibility_scope = 'private' and valid_to is null;

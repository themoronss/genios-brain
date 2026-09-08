-- L2.1.2 · make the provenance contract queryable on every graph fact.
-- Existing rows are deliberately labelled legacy_unclassified; inventing their missing lineage
-- during a migration would be worse than preserving the absence explicitly.
alter table graph_facts
    add column if not exists derivation_type text not null default 'legacy_unclassified',
    add column if not exists trace_id text,
    add column if not exists schema_version text not null default 'graph-fact.v1',
    add column if not exists source_authority text not null default 'unknown',
    add column if not exists provenance_refs jsonb not null default '[]'::jsonb;

alter table graph_facts drop constraint if exists graph_fact_provenance_refs_array;
alter table graph_facts add constraint graph_fact_provenance_refs_array
    check (jsonb_typeof(provenance_refs) = 'array');

alter table graph_facts drop constraint if exists graph_fact_new_provenance_required;
alter table graph_facts add constraint graph_fact_new_provenance_required
    check (derivation_type = 'legacy_unclassified'
           or (trace_id is not null and jsonb_array_length(provenance_refs) > 0));

comment on column graph_facts.derivation_type is
  'source_event | deterministic_derived | legacy_unclassified. New application writers always choose explicitly.';
comment on column graph_facts.provenance_refs is
  'Input event/fact/table receipts for this fact. A join key list, not a replacement for graph_source_refs evidence spans.';

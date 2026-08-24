-- L1-04: the source's own ACL, carried forward from capture.
--
-- contracts/visibility.py existed, fully tested, and nothing on the capture path called it —
-- source_events had no column, so every event was org-scoped from landing and a two-person
-- private thread was indistinguishable from a company-wide page to every layer above.
--
-- Three columns instead of one jsonb: scope is filtered on (partial indexes, gate queries),
-- principals is queried with array operators, and derived_from is a plain audit label. NULL in
-- visibility_scope means "captured before this migration" — distinguishable from every real
-- scope, exactly like recipients' NULL-vs-empty convention on this table.
alter table source_events add column if not exists visibility_scope text;
alter table source_events add column if not exists visibility_principals text[];
alter table source_events add column if not exists visibility_derived_from text;

-- Guarded like 0064's: the startup migration runner and a manual psql application must both be
-- able to run this file — a bare ADD CONSTRAINT made the second runner crash the deploy with
-- DuplicateObject (exactly what took down the first production rollout of this branch).
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'source_events_visibility_scope_ck') then
    alter table source_events add constraint source_events_visibility_scope_ck
        check (visibility_scope is null
               or visibility_scope in ('public', 'org', 'participants', 'private')) not valid;
  end if;
end $$;

comment on column source_events.visibility_scope is
  'Who could see the original: public | org | participants | private. NULL = captured before visibility existed.';
comment on column source_events.visibility_principals is
  'Lowercased emails; meaningful only for participants/private scopes.';
comment on column source_events.visibility_derived_from is
  'Which rule named the audience (connector:gmail:participants, system_of_record:hubspot, ...) — a wrong audience traces to its rule.';

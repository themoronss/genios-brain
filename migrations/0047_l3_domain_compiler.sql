-- Atlas Layer 3: immutable, tenant-scoped ExpertisePackage publication.
-- The package is the exact boundary artifact consumed by Layer 4. Dynamic brain history remains
-- in learned_brain_entries; this row pins the selected versions and authored source hashes.

create table if not exists expertise_packages (
    org_id              text not null,
    expertise_id        text not null,
    semantic_hash       text not null,
    schema_version      text not null,
    trace_id            text not null,
    situation_id        text not null,
    brain_snapshot_id   text not null,
    visibility          jsonb not null,
    payload             jsonb not null,
    created_at          timestamptz not null default clock_timestamp(),
    primary key (org_id, expertise_id),
    constraint expertise_packages_org_fk foreign key (org_id)
        references orgs(id) on delete cascade,
    constraint expertise_id_shape check (expertise_id ~ '^expertise_[0-9a-f]{64}$'),
    constraint expertise_semantic_hash_shape check (semantic_hash ~ '^[0-9a-f]{64}$'),
    constraint expertise_schema_version check (schema_version = 'expertise-package.v1'),
    constraint expertise_trace_required check (nullif(btrim(trace_id), '') is not null),
    constraint expertise_situation_required check (nullif(btrim(situation_id), '') is not null),
    constraint expertise_brain_snapshot_shape check (
        brain_snapshot_id ~ '^brains_[0-9a-f]{64}$'),
    constraint expertise_visibility_valid check (
        jsonb_typeof(visibility) = 'object'
        and visibility->>'scope' in ('public','org','participants','private')
        and visibility ? 'principals'
        and jsonb_typeof(visibility->'principals') = 'array'
        and nullif(btrim(visibility->>'derived_from'), '') is not null),
    constraint expertise_payload_object check (jsonb_typeof(payload) = 'object'),
    constraint expertise_payload_projection check (
        payload->>'org_id' = org_id
        and payload->>'id' = expertise_id
        and payload->>'schema_version' = schema_version
        and payload->>'trace_id' = trace_id
        and payload->>'situation_id' = situation_id
        and payload->>'brain_snapshot_id' = brain_snapshot_id
        and payload->'visibility' = visibility)
);

create unique index if not exists expertise_packages_content
    on expertise_packages (org_id, semantic_hash);
create index if not exists expertise_packages_trace
    on expertise_packages (org_id, trace_id);
create index if not exists expertise_packages_situation
    on expertise_packages (org_id, situation_id, created_at desc);
create index if not exists expertise_packages_brain_snapshot
    on expertise_packages (org_id, brain_snapshot_id);

create or replace function reject_expertise_package_update()
returns trigger language plpgsql as $$
begin
    raise exception 'ExpertisePackage rows are immutable';
end;
$$;

drop trigger if exists expertise_packages_no_update on expertise_packages;
create trigger expertise_packages_no_update
before update on expertise_packages
for each row execute function reject_expertise_package_update();

comment on table expertise_packages is
    'Immutable Atlas Layer 3 output: one situation plus one pinned four-brain snapshot.';

-- Layer 3 scopes dynamic reads by the capability identity already present in L6 values. Exact
-- subject keys use learned_brain_entries' existing unique index; this expression index prevents
-- a capability package from scanning every learned entry in a large tenant.
create index if not exists learned_brain_entries_capability
    on learned_brain_entries (org_id, (value->>'capability_id')) where active;

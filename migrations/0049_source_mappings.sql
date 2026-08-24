-- Custom-source field mappings: how an arbitrary customer data source's fields map onto the
-- canonical capture shape. Human-confirmed, versioned, frozen. Ported from the v1 backend and
-- adapted to text ids / the v2 connections model.

create table if not exists source_mappings (
    id                text primary key,
    org_id            text not null references orgs(id) on delete cascade,
    connection_id     text not null,
    source_type       text not null,
    mapping_json      jsonb not null,
    version           int not null default 1,
    source_confidence numeric,
    confirmed_by      text,
    confirmed_at      timestamptz not null default now(),
    active            boolean not null default true
);
create index if not exists source_mappings_org on source_mappings (org_id);
-- One active mapping per (org, connection, source_type); older versions are deactivated on confirm.
create unique index if not exists source_mappings_active
    on source_mappings (org_id, connection_id, source_type) where active;

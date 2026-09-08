-- L2.5.5 / L2.6 · explicit licence for a pattern to conclude an edge is missing.
create table if not exists edge_coverage_declarations (
    org_id          text not null references orgs (id) on delete cascade,
    edge_type       text not null,
    coverage_ready  boolean not null default false,
    coverage_basis  jsonb not null default '[]'::jsonb,
    coverage_epoch  integer not null check (coverage_epoch > 0),
    declared_by     text not null,
    declared_at     timestamptz not null,
    primary key (org_id, edge_type),
    constraint edge_coverage_ready_has_basis check (
        not coverage_ready or jsonb_array_length(coverage_basis) > 0)
);

comment on table edge_coverage_declarations is
  'Audited per-tenant licence for negative edge inference. Observed edge presence never implies coverage; only a ready declaration with a named capability basis may satisfy edge op=missing.';

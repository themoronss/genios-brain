-- L4 prerequisite: config snapshots are content-addressed but tenant-owned.
--
-- The original primary key covered snapshot_id alone.  Because snapshot_id is a
-- hash of effective configuration (not org_id), two tenants running the same
-- configuration produce the same identifier.  The second tenant therefore
-- could not persist its own provenance row.  All new reasoning foreign keys are
-- tenant-scoped, so make ownership explicit before adding them.

alter table config_snapshots drop constraint if exists config_snapshots_pkey;

alter table config_snapshots
    add constraint config_snapshots_pkey primary key (org_id, snapshot_id);

-- Recreate tenant-owned rows for historical signals that shared a snapshot
-- inserted by another tenant.  The effective bytes are identical by definition
-- of the content address.  DISTINCT ON prevents a cross-product when several
-- signals reference the same snapshot.
insert into config_snapshots
    (snapshot_id, org_id, pack_id, effective, cause, created_at)
select distinct on (s.org_id, cs.snapshot_id)
       cs.snapshot_id,
       s.org_id,
       cs.pack_id,
       cs.effective,
       'tenant_scope_backfill',
       cs.created_at
from signals s
join config_snapshots cs on cs.snapshot_id = s.config_snapshot_id
where s.config_snapshot_id is not null
order by s.org_id, cs.snapshot_id, cs.created_at asc
on conflict (org_id, snapshot_id) do nothing;

create index if not exists config_snapshots_by_snapshot
    on config_snapshots (snapshot_id);

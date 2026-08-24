-- GeniOS Engine · L4 · Domain Packs. pack = data, engine = code. A pack is an immutable,
-- content-addressed, versioned bundle (rules + scoring + plays + schema). Applied per
-- tenant with zero deploy; every signal stamps the config_snapshot that produced it.

-- Immutable content-addressed pack versions (LVL1 = expert baseline).
create table if not exists pack_registry (
    pack_id     text not null,
    version     text not null,                    -- semver, strictly increasing per pack_id
    manifest    jsonb not null,                   -- rules + scoring_defaults + plays + schema
    checksum    text not null,                    -- sha256 over the manifest (content address)
    created_at  timestamptz not null default now(),
    primary key (pack_id, version)
);

-- Which pack version a tenant runs + their LVL2 (admin) / LVL3 (learned) overrides + pins.
create table if not exists tenant_packs (
    org_id      text not null,
    pack_id     text not null,
    version     text not null,
    lvl2_config jsonb not null default '{}',      -- admin overrides
    lvl3_config jsonb not null default '{}',      -- L6-learned (nudges)
    pins        jsonb not null default '[]',      -- pinned paths (LVL2 freezes)
    state       text not null default 'active',   -- active | shadow | disabled
    updated_at  timestamptz not null default now(),
    primary key (org_id, pack_id)
);

-- Effective config snapshots — the truth of record. Every signal FKs one; replay resolves
-- snapshot → effective → byte-identical signal. Immutable, retained for the tenant's life.
create table if not exists config_snapshots (
    snapshot_id text primary key,                 -- sha256 of canonical effective JSON
    org_id      text not null,
    pack_id     text not null,
    effective   jsonb not null,                   -- canonical merged config
    cause       text not null,                    -- pack_apply|pack_promote|pack_rollback|lvl2_edit|lvl3_nudge
    created_at  timestamptz not null default now()
);
create index if not exists config_snapshots_by_org on config_snapshots (org_id, pack_id);

-- every signal carries the config snapshot that produced it (Law 6 · replay)
alter table signals add column if not exists config_snapshot_id text;

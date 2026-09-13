-- 0154 · POST-PASS WATERMARKS (SCREEN_INTEL_P4 §3.1).
--
-- The post-passes run after every L2→L4→cards chain. Each one reads only what changed since its
-- own last run: one row per (org, pass). A pass advances its watermark only after its writes
-- commit, so a crash re-reads (and, digest-gated, re-emits nothing) rather than skipping.
create table if not exists post_pass_watermarks (
    org_id     text not null references orgs (id) on delete cascade,
    pass_id    text not null,
    watermark  timestamptz not null,
    updated_at timestamptz not null default now(),
    primary key (org_id, pass_id)
);

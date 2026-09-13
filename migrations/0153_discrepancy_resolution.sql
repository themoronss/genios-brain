-- 0153 · DISCREPANCY RESOLUTION (SCREEN_INTEL_P4 §3.3).
--
-- `discrepancies` (0004) has always been written and never been answerable: a field was contested
-- until a later write happened to supersede it. A person can now settle one:
--   accept → the challenger value is written as a human-confirmed fact (status 'resolved');
--   keep   → the held value stands and the SAME challenger (by `challenger_digest`) is not raised
--            again for 30 days (status 'kept');
--   snooze → hidden until `snoozed_until`, then open again (status 'snoozed').
-- `updated_at` moves whenever the disagreement itself changes, so the verify post-pass reads only
-- what changed since its watermark (0154) instead of every open row on every chain run.
alter table discrepancies add column if not exists updated_at timestamptz not null default now();
alter table discrepancies add column if not exists resolved_at timestamptz;
alter table discrepancies add column if not exists resolved_by text;
alter table discrepancies add column if not exists resolution text;
alter table discrepancies add column if not exists snoozed_until timestamptz;
alter table discrepancies add column if not exists challenger_digest text;

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'discrepancies_resolution_ck') then
        alter table discrepancies add constraint discrepancies_resolution_ck
            check (resolution is null or resolution in ('accept', 'keep', 'snooze', 'superseded'));
    end if;
end $$;

-- The verify pass: "what changed since my watermark", per org.
create index if not exists discrepancies_by_update on discrepancies (org_id, updated_at);
-- write_discrepancy's "was this exact challenger kept in the last 30 days?" probe.
create index if not exists discrepancies_kept
    on discrepancies (org_id, subject_node_id, field, challenger_digest)
    where status = 'kept';

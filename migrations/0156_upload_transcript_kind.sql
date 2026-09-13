-- 0156 · UPLOAD KIND + ATTENDEES SCOPE (SCREEN_INTEL_P5 §3 upload contract).
--
-- `kind=transcript` uploads share the resource_uploads row (listing, delete, status) with
-- documents. Their scope is `attendees` (the meeting's attendees + the uploader) or `personal`;
-- both name a seat, so the seat rule of 0137 extends to the new value unchanged.
alter table resource_uploads add column if not exists kind text not null default 'document';

do $$
begin
    if exists (select 1 from pg_constraint where conname = 'resource_uploads_scope_check') then
        alter table resource_uploads drop constraint resource_uploads_scope_check;
    end if;
    alter table resource_uploads add constraint resource_uploads_scope_check
        check (scope in ('company', 'personal', 'attendees')
               and (scope = 'company' or seat_id is not null));
end $$;

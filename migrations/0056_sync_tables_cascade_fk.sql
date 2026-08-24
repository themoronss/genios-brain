-- Schema-enforced account deletion for the two new org-scoped tables (onboarding_progress from
-- 0054, sync_jobs from 0055). The account-erasure invariant requires every org_id table to cascade
-- from orgs, so a full account delete leaves nothing behind. Clean any orphan rows first so the
-- constraint validates.

delete from onboarding_progress where org_id not in (select id from orgs);
delete from sync_jobs where org_id not in (select id from orgs);

-- Idempotent (drop-if-exists then add) so a re-run at boot doesn't fail on an already-present
-- constraint (these FKs may already have been applied out-of-band).
alter table onboarding_progress drop constraint if exists onboarding_progress_org_fk;
alter table onboarding_progress add constraint onboarding_progress_org_fk
    foreign key (org_id) references orgs(id) on delete cascade;

alter table sync_jobs drop constraint if exists sync_jobs_org_fk;
alter table sync_jobs add constraint sync_jobs_org_fk
    foreign key (org_id) references orgs(id) on delete cascade;

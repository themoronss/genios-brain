-- GeniOS Engine · organization_resets was missing the org delete-cascade every org-scoped table
-- must carry (test_account_erasure.py's invariant) — added here rather than editing 0059 in place
-- since that migration is already applied and checksummed.
alter table organization_resets
    add constraint organization_resets_org_fk
    foreign key (org_id) references orgs (id) on delete cascade;

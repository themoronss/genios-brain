-- G012 (24 Oct) · the goal tables go with their org: ON DELETE CASCADE to orgs, as every org-scoped table's.
--
-- 0254 created `company_goals` and `goal_situation_links` with `org_id` and no foreign key, so deleting an account
-- left a founder's goals — their own words about what the company works toward — behind
-- (`tests/test_account_erasure.py`), and `/reset` did not erase them (`api/account_routes._ORG_SCOPED_TABLES`).
-- Measured on the test database: goal rows of an org that no longer exists (`org_golden_f61`), left by exactly
-- that. They are removed first — rows of a deleted org are no one's — and the constraint then holds from here on.
-- 0254 is not edited: an applied migration is immutable.

delete from goal_situation_links l where not exists (select 1 from orgs o where o.id = l.org_id);
delete from company_goals g where not exists (select 1 from orgs o where o.id = g.org_id);

alter table company_goals drop constraint if exists company_goals_org_id_fkey;
alter table company_goals
    add constraint company_goals_org_id_fkey foreign key (org_id) references orgs (id) on delete cascade;

alter table goal_situation_links drop constraint if exists goal_situation_links_org_id_fkey;
alter table goal_situation_links
    add constraint goal_situation_links_org_id_fkey foreign key (org_id) references orgs (id) on delete cascade;

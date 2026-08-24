-- Account & org-management (Settings page). Profile fields on the org, notification prefs, and
-- multi-member support (owner lives in orgs; invited teammates + pending invites live here).
alter table orgs add column if not exists first_name  text;
alter table orgs add column if not exists last_name   text;
alter table orgs add column if not exists company     text;
alter table orgs add column if not exists role        text;
alter table orgs add column if not exists notif_prefs jsonb not null default '{}';

-- Accepted teammates (the owner is synthesised from orgs, not stored here).
create table if not exists org_members (
    id          text primary key,
    org_id      text not null,
    email       text not null,
    name        text,
    role        text not null default 'member',
    status      text not null default 'active',
    invited_at  timestamptz not null default now(),
    accepted_at timestamptz,
    unique (org_id, email)
);
create index if not exists org_members_by_org on org_members (org_id);

-- Pending invites (become an org_member on accept — accept flow is a later step).
create table if not exists org_invites (
    id         text primary key,
    org_id     text not null,
    email      text not null,
    role       text not null default 'member',
    created_at timestamptz not null default now(),
    expires_at timestamptz,
    unique (org_id, email)
);
create index if not exists org_invites_by_org on org_invites (org_id);

-- Customer requests for new domain packs (Expertise page). Customers request; the team enables.
create table if not exists domain_requests (
    id         text primary key,
    org_id     text not null,
    domain     text not null,
    note       text,
    status     text not null default 'received',   -- received | reviewing | enabled | declined
    created_at timestamptz not null default now()
);
create index if not exists domain_requests_by_org on domain_requests (org_id, created_at desc);

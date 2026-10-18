-- 0193 · org_self_identities — what a tenant declares is its own (STEP-04, who is us).
--
-- WHY. "Who is us" is decided in eighteen places across the engine, from `orgs.email`, the active
-- seats and `connections.external_account_id` — a column nothing writes (`speedrun008/YC-II W27/`
-- STEP-04 §8.2). An address of ours that is neither — the design partner's `ceo@thegenios.com`, which
-- only ever receives the founder's own mail — and the company's own domain had nowhere to be said. So
-- the engine typed that address a service, put it on "waiting longest" lines, and minted the
-- company's domain as an outside company.
--
-- Here the tenant says it. `platform/self_identity.identity_for` reads this table with the seats,
-- `orgs.email` and the connected accounts, and every module that asks "is this us?" asks it.
--
--   address   an exact address of ours, lowercase, +tag stripped as person keys are
--   domain    a domain every address of which is ours — never a public mail domain (gmail.com …);
--             the code refuses one, because a Gmail founder declaring gmail.com would make every
--             Gmail sender one of us, which is the defect STEP-04 removes from the support lane
--
-- Configuration, like a seat: `/reset` keeps it; the account's deletion takes it with the org.

create table if not exists org_self_identities (
    org_id       text not null references orgs(id) on delete cascade,
    kind         text not null,
    value        text not null,
    declared_by  text not null,
    declared_at  timestamptz not null default now(),
    primary key (org_id, kind, value),
    -- Named, and declared inline rather than dropped and re-added: the erasure guard reads a
    -- `drop constraint …org…` as an org cascade going away, and this table's name starts `org_`.
    constraint self_identity_kind check (kind in ('address', 'domain')),
    constraint self_identity_value check (value <> '' and value = lower(btrim(value)))
);

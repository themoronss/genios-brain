-- L5.0-U1 · `seat_responsibilities` — WHAT a person is accountable for, and WHEN.
--
-- WHAT THE ORG COULD SAY ABOUT A PERSON BEFORE THIS. Six columns: `org_id`, `seat_id`, `email`,
-- `role`, `active`, `created_at`, plus `manager_seat_id` bolted on by 0041. And `role` is TWO
-- WORDS WIDE — `admin | member` — consulted in exactly two places in the engine, both asking
-- the same question: who mans the unrouted queue.
--
-- So "Anisha is accountable for the WEST region's store operations, from 1 June" had no column,
-- table or edge to live in. She was enrolled as `member`, and thereafter the only thing the
-- system knew about her was her address and that she was not an admin. Person and organisation
-- were held; RESPONSIBILITY, BUSINESS SCOPE and EFFECTIVE INTERVAL had no home at all — which
-- is why every situation in the tenant is equally hers, and why a regional manager can be shown
-- a national aggregate and blamed for another region's shortfall.
--
-- `valid_from` IS PART OF THE PRIMARY KEY, copied deliberately from `authority_rules` (0097),
-- and it is what makes an ACTING role expressible. Today the only way to say "Anisha covers the
-- North for June" is to overwrite `manager_seat_id` on her reports' rows on 1 June and hope a
-- human remembers to overwrite them back on 1 July. Nobody does, so July's escalations still
-- climb to her — and worse, there is no row anywhere saying her term was meant to end, because
-- the June state was DESTROYED by the July write. A responsibility is never updated in place:
-- it is CLOSED with `valid_until` and a successor row is inserted, so "who was accountable for
-- the West in June?" stays answerable in September.
--
-- `scope_kind` + `scope_key` RATHER THAN A COLUMN PER BUSINESS. A region, a store, a client, a
-- project, a product line and a ward are the same shape — a named slice of the business one
-- person answers for — and a schema that named them would need a migration per customer, which
-- is the rigidity this whole branch has spent itself removing. The kind is free text on purpose:
-- an exporter's `depot` and a hospital's `ward` are not something this engine should have
-- opinions about, and a closed enum here would be `capture/domain/hints.py`'s four-domain regex
-- table in a new costume.
--
-- `accountability` IS WHAT THEY ARE TO IT, not what they may do about it. `owns`, `covers`,
-- `reviews`, `informed`. AUTHORITY IS NOT HERE and must not be added: `authority_rules` already
-- answers "may this person approve this", it is dated and source-ranked, and a second table
-- that also implied permission would be two answers to one question — the defect this branch
-- has now found fifteen times. Responsibility says a card is YOURS; authority says you may
-- SIGN it. A regional manager owns the region and cannot sign the contract.
--
-- `source` RANKS, AND ONE OF THE THREE MAY NEVER NARROW WHAT SOMEBODY SEES. Same three words as
-- 0097 and the same law: `admin_declared` (a human set it) beats `discovered` (read out of an
-- uploaded org chart) beats `inferred` (observed: this person handles the West's mail). An
-- INFERRED responsibility may WIDEN a person's view — proposing that something is probably
-- theirs is a suggestion nobody is harmed by — and may never NARROW it, because hiding a real
-- situation from somebody on the strength of a guess about their job is a silent false negative
-- and the one failure this table could introduce.
--
-- ABSENCE IS NOT A SCOPE. A tenant with no rows here has declared nothing, and every reader
-- must treat that as "this person's scope is the tenant" — exactly what happens today. Day one
-- changes nothing for anybody, and a tenant only ever narrows by writing a row.

-- THE FK IS THE ERASURE PATH, not the entry in `_ORG_SCOPED_TABLES`.
-- `tests/test_account_erasure.py::test_every_org_scoped_table_has_a_proven_account_delete_cascade`
-- caught this table without one, and it is right to: this is an ORG CHART — the tenant's own
-- staff and what each of them answers for, which region, which client, over which interval. A
-- deletion that skipped it would leave a deleted customer's reporting lines and territory
-- assignments in the database. The list entry makes `/reset` wipe it; the FK is what makes
-- ACCOUNT DELETION schema-enforced, and only one of those two is a guarantee.
create table if not exists seat_responsibilities (
    org_id         text not null references orgs (id) on delete cascade,
    seat_id        text not null,
    -- region | store | client | project | product_line | ward | … — the tenant's own word.
    scope_kind     text not null,
    -- The named slice: 'west', 'store-114', 'acme-corp'. Compared case-insensitively by the
    -- reader; stored as written so a console can show the author their own spelling.
    scope_key      text not null,
    accountability text not null default 'owns',
    source         text not null default 'admin_declared',
    -- What the org chart or the console said, verbatim, so a reviewer reads a sentence rather
    -- than a row. Nullable: a console entry has no document behind it.
    evidence_ref   text,
    valid_from     timestamptz not null,
    valid_until    timestamptz,
    created_at     timestamptz not null default now(),
    primary key (org_id, seat_id, scope_kind, scope_key, valid_from),
    constraint seat_responsibilities_window
        check (valid_until is null or valid_until > valid_from),
    constraint seat_responsibilities_source
        check (source in ('admin_declared', 'discovered', 'inferred')),
    constraint seat_responsibilities_accountability
        check (accountability in ('owns', 'covers', 'reviews', 'informed'))
);

-- The reader's shape: everything one person answers for, at one instant.
create index if not exists seat_responsibilities_by_seat
    on seat_responsibilities (org_id, seat_id, valid_from);

-- And the inverse: who answers for this slice, which is how a card finds its person.
create index if not exists seat_responsibilities_by_scope
    on seat_responsibilities (org_id, scope_kind, scope_key, valid_from);

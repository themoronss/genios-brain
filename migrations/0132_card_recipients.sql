-- L5.0-U3 · card_recipients — WHO ELSE ANSWERS FOR A CARD.
--
-- ONE CARD PER SIGNAL STAYS. `cards_one_per_signal` (0008) is keyed on the signal, three
-- writers upsert on it, refresh-in-place rewrites the words of the SAME row, and every reader
-- from the digest to the per-recipient budget counts rows. Widening it would make one
-- situation two lines in the admin's morning count and break the refresh. So the card is one
-- row, and the people it reaches are these.
--
-- Written beside the card by `deliver/store.insert_card` from `Assignment.co_recipients` —
-- the seats whose DECLARED responsibility (`seat_responsibilities`, 0129) covers a slice the
-- situation names. Read by the queue (a covering seat sees the card, stamped with why), by the
-- outbox (one delivery row per seat, never an interrupt) and by nothing that counts.
--
-- EMPTY ON DAY ONE. A tenant that declared nothing has no rows here and every read is what it
-- was. Cascades from both parents: a deleted card or account leaves no trace of who was told.
create table if not exists card_recipients (
    org_id         text not null references orgs (id) on delete cascade,
    card_id        text not null references cards (card_id) on delete cascade,
    seat_id        text not null,
    accountability text not null,
    -- the slice that made it theirs, verbatim from the declaration
    scope_kind     text not null,
    scope_key      text not null,
    source         text not null,
    -- who it stays with — the card's assignee at the time the recipients were written
    owner_seat     text,
    created_at     timestamptz not null default now(),
    primary key (org_id, card_id, seat_id),
    constraint card_recipients_accountability
        check (accountability in ('owns', 'covers', 'reviews', 'informed')),
    constraint card_recipients_source
        check (source in ('admin_declared', 'discovered', 'inferred'))
);
create index if not exists card_recipients_by_seat on card_recipients (org_id, seat_id);

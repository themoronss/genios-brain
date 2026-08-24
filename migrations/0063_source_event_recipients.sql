-- Recipients as first-class capture data, before the payload TTL takes them.
--
-- To/Cc survived only inside the encrypted `raw_payloads` blob, which carries a 30-day TTL. For
-- the design partner that means 2026-09-16: after it, the backfilled correspondence has no
-- recipient data anywhere in the system and even best-effort reconstruction stops being
-- possible. This is the rare defect with a date attached.
--
-- It is not only a retention problem. One sender per event cannot express who a conversation is
-- WITH: a mediated introduction, a message copied to nine people, and a direct reply are the
-- same shape to every layer above. That is the root of a card targeting an introducer as though
-- they were the counterparty, and of thread state that cannot tell a broadcast from a thread.

alter table source_events add column if not exists recipients text[];

comment on column source_events.recipients is
  'To + Cc, lowercased, in envelope order. Empty array = none carried; NULL = captured before the column existed.';

-- The question this answers is "which events involved this person at all", which the sender
-- column alone cannot: participation is not authorship.
create index if not exists source_events_recipients
  on source_events using gin (recipients);

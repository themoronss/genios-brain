-- 0115 · qualified_signals: the four provenance answers the row could not give.
--
-- Every one of these was computed on the capture path and then dropped at the seam, so a stored
-- signal could not answer a question somebody was always going to ask:
--
--   ingested_at          `occurred_at` is WORLD time (when the email was sent). Nothing recorded
--                        when WE first saw it, so "did this reach us late?" — a backfill against
--                        a live sync, a connector that stalled for a day — was unanswerable from
--                        the row. `source_events.captured_at` already holds it; this carries it
--                        across the seam.
--
--   content_hash         the sha256 of the prepared text the claims were read out of. The
--                        extraction cache already computes exactly this digest as part of its
--                        key (`capture/semantic/cache.py`), and it is what makes "the source was
--                        edited / re-fetched differently since this signal was published" a
--                        comparison rather than an opinion. Stored, never re-derived: the
--                        prepared row has a TTL and the digest must outlive it.
--
--   qualification_reason ALG-18 files its refusals with a reason (`qualification_drops`) and its
--                        acceptances with none, so a published row could not say WHY it crossed
--                        — at/above the floor, unscored-and-therefore-travels, carries a
--                        conflict, internal canon. Four different facts that all read as
--                        "published".
--
--   superseded_by        the FORWARD half of the supersession link. `supersedes` points
--                        backwards, so from an old signal there was no way to reach the newer
--                        one that replaced it without scanning the whole table for a row
--                        pointing at you. A founder asking "what replaced this?" is the ordinary
--                        case, not the rare one.
--
-- All four are nullable and none is backfilled: a row written before this migration genuinely
-- does not know, and a default would be an invented answer. NULL is the honest state.

alter table qualified_signals
    add column if not exists ingested_at          timestamptz,
    add column if not exists content_hash         text,
    add column if not exists qualification_reason text,
    add column if not exists superseded_by        text;

-- 64 lowercase hex or nothing. A truncated or upper-cased digest compares unequal to the same
-- content hashed by the cache, which is the one comparison the column exists for.
alter table qualified_signals
    drop constraint if exists qualified_signals_content_hash_shape;
alter table qualified_signals
    add constraint qualified_signals_content_hash_shape
    check (content_hash is null or content_hash ~ '^[0-9a-f]{64}$');

-- A signal cannot be replaced by itself. The backward half already carries the same rule in the
-- row dataclass; stating it here as well keeps a hand-written UPDATE from creating a cycle of one.
alter table qualified_signals
    drop constraint if exists qualified_signals_superseded_by_not_self;
alter table qualified_signals
    add constraint qualified_signals_superseded_by_not_self
    check (superseded_by is null or superseded_by <> signal_id);

-- "What replaced this?" resolved from the OLD id, which is the direction a human reads it in.
create index if not exists qs_superseded_by on qualified_signals (org_id, superseded_by)
    where superseded_by is not null;

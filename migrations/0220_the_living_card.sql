-- 0220 · the living card — a file's card names its file and its version (STEP-14, the card; §8.4 item 1,
-- tree `yc2_w27_s14` M42.C1.L-contract.V0.U01, `03` F176).
--
-- THE DEFECT. A card is its signal's (`cards_one_per_signal`, 0008), and since STEP-12 a covered file holds ONE
-- decision at a time — but every new decision on the file is a new signal, so it was a NEW card and the old
-- one was expired REPLACED: 10 replacements over 9 golden cases, eight must-detect cases lost (F02, F05, F06,
-- F12, F19, F24, F25, F50). The advice changed as the file moved, or the same advice was said in other words,
-- or the same advice came back after its window — and each time the founder saw a second card about one file.
--
-- THE FIX. A card names the FILE whose decisions and questions it carries — `file_id`, the file's anchor node
-- (`context/workstreams`), as `expert_reviews.file_id` (0197) and `founder_questions.file_id` (0201) do; NULL on
-- a card that is no file's: the legacy and compiled lanes, the P4 team and verify cards — and how many
-- versions it has had, `version`, 1 at creation. Each new decision or question on the file is a VERSION of
-- this card (`platform/card_lifecycle.version_card`, the one writer of `cards.signal_id`): re-pointed at the
-- new signal, its words rewritten in place, one `card.versioned` event keeping the words before — never a
-- second card.
--
-- ⛔ AT MOST ONE OPEN CARD PER FILE, held by the schema: a partial unique index over the states a card is in
-- front of somebody in (`platform/card_lifecycle.OPEN_STATES`, and `built`). A CLOSED card does not hold the
-- file's place: one the clock, a replacement or a clearing closed is reopened by the file's next version — the
-- writer's rule (s14-D2) — and one the founder decided (acted, resolved, dismissed) stays decided, so the
-- file's next card may stand beside it. A dismissal is recorded as an event (`card.dismissed`), not a state,
-- so the decided/closed distinction cannot be an index predicate; it is `version_card`'s.
--
-- ⛔ NO FOREIGN KEY ON `file_id`, as 0197 and 0201: a file is its anchor node, and the graph versions and
-- retires nodes — a card about a file since merged is still the card it was.
--
-- Additive and idempotent: two columns, one check, one partial index. The tenant reset already deletes
-- `cards` (`api/account_routes._ORG_SCOPED_TABLES`) and the tenant's deletion cascades (0033).
alter table cards add column if not exists file_id text;
alter table cards add column if not exists version integer not null default 1;

alter table cards drop constraint if exists cards_version_from_one;
alter table cards add constraint cards_version_from_one check (version >= 1);

create unique index if not exists cards_one_open_card_per_file on cards (org_id, file_id)
  where file_id is not null
    and state in ('built', 'queued', 'surfaced', 'snoozed', 'claimed', 'delivered');

comment on column cards.file_id is
  'The file (its anchor node) whose decisions and questions this card carries, one version at a time (0220, STEP-14). NULL on a card that is no file''s: the legacy and compiled lanes, the P4 team and verify cards.';
comment on column cards.version is
  'How many versions this card has had: 1 at creation, +1 each time the file''s next decision or question re-points it (platform/card_lifecycle.version_card, a card.versioned event each).';

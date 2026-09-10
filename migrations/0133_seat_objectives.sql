-- L5.0-U2 · `seat_objectives` — WHAT THIS PERSON IS WORKING ON RIGHT NOW, as an ordering key.
--
-- WHAT EXISTED. `user_models.priorities_jsonb` (migration 0023) is written and read only by its
-- own CRUD file; no sweep, compiler, scorer or ranker touches it. So two store managers on the
-- same morning — one three days from a launch, the other mid-audit — receive a queue ordered by
-- the identical S = C·(0.45U + 0.35I + 0.20R) over the identical tenant-wide set. The engine held
-- a place to write an objective and nothing that could read one.
--
-- COPIED FROM `org_mission_critical_entities` (0091), which is the right precedent: a per-tenant
-- HUMAN JUDGEMENT, owner-attributed, read on every relevant pass, changing what surfaces first.
-- This is the per-PERSON version of the same idea, and it is deliberately as small.
--
-- IT REORDERS. IT DOES NOT SCORE. The objective is read at the queue READ — `deliver/store.py
-- queue()`, which is already per-viewer — as a stable partition: cards in the objective's domain
-- first, then everything else, each half in its existing utility order. No U, I, R or C moves; no
-- `final_utility_bp` changes; no persisted audit row is re-stamped; two viewers still see the same
-- FACTS and the same SCORES. The owner's second boundary — preference is not truth — holds by
-- construction, because a preference here can only change the order of an explanation, never the
-- evidence in it. A bonus term would have broken `brief_ranking`'s invariant that no portfolio
-- term may raise a decision above what Layer 4 concluded; a partition cannot.
--
-- NOTHING IS HIDDEN. Every card the viewer could see before is still in the list. An objective
-- that could remove a card would be `seat_responsibilities`' narrowing power wearing a
-- preference's name, and the 0129 header explains why a preference may never narrow.
--
-- `domain` IS THE MATCH KEY, because it is the one thing a card actually carries that an
-- objective can be stated in — `cards.domain` has existed since 0008. A free-text objective
-- matched by keyword would be the rigidity this branch spent itself removing. `note` is the
-- sentence for the person who reads their own queue and wonders why the order changed.
--
-- `valid_until` IS NULLABLE AND HONOURED. "Focus on the launch this week" is a statement about
-- this week; a preference that can only be added is a queue that drifts for ever, which is the
-- argument 0091's DELETE route makes and this table makes with a date as well.

create table if not exists seat_objectives (
    org_id       text not null references orgs (id) on delete cascade,
    -- `lower(email)`, the identity `org_seats.email` matches on and the only per-person key the
    -- delivery layer holds.
    seat_key     text not null,
    domain       text not null,
    -- WHO answers for this judgement — never null, on 0088's argument: a change to what a
    -- person sees first is a change somebody owns.
    owner        text not null,
    note         text not null default '',
    added_at     timestamptz not null default now(),
    valid_until  timestamptz,
    primary key (org_id, seat_key),
    constraint seat_objectives_key_folded  check (seat_key = lower(seat_key)),
    constraint seat_objectives_key_present check (length(trim(seat_key)) > 0),
    constraint seat_objectives_domain_present check (length(trim(domain)) > 0),
    constraint seat_objectives_window check (valid_until is null or valid_until > added_at)
);

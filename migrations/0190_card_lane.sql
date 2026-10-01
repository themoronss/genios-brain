-- 0190 · the lane on the CARD — because the surface reads the card, not the signal.
--
-- WHAT WAS MISSING. `0189` put `output_lane` + `lane_reason` on `signals` and `reason/domain_shadow`
-- writes both on every routed decision. Then, grepped 2026-09-30:
--
--     grep -rn "output_lane\|lane_reason" genios_engine/deliver/   ->   nothing
--
-- Built, tested, green, and called by nothing — one step after the step that added the vocabulary to
-- end a different instance of exactly that. `0189`'s own header counted seven; this was the eighth,
-- and the first this programme produced itself. Every surface a founder touches — the app queue, Ask,
-- the agent API, the digest — reads the `cards` row. A lane that stops at `signals` reached nobody.
--
-- ⛔ A CORRECTION TO 0189's HEADER, RECORDED HERE BECAUSE A MIGRATION IS IMMUTABLE. That header says
-- *"`ReasoningDecision.to_semantic_dict` includes `output_lane` and `lane_reason`, so the lane is
-- inside `decision_hash`."* **That is no longer true, and it was wrong to do.** Putting the lane in
-- the hash broke four replay tests (`ReplayIntegrityError`) on decisions minted before the field
-- existed, and the reason it broke them is the reason it should never have been there:
-- `output_lane.route` is a PURE function of `outcome`, `confidence_bp` and the conflict flag, all of
-- which are already in the hash. The lane adds **zero** information to the decision's identity and a
-- derived value has no business in a content hash. It was removed from `contracts`, `audit` and
-- `store`. `0189` cannot be edited — its checksum is its immutability — so the correction lives here,
-- append-only, exactly as the ledger requires.
--
-- Everything else 0189 decided still holds and is not restated: NOT `outcome_kind`; the pair is atomic;
-- NULL is an answer.

-- ── the two columns ───────────────────────────────────────────────────────────────────────────
alter table cards add column if not exists output_lane text;
alter table cards add column if not exists lane_reason text;

-- ⛔ `unrouted` IS A VALUE HERE, AND IT IS NOT ON `signals`. The difference is deliberate.
--
-- On `signals`, NULL means "no router ever looked at this row" — a fact about the writer. On `cards`,
-- the card layer HAS looked, and decided the signal carried nothing it could honour; that is a fact
-- about the READ, and it is the answer the card displays. `deliver/lane_display.UNROUTED` is the same
-- word, and `card_source` set the precedent one file over: *"`situation_id IS NULL` is an ANSWER, not
-- a gap"* — surfaced, marked, and counted.
--
-- Keeping NULL here instead would make "not routed" and "not yet backfilled by this migration"
-- indistinguishable, and a count cannot tell those apart after the fact.
alter table cards drop constraint if exists cards_output_lane_check;
alter table cards add constraint cards_output_lane_check
    check (output_lane is null
           or output_lane in ('decision', 'investigation', 'conflict', 'monitor', 'suppress',
                              'unrouted'))
    not valid;

-- ⛔ A LANE WITHOUT ITS REASON CANNOT BE WRITTEN — the same atomicity 0189 enforces, with one
-- exception stated rather than implied: `unrouted` HAS no router reason, because no router ran. Its
-- reason is the absence itself, and inventing a sentence to satisfy a constraint would put words in
-- the row that no component said.
alter table cards drop constraint if exists cards_lane_has_a_reason;
alter table cards add constraint cards_lane_has_a_reason
    check (output_lane is null
           or output_lane = 'unrouted'
           or (lane_reason is not null and length(trim(lane_reason)) > 0))
    not valid;

-- "What is this tenant's queue actually made of?" — the read that turns the lane mix from an anecdote
-- into a measurement. Partial: a pre-0190 card has no lane and is not part of any mix.
create index if not exists cards_by_output_lane
    on cards (org_id, output_lane, created_at desc)
    where output_lane is not null;

comment on column cards.output_lane is
  'decision | investigation | conflict | monitor | suppress | unrouted — what KIND of output this '
  'card is. `unrouted` means the signal carried no lane this layer could honour; it is displayed and '
  'counted, never defaulted to `decision`. NULL means the card predates this migration.';

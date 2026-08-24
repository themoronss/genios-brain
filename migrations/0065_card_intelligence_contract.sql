-- The Customer Intelligence Contract, given somewhere to land.
--
-- Twelve things a promoted intelligence item must answer. Six had no column at all, so the
-- product's own definition of a useful card could not be stored even when the engine knew the
-- answer. Two of them were literally the string "missing", written into the read projection at
-- request time — `stakes` and `completion` were not absent by accident, they were hardcoded.
--
-- The distinction each column draws, and why an existing field could not carry it:
--
--   business_subject       WHO the loop is with. `assignee` is a GeniOS seat — the person who
--                          should act — which is a different party from the counterparty the
--                          action is aimed at. Conflating them is how a card came to target an
--                          introducer as though they were the investor.
--   relationship_role      WHAT they are to us: counterparty, introducer, introduced, approver.
--                          Without it every person is interchangeable and the deepest thing a
--                          rule can say is "somebody wrote".
--   unresolved_item        The exact open loop, in the counterparty's terms. "Reply to X" names
--                          a channel state; this names the thing actually outstanding.
--   why_now                What changed to make this actionable. Elapsed time alone is not a
--                          reason, and treating it as one is what manufactured urgency.
--   capability_key         Which authored expertise backed this, at which version, in which
--   capability_version     review state. `config_snapshot_id` records a PACK snapshot and
--   capability_review_state  `template_version` a card template — neither is a capability, so
--                          "what taught us to say this" had no home.
--   outcome_window_days    When we expect to know whether it worked.
--   success_signal         What would count as it having worked.
--   do_nothing_consequence What happens if the user ignores it — the honest counterweight to an
--                          imperative, and the field that makes a WAIT candidate legible.
--   confidence_vector      The decomposed confidence. A single scalar cannot say whether we are
--                          unsure about the evidence, the expertise, or the timing, and those
--                          call for different user actions.
--
-- Nullable throughout: existing cards predate the contract and must not be rewritten or
-- blocked. A NULL here means "this card never carried the answer", which is exactly the
-- measurement the scorecard needs — not something to paper over with a default.

alter table cards add column if not exists business_subject text;
alter table cards add column if not exists relationship_role text;
alter table cards add column if not exists unresolved_item text;
alter table cards add column if not exists why_now text;
alter table cards add column if not exists capability_key text;
alter table cards add column if not exists capability_version text;
alter table cards add column if not exists capability_review_state text;
alter table cards add column if not exists outcome_window_days integer;
alter table cards add column if not exists success_signal text;
alter table cards add column if not exists do_nothing_consequence text;
alter table cards add column if not exists confidence_vector jsonb;

comment on column cards.business_subject is
  'The counterparty this loop is WITH. Distinct from assignee, which is the GeniOS seat expected to act.';
comment on column cards.relationship_role is
  'What the business subject is to us: counterparty | introducer | introduced | owner | approver | observer | machine.';
comment on column cards.unresolved_item is
  'The exact open loop in the counterparty''s terms — not the channel state.';
comment on column cards.why_now is
  'What changed to make this actionable. Elapsed time alone is not a reason.';
comment on column cards.capability_review_state is
  'Whether the expertise behind this card was reviewed and accepted. Unreviewed must not instruct.';
comment on column cards.do_nothing_consequence is
  'What happens if this is ignored — the counterweight that makes an imperative honest and a WAIT legible.';
comment on column cards.confidence_vector is
  'Decomposed confidence. A scalar cannot distinguish unsure-about-evidence from unsure-about-timing, and those need different user actions.';

-- "How many cards can actually answer the contract" is the scorecard question, and it needs to be
-- answerable without scanning every row.
create index if not exists cards_contract_completeness
  on cards (org_id, capability_review_state)
  where business_subject is not null;

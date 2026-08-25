-- A signal produced by a compiled capability could not say so.
--
-- deliver/card_builder.py already reads `signal.get("capability_id")` to fill a card's
-- capability_key / capability_version / capability_review_state — the delivery side has been ready
-- for the compiled brain since those columns landed. `signals` never carried the fields, so the
-- lookup returned None on every DB-loaded signal and all 15 cards on the design-partner org came
-- out with capability_key NULL, indistinguishable from "the legacy rules produced this" because
-- that is in fact what produced it.
--
-- Nullable on purpose: a legacy pack rule has no capability and must keep emitting exactly as it
-- does today. The columns identify WHICH brain authored a signal, which is the only way a cutover
-- can be measured rather than believed.

alter table signals add column if not exists capability_id text;
alter table signals add column if not exists capability_version text;
alter table signals add column if not exists capability_review_state text;

comment on column signals.capability_id is
  'Compiled L3 capability that authored this signal. NULL = emitted by a legacy pack rule.';
comment on column signals.capability_review_state is
  'accepted | draft — mirrors the ExpertisePackage. Delivery abstains on anything not accepted, so a draft capability can reach a user only as an observation.';

-- "How much of the queue does the compiled brain actually author?" is the cutover's whole
-- question, and it should be one index scan rather than a table sweep.
create index if not exists signals_capability_authorship
  on signals (org_id, capability_id) where capability_id is not null;

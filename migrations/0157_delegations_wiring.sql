-- 0157 · P6 Act core — a MOMENT or a CARD can own a delegation (SCREEN_INTEL_P6_BUILD §3, §4-A).
--
-- 0073 built the ledger for Layer 5 executions only (`execution_id not null`), so nothing a person
-- sees — a meeting-prep moment, a team card — could hand work to the client's agent. P6 makes the
-- ledger subject-agnostic: a delegation names its seat, its moment and/or card, the typed play and
-- its params, and is idempotent on `proposal_key = sha256(org, moment|card, play, params)`.
--
-- The approval FREEZES the exact request bytes (the outbox row's payload carries them; the sha256
-- is kept here) so every retry resends identical bytes under the same Delivery-Id. `cancelled` is
-- the state a proposal takes when an edit supersedes it; `superseded_by` names the replacement.
--
-- `delivery_outbox.card_id` has NO foreign key to `cards` (0032/0044), so an agent_action row
-- carries the synthetic `dlg:<delegation_id>` card id — same convention as `digest:<date>` — AND
-- the real reference in `delivery_outbox.delegation_id`, unique per org: one outbox row per
-- delegation, however many approvals race. Never credit-charged.
alter table agent_delegations alter column execution_id drop not null;

alter table agent_delegations add column if not exists seat_id          text;
alter table agent_delegations add column if not exists moment_id        text;
alter table agent_delegations add column if not exists card_id          text;
alter table agent_delegations add column if not exists play             text;
alter table agent_delegations add column if not exists params           jsonb;
alter table agent_delegations add column if not exists proposal_key     text;
alter table agent_delegations add column if not exists request_sha256   text;
alter table agent_delegations add column if not exists superseded_by    text;
alter table agent_delegations add column if not exists approver_seat_id text;
alter table agent_delegations add column if not exists decision_reason  text;

alter table agent_delegations drop constraint if exists agent_delegations_state_check;
alter table agent_delegations add constraint agent_delegations_state_check
    check (state in ('proposed', 'approved', 'rejected', 'dispatched', 'succeeded', 'failed',
                     'expired', 'cancelled'));

create unique index if not exists agent_delegations_proposal_key
    on agent_delegations (org_id, proposal_key) where proposal_key is not null;
create index if not exists agent_delegations_moment
    on agent_delegations (org_id, moment_id);
create index if not exists agent_delegations_state
    on agent_delegations (org_id, state, proposed_at);

alter table delivery_outbox add column if not exists delegation_id text;
create unique index if not exists delivery_outbox_delegation
    on delivery_outbox (org_id, delegation_id) where delegation_id is not null;
-- The act pump (deliver/act_pump.py) asks "when is the next action row due?" after every pass.
create index if not exists delivery_outbox_act_due
    on delivery_outbox (next_attempt_at) where status = 'queued' and channel = 'agent_action';

comment on column agent_delegations.proposal_key is
  'sha256(org, moment|card, play, params) — a repeated proposal returns the existing row.';
comment on column delivery_outbox.delegation_id is
  'P6: the agent_action row for one approved delegation (at most one per delegation).';

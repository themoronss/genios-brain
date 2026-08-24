-- L4-05: the DecisionObject survives onto the signal row.
--
-- `signals` carried only score, reason_code, evidence and play — so the card layer rebuilt its
-- recommendation from the reason_code STRING through an if/elif chain in the API, a parallel
-- independent generator sharing nothing with Layer 4 but one label. The decision's own content
-- (what happens if you do nothing, what the engine was unsure about, which alternatives lost
-- and why, the steps of the chosen play) existed in the reasoning ledger and never reached any
-- surface. This is why cards read as activity reminders.
alter table signals add column if not exists do_nothing_consequence text;
alter table signals add column if not exists uncertainty jsonb;
alter table signals add column if not exists outcome_window_days int;
-- The candidates that LOST, with disposition + utility: the receipt that a choice happened.
alter table signals add column if not exists rejected_candidates jsonb;
-- The chosen play's authored steps — so the card renders what L4 decided, not what an API
-- helper re-guessed from the reason code.
alter table signals add column if not exists candidate_steps jsonb;

comment on column signals.do_nothing_consequence is
  'From ReasoningDecision — the stated cost of inaction. NULL = pre-0070 signal.';
comment on column signals.rejected_candidates is
  '[{play_id, disposition, utility_bp}] — the alternatives this decision beat (or that were eliminated).';
comment on column signals.candidate_steps is
  'The selected play''s authored steps, verbatim from the manifest.';

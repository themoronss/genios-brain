-- Layer 4 replay and emitted-signal integrity hardening.
--
-- Selector bytes are necessary to verify selector_hash independently.  The
-- column remains nullable for historical rows: replay fails closed for those
-- rows instead of pretending that a hash without bytes is independently
-- auditable.  Fresh installs receive NOT NULL from migration 0026.

alter table reasoning_context_snapshots
    add column if not exists selector jsonb;

alter table reasoning_context_snapshots
    add constraint reasoning_context_selector_object
    check (selector is null or jsonb_typeof(selector) = 'object')
    not valid;

-- Preserve the contract's distinct insufficient-context state and permit a
-- failed decision envelope to be retained as non-authoritative audit evidence.
alter table reasoning_reasoner_results
    drop constraint if exists reasoning_reasoner_results_status_check;

alter table reasoning_reasoner_results
    add constraint reasoning_reasoner_results_status_check
    check (status in ('completed', 'skipped', 'failed', 'insufficient_context'))
    not valid;

alter table reasoning_run_outputs
    drop constraint if exists reasoning_run_outputs_outcome_kind_check;

alter table reasoning_run_outputs
    add constraint reasoning_run_outputs_outcome_kind_check
    check (outcome_kind in ('decision', 'no_action', 'defer',
                            'insufficient_context', 'blocked', 'failed'))
    not valid;

-- The unique identity allows a signal to reference the run and exact config in
-- one tenant-scoped foreign key.  MATCH SIMPLE permits historical unlinked
-- signals; the check below requires every newly linked signal to carry config.
alter table reasoning_runs
    add constraint reasoning_runs_config_identity
    unique (org_id, run_id, config_snapshot_id);

alter table signals
    add constraint signals_config_snapshot_fk
    foreign key (org_id, config_snapshot_id)
    references config_snapshots (org_id, snapshot_id)
    not valid;

alter table signals
    add constraint signals_reasoning_run_config_fk
    foreign key (org_id, reasoning_run_id, config_snapshot_id)
    references reasoning_runs (org_id, run_id, config_snapshot_id)
    not valid;

alter table signals
    add constraint signals_linked_run_requires_config
    check (reasoning_run_id is null or config_snapshot_id is not null)
    not valid;

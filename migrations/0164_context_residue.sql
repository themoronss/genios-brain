-- L2 · `context_residue` — what this layer looked at and could not explain.
--
-- THE MEASUREMENT THAT DID NOT EXIST. Every pass in `process_pending` reports what it PRODUCED:
-- derived rows, situations refreshed, metric points, cohort changes, budgets exhausted. Nothing
-- reported what it left behind. So the question a founder actually asks — "what is happening in my
-- mailbox that this thing never mentioned?" — had no answer anywhere in the engine, and the only
-- way to find out was to read the graph by hand and compare it against the cards, which is how
-- every defect on this branch was found.
--
-- A sweep that explains nothing and a sweep with nothing to explain look identical in the report.
-- This table is the difference.
--
-- CURRENT STATE, NOT A LOG. A row means "still unexplained as of the last sweep". When a reading
-- finally covers the subject, the row is DELETED rather than marked resolved — the interesting
-- number is what is unexplained now, and `first_seen_at` already answers "for how long". That also
-- means the table needs no retention: it cannot grow past the size of the graph, and it shrinks as
-- coverage improves. `analytic/history` and `graph_change_outbox` both needed horizons because
-- they append; this one does not append.
--
-- FOUR KINDS, and each one is a JOIN THAT CAN BE CHECKED rather than a heuristic:
--
--   node_evidence_unread     a node carrying active observations that no live situation anchors
--                            on and no live situation `concerns`. Evidence the layer holds and
--                            never speaks about.
--   ball_in_court_unreported a node whose `thread.ball_in_court` fact says the turn is OURS, with
--                            no live situation. This is the shape the founder named directly:
--                            they replied, we went quiet, and nothing said so.
--   open_loop_unreported     an open loop whose subject carries no live situation. An ask that is
--                            recorded, still open, and attached to nothing anybody can be shown.
--   signal_unreached         a Layer 1 qualified signal whose event reached no live situation. L1
--                            publishes deadline, decision, contract_renewal and risk signals that
--                            no L2 reading consumes; this counts them, by type.
--
-- WHY `signal_unreached` CHECKS TWO PATHS. `situation_bso._L1_SELECT` joins a signal to a
-- situation through `context_correlation_members`, and ONLY `correlation.py` writes that table.
-- Every state reading, the period sweep, meeting touch and the document register mint a SYNTHETIC
-- correlation id with no membership rows at all — so a signal whose event produced a state-reading
-- situation has no membership row and would be counted as unreached by that join alone. The second
-- path goes through `graph_source_refs` to whatever subject the event wrote, and asks whether THAT
-- carries a live situation. A detector that slandered the readings which do work would be worse
-- than no detector.
--
-- LIVE MEANS `active` OR `partial`, the same two statuses both Layer 3 doors admit
-- (`reason/runner` and `reason/domain_shadow`). A dormant situation does not explain a subject,
-- because a dormant situation cannot reach a card.

create table if not exists context_residue (
    org_id        text not null,
    residue_kind  text not null,
    subject_ref   text not null,
    detail        jsonb not null default '{}'::jsonb,
    first_seen_at timestamptz not null default now(),
    last_seen_at  timestamptz not null default now(),
    primary key (org_id, residue_kind, subject_ref)
);

-- "What has this layer been unable to explain for longest" — the read that turns the table into a
-- work queue rather than a number.
create index if not exists context_residue_by_age
    on context_residue (org_id, residue_kind, first_seen_at);

-- ACCOUNT ERASURE. Every org-scoped table in this engine carries this, and
-- `test_every_org_scoped_table_has_a_proven_account_delete_cascade` is what makes that true
-- rather than aspirational — it caught this table the first time the suite ran against it. A
-- residue row names a node id and a signal type belonging to one tenant, so it is exactly the
-- kind of row a deletion request has to take with it.
--
-- `not valid`, matching every constraint in `0033_org_data_cascade.sql`: the check is enforced on
-- new rows immediately and the existing table is not scanned while the migration holds a lock.
alter table context_residue add constraint context_residue_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

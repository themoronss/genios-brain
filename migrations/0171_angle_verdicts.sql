-- L2 · `context_angle_verdicts` — what a model was asked, about what, and what it answered.
--
-- THE ONE-HOP LAW NEEDS A PLACE TO STAND. `reason/llm_interpretation.py` states the rule this
-- table exists to enforce: "the one-hop law (a snapshot that already carries `interpretation.*` is
-- never read again)". Without it a model reads its own output on the next sweep and re-judges a
-- subject on evidence it produced, which is how a wrong reading stops being one opinion and starts
-- being a trend. A verdict has to be REMEMBERED for that rule to mean anything.
--
-- CONTENT-ADDRESSED, WHICH IS ALSO THE BUDGET. `saw_hash` is the digest of the exact field values
-- the model was shown. A subject whose slice has not changed is not asked again — at any price,
-- on any sweep, for ever — so the steady-state cost of an angle is the rate at which its queue
-- CHANGES rather than the size of the queue. That is the difference between a bill that grows
-- with a tenant and one that grows with their activity, and it is the same trick
-- `graph_store.write_event_presence` uses for replay safety.
--
-- ONE ROW PER (ORG, ANGLE, SUBJECT), REPLACED IN PLACE. Not a log: the interesting question is
-- what the model thinks NOW, and the audit trail of what it thought before lives in
-- `l2_model_runs` with the prompt bytes beside it — `model_audit` already stores "the prompt hash
-- and the complete returned artifact", so a second history here would be a worse copy of one that
-- already exists. `model_run_id` is the join.
--
-- `refused` IS A COLUMN AND NOT A DERIVATION. An angle whose refusals dominate is asking the wrong
-- question or reading the wrong queue, and that is only answerable if the refusals are counted.
-- Deriving it would mean joining every read against the registry to learn which word meant "I
-- cannot tell" for the VERSION that answered, and an angle that later changes its enum would
-- silently rewrite its own history.
--
-- NO RETENTION, and the reason is the shape rather than a promise: the table cannot exceed
-- (angles × subjects) and shrinks when a queue empties, because a subject that leaves the gate is
-- deleted by the evaluator on the pass that finds it gone. `metric_history` and
-- `graph_change_outbox` needed horizons because they append. This does not append.

create table if not exists context_angle_verdicts (
    org_id         text not null,
    angle_id       text not null,
    angle_version  text not null,
    subject_ref    text not null,
    verdict        text not null,
    confidence_bp  integer not null,
    refused        boolean not null default false,
    -- The digest of what the model was shown. Unchanged slice, no second call.
    saw_hash       text not null,
    -- The `l2_model_runs` row carrying the prompt bytes and the parsed artifact.
    model_run_id   text,
    first_seen_at  timestamptz not null default now(),
    last_seen_at   timestamptz not null default now(),
    primary key (org_id, angle_id, subject_ref)
);

-- "What has this angle been saying, and how often does it refuse" — the read that decides whether
-- an angle is worth its budget.
create index if not exists context_angle_verdicts_by_angle
    on context_angle_verdicts (org_id, angle_id, verdict);

-- Every org-scoped table in this engine carries this, and
-- `test_every_org_scoped_table_has_a_proven_account_delete_cascade` is what makes that true rather
-- than aspirational. A verdict names a subject belonging to one tenant.
alter table context_angle_verdicts add constraint context_angle_verdicts_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

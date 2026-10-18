-- 0191 · reasoning_fingerprints — what each subject's last decision was made on (STEP-02, the change gate).
--
-- WHY. Every sweep re-decides every subject. On the golden runner, one more sweep that brings NOTHING
-- new costs F13 2 model calls, F29 12 — the decider and its R-1 pass, again, for every subject — and
-- changes no card (`speedrun008/YC-II W27/STEP-02` §8.1). In production that is 760–1,890 calls a
-- day (`l4_llm_decision` + `l4_llm_r1`, 2–4 Oct). The gate skips a subject whose decision inputs
-- are unchanged; to know they are unchanged it has to remember them. One row per subject: the
-- fingerprint of the inputs, the run that decided on them, what came of it, and how often since it
-- was skipped.
--
-- ⛔ NOT `reasoning_runs.supersedes_run_id`. That column exists and is never written, and it is part
-- of `input_hash` and of the replay integrity check (`reason/store.py`): filling it in would change
-- every run's identity. The gate's memory stands alone.
--
-- ⛔ NO FOREIGN KEY ON `run_id`. It points at the run for an audit read; a run can be retired by
-- retention while the subject's fingerprint is still the one to compare against. A shadow decision
-- is never persisted, so its row carries no run at all.

create table if not exists reasoning_fingerprints (
    org_id          text        not null references orgs (id) on delete cascade,

    --: Which subject, in which lane (the pack is in the key: the legacy pass runs once per pack, and
    --: two packs may share a rule id):
    --:   compiled   '<situation_id>|<capability_id>'
    --:   legacy     'legacy|<pack_id>|<rule_id>|<node_id>'
    --:   native     'native|<pack_id>|<capability_id>|<node_id>'
    subject_key     text        not null,
    lane            text        not null,

    --: `reason/fingerprint.material_fingerprint` — never `evaluation_time`.
    fingerprint     text        not null,

    --: What the last decision on this fingerprint came to, so a skip can replay its bookkeeping:
    --:   emitted        a signal was written
    --:   standing       a signal already open was kept
    --:   deferred       a live run that could not decide — the card it found stays
    --:   indeterminate  the evaluation failed — never auto-resolved
    --:   suppressed     a live run that decided nothing should surface
    --:   shadow         a run that may not deliver — it keeps nothing alive
    outcome         text        not null,

    run_id          text,
    decided_at      timestamptz not null,

    --: The skip receipt: the last sweep that looked, and how many sweeps skipped since the decision.
    last_checked_at timestamptz not null,
    skips           integer     not null default 0,

    primary key (org_id, subject_key),

    constraint reasoning_fingerprints_lane_check
        check (lane in ('compiled', 'legacy', 'native')),
    constraint reasoning_fingerprints_outcome_check
        check (outcome in ('emitted', 'standing', 'deferred', 'indeterminate', 'suppressed',
                           'shadow')),
    constraint reasoning_fingerprints_skips_check
        check (skips >= 0)
);

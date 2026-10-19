-- 0249 · l2_admissions — Layer 3's admission of what the Layer 2 judgment proposed (L2 rebuild B3 / GeniOS-008 L2-G2).
--
-- THE ORDER THIS MAKES TRUE (Design Atlas v2, L3 §): the Evidence Graph is written by L1 facts; the
-- Intelligence Graph — what GeniOS concluded — only by "L3 admission of L2's mutations". Today's joins and
-- readings still form a situation row per file BEFORE reasoning; from here those rows are SEEDS. A seed becomes
-- a situation GeniOS stands behind only when the L2 judgment of its file is admitted here.
--
-- WHAT IT HOLDS. The LATEST decision per (subject, situation): admit | hold | reject, the op it came from
-- (create | update | close | merge | link | unchanged | none), why, and the result it was decided on
-- (`reasoning_results` by subject + fingerprint). One row per pair, upserted — a decision replaces the last
-- one, so the table grows with situations, never with sweeps (the 500 MB free plan).
--
-- `situation_id = '-'` is a subject-level decision: a seed subject L2 reasoned about that no join has filed
-- yet, so there is no situation row to admit — HOLD, until there is.
--
-- ⛔ SHADOW. Nothing here changes `context_situations`; the card path built on it (L2 rebuild Phase C) reads
-- this table. Idempotent: safe to run twice.

create table if not exists l2_admissions (
    org_id              text        not null,
    subject_ref         text        not null,
    situation_id        text        not null,
    decision            text        not null,
    op                  text        not null,
    reason              text,
    result_fingerprint  text        not null,
    lane                text,
    decided_at          timestamptz not null,
    primary key (org_id, subject_ref, situation_id),
    constraint l2_admissions_decision_ck check (decision in ('admit', 'hold', 'reject')),
    constraint l2_admissions_op_ck
        check (op in ('create', 'update', 'close', 'merge', 'link', 'unchanged', 'none'))
);

-- The card path's read: a tenant's admitted situations.
create index if not exists l2_admissions_admitted_idx
    on l2_admissions (org_id, decided_at desc) where decision = 'admit';

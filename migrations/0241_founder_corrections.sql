-- 0241 · founder_corrections — your correction of a file, in your words (STEP-16, learning from you).
--
-- WHY. Until now the only thing you said that reached the expert's next judgment was your answer to a
-- question the file asked (`founder_questions`, 0201). A *wrong because* you pressed on a card landed as a
-- verdict without its reason in front of the expert, and there was no place at all to say, in your own
-- words, what is true of a file: *"she asked for updates only with real news — don't push me"*, *"saka.vc
-- is no fund"*. This table is that place (`speedrun008/YC-II W27/` STEP-16 §8.4 item 2, S16-D1, tree
-- `yc2_w27_s16` M46.C3.L-contract.V0.U01). The file's dossier prints each standing correction with its id,
-- its fingerprint names them, and a new one brings the file back to the expert, whose next review follows
-- it or says, citing it, why the file now outweighs it.
--
-- WHAT A CORRECTION IS. Your words (one line, required), on a file (its anchor node), with their SCOPE:
--   * `file`    — this file;
--   * `kind`    — every file of this kind of work (`contracts/company_brief.WORK_KINDS`), the kind
--                 recorded: it prints beside that kind's playbook prior, as yours;
--   * `company` — how your company works: your own preferences line of the brief, written through the
--                 brief's one writer and accepted as written, its line id kept here.
-- Optionally the card it was about, the verdict it rode on and that verdict's reason (one of the eleven,
-- as `0210` admits them on the verdict ledger). Who wrote it and when; standing, or withdrawn (by whom,
-- when). NEVER DELETED: a withdrawn correction stays, so a review that cited it can still be read.
--
-- ⛔ NOT `user_model_proposals` (unwritten persona JSON, `0023`), and not a learned brain: a correction is
-- read by the expert already running, never proposed into L6's evidence route (S16-D1, S16-D8) — nothing
-- here learns a pattern from a click.
--
-- ⛔ NO FOREIGN KEY ON `file_id` (nor on the card or the verdict), as `founder_questions` (0201) and
-- `expert_reviews` (0197): a file is its anchor node, the graph versions and retires nodes, and cards
-- expire — a correction of a file since merged is still what you said.
--
-- ⛔ `/reset` ERASES IT (`api/account_routes._ORG_SCOPED_TABLES`): your words ABOUT the tenant's own
-- counterparties. A `company` correction's line of the brief is the brief's, which the reset keeps (0195).
--
-- ADDITIVE: one new table; the previous image never names it.

create table if not exists founder_corrections (
    org_id         text        not null references orgs (id) on delete cascade,
    correction_id  text        not null,
    file_id        text        not null,          -- the file's anchor node
    card_id        text,                          -- the card it was about, when it came by one
    feedback_id    text,                          -- the verdict it rode on (`card_feedback_verdicts`)
    reason         text,                          -- that verdict's reason, one of the eleven
    words          text        not null,          -- yours, verbatim
    scope          text        not null,
    kind           text,                          -- the kind of work, for a `kind` correction
    brief_line_id  text,                          -- your preferences line, for a `company` correction
    corrected_by   text        not null,
    corrected_at   timestamptz not null,
    state          text        not null default 'standing',
    withdrawn_by   text,
    withdrawn_at   timestamptz,

    primary key (org_id, correction_id),

    constraint founder_corrections_scope_check
        check (scope in ('file', 'kind', 'company')),
    constraint founder_corrections_state_check
        check (state in ('standing', 'withdrawn')),
    -- Your words: one line, said.
    constraint founder_corrections_words_check
        check (length(btrim(words)) between 1 and 500 and position(E'\n' in words) = 0),
    -- The reason a verdict carries, as `0210` admits it.
    constraint founder_corrections_reason_check
        check (reason is null or reason in (
               'not_relevant', 'wrong_facts', 'bad_timing',
               'misread_source', 'stale_data', 'wrong_subject', 'bad_link',
               'bad_reasoning', 'wrong_playbook', 'wrong_person', 'badly_written')),
    -- A kind correction records its kind, and only it does.
    constraint founder_corrections_kind_check
        check ((scope = 'kind') = (coalesce(btrim(kind), '') <> '')),
    -- A company correction keeps its line of the brief, and only it does.
    constraint founder_corrections_company_check
        check ((scope = 'company') = (brief_line_id is not null)),
    -- A withdrawal says who and when — on a withdrawn correction, and only there.
    constraint founder_corrections_withdrawn_check
        check ((state = 'withdrawn') = (withdrawn_by is not null and withdrawn_at is not null)
               and (state = 'withdrawn' or (withdrawn_by is null and withdrawn_at is null)))
);

-- "What did you correct about this file" — its dossier, its fingerprint, its route.
create index if not exists founder_corrections_by_file
    on founder_corrections (org_id, file_id, corrected_at desc);

-- "What did you say about this kind of work" — every file of the kind reads it.
create index if not exists founder_corrections_by_kind
    on founder_corrections (org_id, kind, corrected_at desc) where scope = 'kind';

comment on table founder_corrections is
  'STEP-16: your correction of a file in your own words - its scope (this file, every file of its kind of work, or the company: your preferences line of the brief), the card, verdict and reason it rode on, who and when; standing or withdrawn, never deleted. Read by the expert''s dossier; never a learning object.';

-- 0201 · founder_questions — the one question a file asks you (STEP-13, check every claim; §3.6, `06` D60).
--
-- WHY. Since STEP-13 a review's move that lost its ground is not shown: the file is HELD, and asks the
-- founder ONE question (`contracts/claim_check.CheckedReview.question`); a review that must find out first
-- asks its own (`speedrun008/YC-II W27/` STEP-13 §8.4 item 7, tree `yc2_w27_s13` M36.C2.L-contract.V0.U01).
-- Until now a question had no road to the founder (`03` F184): a find-out decision has no candidate, the
-- delivery authority needs a selected move, and any lane but DECISION emits no signal. The question is kept
-- here — what it asks, why it matters, the review that asks it (its fingerprint) and the audited run that
-- ended insufficient on it (its authority) — and then the founder's answer (the words, by whom, when), or
-- why it was retired. The answer is the file's: its dossier shows it, its fingerprint moves, and the next
-- sweep reviews the file with the answer in front of the expert.
--
-- NOT `evidence_needs`. A question to the founder is answered by the founder; the needs executor closes for
-- good a need no source can fetch, and would close a question nobody had been asked.
--
-- ONE OPEN QUESTION PER FILE (`06` D60: the file's one card). A file's new question retires its old one,
-- which keeps why; an answer is given once.
--
-- ⛔ NO FOREIGN KEY ON `file_id`, as `expert_reviews` (0197): a file is its anchor node, and the graph
-- versions and retires nodes — a question asked of a file since merged is still what was asked.

create table if not exists founder_questions (
    org_id        text        not null references orgs (id) on delete cascade,
    question_id   text        not null,
    file_id       text        not null,
    fingerprint   text        not null,          -- the review that asks it (`expert_reviews`)
    run_id        text,                          -- the audited run that ended insufficient on it
    question      text        not null,
    why           text        not null,          -- why it matters: what the check could not stand on
    asked_at      timestamptz not null,
    state         text        not null default 'open',
    answer        text,
    answered_by   text,
    answered_at   timestamptz,
    retired_at    timestamptz,
    retired_why   text,

    primary key (org_id, question_id),

    constraint founder_questions_state_check
        check (state in ('open', 'answered', 'retired')),
    constraint founder_questions_words_check
        check (btrim(question) <> '' and btrim(why) <> ''),
    -- An answer is the founder's words, who gave them and when — on an answered question, and only there.
    constraint founder_questions_answer_check
        check ((state = 'answered') = (coalesce(btrim(answer), '') <> '' and answered_by is not null
                                       and answered_at is not null)
               and (state = 'answered' or (answer is null and answered_by is null and answered_at is null))),
    -- A retirement says when and why — on a retired question, and only there.
    constraint founder_questions_retired_check
        check ((state = 'retired') = (retired_at is not null and coalesce(btrim(retired_why), '') <> '')
               and (state = 'retired' or (retired_at is null and retired_why is null)))
);

-- The file's one open question.
create unique index if not exists founder_questions_one_open
    on founder_questions (org_id, file_id) where state = 'open';

-- "What has this file been asked, and what did you answer" — its dossier and its history.
create index if not exists founder_questions_by_file
    on founder_questions (org_id, file_id, asked_at desc);

comment on table founder_questions is
  'STEP-13: the one question a file asks the founder — the review that asks it, the run that ended insufficient on it, the question and why; then the answer (words, by whom, when) or why it was retired. One open question per file.';

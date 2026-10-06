-- 0192 · attention — the gate stops deleting mail (STEP-03, the gate keeps everything).
--
-- WHY. Of ~395 mails on the design partner's account, 258 were deleted at the first gate with
-- their content gone: every noise rule (N-01 … N-10) and the AI filter's confident `llm_junk` were a
-- DROP, and a drop kept no body (`speedrun008/YC-II W27/` STEP-03 §1, §8). On the golden set, 33 of 86
-- mail objects — Boardy's introductions, the government portal's updates, a bounce report. The Atlas
-- says it as a rule (RULE 04): uncertainty routes, it never deletes.
--
-- From this migration the gate ARCHIVES what it would have dropped: the mail is kept — its
-- encrypted payload and its prepared text, for 180 days (06 D4) — and read by no model, and the rule
-- that archived it is its reason. Every kept mail carries an attention tier:
--
--   deep      read — emitted, or parked waiting to be read
--   skim      declared for STEP-07, which assigns it from the company brief; nothing writes it yet
--   archive   kept, unread — what the noise rules and the AI filter would have deleted
--   (null)    a dropped object that is not mail, and a row written before this migration
--
-- `outcome` gains the value `archived` (the column carries no check; the vocabulary lives in
-- `capture/attention.py` and the sync summary, where an outcome with no field raises).

alter table source_events add column if not exists attention text;
alter table source_events add column if not exists attention_reason text;

alter table source_events drop constraint if exists source_events_attention_check;
alter table source_events add constraint source_events_attention_check
    check (attention is null or attention in ('deep', 'skim', 'archive'));

-- A sync run says what it archived, beside what it emitted, dropped and parked. NOT NULL with a
-- zero: a run written before this column existed archived nothing, because nothing archived.
alter table l1_sync_runs add column if not exists archived integer not null default 0;

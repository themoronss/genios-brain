-- 0196 · company_brief_lines.kind — the kind of work an in-motion line of the brief names (STEP-11, D31).
--
-- WHY. A founder's file (`context/workstreams`) knew only its ROLE — `connector`, `watched`, `person`,
-- `intro` — and nothing could say what kind of WORK it is: raising from a fund, an application to a
-- program, a filing, a hire, an introduction, a partnership. So no file could pick the playbook the next
-- step's expert reads for it (`speedrun008/YC-II W27/` STEP-11 §8.3 N1). `06` D31: an in-motion line of
-- the brief names its kind of work and its counterparty; the drafter proposes them, and the founder
-- accepts them with the line. A file takes the kind of the line that names its counterparty.
--
-- ONE NULLABLE COLUMN, AND THE NULL IS AN ANSWER. A line written before this migration named no kind,
-- and most lines never will — only an in-motion line may name one. No default: a default would claim a
-- kind nobody chose.
--
-- NO CHECK CONSTRAINT. The closed list (`investor`, `program`, `compliance`, `hiring`, `intro`,
-- `partner`) and the rule that only an in-motion line carries a kind live in
-- `contracts/company_brief.WORK_KINDS` and the line's own validation, as `l3_activation.domain` is
-- validated in code (0107): a seventh kind is an authoring event, not a schema event.
--
-- THE COUNTERPARTY NEEDS NO COLUMN. It is the line's `address` (a person) or `domain` (a fund, a
-- program, a portal, a company), which 0195 already holds and checks for every section.
--
-- ADDITIVE, SO THE PREVIOUS IMAGE STILL RUNS: it never names the column, and its inserts leave it null.

alter table company_brief_lines add column if not exists kind text;

comment on column company_brief_lines.kind is
  'STEP-11 (06 D31): the kind of work an in-motion line names, so a file it names can pick its playbook - investor, program, compliance, hiring, intro or partner. Validated in contracts/company_brief.WORK_KINDS, not by a check constraint. NULL means the line names no kind of work, and only an in-motion line may name one.';

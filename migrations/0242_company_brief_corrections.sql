-- 0242 · company_brief_lines.proposed_kind, .replaces — the brief keeps what you corrected (STEP-16).
--
-- WHY. Two corrections of the brief were lost or impossible (`speedrun008/YC-II W27/03` F126, F157; tree
-- `yc2_w27_s16` M46.C5.L-contract.V0.U01):
--
--   * F126 — when you accept a proposal naming ANOTHER kind of work than the drafter proposed, the drafter's
--     kind was overwritten: 0196 holds one `kind`, and nothing kept the proposal's beside its words
--     (`proposed_text` keeps only the words). `proposed_kind` is that kind — written only when you accepted
--     another (or cleared it), so a NULL still says "accepted as the proposal named it".
--   * F157 — the expert could propose a kind only for a file the brief names no kind for: a counterparty
--     with an accepted line is "already said", so a programme the brief files as `program` that behaves
--     like the fund behind it (F132) could never be proposed as `investor`. `replaces` is the accepted line
--     a proposal would replace: accepting it removes that line in the same act, so the brief in force at
--     any instant still says what it said then.
--
-- TWO NULLABLE COLUMNS, NO DEFAULT, NO CHECK: a line written before this migration replaced nothing and
-- kept no other kind, and the kinds are `contracts/company_brief.WORK_KINDS`, validated in code (0196's
-- rule). Nothing here arms anything: a replacing proposal is a proposal — nothing changes until you accept.
--
-- ADDITIVE, SO THE PREVIOUS IMAGE STILL RUNS: it never names either column, and its inserts leave both null.

alter table company_brief_lines add column if not exists proposed_kind text;
alter table company_brief_lines add column if not exists replaces text;

comment on column company_brief_lines.proposed_kind is
  'STEP-16 (03 F126): the kind of work the proposal named, when the founder accepted the line as another kind (or none). NULL: accepted as the proposal named it.';
comment on column company_brief_lines.replaces is
  'STEP-16 (03 F157): the accepted line this proposal would replace - accepting it removes that line in the same act. NULL: replaces nothing.';

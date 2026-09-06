-- W10 / G10 · the pilot activation table gains the third column the plan actually printed, and
-- the columns that make a switch-off legible.
--
-- WHY NOT A NEW TABLE. `09-Build-Order-and-Acceptance.md` ("The activation rule") prints a DDL
-- named `l1_v2_activation` with four columns: org_id, enabled_at, enabled_by, notes. Migration
-- 0085 already shipped `l1_semantic_activation` with the first three, it is read on the request
-- path (`api/routes.py::_semantic_activated_orgs` -> `platform/wiring.make_semantic_lane`), and
-- a second table would be exactly the duplicate the rule exists to prevent: two switches for one
-- lane, one of which some code reads and the other of which some human edits. So this migration
-- EXTENDS the shipped table to the printed shape. The name difference is deliberate and kept:
-- "semantic" says which lane, and no code in the tree spells the plan's name.
--
-- `notes` — the plan prints it and it is the only column that answers "why was this tenant
-- chosen". A pilot is a decision about ONE customer's bill and ONE customer's extraction
-- quality; "who" and "when" without "why" leaves the next operator guessing whether an org is a
-- deliberate design partner or a leftover from a debugging session.
--
-- `disabled_at` / `disabled_by` — the rollback half. `deactivate_semantic` DELETES the row, which
-- is correct for the lookup (an absent row is off, and the lookup must stay a single indexed
-- read) but erases the fact that the tenant was ever on. G10 is a SEVEN-DAY comparison, and a
-- window that silently contains a mid-week switch-off is a diff nobody can read. These two
-- columns let a deactivation be recorded on a row that stays absent from the activated set:
-- `disabled_at is not null` means "was on, is off", and the activated read filters on it.
alter table l1_semantic_activation add column if not exists notes       text;
alter table l1_semantic_activation add column if not exists disabled_at timestamptz;
alter table l1_semantic_activation add column if not exists disabled_by text;

-- The activated set is now "a row with no disabled_at", so it is worth an index: this is read
-- ONCE PER SWEEP for every tenant (api/routes.py::_semantic_activated_orgs) and it is on the
-- hot path of every capture run.
create index if not exists l1_semantic_activation_live
    on l1_semantic_activation (org_id) where disabled_at is null;

comment on table l1_semantic_activation is
  'G10 pilot activation. Per-tenant, never a config boolean (09-Build-Order-and-Acceptance.md, "The activation rule"). A row with disabled_at null means this tenant runs the L1 v2 semantic lane. Written only by api/admin_routes.py; read by api/routes.py::_semantic_activated_orgs.';
comment on column l1_semantic_activation.notes is
  'Why this tenant was chosen for the pilot. The plan''s printed fourth column.';
comment on column l1_semantic_activation.disabled_at is
  'When the tenant was switched back off. Null means live. The row is kept rather than deleted so a G10 window that contains a mid-window switch-off can say so.';

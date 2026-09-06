-- L1.6.7 term 4 rung 1 · `mission_critical`, given the writer it never had.
--
-- THE DEFECT THIS CLOSES. `capture/esqe/importance.py` defines a six-rung entity ladder worth
-- 2000 of ALG-17's 10000 basis points, and its TOP rung — MISSION_CRITICAL, 10000 bp — was
-- unreachable in production. `baseline_reader.load_org_baseline` says so in its own docstring:
-- *"`mission_critical` is a parameter with an empty default and that is a REPORTED GAP... this
-- build has no such tag anywhere — no column, no writer, no route."* The consequence is not a
-- crash, which is why it survived: every tenant's most important vendor was ranked at
-- TOP_DECILE (8000) at best, so the difference between "our payroll provider" and "our biggest
-- customer by contract value" — two entirely different kinds of important — did not exist.
--
-- It is measurable, and doc 06 measures it: the plan's own headline acceptance row is
-- *"$84K renewal, 12 days out, CFO sender, MISSION-CRITICAL VENDOR, signed PDF, org p50 $45K
-- -> importance_bp in [7500, 8500]"*. On the production path, with rung 1 unreachable, that row
-- scores **7425** — below its band, by exactly the 400 bp the missing rung is worth.
--
-- WHY A TABLE AND NOT A TAG ON `graph_nodes`. The same argument migration 0088 makes about the
-- qualification floor, and this is the sibling of that table in every respect. It is a per-tenant
-- JUDGEMENT, not an observation: nothing in a mailbox says "this vendor is mission-critical", a
-- human does, and a judgement with no owner and no date is the global constant again wearing a
-- row. `owner` is who answers for it and `note` is why — "single-source payroll", "the only
-- provider with our production keys" — because the next operator to see a vendor outranking a
-- larger customer needs the reason, not the fact.
--
-- `entity_key` IS THE CASEFOLDED FORM AND IT IS THE PRIMARY KEY, because that is the shape
-- `OrgBaseline.__post_init__` folds every entity set into before `standing_of` compares against
-- it. Storing only the display form would mean "Acme Corp" tagged here and "ACME CORP" read out
-- of a message resolve to different rungs, which returns a plausible number and is invisible.
-- `display_name` is kept beside it so a UI never has to show a founder their own vendor in
-- lower case.
create table if not exists org_mission_critical_entities (
    org_id       text not null references orgs (id) on delete cascade,
    entity_key   text not null,
    display_name text not null,
    -- WHO answers for this judgement. Never null, for migration 0088's reason.
    owner        text not null,
    note         text not null default '',
    added_at     timestamptz not null default now(),
    primary key (org_id, entity_key),
    constraint org_mission_critical_entities_key_folded check (entity_key = lower(entity_key)),
    constraint org_mission_critical_entities_key_present check (length(trim(entity_key)) > 0)
);

-- The whole read: "which entities has this tenant tagged", once per sweep. The primary key
-- already covers it; named here so the intent of the access pattern is on the record.
comment on table org_mission_critical_entities is
  'L1.6.7 term 4 rung 1: entities this tenant declared mission-critical. Read once per sweep by capture/esqe/baseline_reader.mission_critical_entities; written only through PUT /qualification/mission-critical (owner-only). Erased with the tenant (org cascade + api/account_routes._ORG_SCOPED_TABLES).';
comment on column org_mission_critical_entities.entity_key is
  'The CASEFOLDED name, which is the form OrgBaseline folds every entity set into. A stored display-cased key would resolve to a different rung than the same name read out of a message.';
comment on column org_mission_critical_entities.owner is
  'Who answers for this judgement. A mission-critical tag outranks the org''s largest contract, so an unattributed one is a ranking change nobody owns.';

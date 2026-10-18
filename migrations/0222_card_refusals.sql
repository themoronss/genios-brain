-- 0222 · card_refusals — what the card contract refused, kept where it can be read (STEP-14, the card; tree
-- `yc2_w27_s14` M43.C4.L-integration.V2.U05).
--
-- WHY. Since STEP-14 both card writers run the card contract (`contracts/card_contract`) before anything is written:
-- the pipeline's decision and question cards (`deliver/pipeline`) and the P4 team and verify cards
-- (`reason/team/emit`). A refused card is never written, so nothing in `cards` says it existed — and a refusal
-- nobody can see is a silent stop. Each refusal is kept here, one row per rule it broke: which writer, the signal or
-- the situation it was for, the rule, what it found, when. `scripts/pipeline_health` says them, per rule.
--
-- Additive and idempotent. The tenant reset deletes it (`api/account_routes._ORG_SCOPED_TABLES`) and the tenant's
-- deletion cascades.
create table if not exists card_refusals (
    org_id      text        not null references orgs (id) on delete cascade,
    refusal_id  text        primary key,
    writer      text        not null,
    ref         text        not null,      -- the signal (pipeline) or the situation's key (team)
    rule        text        not null,
    found       text        not null,
    refused_at  timestamptz not null default now()
);

alter table card_refusals drop constraint if exists card_refusals_writer_check;
alter table card_refusals add constraint card_refusals_writer_check check (writer in ('pipeline', 'team'));
alter table card_refusals drop constraint if exists card_refusals_rule_check;
alter table card_refusals add constraint card_refusals_rule_check
    check (rule in ('us', 'internal', 'money', 'quote', 'number'));

create index if not exists card_refusals_by_org on card_refusals (org_id, refused_at desc);

comment on table card_refusals is
  'STEP-14 (0222): each rule of the card contract (contracts/card_contract) a card broke before it could be written — by the pipeline or the team writer — said by scripts/pipeline_health.';

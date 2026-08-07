-- Tenant erasure must be complete by schema, not by a best-effort application list.
-- These legacy tables predate `orgs` and carried org_id without ownership FKs. Constraints are
-- NOT VALID so deployment is not blocked by unrelated historical orphan cleanup; PostgreSQL still
-- enforces new writes and installs the ON DELETE CASCADE trigger for existing tenant rows.

alter table source_events add constraint source_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table raw_payloads add constraint raw_payloads_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table sync_cursors add constraint sync_cursors_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table event_trace add constraint event_trace_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table connections add constraint connections_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table document_jobs add constraint document_jobs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table parked_events add constraint parked_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table agent_registry add constraint agent_registry_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table agent_events add constraint agent_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table human_events add constraint human_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table source_coverage add constraint source_coverage_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

alter table graph_nodes add constraint graph_nodes_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table source_identity_map add constraint source_identity_map_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table graph_facts add constraint graph_facts_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table graph_edges add constraint graph_edges_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table graph_source_refs add constraint graph_source_refs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table graph_observations add constraint graph_observations_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table merge_proposals add constraint merge_proposals_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table merge_history add constraint merge_history_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table discrepancies add constraint discrepancies_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table graph_versions add constraint graph_versions_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table graph_change_outbox add constraint graph_change_outbox_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table context_read_models add constraint context_read_models_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table l2_extraction_results add constraint l2_extraction_results_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table llm_costs add constraint llm_costs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

alter table signals add constraint signals_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table signal_suppression_log add constraint signal_suppression_log_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table baselines add constraint baselines_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table tenant_packs add constraint tenant_packs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

alter table cards add constraint cards_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table card_events add constraint card_events_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table agent_claims add constraint agent_claims_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table org_seats add constraint org_seats_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table agent_metering add constraint agent_metering_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

alter table l2_processing_runs add constraint l2_processing_runs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table rule_mutes add constraint rule_mutes_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table calibration_nudges add constraint calibration_nudges_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table macv_ledger add constraint macv_ledger_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

alter table workspace_accounts add constraint workspace_accounts_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table user_tasks add constraint user_tasks_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table decisions add constraint decisions_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table domain_requests add constraint domain_requests_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table agent_grants add constraint agent_grants_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table org_members add constraint org_members_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table org_invites add constraint org_invites_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table resource_uploads add constraint resource_uploads_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table policy_rules add constraint policy_rules_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table approvals_queue add constraint approvals_queue_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table user_models add constraint user_models_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table user_model_proposals add constraint user_model_proposals_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table audit_log add constraint audit_log_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

alter table prepared_content add constraint prepared_content_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table l1_sync_runs add constraint l1_sync_runs_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table context_attention add constraint context_attention_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table org_channels add constraint org_channels_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;
alter table delivery_outbox add constraint delivery_outbox_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

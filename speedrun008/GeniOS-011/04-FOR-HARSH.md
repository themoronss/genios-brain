# 04 · For Harsh — production facts, actions and the read-only SQL

**Written for:** Harsh (and Rohit, who must give the permission for production reads).

GeniOS-011 starts by measuring production, because nobody has since the big merge reached the prod branch. Three things only you can answer come first:

1. **What is deployed, and since when** (S01.U3).
   - The SHA the deploy host runs, and the date it went live.
   - Whether migrations 0191–0250 are applied: `select max(version) …` and the list since 0191.
   - Which env switches are set (`GENIOS_NEED_FETCHERS`, the `l4_llm_*` flags).
2. **Is Rohit's org still running at all** (S02.U1).
   - Since `7075014c` (4 Oct), the scheduled sweep skips the whole L1 → L5 chain for an org whose plan expired. The warm lane refuses its events too.
   - That commit measured Rohit's grace as closed on 21 Sep, and nothing in the repo extends it.
   - If his org is expired, only a manual **Sync now** reasons for it. That alone would explain "fewer cards, sometimes".
   - Fix: put his org (and the design partners) on a non-expiring internal plan.
3. **Which switches are on for his org** (S02.U3).
   - These tables decide which path makes his cards: `l4_activation` (`expert_review`, `l2_reasoning`, `l2_cards`, …), the L1/L2/L3 activation tables, and the Founder Office domain.
   - All of them default off.

After that, the readings in §2 give the baseline. Every item below names the step it unblocks.


## 1 · Production actions in the plan (yours, or yours with Rohit)

| Unit | What | Done when | Owner |
|---|---|---|---|
| [S01.U2](02-PLAN.md#s01) | Rohit's permission and one run of the readings | Rohit says yes (or runs it himself); the JSON, with e-mail addresses redacted, is committed at speedrun008/GeniOS-011/measurements/<date>-prod-readings.json. | rohit |
| [S01.U3](02-PLAN.md#s01) | Deploy and env facts SQL cannot answer | Harsh records in GeniOS-011 03-LOG: DO App Platform deployment history (SHA, time) 18–23 Oct for brain and dashboard; the auto-deploy setting; set/unset state of GENIOS_L4_LLM_DECISION_MAKER(_ORGS), GENIOS_USE_DOMAIN_COMPILER, GENIOS_L1_LLM_GATE, GENIOS_ENABLE_L1_RELEVANCE, GENIOS_NEED_FETCHERS, GENIOS_OPS_ALERT_WEBHOOK; Composio SDK and toolkit versions; whether rest_stuck_reviews.py --apply and resync_deleted_mail ran. | harsh |
| [S02.U1](02-PLAN.md#s02) | Rohit's org (and design partners) on a non-expiring internal plan | orgs row for <ORG> shows plan_status active, plan_expires_at null, grace_until null; the next heavy tick writes an l1_sync_runs row per connection and cards_7d moves; same for Sole Mate's tenant if Rohit wants it running. | harsh |
| [S02.U2](02-PLAN.md#s02) | Schema and deploy order | All 25 migrations 0191–0250 are in schema_migrations, 0210's constraints list eleven reasons, default_transaction_read_only is off; the dashboard is deployed at 2edfb86 or later before or with brain 0cc8d83c; results logged in GeniOS-011 03-LOG. | harsh |
| [S02.U3](02-PLAN.md#s02) | Switches and env for Rohit's org | Rohit confirms A5 (retire R-1) and D1/A4; Harsh leaves GENIOS_L4_LLM_DECISION_MAKER unset or false (or records why it stays on); founder_office domain and expert_review are active for Rohit's org via scripts/activate_tenant.py, l2_reasoning in shadow; every flip is a dated 03-LOG line with its one-line rollback. | rohit+harsh |
| [S02.U4](02-PLAN.md#s02) | Brief accepted and self identity declared | Rohit accepts the drafted brief lines naming Boardy, the sampark.gov.in portal, accelerators and investors; D35 yes → declare_self_identity for his domain; repair_self_identity dry run read by Rohit → --apply; counts logged. | rohit+harsh |
| [S03.U2](02-PLAN.md#s03) | Branch protection and green-only deploys | harsh/mvp and speedrun008 are protected (required checks test, database, golden-pg; branch up to date; no force push); DO auto-deploy is off or bound to a branch that only fast-forwards to green SHAs; DO binds the commit hash into GENIOS_BUILD_SHA; /health on production shows a SHA whose CI run is green. | rohit+harsh |
| [S03.U3](02-PLAN.md#s03) | One branch, one push owner, repository visibility | speedrun008 is fast-forwarded to origin/harsh/mvp; GeniOS-011 00-START-HERE states the rule (all code lands on speedrun008 through green CI; harsh/mvp only fast-forwards to a green speedrun008 SHA); the push owner is fixed (or a Bash permission rule allows fast-forward pushes to speedrun008); the default branch is moved off main; Rohit decides public vs private (and a CI-annotation token if private). | rohit+harsh |
| [S06.U4](02-PLAN.md#s06) | Promote Boardy's archived intros (D23) | After U2 ships, promote_archived --rule N-02 --sender-domain boardy.ai dry run → Rohit reads ids/dates → --apply; counts logged in 03-LOG. | rohit+harsh |
| [S08.U3](02-PLAN.md#s08) | Connect <founder company mailbox> as a seat; coverage names what is not connected | Rohit says yes (R3/C2); Harsh connects it as a seat connection and l1_sync_runs shows its runs; coverage names brief-listed addresses that are not connected. | rohit+harsh |
| [S09.U4](02-PLAN.md#s09) | Resync, requeue and re-file in production | Harsh PATCHes Gmail and Calendar windows; resync_deleted_mail --days N dry run → Rohit reads → --apply; requeue_refused_attachments dry → --apply; the F101 noise count; after S14 lands, rebuild_graph then situations/backfill?rebuild=true; the business-facts runner dry → apply; every count logged. | harsh |
| [S10.U4](02-PLAN.md#s10) | Ops alert webhook | Harsh sets GENIOS_OPS_ALERT_WEBHOOK in production and one test alert arrives. | harsh |
| [S11.U1](02-PLAN.md#s11) | Production toolkit versions and live history fixtures | Harsh reports the toolkit versions the production SDK resolves for gmail, googlecalendar and googledrive, and saves one redacted GMAIL_LIST_HISTORY response and one expired-historyId 404 as fixtures. | harsh |
| [S13.U4](02-PLAN.md#s13) | Arm the fetchers and wire HOLD → EvidenceNeed → resolve | Harsh runs 04-FOR-HARSH §8 steps 1–3 by hand on Rohit's org, then sets GENIOS_NEED_FETCHERS=on and confirms migration 0210; Claude wires needs_from_holds → store_needs in the L2 pass transaction and resolve_hold on the need's outcome, adds REEXTRACT from the stored payload, and shows open needs as 'waiting on' on the card; context_health stops declaring them UNREACHED. | claude+harsh |
| [S17.U4](02-PLAN.md#s17) | One authority scale (R16/R17, H9) | Rohit decides R16/R17; Harsh runs the H9 read; Claude builds the chosen remap of rank-100 rows. | rohit+harsh |
| [S25.U3](02-PLAN.md#s25) | First type switched on Rohit's org, one week side by side | Rohit confirms A3 (first type awaiting reply/outreach, or whole tenant); the real-model board (S07) shows the new path at least as good; Harsh flips l2_reasoning → l2_cards for that type; one week of l2_shadow_report plus the daily health rows shows no card lost; rollback line recorded. | rohit+harsh |
| [S32.U4](02-PLAN.md#s32) | human_decides on for Rohit's org | Rohit confirms B2 (Rohit the only approver) and switches human_decides on; Harsh flips it and logs the rollback. | rohit+harsh |
| [S34.U4](02-PLAN.md#s34) | Confirm what live cards anchor on | Rohit's read-only query (in S01's pack) shows subject_node_id distribution of open cards and the garbled-headline rows with their builder_version; the writer of 'Send calendar invites … to body' is named. | rohit |
| [S37.U3](02-PLAN.md#s37) | Email live for Rohit's org | Harsh sets the provider key, adds the org_channels email row, and confirms one digest and one high-band card arrive. | harsh |
| [S38.U3](02-PLAN.md#s38) | Signed release and one download | Harsh tags desktop-v0.3.x, the release workflow builds the installers (Developer ID signing), and the Download link points at the release; DMGs only via scripts/mac-dev-dmg.sh. | harsh |
| [S41.U2](02-PLAN.md#s41) | Layer 3 folder | Rohit opens L3; then 00–04 written from the L3 audit, recording L3-1…L3-7 status and Harsh's nine commits; Harsh commits docs/plans/L1_REBUILD_PLAN.md. | rohit+harsh |

## 2 · Every production question, with its read-only SQL

Run each inside `begin transaction read only; … rollback;`. Replace `<ORG>` with Rohit's org id. Send the output back (paste into `speedrun008/GeniOS-011/readings/` or to Rohit) — S01 turns it into the measured baseline every later step is judged against.

### A lapsed trial, a full ingestion meter or the daily model cap silently stop Rohit's org; only a manual 'Sync now' still reasons

[`cross-billing-gates-silently-stop-the-org`](05-EXPECTED-VS-ACTUAL.md#cross-billing-gates-silently-stop-the-org) · P0 · step S02

Production read (Rohit's permission). Read-only SQL:
-- A. plan state (expired = sweep, warm lane and Ask all stop)
select id, name, company, email, subscription_tier, plan_status, plan_started_at, plan_expires_at, grace_until, credit_period_start, created_at from orgs where id = '<ORG>' or name ilike '%swerashi%';
select org_id, timestamp, metadata_jsonb from audit_log where action = 'plan_expired' and org_id in (select id from orgs where id = '<ORG>' or name ilike '%swerashi%') order by timestamp;
-- B. paused?
select key, enabled from feature_flags where key in ('kill_switch:<ORG>', 'kill_switch_all');
-- C. ingestion meter this period
select count(*) from source_events where org_id = '<ORG>' and captured_at >= (select coalesce(credit_period_start, plan_started_at, created_at) from orgs where id = '<ORG>');
-- D. automatic sweeps vs manual Sync jobs vs cards, per day
select date_trunc('day', finished_at) d, count(*) l1_runs, sum(emitted) emitted, count(*) filter (where error is not null) errors from l1_sync_runs where org_id = '<ORG>' and finished_at >= '2026-10-01' group by 1 order by 1;
select date_trunc('day', created_at) d, count(*) sync_jobs from sync_jobs where org_id = '<ORG>' and created_at >= '2026-10-01' group by 1 order by 1;
select date_trunc('day', created_at) d, count(*) cards from cards where org_id = '<ORG>' and created_at >= '2026-10-01' group by 1 order by 1;
-- E. model calls per day (cap: 20,000 calls or $25)
select date_trunc('day', created_at) d, count(*) calls, count(*) filter (where not success) failed from llm_costs where org_id = '<ORG>' and created_at >= '2026-10-15' group by 1 order by 1;

### G0 ground: CI is green, but l2_cards, admission-decides-existence and D1–D8 are all still open

[`goals-g0-ground-partial`](05-EXPECTED-VS-ACTUAL.md#goals-g0-ground-partial) · P0 · step S24

Production state of the switches (read-only): select * from l4_activation where org_id = :org;  select * from l3_activation where org_id = :org;

### GeniOS-008 A4 + L2 04-FOR-HARSH §3: Founder Office, expert_review and l2_reasoning activation for Rohit's org is unverified; all default off

[`l2-founder-office-and-expert-switches-prod-state`](05-EXPECTED-VS-ACTUAL.md#l2-founder-office-and-expert-switches-prod-state) · P0 · step S02

select domain, enabled_at, disabled_at from l3_activation where org_id='<ORG>'; select feature, enabled_at, disabled_at from l4_activation where org_id='<ORG>';

### A valid expert/L2 judgment makes no card unless L3 already filed a situation on the file in an activated domain; 'general' is dark

[`l2-l3-binding-no-situation-no-card`](05-EXPECTED-VS-ACTUAL.md#l2-l3-binding-no-situation-no-card) · P0 · step S18

How many judged files are lost this way in production. Rohit to run: select s.domain, count(distinct r.file_id) from expert_reviews r join context_situations s on s.org_id=r.org_id and s.anchor_node_id=r.file_id where r.org_id='<ORG>' and r.status='valid' and s.status in ('active','partial') group by 1; select count(distinct r.file_id) from expert_reviews r where r.org_id='<ORG>' and r.status='valid' and not exists (select 1 from context_situations s where s.org_id=r.org_id and s.anchor_node_id=r.file_id);

### 823 commits reached production in one merge on 18 Oct, with no production number per step

[`process-823-commit-big-bang-deploy`](01-WHAT-WENT-WRONG.md#process-823-commit-big-bang-deploy) · P0 · step S01

Read-only, Rohit's org: set transaction read only; select date_trunc('day',created_at)::date d, output_lane, template_version, state, count(*) from cards where org_id='<ORG>' and created_at >= '2026-10-10' group by 1,2,3,4 order by 1;

### The deploy host builds production on its own; no CI job deploys, and no deploy waits for CI or runs the health gate

[`process-deploy-not-gated-on-ci`](05-EXPECTED-VS-ACTUAL.md#process-deploy-not-gated-on-ci) · P0 · step S03

Harsh: report the DO app's auto-deploy setting for harsh/mvp and the deployment history (SHA, time) for 18–22 Oct.

### No one measured production after the 18 Oct deploy: switch state, card counts and expert outcomes are unknown

[`process-no-production-number-after-deploy`](01-WHAT-WENT-WRONG.md#process-no-production-number-after-deploy) · P0 · step S01

set transaction read only; select feature, enabled_at, enabled_by, disabled_at from l4_activation where org_id='<ORG>' order by feature; select date_trunc('day',created_at)::date d, site, outcome, count(*) from l4_r_site_calls where org_id='<ORG>' and site in ('R-7','R-9') and created_at >= '2026-10-10' group by 1,2,3 order by 1; select date_trunc('day',reviewed_at)::date d, model, status, checked->>'fate' fate, count(*) from expert_reviews where org_id='<ORG>' and reviewed_at >= '2026-10-18' group by 1,2,3,4 order by 1;

### Nothing stops a push or merge to the production branch while CI is red

[`process-prod-branch-unprotected-red-ci-ships`](05-EXPECTED-VS-ACTUAL.md#process-prod-branch-unprotected-red-ci-ships) · P0 · step S03

Repository admin rights on themoronss/genios-brain (Rohit or Harsh) to enable branch protection.

### No plan budgeted the 500 MB database tier, and production reached 999 MB before a purge was added

[`cross-db-tier-never-budgeted`](01-WHAT-WENT-WRONG.md#cross-db-tier-never-budgeted) · P1 · step S05

select pg_size_pretty(pg_database_size(current_database())); select relname, pg_size_pretty(pg_total_relation_size(relid)) from pg_catalog.pg_statio_user_tables order by pg_total_relation_size(relid) desc limit 15;

### L2 subjects come from L1 bundles matched to L3 files by event: an unfiled bundle becomes a contextless 'seed' whose HOLD dead-ends, the watermark passes it, and a bundle spanning two files is judged under the first only

[`cross-l2-subject-to-file-seam`](05-EXPECTED-VS-ACTUAL.md#cross-l2-subject-to-file-seam) · P1 · step S21

Production read: select (subject_ref like 'seed:%') as seed, status, lane, count(*) from reasoning_results where org_id='<rohit_org>' and reasoned_at > now() - interval '7 days' group by 1,2,3;

### Why 'Antler Singapore admission' cannot become a goal automatically today

[`goals-antler-cannot-appear-today`](05-EXPECTED-VS-ACTUAL.md#goals-antler-cannot-appear-today) · P1 · step S27

Production (read-only, Rohit's permission): select section,status,proposed_by,left(text,120),proposed_at,accepted_at from company_brief_lines where org_id=:org and section in ('goals','in_motion') order by proposed_at;  select week_key,outcome,proposed,finished_at from company_brief_reviews where org_id=:org order by week_key desc limit 10;  select field,left(value::text,160),occurred_at from graph_facts where org_id=:org and valid_to is null and value::text ilike '%antler%' order by occurred_at desc limit 20;  select file_id,status,reviewed_at from expert_reviews where org_id=:org and (file_id ilike '%antler%' or review::text ilike '%antler%') order by reviewed_at desc limit 10;  select subject_ref,status,lane,reasoned_at from reasoning_results where org_id=:org and (subject_ref ilike '%antler%' or result::text ilike '%antler%') order by reasoned_at desc limit 10;

### The golden tenant ships a hand-curated brief (5 accepted goals, 20 in-motion lines), so no test sees a tenant whose brief was never accepted

[`goals-golden-brief-is-pre-curated`](01-WHAT-WENT-WRONG.md#goals-golden-brief-is-pre-curated) · P1 · step S27

set transaction read only; select section, status, proposed_by, count(*) from company_brief_lines where org_id='<ORG>' group by 1,2,3 order by 1,2;

### Historical mail never got its business facts (thread.objective, party.role): backfill_business_facts has no caller, so the goal drafter sees objectives only from mail processed after the fix

[`goals-thread-objective-history-missing`](05-EXPECTED-VS-ACTUAL.md#goals-thread-objective-history-missing) · P1 · step S09

Production read: select date_trunc('month', f.created_at) m, count(*) from graph_facts f where f.org_id='<rohit_org>' and f.field='thread.objective' and f.valid_to is null group by 1 order by 1;

### GeniOS-008 C3 / YC-II D5, D16, D26: the history window is still 60 days in code; the 365-day resync needs a production action

[`l1-c3-d16-history-window-still-60-days`](05-EXPECTED-VS-ACTUAL.md#l1-c3-d16-history-window-still-60-days) · P1 · step S09

select connection_id, source_type, status, capture_scope->>'backfill_days' as backfill_days from connections where org_id='<ORG>';

### The gate's protections for founder workstreams depend on accepted company-brief lines; production state is unknown

[`l1-company-brief-gate-dependence`](05-EXPECTED-VS-ACTUAL.md#l1-company-brief-gate-dependence) · P1 · step S02

Production: select section, status, count(*) from company_brief_lines where org_id='<ORG>' group by 1,2;

### The old gate deleted mail content (258 S1 drops). The fix shipped, but the re-sync that brings that mail back is a manual step in an unknown state

[`l1-deleted-mail-needs-resync`](01-WHAT-WENT-WRONG.md#l1-deleted-mail-needs-resync) · P1 · step S09

set transaction read only; select outcome, count(*), min(occurred_at), max(occurred_at) from source_events where org_id='<ORG>' and source='gmail' group by 1;

### EvidenceNeed fetchers (E2) are built but not armed, so every request L2 makes for more evidence stays open

[`l1-e2-need-fetchers-armed-off`](05-EXPECTED-VS-ACTUAL.md#l1-e2-need-fetchers-armed-off) · P1 · step S13

Production (Rohit's permission): select state, count(*) from evidence_needs where org_id='<ORG>' group by state; plus whether GENIOS_NEED_FETCHERS is set in the App Platform env

### L1 E2 / YC-II F224 + L2 G-1: evidence-need fetchers are built but unarmed, so L2's questions are never answered and holds never resolve

[`l1-e2-need-fetchers-armed-off-2`](05-EXPECTED-VS-ACTUAL.md#l1-e2-need-fetchers-armed-off-2) · P1 · step —

select need_id, state, created_at from evidence_needs where org_id='<ORG>' and need_id like 'l2need:%' order by created_at desc limit 20;

### L1 H3: Composio toolkit versions are still unpinned (dangerously_skip_version_check=True)

[`l1-h3-composio-toolkits-unpinned`](05-EXPECTED-VS-ACTUAL.md#l1-h3-composio-toolkits-unpinned) · P1 · step S11

Harsh: the Composio SDK and toolkit versions in the production image (not SQL)

### Whether the attachments refused since 3 Oct were requeued after the deploy is unknown (H4)

[`l1-h4-refused-attachments-requeue`](05-EXPECTED-VS-ACTUAL.md#l1-h4-refused-attachments-requeue) · P1 · step S09

Production (Rohit's permission): select reason_code, status, refetch_failure_kind, count(*) from parked_events where org_id='<ORG>' and reason_code like 'DOC-%' group by 1,2,3;

### A mail the junk filter archived as llm_junk is re-admitted on every heartbeat and extracted from its list snippet, skipping the gate

[`l1-junk-verdict-readmitted-on-snippet`](05-EXPECTED-VS-ACTUAL.md#l1-junk-verdict-readmitted-on-snippet) · P1 · step S06

Production size (needs Rohit's permission): select attention_reason, count(*) from source_events where org_id='<ORG>' and attention_reason like 'readmitted:%' and captured_at >= '2026-10-18' group by 1;

### The 4 Oct funnel loss is fixed in code, but production's funnel has not been measured since the 18 Oct deploy

[`l1-post-deploy-funnel-unmeasured`](05-EXPECTED-VS-ACTUAL.md#l1-post-deploy-funnel-unmeasured) · P1 · step S01

Production (Rohit's permission): select source, outcome, attention, count(*) from source_events where org_id='<ORG>' and captured_at >= '2026-10-18' group by 1,2,3 order by 4 desc; select et.stage, et.action, et.reason_code, count(*) from event_trace et where et.org_id='<ORG>' and et.at >= '2026-10-18' and et.stage in ('S1','S2') group by 1,2,3 order by 4 desc; select signal_type, state, count(*) from qualified_signals where org_id='<ORG>' group by 1,2; select disabled_at from l1_semantic_activation where org_id='<ORG>';

### A failed or partial sync is recorded but the founder never sees it; the ops alert is only a log line unless a webhook is set

[`l1-refusal-and-coverage-invisible`](05-EXPECTED-VS-ACTUAL.md#l1-refusal-and-coverage-invisible) · P1 · step S10

Production: select finished_at, source, mode, scanned, emitted, archived, parked, duplicate, cursor_exhausted, page_budget_spent, claimed_total, left(error,200) from l1_sync_runs where org_id='<ORG>' and finished_at >= '2026-10-18' order by finished_at desc limit 60;

### Mail the old gate deleted, and anything older than 60 days, stay outside memory until Rohit picks the window and Harsh runs the resync

[`l1-resync-and-history-window`](05-EXPECTED-VS-ACTUAL.md#l1-resync-and-history-window) · P1 · step S09

Rohit's window decision (R4/D16). Production: select connection_id, source_type, status, capture_scope->>'backfill_days' from connections where org_id='<ORG>'; select count(*) from source_events where org_id='<ORG>' and dedup_key like '%#resync:%';

### GeniOS-008 A2/A3 + GeniOS-009 D5/D6: the cutover is per tenant and covers every type at once, not one situation type at a time

[`l2-a2-a3-per-type-cutover-not-built`](05-EXPECTED-VS-ACTUAL.md#l2-a2-a3-per-type-cutover-not-built) · P1 · step S25

Production state of the switches: select feature, enabled_at, disabled_at from l4_activation where org_id='<ORG>';

### GeniOS-008 A5 / YC-II D11, F230, F274: the LLM decider (R-1) is not retired, and the golden set always runs with it on

[`l2-a5-llm-decider-not-retired-golden-forces-it-on`](05-EXPECTED-VS-ACTUAL.md#l2-a5-llm-decider-not-retired-golden-forces-it-on) · P1 · step S25

Harsh reads GENIOS_L4_LLM_DECISION_MAKER and GENIOS_L4_LLM_DECISION_MAKER_ORGS from the production service environment (not SQL)

### L2-G2 admission is built but shadow: it never creates or changes a situation; a HOLD raises no EvidenceNeed

[`l2-admission-g2-shadow`](05-EXPECTED-VS-ACTUAL.md#l2-admission-g2-shadow) · P1 · step S24

select decision, op, count(*) from l2_admissions where org_id='<ORG>' group by 1,2;

### Up to six producers can make a card today, each with its own switch; the L2 judgment is off by default

[`l2-card-paths-six-producers`](05-EXPECTED-VS-ACTUAL.md#l2-card-paths-six-producers) · P1 · step S25

Production state not read. Rohit to run (read-only): select org_id, feature, enabled_at, disabled_at from l4_activation where feature in ('expert_review','l2_reasoning','l2_cards','cards_from_situations','bundle') order by 1,2; select org_id, domain, enabled_at, disabled_at from l3_activation order by 1,2; select capability_key, builder_version, output_lane, count(*) from cards where org_id='<ORG>' and created_at >= '2026-10-18' group by 1,2,3 order by 4 desc; plus Harsh: the value of GENIOS_L4_LLM_DECISION_MAKER(_ORGS) in the prod environment.

### With l2_cards on but l2_reasoning off (or no R-9 client), nobody judges a moved file

[`l2-cards-precondition-not-enforced`](05-EXPECTED-VS-ACTUAL.md#l2-cards-precondition-not-enforced) · P1 · step S18

Whether production is in this state: select org_id, feature, disabled_at from l4_activation where feature in ('l2_cards','l2_reasoning','expert_review');

### The shared 7-per-day signal cap is spent by formula situations before the expert/L2 file decisions get a turn

[`l2-daily-cap-formula-first`](05-EXPECTED-VS-ACTUAL.md#l2-daily-cap-formula-first) · P1 · step S18

select created_at::date d, rule_id, count(*) from signals where org_id='<ORG>' and created_at>='2026-10-18' group by 1,2 order by 1,3 desc;

### When a judgment fails or is held, the file falls back to the formula/pack lanes; refused and truncated answers are never retried

[`l2-fallback-to-formula-lanes`](05-EXPECTED-VS-ACTUAL.md#l2-fallback-to-formula-lanes) · P1 · step S19

select status, left(reason,120) r, count(*) from expert_reviews where org_id='<ORG>' and reviewed_at>='2026-10-18' and status<>'valid' group by 1,2 order by 3 desc; select status, count(*) from reasoning_results where org_id='<ORG>' group by 1;

### The investor and programme playbooks were gated on a 267-line YAML review that was never done, and the Sales investor copy was retired

[`l2-founder-playbooks-gated-on-unread-review`](01-WHAT-WENT-WRONG.md#l2-founder-playbooks-gated-on-unread-review) · P1 · step S23

set transaction read only; select outcome, reason, count(*) from situation_outcomes where org_id='<ORG>' and last_seen_at >= '2026-10-18' group by 1,2 order by 3 desc;

### H1–H3 not done: 23 formula reasoners, the LLM decider and the per-pack rule lane still decide

[`l2-h1-h3-formula-lanes-still-decide`](05-EXPECTED-VS-ACTUAL.md#l2-h1-h3-formula-lanes-still-decide) · P1 · step S25

Harsh: the production value of GENIOS_L4_LLM_DECISION_MAKER and GENIOS_L4_LLM_DECISION_MAKER_ORGS (env, not SQL).

### Held cards read as engineer sentences: a fixed template replaces the model's advice, and nothing repairs before holding

[`l2-held-card-engineer-template`](05-EXPECTED-VS-ACTUAL.md#l2-held-card-engineer-template) · P1 · step S20

Share of held cards in production: select checked->>'fate' fate, checked->>'because' because, count(*) from expert_reviews where org_id='<ORG>' and reviewed_at>='2026-10-18' and status='valid' group by 1,2 order by 3 desc;

### I2 not made: l2_cards is a whole-tenant switch, compared only offline on the ideal reader

[`l2-i2-first-switch-not-made`](05-EXPECTED-VS-ACTUAL.md#l2-i2-first-switch-not-made) · P1 · step S25

select org_id, feature, enabled_at, disabled_at from l4_activation where feature in ('l2_reasoning','l2_cards','expert_review'); select status, lane, count(*), sum(cost_micro_usd)/1e6 usd from reasoning_results where org_id='<ORG>' group by 1,2;

### Since 21 Oct an overdue move, an 'unknown' confidence or an unnamed decider turns the move into a held question

[`l2-judgment-holds-overdue-and-unknown`](05-EXPECTED-VS-ACTUAL.md#l2-judgment-holds-overdue-and-unknown) · P1 · step S20

select checked->>'because', count(*) from expert_reviews where org_id='<ORG>' and prompt_version like 'l2-%' and checked->>'fate'='held' group by 1;

### The LLM decision maker ran in production for every org with no fallback, and a spend limit then stopped all cards from 25 Sep

[`l2-llm-decider-without-fallback-in-production`](01-WHAT-WENT-WRONG.md#l2-llm-decider-without-fallback-in-production) · P1 · step S02

The production env value of GENIOS_L4_LLM_DECISION_MAKER (Harsh); set transaction read only; select date_trunc('day',created_at)::date d, purpose, model, count(*), sum(output_tokens) from llm_costs where org_id='<ORG>' and created_at >= '2026-10-10' group by 1,2,3 order by 1;

### STEP-13b claim-check fixes (79% → 18.5% held on Haiku) never reached production; the production model has no completed live golden pass

[`l2-step13b-check-fixes-unmerged`](05-EXPECTED-VS-ACTUAL.md#l2-step13b-check-fixes-unmerged) · P1 · step S20

Rohit's yes for the live-pass spend (D72-style cap, about $7), and the production held share (SQL in l2-held-card-engineer-template).

### YC-II D14, D35 (+F96): whether Rohit's company domain is declared as 'us' and the self-identity repair was run is unknown

[`l3-d14-d35-self-identity-declaration-and-repair`](05-EXPECTED-VS-ACTUAL.md#l3-d14-d35-self-identity-declaration-and-repair) · P1 · step S02

select kind, value, declared_by from org_self_identities where org_id='<ORG>'; then `python scripts/repair_self_identity.py --org <ORG> --database-url <prod>` (dry run, no --apply)

### A situation's domain is a per-message keyword decision with an 'admin' fallback; fundraising situations route only to Founder Office, which is off by default

[`l3-domain-routing-fundraising`](05-EXPECTED-VS-ACTUAL.md#l3-domain-routing-fundraising) · P1 · step S15

Production read: select * from l3_activation where org_id='<rohit_org>'; select domain, situation_type, status, count(*) from context_situations where org_id='<rohit_org>' group by 1,2,3 order by 4 desc;

### Many events never reach a file, silently (noise, archived/metadata-only, held, parked, anchorless, private), and the funnel cannot show it

[`l3-events-outside-any-file`](05-EXPECTED-VS-ACTUAL.md#l3-events-outside-any-file) · P1 · step S14

Production read: select se.outcome, se.source, count(*) as events, count(*) filter (where exists (select 1 from context_correlation_members m join context_correlations c on c.org_id=m.org_id and c.correlation_id=m.correlation_id where m.org_id=se.org_id and m.event_id=se.event_id)) as in_a_file from source_events se where se.org_id='<rohit_org>' and se.occurred_at > now() - interval '60 days' group by 1,2 order by 3 desc; plus: select status, left(last_error,60), count(*) from l2_processing_runs where org_id='<rohit_org>' and status in ('held','parked','failed') group by 1,2;

### A HOLD raises no EvidenceNeed: needs_from_holds and resolve_hold have no production caller, though the plan says 'wired'

[`l3-hold-evidence-chain-unwired`](05-EXPECTED-VS-ACTUAL.md#l3-hold-evidence-chain-unwired) · P1 · step S13

L1 need executor fetchers (capture/acquire/need_executor.build_fetchers is empty; Harsh's, per context_health.py:43-44)

### l2_admissions is shadow only: written only when l2_reasoning is on, read by nothing, HOLDs have no applier, merge/link have no applier

[`l3-l2-admissions-shadow-status`](05-EXPECTED-VS-ACTUAL.md#l3-l2-admissions-shadow-status) · P1 · step S24

Production read: select * from l4_activation where org_id='<rohit_org>' and feature in ('expert_review','l2_reasoning','l2_cards','cards_from_situations'); select decision, op, count(*) from l2_admissions where org_id='<rohit_org>' group by 1,2 order by 3 desc;

### One counterparty file holds many live situations (one per keyword domain × 45-day generation, plus readings), so the L2 judgment is HELD instead of admitted

[`l3-one-subject-many-situations`](05-EXPECTED-VS-ACTUAL.md#l3-one-subject-many-situations) · P1 · step S15

Production read (Rohit's permission): select anchor_node_id, count(*) filter (where status in ('active','partial')) as live, array_agg(distinct domain) as domains, array_agg(distinct situation_type) as types from context_situations where org_id='<rohit_org>' group by anchor_node_id having count(*) filter (where status in ('active','partial')) > 1 order by live desc limit 30;

### Thread inheritance reads reading-declared memberships: a reply can join a reading's synthetic correlation and no file, and the backfill and the 'filed' health check count those events as filed

[`l3-thread-inherits-reading-correlations`](05-EXPECTED-VS-ACTUAL.md#l3-thread-inherits-reading-correlations) · P1 · step S14

Production read to size it: select count(*) from context_correlation_members m where m.org_id='<rohit_org>' and m.joined_via='thread' and not exists (select 1 from context_correlations c where c.org_id=m.org_id and c.correlation_id=m.correlation_id); and: select count(*) from (select m.event_id from context_correlation_members m left join context_correlations c on c.org_id=m.org_id and c.correlation_id=m.correlation_id where m.org_id='<rohit_org>' group by m.event_id having bool_and(c.correlation_id is null)) x;

### R-1 model decider: GENIOS_L4_LLM_DECISION_MAKER defaults off, but it was on in production on 1 Oct, which DEFERred every decision; current production value unknown

[`l4-llm-decision-maker-env`](05-EXPECTED-VS-ACTUAL.md#l4-llm-decision-maker-env) · P1 · step S02

Harsh: read the production env for GENIOS_L4_LLM_DECISION_MAKER and GENIOS_L4_LLM_DECISION_MAKER_ORGS (env, not .env file contents shared here).

### GeniOS-008 B3: a card or reminder cannot reach Rohit by email; there is no email transport

[`l5-b3-email-delivery-channel-missing`](05-EXPECTED-VS-ACTUAL.md#l5-b3-email-delivery-channel-missing) · P1 · step S37

select channel, active, last_digest_date from org_channels where org_id='<ORG>';

### C6 unbuilt: card context is the subject node's last 4 meetings and 3 promises, plus stock sentences, so details repeat across cards

[`l5-c6-person-level-context`](05-EXPECTED-VS-ACTUAL.md#l5-c6-person-level-context) · P1 · step S34

To confirm live cards anchor on one node: select s.subject_node_id, count(*) from cards k join signals s on s.signal_id=k.signal_id and s.org_id=k.org_id where k.org_id=:org and k.state in ('queued','surfaced','snoozed','claimed','delivered') group by 1 order by 2 desc;

### Cards read thin, repeated or garbled on every surface: the card writer (C1), the expert's result (C2) and per-card context (C6) are unbuilt

[`l5-card-writer-c1-c2-c6-unbuilt`](05-EXPECTED-VS-ACTUAL.md#l5-card-writer-c1-c2-c6-unbuilt) · P1 · step S34

select subject_node_id, count(*) from cards c join signals s on s.signal_id=c.signal_id where c.org_id='<rohit org>' and c.state in ('queued','surfaced','snoozed','delivered') group by 1 order by 2 desc limit 10;

### Delivery is pull-only: provisioning registers only in_app, Slack is the only push adapter and has no dashboard setup, and there is no email channel

[`l5-delivery-only-in-app`](05-EXPECTED-VS-ACTUAL.md#l5-delivery-only-in-app) · P1 · step S37

Read-only: select org_id, channel, active, last_digest_date, updated_at from org_channels order by 1,2;

### Fewer cards since 18 Oct: L5's own drop paths are recorded but have no surface, and production was not read

[`l5-fewer-cards-refusals-unmeasured`](05-EXPECTED-VS-ACTUAL.md#l5-fewer-cards-refusals-unmeasured) · P1 · step S01

Rohit's OK for read-only SQL: (1) select builder_version, output_lane, render_mode, state, count(*) from cards where org_id=:org and created_at >= '2026-10-11' group by 1,2,3,4 order by 5 desc; (2) select rule, writer, count(*), max(refused_at) from card_refusals where org_id=:org and refused_at >= '2026-10-11' group by 1,2; (3) select date_trunc('day', created_at) d, count(*) from cards where org_id=:org and created_at >= '2026-10-01' group by 1 order by 1;

### Post-meeting follow-up cards ('meeting.followup') fail all three card doors: never on GET /cards, and 'Open card' gives a 404

[`l5-meeting-followup-cards-fail-every-door`](05-EXPECTED-VS-ACTUAL.md#l5-meeting-followup-cards-fail-every-door) · P1 · step S36

Production impact, read-only: select count(*) as followup_cards, count(*) filter (where k.state in ('queued','surfaced','snoozed')) as open_ones, min(k.created_at), max(k.created_at) from cards k join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id where k.org_id = '<ORG>' and s.capability_id = 'meeting.followup'; select status, count(*) from transcripts where org_id = '<ORG>' group by 1;

### No card writer (C1): the subject is a clause cut of the model's move, a pack template, or the l5_render line; garbled headlines come from this chain

[`l5-subject-writer`](05-EXPECTED-VS-ACTUAL.md#l5-subject-writer) · P1 · step S34

To find the writer of the garbled headline (read-only, Rohit's permission): select card_id, builder_version, render_mode, capability_key, level, headline, recommended->>'what' as move, reject_code, reject_detail, created_at from cards where org_id=:org and (headline ilike '%calendar invite%' or headline ilike '%to body%'); then: select kind, cause, detail->'words' from card_events where card_id=:card order by occurred_at;

### The Mac app's 'Not useful' sends 'wrong' with no reason; the brain refuses it (422 invalid_wrong_reason) and the app swallows it, so no verdict reaches L6

[`l5-wrong-without-reason`](05-EXPECTED-VS-ACTUAL.md#l5-wrong-without-reason) · P1 · step S38

To size it (read-only): select type, detail->>'surface' as surface, detail->>'reason' as reason, count(*) from human_events where org_id=:org and type like 'card.%' and occurred_at >= '2026-10-01' group by 1,2,3 order by 4 desc; a missing 'desktop' wrong means every Mac 'Not useful' was lost.

### Migrations apply at boot, but a read-only database silently skips them; whether 0243–0250 are applied in production is unknown

[`process-migrations-applied-unknown`](05-EXPECTED-VS-ACTUAL.md#process-migrations-applied-unknown) · P1 · step S02

Production read: show default_transaction_read_only; select filename, applied_at from schema_migrations where filename >= '0243' order by filename; (expected: 0243_reasoning_results, 0248_l1_sync_runs_coverage_index, 0249_l2_admissions, 0250_screen_followup_read_path).

### Nothing measures production card volume or quality daily; the health tools exist but nothing runs or shows them

[`process-no-daily-production-card-health`](05-EXPECTED-VS-ACTUAL.md#process-no-daily-production-card-health) · P1 · step S05

Production read (Rohit's permission), read-only: select created_at::date d, builder_version, output_lane, count(*) from cards where org_id='<ORG>' and created_at >= now()-interval '45 days' group by 1,2,3 order by 1,2,3; select refused_at::date, writer, rule, count(*) from card_refusals where org_id='<ORG>' and refused_at >= now()-interval '45 days' group by 1,2,3 order by 1; select reviewed_at::date, status, count(*) from expert_reviews where org_id='<ORG>' and reviewed_at >= now()-interval '30 days' group by 1,2 order by 1; select reasoned_at::date, status, count(*) from reasoning_results where org_id='<ORG>' group by 1,2 order by 1; select sweep_at::date, stage, sum(n) from pipeline_counters where org_id='<ORG>' and sweep_at >= now()-interval '30 days' group by 1,2 order by 1,2;

### About 20 switches decide the card path; code flips some itself, and their production state is shown nowhere

[`process-switch-state-invisible`](05-EXPECTED-VS-ACTUAL.md#process-switch-state-invisible) · P1 · step S05

Production read: select org_id, feature, enabled_at, enabled_by, disabled_at from l4_activation where org_id='<ORG>' order by feature; select * from l3_activation where org_id='<ORG>'; select * from l2_v2_activation where org_id='<ORG>'; select * from l1_semantic_activation where org_id='<ORG>'; plus Harsh reads the host's GENIOS_L4_LLM_DECISION_MAKER, GENIOS_L4_LLM_DECISION_MAKER_ORGS, GENIOS_USE_DOMAIN_COMPILER, GENIOS_L1_LLM_GATE, GENIOS_ENABLE_L1_RELEVANCE values.

### The Screen page and the desktop's screen items depend on migration 0250 being applied in production

[`surfaces-0250-applied-unverified`](05-EXPECTED-VS-ACTUAL.md#surfaces-0250-applied-unverified) · P1 · step S02

select filename from schema_migrations where filename like '0250%'; select column_name from information_schema.columns where table_name='screen_followups' and column_name in ('read_by','due_phrase');

### B9 removed snapshot.notice, which the old dashboard reads unguarded; the deploy order was never verified

[`surfaces-b9-deploy-order-unverified`](05-EXPECTED-VS-ACTUAL.md#surfaces-b9-deploy-order-unverified) · P1 · step S02

Production check, not a database read: the deployed commit of the dashboard app (DO App Platform deployments list) vs the brain's deployed commit.

### YC-II D9 (STEP-15): the 08:00 morning brief is composed and kept, but the dashboard and Mac app read the old 'brief' endpoint

[`surfaces-d9-morning-brief-composed-but-no-surface-reads-it`](05-EXPECTED-VS-ACTUAL.md#surfaces-d9-morning-brief-composed-but-no-surface-reads-it) · P1 · step S36

Whether briefs are being kept in production: select local_date, composed_at from morning_briefs where org_id='<ORG>' order by local_date desc limit 7;

### Question cards and team/verify cards reach only GET /cards; Home 'Today', MCP, the agent API, push lanes, /v1/insights, Ask and the Context panel read decision cards only

[`surfaces-question-and-team-cards-reach-only-the-cards-page`](05-EXPECTED-VS-ACTUAL.md#surfaces-question-and-team-cards-reach-only-the-cards-page) · P1 · step S36

Production share, read-only: select k.builder_version, k.output_lane, count(*) from cards k where k.org_id = '<ORG>' and k.state in ('queued','surfaced','snoozed') group by 1, 2 order by 3 desc;

### The eight live bugs of 4 Oct: six are fixed in code, one is closed by an earlier note only, one is half verified

[`cross-eight-bugs-of-4-oct`](05-EXPECTED-VS-ACTUAL.md#cross-eight-bugs-of-4-oct) · P2 · step S13

Read-only: select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid in ('card_feedback_verdicts'::regclass,'card_feedback_revisions'::regclass) and contype='c'; and select max(completed_at), count(*) from calibration_runs where status='completed';

### 'Sync now' runs a second copy of the chain: no funnel numbers, no meeting/team/verify post-passes, and none of the sweep's plan or quota gates

[`cross-sync-now-runs-a-second-chain`](05-EXPECTED-VS-ACTUAL.md#cross-sync-now-runs-a-second-chain) · P2 · step S10

Production comparison, read-only: select date_trunc('day', sweep_at) d, sum(n) filter (where stage = 'card_delivered') funnel_cards from pipeline_counters where org_id = '<ORG>' and sweep_at >= '2026-10-15' group by 1 order by 1; select date_trunc('day', created_at) d, count(*) cards_created from cards where org_id = '<ORG>' and created_at >= '2026-10-15' group by 1 order by 1; select date_trunc('day', created_at) d, count(*) sync_jobs from sync_jobs where org_id = '<ORG>' and created_at >= '2026-10-15' group by 1 order by 1;

### Gmail incremental sync keys on a date, not historyId (A4)

[`l1-a4-gmail-historyid-cursor`](05-EXPECTED-VS-ACTUAL.md#l1-a4-gmail-historyid-cursor) · P2 · step S11

H2 fixture from the production Composio connection

### GeniOS-008 C2: <founder company mailbox> as a second (seat) mailbox, default yes, not known to be connected

[`l1-c2-second-mailbox`](05-EXPECTED-VS-ACTUAL.md#l1-c2-second-mailbox) · P2 · step S08

select connection_id, source_type, seat_id, status, created_at from connections where org_id='<ORG>';

### YC-II D23 + B27/F58: promoting Boardy's archived intros (pending Rohit's list read) would read only the stored list snippet

[`l1-d23-b27-promoted-archive-reads-only-the-snippet`](05-EXPECTED-VS-ACTUAL.md#l1-d23-b27-promoted-archive-reads-only-the-snippet) · P2 · step S06

`python scripts/promote_archived.py --org <ORG> --rule N-02 --sender-domain boardy.ai --database-url <prod>` (dry run)

### Bundles (E1) are written every sweep, but their only reader is the L2 pass, which is off unless l2_reasoning is on

[`l1-e1-bundles-read-only-in-shadow`](06-DECISIONS.md#l1-e1-bundles-read-only-in-shadow) · P2 · step S25

Production: select feature, enabled_at, disabled_at from l4_activation where org_id='<ORG>'; select count(*), max(created_at) from signal_bundles where org_id='<ORG>';

### L2 raises evidence needs, but the fetchers are off, so no re-entry happens and no card says 'waiting on X'

[`l2-evidence-loop-not-armed`](05-EXPECTED-VS-ACTUAL.md#l2-evidence-loop-not-armed) · P2 · step S13

select count(*), state from evidence_needs where org_id='<ORG>' and need_id like 'l2need:%' group by 2;

### graph_facts.authority_rank holds a 0-6 ladder and a derived default of 100 in the same column

[`l3-two-authority-scales`](01-WHAT-WENT-WRONG.md#l3-two-authority-scales) · P2 · step S17

H9: set transaction read only; select field, count(*) from graph_facts group by field having bool_or(authority_rank <= 6) and bool_or(authority_rank > 6);

### Half of planned actions require approval but nothing can name the approver; there is no engine writer for org data (seats, reports_to, responsibilities)

[`l4-approver-and-org-data-writer`](05-EXPECTED-VS-ACTUAL.md#l4-approver-and-org-data-writer) · P2 · step S32

Read-only: select count(*) filter (where requires_approval) as gated, count(*) from execution_actions where org_id=:org; select count(*) from authority_rules where org_id=:org;

### The durable ADAPTIVE recommendation-learning write is closed only by arithmetic (distinct_days=1); fixing it opens an auto-promoted write

[`l6-adaptive-distinct-days-trap`](06-DECISIONS.md#l6-adaptive-distinct-days-trap) · P2 · step S40

Rohit's OK for: select unit, result_state, sink_reason, count(*) from learning_object_evaluations where unit='recommendation_learning' group by 1,2,3;

### Calibration now runs (bug 1 fixed in shadow), but its would-mute and would-nudge results are read by nobody; the B22–B24 traps are still in the apply path

[`l6-calibration-shadow-unread`](05-EXPECTED-VS-ACTUAL.md#l6-calibration-shadow-unread) · P2 · step S40

Read-only: select run_id, status, completed_at, result->'would_mute' wm, result->'would_nudge' wn, result->'rules_scored' rs from calibration_runs where org_id=:org order by completed_at desc nulls last limit 5;

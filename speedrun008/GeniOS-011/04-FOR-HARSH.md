# 04 · For Harsh: what was built, how to deploy it, what to do in production

**Written for:** Harsh (CTO; owns deploys, production, switches and migrations). Rohit reads §0 and §4.

**Where it is:** `origin/speedrun008` (see [03-LOG](03-LOG.md) for the head SHA).
- It is a strict descendant of `origin/harsh/mvp` `0cc8d83c` (your 22 Oct head, CI green). So it merges into `harsh/mvp` as a **fast-forward**, with no conflict.
- Two built-and-held units are on their own remote branches: `g011-S02U5` and `g011-S16U3` (§3).

**What GeniOS-011 is:** the 23 Oct audit (255 verified items, [05](05-EXPECTED-VS-ACTUAL.md)) and its plan ([02](02-PLAN.md)). [07-LOOPHOLES](07-LOOPHOLES.md) is the shortest read: 23 reasons the website does not make the cards Rohit's local ideal dashboard shows.

---

## §0 · TL;DR: your list, in order

| # | Do | Why (loophole) | How | Done when |
|---|---|---|---|---|
| 1 | **Tell us what is deployed** | F1, A3 | The SHA and the date the deploy host runs. Whether migrations 0191–0250 are applied: `select filename, applied_at from schema_migrations where filename >= '0191' order by 1;` | written into [03-LOG](03-LOG.md) |
| 2 | **Is Rohit's org expired?** If yes, put it (and the design partners) on a non-expiring internal plan | **A1**: since `7075014c` the sweep skips the whole chain for an expired org | `select id, subscription_tier, plan_status, plan_expires_at, grace_until, is_internal from orgs where id = '<ORG>';` (reading `org_plan_state` in S01.U1), then your plan tool or the admin route. Pricing rules stay as you restored them in `4f791884`. | the sweep runs for his org (a `daily_health` row tomorrow, §2) |
| 3 | **Deploy `origin/speedrun008`** | everything in §1 | Fast-forward `harsh/mvp` to it. Set `GENIOS_BUILD_SHA=<sha>` in the deploy env. Migration **0251** applies at boot (`main.py:89` `apply_migrations`). | `GET /health` → `build_sha` = the SHA, `schema_head` = `0251_daily_health.sql` |
| 4 | **Run the read-only readings** (with Rohit's permission) | every "unknown" item | `python scripts/g011_prod_readings.py --org <ORG> --show-sql` (prints, opens nothing), then `--out readings.json`. One read-only transaction; it refuses anything but SELECT/WITH/SHOW. | `readings.json` sent to Rohit/Claude. **Never commit it** (real data). |
| 5 | **Switches for Rohit's org** | **A2** | Read `l4_activation`, `l1/l2/l3` activation and the Founder Office domain for `<ORG>` (SQL in §5). Switch on `expert_review` and Founder Office. Leave `l2_reasoning`/`l2_cards` off until the real-model pass (§4 #3). | the readings show them on |
| 6 | **365-day resync of his Gmail and Calendar** | **B1**: the default window is 60 days; the Theresa/Antler thread is 77 days old | PATCH `/connections/{id}/backfill-window` to 365 days (or after S09.U1 ships, the founder's pick). Then `python scripts/resync_deleted_mail.py --org <ORG> --days 365` (dry run first, then `--apply`). **Quota:** the resync can fill the ingestion meter (see #2). | `l1_sync_runs` shows the backfill; the funnel's events-in rises |
| 7 | **Arm the evidence fetchers** | **B6** | `GENIOS_NEED_FETCHERS=on` in env (after #3). | `evidence_needs` rows move off `open` |
| 8 | **Branch protection** (with Rohit, repo admin) | **F1**: the prod branch took red CI four times | Require the `ci` checks on `harsh/mvp`, and let the deploy host build green SHAs only. | a red PR cannot merge |
| 9 | **D23 Boardy promotion** (dry run first, Rohit reads the list) | old archived intros | `python scripts/promote_archived.py --org <ORG>` (dry), then `--apply --crypto-key …` with `GENIOS_ALLOW_PROD_WRITE=1`. **Changed by S06.U2:** `--apply` now re-fetches each body through the connector before promoting, and a mail that can't be fetched stays archived ("NOT FETCHED"). | promoted mail has full bodies |
| 10 | **Do NOT** add an `org_channels` email row yet | S37.U2 note | Email is registered but has **no transport**. An email row before a provider exists makes every card fail its one email delivery. | — |

---

## §1 · What is on `origin/speedrun008`: every unit, what it changes, how to see it, how to roll back

Each unit is one commit with its own tests and a **mutation proof**: the change was reverted, its test went red, and it was restored. The integrator (Claude) re-ran every test and redid one mutation per unit. The hermetic suite across all folders is green (~19,200). Golden: board unchanged (63/4 on both paths, the same four failing). **Rollback of any unit** = `git revert <commit>`; units are independent except where noted.

### L1 Signals (`capture/`)

| Unit · commit | What changes in behaviour | Flags / env | What you should see after deploy | Risk |
|---|---|---|---|---|
| **S06.U1** `c90cdc3a` | The parked drain **never re-admits an archive** any more. An `llm_junk` archive whose gate version changed is filed as a pending `llm_junk_rejudge` park and re-judged only from the **whole message**. Every S2 verdict now records `gate_version`. | — | Fewer junk extractions. `capture_park` rows with code `llm_junk_rejudge` appear only after a gate prompt change. | Until the whole-message reader is wired into `api/routes._reread_unread` (open, next unit), a re-judgment waits `pending`. Nothing is filed until a gate change, because only new verdicts carry a version. |
| **S06.U2** `5c93b2ae` | A failed or refused Gmail full fetch **retries once (1 s), then parks as DOC-05**. It is never stored as the snippet. Gmail `_execute` has a hard deadline. `SyncSummary.body_fetch_failed` counts it. `promote_archived --apply` re-fetches. `composio.whole_message_reader` exists. | `GENIOS_L1_FULL_FETCH_RETRY_PAUSE_S` (default 1) | DOC-05 parks on `email_message` when Gmail refuses; a `document_jobs` row with `fetch_failed`. | The DOC-05 email parks have **no re-fetch rung yet**; they wait `pending` (visible in `read_aging`). The count is in `SyncSummary`, not yet a column of `l1_sync_runs`; that needs `alter table l1_sync_runs add column if not exists body_fetch_failed integer not null default 0` plus the `_run_ledger` insert (next routes unit). |

### L3 Context Graph (`context/`)

| Unit · commit | What changes | What you should see | Risk |
|---|---|---|---|
| **S14.U1** `ee46dc5f` | A reply after a reading **joins the counterparty's file**. Thread inheritance, the backfill skip and the workstreams "filed" count read engine-owned correlations only (a join on `context_correlations`). | Fewer "unfiled" counterparties in context health. More events in files. | The backfill pass now files events only a reading had declared, so a one-time catch-up on the next backfill run is expected. |

### L2 Qualification (`reason/`)

| Unit · commit | What changes | What you should see | Risk |
|---|---|---|---|
| **S18.U1** `c4bfba7a` | Judged (expert/L2) files are **decided before the formula situation loop** spends the 7-a-day cap. Every no-card reason (`covered_without_situation`, `expert_no_tenant_pack`, `expert_shadow`, `budget_exhausted`, `expert_error`) is in `covered_no_card` and logged at **WARNING** with the file id. | Expert cards are no longer crowded out by template cards. WARNING lines name lost files. | The daily allowance is now taken from the first covered file's pack. An unadmitted situation the review explains can now be a file's home. |
| **S18.U2** `4c96dfa5` | `l2_judges` requires `l2_cards` **and** `l2_reasoning` **and** a buildable R-9 client; otherwise R-7 reviews as before and logs a WARNING. A per-call over-budget refusal carries **only that file** (the daily cap still stops the pass). | With `l2_cards` on and `l2_reasoning` off, the expert still reviews (before, nothing did). | A tenant with `l2_cards` on and no model returns `skipped: no_model_configured` with two WARNINGs. |
| **S18.U3** `7fdd410b` | `run_all` puts **8 why-no-card counts** on the sweep outcomes (judged, held, refused, truncated, carried_budget, fell_back, covered_not_carded, budget_exhausted) and logs one line per sweep. It logs `l2_pass`'s skip. `scripts/pipeline_health.py` gains `check_the_l2_judgment_says_why`. `GET /v1/workstreams/{file_id}` gains `why_no_card` (`reason`, `says`). | Run `python scripts/pipeline_health.py`: the new check reads `reasoning_results`, `l2_admissions` and R-9 spend. The file page says why it has no card. | The counts are not yet persisted per sweep: `_run_l2_chain` does not store `outcomes` (S05.U1's daily row reads the tables instead). |
| **S27.U1** `bb0060b7` | **Goals, interim:** the weekly brief review now drafts for **every tenant**, not only one with an accepted line, and re-claims a failed week. The drafter (prompt v4) sees **files, open situations and in-motion lines** and proposes **one goal per piece of work** (deduped). | New goal **proposals** on the Goals page (accept/reject). | **Cost:** one Sonnet-class call per tenant per week, now for every tenant with memory (`no_patterns` makes no call). Skipping expired orgs is an open follow-up. |

### L5 Delivery (`deliver/`) and surfaces

| Unit · commit | What changes | What you should see | Risk |
|---|---|---|---|
| **S36.U1** `f3579b0d` | The situation-card door keys on its **builder** (`team.emit.v1`, no run, rule = capability), not a `team./verify.` prefix. | **Meeting follow-up cards** appear in `GET /cards` and open (before: 404). | — |
| **S36.U2** `8c5cd041` | **One live-card fragment** (decision + situation + question doors) for every reader: morning brief / Home Today, Context panel, `/v1/insights` and dismiss, MCP session, agent poll, push, outbox, Ask recall. `PUSH_CARD_DOORS = ("decision",)`. An AST guard fails any card SQL naming its own door. | Question and follow-up cards on Home, MCP and Ask. | Recall now grounds on live cards, not open signals. Agent keys still see decisions only, and feedback on a question card from the extension returns 409 (both product calls for Rohit). |
| **S37.U2** `6224ccaa` | `get_channel('email')` returns `EmailChannel`, **OFF**. `TRANSPORTS` is empty and a test pins it. `CHAT_CHANNELS` gains email, so quiet hours apply. | Nothing, until a provider exists (Rohit, S37.U1). | §0 #10: no email row before a transport. |

### Process, measurement, goals docs

| Unit · commit | What it is | How you use it |
|---|---|---|
| **S03.U1** `67404da2` | `GET /health` returns `build_sha` (env `GENIOS_BUILD_SHA`, `'dev'` if unset) and `schema_head` (latest `schema_migrations` filename, null on a read error, never raises). | Set `GENIOS_BUILD_SHA` at deploy; check it after. |
| **S05.U1** `aa338284` | **Migration `0251_daily_health`** plus `platform/daily_health.py`. After each heavy tick (fail-open, 20-minute bound) it writes yesterday's row per org: cards by builder and lane, refusals by rule, expert, L2 and admission counts, the funnel's five numbers, LLM calls, failures and truncations, R-site outcomes and DB size. It runs once a day by key. **ops_alert** fires when cards fall below half the 14-day median, when a lane with a non-zero median is empty all day, or when the **DB passes 450 MB** (`GENIOS_DB_SIZE_CEILING_MB`). Rows older than 120 days are purged. `/reset` erases it (`7d3a5c7b`). | `select * from daily_health where org_id='<ORG>' order by day desc limit 7;` ⚠ Production was 446 MB on 19 Oct, so the size alert will likely fire; that is intended, and you can raise the env value. |
| **S01.U1** `1c66931b` | `scripts/g011_prod_readings.py`: 86 read-only readings keyed by audit item (§0 #4). The builder fixed 3 SQL errors in the audit's own queries. | §0 #4 |
| **S07.U1** `7c353eb5` | `scripts/golden_eval.py` asks R-9 on `claude-sonnet-5` with its site settings (thinking off, 8,000), `--l2-path`, and `--probe` (≤2 live calls, prints stop_reason/output_tokens). | Only with Rohit's spend yes (S07.U2). |
| **S40.U2** `88473081` | `GET /feedback/precision` also returns the last **shadow** calibration (would mute, recover or nudge, with precision and n) and precision by layer. Read-only; `calibration_apply` untouched. | Look before ever arming calibration (D13 stays off). |
| **S04.U1** `c6e10ee4`, **S04.U3** `5044b70b`, `a77fd748` | CI guards: the nine situation writers may only shrink; model sites stay in their layer (6 out-of-place sites pinned, shrink-only); no fixed calendar date beside a wall-clock read; the clock-at-import guard reads every import statement. | They fail CI when a new violation lands. |
| **S26.U2** `f5ed8a19`, **S26.U3** `742859dd` | Docs: GeniOS-009 corrected. `00-ARCHITECTURE` defines the goal object, `GoalImpact` and `GoalProposal`. GeniOS-009 gains G1.6/G3.5/G4.5/G6.8 and F72; D7/D9–D12 recorded from Rohit's words ("goals manually nahi daal sakte"): L2 proposes, he approves in one click via the brief door. | Read before building G1. |

---

## §2 · After the deploy: what to check (15 minutes)

1. `curl https://api.thegenios.com/health` returns `build_sha` = the deployed SHA and `schema_head` = `0251_daily_health.sql`.
2. Logs of the next heavy tick:
   - a `why no card` line per sweep (S18.U3);
   - WARNINGs naming lost files (S18.U1/U2);
   - `daily_health` written.
3. `select * from daily_health order by day desc limit 5;` has a row for each active org.
4. Rohit's Cards page:
   - meeting follow-ups open;
   - question cards show on Home Today.
5. `python scripts/pipeline_health.py` shows `check_the_l2_judgment_says_why` as PASS or NO DATA, never FAIL without a reason.

If anything breaks: revert the one unit (table in §1). Migration 0251 is additive (one new table) and safe to leave.

---

## §3 · Built, verified, and held on purpose (do not merge yet)

| Branch | Unit | What it does | Why it is held | Merge when |
|---|---|---|---|---|
| `g011-S02U5` (`15a86e31`) | Every sweep skip is a row | Every gate refusal (paused, plan_expired, over_budget, sync_quota) writes an `l1_sync_runs` row with its reason. All four doors (sweep, Sync now, sync one, backfill) ask one `_sweep_gate`. The quota bypass is logged and audited. 82 tests; mutation red. | It makes **Sync now refuse an expired org**. If Rohit's org is expired (A1), Sync now is his only remaining source of cards. | §0 #2 is done, so his org is on an internal plan |
| `g011-S16U3` (`bd260f0a`) | The L2 snapshot is as-of, with unknowns and contradictions | `read_snapshot(as_of=)` is required, and block B shows typed absences and open contradictions. 14 tests, 9 mutants red. | Golden replays judge at past instants, but `recorded_at` is wall-clock, so on the L2 path every replay snapshot loses its edges. That path is the measurement for switching `l2_cards` on. | the replay harness pins knowledge time (new unit) |

---

## §4 · What only Rohit decides (Harsh: nothing to do until he answers)

1. **Production read permission**, or he runs §0 #4 himself.
2. **STEP-13b go.** It merges the claim-check fixes that cut held cards from 79% to 18.5% (branches `yc2w27-int13b`/`yc2w27-s13b`). Loophole D5.
3. **~$5 for one real-model pass** (S07.U2). Loophole D10.
4. **Founder playbooks "label and use"** (D6) · **D57** quiet files (D7) · **L1 contract words** (B5) · **email provider** (S37.U1).
All are in [06-DECISIONS](06-DECISIONS.md), each with a recommended default.

---

## §5 · Known issues you will meet

- **Golden runs on a shared scratch DB collide.** `tests/replays/engine_runner.py` (~line 581) upserts `connections` on the global `connection_id`, so overlapping runs steal each other's mailbox and give false CassetteMiss. Run golden alone. A fix unit is open.
- **F45 missed only in a whole-lane local run** (4 tests); the four files in full gave 272 passed. CI's `golden-pg` job decides; see 03-LOG.
- **Pre-existing failures** (fail on `0cc8d83c` too): 6 in `tests/reason/adapters/test_l3_pilot_report.py` and `test_roster_reaches_the_audit.py`.
- **The repo is public** and carries Rohit's address and the prod org id in older files. Making it private is Rohit's call (06). This folder redacts them.

---

# Appendix (generated from the audit)

## A1 · Production actions in the plan (yours, or yours with Rohit)

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

## A2 · Every production question, with its read-only SQL

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

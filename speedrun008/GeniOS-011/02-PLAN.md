# 02 · The plan — every remaining step, in order

**Written for:** Rohit, Harsh and every coding agent.

43 steps close the 255 verified items of [05](05-EXPECTED-VS-ACTUAL.md), [01](01-WHAT-WENT-WRONG.md) and [06](06-DECISIONS.md). Every item lands in exactly one step.

The planner checked the placement with a script. Its notes at the end list the corrections and the dependency conflicts it resolved.

## How the order was chosen

1. **Measure production first (S01–S02).** Every later step should fix a measured cause, not a guess. This is what we skipped before.
2. **Stop red code reaching production (S03–S05).** Build SHA on /health, branch protection, a post-deploy health job, a daily card-health row, and a release gate.
3. **Real-model measurement (S07).** Fix the harness, then run capped live passes. Each paid pass starts with 1–2 probe calls.
4. **Make the chain carry the work, layer by layer:**
   - L1 (S06, S08–S13): the junk filter filters, the gate sees who wrote, the history window, and workstream words;
   - L3 (S14–S17): an event stays in its conversation's file, one counterparty has one file and one live situation, and memory holds what was said;
   - L2 (S18–S25): a judged file is never lost silently, held cards speak in the founder's words, and the switch to L2 cards happens one type at a time.
5. **Goals (S26–S33).**
   - First the plan is amended so that L2 proposes goals from what is in motion. L3 admits them as proposals, and Rohit approves in one click.
   - Then G1 → G9.
   - S27 is the interim: the brief drafter sees what is in motion now.
6. **Cards and surfaces (S34–S39).** The L5 card writer, the queue, delegate, every card door on every surface, push by email, the Mac app, and dashboard honesty.
7. **Learning (S40) and docs/lessons (S41–S42).**
8. **Blind verification (S43).**

## Standing rules for every unit

- **New architecture only** (GeniOS-008 `01-RULES`):
  - built beside, not instead;
  - the golden set compares the two paths;
  - a switch flips only when the new path is at least as good.
- **One writer per file.** Shared hot files are serialised:
  - `api/routes.py`: S03.U1 → S02.U5 → S10 → S14.U2 → S17.U3 → S34.U1 → S35.U3 → S39.U1;
  - `reason/domain_shadow.py`: S18.U1 → S18.U4 → S24.U2 → S25.U4 → S34.U2.
- **Every code unit has its own tests plus a mutation proof.** The proof needs a clean baseline and `PYTHONDONTWRITEBYTECODE=1`, and the mutant must be restored.
- **Full suites run in CI.** Locally only the unit's own tests run (memory: full-suites-are-ci-and-harsh).
- **Dashboard and Mac changes start as a clickable dummy.** Real files follow only after Rohit approves. A "ha" to a plan is not a go.
- **Never repair `distinct_days` before ADR-10.** `calibration_apply` stays off (D13).
- **Founder golden cases cannot name Antler or Theresa** (`REAL_NAMES`), so the goal case is a synthetic analogue.
- **No production read without Rohit's permission.** No paid pass without his spend yes.


## The North Star

Every piece of work Rohit is pursuing reaches him as ONE clear card that names the goal it moves: real mail and meetings in (L1 capture) → filed into one counterparty file (L3 context) → judged by the model as a domain expert (L2 packs + reason/l2) → admitted by L3 → one card per piece of work with its next move and goal (L4 executive / L5 deliver) → goals proposed automatically from what is in motion (L2 proposes, L3 admits, Rohit approves in one click) → outcomes learned (L6 feedback). And no change reaches production unless CI is green on that SHA, a capped real-model pass measured it, and the next day's production card numbers hold on Rohit's org first.

## Critical path

[S01](#s01) → [S02](#s02) → [S07](#s07) → [S18](#s18) → [S14](#s14) → [S15](#s15) → [S20](#s20) → [S21](#s21) → [S24](#s24) → [S25](#s25) → [S26](#s26) → [S28](#s28) → [S29](#s29) → [S30](#s30) → [S31](#s31) → [S43](#s43)

## Every step at a glance

| Step | Title | Layers | Depends on | Claude can start now | Group | Items |
|---|---|---|---|---|---|---|
| [S01](#s01) | Measure production first (read-only) | Process, L1, L2, L3, L5 | — | yes | A-measure | 5 |
| [S02](#s02) | Unblock production after measuring (plan state, schema, deploy order, switches, brief) | Process, Cross-layer, L1, L2, L3, Surfaces | S01 | yes | A-measure | 9 |
| [S03](#s03) | Stop red code reaching production | Process | — | yes | B-gates | 7 |
| [S04](#s04) | Fast CI and the Rule 3 guards | Process | — | yes | B-gates | 7 |
| [S05](#s05) | Daily production card health, switch state and the release gate | Process, Cross-layer | S03, S01 | yes | B-gates | 4 |
| [S06](#s06) | L1: the junk filter filters, and a body we did not get is never passed off as the body | L1 | — | yes | C-L1 | 4 |
| [S07](#s07) | Real-model measurement: fix the harness, then capped live passes | Process, L1, L2 | — | yes | A-measure | 8 |
| [S08](#s08) | L1: the gate sees who wrote; the second mailbox; Indian public mail hosts | L1 | S07, S06 | no | C-L1 | 4 |
| [S09](#s09) | L1: the history window the founder picks, and the resync | L1, L3, Goals | S02, S14 | yes | C-L1 | 6 |
| [S10](#s10) | L1: refusals and skips the founder can see; one chain for Sync now | L1, Cross-layer, Surfaces | S02, S03 | yes | C-L1 | 3 |
| [S11](#s11) | L1 connector hardening: pin Composio, key Gmail on historyId | L1 | S06, S01 | no | C-L1 | 4 |
| [S12](#s12) | L1 contract: words for the founder's workstreams (vocabulary, objects, roles, lifecycle) | L1, L2 | S07 | no | C-L1 | 8 |
| [S13](#s13) | L1→L2 bundle and the evidence loop | L1, L2, L3, Cross-layer | S12, S02 | yes | C-L1 | 6 |
| [S14](#s14) | L3: events stay in their conversation's file; a rebuild is reproducible | L3 | — | yes | D-L3 | 4 |
| [S15](#s15) | L3: one counterparty, one file, one live situation; admission sees every reading | L3 | S14, S01 | no | D-L3 | 5 |
| [S16](#s16) | L3: memory holds what was said (promises, quotes, snapshot) | L3, L2 | — | yes | D-L3 | 3 |
| [S17](#s17) | L3 hygiene: failures visible, no every-sweep rewrites, layer names, one authority scale | L3 | S14 | yes | D-L3 | 4 |
| [S18](#s18) | L2: a judged file is never lost silently | L2, Cross-layer | — | yes | E-L2 | 5 |
| [S19](#s19) | L2: what the judgment proposes is written; a failed judgment keeps the last good review | L2 | S18, S20 | yes | E-L2 | 3 |
| [S20](#s20) | STEP-13b decision, the claim check, and held cards in the founder's words | L2, Process | S07 | no | E-L2 | 7 |
| [S21](#s21) | L2 subjects: one investor wave, quiet files re-looked, seeds become files | L2, Cross-layer | S20, S15, S13 | no | E-L2 | 4 |
| [S22](#s22) | L2's judgment reaches the card: six-dimension confidence, options, Plane D package | L2, L5, Surfaces | S20, S19 | no | E-L2 | 3 |
| [S23](#s23) | Founder Office expertise reaches founder work | L2, L5 | S02 | yes | E-L2 | 5 |
| [S24](#s24) | L3 admits: a situation exists only after L2's judgment (G0.3), first type | L3, L2, Cross-layer, Goals | S15, S18, S21 | no | D-L3 | 6 |
| [S25](#s25) | Switch L2 cards on one situation type at a time and retire the formula lanes | L2, L1, Process | S07, S20, S24, S05, S04 | no | E-L2 | 8 |
| [S26](#s26) | Goal decisions, and the plan amended so L2 proposes goals | Goals, Process | — | yes | F-goals | 10 |
| [S27](#s27) | Interim: goals proposed from what is in motion and visible today | Goals, Surfaces | S02 | yes | F-goals | 5 |
| [S28](#s28) | G1: the goal object | Goals, L3 | S26 | no | F-goals | 3 |
| [S29](#s29) | G2 + G3: goals in the judgment, and L2 proposes a goal that L3 admits as a proposal | Goals, L2, L3, Cross-layer | S28, S24, S20 | no | F-goals | 4 |
| [S30](#s30) | G4 + G5: goals linked to situations, progress measured | Goals, L3, L2 | S29, S15 | no | F-goals | 2 |
| [S31](#s31) | G6 + C8: the goal on every card, and one-click approve where the founder looks | Goals, L5, Surfaces | S30, S35, S36 | no | F-goals | 3 |
| [S32](#s32) | G7 + G8: check-in states, a human decides, then L4 plans | Goals, L4 | S30, S24 | no | F-goals | 5 |
| [S33](#s33) | G9 and value: outcomes move goals; the North Star and AER/HIR | Goals, L6, Surfaces | S32 | no | H-L6 | 5 |
| [S34](#s34) | L5 card writer: own context (C6), the expert's result (C2), a clear subject (C1) | L5, L2 | S01, S18, S20 | no | G-L5 | 6 |
| [S35](#s35) | L5 queue, quotes, delegate, 'this is right', versions (C3, C4, C5, C7, C9) | L5, Surfaces | S34, S36 | no | G-L5 | 9 |
| [S36](#s36) | L5: every card door reaches every surface; meeting follow-ups open | L5, L4, Surfaces | — | yes | G-L5 | 4 |
| [S37](#s37) | Push delivery: email first | L5 | — | yes | G-L5 | 2 |
| [S38](#s38) | Mac app: one app, and no press is swallowed | Surfaces, L5 | — | no | G-L5 | 4 |
| [S39](#s39) | Dashboard honesty: no made-up numbers, no dead routes, one card reader | Surfaces | S03 | yes | G-L5 | 10 |
| [S40](#s40) | L6: learning that someone reads | L6, Surfaces | — | yes | H-L6 | 5 |
| [S41](#s41) | Docs tell the truth (layer logs, L3 folder, status files, memory) | Process, L1, L2, L3 | — | yes | I-docs | 10 |
| [S42](#s42) | Lessons kept as rules | Process, Surfaces, L2, L4, L6 | — | yes | I-docs | 33 |
| [S43](#s43) | Verify the product blind (Phase 0 registry, Phase 5 / STEP-19 benchmark re-run) | Process, L1 | S25, S31, S07, S08 | yes | I-docs | 2 |

## The steps

<a id="s01"></a>
### S01 · Measure production first (read-only)

- **Why:** Every later step must fix a measured cause, not a guess. Production has not been read since the 823-commit merge (which reached origin only in the 21 Oct 16:20 UTC push, per 480f7cd4 and the Actions API), so which producer makes Rohit's cards, the switch state, the funnel loss, card counts per day and card_refusals are all unknown (F6). Fewer/weird cards (F2) cannot be attributed without this.
- **Layers:** Process, L1, L2, L3, L5 · **group:** A-measure · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U2 needs Rohit's permission for read-only production SQL; U3 needs Harsh. U1 needs neither.
- **Items it closes:** [The 4 Oct funnel loss is fixed in code, but production's funnel has not been mea](05-EXPECTED-VS-ACTUAL.md#l1-post-deploy-funnel-unmeasured); [No one measured production after the 18 Oct deploy: switch state, card counts an](01-WHAT-WENT-WRONG.md#process-no-production-number-after-deploy); [Fewer cards since 18 Oct: L5's own drop paths are recorded but have no surface, ](05-EXPECTED-VS-ACTUAL.md#l5-fewer-cards-refusals-unmeasured); [823 commits reached production in one merge on 18 Oct, with no production number](01-WHAT-WENT-WRONG.md#process-823-commit-big-bang-deploy); [The L2/L3 rebuild reached production before its audit, and the audit then found ](01-WHAT-WENT-WRONG.md#cross-l2-l3-rebuild-shipped-before-its-audit)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S01.U1** | One read-only measurement runner holding every blocked_on query of GeniOS-011 | `scripts/g011_prod_readings.py`<br>`tests/scripts/test_g011_prod_readings.py` | The script opens one connection, issues `set transaction read only` first, refuses any statement whose first keyword is not SELECT/WITH/SHOW, requires --org, and writes one JSON keyed by item key: source_events outcome/attention since 18 Oct, event_trace S1/S2, qualified_signals by type/state, l1_sync_runs, l1..l4 activation rows, cards per day by builder_version/output_lane/state since 1 Oct, card_refusals by rule, expert_reviews and reasoning_results by status/fate, l2_admissions by decision/op, l4_r_site_calls by site/outcome, llm_costs per day, schema_migrations >= 0191, orgs plan/billing state, kill switches, evidence_needs by state, connections capture_scope, company_brief_lines by section/status, live-situation multiplicity per anchor, DB size and top tables. Hermetic test: a planted INSERT/UPDATE/DELETE is refused and every query binds the org parameter; mutation removing the guard turns the test red. | claude | code |
| **S01.U2** | Rohit's permission and one run of the readings | — | Rohit says yes (or runs it himself); the JSON, with e-mail addresses redacted, is committed at speedrun008/GeniOS-011/measurements/<date>-prod-readings.json. | rohit | prod_action |
| **S01.U3** | Deploy and env facts SQL cannot answer | — | Harsh records in GeniOS-011 03-LOG: DO App Platform deployment history (SHA, time) 18–23 Oct for brain and dashboard; the auto-deploy setting; set/unset state of GENIOS_L4_LLM_DECISION_MAKER(_ORGS), GENIOS_USE_DOMAIN_COMPILER, GENIOS_L1_LLM_GATE, GENIOS_ENABLE_L1_RELEVANCE, GENIOS_NEED_FETCHERS, GENIOS_OPS_ALERT_WEBHOOK; Composio SDK and toolkit versions; whether rest_stuck_reviews.py --apply and resync_deleted_mail ran. | harsh | prod_action |
| **S01.U4** | Measured baseline and loss attribution | `speedrun008/GeniOS-011/01-MEASURED.md` | Each unknown P0/P1 item is restated with its measured number; the biggest card-loss stage is named (funnel stage, card_refusals rule, covered_without_situation/expert_shadow, billing skip, switch off); the order of S02–S25 is re-ranked where a measurement contradicts it, as an appended line, never an edit. | claude | docs |

<a id="s02"></a>
### S02 · Unblock production after measuring (plan state, schema, deploy order, switches, brief)

- **Why:** Several silent stops sit outside code. A lapsed trial drops Rohit's org from every scheduled sweep, the warm lane and Ask (P0, 7075014c measured his grace closed 21 Sep). Unapplied migrations (25 files 0191–0250) break admission and screen reads. An old dashboard crashes on the new brain (B9). The LLM decider may DEFER every decision. Founder Office/expert_review may be off. The gate protects founder senders only through accepted brief lines.
- **Layers:** Process, Cross-layer, L1, L2, L3, Surfaces · **group:** A-measure · **depends on:** S01 · **Claude can start now:** yes
- **Blocked on:** U1–U4 wait on S01's readings, Rohit's yes (A5, D1, D35, brief lines) and Harsh. U5 is code and can start after S03.U1 releases api/routes.py.
- **Items it closes:** [A lapsed trial, a full ingestion meter or the daily model cap silently stop Rohi](05-EXPECTED-VS-ACTUAL.md#cross-billing-gates-silently-stop-the-org); [The Screen page and the desktop's screen items depend on migration 0250 being ap](05-EXPECTED-VS-ACTUAL.md#surfaces-0250-applied-unverified); [Migrations apply at boot, but a read-only database silently skips them; whether ](05-EXPECTED-VS-ACTUAL.md#process-migrations-applied-unknown); [B9 removed snapshot.notice, which the old dashboard reads unguarded; the deploy ](05-EXPECTED-VS-ACTUAL.md#surfaces-b9-deploy-order-unverified); [R-1 model decider: GENIOS_L4_LLM_DECISION_MAKER defaults off, but it was on in p](05-EXPECTED-VS-ACTUAL.md#l4-llm-decision-maker-env); [The LLM decision maker ran in production for every org with no fallback, and a s](01-WHAT-WENT-WRONG.md#l2-llm-decider-without-fallback-in-production); [GeniOS-008 A4 + L2 04-FOR-HARSH §3: Founder Office, expert_review and l2_reasoni](05-EXPECTED-VS-ACTUAL.md#l2-founder-office-and-expert-switches-prod-state); [YC-II D14, D35 (+F96): whether Rohit's company domain is declared as 'us' and th](05-EXPECTED-VS-ACTUAL.md#l3-d14-d35-self-identity-declaration-and-repair); [The gate's protections for founder workstreams depend on accepted company-brief ](05-EXPECTED-VS-ACTUAL.md#l1-company-brief-gate-dependence)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S02.U1** | Rohit's org (and design partners) on a non-expiring internal plan | — | orgs row for <ORG> shows plan_status active, plan_expires_at null, grace_until null; the next heavy tick writes an l1_sync_runs row per connection and cards_7d moves; same for Sole Mate's tenant if Rohit wants it running. | harsh | prod_action |
| **S02.U2** | Schema and deploy order | — | All 25 migrations 0191–0250 are in schema_migrations, 0210's constraints list eleven reasons, default_transaction_read_only is off; the dashboard is deployed at 2edfb86 or later before or with brain 0cc8d83c; results logged in GeniOS-011 03-LOG. | harsh | prod_action |
| **S02.U3** | Switches and env for Rohit's org | — | Rohit confirms A5 (retire R-1) and D1/A4; Harsh leaves GENIOS_L4_LLM_DECISION_MAKER unset or false (or records why it stays on); founder_office domain and expert_review are active for Rohit's org via scripts/activate_tenant.py, l2_reasoning in shadow; every flip is a dated 03-LOG line with its one-line rollback. | rohit+harsh | prod_action |
| **S02.U4** | Brief accepted and self identity declared | — | Rohit accepts the drafted brief lines naming Boardy, the sampark.gov.in portal, accelerators and investors; D35 yes → declare_self_identity for his domain; repair_self_identity dry run read by Rohit → --apply; counts logged. | rohit+harsh | prod_action |
| **S02.U5** | Every sweep skip is a row, and every door asks the same gates | `genios_engine/api/routes.py`<br>`genios_engine/platform/billing.py`<br>`genios_engine/platform/quota.py`<br>`tests/api/test_a_skipped_sweep_writes_its_reason.py` | plan_expired, sync_quota, over_budget and paused each write an l1_sync_runs row with a reason (migration at the next free number if a column is needed); Sync now, POST /sync/{id} and POST /connections/{id}/backfill ask the same gate function or are exempted in one named place; a resync's quota bypass is an explicit logged decision; tests plus a mutation that removes the row write. | claude | code |

<a id="s03"></a>
### S03 · Stop red code reaching production

- **Why:** Every harsh/mvp push from 6 Sep to 21 Oct was red, nothing protects the branch, the deploy host builds on its own, and the live SHA cannot be read from outside. Without these gates every later fix can regress in production unseen.
- **Layers:** Process · **group:** B-gates · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U2/U3 need repo admin rights (Rohit or Harsh); U4 needs Harsh to add a read-only DB secret.
- **Items it closes:** [Nothing stops a push or merge to the production branch while CI is red](05-EXPECTED-VS-ACTUAL.md#process-prod-branch-unprotected-red-ci-ships); [The deploy host builds production on its own; no CI job deploys, and no deploy w](05-EXPECTED-VS-ACTUAL.md#process-deploy-not-gated-on-ci); [Which commit production runs cannot be read from outside](05-EXPECTED-VS-ACTUAL.md#process-live-sha-not-observable); [Code reached the production branch while CI was red (4, 9, 11, 21 Oct), and 199 ](01-WHAT-WENT-WRONG.md#process-red-ci-reached-production); [Two writers on two branches: harsh/mvp is 42 commits ahead of speedrun008, and H](05-EXPECTED-VS-ACTUAL.md#process-two-branches-drift-and-undocumented-prod-commits); [Who pushes changed several times (Rohit, then Claude, then classifier-denied, th](01-WHAT-WENT-WRONG.md#process-push-ownership-flip-flop); [The production repository is public and carries Rohit's personal address, the pr](06-DECISIONS.md#process-repo-is-public-with-real-data)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S03.U1** | /health names the build SHA and the schema head | `genios_engine/api/routes.py`<br>`tests/api/test_health_names_build_sha_and_schema_head.py` | GET /health returns build_sha (GENIOS_BUILD_SHA, 'dev' when unset) and schema_head (latest schema_migrations filename, null when the read fails, never raising); the degraded shape keeps both keys; hermetic test plus a mutation that drops either key turns it red. | claude | code |
| **S03.U2** | Branch protection and green-only deploys | — | harsh/mvp and speedrun008 are protected (required checks test, database, golden-pg; branch up to date; no force push); DO auto-deploy is off or bound to a branch that only fast-forwards to green SHAs; DO binds the commit hash into GENIOS_BUILD_SHA; /health on production shows a SHA whose CI run is green. | rohit+harsh | prod_action |
| **S03.U3** | One branch, one push owner, repository visibility | — | speedrun008 is fast-forwarded to origin/harsh/mvp; GeniOS-011 00-START-HERE states the rule (all code lands on speedrun008 through green CI; harsh/mvp only fast-forwards to a green speedrun008 SHA); the push owner is fixed (or a Bash permission rule allows fast-forward pushes to speedrun008); the default branch is moved off main; Rohit decides public vs private (and a CI-annotation token if private). | rohit+harsh | decision |
| **S03.U4** | Post-deploy health job | `.github/workflows/post-deploy.yml` | A workflow_run on a green ci (or manual dispatch) runs scripts/pipeline_health.py --json read-only against a repo secret, uploads the JSON as an artifact, and a next-day run uses --require-data; a failing run blocks the release gate (S05.U3). | claude | code |

<a id="s04"></a>
### S04 · Fast CI and the Rule 3 guards

- **Why:** CI takes about 1.5 h per push with no cancel, and the three guards GeniOS-008 Rule 3 requires do not exist (the nearest ratchet covers 5 INSERT modules, not the 9 writers, and is not shrink-only). The dashboard has no CI at all.
- **Layers:** Process · **group:** B-gates · **depends on:** nothing · **Claude can start now:** yes
- **Items it closes:** [CI takes 1.5 h per push and has no concurrency cancel](05-EXPECTED-VS-ACTUAL.md#process-ci-slow-no-concurrency); [The Next.js dashboard has no CI on push](05-EXPECTED-VS-ACTUAL.md#process-dashboard-has-no-ci); [CI structure itself is now right: production's Python, real Postgres, no silent ](05-EXPECTED-VS-ACTUAL.md#process-ci-structure-sound); [The three CI guards GeniOS-008 requires (card guard, situation-writer ratchet, m](05-EXPECTED-VS-ACTUAL.md#process-rule3-ci-guards-not-built); [The 9 sweep writers that form situations before reasoning are all live, and the ](05-EXPECTED-VS-ACTUAL.md#l3-nine-situation-writers-and-missing-ratchet); [Local QA runs on Python 3.13, and tests seeded with fixed dates passed locally b](01-WHAT-WENT-WRONG.md#process-python-and-calendar-time-bombs); [About half of the dashboard source is unreachable, and the repo has no test runn](05-EXPECTED-VS-ACTUAL.md#surfaces-dead-code-and-no-tests)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S04.U1** | Rule 3 guards: situation writers only shrink; model sites stay in their layer | `tests/test_rule3_situation_writers_only_shrink.py`<br>`tests/test_rule3_model_sites_stay_in_their_layer.py` | An AST guard (qualified calls, not text) pins the nine writers (refresh_situations, age_uncorrelated_situations, refresh_support_situations, refresh_state_situations via support_situations._upsert, refresh_period_situations, refresh_channel_touch_situations, refresh_document_situations, refresh_situation_importance, apply_lifecycle) and fails on any new create/refresh call or INSERT/UPDATE of context_situations elsewhere and when the count grows; a placement guard maps every model site in tests/replays/harness.SITE_MARKERS plus the metering register to its allowed package per 00-ARCHITECTURE, with context/ detect_resolutions declared as the one shrinking exception; each guard has a planted-violation negative control that turns it red. | claude | code |
| **S04.U2** | CI fast: concurrency, timeouts, shards | `.github/workflows/ci.yml` | Concurrency group per ref with cancel-in-progress; timeout-minutes on every job; database and golden-pg sharded (pytest-xdist or a matrix); the hermetic job runs only import/no-DB guards; scripts/qa/database_skips.py still enforced; one push shows the new wall time with all jobs green. | claude | code |
| **S04.U3** | No fixed calendar date against the wall clock | `tests/test_no_fixed_date_against_wall_clock.py` | An AST guard flags a test that seeds a literal date and compares it with a now()-relative window; current offenders are fixed or listed with a dated reason; CI runs it on Python 3.11. | claude | code |
| **S04.U4** | Dashboard web CI, reader tests and the dead-file sweep | `(dashboard repo) .github/workflows/web-ci.yml`<br>`(dashboard repo) src/lib/card-read.test.ts`<br>`(dashboard repo) package.json` | On push and PR the dashboard runs npm ci, tsc --noEmit, next lint and next build; vitest covers lib/card-read.ts and the live.ts mappers; the 116 unreachable files are listed for Rohit and deleted in one reviewed commit. | claude | code |

<a id="s05"></a>
### S05 · Daily production card health, switch state and the release gate

- **Why:** Nothing measures production card volume or quality daily, about 20 switches decide the card path and none is visible, and the database hit its 500 MB tier twice in 17 days. A release gate needs all three.
- **Layers:** Process, Cross-layer · **group:** B-gates · **depends on:** S03, S01 · **Claude can start now:** yes
- **Blocked on:** U3 needs S03.U1 (SHA on /health) and S07 scorecards; U4 needs Rohit's approval of the dummy.
- **Items it closes:** [Nothing measures production card volume or quality daily; the health tools exist](05-EXPECTED-VS-ACTUAL.md#process-no-daily-production-card-health); [About 20 switches decide the card path; code flips some itself, and their produc](05-EXPECTED-VS-ACTUAL.md#process-switch-state-invisible); [There is no release gate for a 'fully functional' product](05-EXPECTED-VS-ACTUAL.md#process-release-gate-missing); [No plan budgeted the 500 MB database tier, and production reached 999 MB before ](01-WHAT-WENT-WRONG.md#cross-db-tier-never-budgeted)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S05.U1** | One health row per org per day, with alerts | `genios_engine/platform/daily_health.py`<br>`migrations/<next free, >=0251>_daily_health.sql`<br>`genios_engine/platform/scheduler.py`<br>`tests/platform/test_daily_health_pg.py` | Once a day per org a row holds cards by builder_version/output_lane, card_refusals by rule, expert_reviews/reasoning_results/l2_admissions by status, the funnel's five numbers, LLM failure and truncation counts, and database size; ops_alert fires when cards per day fall below half the 14-day median, when a lane is NO DATA for 24 h, or when DB size passes a ceiling; PG test plus a mutation of the threshold. | claude | code |
| **S05.U2** | Staff live-state route | `genios_engine/api/admin_routes.py`<br>`tests/api/test_admin_live_state.py` | Staff-only GET /admin/live-state/{org} returns every l1_semantic/l2_v2/l3/l4 activation row (live and stamped off), the env flags as set/unset (never values of secrets), the deployed SHA and the schema head; test. | claude | code |
| **S05.U3** | scripts/release_gate.py | `scripts/release_gate.py`<br>`tests/scripts/test_release_gate.py` | Exits 0 only if the CI run for the SHA is green (GitHub API), committed scorecards cover every model site whose prompt hash changed since the last release, /health's SHA matches, and the next day's pipeline_health --require-data plus the card-volume band pass on the canary org; one failing-case test per condition. | claude | code |
| **S05.U4** | Admin 'Health' and 'Switches' tabs (dummy first) | `(dashboard repo) src/app/dashboard/admin/` | Rohit approves a clickable dummy; then the tabs show the 30-day health chart and the live-state route. | claude | ui_dummy |

<a id="s06"></a>
### S06 · L1: the junk filter filters, and a body we did not get is never passed off as the body

- **Why:** An llm_junk archive is re-admitted on every heartbeat and extracted from its list snippet without the gate, so marketing snippets become claims; a refused Gmail full fetch silently becomes the snippet; promotion reads only the snippet; archived text leaks to membership readers.
- **Layers:** L1 · **group:** C-L1 · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U4 needs production and Rohit's read of the list.
- **Items it closes:** [A mail the junk filter archived as llm_junk is re-admitted on every heartbeat an](05-EXPECTED-VS-ACTUAL.md#l1-junk-verdict-readmitted-on-snippet); [A failed or refused per-message Gmail fetch silently falls back to the list snip](05-EXPECTED-VS-ACTUAL.md#l1-gmail-full-fetch-failure-silent); [YC-II D23 + B27/F58: promoting Boardy's archived intros (pending Rohit's list re](05-EXPECTED-VS-ACTUAL.md#l1-d23-b27-promoted-archive-reads-only-the-snippet); [Giving archived mail its text exposed it to every reader that selects by thread ](01-WHAT-WENT-WRONG.md#l1-archive-text-exposed-by-membership)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S06.U1** | A junk archive is re-judged, never re-admitted on its snippet | `genios_engine/capture/parked/drain.py`<br>`genios_engine/capture/landing/unread.py`<br>`genios_engine/capture/gate/gate.py`<br>`tests/capture/test_a_junk_archive_is_rejudged_not_readmitted.py` | drain_parked no longer flips an llm_junk archive to emitted/needs_extraction unless the gate version recorded with the verdict differs from the current one; when it does, the mail is full-fetched and the current S2 gate runs (the re-read S2 skip at gate.py:166-179 does not apply to it); an archive with no recorded version stays archived; llm_junk_unconfident's rule is stated in the test; test on the drain → re-read path plus a mutation restoring the bypass turns it red. | claude | code |
| **S06.U2** | A refused Gmail fetch is said, retried once, then parked; promotion re-fetches | `genios_engine/capture/connectors/composio.py`<br>`genios_engine/capture/acquire/sync_runner.py`<br>`scripts/promote_archived.py`<br>`tests/capture/connectors/test_a_failed_full_fetch_is_not_the_body.py` | fetch_content passes raise_if_refused; Gmail _execute has a hard deadline like ComposioExec; a keeper's failed full fetch retries once, then parks NEEDS_REFETCH (or sets raw['body_fetch']='failed', which extraction refuses); the count is in SyncSummary and l1_sync_runs; promote_archived re-fetches the body through the connector before reading (B27); tests plus mutations. | claude | code |
| **S06.U3** | Every membership reader asks the event's outcome | `genios_engine/context/lifecycle/store.py`<br>`genios_engine/context/situation_bso.py`<br>`genios_engine/context/document_register.py`<br>`genios_engine/feedback/org_rule_ingest.py` | Each reader that selects by thread membership excludes an archived event's words; one PG test per reader with an archived member; card_builder and backfill are fixed in S34/S14 by their owners. | claude | code |
| **S06.U4** | Promote Boardy's archived intros (D23) | — | After U2 ships, promote_archived --rule N-02 --sender-domain boardy.ai dry run → Rohit reads ids/dates → --apply; counts logged in 03-LOG. | rohit+harsh | prod_action |

<a id="s07"></a>
### S07 · Real-model measurement: fix the harness, then capped live passes

- **Why:** Every golden answer is pre-authored (F5); no L1 site, R-9, or R-7 on production's prompt and Sonnet 5 has a live pass, and the 19 Oct junk-gate rewrite shipped on ideal-reader recordings. golden_eval would ask Haiku for R-9. Switch decisions need a real-model board.
- **Layers:** Process, L1, L2 · **group:** A-measure · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U2–U4: Rohit's key and a yes on spend (D65 is ≈$2 from its cap).
- **Items it closes:** [A live R-9 pass through golden_eval would ask Haiku instead of production's Sonn](05-EXPECTED-VS-ACTUAL.md#process-golden-eval-r9-wrong-model); [No Layer 1 model site has been measured on a real model; the B2 prompt change sh](05-EXPECTED-VS-ACTUAL.md#l1-b1-live-pass-never-run); [GeniOS-008 C1 + YC-II D29/B26 (+F18): L1's model calls were never measured on a ](05-EXPECTED-VS-ACTUAL.md#l1-c1-d29-live-junk-filter-never-measured); [The L1 junk-gate prompt was rewritten and shipped to production on ideal-reader ](01-WHAT-WENT-WRONG.md#l1-junk-gate-prompt-shipped-on-ideal-reader); [The card-making model sites have never been measured on production's models; eve](05-EXPECTED-VS-ACTUAL.md#process-no-real-model-pass-on-card-sites); [Every gate, board and switch rule was proven with the ideal reader; the real mod](01-WHAT-WENT-WRONG.md#process-verified-with-the-ideal-reader-only); [YC-II D72, D73 + F267–F269, s13b-D8: whether R-7 / the brief drafter should thin](05-EXPECTED-VS-ACTUAL.md#l2-d72-d73-thinking-and-live-eval-budget); [YC-II D12a: all 67 golden cases are labelled by Claude; Rohit has labelled none](06-DECISIONS.md#process-d12a-golden-labels-all-by-claude)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S07.U1** | golden_eval asks R-9 on its production tier and takes the L2 path | `scripts/golden_eval.py`<br>`tests/scripts/test_golden_eval_asks_r9_on_its_tier.py` | SITE_TIERS gains reason_l2 → R-9; model_for('reason_l2') returns claude-sonnet-5 with R-9's site settings (thinking off, 8,000 ceiling); --l2-path sets GENIOS_GOLDEN_L2=1; a --probe mode makes at most 2 live calls and prints stop_reason and output_tokens before any pass; a dry-run test asserts model and settings with no key; mutation removing the SITE_TIERS entry turns it red. | claude | code |
| **S07.U2** | Live key, capped budget and label review | — | GENIOS_GOLDEN_LIVE_KEY is set; Rohit approves caps (L1 ≈$1.02, R-7 D72 two arms ≤$7, R-9 a stated cap); Rohit reviews the labels of the 4 failing and the investor/programme cases (D12a). | rohit | paid_run |
| **S07.U3** | L1 live pass: junk_gate_batch, relevance, extraction on Haiku | — | 1–2 probe calls first; scorecards committed under speedrun008/GeniOS-011/scores/; each case's keep/drop compared with its label; RESCUE_AT and DROP_BELOW_RELEVANCE set from the measurement or recorded unchanged with the number; F18/D29 data put to Rohit. | claude | paid_run |
| **S07.U4** | R-7 on claude-sonnet-5 (D72) and R-9 live pass | — | Scorecards for both sites committed with held share, recall, precision, forbidden outputs and cost; GeniOS-011 rules record that the real-model board, not the ideal reader, is the switch rule. | claude | paid_run |

<a id="s08"></a>
### S08 · L1: the gate sees who wrote; the second mailbox; Indian public mail hosts

- **Why:** The gate asks 'is a specific human writing?' without the sender, so strangers (investors, a fund's round notice F18) are judged blind; <founder company mailbox> is not captured, so 'you never replied' can be false; Indian public hosts mint company nodes.
- **Layers:** L1 · **group:** C-L1 · **depends on:** S07, S06 · **Claude can start now:** no
- **Blocked on:** U1 is measured only with the live key (S07); U2 needs Rohit's yes on the hosts; U3 needs Rohit and Harsh.
- **Items it closes:** [The junk gate asks 'is a specific human writing?' but never sees who sent the ma](05-EXPECTED-VS-ACTUAL.md#l1-gate-judges-without-sender); [YC-II F263 (S18-X13): Indian public mail hosts are missing from the public-host ](06-DECISIONS.md#l1-f263-indian-public-mail-hosts); [The founder's second mailbox (<founder company mailbox>) is not connected, so 'y](05-EXPECTED-VS-ACTUAL.md#l1-r3-second-mailbox); [GeniOS-008 C2: <founder company mailbox> as a second (seat) mailbox, default yes](05-EXPECTED-VS-ACTUAL.md#l1-c2-second-mailbox)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S08.U1** | Each gate item carries sender name, domain, reply-to-us and attachment | `genios_engine/capture/gate/relevance.py`<br>`tests/capture/test_the_gate_sees_who_wrote.py` | Each fenced item carries display name and domain (never the full address), is_reply_to_us from In-Reply-To/References against our sent ids, and has_attachment; gate cassettes re-recorded; the effect measured by re-running S07.U3, with F18 and an unfamiliar-domain investor case kept. | claude | code |
| **S08.U2** | Indian public hosts in the one canonical list | `genios_engine/capture/validate/canonical.py`<br>`genios_engine/capture/pipeline.py`<br>`tests/capture/test_indian_public_hosts_are_not_companies.py` | After Rohit approves the six hosts they are in CONSUMER_EMAIL_DOMAINS; capture/pipeline._FREE_MAIL is folded into it or retired; Harsh's merge/retire dry run lists existing company nodes minted from them. | claude | code |
| **S08.U3** | Connect <founder company mailbox> as a seat; coverage names what is not connected | — | Rohit says yes (R3/C2); Harsh connects it as a seat connection and l1_sync_runs shows its runs; coverage names brief-listed addresses that are not connected. | rohit+harsh | prod_action |

<a id="s09"></a>
### S09 · L1: the history window the founder picks, and the resync

- **Why:** Capture still uses 60 days although the dashboard offers 365 (the stored choice is read by nothing); mail the old gate deleted and July's investor threads are outside memory; refused attachments, noise filed by the old replay, and historical business facts (thread.objective, which the goal drafter reads) need production runs.
- **Layers:** L1, L3, Goals · **group:** C-L1 · **depends on:** S02, S14 · **Claude can start now:** yes
- **Blocked on:** U3 Rohit; U4 Harsh in production after the brief is accepted (D26) and after S14's rebuild fixes.
- **Items it closes:** [Mail the old gate deleted, and anything older than 60 days, stay outside memory ](05-EXPECTED-VS-ACTUAL.md#l1-resync-and-history-window); [GeniOS-008 C3 / YC-II D5, D16, D26: the history window is still 60 days in code;](05-EXPECTED-VS-ACTUAL.md#l1-c3-d16-history-window-still-60-days); [The old gate deleted mail content (258 S1 drops). The fix shipped, but the re-sy](01-WHAT-WENT-WRONG.md#l1-deleted-mail-needs-resync); [Whether the attachments refused since 3 Oct were requeued after the deploy is un](05-EXPECTED-VS-ACTUAL.md#l1-h4-refused-attachments-requeue); [The history replay filed mail the live drain had called noise (newsletters, out-](01-WHAT-WENT-WRONG.md#l3-replay-filed-noise); [Historical mail never got its business facts (thread.objective, party.role): bac](05-EXPECTED-VS-ACTUAL.md#goals-thread-objective-history-missing)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S09.U1** | The window the founder picks is the window captured | `genios_engine/capture/connectors/backfill.py`<br>`genios_engine/capture/coverage/window.py`<br>`genios_engine/api/account_routes.py`<br>`tests/capture/test_the_chosen_backfill_window_is_used.py` | integration_preferences.sync_settings.historical_backfill is written through to connections.capture_scope.backfill_days (or the dashboard calls PATCH backfill-window); picking 12 months yields 365; the resync reserves or bypasses the ingestion quota by an explicit logged decision; test plus mutation. | claude | code |
| **S09.U2** | Business-facts backfill runner | `scripts/backfill_business_facts.py`<br>`tests/scripts/test_backfill_business_facts.py` | Dry run prints per-field counts (thread.objective, party.role) it would write; --apply needs GENIOS_ALLOW_PROD_WRITE=1; it calls context backfill_business_facts; context_health no longer declares it UNREACHED. | claude | code |
| **S09.U3** | History window decision (D16, 365 recommended) | — | Rohit's number is recorded in GeniOS-011 03-LOG. | rohit | decision |
| **S09.U4** | Resync, requeue and re-file in production | — | Harsh PATCHes Gmail and Calendar windows; resync_deleted_mail --days N dry run → Rohit reads → --apply; requeue_refused_attachments dry → --apply; the F101 noise count; after S14 lands, rebuild_graph then situations/backfill?rebuild=true; the business-facts runner dry → apply; every count logged. | harsh | prod_action |

<a id="s10"></a>
### S10 · L1: refusals and skips the founder can see; one chain for Sync now

- **Why:** A failed or partial sync is a log line nobody sees; time_inferred lives only in logs; 'Sync now' runs a second copy of the chain with no funnel rows, no post-passes and none of the sweep's gates, so production card volume cannot be measured from one source.
- **Layers:** L1, Cross-layer, Surfaces · **group:** C-L1 · **depends on:** S02, S03 · **Claude can start now:** yes
- **Blocked on:** U1/U2 wait for S02.U5 and S03.U1 to release api/routes.py (one writer per file).
- **Items it closes:** [A failed or partial sync is recorded but the founder never sees it; the ops aler](05-EXPECTED-VS-ACTUAL.md#l1-refusal-and-coverage-invisible); [A3's count of mail with an inferred timestamp lives only in a log line, not in l](05-EXPECTED-VS-ACTUAL.md#l1-time-inferred-not-ledgered); ['Sync now' runs a second copy of the chain: no funnel numbers, no meeting/team/v](05-EXPECTED-VS-ACTUAL.md#cross-sync-now-runs-a-second-chain)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S10.U1** | l1_sync_runs carries time_inferred; a per-connection status read | `migrations/<next free>_l1_sync_runs_time_inferred.sql`<br>`genios_engine/api/routes.py`<br>`tests/api/test_connection_status_says_last_run.py` | time_inferred is a column named in the insert; a per-connection status endpoint returns last run, finished or truncated, scanned vs claimed_total, archived, error and coverage-window state; test plus mutation. | claude | code |
| **S10.U2** | Sync now runs the sweep's chain | `genios_engine/api/routes.py`<br>`tests/api/test_sync_now_and_sweep_run_one_chain.py` | The Sync job calls the same chain body as _run_l2_chain with its progress hooks as parameters; both doors write card_delivered funnel rows, run the team/verify/meetings post-passes and ask the same plan/quota gates; test. | claude | code |
| **S10.U3** | Sources page per-connection line (dummy first) | `(dashboard repo) src/components/sources/` | Rohit approves a dummy; then the Sources page shows last run, read N of about M, archived and the error per connection. | claude | ui_dummy |
| **S10.U4** | Ops alert webhook | — | Harsh sets GENIOS_OPS_ALERT_WEBHOOK in production and one test alert arrives. | harsh | prod_action |

<a id="s11"></a>
### S11 · L1 connector hardening: pin Composio, key Gmail on historyId

- **Why:** An unannounced toolkit change refused 88/88 attachment fetches on 3 Oct and the skip flag is still on; Gmail incremental sync keys on a date.
- **Layers:** L1 · **group:** C-L1 · **depends on:** S06, S01 · **Claude can start now:** no
- **Blocked on:** Harsh's versions and fixtures (U1); composio.py is owned by S06.U2 first.
- **Items it closes:** [Composio toolkit versions are still unpinned (dangerously_skip_version_check=Tru](05-EXPECTED-VS-ACTUAL.md#l1-h3-composio-toolkit-unpinned); [L1 H3: Composio toolkit versions are still unpinned (dangerously_skip_version_ch](05-EXPECTED-VS-ACTUAL.md#l1-h3-composio-toolkits-unpinned); [Gmail incremental sync keys on a date, not historyId (A4)](05-EXPECTED-VS-ACTUAL.md#l1-a4-gmail-historyid-cursor); [L1 H2 → A4: the Gmail cursor is still a day-granular date; the live historyId fi](05-EXPECTED-VS-ACTUAL.md#l1-h2-a4-gmail-history-cursor)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S11.U1** | Production toolkit versions and live history fixtures | `tests/capture/connectors/fixtures/gmail_history_live.json`<br>`tests/capture/connectors/fixtures/gmail_history_expired_404.json` | Harsh reports the toolkit versions the production SDK resolves for gmail, googlecalendar and googledrive, and saves one redacted GMAIL_LIST_HISTORY response and one expired-historyId 404 as fixtures. | harsh | prod_action |
| **S11.U2** | Pin toolkit versions and refuse the skip flag | `genios_engine/capture/connectors/composio.py`<br>`genios_engine/capture/connectors/composio_base.py`<br>`tests/capture/connectors/test_composio_toolkits_are_pinned.py` | Both executors pass toolkit_versions and no dangerously_skip_version_check; a test fails if the flag returns. | claude | code |
| **S11.U3** | Gmail historyId cursor with bounded gap backfill (A4) | `genios_engine/capture/connectors/composio.py`<br>`genios_engine/capture/connectors/manifest.py`<br>`tests/capture/connectors/test_gmail_history_cursor.py` | Incremental sync keys on historyId; an expired historyId starts a bounded backfill; a saved page token is never reused with a new query; tests run against U1's fixtures. | claude | code |

<a id="s12"></a>
### S12 · L1 contract: words for the founder's workstreams (vocabulary, objects, roles, lifecycle)

- **Why:** The closed 16-type vocabulary has no word for introductions, meetings, investor interest or application status, so founder work is mistyped or lost to an unpromoted open lane; conditions, delivery links, meeting follow-ups and thread end states are not L1 objects; roles are free text; E5/E7/E10 are open decisions.
- **Layers:** L1, L2 · **group:** C-L1 · **depends on:** S07 · **Claude can start now:** no
- **Blocked on:** Rohit's choices (U1) and the live key for the extraction re-record (S07).
- **Items it closes:** [The closed 16-type signal vocabulary has no word for the founder's main workstre](05-EXPECTED-VS-ACTUAL.md#l1-signal-vocabulary-16-types); [Condition, delivery-status link, meeting follow-up link and thread end state are](05-EXPECTED-VS-ACTUAL.md#l1-e4-six-object-types); [Roles are free text: sender, promisor, owner and approver are not a closed set (](05-EXPECTED-VS-ACTUAL.md#l1-e6-closed-roles); [Absence-derived signals (no reply, no owner, no approval, no delivery) are not L](06-DECISIONS.md#l1-e5-absence-signals); [Signal lifecycle has no 'new' or 'revoked' state (E7)](06-DECISIONS.md#l1-e7-lifecycle-new-revoked); [L1 E5, E7: two of Rohit's L1 decisions are unanswered (absence as L1 signals; 'n](06-DECISIONS.md#l1-e5-e7-absence-signals-and-lifecycle-states); [Business metric definitions (what 'sales' means: booked, collected or signed) ha](06-DECISIONS.md#l1-e10-metric-definitions-owner); [GeniOS-008 C4 / L1 E10: who owns metric definitions ('sales' = booked/collected/](06-DECISIONS.md#l2-c4-e10-metric-definitions-owner)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S12.U1** | Rohit's L1 contract decisions | — | Rohit picks the kinds to add (recommended introduction, meeting, investor_interest, application_status), answers E5 (recommended: absence stays L2 tool evidence) and E7 (rule for new→active and the revoke detector), and confirms Plane D owns metric definitions (C4 default); recorded in 03-LOG. | rohit | decision |
| **S12.U2** | New signal types end to end | `genios_engine/contracts/signal.py`<br>`migrations/<next free>_signal_type_check.sql`<br>`genios_engine/context/open_lane.py`<br>`tests/contracts/test_new_signal_types_have_precedence_weight_expiry.py` | Each chosen member has ALG-16 precedence, ALG-17 weight, ALG-19 expiry, the check constraint and the pins; matching open-lane kinds are promoted; extraction re-recorded with the live key and measured. | claude | code |
| **S12.U3** | E4 objects and E6 closed roles | `genios_engine/contracts/extraction.py`<br>`genios_engine/reason/l2/dossier.py`<br>`tests/contracts/test_extraction_objects_and_roles.py` | Condition, outbound delivery-status link, meeting→follow-up link and per-thread terminal state exist in the extraction contract, each with a reader in the L2 dossier; RoleAssertion.role is a closed set; extraction re-recorded. | claude | code |
| **S12.U4** | Metric definitions in the Plane D corpus | `Domain Expertise/` | 'sales' and the other business metrics are defined in reviewed corpus YAML with a reviewer stamp, read by the compiler. | claude | code |

<a id="s13"></a>
### S13 · L1→L2 bundle and the evidence loop

- **Why:** Bundles carry only published signals and bundle.py reads extraction.entities while the field is entity_mentions, so proximity joins and G6 name-only candidates never fire; qualified_signals stores NULL for all five conversation columns (bug 8); L2's evidence needs stay open forever because fetchers are unarmed and HOLD→need is unwired.
- **Layers:** L1, L2, L3, Cross-layer · **group:** C-L1 · **depends on:** S12, S02 · **Claude can start now:** yes
- **Blocked on:** U1 can start; U2 needs Rohit; U3 needs U2 and S12; U4 needs Harsh's hand fetch.
- **Items it closes:** [The L1→L2 bundle carries only published signals, so below-floor, archived, calen](05-EXPECTED-VS-ACTUAL.md#l1-bundle-carries-only-published-signals); [Entity doubt is thrown away, and a person known only by name never joins a bundl](05-EXPECTED-VS-ACTUAL.md#l1-e3-entity-doubt-and-person-joins); [EvidenceNeed fetchers (E2) are built but not armed, so every request L2 makes fo](05-EXPECTED-VS-ACTUAL.md#l1-e2-need-fetchers-armed-off); [L2 raises evidence needs, but the fetchers are off, so no re-entry happens and n](05-EXPECTED-VS-ACTUAL.md#l2-evidence-loop-not-armed); [A HOLD raises no EvidenceNeed: needs_from_holds and resolve_hold have no product](05-EXPECTED-VS-ACTUAL.md#l3-hold-evidence-chain-unwired); [The eight live bugs of 4 Oct: six are fixed in code, one is closed by an earlier](05-EXPECTED-VS-ACTUAL.md#cross-eight-bugs-of-4-oct)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S13.U1** | Bundles see entities and keep doubt; signals keep their conversation | `genios_engine/capture/esqe/bundle.py`<br>`genios_engine/capture/esqe/publisher.py`<br>`genios_engine/capture/validate/canonical.py`<br>`tests/capture/test_bundle_reads_entity_mentions.py` | bundle.py reads entity_mentions (a regression test shows entity_keys() non-empty on a real ExtractionResult, red before the fix); CanonicalHint.alternatives and basis are carried on the mention; publisher._row_for writes thread_key, direction, turn_index, thread_depth and ball_in_court and a PG test reads them back from qualified_signals; mutations for both. | claude | code |
| **S13.U2** | Bundle road decision | — | Rohit (with the S12 vocabulary) picks (a) a bundle also carries below-floor extractions and open-lane observations as unqualified members, or (b) the L2 pass also seeds subjects from L3 files that got new events this sweep. | rohit | decision |
| **S13.U3** | Build the chosen road | `genios_engine/capture/esqe/publisher.py`<br>`genios_engine/reason/l2/inputs.py` | The chosen road is built with one golden case per road; below-floor, calendar-only and archived-metadata items can trigger an L2 judgment. | claude | code |
| **S13.U4** | Arm the fetchers and wire HOLD → EvidenceNeed → resolve | `genios_engine/reason/l2/sweep.py`<br>`genios_engine/context/hold_needs.py`<br>`genios_engine/context/hold_resolution.py`<br>`genios_engine/capture/acquire/need_fetchers.py` | Harsh runs 04-FOR-HARSH §8 steps 1–3 by hand on Rohit's org, then sets GENIOS_NEED_FETCHERS=on and confirms migration 0210; Claude wires needs_from_holds → store_needs in the L2 pass transaction and resolve_hold on the need's outcome, adds REEXTRACT from the stored payload, and shows open needs as 'waiting on' on the card; context_health stops declaring them UNREACHED. | claude+harsh | mixed |

<a id="s14"></a>
### S14 · L3: events stay in their conversation's file; a rebuild is reproducible

- **Why:** A reply can join a reading's synthetic correlation and land in no file while health checks count it filed ('no correlation'); a rebuild deletes every situation and re-mints random ids, orphaning admissions and human closes; rebuild_graph keeps stale correlations; the funnel cannot show events outside any file.
- **Layers:** L3 · **group:** D-L3 · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U2 touches api/routes.py after S03.U1/S02.U5/S10 release it.
- **Items it closes:** [Thread inheritance reads reading-declared memberships: a reply can join a readin](05-EXPECTED-VS-ACTUAL.md#l3-thread-inherits-reading-correlations); [A correlation rebuild deletes every situation (readings, human and statement clo](05-EXPECTED-VS-ACTUAL.md#l3-rebuild-deletes-situations-and-ids); [scripts/rebuild_graph.py wipes graph_* but keeps correlations, members, situatio](05-EXPECTED-VS-ACTUAL.md#l3-rebuild-graph-keeps-stale-correlations); [Many events never reach a file, silently (noise, archived/metadata-only, held, p](05-EXPECTED-VS-ACTUAL.md#l3-events-outside-any-file)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S14.U1** | Thread inheritance, backfill skip and 'filed' count use engine-owned correlations only | `genios_engine/context/correlation.py`<br>`genios_engine/context/backfill.py`<br>`genios_engine/context/workstreams.py`<br>`tests/context/test_a_reply_after_a_reading_joins_the_file_pg.py` | thread_correlations, the non-rebuild backfill skip and workstreams._NAMED_MAIL count only ids owned by context_correlations (or joined_via <> 'reading'); a PG test where a reading declared the only earlier event of a thread asserts the reply joins the counterparty's file and appears in files_for; mutation dropping the filter turns it red. | claude | code |
| **S14.U2** | Deterministic situation ids; a rebuild keeps readings and human decisions | `genios_engine/context/situations.py`<br>`genios_engine/context/periodic.py`<br>`genios_engine/context/support_situations.py`<br>`genios_engine/context/meeting_touch.py`<br>`genios_engine/context/document_register.py`<br>`genios_engine/context/backfill.py`<br>`genios_engine/api/routes.py` | situation_id derives from correlation_id (no uuid4); two rebuilds return identical ids; reading rows and rows with a human or statement resolution survive a rebuild; _replay_l2_history runs under the org lease; situations_written leaves _MOVED_KEYS so the chain runs once after a backfill; the docstring matches; PG tests plus mutation. | claude | code |
| **S14.U3** | rebuild_graph re-derives correlations; files_for reports dropped anchors | `scripts/rebuild_graph.py`<br>`genios_engine/context/workstreams.py` | After the replay, rebuild_graph calls backfill_layer2(rebuild=True) and prints its counts; files_for reports anchors it dropped instead of skipping silently; test. | claude | code |
| **S14.U4** | Events-filed numbers on the funnel | `genios_engine/context/runner.py`<br>`genios_engine/platform/funnel.py`<br>`tests/context/test_events_filed_are_counted_pg.py` | Each sweep reports events drained vs events in an engine-owned correlation, broken down by noise, metadata, held, parked and anchorless (on the sweep outcomes, not a sixth funnel stage); SITUATIONS_FORMED counts situations this sweep opened or changed; held_missing_qes_extraction is capped and reported; test. | claude | code |

<a id="s15"></a>
### S15 · L3: one counterparty, one file, one live situation; admission sees every reading

- **Why:** L2 admission sees only situations anchored on the file node, so every reading situation (awaiting reply, commitment, support, document, meeting touch, periodic) is invisible to it (P0 for G0.3); one counterparty holds many live situations (one per keyword domain), so any unnamed one HOLDs the judgment and the file falls back to the old lane ('L2 and L3 keep failing each other'); arrival order can split a counterparty into two files.
- **Layers:** L3 · **group:** D-L3 · **depends on:** S14, S01 · **Claude can start now:** no
- **Blocked on:** S14.U1 owns correlation.py/workstreams.py first; U2's design waits for S01's multiplicity reading.
- **Items it closes:** [L2 admission only sees situations anchored on the file node; every reading situa](05-EXPECTED-VS-ACTUAL.md#l3-admission-cannot-see-reading-situations); [One counterparty file holds many live situations (one per keyword domain × 45-da](05-EXPECTED-VS-ACTUAL.md#l3-one-subject-many-situations); [Anchoring depends on arrival order: a person is lifted to their company only if ](05-EXPECTED-VS-ACTUAL.md#l3-person-company-lift-order); [Identity: the exact-key law holds in identity.py, but readers join by name aroun](05-EXPECTED-VS-ACTUAL.md#l3-name-only-joins); [A situation's domain is a per-message keyword decision with an 'admin' fallback;](05-EXPECTED-VS-ACTUAL.md#l3-domain-routing-fundraising)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S15.U1** | Reading situations name the file they concern | `migrations/<next free>_situation_concerns_node.sql`<br>`genios_engine/context/outreach_situations.py`<br>`genios_engine/context/support_situations.py`<br>`genios_engine/context/meeting_touch.py`<br>`genios_engine/context/workstreams.py`<br>`tests/context/test_a_reading_reaches_its_files_admission_pg.py` | Each reading row stores concerns_node_id (from finding.concerns_node) beside its synthetic anchor; lifecycle_for(file) returns reading rows that concern the file; decide() receives them; PG test: an outreach reading on a firm is named by that firm's file admission. | claude | code |
| **S15.U2** | One live situation per file; the judgment may name sit:<id> | `genios_engine/context/correlation.py`<br>`genios_engine/context/situations.py`<br>`genios_engine/context/l2_admission.py`<br>`tests/context/test_one_counterparty_one_live_situation_pg.py` | Measured multiplicity from S01 recorded first; domain becomes an attribute rather than part of the correlation key (or a file-level admission names a primary situation); the keyword 'admin' fallback stops splitting files; the judgment can cite sit:<id> from the dossier; a test where an invite 'X <> Rohit' and an 'investor' mail from the same company yield one live situation and the L2 file review is written. | claude | code |
| **S15.U3** | Re-anchor when the company appears; names go through resolve_alias | `genios_engine/context/correlation_people.py`<br>`genios_engine/context/pipeline.py`<br>`tests/context/test_a_person_lifts_to_a_company_that_arrives_later_pg.py` | An incremental re-anchor runs when a person's company node appears; load_directory excludes contended aliases; _business_subject goes through resolve_alias; the stale same-name comment is corrected; PG tests. | claude | code |

<a id="s16"></a>
### S16 · L3: memory holds what was said (promises, quotes, snapshot)

- **Why:** Undated and conditional promises never become commitments, so the dossier says 'No promise was found'; signal-type observations quote a bare name and cards narrate it as speech; the snapshot L2 reads has no as-of, unknowns or contradictions.
- **Layers:** L3, L2 · **group:** D-L3 · **depends on:** nothing · **Claude can start now:** yes
- **Items it closes:** [YC-II F165: an undated or conditional promise in mail never becomes a commitment](05-EXPECTED-VS-ACTUAL.md#l3-f165-undated-and-conditional-promises-never-enter-memory); [Signal-type observations take the extraction's first span as their 'quote', ofte](01-WHAT-WENT-WRONG.md#l3-signal-type-observation-quotes-a-name); [The bounded snapshot L2 reads has no as-of in use, no unknowns or contradictions](05-EXPECTED-VS-ACTUAL.md#l3-bounded-snapshot-incomplete)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S16.U1** | Every promise enters memory | `genios_engine/context/pipeline.py`<br>`tests/context/test_every_promise_enters_memory_pg.py` | A commitment node is written for every extracted promise: undated → no due fact; conditional → commitment.condition fact and status conditional; the L2/expert dossier lists them; affected ideal-reader cases re-recorded; mutation of the old `if subj and (due or transcript_mode)` condition turns it red. | claude | code |
| **S16.U2** | A marker is not a quote | `genios_engine/context/qes_adapter.py`<br>`tests/replays/test_no_quote_is_a_bare_name.py` | Signal-type observations carry no evidence span (or the signal's own span); a golden check fails when any card quote equals a bare name; F25/F51 re-read. | claude | code |
| **S16.U3** | The snapshot has an as-of, unknowns and contradictions | `genios_engine/reason/l2/snapshot.py`<br>`tests/reason/l2/test_snapshot_as_of_and_unknowns.py` | read_snapshot passes as_of=eval_time; the view adds typed absences and contradictions (discrepancies, signal_conflicts); ReadRequest.visibility is applied or deleted; tests. | claude | code |

<a id="s17"></a>
### S17 · L3 hygiene: failures visible, no every-sweep rewrites, layer names, one authority scale

- **Why:** A failed L3 pass is an INFO line and the first derived pass can take six passes down; L3 still calls a model and rewrites every situation row each sweep; stages log under the old layer numbers; authority_rank mixes a 0–6 ladder with 100.
- **Layers:** L3 · **group:** D-L3 · **depends on:** S14 · **Claude can start now:** yes
- **Blocked on:** U4 Rohit and Harsh; U2/U3 wait for S14 owners of situations.py and routes.py.
- **Items it closes:** [L3 still calls a model every sweep (resolution detection) and still recomputes c](05-EXPECTED-VS-ACTUAL.md#l3-model-call-and-clock-values-in-l3); [A failed L3 pass now appears in the sweep's return but only in an INFO log line,](05-EXPECTED-VS-ACTUAL.md#l3-failed-pass-visibility); [The chain's stage names and loggers still use the old layer numbering: L3 work i](05-EXPECTED-VS-ACTUAL.md#l3-layer-names-in-code); [graph_facts.authority_rank holds a 0-6 ladder and a derived default of 100 in th](01-WHAT-WENT-WRONG.md#l3-two-authority-scales)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S17.U1** | One boundary per pass; failed passes reach the funnel and ops_alert | `genios_engine/context/runner.py`<br>`tests/context/test_a_failed_pass_is_not_a_quiet_sweep.py` | compute_derived and compute_deal_view are wrapped individually; failed_passes is written to the sweep outcomes / daily health and sent to ops_alert; test with a planted failure. | claude | code |
| **S17.U2** | Write only what moved; clock values become L2 tools | `genios_engine/context/situations.py`<br>`genios_engine/context/situation_bso.py`<br>`genios_engine/reason/l2/tools.py` | Situation upserts and the importance UPDATE are guarded by value-moved (an unchanged sweep writes 0 situation rows, asserted); days-waiting and ages are computed in L2 tools; resolution detection's move into L2 (L2-12) is drawn as a unit in 03-LOG. | claude | code |
| **S17.U3** | Stage and logger names in the GeniOS-008 layers | `genios_engine/api/routes.py`<br>`genios_engine/platform/stage_timer.py` | stage('l2.process_pending') becomes the L3 name, run_all is staged as L2, context passes log as L3, with old aliases kept where alerts depend on them; test. | claude | code |
| **S17.U4** | One authority scale (R16/R17, H9) | — | Rohit decides R16/R17; Harsh runs the H9 read; Claude builds the chosen remap of rank-100 rows. | rohit+harsh | decision |

<a id="s18"></a>
### S18 · L2: a judged file is never lost silently

- **Why:** A valid expert/L2 judgment makes no card unless L3 already filed a situation in an activated domain ('general' is dark), the shared 7-a-day cap is spent by formula situations before judged files get a turn, l2_cards without l2_reasoning leaves moved files unjudged, one oversized prompt stops the whole expert pass, and every skip is a log line Rohit never sees. This is the most direct cause of 'L2 and L3 fail each other' and 'fewer cards'.
- **Layers:** L2, Cross-layer · **group:** E-L2 · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U4 waits for U1 (same file), S15.U1 and the D1 decision in S23 for the founder_office default.
- **Items it closes:** [A valid expert/L2 judgment makes no card unless L3 already filed a situation on ](05-EXPECTED-VS-ACTUAL.md#l2-l3-binding-no-situation-no-card); [The shared 7-per-day signal cap is spent by formula situations before the expert](05-EXPECTED-VS-ACTUAL.md#l2-daily-cap-formula-first); [Nearly every skip, refusal, budget cap or shadow decision is invisible to Rohit ](05-EXPECTED-VS-ACTUAL.md#l2-skips-invisible); [With l2_cards on but l2_reasoning off (or no R-9 client), nobody judges a moved ](05-EXPECTED-VS-ACTUAL.md#l2-cards-precondition-not-enforced); [The expert pass still stops entirely on a per-call budget refusal (the L2 pass w](05-EXPECTED-VS-ACTUAL.md#l2-r7-per-call-refusal-stops-pass)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S18.U1** | Judged files are decided before the formula spends the day, and every no-card reason is counted | `genios_engine/reason/domain_shadow.py`<br>`tests/reason/test_a_judged_file_is_decided_before_the_formula_spends_the_day.py` | Covered expert/L2 files are decided before the situation loop (or from an allowance of their own); covered_without_situation, expert_no_tenant_pack, expert_shadow and budget_exhausted are counted on the sweep outcomes beside no_capability and each logs at WARNING with file id and reason; PG test: 7 formula situations emitted, then 1 expert file → the expert card exists; mutation moving the file decisions back after the loop turns it red. | claude | code |
| **S18.U2** | The expert pass still reviews when L2 cannot; one oversized file is that file's problem | `genios_engine/reason/expert/sweep.py`<br>`tests/reason/expert/test_the_expert_pass_still_reviews_when_l2_cannot.py` | l2_judges = l2_cards AND l2_reasoning AND a buildable R-9 client, else R-7 reviews as before and logs a WARNING; a per-call OVER_BUDGET (REASON_PER_CALL) carries that file and continues while the daily cap still stops the pass; the skipped reason is always logged; tests: l2_cards on with l2_reasoning off → R-7 runs; an oversized file between two small ones → both small files reviewed; mutations for both. | claude | code |
| **S18.U3** | Why-no-card counts reach operators and the file page | `genios_engine/reason/runner.py`<br>`scripts/pipeline_health.py`<br>`genios_engine/api/workstream_routes.py`<br>`tests/reason/test_run_all_counts_why_no_card.py` | run_all returns and logs judged, held, refused, truncated, carried_budget, fell_back, covered_not_carded and budget_exhausted per sweep (fed into S05's daily row); pipeline_health reads reasoning_results and l2_admissions; GET /v1/workstreams/{file_id} carries a one-line 'why no card'; tests. | claude | code |
| **S18.U4** | Bind a covered file's decision to the file itself | `genios_engine/reason/domain_shadow.py`<br>`genios_engine/context/domain_silence.py` | A covered file with no home situation decides on its own node, with the pack from its work kind and a founder_office/admin default for founder work; the 'general' census named by DARK_DOMAINS is run on the golden tenant and recorded; covered_without_situation and expert_shadow fall to 0 on the golden board without losing a must-abstain case. | claude | code |

<a id="s19"></a>
### S19 · L2: what the judgment proposes is written; a failed judgment keeps the last good review

- **Why:** Under l2_cards no kind-of-work proposal is ever written, so unlisted files never gain a playbook; a refused, truncated or held judgment hands the file back to the formula lanes and is never retried.
- **Layers:** L2 · **group:** E-L2 · **depends on:** S18, S20 · **Claude can start now:** yes
- **Blocked on:** U2 needs S20's repair call and S18.U2 (expert/sweep.py) first; U1 can start once reason/l2/sweep.py is free.
- **Items it closes:** [When a judgment fails or is held, the file falls back to the formula/pack lanes;](05-EXPECTED-VS-ACTUAL.md#l2-fallback-to-formula-lanes); [Under l2_cards no 'kind of work' proposal is ever written, so unlisted files nev](05-EXPECTED-VS-ACTUAL.md#l2-kind-proposals-lost-under-l2-cards); [On the L2 card path, the model is asked for proposed_kind but nothing writes it,](05-EXPECTED-VS-ACTUAL.md#l2-path-drops-kind-proposals)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S19.U1** | Kind proposals on the L2 path | `genios_engine/reason/l2/sweep.py`<br>`tests/reason/l2/test_l2_cards_writes_kind_proposals_pg.py` | For an admitted file result whose review.proposed_kind stands the check, kind_proposal.propose_kind runs inside the write step; PG test under l2_cards shows a brief proposal; mutation removing the call turns it red; the goal proposer (S29) is wired the same way. | claude | code |
| **S19.U2** | Keep cover from the last valid review; retry truncated; repair refused | `genios_engine/reason/expert/sweep.py`<br>`genios_engine/reason/expert/store.py`<br>`genios_engine/reason/l2/store.py` | A file stays covered by its last valid review (shown 'as of <date>') when the new one fails; a truncated answer retries once at a larger ceiling; a refused answer gets one repair with the verdicts; 'fell back' is counted per sweep; tests plus mutation. | claude | code |

<a id="s20"></a>
### S20 · STEP-13b decision, the claim check, and held cards in the founder's words

- **Why:** Held cards read as engineer sentences ('We held the one we found: a fact your move rests on quotes nothing…'); since 21 Oct an overdue move, an 'unknown' confidence or an unnamed decider becomes a held question; a move resting on Rohit's confirmed answer gets no card. The only fix measured on a real model (STEP-13b: held 79% → 18.5% on Haiku) sits on unpushed local branches and collides on migration 0250.
- **Layers:** L2, Process · **group:** E-L2 · **depends on:** S07 · **Claude can start now:** no
- **Blocked on:** Rohit's STEP-13b decision (U1) comes first because U3/U4 edit the same files STEP-13b changes; the before/after is measured with S07's real-model pass.
- **Items it closes:** [The only expert pass that met its live target (STEP-13b ladder) exists only on l](06-DECISIONS.md#process-step13b-ladder-left-unpushed); [YC-II D63/D64 (STEP-13b): the GeniOS Engine in the expert's hands was built but ](06-DECISIONS.md#l2-step13b-built-on-local-branches-never-merged); [STEP-13b claim-check fixes (79% → 18.5% held on Haiku) never reached production;](05-EXPECTED-VS-ACTUAL.md#l2-step13b-check-fixes-unmerged); [Held cards read as engineer sentences: a fixed template replaces the model's adv](05-EXPECTED-VS-ACTUAL.md#l2-held-card-engineer-template); [Since 21 Oct an overdue move, an 'unknown' confidence or an unnamed decider turn](05-EXPECTED-VS-ACTUAL.md#l2-judgment-holds-overdue-and-unknown); [YC-II F302 (+F216, F292, F306): claim-check product calls still open; a move res](06-DECISIONS.md#l2-f302-confirmed-answer-gets-no-card); [Migration number 0250 was reserved by two plans and then taken by a third change](01-WHAT-WENT-WRONG.md#process-migration-0250-booked-three-times)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S20.U1** | Rohit decides STEP-13b and the claim-check product calls | — | Rohit chooses merge (port the ladder, dossier enrichment and check.v5 into reason/l2) or retire; answers F302 (recommended: a confirmed answer is a source event), F216, F292, F306; recorded in 03-LOG. | rohit | decision |
| **S20.U2** | Rebase STEP-13b onto speedrun008 (or record its retirement) | `migrations/<next free>_expert_review_attempts.sql`<br>`genios_engine/reason/l2/judge.py`<br>`genios_engine/contracts/claim_check.py` | Branches pushed for safekeeping; 0250_expert_review_attempts renumbered to the next free number (test_migration_numbers_are_unique green); check.v5 resolved against reason/l2/judge.py; golden re-recorded; the 17 Oct scorecards committed under GeniOS-011/scores; or, if retired, a 03-LOG line. | claude | code |
| **S20.U3** | Held cards in the founder's voice, after one repair | `genios_engine/contracts/claim_check.py`<br>`genios_engine/reason/expert/verify.py`<br>`genios_engine/reason/expert/asks.py`<br>`genios_engine/reason/expert/review.py`<br>`genios_engine/reason/l2/judge.py` | HELD_BECAUSE, _held_question and asks.WHY_* lead with the move to confirm in plain words (sample texts shown to Rohit first); a bare domain is never printed as a name; one repair call carrying the check's verdicts runs at every depth on R-7 and R-9 before holding; golden headline assertion on F15 plus a mutation on the template. | claude | code |
| **S20.U4** | Uncertainty routes to a lane, never to a held question | `genios_engine/contracts/reasoning_result.py`<br>`genios_engine/reason/expert/decide.py`<br>`tests/contracts/test_judgment_hold_holds_only_an_open_conflict.py` | An overdue move is shown as overdue and re-dated to today; weak or 'unknown' ground becomes a monitor card that keeps the move as a watch; a solo-founder tenant's decider defaults to 'you'; only an open conflict holds; a confirmed founder answer counts as a source event in _confidence; mutations for each rule. | claude | code |

<a id="s21"></a>
### S21 · L2 subjects: one investor wave, quiet files re-looked, seeds become files

- **Why:** F15 (five funds, eight weeks silent) makes 0 cards today and 5 held cards on the L2 path instead of 1; a quiet file with no reply pattern is never re-examined (D57); a seed subject is judged but can never become a card, and its HOLD dead-ends.
- **Layers:** L2, Cross-layer · **group:** E-L2 · **depends on:** S20, S15, S13 · **Claude can start now:** no
- **Blocked on:** S20 (held wording and repair), S15 (one file per counterparty), S13.U4 (HOLD → need wiring); U2 needs Rohit's D57 yes.
- **Items it closes:** [F15 (five funds, eight weeks silent): today's path makes 0 cards, the L2 path sp](05-EXPECTED-VS-ACTUAL.md#l2-f15-five-held-cards); [YC-II D57 / F169: a file with no reply pattern yet is never re-examined, so sile](05-EXPECTED-VS-ACTUAL.md#l2-d57-quiet-file-without-pattern-never-relooked); [L2 subjects come from L1 bundles matched to L3 files by event: an unfiled bundle](05-EXPECTED-VS-ACTUAL.md#cross-l2-subject-to-file-seam); [A subject with no file (a first mail, a new admission) is judged but can never b](05-EXPECTED-VS-ACTUAL.md#l2-seed-subject-no-card)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S21.U1** | A wave subject judged once | `genios_engine/reason/l2/inputs.py`<br>`genios_engine/reason/l2/sweep.py`<br>`tests/reason/l2/test_a_wave_is_one_subject.py` | Files of one kind with the same unanswered ask form one wave subject judged once; a fact about our own sent mail or a silence grounds on our own words or a tool line; F15 yields exactly one card on the ideal reader (its strict-xfail removed only when it passes; its expectation never edited). | claude | code |
| **S21.U2** | A quiet file with an open ask comes back (D57) | `genios_engine/reason/expert/triggers.py`<br>`genios_engine/reason/l2/inputs.py` | After Rohit takes D57's recommendation: while an ask is open and the file has no usual gap, crossing the playbook's STAGE_PRIOR or the 7/14/30-day rungs re-judges it, in the expert triggers and the L2 subject selection; F15 re-recorded; mutation. | claude | code |
| **S21.U3** | Seeds re-key to their file; multi-file bundles judged per file | `genios_engine/reason/l2/inputs.py`<br>`genios_engine/reason/l2/sweep.py`<br>`genios_engine/context/l2_admission.py` | A seed whose events are filed later is re-judged under its file; a bundle spanning two files is judged under each; HOLD '-' raises an EvidenceNeed; a seed's result can make a card (subject = the thread's counterparty node); the pass receipt counts seeds and empty snapshots; PG tests. | claude | code |

<a id="s22"></a>
### S22 · L2's judgment reaches the card: six-dimension confidence, options, Plane D package

- **Why:** Under l2_cards only the review half of the judgment is written; the card still shows formula C/U/I and an event-count scalar floor; Plane D reaches the judgment only through a brief-named kind's playbook; no surface shows the architecture's card parts.
- **Layers:** L2, L5, Surfaces · **group:** E-L2 · **depends on:** S20, S19 · **Claude can start now:** no
- **Blocked on:** S20 and S19 own the shared L2 files first.
- **Items it closes:** [Under l2_cards the judgment half (six-dimension confidence, options, decision ne](05-EXPECTED-VS-ACTUAL.md#l2-judgment-half-dropped-confidence-cui); [Domain expertise (Plane D) barely reaches the judgment: one Founder Office playb](05-EXPECTED-VS-ACTUAL.md#l2-plane-d-thin); [No surface shows the architecture's card parts: the confidence vector, unknowns,](05-EXPECTED-VS-ACTUAL.md#surfaces-card-shape-vs-architecture)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S22.U1** | Carry the judgment half to the card | `genios_engine/reason/expert/store.py`<br>`genios_engine/reason/l2/sweep.py`<br>`genios_engine/deliver/card_builder.py`<br>`genios_engine/contracts/reasoning_result.py` | The judgment half is stored with the review row (or joined from reasoning_results by fingerprint); card.v1 carries the six named levels with reasons, options and decision need; the scalar floor is dropped for L2 cards; 'framing' vs 'frame' aligned; tests. | claude | code |
| **S22.U2** | The routed capability's ExpertisePackage in block D | `genios_engine/reason/l2/dossier.py`<br>`genios_engine/packs/compiler/playbook_reader.py` | Block D folds the compiled package (patterns, counter-patterns, evidence standards, heuristics) with its hash in expertise_ref; a file with no brief kind can have one inferred and proposed (S19.U1); tests. | claude | code |
| **S22.U3** | Confidence dots and 'held back, and why' on the surfaces (dummy first) | `(dashboard repo) src/lib/card-read.ts` | Rohit approves a dummy; then cards render the six levels and a view lists /v1/executive/why-not. | claude | ui_dummy |

<a id="s23"></a>
### S23 · Founder Office expertise reaches founder work

- **Why:** The compiled lane refuses every Founder Office situation as 'unreviewed' (all 6 capabilities draft; 267 review lines untouched), so investor and programme work (Antler) gets no compiled card; the Admin vendor-renewal gate can never fire (F56); reply-time rules are fixed; the cadence line overclaims whose normal it is.
- **Layers:** L2, L5 · **group:** E-L2 · **depends on:** S02 · **Claude can start now:** yes
- **Blocked on:** U1 Rohit; U2/U3 follow U1. U4 can start now.
- **Items it closes:** [GeniOS-008 D1 / YC-II D45, D3: founder playbooks are unreviewed; the compiled la](06-DECISIONS.md#l2-d1-founder-playbooks-unreviewed-compiled-lane-refuses); [The investor and programme playbooks were gated on a 267-line YAML review that w](01-WHAT-WENT-WRONG.md#l2-founder-playbooks-gated-on-unread-review); [YC-II STEP-18 B10 / s18-D2 (+F56): the Admin vendor-renewal situation is gated o](06-DECISIONS.md#l2-b10-vendor-renewal-gate-can-never-fire); [YC-II D42, D43, D44 (F107, F114, F105): reply-time decisions unanswered; 'reply ](06-DECISIONS.md#l2-d42-d44-reply-time-rules); [YC-II STEP-18 B15 / F280: the card says 'they normally reply in about N days' ev](05-EXPECTED-VS-ACTUAL.md#l5-b15-reply-cadence-wording-ignores-basis)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S23.U1** | Rohit's playbook and reply-time decisions | — | Rohit chooses D1 (review the two sheets line by line, or run labelled 'playbook not yet reviewed'), approves re-pointing B10 to we_evaluate_them, and answers D42/D43/D44; recorded in 03-LOG. | rohit | decision |
| **S23.U2** | The compiled lane admits draft Founder Office capabilities, labelled | `genios_engine/packs/compiler/capability_resolver.py`<br>`tests/packs/test_draft_founder_office_runs_labelled.py` | Under D1's default, for Rohit's org a draft Founder Office capability is admitted with 'playbook not yet reviewed' (mirroring card_builder.PLAYBOOK_NOT_YET_REVIEWED) instead of UnsupportedCoverage('unreviewed'); other tenants unchanged; test plus mutation. | claude | code |
| **S23.U3** | Vendor renewal reaches a renewal card | `Domain Expertise/Admin Expertise/capabilities/05-contract-and-vendor-administration/renewal-management/situations/vendor-relationship-live.yaml` | The gate reads we_evaluate_them; a vendor-renewal play exists for the 'vendor' kind; F56 re-recorded and passing. | claude | code |
| **S23.U4** | The cadence line says whose normal it is | `genios_engine/deliver/slots.py`<br>`tests/deliver/test_cadence_line_states_its_basis.py` | A their_cadence_basis slot: 'they' only on a person basis, 'people at <firm>' on a firm basis, clause dropped on tenant/floor; F55 narrator answer re-recorded; mutation. | claude | code |

<a id="s24"></a>
### S24 · L3 admits: a situation exists only after L2's judgment (G0.3), first type

- **Why:** Situations are still born in L3 before any reasoning, and both admission doors (l2_admission, situation_publisher) run after the row exists, with two vocabularies on two tables; no 'seed' status exists, merge/link have no applier, and the DecisionObject is write-only. This is the architecture's L2-primary seam and the ground goals hang on.
- **Layers:** L3, L2, Cross-layer, Goals · **group:** D-L3 · **depends on:** S15, S18, S21 · **Claude can start now:** no
- **Blocked on:** Needs reading situations attached to files (S15.U1) and one live situation per file (S15.U2) first.
- **Items it closes:** [Situations are still formed in L3 before any reasoning; both admission doors run](05-EXPECTED-VS-ACTUAL.md#l3-situations-born-before-reasoning); [L2-G2 admission is built but shadow: it never creates or changes a situation; a ](05-EXPECTED-VS-ACTUAL.md#l2-admission-g2-shadow); [l2_admissions is shadow only: written only when l2_reasoning is on, read by noth](05-EXPECTED-VS-ACTUAL.md#l3-l2-admissions-shadow-status); [The exact order in _run_l2_chain: L3 forms situations, then L2 reasons, then adm](05-EXPECTED-VS-ACTUAL.md#cross-chain-order); [What L3 records of an admitted judgment, including the decision object, is write](05-EXPECTED-VS-ACTUAL.md#l3-interpretations-decision-object-write-only); [G0 ground: CI is green, but l2_cards, admission-decides-existence and D1–D8 are ](05-EXPECTED-VS-ACTUAL.md#goals-g0-ground-partial)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S24.U1** | Seeds for the first type; ADMIT makes them live | `migrations/<next free>_situation_seed_status.sql`<br>`genios_engine/context/outreach_situations.py`<br>`genios_engine/context/l2_admission.py`<br>`genios_engine/reason/l2/sweep.py`<br>`genios_engine/deliver/pipeline.py` | Status 'seed' exists; the first type's writer (awaiting reply/outreach) writes seeds only; ADMIT flips a seed to active, REJECT archives it with resolved_by='admission', HOLD keeps it a seed with its reason and an EvidenceNeed; the card source reads only admitted rows for that type; the situation-writer ratchet (S04.U1) shrinks by one; PG tests plus mutation. | claude | code |
| **S24.U2** | Merge and link appliers; one admission door | `genios_engine/context/l2_admission.py`<br>`genios_engine/context/situation_publisher.py`<br>`genios_engine/reason/domain_shadow.py` | Admitted merge and link proposals are applied; situation_publisher takes L2's proposal or is retired so one ADMIT/HOLD/REJECT vocabulary remains; tests. | claude | code |
| **S24.U3** | Admission is a stage between L2 and L4; a typed DecisionObject with its reader | `genios_engine/api/routes.py`<br>`genios_engine/context/l2_admission.py`<br>`genios_engine/contracts/reasoning_result.py` | _run_l2_chain runs admission as its own stage after the L2 pass and before cards; the DecisionObject is a typed contract with an L4 reader (used by S32), and situation_interpretations' outcome column no longer receives op values; tests. | claude | code |
| **S24.U4** | G0 status and D1–D8 defaults logged | `speedrun008/GeniOS-009/03-LOG.md`<br>`speedrun008/GeniOS-009/00-START-HERE.md` | G0.1 done, G0.2/G0.3 status from this programme, D1–D8 recorded as defaults or Rohit's answers. | claude | docs |

<a id="s25"></a>
### S25 · Switch L2 cards on one situation type at a time and retire the formula lanes

- **Why:** Up to six producers make cards with their own switches; l2_cards is a whole-tenant switch compared only offline on the ideal reader; 23 formula reasoners, the LLM decider and the per-pack rule lane still decide; the golden runner forces the decider on; the L2-vs-today board is not in CI. GeniOS-008 Rule 2: beside, compared, switched per type with a one-line rollback.
- **Layers:** L2, L1, Process · **group:** E-L2 · **depends on:** S07, S20, S24, S05, S04 · **Claude can start now:** no
- **Blocked on:** Real-model board (S07), admission deciding existence (S24), Rohit's A3/A5 and Harsh's flip.
- **Items it closes:** [I2 not made: l2_cards is a whole-tenant switch, compared only offline on the ide](05-EXPECTED-VS-ACTUAL.md#l2-i2-first-switch-not-made); [GeniOS-008 A2/A3 + GeniOS-009 D5/D6: the cutover is per tenant and covers every ](05-EXPECTED-VS-ACTUAL.md#l2-a2-a3-per-type-cutover-not-built); [Up to six producers can make a card today, each with its own switch; the L2 judg](05-EXPECTED-VS-ACTUAL.md#l2-card-paths-six-producers); [H1–H3 not done: 23 formula reasoners, the LLM decider and the per-pack rule lane](05-EXPECTED-VS-ACTUAL.md#l2-h1-h3-formula-lanes-still-decide); [GeniOS-008 A5 / YC-II D11, F230, F274: the LLM decider (R-1) is not retired, and](05-EXPECTED-VS-ACTUAL.md#l2-a5-llm-decider-not-retired-golden-forces-it-on); [Bundles (E1) are written every sweep, but their only reader is the L2 pass, whic](06-DECISIONS.md#l1-e1-bundles-read-only-in-shadow); [YC-II W27 spent ~20 days (5-17 Oct) patching the old flow while Design Atlas v2 ](01-WHAT-WENT-WRONG.md#process-built-on-the-old-flow); [The L2-vs-today golden comparison runs by hand, measures the path only, and lack](05-EXPECTED-VS-ACTUAL.md#process-l2-golden-board-not-in-ci)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S25.U1** | A per-type gate for l2_cards and the producer on every card | `genios_engine/platform/l4_activation.py`<br>`genios_engine/reason/l2/sweep.py`<br>`genios_engine/deliver/card_builder.py`<br>`tests/replays/engine_runner.py` | l2_cards makes a file's card only for situation types on a per-tenant allow-list read by admission; every card records its producer and the sweep counts cards per producer; the golden runner runs the production configuration (or scores both with and without R-1); tests. | claude | code |
| **S25.U2** | Card guard and the L2 board in CI | `tests/test_rule3_switched_type_cards_trace_to_a_judgment_pg.py`<br>`.github/workflows/ci.yml`<br>`tests/replays/specs/founder/` | A PG test fails when a card of a switched type has no admitted reasoning_results row; golden-pg runs python -m tests.replays.l2_score and exits 1 when the new path loses a case; the seven L2 scenario-kind cases are authored (ideal-reader answers marked as such); negative controls. | claude | code |
| **S25.U3** | First type switched on Rohit's org, one week side by side | — | Rohit confirms A3 (first type awaiting reply/outreach, or whole tenant); the real-model board (S07) shows the new path at least as good; Harsh flips l2_reasoning → l2_cards for that type; one week of l2_shadow_report plus the daily health rows shows no card lost; rollback line recorded. | rohit+harsh | prod_action |
| **S25.U4** | Retire the old lanes for the switched type | `genios_engine/reason/runner.py`<br>`genios_engine/reason/domain_shadow.py`<br>`genios_engine/reason/llm_decision_maker.py`<br>`genios_engine/reason/l2/tools.py` | For the switched type the compiled lane, the per-pack rule run and R-1 no longer decide; date and number logic sits behind reason/l2/tools; R-1 is removed once no type depends on it; tests and the ratchet move. | claude | code |

<a id="s26"></a>
### S26 · Goal decisions, and the plan amended so L2 proposes goals

- **Why:** No unit in GeniOS-009 lets the L2 judgment propose a goal, so a workstream like the Antler Singapore admission can never become a goal even after G1–G9; the architecture defines no goal object; D7/D9–D12 are open; GeniOS-009 docs are stale (G0 'red', migration 0250 taken, Goals page 'unmerged').
- **Layers:** Goals, Process · **group:** F-goals · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U1 Rohit; U3 follows U1. U2 can start now.
- **Items it closes:** [Decision needed: may L2 propose goals, at what granularity, and through which do](06-DECISIONS.md#goals-decision-goal-granularity-and-door); [Plan gap: even after G1–G9, a workstream like Antler cannot become a goal of its](05-EXPECTED-VS-ACTUAL.md#goals-plan-gap-no-l2-goal-proposer); [GeniOS-009 D1, D2, D8: the goal model decisions are on their defaults, and nothi](06-DECISIONS.md#goals-g009-d1-d2-d8-goal-model-defaults-unbuilt); [GeniOS-009 D7: inferred goals come only from the brief drafter's memory patterns](06-DECISIONS.md#goals-g009-d7-inferred-goals-only-from-brief-patterns); [GeniOS-008's architecture names the goal loop but defines no goal object, so the](01-WHAT-WENT-WRONG.md#goals-architecture-defines-no-goal-object); [The judgment cannot propose a goal, so graph context such as the Antler Singapor](05-EXPECTED-VS-ACTUAL.md#goals-judgment-cannot-propose-goal); [The goal plan's only inferred-goal source is the weekly brief drafter, which rea](01-WHAT-WENT-WRONG.md#goals-no-unit-proposes-goals-from-context); [A second goal door that GeniOS-009 never mentions: internal knowledge of kind 'g](06-DECISIONS.md#l1-internal-knowledge-goal-door-unlinked); [Goals docs are stale: G0 still marked red, the 0250 number is taken, and the Goa](05-EXPECTED-VS-ACTUAL.md#process-goals-docs-stale); [GeniOS-009 04-FOR-HARSH plans G1 as migration 0250, which the head already uses](05-EXPECTED-VS-ACTUAL.md#process-g009-migration-numbers-collide)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S26.U1** | Rohit's goal decisions | — | Rohit answers D9 (L2 may propose goals; recommended yes), D10 (child goals under umbrella goals; yes), D11 (door: company_goals direct with the brief kept in sync), D12 (cap, 3 a week), confirms D1/D2/D7/D8, chooses the internal-knowledge 'goal' door, and gives the Rule 1.4 yes to the architecture change; recorded in 03-LOG. | rohit | decision |
| **S26.U2** | GeniOS-009 docs tell the truth | `speedrun008/GeniOS-009/00-START-HERE.md`<br>`speedrun008/GeniOS-009/04-FOR-HARSH.md`<br>`speedrun008/GeniOS-009/03-LOG.md`<br>`speedrun008/GeniOS-009/STEP-G1-the-goal-object.md`<br>`speedrun008/GeniOS-010/03-GOALS/README.md` | G0.1 marked done, G0.2–G0.4 open; migration table renumbered to 'next free at build time (>=0251)' with the check command; the Goals page marked merged in 2edfb86; team_milestones and seat_objectives named; a correction line appended to 03-LOG. | claude | docs |
| **S26.U3** | Architecture and plan amendment for goal proposals | `speedrun008/GeniOS-008/00-ARCHITECTURE.md`<br>`speedrun008/GeniOS-009/STEP-G1-the-goal-object.md`<br>`speedrun008/GeniOS-009/STEP-G3-goal-impact-in-the-judgment.md`<br>`speedrun008/GeniOS-009/STEP-G4-goal-situation-links.md`<br>`speedrun008/GeniOS-009/STEP-G6-the-goal-on-the-card.md` | After U1: 00-ARCHITECTURE defines the goal object, GoalImpact and GoalProposal; GeniOS-009 gains G1.6 (structured proposal fields), G3.5 (L2Judgment.proposed_goal), G4.5 (context/goal_admission), G6.8 (proposed-goal chip) and founder case F72; D7 names L2 as a goal source beside the drafter. | claude | docs |

<a id="s27"></a>
### S27 · Interim: goals proposed from what is in motion and visible today

- **Why:** Rohit has to type goals by hand and the Antler admission never became one: the drafter runs only for orgs with an accepted line, reads memory patterns and never the graph's situations or files; the home always says 'No goals set yet' even when the brief holds accepted goals; the Goals page shows no proof for a proposal. This gives value before G1–G6 land, through the existing brief door (D7 default).
- **Layers:** Goals, Surfaces · **group:** F-goals · **depends on:** S02 · **Claude can start now:** yes
- **Blocked on:** U3 needs Rohit's approval of the dummy; U4 needs production.
- **Items it closes:** [Why 'Antler Singapore admission' cannot become a goal automatically today](05-EXPECTED-VS-ACTUAL.md#goals-antler-cannot-appear-today); [The golden tenant ships a hand-curated brief (5 accepted goals, 20 in-motion lin](01-WHAT-WENT-WRONG.md#goals-golden-brief-is-pre-curated); [Goals page: approval needs typing to be useful, the answers become free text, an](05-EXPECTED-VS-ACTUAL.md#surfaces-goals-page-proposal-flow); [Home page always says there are no goals, even when the brief holds accepted goa](05-EXPECTED-VS-ACTUAL.md#surfaces-home-goals-always-empty); [The home says 'No goals set yet' and 'Goals are coming next' even when the brief](05-EXPECTED-VS-ACTUAL.md#surfaces-home-ignores-brief-goals)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S27.U1** | The drafter sees what is in motion | `genios_engine/reason/brief_review.py`<br>`genios_engine/reason/brief_patterns.py`<br>`genios_engine/reason/brief_drafter.py`<br>`tests/reason/test_the_drafter_sees_what_is_in_motion.py` | An org with zero accepted lines gets a first weekly draft and a failed week is retried the next tick; brief_patterns adds open situations and workstream files with their kinds and in-motion lines as pattern items with evidence ids; a test where an accelerator-application file in motion (synthetic, F17-like) yields a proposed goal line naming it; the second run proposes nothing new (dedupe); mutation. | claude | code |
| **S27.U2** | Golden cases with no accepted brief | `tests/replays/specs/founder/` | Cases run with no accepted brief and with drafter-only proposals; the board reports them separately from the curated-brief cases. | claude | code |
| **S27.U3** | Home and Goals page show the brief's goals and proposals (dummy first) | `(dashboard repo) src/components/homepage/genios-at-work.tsx`<br>`(dashboard repo) src/product/internal/dashboard/homepage/live.ts`<br>`(dashboard repo) src/product/internal/dashboard/goals/live.ts` | Rohit approves a clickable dummy; then the home shows accepted brief goals with progress unknown, 'Goals formed' counts accepted_at this month and links to /dashboard/goals, 'No goals set yet' appears only with zero goals, 'N goals waiting for you' lists pending lines, and proofOf renders the drafter's pattern evidence. | claude | ui_dummy |
| **S27.U4** | Rohit reads and decides the proposals | — | Rohit approves or rejects the drafted goal lines in production (read via S01's brief query). | rohit | decision |

<a id="s28"></a>
### S28 · G1: the goal object

- **Why:** No contract, table, sync or API for goals exists; a goal is only a free-text brief line, and migration 0250 is already taken.
- **Layers:** Goals, L3 · **group:** F-goals · **depends on:** S26 · **Claude can start now:** no
- **Blocked on:** Rohit's goal decisions (S26.U1) change the schema.
- **Items it closes:** [G1 goal object is not built: no contract, table, sync, API, and migration 0250 i](05-EXPECTED-VS-ACTUAL.md#goals-g1-goal-object-missing); [L3 has no goal object and no goal↔situation link, and the planned link (G4) depe](05-EXPECTED-VS-ACTUAL.md#goals-no-goal-in-l3); [The Theresa/Antler acceptance replay has no goal obligation, uses the retired 7-](05-EXPECTED-VS-ACTUAL.md#process-theresa-spec-has-no-goal)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S28.U1** | Goal contract and tables | `genios_engine/contracts/goal.py`<br>`migrations/<next free, >=0251>_company_goals.sql`<br>`tests/contracts/test_goal.py` | Goal with status proposed/approved/active/completed/superseded/cancelled and source founder/brief/inferred/document; company_goals and company_goal_revisions with the structured proposal fields (metric, target, deadline, owner, parent_goal_id, subject_ref, evidence_refs); check constraint company_goals_live_is_approved_ck; mutation: an active row without approved_by is refused. | claude | code |
| **S28.U2** | Sync, routes and one-click approve | `genios_engine/context/goals.py`<br>`genios_engine/api/goal_routes.py`<br>`tests/api/test_goal_routes_pg.py` | context/goals.sync_from_brief runs as the first sweep stage l3.goals_sync; GET /v1/goals, PATCH (metric, target, deadline, owner), POST /v1/goals/{id}/approve {revision} with no text and /reject (quiet 90 days); PG tests. | claude | code |
| **S28.U3** | Founder case F72 and the Theresa spec restated | `tests/replays/specs/founder/`<br>`tests/replays/specs/01-theresa_investor_reconsideration_and_update_cade.json` | Synthetic F72 ('an accelerator application with the partner's conditional reply becomes a proposed goal') with expected.proposed_goal and expected.goals, recorded on the ideal reader, strict-xfail until S29; spec 01 restated in GeniOS-008 terms or marked superseded by F72 (real names stay out, per REAL_NAMES). | claude | code |

<a id="s29"></a>
### S29 · G2 + G3: goals in the judgment, and L2 proposes a goal that L3 admits as a proposal

- **Why:** Goals reach the judgment only as id-less background prose; nothing asks for or carries goal impact; L2 cannot propose a goal, so graph context like the Antler admission never becomes one.
- **Layers:** Goals, L2, L3, Cross-layer · **group:** F-goals · **depends on:** S28, S24, S20 · **Claude can start now:** no
- **Blocked on:** G1 (S28), admission deciding existence (S24) and the check work in S20.
- **Items it closes:** [G2: the L2 judgment sees goals only as brief words; no block G, no goal ids, and](05-EXPECTED-VS-ACTUAL.md#goals-g2-goals-not-in-l2-dossier); [G3: neither L2Judgment nor ExpertReview has any goal field](05-EXPECTED-VS-ACTUAL.md#goals-g3-no-goal-impacts); [Goals reach the judgment only as id-less background prose; nothing asks for or c](05-EXPECTED-VS-ACTUAL.md#goals-not-in-judgment); [Missing design: L2 proposes a goal from a workstream, L3 admits it as a proposal](05-EXPECTED-VS-ACTUAL.md#cross-layer-l2-proposes-l3-admits-goal-design)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S29.U1** | Block G: live goals with ids, and pending proposals apart | `genios_engine/reason/l2/dossier.py`<br>`genios_engine/reason/l2/sweep.py`<br>`genios_engine/contracts/reasoning_result.py` | Block G prints live goals with goal: ids, owner, deadline and progress, plus a sub-block of pending proposals marked 'proposed — not the company's goal yet'; fingerprint gains goal_set and linked_goals; trigger goal_changed re-judges linked subjects exactly once; tests. | claude | code |
| **S29.U2** | GoalImpact in the judgment | `genios_engine/contracts/reasoning_result.py`<br>`genios_engine/reason/l2/prompt.py`<br>`genios_engine/reason/l2/judge.py` | L2Judgment.goal_impacts (goal_ref, relation advances/threatens/depends_on/unclear, why, evidence, size_basis) is asked for in the prompt and refused by GOAL_NOT_PRINTED, IMPACT_WITHOUT_EVIDENCE, SIZE_NOT_PRINTED and DUPLICATE_GOAL; carried to the review and card; tests per refusal code. | claude | code |
| **S29.U3** | L2 proposes, L3 admits a proposal | `genios_engine/contracts/reasoning_result.py`<br>`genios_engine/context/goal_admission.py`<br>`genios_engine/reason/l2/sweep.py` | L2Judgment.proposed_goal with its refusals (GOAL_PROPOSAL_NO_EVIDENCE, UNPRINTED_REF, TARGET_NOT_PRINTED, DEADLINE_NOT_PRINTED, PARENT_NOT_PRINTED); context/goal_admission.decide_goal_proposal runs in the admission savepoint: REJECT on a rejected subject or a monitor/suppress lane, HOLD on a held situation, a duplicate, a rejection within 90 days, the weekly cap, or no evidence of the company's own act; ADMIT writes company_goals status proposed, source inferred, never active. | claude | code |
| **S29.U4** | F72 green and the proposal's mutation proofs | — | F72 passes on the ideal reader; mutations: active without approved_by refused; skipping dedupe re-proposes on the second sweep; dropping the own-act rule lets a newsletter propose; then one capped real-model probe of R-9 with block G (1–2 calls) shows the field is produced. | claude | code |

<a id="s30"></a>
### S30 · G4 + G5: goals linked to situations, progress measured

- **Why:** No goal↔situation link and no progress tool exist; the dashboard draws every goal as 'Not measured'.
- **Layers:** Goals, L3, L2 · **group:** F-goals · **depends on:** S29, S15 · **Claude can start now:** no
- **Blocked on:** S29.
- **Items it closes:** [G4: no goal↔situation links, and the admission they hang on is still shadow](05-EXPECTED-VS-ACTUAL.md#goals-g4-no-goal-situation-links); [G5: no goal progress tool; progress is never measured, counted or marked unknown](05-EXPECTED-VS-ACTUAL.md#goals-g5-no-goal-progress)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S30.U1** | Goal↔situation links on ADMIT | `migrations/<next free>_goal_situation_links.sql`<br>`genios_engine/context/goal_links.py`<br>`genios_engine/context/l2_admission.py` | On ADMIT with a live goal, many-to-many revisioned links are written in the admission savepoint, including reading situations attached to the file (S15.U1); a link to a non-live goal is HOLD; links close when the situation ends; PG tests. | claude | code |
| **S30.U2** | Goal progress | `genios_engine/context/goal_progress.py`<br>`genios_engine/reason/l2/tools.py`<br>`genios_engine/api/goal_routes.py` | A closed METRICS registry (files_at_stage, manual); progress_of returns measured, counted or unknown (never 0 for unknown); goals_tool printed with line ids; GET /v1/goals returns progress in the GeniOS-010/03-GOALS §3 shape; tests. | claude | code |

<a id="s31"></a>
### S31 · G6 + C8: the goal on every card, and one-click approve where the founder looks

- **Why:** No card names a goal; the dashboard hard-codes 'Not linked to a goal yet'; G6 planned the board on /v1/insights, which the Cards page does not read; the 'Proposed goal' card has no unit.
- **Layers:** Goals, L5, Surfaces · **group:** F-goals · **depends on:** S30, S35, S36 · **Claude can start now:** no
- **Blocked on:** S30 links and S35/S36 (deliver/store.py owners first); UI needs Rohit's dummy approval.
- **Items it closes:** [G6: no goal line or goal_refs on cards, no goal board, no goal_board switch, and](05-EXPECTED-VS-ACTUAL.md#goals-g6-no-goal-on-card); [No goal on any card (C8/G6); and G6 plans the goal board on GET /v1/insights, wh](05-EXPECTED-VS-ACTUAL.md#goals-c8-no-goal-on-card); [No surface can show a goal: GET /v1/goals (B1) is unbuilt, and every goal slot i](05-EXPECTED-VS-ACTUAL.md#surfaces-b1-no-goal-on-any-surface)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S31.U1** | Cards carry goal_refs and a goal line | `migrations/<next free>_cards_goal_refs.sql`<br>`genios_engine/deliver/card_builder.py`<br>`genios_engine/deliver/store.py` | cards.goal_refs and goal_line are written by code from admitted links ('Moves: <goal> — advances · <date>'); queue rows carry them; 'Not linked' is counted; tests. | claude | code |
| **S31.U2** | Goal board on the Cards route, behind goal_board | `genios_engine/deliver/board.py`<br>`genios_engine/api/routes.py`<br>`genios_engine/platform/l4_activation.py` | GET /cards?group=goal (not /v1/insights) groups by goal then lane; goal_board is a per-tenant switch; tests. | claude | code |
| **S31.U3** | Goal row, proposed-goal chip and home 'goals waiting' (dummy first) | `(dashboard repo) src/lib/card-read.ts`<br>`(dashboard repo) src/app/dashboard/cards/page.tsx`<br>`(dashboard repo) Extension/` | Rohit approves a dummy; then readCard fills the Goal row, a 'Make this a goal?' chip on the card of the subject whose judgment proposed it approves in one click, the home lists goals waiting, and the Mac app shows the goal instead of null. | claude | ui_dummy |

<a id="s32"></a>
### S32 · G7 + G8: check-in states, a human decides, then L4 plans

- **Why:** L4 auto-plans an execution from every authoritative signal with no human step; the DecisionObject is read by nothing; 'done when' is free text; nothing can name an approver.
- **Layers:** Goals, L4 · **group:** F-goals · **depends on:** S30, S24 · **Claude can start now:** no
- **Blocked on:** Typed DecisionObject (S24.U3) and goal links (S30).
- **Items it closes:** [G7: no check-in states on the situation; 'done when' exists only as a free-text ](05-EXPECTED-VS-ACTUAL.md#goals-g7-no-checkin-states); [G8: the DecisionObject is written and nobody reads it; no decision requests; L4 ](05-EXPECTED-VS-ACTUAL.md#goals-g8-no-human-decision-requests); [L4 auto-plans executions from every authoritative signal on each heartbeat; the ](05-EXPECTED-VS-ACTUAL.md#l4-auto-plans-no-human-decides); [GeniOS-008 B1/B2: no human approval before work is planned; plan_commitments tur](05-EXPECTED-VS-ACTUAL.md#l4-b1-b2-human-approval-before-planning-missing); [Half of planned actions require approval but nothing can name the approver; ther](05-EXPECTED-VS-ACTUAL.md#l4-approver-and-org-data-writer)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S32.U1** | G7 check-in states | `genios_engine/context/checkin.py`<br>`genios_engine/contracts/reasoning_result.py`<br>`migrations/<next free>_situation_resolution_state.sql` | L2Judgment.done_when (says, evidence_kind, from_whom, by_when); context_situations.resolution_state with seven states; a pure evaluate that never calls overdue without full coverage; resolve only from verified or withdrawn; golden F68–F70. | claude | code |
| **S32.U2** | G8 decision requests and human_decides | `migrations/<next free>_decision_requests.sql`<br>`genios_engine/contracts/decision.py`<br>`genios_engine/executive/decisions.py`<br>`genios_engine/executive/sweep.py`<br>`genios_engine/api/decision_routes.py` | open_requests_from_interpretations reads situation_interpretations; GET/POST /v1/decisions; executions only from an approved choice carrying goal_refs and decision_request_id; plan_commitments skips a human_decides tenant; record_result → reported_complete; tests. | claude | code |
| **S32.U3** | Org data writer and approver resolution (L4-3, L4-2) | `genios_engine/executive/assignment.py`<br>`genios_engine/api/account_routes.py` | Seat responsibilities and reports_to are written from onboarding and accepted brief lines, owner-confirmed; resolve_approver_seat has a caller; a card says 'no approver named' instead of nothing; tests. | claude | code |
| **S32.U4** | human_decides on for Rohit's org | — | Rohit confirms B2 (Rohit the only approver) and switches human_decides on; Harsh flips it and logs the rollback. | rohit+harsh | prod_action |

<a id="s33"></a>
### S33 · G9 and value: outcomes move goals; the North Star and AER/HIR

- **Why:** Verified outcomes move no goal, macv_ledger has had no writer since 0012, AER and time_saved are literal 0, and there is no AER/HIR series.
- **Layers:** Goals, L6, Surfaces · **group:** H-L6 · **depends on:** S32 · **Claude can start now:** no
- **Blocked on:** Rohit's D4 and metric definitions; G7/G8.
- **Items it closes:** [G9: verified outcomes move no goal; no progress events; macv_ledger still has no](05-EXPECTED-VS-ACTUAL.md#goals-g9-outcomes-move-no-goal); [GeniOS-009 D4: what counts as recovered value in macv_ledger (the North Star) is](06-DECISIONS.md#goals-g009-d4-macv-ledger-value-rule); [macv_ledger, the North Star value ledger, was created in 0012 and has never had ](01-WHAT-WENT-WRONG.md#l6-north-star-ledger-no-writer); [The North Star ledger macv_ledger has no writer, and AER and time_saved are hard](06-DECISIONS.md#l6-macv-and-aer-empty); [AER and HIR have no weekly series (B2): AER is locked and blurred, HIR shows rea](05-EXPECTED-VS-ACTUAL.md#surfaces-b2-aer-hir-rollup-missing)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S33.U1** | Rohit defines value and the metrics | — | Rohit defines recovered value and the anti-double-count rule (D4), the AER/HIR formulas, and whether Agents unlock. | rohit | decision |
| **S33.U2** | Verified outcomes move goals | `genios_engine/feedback/goal_learning.py`<br>`migrations/<next free>_goal_progress_events.sql` | goal_progress_events appended only on a verified outcome; completion proposed and confirmed by the founder; goal_outcome learning candidates go through brain_pipeline (>=3 independent); tests. | claude | code |
| **S33.U3** | One macv writer and the AER/HIR rollup | `genios_engine/feedback/`<br>`genios_engine/api/intelligence_routes.py` | After U1, one macv writer at outcome closure; AER from executions and delegations; a weekly AER/HIR rollup route with 'not enough data (n=…)'; tests. | claude | code |

<a id="s34"></a>
### S34 · L5 card writer: own context (C6), the expert's result (C2), a clear subject (C1)

- **Why:** Cards repeat the subject node's last meetings and promises, so the UI hides repeated text and cards come out thin; 'what doing it gets you' is a stock line; headlines are cut before prepositions or come from templates ('…to body'); expert cards lose their step because the compiled insert never writes candidate_steps.
- **Layers:** L5, L2 · **group:** G-L5 · **depends on:** S01, S18, S20 · **Claude can start now:** no
- **Blocked on:** routes.py and domain_shadow.py owners first (S03, S18); verify.py after S20; U3 needs a paid probe (S07 key).
- **Items it closes:** [Rohit's binding card contract vs what GET /cards and GET /cards/{id} return, fie](05-EXPECTED-VS-ACTUAL.md#l5-card-contract-vs-routes); [No card writer (C1): the subject is a clause cut of the model's move, a pack tem](05-EXPECTED-VS-ACTUAL.md#l5-subject-writer); [C6 unbuilt: card context is the subject node's last 4 meetings and 3 promises, p](05-EXPECTED-VS-ACTUAL.md#l5-c6-person-level-context); [C2 partial: the expert's done_when reaches success_signal, but scenarios.act ('i](05-EXPECTED-VS-ACTUAL.md#l5-c2-act-not-carried); [Cards read thin, repeated or garbled on every surface: the card writer (C1), the](05-EXPECTED-VS-ACTUAL.md#l5-card-writer-c1-c2-c6-unbuilt); [The Cards page hides text that repeats across cards instead of fixing why the br](01-WHAT-WENT-WRONG.md#surfaces-ui-hides-repeated-brain-text)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S34.U1** | C6: context belongs to this card's thread | `genios_engine/api/routes.py`<br>`tests/api/test_two_cards_on_one_person_have_their_own_context_pg.py` | _card_intelligence keeps meetings and commitments only on the card's thread or among its why[] evidence and sentence sources; neighbour reads batched (no N+1); a test shows two cards on one person with different threads have different context; stock repeated sentences are omitted rather than repeated. | claude | code |
| **S34.U2** | C2: the expert's result and step reach the card | `genios_engine/reason/expert/verify.py`<br>`genios_engine/reason/expert/decide.py`<br>`genios_engine/deliver/card_builder.py`<br>`genios_engine/reason/domain_shadow.py` | scenarios.act is held through the check and carried as gold.act into a card result; the compiled/expert signal insert writes candidate_steps so an actionable expert card keeps its step; tests plus mutation. | claude | code |
| **S34.U3** | C1: deliver/card_copy.py | `genios_engine/deliver/card_copy.py`<br>`migrations/<next free>_cards_copy.sql`<br>`genios_engine/deliver/render.py`<br>`genios_engine/deliver/store.py` | One claim-checked model call per new card version (never per view) writes subject, summary, steps, result and goal with rests_on; a sentence resting on nothing is dropped; own model site and budget, failing closed to today's fields; gold_headline cuts only at real clause punctuation; 1–2 live probe calls first with max_tokens sized for thinking; golden headline assertions. | claude | code |
| **S34.U4** | Confirm what live cards anchor on | — | Rohit's read-only query (in S01's pack) shows subject_node_id distribution of open cards and the garbled-headline rows with their builder_version; the writer of 'Send calendar invites … to body' is named. | rohit | prod_action |

<a id="s35"></a>
### S35 · L5 queue, quotes, delegate, 'this is right', versions (C3, C4, C5, C7, C9)

- **Why:** The queue lacks what the list draws so the dashboard makes up to 40 detail calls and cards past 40 never load; quotes have no sender or date; Delegate is drawn but locked; there is no positive verdict; versions are miscounted; Feedback is offered where the brain refuses it.
- **Layers:** L5, Surfaces · **group:** G-L5 · **depends on:** S34, S36 · **Claude can start now:** no
- **Blocked on:** deliver/store.py and card_builder.py owners first (S36.U1, S34); UI needs Rohit's dummy approval.
- **Items it closes:** [C3 unbuilt: the queue lacks what the list draws, so the dashboard makes up to 40](05-EXPECTED-VS-ACTUAL.md#l5-c3-queue-fields); [C4 unbuilt: quotes on a card are bare strings with no sender or date](05-EXPECTED-VS-ACTUAL.md#l5-c4-quote-sender-date); [C5: there is no route to delegate a card to a person; agent delegation of a card](05-EXPECTED-VS-ACTUAL.md#l5-c5-delegate-route); [C7 unbuilt: no 'this is right' verdict; the action set has 'wrong' and nothing p](05-EXPECTED-VS-ACTUAL.md#l5-c7-no-right-verdict); [C9 and version: the brain keeps each version's words and change, but the dashboa](05-EXPECTED-VS-ACTUAL.md#l5-version-count-dashboard); [Delegate is drawn on every card but cannot be pressed: the brain has no delegate](05-EXPECTED-VS-ACTUAL.md#surfaces-delegate-locked-c5); [Cards past the 40th never load their detail, even when opened](05-EXPECTED-VS-ACTUAL.md#surfaces-cards-detail-cap-40); [The brain serves which screen items fed a card, but the Cards page never shows i](05-EXPECTED-VS-ACTUAL.md#surfaces-screen-items-unread-on-cards); [Web Cards offers Feedback on answered question cards, which the brain refuses, a](05-EXPECTED-VS-ACTUAL.md#surfaces-feedback-on-answered-card)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S35.U1** | C3: the queue carries what the list draws | `genios_engine/deliver/store.py`<br>`tests/deliver/test_queue_carries_list_fields_pg.py` | All three queue SELECTs return output_lane, business_subject, relationship_role, recommended->>'by_when', version, context_tags and from_screen; test. | claude | code |
| **S35.U2** | C4 quote objects and C7 'right' | `genios_engine/deliver/card_builder.py`<br>`genios_engine/deliver/actions.py`<br>`genios_engine/deliver/verdicts.py` | Each why[] quote is {text, from, at, event_id} resolved at build time; a 'right' action writes a verdict with optional words and scope, leaves card state unchanged and stays out of the precision 'wrong' set (migration if the CHECK lists causes); tests. | claude | code |
| **S35.U3** | C5: POST /cards/{card_id}/delegate | `genios_engine/api/routes.py`<br>`genios_engine/executive/delegation.py`<br>`tests/api/test_delegate_a_card_pg.py` | {to_seat} (owner/admin only) sets cards.assignee, writes a human.card_action event with cause delegate and a human_events row, and the card appears in that seat's queue; {agent_id} builds the play and params on the server and calls delegation.create_proposal(card_id=…); tests. | claude | code |
| **S35.U4** | Cards page catches up (dummy first) | `(dashboard repo) src/app/dashboard/cards/page.tsx`<br>`(dashboard repo) src/lib/card-read.ts` | After Rohit approves a dummy: DELEGATE_LIVE true for hand-over to a person; version from card.version with the last card.versioned change; screen_items as 'Fed by your screen'; Feedback drawn only when the card offers 'wrong'; an opened card forces its detail load; readCard accepts quote objects; details load only for the opened card once C3 lands. | claude | ui_dummy |

<a id="s36"></a>
### S36 · L5: every card door reaches every surface; meeting follow-ups open

- **Why:** meeting.followup cards fail all three card doors (never on GET /cards, 'Open card' 404s); question and team cards reach only the Cards page while Home Today, MCP, agents, push, /v1/insights and Ask read decision cards only; the kept 08:00 brief is read by no surface.
- **Layers:** L5, L4, Surfaces · **group:** G-L5 · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U3 needs Rohit's dummy approval; U2 follows U1 (same file).
- **Items it closes:** [Post-meeting follow-up cards ('meeting.followup') fail all three card doors: nev](05-EXPECTED-VS-ACTUAL.md#l5-meeting-followup-cards-fail-every-door); [Question cards and team/verify cards reach only GET /cards; Home 'Today', MCP, t](05-EXPECTED-VS-ACTUAL.md#surfaces-question-and-team-cards-reach-only-the-cards-page); [The STEP-15 kept morning brief has no reader on any surface; the dashboard reads](05-EXPECTED-VS-ACTUAL.md#l4-morning-brief-unreached); [YC-II D9 (STEP-15): the 08:00 morning brief is composed and kept, but the dashbo](05-EXPECTED-VS-ACTUAL.md#surfaces-d9-morning-brief-composed-but-no-surface-reads-it)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S36.U1** | The situation-card door keys on its builder, not a capability prefix | `genios_engine/deliver/store.py`<br>`tests/test_a_meeting_followup_card_opens_pg.py` | SITUATION_CARD_SQL admits builder_version team.emit.v1 with no reasoning run and rule_id = capability_id, without the team/verify prefix; an emitted meeting.followup card is in queue() and GET /cards/{id} returns it; mutation restoring the prefix turns the test red. | claude | code |
| **S36.U2** | One shared live-card fragment for every reader | `genios_engine/deliver/store.py`<br>`genios_engine/api/workspace_routes.py`<br>`genios_engine/api/intelligence_routes.py`<br>`genios_engine/mcp/server.py`<br>`genios_engine/deliver/agent_api.py`<br>`genios_engine/deliver/push.py`<br>`genios_engine/deliver/outbox.py`<br>`genios_engine/reason/moments/recall.py` | The three-door FROM/WHERE lives in one fragment used by the morning brief, Context panel, /v1/insights, MCP, agent poll and push, and recall; whether push lanes send questions is an explicit constant; a guard test fails when SQL reading open cards does not use the fragment. | claude | code |
| **S36.U3** | One morning brief (dummy first) | `(dashboard repo) src/components/dashboard/today-card.tsx`<br>`(dashboard repo) Extension/` | After Rohit approves a dummy, the dashboard Today card and the Mac app read GET /v1/executive/morning (one line, five items, feedback marks) with the old route as fallback until a brief is kept; the other brief is retired afterwards. | claude | ui_dummy |

<a id="s37"></a>
### S37 · Push delivery: email first

- **Why:** Delivery is pull-only: only in_app is provisioned, Slack has no setup screen, and there is no email transport, so reminders, escalations and the kept brief reach no one.
- **Layers:** L5 · **group:** G-L5 · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U1 Rohit; U3 Harsh. U2 can be built against a fake transport.
- **Items it closes:** [Delivery is pull-only: provisioning registers only in_app, Slack is the only pus](05-EXPECTED-VS-ACTUAL.md#l5-delivery-only-in-app); [GeniOS-008 B3: a card or reminder cannot reach Rohit by email; there is no email](05-EXPECTED-VS-ACTUAL.md#l5-b3-email-delivery-channel-missing)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S37.U1** | Channel and provider | — | Rohit confirms B3's default (email to <founder Gmail> first, Slack later) and the transactional provider account. | rohit | decision |
| **S37.U2** | Email channel adapter | `genios_engine/deliver/channels/email.py`<br>`genios_engine/deliver/channels/base.py`<br>`tests/deliver/test_email_channel.py` | An email adapter registered in get_channel sends the digest and high-band cards to the seat/owner address, never other people's mail bodies; tests with a fake transport; deliverable_channels can contain email. | claude | code |
| **S37.U3** | Email live for Rohit's org | — | Harsh sets the provider key, adds the org_channels email row, and confirms one digest and one high-band card arrive. | harsh | prod_action |

<a id="s38"></a>
### S38 · Mac app: one app, and no press is swallowed

- **Why:** Three Mac apps circulate (0.3.4 unmerged, main 0.2.4, a 14 Sep 0.2.0 zip); on main 'Not useful' sends wrong with no reason and Done on question cards, both refused with 422 and swallowed, so no verdict reaches L6.
- **Layers:** Surfaces, L5 · **group:** G-L5 · **depends on:** nothing · **Claude can start now:** no
- **Blocked on:** Rohit's go to merge (the auto-mode classifier refused merges to main before).
- **Items it closes:** [Three Mac apps in circulation: Rohit's 0.3.4 is unmerged, main is 0.2.4, and the](05-EXPECTED-VS-ACTUAL.md#surfaces-mac-three-versions); [The Mac app on main (0.2.4) and the downloadable 0.2.0 lose presses: 'Not useful](05-EXPECTED-VS-ACTUAL.md#surfaces-mac-main-silent-refusals); [Question cards: brain and web Cards page are correct; the Mac app offers Done (4](05-EXPECTED-VS-ACTUAL.md#l5-question-card-answer); [The Mac app's 'Not useful' sends 'wrong' with no reason; the brain refuses it (4](05-EXPECTED-VS-ACTUAL.md#l5-wrong-without-reason)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S38.U1** | Go to merge desktop-ux | — | Rohit approves the fast-forward of origin/rohit/desktop-ux (ed2724d) into dashboard main. | rohit | decision |
| **S38.U2** | M1–M5 verified and gaps closed | `(dashboard repo) Extension/` | On desktop-ux: only offered buttons drawn, an Answer box on question cards, a reason picker from reason_groups for 'wrong', refusals shown with the optimistic removal undone, surface 'desktop' sent; cargo and vitest tests green. | claude | code |
| **S38.U3** | Signed release and one download | — | Harsh tags desktop-v0.3.x, the release workflow builds the installers (Developer ID signing), and the Download link points at the release; DMGs only via scripts/mac-dev-dmg.sh. | harsh | prod_action |

<a id="s39"></a>
### S39 · Dashboard honesty: no made-up numbers, no dead routes, one card reader

- **Why:** A fake bell shows four invented notices to every customer, 'Policy-safe 100%' and AER 0 are constants, home tiles count recomputes, Goals and Screen read cards with their own mapper (verdict codes as 'What to do'), and pages call routes the brain lacks.
- **Layers:** Surfaces · **group:** G-L5 · **depends on:** S03 · **Claude can start now:** yes
- **Blocked on:** U1 waits for api/routes.py to be free (S03.U1); U2 needs Rohit's dummy approval.
- **Items it closes:** [The home bell shows four made-up system notices to every signed-in customer](05-EXPECTED-VS-ACTUAL.md#surfaces-fake-bell-notices); [The home claims 'No action bypassed a hard rule' and 'Policy-safe 100%' without ](05-EXPECTED-VS-ACTUAL.md#surfaces-policy-safe-constant-claim); [The dashboard metrics endpoint returns aer: 0, time_saved_hours: 0 and context_c](01-WHAT-WENT-WRONG.md#surfaces-aer-hardcoded-zero); [Home week tiles are labelled as situations formed and closed, but count recomput](05-EXPECTED-VS-ACTUAL.md#surfaces-home-tiles-measure-other-things); [Goals and Screen read cards with their own mapper: 'What to do' shows a verdict ](05-EXPECTED-VS-ACTUAL.md#surfaces-goals-screen-own-card-mapper); [Resources: manual entries vanish on reload, edit and delete hit routes that do n](05-EXPECTED-VS-ACTUAL.md#surfaces-resources-manual-context-dead-routes); [Reports and Memory pages call routes the brain lacks, and the Documentation page](05-EXPECTED-VS-ACTUAL.md#surfaces-dead-routes-gated-pages-and-docs); [Goals page draws empty-domain cards under Admin and collapses other domains' car](05-EXPECTED-VS-ACTUAL.md#surfaces-goals-domain-fold-r2); [The Goals page folds cards with an empty domain, and Founder Office cards, into ](01-WHAT-WENT-WRONG.md#surfaces-goals-page-folds-domains); [Several reachable pages and surfaces are placeholders: Memory providers (all loc](06-DECISIONS.md#surfaces-placeholder-pages)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S39.U1** | Brain numbers that are measured or say so | `genios_engine/api/home_routes.py`<br>`genios_engine/api/routes.py`<br>`tests/api/test_unmeasured_numbers_are_null.py` | policy_safe is computed from the gate/approval log or null; aer, time_saved_hours and context_calls_today return null with a reason; 'Situations formed' counts created_at and 'closed' counts resolved_at; fixed home-summary fields dropped; tests. | claude | code |
| **S39.U2** | Dashboard cleanup (dummy first) | `(dashboard repo) src/` | After Rohit approves a dummy: the bell reads /integrations/status and billing with no badge when empty; Goals and Screen render cards through readCard/ownCard; '' shows as Unknown; manual-context list/edit/delete wired or removed; Documentation lists only real routes; dead calls removed. | claude | ui_dummy |
| **S39.U3** | Placeholder pages | — | Rohit decides which locked pages stay visible and which leave the nav. | rohit | decision |

<a id="s40"></a>
### S40 · L6: learning that someone reads

- **Why:** Ledgers are written and never read, moment feedback is loaded and dropped, human-review proposals cannot be decided, and shadow calibration results are invisible. Calibration_apply stays off until B24 and D13; distinct_days is not touched before ADR-10.
- **Layers:** L6, Surfaces · **group:** H-L6 · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U1 Rohit; U3 dummy approval; U4 after U1. U2 can start (verify the feedback route file name before editing).
- **Items it closes:** [L6 and L5 write ledgers that nothing reads, or that only a count(*) receipt read](05-EXPECTED-VS-ACTUAL.md#l6-unread-ledgers); [Moment feedback (Mac Useful / Not useful) is written to learning_event_inbox, lo](05-EXPECTED-VS-ACTUAL.md#l6-inbox-dropped); [Human-review learning objects now reach the human_review state (bug 4 fixed) but](05-EXPECTED-VS-ACTUAL.md#l6-human-review-no-surface); [Calibration now runs (bug 1 fixed in shadow), but its would-mute and would-nudge](05-EXPECTED-VS-ACTUAL.md#l6-calibration-shadow-unread); [The durable ADAPTIVE recommendation-learning write is closed only by arithmetic ](06-DECISIONS.md#l6-adaptive-distinct-days-trap)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S40.U1** | Rohit's learning decisions | — | Per ledger keep-with-reader or retire; which preference kinds the founder can state (Atlas L7 #1); ADR-10; D13 (arm calibration or not). | rohit | decision |
| **S40.U2** | Shadow calibration and precision on a read route | `genios_engine/api/feedback_routes.py`<br>`tests/api/test_precision_shows_shadow_calibration.py` | GET /feedback/precision returns the last shadow would_mute/would_nudge with precision and n, plus precision by layer from learning_metrics; tests; calibration_apply untouched. | claude | code |
| **S40.U3** | Learning screen (dummy first) | `(dashboard repo) src/app/dashboard/` | After Rohit approves a dummy, an owner-only screen lists /v1/learning/objects?state=human_review and suggestions with Approve/Reject calling the review route. | claude | ui_dummy |
| **S40.U4** | Temporary memory from moment feedback | `genios_engine/feedback/units.py` | After U1, unit_temporary_memory turns moment_feedback into a leased, expiring TEMPORARY memory with typed evidence and no model; inbox_unconsumed falls; tests. | claude | code |

<a id="s41"></a>
### S41 · Docs tell the truth (layer logs, L3 folder, status files, memory)

- **Why:** The L1/L2 logs stop on 18 Oct and contradict the code; Harsh's 27 rebuild/audit commits are undocumented; L3 has no folder; GeniOS-010, 06-CARDS and YC-II status files say 'not merged' or 'TO BUILD'; two memory notes are false.
- **Layers:** Process, L1, L2, L3 · **group:** I-docs · **depends on:** nothing · **Claude can start now:** yes
- **Blocked on:** U2 needs Rohit to open L3.
- **Items it closes:** [The L1 folder docs stop at 18 Oct and contradict the code; the rebuild plan Hars](05-EXPECTED-VS-ACTUAL.md#l1-docs-stale-after-19-oct-rebuild); [The GeniOS-008 L2 folder stops at 18 Oct; Harsh's L2 rebuild and audit (19–21 Oc](05-EXPECTED-VS-ACTUAL.md#process-l2-docs-stale); [L3 was rebuilt and audited (20–21 Oct, now in prod) with no GeniOS-008 layer-3 f](05-EXPECTED-VS-ACTUAL.md#process-no-layer-3-folder); [Harsh's L1/L2/L3 rebuilds have no GeniOS-008 layer log, L3 has no folder, and th](01-WHAT-WENT-WRONG.md#process-rebuild-without-layer-docs); [06-CARDS README says the Cards page is 'Not merged, so not live', but dashboard ](05-EXPECTED-VS-ACTUAL.md#l5-docs-stale-merge-state); [GeniOS-010 docs and a memory note no longer match the repos](05-EXPECTED-VS-ACTUAL.md#process-geni010-docs-and-memory-drift); [A memory note says dashboard origin/main contains rohit/desktop-ux; it does not](01-WHAT-WENT-WRONG.md#process-memory-says-desktop-ux-on-main); [YC-II W27 status files still read 'TO BUILD' and 'PENDING deploy' after the work](01-WHAT-WENT-WRONG.md#process-yc2w27-status-files-stale); [reason/expert/triggers.py still says D48 is open and a version change waits for ](05-EXPECTED-VS-ACTUAL.md#process-triggers-docstring-says-d48-open); [Docs were rsynced into the main checkout as untracked copies, and VS Code showed](01-WHAT-WENT-WRONG.md#process-rsync-copies-67-files)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S41.U1** | L1 and L2 logs and Harsh notes for 19–21 Oct | `speedrun008/GeniOS-008/layer-1-enterprise-signals/`<br>`speedrun008/GeniOS-008/layer-2-reasoning/` | 03-LOG rows appended for 1925a5bb, a8dbefa2, 0d5939d1 and every L2 rebuild/audit commit with proof; 04-FOR-HARSH gains G-2 for l2_cards (switch, what to watch, rollback); 00/02/04 status refreshed (B2, E9, H1 done; B1 open); 08:582 corrected. | claude | docs |
| **S41.U2** | Layer 3 folder | `speedrun008/GeniOS-008/layer-3-context-graph/` | Rohit opens L3; then 00–04 written from the L3 audit, recording L3-1…L3-7 status and Harsh's nine commits; Harsh commits docs/plans/L1_REBUILD_PLAN.md. | rohit+harsh | docs |
| **S41.U3** | GeniOS-010, YC-II, docstring and memory corrections | `speedrun008/GeniOS-010/`<br>`speedrun008/YC-II W27/00-START-HERE.md`<br>`genios_engine/reason/expert/triggers.py` | 06-CARDS README and 04-WHAT-WHY-HOW say merged in 2edfb86; GeniOS-010 LOG and 00 updated; YC-II STEP-13..18 renamed and 00 status updated with the true reach date (21 Oct push); triggers.py docstring describes D48 as answered; memory notes corrected with dated lines (desktop-ux not on main; merge, never rsync). | claude | docs |

<a id="s42"></a>
### S42 · Lessons kept as rules

- **Why:** These items are done or are lessons; GeniOS-011 must keep each as a rule with the place it is enforced, so the same mistakes do not return (fan-out, ideal-reader-only proof, guards that cannot fail, retractions without measurement, building before a dummy).
- **Layers:** Process, Surfaces, L2, L4, L6 · **group:** I-docs · **depends on:** nothing · **Claude can start now:** yes
- **Items it closes:** [A hermetic suite with 15,494 passing tests hid eight live SQL bugs, because no t](01-WHAT-WENT-WRONG.md#process-green-suite-never-ran-sql); ['Calibration repaired' was planned as a one-line fix that would have switched on](01-WHAT-WENT-WRONG.md#l6-calibration-one-line-fix-was-a-trap); [A $10.4 Sonnet pass measured nothing: Claude 5 thinks by default, the thinking a](01-WHAT-WENT-WRONG.md#process-claude5-thinking-ate-the-budget); [Wide agent fan-out burned the shared session limit and killed every worker mid-u](01-WHAT-WENT-WRONG.md#process-fan-out-exhausted-the-quota); [A crosscheck report silently dropped three of five lenses (8 blocking findings) ](01-WHAT-WENT-WRONG.md#process-report-silently-truncated); [Full suites and fresh scratch databases for small changes filled Rohit's disk an](01-WHAT-WENT-WRONG.md#process-local-full-suites-and-scratch-dbs); [QA runs spanned a sleeping Mac (battery, closed lid), and their clock failures w](01-WHAT-WENT-WRONG.md#process-qa-on-a-sleeping-mac); [Layers were reported complete before their plan and recrosscheck existed](01-WHAT-WENT-WRONG.md#process-layers-reported-complete-early); [The L6 plan put the Atlas check last and drew its units from ledgers; three inve](01-WHAT-WENT-WRONG.md#process-atlas-check-last); [A plan was built on a corpus count of files ('534 capabilities, 37% admissible')](01-WHAT-WENT-WRONG.md#l2-corpus-counted-as-files); [A unit was specified on a stale code comment ('A situation's status gates nothin](01-WHAT-WENT-WRONG.md#l2-stale-comment-specified-a-unit); [U03 was retracted on a fact about a different writer, while the publisher wrote ](01-WHAT-WENT-WRONG.md#l6-retraction-on-a-neighbouring-fact); [Two planned L4 fixes would have discarded every future meeting (F9) and invalida](01-WHAT-WENT-WRONG.md#l4-fixes-that-would-have-caused-harm); [Findings were drawn from one module or a narrow regex: F17, six context/ retract](01-WHAT-WENT-WRONG.md#process-findings-from-narrow-measurements); [Guards and mutation runs that could not fail: no clean baseline, stale .pyc muta](01-WHAT-WENT-WRONG.md#process-guards-that-could-not-fail); [Production guards per package were counted with the hand-written Receipt.layer l](01-WHAT-WENT-WRONG.md#process-receipt-label-miscount); [Defects were filed twice under new numbers (F80=F71, F136=F67, F146=F46, and a u](01-WHAT-WENT-WRONG.md#process-duplicate-findings-minted); [Harsh's deploy notes contained instructions that would fail or that were stale](01-WHAT-WENT-WRONG.md#process-runbook-told-harsh-wrong-things); [The golden set's window (4 Aug-5 Oct) left out the benchmark's best findings, ST](01-WHAT-WENT-WRONG.md#process-golden-window-missed-benchmark); [Three background agents produced nothing across a context compaction and were ab](01-WHAT-WENT-WRONG.md#process-background-agents-vanished); [Workers spawned with isolation: worktree started from origin/main, 826 commits b](01-WHAT-WENT-WRONG.md#process-worker-worktree-wrong-base); [A no-op git stash followed by pop applied an old parked stash (five conflicted f](01-WHAT-WENT-WRONG.md#process-stash-pop-applied-old-stash); [Rohit was asked questions the data or the code already answered](01-WHAT-WENT-WRONG.md#process-asked-what-the-data-answered); [Explaining the system with Atlas/package layer digits made Rohit believe the wor](01-WHAT-WENT-WRONG.md#process-old-vocabulary-confused-rohit); ['Turn the LLM decider off and let the formula decide' (W4) was proposed against ](01-WHAT-WENT-WRONG.md#process-proposed-formula-decides); [A finished deliverable was handed back with decisions D1-D8 and 'who fixes the r](01-WHAT-WENT-WRONG.md#process-extra-asks-after-deliverable); [Two read-only Layer 2 audits were launched right after L1 was pushed, without Ro](01-WHAT-WENT-WRONG.md#process-started-layer-unasked); [The Mac app's real files were rebuilt and pushed after a 'ha' to a plan, instead](01-WHAT-WENT-WRONG.md#surfaces-real-files-before-dummy); [A design canvas with golden sample cards was delivered when Rohit asked for his ](01-WHAT-WENT-WRONG.md#surfaces-canvas-instead-of-real-cards); [A dashboard redesign prototype was built when Rohit asked only to regroup the ex](01-WHAT-WENT-WRONG.md#surfaces-redesign-instead-of-regroup); [The UI audit said the web dashboard shows no cards, judging from an unmounted co](01-WHAT-WENT-WRONG.md#surfaces-claimed-dashboard-shows-no-cards); [Mac app rounds were lost to ad-hoc signed builds (Accessibility lost), an old mo](01-WHAT-WENT-WRONG.md#surfaces-desktop-build-traps); [GeniOS-010 B3, B4, B5, B6, B8 (S1–S6, S8) and B9 are built in the brain and wire](05-EXPECTED-VS-ACTUAL.md#surfaces-b-items-built)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S42.U1** | GeniOS-011 rules from lessons | `speedrun008/GeniOS-011/05-RULES-FROM-LESSONS.md` | Each of the 33 items is one rule with its source and where it is enforced (CI job, guard test, workflow rule, memory note), and the rules that are still memory-only are flagged for a guard. | claude | docs |
| **S42.U2** | Receipt label decision | — | Rohit decides whether to relabel Receipt.layer; until then counts never filter by the label. | rohit | decision |

<a id="s43"></a>
### S43 · Verify the product blind (Phase 0 registry, Phase 5 / STEP-19 benchmark re-run)

- **Why:** The programme is done only when real cards on real data are judged by the benchmark's five shapes, not by the ideal-reader board; the Blueprint's Phase 0 registry and Phase 5 behavioural run were never produced, and STEP-19 was never written.
- **Layers:** Process, L1 · **group:** I-docs · **depends on:** S25, S31, S07, S08 · **Claude can start now:** yes
- **Blocked on:** U2 Rohit; U3 needs the switch done, goals on cards, the second mailbox and a paid budget.
- **Items it closes:** [YC-II D17, D19: the blind benchmark re-run (STEP-19) was never written, and Sole](06-DECISIONS.md#process-d17-d19-step19-and-sole-mate); [The Blueprint's Phase 0 registry and Phase 5 benchmark run were never produced](05-EXPECTED-VS-ACTUAL.md#l1-blueprint-phase0-and-phase5-missing)

| Unit | What | Files | Done when | Owner | Kind |
|---|---|---|---|---|---|
| **S43.U1** | L1 Architecture Registry (Phase 0) | `speedrun008/GeniOS-008/layer-1-enterprise-signals/06-REGISTRY.md` | Every capture/ file mapped group → section → function → component → unit with BUILT/RUNNING/TARGET/GAP/UNVERIFIED, RUNNING only where a production caller chain exists. | claude | docs |
| **S43.U2** | STEP-19 and Sole Mate placement | — | Rohit decides that the blind benchmark re-run (D17) is GeniOS-011's closing step and where Sole Mate's tenant (D19) goes. | rohit | decision |
| **S43.U3** | Blind P1–P5 run on the deployed models | — | With the second mailbox and corpus minimum met (benchmark.py CORPUS_MINIMUM), the five prompts run against the actual source enumeration on production's models, capped; scorecard committed and compared with the 4 Aug benchmark. | claude | paid_run |

## Planner's notes (coverage, corrections, standing rules)

Coverage: all 255 input items are placed. There are 254 unique keys because 'l1-e2-need-fetchers-armed-off' appears twice (once as L1 E2, once as E2/F224 + G-1). It is placed once, in S13. No item is dropped. I checked the placement with a script: every key lands in exactly one step.

Start-now file check: the files of the 8 start_now units do not overlap, and I confirmed each existing file is present at HEAD 0cc8d83c:
- capture/parked/drain.py, capture/landing/unread.py, capture/gate/gate.py
- context/correlation.py:340 thread_correlations, context/backfill.py:94, context/workstreams.py:230 _NAMED_MAIL
- reason/domain_shadow.py:744-815 skip counters
- reason/expert/sweep.py:171 l2_judges
- api/routes.py:140 /health
- scripts/golden_eval.py:72 SITE_TIERS
The test directories tests/{api,capture,context,reason/expert,scripts} exist, and every test file named in start_now is new. If the session limit is tight, run at most 6 builders at once (memory: fan-out burns the session limit). Drop S07.U1 and S04.U1 first.

Corrections that change the plan:
1. F1's '18 Oct deploy' is not supported. c501eec9 first reached origin/harsh/mvp in the 21 Oct 16:20 UTC push (869 commits), and 480f7cd4 says prod ran 10 Oct code on 19 Oct. The real deploy date is a Harsh fact (S01.U3).
2. Migrations end at 0250, not 0249. 0250 is claimed three times, so every new migration in this plan says '<next free, >=0251>' and gets its number at build time.
3. The 25 migrations 0191–0250 are unverified in production, not just 0243–0250 (S02.U2).

Dependency conflicts resolved:
- goals-g009-d1-d2-d8 says it depends on l2-a2-a3, but the goal decisions do not need the L2 cutover. S26 can run in parallel; only S29 (the L2 proposer) needs S24/S20.
- surfaces-question-and-team-cards says it depends on goals-c8, but its own fix says to do it before G6 moves the board. So S36 comes before S31.
- l2-held-card-engineer-template depends on the STEP-13b decision because both edit verify.py and claim_check.py, so S20 is not start-now.

Standing rules for every unit:
- Each code unit gets its own tests plus a mutation proof with a clean baseline and PYTHONDONTWRITEBYTECODE=1.
- Root and platform guards run per group of 2–3 units, and full suites run in CI.
- One writer per file. Shared hot files are serialised: api/routes.py goes S03.U1 → S02.U5 → S10 → S14.U2 → S17.U3 → S34.U1 → S35.U3 → S39.U1, and reason/domain_shadow.py goes S18.U1 → S18.U4 → S24.U2 → S25.U4 → S34.U2.
- Dashboard and Mac changes are a clickable dummy first, then Rohit's approval, then real files. A 'ha' to a plan is not a go.
- The L3 folder waits for Rohit to open L3.
- Never repair distinct_days before ADR-10, and calibration_apply stays off (D13).
- Founder golden cases cannot name Antler or Theresa (REAL_NAMES), so F72 is a synthetic analogue.
- Paid passes always start with 1–2 probe calls. Thinking eats max_tokens on Claude 5.

Production SQL is not run in any start-now unit. S01.U1 only writes the read-only runner, and Rohit's permission gates the run (F6).

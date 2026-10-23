# 10 · Unit briefs: paste one into a coding agent, and it can build the unit cold

**Written for:** Harsh, to hand units to coding agents; and the agents themselves.
**Covers:** every unit this folder adds (`U12-01` … `U12-21`) and the 07 units it details (`N1a`, `N1b`, `N2`, `N4`, `N5`). Units that already exist in GeniOS-011 keep their own spec in [GeniOS-011 02-PLAN](../GeniOS-011/02-PLAN.md).

---

## The preamble every brief starts with (paste it too)

```
You are building ONE unit of GeniOS (repo github.com/themoronss/genios-brain, Python package genios_engine/).
Base: create your own git worktree from origin/speedrun008 (NOT origin/main, which is ~800 commits behind):
    git fetch origin speedrun008 && git worktree add ../wt-<unit> -b g012-<unit> origin/speedrun008
Rules:
 1. Change only the files the brief names. If you must touch another, stop and report why.
 2. Write the test first; it must fail on the base and pass with your change.
 3. Mutation proof: revert your core change (one line or one function), run your test, see it RED,
    restore it byte-identical (check with `cmp` against a saved copy), see it GREEN.
    Run with PYTHONDONTWRITEBYTECODE=1 so a restored file is not shadowed by a stale .pyc.
 4. Python 3.11 syntax (CI and production run 3.11): check with
    python -c "import ast,sys; ast.parse(open(sys.argv[1]).read(), feature_version=(3,11))" <file>
 5. Imports: one imported name per line (`from x import (\n    a,\n    b,\n)`); a tuple of names on one
    line is invisible to the dependency guard.
 6. Run your own tests, the folder they live in, and `pytest tests/test_*.py tests/platform -q` (the
    root guards). The full suite runs in CI; do not create scratch databases beyond what your tests need.
 7. Tests use synthetic data only. Never a real person, company or address (the REAL_NAMES rule).
 8. No model calls in tests; a recorded or stub client only. No paid call at all without an explicit
    spend yes from Rohit in your brief.
 9. A migration takes the next free number at the time you commit (`ls migrations | tail`). 0252 is
    claimed by S34.U3 (cards_copy).
10. Commit once: "G012 <unit>: <what is now true>". Do not push to speedrun008 yourself unless told;
    push your branch and report.
Report back: the commit SHA, the files changed, the test names, the mutation you applied and its red
output (one line), anything you found that the brief did not expect.
```

---

## U12-01 · An expired org is never silent

- **Why:** since `7075014c` the scheduled sweep skips an org whose plan expired (`api/routes.py:1042-1077` `_plan_expired`, used at `:1211-1214`; the org is removed from the L2/L3/L5 pass at `:1289-1290`). Nobody is told. The founder's own org stopped this way on 21 Sep and nobody noticed for a month.
- **Read first:** `api/routes.py` 1042-1077, 1200-1320; `platform/daily_health.py`; `platform/billing.py:338` `expiry_state`; `platform/ops_alert.py` (or wherever `ops_alert` is defined: `grep -rn "def ops_alert" genios_engine`).
- **Change:**
  1. When `_plan_expired` skips an org, call `ops_alert` once per org per day: "org <id> skipped by the sweep: plan expired since <date>". Use the same once-a-day key pattern as `daily_health`.
  2. Add `plan_state text` to `daily_health` (new migration, additive, `add column if not exists`) and fill it with `expiry_state(...)` for each org row.
- **Do not touch:** the gate logic itself (S02.U5 owns it, on branch `g011-S02U5`).
- **Tests:** `tests/platform/test_an_expired_org_is_not_silent_pg.py`: an org set expired gets exactly one alert across two sweeps on the same day, and `daily_health.plan_state = 'expired'`; an active org gets none.
- **Mutation:** remove the `ops_alert` call → red.
- **Done when:** both tests green; the migration applies on a fresh DB.

## U12-02 · `activate_tenant.py` applies what it says

- **Why:** `scripts/activate_tenant.py` `_plan_for` (`:155-179`) only appends L4 features listed in `PLAN` (`:51-61`), so `--features expert_review,l2_reasoning,l2_cards` passes validation and is silently dropped. GeniOS-011's runbook told Harsh to use it for exactly those three.
- **Read first:** the whole script; `platform/l4_activation.py` (`L4_FEATURES`, `PRECONDITIONS`, `NOT_DEFAULT_ON`, `activate`); `platform/l3_activation.py` (`require_domain`).
- **Change:** `_plan_for` accepts every feature in `L4_FEATURES`; it orders the requested ones by `PRECONDITIONS` (expert_review → l2_reasoning → l2_cards); `--domains` accepts `founder_office`; a requested feature or domain it will not apply exits with code 2 and names it. The dry run prints every step.
- **Tests:** `tests/scripts/test_activate_tenant_plan.py`: `--features expert_review,l2_reasoning --dry-run` prints both in order; `--features l2_cards` alone prints its missing preconditions; an unknown feature exits 2.
- **Mutation:** restore the `PLAN` filter → red.

## U12-03 · A judged file is always decided

- **Why:** `reason/runner.run_all` calls `shadow_compile` (which decides covered files first, `_decide_covered_files` `domain_shadow.py:780-972`) only under `if live_compile or l3_domains or l1_seam_enabled(engine, org_id):` (`runner.py:2029`). An org with no activated L3 domain and no `l1_semantic_activation` row gets correct judgments and no cards, silently.
- **Read first:** `reason/runner.py` 1923-2126 (and 1842-1920, `WHY_NO_CARD`); `reason/domain_shadow.py` 547-1000, 1328-1760.
- **Change:** when `covered` is non-empty, decide the covered files even if the guard is false (either call `_decide_covered_files` directly, or widen the guard). If a covered file still gets no decision, count it as `covered_not_decided` in `WHY_NO_CARD`.
- **Tests:** `tests/reason/test_a_judged_file_is_decided_without_compile_flags.py`: an org with no L3 activation, no L1 row, `use_domain_compiler=False`, one covered file → a card or a counted reason.
- **Mutation:** restore the guard → red.

## U12-04 · Evidence fetchers use the connection's real window

- **Why:** `api/routes.py:3596-3611` `_need_fetchers` builds `Connection(config={})`, so the window fetcher uses the default 60 days even after the connection's window is widened.
- **Read first:** `api/routes.py` 3590-3620 and `_saved_connection_config` (`:3754`); `capture/acquire/need_executor.py:224-247`; `capture/connectors/backfill.py:34-118`.
- **Change:** build the fetcher's `Connection` with `_saved_connection_config(...)`.
- **Tests:** `tests/api/test_need_fetchers_use_the_saved_window.py`: a connection with `capture_scope.backfill_days=365` → the window fetcher's Gmail query contains `newer_than:365d`.
- **Mutation:** back to `config={}` → red.

## U12-05 · Founder mail classes in the gate

- **Why:** intro platforms send personal intros through a bulk mailer (N-02 List-Unsubscribe archives them); programme and government portals send from no-reply senders (N-03/N-06); the batch judge has no application-status class.
- **Read first:** `capture/gate/relevance.py` (`_GATE_PROMPT` `:73`, `_GATE_BATCH_PROMPT` `:113`, `prime` `:266-293`, `classify` `:328-353`, `DROP_BELOW_RELEVANCE` `:17`, `RESCUE_AT` `:23`); `capture/gate/rules.py` (`noise_rule` `:397-464`, `SOFT_NOISE`/`FINAL_NOISE` `:249-250`, `whitelist` `:323`); `capture/gate/gate.py` (`_overruling_keep` `:53-66`, `run_gate` `:162-261`).
- **Change:**
  1. Both prompts gain an ALWAYS KEEP class: "the status of an application, programme, grant or registration the company made".
  2. A reviewed list `capture/gate/intro_platforms.py` (one entry to start; domains only), and in `_overruling_keep`: an N-02 archive is overruled when the sender domain is on that list, or the batch verdict's class is introduction, at any relevance ≥ `DROP_BELOW_RELEVANCE`.
  3. Bump the gate version, so S06.U1's re-judgment covers old verdicts.
- **Tests (synthetic mail only):** a platform intro with List-Unsubscribe → kept; a newsletter from the same mailer software and a different domain → archived; "your application is incomplete" from a no-reply portal → kept by the class (stub judge returns the class); an old verdict with the previous gate version is filed for re-judgment.
- **Mutation:** one per rule: remove the platform overrule → red; remove the class from the prompt's class list (the parser) → red.
- **After merge:** measure on the production model with S07.U3 (Rohit's spend yes).

## U12-06 · The open lane is read

- **Why:** what fits no signal type goes to `unclassified_observations` (migration 0079, `capture/semantic/open_lane.py`) and no rule reads it.
- **Change:** a daily count by proposed label into `daily_health` (a jsonb column, top 20), and a staff route `GET /admin/open-lane/{org}` returning the counts (never the text).
- **Tests:** planted observations with 3 labels → counted per label.
- **Mutation:** skip the count → red.

## U12-07 · A meeting is an event the chain can use

- **Why:** 0 of 22 past meetings reached the graph as anything usable (4 Oct). Calendar events take the structured path (`capture/structured/registry.py:203-218` `gcal.event.v1`, `mapper.py:392,410-416`); there is no meeting signal type; `context/meeting_touch.py` (`_MEETINGS` `:81`) drops internal and cohort meetings; `lane_health` lists `meeting` dormant.
- **Depends on:** S12.U2 (the `meeting` type exists).
- **Read first:** `capture/connectors/calendar.py:66-191`; the registry and mapper; `capture/esqe/detector.py`; `context/meeting_touch.py`; `context/meeting_situations.py`; `context/correlation.py` (`choose_anchors`).
- **Change:** map `gcal.event.v1` with an external attendee to `meeting` (intent `schedule` → `meeting`), counterparty = the external attendees; correlate the meeting event into each external attendee's file; `meeting_touch` reads meetings where we are organizer or attendee and at least one attendee is external, past and coming.
- **Tests:** a synthetic calendar of 22 past external meetings → 22 meeting events in files; a past meeting with no mail after it within the kind's gap → one `meeting_without_follow_through` situation; an internal-only meeting → none.
- **Mutation:** drop the external-attendee mapping → red.

## U12-08 · An ask closed only by "replied" stays open for judgment

- **Why:** any reply closes every open ask on the thread (`context/vocabulary.py:263-274`, `context/open_loops.py:66-77`); `answered` only when the message kind is in `kinds.yaml` `discharges`, else `replied`. "What is your ARR?" → "will send soon" is closed.
- **Change:** a new closure state `replied_unanswered`: off the awaiting-their-reply list; on the file's dossier at every review (not only since the last), until L2 decides (U12-16). Dossier: `reason/expert/dossier.py` `_asks_closed` `:361-371` reads it.
- **Tests:** "what is your ARR?" → "will send soon" → `replied_unanswered`, shown in the next two dossiers; → "ARR is $X" → `answered`.
- **Mutation:** map `replied` back to closed → red.

## U12-09 · The replay harness pins knowledge time

- **Why:** S16.U3 (branch `g011-S16U3`, `bd260f0a`) makes the snapshot read `as_of`. Golden replays judge at past sweep instants, but `recorded_at` is wall-clock, so every L2 snapshot lost its edges (10 of 10 had 1 node, 0 edges). Separately, overlapping golden runs share one global connection id and steal each other's mailbox.
- **Read first:** `tests/replays/engine_runner.py`; `reason/l2/snapshot.py`; `context/bounded_read.py`; the S16.U3 diff (`git show bd260f0a`).
- **Change:** the harness stamps every graph write's `recorded_at` with the replay's sweep instant (an injectable clock the store reads), and gives each run its own connection id.
- **Tests:** with S16.U3 applied on top, F02–F04 snapshots have their edges; two runs in parallel do not see each other's events.
- **Then:** merge S16.U3.

## U12-10 · A promoted archive gets filed

- **Why:** `context/backfill.backfill_correlations` considers only `outcome='emitted'`, and archived mail took the METADATA lane with no correlation. A mail promoted later (by `scripts/promote_archived.py --apply`, or by S06.U1's re-judgment) is never filed until someone re-runs a backfill.
- **Change:** when promotion turns an archive into an emitted event, enqueue it for `correlate_event` in the same transaction (or mark it pending for `process_pending`).
- **Tests:** a synthetic archived intro, promoted → in its counterparty's file after one `process_pending`.
- **Mutation:** drop the enqueue → red.

## U12-11 · The automatic replay never rebuilds destructively

- **Why:** `context/backfill.backfill_layer2` (`:428-447`) calls `backfill_correlations(rebuild=True)` whenever `deal_nodes_created` is non-zero, including the automatic history replay (`api/routes.py:777-778`). A rebuild deletes every situation, including human resolutions.
- **Depends on:** S14.U2 (stable situation ids).
- **Change:** re-correlate only the anchors of the created deal nodes; keep `rebuild=True` for the explicit staff route only.
- **Tests:** a replay that creates one deal node → only that deal's file changes; a human-resolved situation elsewhere is untouched.

## U12-12 · The five deferred Founder Office capabilities get triggers

- **Why:** only `investor_relationship`/`investor_contact` route (to `investor_relations`); `program_applications`, `introductions`, `registrations_and_recognition`, `offers_and_joining`, `external_meetings` are `deferred_capabilities` (`no_runtime_trigger`).
- **Depends on:** S12.U2 (the new signal types), S23.U2 (labelled admission).
- **Read first:** `Domain Expertise/Founder Office Expertise/` (domain.yaml, the registry, the six capability folders); `packs/compiler/capability_resolver.py:274-298, 820-823`; `reason/domain_shadow.py:1146-1153, 1913-1917` (`misfiled_kind`).
- **Change (Plane D files + resolver):** route `application_status` → program_applications; `introduction` → introductions; kind `compliance` portal mail → registrations_and_recognition; kind `hiring` offers → offers_and_joining; `meeting` with an external attendee → external_meetings. Program and compliance files stop being `misfiled_kind`.
- **Tests:** one synthetic case per route → the right capability; `deferred_capabilities` is empty.

## U12-13 · A customer (prospect) work kind

- **Why:** `WORK_KINDS` (`contracts/company_brief.py:48`) has no sales/customer kind, so `KIND_CAPABILITY` (`playbook_reader.py:48-56`) gives a design-partner outreach file no playbook while Sales is off.
- **Depends on:** Rohit names the kind (default `customer`).
- **Change:** add the kind; map it to Admin's outreach play; the brief drafter may propose it.
- **Tests:** a prospect file's dossier carries a playbook.

## U12-14 · Judged files keep their slots across the day

- **Why:** `_daily_allowance` (`reason/domain_shadow.py:165-186`) = 7 × seats − `_budget_used` (`reason/runner.py:551-555`), and `_budget_used` counts every signal of the day from any lane. A morning sweep's template cards spend the allowance before an afternoon judgment.
- **Change:** split the allowance: `judged` (default max(3, half)) and `formula` (the rest); formula lanes (compiled and legacy) spend only `formula`; judged files spend `judged`, then `formula`. `_budget_used` counts per lane from `signals.output_lane`.
- **Tests:** 7 formula signals at 09:00, one judged file at 15:00 → the judged file gets a card.
- **Mutation:** one shared pool → red.

## U12-15 · The "what else is true today" dossier block

- **Why:** the judgment reads one file; it cannot state the one cross-thread fact that changes the move (field 13 of the card contract).
- **Read first:** `reason/expert/dossier.py` (`read_parts` `:759-813`, `SECTIONS` `:67`, the caps); `reason/l2/dossier.py`; `contracts/expert_review.py`; `contracts/claim_check.py`.
- **Change:** a bounded block (≤ 2,000 characters): the founder's calendar for the last 3 and next 7 days (titles, attendees, a flag when this counterparty attends); up to 5 other files linked to the same goal (after S30) or in-motion line, one line each; open discrepancies on the tenant node. The output schema gains `cross_fact` (one sentence with the source id it cites), checked like every other sentence.
- **Tests:** a synthetic founder with an investor file and a programme review on today's calendar → the block carries the review; a stub judgment's `cross_fact` citing a non-printed id is refused by the claim check.

## U12-16 · The judgment says whether a reply answered the ask

- **Depends on:** U12-08.
- **Change:** output `asks: [{ask_id, answered: yes|no|partly, quote}]` for every `replied_unanswered` ask printed; verify checks the quote; `no`/`partly` keeps the ask open as `reply_owed` and the move becomes "answer what they asked"; `yes` closes it `answered`.
- **Tests:** "what is your traction?" → a reply with no number → a `reply_owed` move naming the unanswered ask.

## U12-17 · A catch-up budget after a resync

- **Why:** R-7 and R-9 each have $2/day and R-7 reviews ≤ 10 files per pass. After a 365-day resync, every in-motion file needs a first look at once.
- **Change:** a per-org, time-boxed override (a row: org, until, daily_budget, files_per_pass) set by Harsh; the sites read it before `OWN_BUDGETS`; nearest deadline and in-motion lines first.
- **Tests:** with the override, 40 first-look files are reviewed within 3 simulated days; without it, 10 per pass; spend never exceeds the override.
- **Spend:** the override's numbers are Rohit's yes; the default proposal is 3 days × $10/day per site.

## U12-18 · The lane is a chip, not a prefix

- **Why:** `deliver/pipeline.py:1003` → `render.state_not_command` prefixes "Needs a decision — " and leaves about 42 characters for the subject.
- **Change:** return `state_label` as a field; stop prefixing new cards; the 60-character cap applies only to legacy cards without `copy`.
- **Tests:** a review-level card's headline has no prefix and its `state_label` is "Needs your decision".
- **Coordinate:** the dashboard and the Mac app must read `state_label` (N3a).

## U12-19 · The list carries what the page needs

- **Change:** `deliver/store.py` `queue()` returns `category`, `goal_refs`, `copy.subject`, `copy.summary`, `label`, `state_label`.
- **Tests:** `GET /cards` returns them; a card without `copy` falls back to `headline`.

## U12-20 · Founder defaults on, after the gate

- **Do not build before:** Gate 7 has passed on Rohit's org and on two more design partners ([09](09-STEPS.md), [12 §A](12-PRODUCTION-READY.md)).
- **Change:** `platform/l4_activation.py` `NOT_DEFAULT_ON` (`:167-203`) loses `expert_review` and `l2_reasoning`; `platform/intelligence_onboarding.make_tenant_live` (`:222`) activates `founder_office` when the setup says "founder-led" (a field the setup form writes).
- **Tests:** a tenant made live with "founder-led" has the three switches on; one without it has Admin only.

## U12-21 · Self identity at connect

- **Change:** when a Gmail connection is created, add the mailbox address, and its domain unless it is a public mail host (the canonical list of S08.U2), as "us" in the brief, pending the owner's confirmation.
- **Tests:** `founder@acme.example` → `acme.example` is us; `someone@gmail.com` → only the address.

## N1a · The founder's self-claims from sent mail (capture half)

- **Why:** `ExtractionResult.amounts` is filled, but `context/pipeline.py` never writes amounts; there is no own-claim lane. Card `p1` (four different traction numbers) is impossible.
- **Change:** new `capture/extract/self_claims.py`: for **outbound** messages only (`capture/pipeline.py:515` `_envelope_direction`), extract claims about us: metric (from the reviewed vocabulary of S12.U4: `arr`, `mrr`, `customers`, `partners`, `pilots`, `users`, `revenue`; else `other.<word>`), value, unit, period, date, recipients. Rules and the existing extraction first; a model only for the sentence-to-metric mapping, with a recorded client in tests.
- **Tests:** "we're at $10k ARR" in a sent mail → one claim; the same sentence in a received mail → none.
- **Mutation:** drop the outbound filter → red.

## N1b · Conflicting own claims are one conflict (graph half)

- **Depends on:** N1a.
- **Change:** write claims as `company.<metric>` on the tenant node at rank 2 with source and recipients (`context/pipeline.py`, outbound leg); in `context/graph_store.py` `fact_write_action` (`:40-71`), for `company.*` only: an equal-rank differing value within 120 days → keep both and `write_discrepancy`; a reading `information_conflict` on the tenant node naming who received which value.
- **Tests (`tests/context/test_own_claims_conflict_pg.py`, golden F73 synthetic):** two sent mails "$10k ARR" and "$5K MRR" → one conflict with both values and recipient counts; a third identical value → no new conflict; a received number → no claim.
- **Mutation:** remove the equal-rank branch → red.

## N2 · Categories

- **Change:** `Domain Expertise/Admin Expertise/registry/category-map.yaml` (new, reviewer stamp): categories (Rohit's eight as Admin's default) and the capability → category and work kind → category maps; compile it in `packs/compiler/`; set `cards.category` in `deliver/card_builder.py` and `company_goals.category` (after S28.U1); return it from `GET /cards` and `GET /v1/goals`.
- **Tests:** every map entry names an existing capability; an unmapped capability → `null`.
- **Before building:** the architecture amendment for `category` (Rohit's yes, Rule 1.4).

## N4 · A bounce is "never arrived"

- **Why:** `context/delivery.py:70` `record_delivery_failure` writes an observation and `context/waiting.py:199-230` retires the waiting facts, so the awaiting-reply card disappears and nothing replaces it.
- **Change:** a reading `delivery_failed` in `context/outreach_situations.READINGS`, anchored on the recipient's file (S15.U1), one per recipient, carrying the original's subject and date; an Admin `domain_spec` type; a Plane D playbook line; the waiting situation closes as `superseded_by_bounce`.
- **Tests (`tests/context/test_a_bounce_is_a_card_pg.py`):** a planted mailer-daemon notice → one `delivery_failed` situation naming the recipient; a second bounce on the thread updates it; the gate keeps DSNs.

## N5 · Preview parity

- **Change:** `scripts/preview_parity.py`: reads live `GET /cards?state=open` and `GET /v1/goals` (or a read-only DB) for an org, and an expected list from `PREVIEW_EXPECTED_PATH` (a file outside the repo); prints appeared / missing / extra; for each missing card, the file's `why_no_card` (`GET /v1/workstreams/{file_id}`); exit 0 only at ≥ 18/20 cards and 10/10 goals.
- **Tests:** a synthetic expected list and a stub API.

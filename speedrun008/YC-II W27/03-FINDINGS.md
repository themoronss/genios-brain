# 03 · Findings — what is broken, what only looked broken, what exists, what is missing

**Written for:** everyone. **Measured:** 2026-10-05, `speedrun008` @ `2dc61dac` and production
(read-only, metadata). **Re-measured the same day after the merge** (`8a472b81`, the `STEP-00`
re-do): F26–F29, E8, and the corrections to F24 and E4. A finding is never deleted; a correction
is a new line that says what it corrects.

---

## A · Defects — live, verified

| # | Defect | Evidence | Fixed in |
|---|---|---|---|
| F01 | The first gate **deletes**: a rule-dropped mail keeps no body and can never be re-fetched | `[CODE]` `capture/pipeline.py:105-107, 1567-1640`; `[PROD]` 258 mails | `STEP-03`, `STEP-08` |
| F02 | The AI filter judges one mail with no company context, and its prompt names *"automated matchmaking"* and *"self-service"* as junk | `[CODE]` `capture/gate/relevance.py:65-122`; `[PROD]` Khushi (247VC), Troy (a16z), Hub71, iHub, IIITD-IC ×3, DPIIT 30 Sep — junked | `STEP-03`, `STEP-07` |
| F03 | Memory is gated on a qualified signal | `[CODE]` `context/runner.py:244-254`; `[PROD]` ~27 of 395 mails in memory | `STEP-05` |
| F04 | A meeting becomes a deadline and vanishes when the deadline expires | `[CODE]` `capture/structured/mapper.py:392-394` → `capture/esqe/detector.py:347-351` → `capture/esqe/lifecycle.py:357-375`; `[PROD]` 18 of 20 expired, 2 meeting nodes | `STEP-05` |
| F05 | Every recovery path only flips `outcome` | `[CODE]` `capture/parked/drain.py:151-154`, `api/routes.py:2453-2473`, `refetch.py:849-851`, `recapture.py:262-274` | `STEP-05` (new rows: `harsh/mvp` `adb04093`) |
| F06 | The closed vocabulary has no word for a pitch, an application, an intro or a program | `[CODE]` `contracts/signal.py:210-299`; `[PROD]` investor outreach typed `contract_renewal` | `STEP-09` |
| F07 | The model re-decides every situation every sweep; every key and cache moves with `evaluation_time` | `[CODE]` `reason/store.py:785-802`; `reason/llm_decision_maker.py:667-697`; `[PROD]` ~1,400 calls a day, 113 / 118 flips | `STEP-02` |
| F08 | A DEFER expires the card | `[CODE]` `reason/runner.py:1116-1125, 1168-1175, 1382-1410` | `STEP-02` |
| F09 | The card's score is the model's utility — the Atlas's RULE 02, violated | `[CODE]` `reason/domain_shadow.py:361`; `reason/llm_decision_maker.py:798-808` | `STEP-12`, `06` D1 |
| F10 | The decider's context: four messages, no company, no history, no prior outcomes; its rationale is read by nothing; `output_lane` left NULL | `[CODE]` `reason/llm_decision_maker.py:413-593, 813-846` | `STEP-12`, `STEP-13` |
| F11 | Shadow runs pay for model calls whose decisions are discarded | `[CODE]` `reason/orchestrator.py:252-263`; `reason/domain_shadow.py:1178-1193` `[inference]` | `STEP-02` |
| F12 | `fundraising` and `general` can never be live; fundraising is aliased to Sales | `[CODE]` `reason/domain_shadow.py:512-526`; `packs/compiler/capability_resolver.py:35-47` | `STEP-11` |
| F13 | "Who is us" is decided four ways; you are the subject of cards | `[PROD]` *"Send Mr Rohit Swerashi your traction metrics"*; `[CODE]` `context/backfill.py:601` | `STEP-04` |
| F14 | Boardy can never be an agent sender; no tenant allow-list exists | `[CODE]` `capture/connectors/composio.py:575`; `capture/gate/rules.py:274, 345` (read, never written) | `STEP-03` |
| F15 | Nine of eleven card-expiry sites write no event; the compiled lane's outcomes are discarded | `[CODE]` `01` §4; `reason/runner.py:1494-1498` | `STEP-06` |
| F16 | One subject becomes many cards | `[CODE]` `deliver/pipeline.py:381`; `[PROD]` the offer to Khushi, six cards | `STEP-14` |
| F17 | The card copy prompt carries real names and a salesperson persona | `[CODE]` `deliver/render.py:750, 767` | `STEP-14` |
| F18 | A fallback asserts money where there is none | `[PROD]` *"nsrcel — a dated payment obligation is open"*; the corpus gate is any `commitment.due_at` | `STEP-14` |
| F19 | Screen reminders are built and hidden | `[CODE]` `reason/moments/guards.py:68-71`; `[PROD]` 65 hidden | `STEP-14`, `06` D8 |
| F20 | Bounces never become delivery failures | `[PROD]` 5 junked, 8 parked | `STEP-10`, `STEP-18` B6 |
| F21 | A 30-day TTL on emitted payloads strands any event not drained within a month | `[CODE]` `capture/pipeline.py:179-187`; `context/runner.py:242` | `STEP-03` |
| F22 | Intro, information, approval and investor-update requests never open a loop | `[CODE]` `contracts/open_loop.py:24` vs `observations/kinds.yaml` | `STEP-09` |
| F23 | The golden replays cannot fail or pass on the engine — the harness never calls it | `[CODE]` `tests/replays/test_golden_replays.py:34-48` | `STEP-01` |
| F24 | The narrator truncates at its token ceiling | `[PROD]` `l4_bundle` 29 of 55 failed on 3 Oct, all at 1,400 | `harsh/mvp` `5ebfef8e` (cap 2,400) — verify after `STEP-00` |
| F25 | The sixteen bugs of `STEP-18`, B1–B16 (B17–B19 came later: F27–F29) | per row there | `STEP-18` |
| F24 · re-measured | ⚠️ **not yet verified.** All eight narrator failures of 4 Oct stopped at exactly 1,400 tokens, the last at 11:30 UTC — before `5ebfef8e` was committed (14:29 UTC). No narrator call has run since. The 24 h ceiling check in `pipeline_health` therefore passes on no data for this lane | `[PROD]` `baseline/2026-10-05/production_state.txt` `@narrator_ceiling` | unchanged — re-run the probe after the next narrator call |
| F26 | The database tests had never run on this branch. Run, **50 fail** — none caused by the merge | `[TEST]` `baseline/2026-10-05/suite_with_database.txt`; attribution on three trees in `STEP-00` §4.2 | `STEP-17` §3.0; 27 of them are `STEP-18` B2 |
| F27 | The funnel never records a zero decision: every sweep that emitted nothing reads *"nobody looked"* — and the stage counts the rule lane only | `[CODE]` `reason/runner.py:860, 1364`; `api/routes.py:774-775`; `[PROD]` 64 sweeps since 3 Oct, `decision_emitted` written in 3, values 1–4, never 0 | `STEP-18` B17 → `STEP-06` §3.2 |
| F28 | A mail whose extraction did not parse waits forever: the extractor's four park codes are in no drain set, and the funnel calls the mail *kept unread* | `[CODE]` `capture/semantic/extractor.py:199-210` vs `capture/parked/drain.py:41-77`; `[PROD]` 2 mails pending since 3 Oct, 0 attempts | `STEP-18` B18 → `STEP-06` §3.1 |
| F29 | **No Gmail attachment is read.** Composio refuses every fetch — *"Missing required fields: file_name"* | `[CODE]` `capture/connectors/composio.py:298-299`; `[PROD]` 88 of 88 stored errors; 50 dead-lettered, 38 pending, 0 recovered | `STEP-18` B19 |

## B · False alarms — things that looked wrong and are not

| # | Looked like | Actually |
|---|---|---|
| B1 | *"The model is not used"* | it makes ~2,000 calls a day — in the wrong places |
| B2 | *"Screen data never reaches the graph"* (memory, 4 Oct) | follow-ups **are** written as graph observations (`reason/moments/screen_memory.py:64-102`); the moments built from them are what is hidden |
| B3 | *"Cards stopped on 25 Sep"* | superseded — 22 cards since the 3 Oct re-capture |
| B4 | *"Migrations 0186–0190 are unapplied"* | applied 2 Oct |
| B5 | *"Boardy's mail is bulk"* | each intro is one-to-one with a named contact in `To`/`Cc`; the unsubscribe header is the sending service's, not a mailing list's |
| B6 | *"R-6 mostly records `unknown` without calling"* (this folder's first draft of `01`) | ⛔ corrected: R-6 has **never** called a model in production — its feature is not default-on; 1,839 rows, 0 proposals |
| B7 | *"Sales and Support are live by default"* (memory, 4 Oct) | true on `speedrun008`; on `harsh/mvp` both are `default_on: false` (`9a51d0ea`) and production's `l3_activation` holds Admin only |

## C · Already built — reuse, do not rebuild

| # | What | Where | Used by |
|---|---|---|---|
| C1 | the deterministic lane router | `reason/output_lane.py` | `STEP-13` |
| C2 | the bounded, revision-returning graph read | `context/bounded_read.py` | `STEP-12` |
| C3 | the R-site runner, gate, durable cache and budget | `reason/llm_sites.py`; `reason/bundle/gate.py` | `STEP-12` |
| C4 | replay-safe injection of a model's reading | `reason/llm_interpretation.py:250-269` → `reason/replay.py:145-201` | `STEP-12` |
| C5 | the persisted-interpretation table | `situation_interpretations`, `context/interpretation_store.py` | `STEP-12` |
| C6 | counterparty reply cadence, waiting, follow-up count | `context/waiting.py` | `STEP-10` |
| C7 | 12 trended metrics, trends, anomalies, cohorts, peer baselines | `context/analytic/` | `STEP-10` |
| C8 | relationship history facts | `context/correlation_history.py` | `STEP-10`, `STEP-12` |
| C9 | the timeline, cadence, cost and do-nothing units | `reason/reasoners/` | `STEP-10`, `STEP-12` |
| C10 | a deterministic what-if engine | `reason/simulation.py` | `STEP-10` §3.11 |
| C11 | counterparty × domain episodes with members | `context_correlations` | `STEP-09` |
| C12 | open loops with who owes them | `context/open_loops.py` | `STEP-09` |
| C13 | state readings — awaiting response, campaigns, cohorts, conditions, dependencies | `context/outreach_situations.py` | `STEP-09` |
| C14 | meeting lifecycle and meeting prep | `context/meeting_lifecycle.py`; `reason/meetings/prep.py` | `STEP-05`, `STEP-15` |
| C15 | the evidence-need queue and its executor | `context/evidence_needs.py`; `capture/acquire/need_executor.py` | `STEP-13` |
| C16 | an approval queue for learned preferences | `user_model_proposals` + `api/usermodel_routes.py` | `STEP-07`, `STEP-16` |
| C17 | the summary ladder, daily digest, book-level re-rank, decision brief | `executive/summary.py`; `reason/brief_ranking.py`; `executive/brief.py` | `STEP-15` |
| C18 | the pipeline-health gate | `scripts/pipeline_health.py` (`harsh/mvp`) | `STEP-00`, `STEP-17` |
| C19 | the real-Postgres test seam | `tests/conftest.py:79-138` | `STEP-01`, `STEP-17` |
| C20 | relay detection, introducer / introduced roles | `capture/gate/rules.py:121-190`; `context/pipeline.py:416-424` | `STEP-03`, `STEP-09` |

## D · Genuinely missing

| # | What | Built in |
|---|---|---|
| D1 | the expert judgment pass | `STEP-12` |
| D2 | the material-change fingerprint and gate | `STEP-02` |
| D3 | a company brief, and any prompt that carries one | `STEP-07` |
| D4 | workstreams with stages, roles and request-scoped asks | `STEP-09` |
| D5 | expertise for fundraising, programs, intros, compliance, hiring | `STEP-11` |
| D6 | attention tiers in place of deletion | `STEP-03` |
| D7 | your own reply time; per-wave and per-connector rates; stage dwell; coverage on every absence | `STEP-10` |
| D8 | a claim and number check on a model's reasoning | `STEP-13` |
| D9 | one living card per subject | `STEP-14` |
| D10 | a morning brief built on judgments | `STEP-15` |
| D11 | an exam that drives the engine | `STEP-01` |

## E · Open questions — each with the person who can answer it

| # | Question | Owner |
|---|---|---|
| E1 | Which address is the founder's? | ✅ answered 2026-10-05: `mrrohitswerashi@gmail.com`, the source of Gmail and Calendar (`06` D6) |
| E2 | What did the Startup India mails of 24–30 Sep say? | Rohit — content reads are blocked for me |
| E3 | Is saka.vc a fund? | Rohit |
| E4 | Which commit is production running? | Harsh — ⚠️ partly answered 2026-10-05: production passes `pipeline_health` 7/7, so the 2–4 Oct fixes are live; the exact commit is still his to confirm |
| E5 | After the merge, do Sales and Support stay `default_on: false`? | Harsh, Rohit (`06` D2) |
| E6 | May I read email text for the golden labels — a permission rule, or will you run those queries? | Rohit (`06` D12) |
| E7 | The 11 Aug bounce reports — which addresses failed? | answered by `STEP-10` §3.5 once bounces are parsed |
| E4 · corrected | ⚠️ 2026-10-05, the `STEP-00` re-do: E4's *"so the 2–4 Oct fixes are live"* claimed more than a 7/7 pass shows — the checks read production's data, not its commit. Measured per fix: `d4e035bb` is visibly live (the refetch errors written on 5 Oct carry their reason); `5ebfef8e`'s cap cannot show yet (F24 · re-measured). The commit is still Harsh's to confirm | Harsh |
| E8 | Merge `origin/rohit-yc-brain`? 19 commits, 22 Aug – 9 Sep, **no code**: it moves 81 files from `Rohit_Updates/` into `Rohit_Updates (Version 2)/Version 1 Updates/`, adds one failure-analysis document, `qa-contract.yaml` (38 lines) and `tree.yaml` (656 lines). A dry-run merge conflicts in `tree.yaml` and on two `00-CORRECTIONS-2026-10-01.md` files this branch added inside a folder that branch renamed | Rohit |

## F · Numbers, with their sources

Every number below was measured on 2026-10-05 against production, read-only; *snapshot* means
11:03 UTC.

| Number | Value | Query (abridged) |
|---|---|---|
| gmail events captured | 616 | `source_events where source='gmail'` grouped by `outcome, object_type` |
| messages (non-superseded) | 395 | `object_type='email_message' and outcome<>'superseded'` |
| S1-dropped with no content | 258 | dropped ⨝ `prepared_content` / `raw_payloads` → none |
| S2 `llm_junk` | 69 | emitted with `event_trace` S2 drop `llm_junk` |
| events with an active signal | ~27 | `qualified_signals.state='active'` by event |
| meeting signals typed `deadline_stated` | 20 (18 expired) | gcal events ⨝ `qualified_signals` |
| meeting nodes | 2 | `graph_nodes node_type='meeting' and valid_to is null` |
| screen follow-ups | 102 (93 open) | `screen_followups` by `kind`, snapshot |
| hidden moments | 65 | `moments display=false, suppressed_reason='shadow'`, snapshot |
| cards | 22 (18 queued, 3 surfaced, 1 expired) | `cards` by `state`, snapshot |
| model calls a day | ~1,990 | `llm_costs`, last 3 days ÷ 3 |
| re-deciding share | 70% | `l4_llm_decision` + `l4_llm_r1` |
| R-6 interpretations with a proposal | 0 of 1,839 | `situation_interpretations` by `outcome`, `proposal<>'{}'` |
| L4 features on for the org | brief, bundle, critique, ranking_v2, roster_v2 | `l4_activation` |
| L3 domains on | admin | `l3_activation` |
| unclassified observations | 118, 0 reviewed | `unclassified_observations` |
| golden replays | 153 mutations · 150 xfail · 3 "runnable" | `[TEST]` `pytest tests/replays -q` → 33 passed, 150 xfailed |
| branch divergence | 13 / 28 → merged | `git rev-list --left-right --count origin/harsh/mvp...speedrun008`; `STEP-00` |
| `pipeline_health` on production | **7 / 7 pass** | `baseline/2026-10-05/pipeline_health.txt` |
| inbound mail by fate | 365 = 15 reached reasoning · 18 read, no signal · 67 junked · 258 deleted · 7 kept unread | `baseline/2026-10-05/workstream_funnel.txt` (`scripts/workstream_funnel.py`) |
| **Re-measured in the `STEP-00` re-do, 13:51 UTC** — statements in `baseline/production_state.sql`, output in `baseline/2026-10-05/production_state.txt` | | |
| funnel sweeps since 3 Oct 08:50 UTC | 64; `decision_emitted` written in 3 (values 1–4); `card_delivered` 0 in the last 7 that wrote it | `@sweeps_recorded`, `@funnel_per_stage`, `@funnel_last_8_sweeps` |
| L2 processing runs | 30, all `done`, 0 edge-type errors (3–5 Oct) | `@l2_processing_runs` |
| park queue | 88 attachments (50 dead-lettered, 38 pending) · 95 screen items pending, 162 recovered · 2 mails pending at extraction · 4 mails recovered | `@park_queue` |
| per-sweep decider calls per UTC day | 718 · 477 · 1,204 · 306 (2–5 Oct; 5 Oct to 13:51) | `@model_calls_by_day` |
| the database suite on the merged branch | see `STEP-00` §4.2 | `baseline/2026-10-05/suite_with_database.txt` |

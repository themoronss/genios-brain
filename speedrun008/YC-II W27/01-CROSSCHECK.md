# 01 · Crosscheck — what is actually true, measured before planning

**Written for:** Harsh and the coding agent; Rohit can read §0 and stop. **Measured:** 2026-10-05.
**Code at:** `speedrun008` @ `2dc61dac`, clean tree — line numbers are against it and will move
once `STEP-00` merges `harsh/mvp`. **Production:** org `org_e97e86f858ad48b2bbf64b8a`, read-only,
metadata only.

`[PROD]` measured on production · `[CODE]` read in the repository · `[TEST]` a test run ·
`[ATLAS]` Design Atlas v2 or the Secret War audit · `[inference]` followed in code, not run.

---

## 0 · The crosscheck in six sentences

1. **Memory is gated on a "signal"**, and almost nothing gets one: the L2 drain pulls only events
   carrying an active qualified signal, so ~27 of ~395 mails and 2 of 34 meetings reached the graph.
2. **The gate deletes.** A mail dropped by a deterministic rule keeps no body anywhere and cannot be
   re-fetched (dedup blocks it); 258 mails are in that state, including all of Startup India's and
   31 of Boardy's 35.
3. **Every recovery path is a flag flip.** Parked, junked and refetched mail is marked `emitted` and
   never re-processed — it cannot get a signal, so it can never enter memory.
4. **The model never sees a whole piece of work.** The decider sees one situation, four recent
   messages and a formula baseline, every 15 minutes, with nothing ever cached across sweeps. The
   context reasoner built for exactly this (R-6) has **never called a model in production** — its
   feature switch is not default-on — and the table it writes has no reader.
5. **History, patterns, analytics and scenarios exist as code, unused for judgment** — a timeline
   unit, cadence, delay cost, do-nothing baselines, a counterfactual simulator with no production
   caller, metric history, a bounded graph read with no reasoning caller.
6. **Harsh's branch already fixed** several downstream leaks (park routing, known senders,
   attachment errors, truncation, expired-card rebuilds); none of those fixes reaches the core —
   memory gated on a signal, deletion at the gate, the decider's context.

---

## 1 · The funnel `[PROD]`

### 1.1 Mail, 4 Aug → 5 Oct

```
gmail events captured          616   = 395 messages (non-superseded) + 133 re-reads + 88 attachments
  S1 rule drop                 258   content: NONE (no prepared_content, no raw_payloads)
  emitted                      137
    of which S2 "llm_junk"      69   prepared text gone; encrypted raw kept (90 d) → re-processable
    passed the gates            68   → L1 extraction ran on 57 → active qualified signal on ~27
  parked (attachments)          88
calendar                        34   → meeting signals typed deadline_stated: 20 (18 expired)
                                     → meeting nodes in the graph: 2
screen                         368 events (342 emitted, 26 parked) · 102 follow-ups (93 open) · 65 moments, all hidden
cards                           22   all since the 3 Oct re-capture
```

S1 drop codes: `N-06` Gmail Promotions **89** · `N-02` list/unsubscribe headers **80** · `N-03`
no-reply / automated sender **69** · `N-01` Auto-Submitted **13** · `N-04` Precedence **7**.

### 1.2 By workstream (inbound, 365 mails; grouping by sender domain is mine)

| Workstream | Mails | S1 deleted | S2 junk | Read, no signal | Reached reasoning |
|---|---:|---:|---:|---:|---:|
| Investors | 15 | 4 | 6 | 4 | 1 |
| Programs, incubators, grants | 168 | 112 | 38 | 11 | 3 |
| Government | 8 | 7 | 1 | 0 | 0 |
| Networking (Boardy) | 35 | 31 | 1 | 0 | 1 |
| Partners, peers, intros | 41 | 19 | 9 | 3 | 10 |
| Jobs, learning | 5 | 3 | 2 | 0 | 0 |
| Bounces | 5 | 0 | 5 | 0 | 0 |
| Vendors, newsletters, accounts | 87 | 81 | 5 | 0 | 0 |

The case-by-case reading is `04-NOW-VS-SHOULD-VS-EXPECTED.md` §2.

### 1.3 The founder's own outbound, typed `[PROD]`

The 11 Aug investor wave and the program replies were typed by the closed vocabulary as:
`contract_renewal` (Peak XV, Titan, Afore, Surge, Antler, Hub71, Bharat Ke Super Founders, two
angels), `financial_obligation` (Z Fellows, Antler, Hub71, BKSF), `decision_made`, `risk_flagged`.
**No member of the vocabulary means "pitch", "application", "intro" or "program".**

### 1.4 The model `[PROD]` — last 3 days, per day

| Purpose | Model | Calls | Input tok | Output tok |
|---|---|---:|---:|---:|
| `l4_llm_decision` | Haiku 4.5 | 874 | 2,229,426 | 229,275 |
| `l4_llm_r1` | Haiku 4.5 | 528 | 269,634 | 61,332 |
| `relevance_gate` | Haiku 4.5 | 250 | 225,692 | 42,858 |
| `screen_memory_batch` | Haiku 4.5 | 75 | 102,115 | 6,968 |
| `l1_extract` | Haiku 4.5 | 70 | 167,417 | 199,618 |
| `l1_relevance` | Haiku 4.5 | 64 | 64,450 | 19,660 |
| `l2:resolution` | Haiku 4.5 | 52 | 74,928 | 10,217 |
| `l5_render` | Haiku 4.5 | 30 | 39,031 | 4,487 |
| `moment.screen_insight` | Haiku 4.5 | 25 | 71,403 | 2,316 |
| `l4_bundle` | Sonnet 5 | 22 | 93,633 | 27,792 |

≈ 1,990 calls a day; **70% re-decide** (`l4_llm_decision` + `l4_llm_r1`); **3.5% read mail**.
`l4_bundle`: 29 of 55 failed on 3 Oct, 8 of 12 on 4 Oct, all at the 1,400-token ceiling — raised to
2,400 on `harsh/mvp` (`5ebfef8e`).

### 1.5 The context an expert needs `[PROD]`

`seat_objectives` 0 · `seat_responsibilities` 0 · `org_mission_critical_entities` 0 · `user_models`
0 · `user_model_proposals` 0 · `learned_brain_entries` 0 · `knowledge_suggestions` 0 ·
`temporary_memories` 0 · `user_tasks` 0 · `card_feedback_verdicts` 0 · `human_events` 0 ·
`seat_profiles` 1. **`unclassified_observations` 118, promoted 0, reviewed 0.**
`situation_interpretations` (R-6) 1,683 rows: 1,354 `unknown`, 329 `accept` — and **no row involved a
model call**: the `situation_reasoner` L4 feature is not default-on (`platform/intelligence_onboarding.py`
`NOT_DEFAULT_ON`), so the gate refuses with `l4_situation_reasoner_not_activated` and `proposal` is `{}`;
`outcome` records the quadrant, not whether a model ran. The table has no reader (`platform/table_coverage.py:133`).

### 1.6 Connections `[PROD]`

One Gmail and one Calendar connection, both `workspace`, created 21 Aug. `ceo@thegenios.com` is not
connected; it appears only as a recipient of the founder's own mail.

---

## 2 · Capture and the gate `[CODE]`

| What | Where | What it does |
|---|---|---|
| S1 noise rules | `capture/gate/rules.py:335-382` `noise_rule` | N-09, N-08 (`sender_blocked`), N-06, N-07, availability bypass, N-01, N-03 (machine, no attachment), N-04, N-02 (list headers) — every one a **drop** |
| Integrity | `capture/gate/rules.py:287-332` | DOC-02/04/05/06/07/08/09 and MUT-01 park; N-10 empty-body drop at `:329-331`; no whitelist bypasses it |
| Whitelist | `capture/gate/rules.py:269-284` | W-01 `sender_known`, W-02 starred/`approved_sender`, W-03 `actor.type == "agent"`, W-04, W-05 — bypasses `noise_rule` only |
| Gmail actor type | `capture/connectors/composio.py:575` | hard-coded `actor_type="external_contact"`. **Boardy can never be W-03.** The only producer of `agent` is `capture/intake.py:146-151` |
| Tenant allow/block list | `rules.py:274`, `:345` | `approved_sender` and `sender_blocked` are read and **never written anywhere** — N-08 cannot fire, no allowlist exists |
| `sender_known` | `api/routes.py:351-367`, SQL `:330-336` | a person with an active `thread.last_outbound` — which exists only after L2 drained the founder's outbound mail. *On `harsh/mvp` widened to recipients of the account's own sent mail (`48768ca7`): 11 → 29 known people* |
| S2 LLM gate | `capture/gate/gate.py:121-132`; prompt `capture/gate/relevance.py:65-122` | drop when relevance < 0.25 (`relevance.py:15`); the prompt has **no company context** and lists *"automated, one-to-many, self-service"* and *"automated matchmaking"* as drop classes |
| S2 park reason | `gate.py:133-135` | every S2 park is recorded as `low_relevance`; the classifier's own reason is lost |
| List-time junk | `capture/connectors/composio.py:406-422` `light_junk` | N-09/N-06/N-07/N-03 before the full fetch; recorded as `dropped` |
| What a drop writes | `capture/pipeline.py:1567-1640` | `source_events` always; `raw_payloads` only if kept or judged-drop (TTL parked 365 d, judged drop 90 d, emitted **30 d**, `:179-187`); `prepared_content` only if kept; returns before the semantic lane and ESQE |
| Purges | `capture/payload_store.py:56-67`, `capture/prepared_store.py:121-126` | `delete … where expires_at < now`, every maintenance tick (`api/routes.py:996-1000`) |
| Re-fetch of a dropped mail | `capture/pipeline.py:105-107`; `landing/pg_repository.py:44,58-60` | **none** — dedup ignores outcome, so a re-sync lands it as a duplicate. Only an org reset, a disconnect-wipe or a script frees the key |
| Bounces | `[PROD]` 5 DSNs passed S1 and were junked at S2; 8 parked | `DELIVERY_FAILURE` exists (`contracts/signal.py:284-299`) and never fired on this tenant |

## 3 · From capture to memory `[CODE]`

| What | Where | What it does |
|---|---|---|
| The closed vocabulary | `contracts/signal.py:210-299` | 16 members; *"something genuinely new goes to the OPEN LANE … reviewed weekly"* — 118 waiting, 0 reviewed |
| Type choice | `capture/esqe/detector.py:327-489`; precedence `esqe/classifier.py:45-75` | deterministic predicates over the extraction; ≤ 5 per event |
| Relevance before detection | `capture/pipeline.py:1293-1296`; `esqe/relevance.py:173-177` | `bulk_headers`, `service_account_no_claims`, `llm5_not_business` refuse detection entirely |
| The floor | `capture/esqe/qualification.py:78` | `DEFAULT_FLOOR_BP = 2500`; refusals go to `qualification_drops`, which nothing reads back |
| No signal, no memory | `qualification.py:857-861`; `context/runner.py:244-254` | an event extracted with zero qualified signals is never pulled by L2 |
| **The pull** | `context/runner.py:218-270` `_pull` | inner `join raw_payloads` (`:242` — an emitted payload expires in 30 d, after which the event is undrainable) · inner lateral join to an **active** qualified signal (`:244-254`) · `outcome='emitted'` (`:257`) |
| The structured lane | `context/runner.py:138-156` | calendar mapping → `commit_structured` (`context/structured.py:36-142`), no model — **only reached if the event already has an active signal** |
| No-signal events | `context/runner.py:162-167` | `held_missing_qes_extraction` |
| No extraction, no LLM | `context/pipeline.py:862-871` | `process_event` raises when there is neither |
| Writers that need no model | `context/pipeline.py` | `_person` 970-1007 · `_works_at` 1011-1043 · recipients and `corresponded_with` 1183-1225 · outbound direction and ball-in-court 1233-1301 · `_thread_node` 466-488 · inbound direction 1719-1760 |
| Meetings | `capture/structured/registry.py:197-211` → `structured/mapper.py:392-394` → `esqe/detector.py:267-274, 347-351` | a meeting's start becomes an unattached date → `DEADLINE_STATED` (*"stated_date_without_commitment"*) |
| Meetings expire | `capture/esqe/lifecycle.py:357-365, 371-375, 796-813` | `DEADLINE_STATED` expires 30 d after the date; a meeting 30–60 d old is **published already expired** and never drained `[inference]` |
| Recovery = flag flip | `capture/parked/drain.py:151-154`; `api/routes.py:2453-2473`; `capture/parked/refetch.py:849-851`; `capture/parked/recapture.py:262-274` | `outcome → 'emitted'`, nothing re-processed. *On `harsh/mvp`, `adb04093` sets `route`/`triage_lane` on re-admission so new rows are extracted; old rows stay unrouted* |
| The unread re-read | `capture/landing/unread.py:37-55` | only `emitted` rows captured **before** activation; never a recovered park |
| Strands with no drain | `capture/semantic/extractor.py:199-210`; `capture/acquire/sync_runner.py:751-758` | extraction parks and `poison_quarantine` are in no drain set |
| Screen | `reason/moments/guards.py:68-71`; default `platform/capture_policy.py:254, 498` | moments hidden unless `capture_policies.moments_display`; follow-ups become graph **observations** (`reason/moments/screen_memory.py:64-102`), never new people; screen-session events carry no semantic lane and are never drained `[inference]` |
| Backfill window | `capture/connectors/backfill.py:37` | `DEFAULT_BACKFILL_DAYS = 60`; per-connection override `PATCH /connections/{id}/backfill-window` (`api/routes.py:2509-2540`) |

## 4 · Reasoning and cards `[CODE]`

| What | Where | What it does |
|---|---|---|
| The chain | `api/routes.py:591-689` `_run_l2_chain` | provision → `_reread_unread` → `process_pending` → `run_all` → `build_cards_for_org` → post-passes |
| Ticks | `platform/scheduler.py:37-119`; `config.py:132, 139` | heavy every 6 h (`run_maintenance_sweep`), light every 15 min (`run_sync_sweep(chain_only_on_new_data=True)`) |
| Re-reason everything | `api/routes.py:947-950`; `reason/runner.py:856-910` | one new event in an org re-reasons **every** node and situation; `process_pending` knows the touched nodes (`context/runner.py:534, 559`) and returns only their count |
| Compiled lane | `reason/runner.py:1494-1498` | `shadow_compile(...)` — its return value is discarded |
| Selection | `reason/domain_shadow.py:107-128` | `context_situations` active/partial, limit 200; no "changed since" filter |
| A domain that can never be live | `reason/domain_shadow.py:512-526` | `fundraising` and `general` map to no live lane — **the 13 investor situations can never produce a live card** |
| Paying for discarded decisions | `reason/domain_shadow.py:1178-1193`; `reason/orchestrator.py:252-263` | shadow rows still run R-1 and the LLM decider, then `continue` `[inference]` |
| Unchanged check | `reason/runner.py:1190-1212` | `no_new_evidence` runs **after** reasoning; derived/waiting facts are rewritten every drain with `occurred_at = now` (`context/derived.py:145-161`, `context/waiting.py:348-353`), so it rarely fires |
| Every key moves every sweep | `reason/store.py:785-802`; `contracts/reasoning.py:479-496, 779-786`; `reason/audit.py:211-215` | `input_hash`, `context_snapshot_id` and `idempotency_key` all include `evaluation_time`; `load_by_idempotency` has no caller; `reasoning_runs.supersedes_run_id` no writer |
| The time-blind address that exists | `contracts/domain_expertise.py:626-686` | `SituationContextSlice.semantic_hash` drops trace, eval time and graph version — but carries rewritten derived values, so it too moves `[inference]` |
| DEFER closes cards | `reason/runner.py:1116-1125, 1168-1175, 1382-1410` | DEFER is not indeterminate → logged as `shadow` → the lifecycle pass resolves the signal and expires the card |
| The decider's prompt | `reason/llm_decision_maker.py:479-593` | *"You are the chief of staff of a busy founder…"* — then one situation, the latest **4** messages' L1 summaries, ≤ 40 rule facts, ≤ 25 neighbour facts, the **formula's baseline**, plays with formula utilities. **No company profile, no prior decisions or cards or feedback, no history beyond 4 messages, no timeline** |
| Its output | `reason/llm_decision_maker.py:581-635, 747-847` | `{outcome, scores per play 0-10000, confidence_bp, rationale, missing}`; the utility **is** the model's score; rationale and missing are written onto the winner and **read by nothing**; `output_lane` is left NULL, so its cards are "unrouted" |
| Its cache and cap | `reason/llm_decision_maker.py:93, 667-697, 201-218`; `config.py:81-88` | in-process, keyed on `evaluation_time` → never hits across sweeps; a 400/day in-process counter shared with R-1, reset on restart; **no dollar governor** |
| R-1 | `reason/llm_interpretation.py:69-269` | ≤ 12 items, ≤ 3 readings kept; cache keyed on `context_snapshot_id` → misses every sweep; no mode check |
| R-6, the context reasoner | `reason/situation_reasoner.py` (262 lines); called `reason/domain_shadow.py:1072-1124`; persisted `context/interpretation_store.py:30-59` | one call per situation behind `RSiteGate`, cache keyed on the slice digest; asks only for `model_writable_fields`; *"the model may lower a confidence and never raise one"*. ⛔ Its L4 feature `situation_reasoner` is **not default-on**, so in production it has never called a model; `situation_interpretations` is written every sweep and **read by nothing** |
| Score, band, level | `reason/domain_shadow.py:353, 361`; `reason/authority.py:55, 139`; `deliver/bands.py:8-14` | score = `(final_utility_bp + 50) // 100` — **the model's number** while the LLM decider is on; high ≥ 70, critical ≥ 85; compiled level is `prescriptive` only for accepted review state |
| The lane router | `reason/output_lane.py` | deterministic, from `DecisionOutcome` + a 6,000 bp floor + conflict; reusable as-is |
| Card selection | `deliver/pipeline.py:46-131, 134-179, 374-381` | per **signal**; the per-situation grouping is measurement only; `cards_from_situations` sets a label only |
| Card copy | `deliver/render.py:698-784, 787-904` | Haiku, 600 tokens; examples hard-code *"Send Titan Capital your traction metrics"*, *"Answer Divyanshu's pricing question"* (`:750`) and the persona *"for a salesperson"* (`:767`); receives facts and quotes, **not** the decider's rationale, the rejected options, the unit findings or any history |
| R-2 narrator | `reason/bundle/sweep.py:47-196`; `reason/bundle/sites.py:49-56` | Sonnet 5, $2/day; output read only by the API feed, **never by the card** |
| Expiry | 11 sites | only `deliver/store.py:322` (`window.lapsed`) and `api/intelligence_routes.py:1190` (`card.dismissed`) write a `card_event`; nine are silent |

## 5 · The Atlas, claim by claim — before any unit was written

| # | The Atlas says | Where | True today? |
|---|---|---|---|
| A1 | one bounded **judgment pass** inside L2 — frames, hypotheses, counterexamples, consequences, next move | II.2; L2 Fig. L2.1 | ❌ **not built.** What runs instead is a per-sweep scorer (§4) |
| A2 | **material-change gate** + situation fingerprint — *"no material change → zero model calls"* | L2·O steps 2, 12 | ❌ not built (§4: every key moves every sweep) |
| A3 | *"the model may never score importance, priority or confidence"* (RULE 02) | II.2; V.6 | ❌ **violated in production** — the card's score is the model's utility |
| A4 | five output lanes | A.3 | ⚠️ the router exists (`reason/output_lane.py`); the LLM path leaves the lane NULL |
| A5 | Plane R Groups 1–3: baselines, relationship history, prior situations, pattern / base rate / counter-pattern, scenario set | Plane R directory | ⚠️ pieces exist as units (timeline, cadence, delay cost, do-nothing, alternative); `reason/simulation.py` has no production caller; no unit computes a reply rate |
| A6 | coverage receipts; *"no reply"* only with window and completeness (RULE 05) | P1·6 | ⚠️ capture coverage exists; per-signal coverage is NULL; one of two mailboxes connected and no card says so |
| A7 | six object types — commitment, condition, open question, delivery status, meeting follow-up link, thread terminal state | P1·8 | ⚠️ the extractor emits commitments, questions, decision states, scheduling; no delivery status reached production; no meeting follow-up link |
| A8 | populate the organisation and behaviour brains | P1·9 | ❌ every table 0 rows (§1.5) |
| A9 | screen into the graph, with seat visibility | P2·15 | ⚠️ follow-ups become observations; moments all hidden |
| A10 | reach beyond 60 days | P2·17 | ❌ 60-day window; July is gone since the 3 Oct re-capture |
| A11 | a bounded, bitemporal read for L2 | P2·13 | ✅ `context/bounded_read.py` — its only caller is `context/context_health.py`; **reasoning never uses it** |
| A12 | uncertainty routes, never deletes (RULE 04); silence is a decision with a receipt (RULE 14) | V.6 | ❌ violated at the gate (§2) and at nine expiry sites (§4) |
| A13 | *"a 28-day outbound silence during a raise; pitch emails that bounced; investor-adjacent contacts waiting 46–77 days; ~13 warm intros with no follow-up; events with no post-event outreach — all resolve at L1 and L2 with state and absence detection"* | I.2 | ❌ **still true on 5 Oct**, on the same mailbox, class for class |
| A14 | golden replays 01–07 must pass before advice on these situations | Secret War 09 | ❌ `[TEST]` 0 of 80 mutations runnable; 150 of 153 overall `xfail` |
| A15 | *"classification is rules and tables, never the model"* (L2·O step 5) | L2·O | ✅ kept by this plan: triggers and the dirty set stay deterministic |
| A16 | the model **may** run the integrated judgment pass and word the card | II.2 | ✅ this plan builds exactly that — with one amendment (`06` D1) |

## 6 · `origin/harsh/mvp` — what is already fixed there `[CODE]`

> ✅ **2026-10-05, after this crosscheck:** merged into `speedrun008` (`STEP-00`). And production
> passes Harsh's `pipeline_health` checks **7 of 7** — 0 unrouted emitted events, 29 known
> counterparties, no failing or truncating model lane in 24 h (`baseline/2026-10-05/`). So
> these fixes are live and the stranded rows were repaired. What they do not touch is unchanged:
> 258 mails still have no content, 67 junked mails were never read, and 15 of 365 inbound mails
> reach reasoning.

| Commit | Fixes | Overlap with this plan |
|---|---|---|
| `adb04093` | re-admitted parks get a `route`, so **new** recoveries are extracted | `STEP-05` keeps it and adds re-processing of old rows and a real re-run |
| `48768ca7` | `sender_known` reads the sent folder: 11 → 29 known people | `STEP-03` builds on it: known senders get attention, not just "no drop" |
| `d4e035bb` | attachment errors keep their reason | `STEP-06` reuses the readable error |
| `2caf88aa` | truncation reported as truncation (`stop_reason`) | `STEP-12` relies on it for the expert pass |
| `5ebfef8e` | `scripts/pipeline_health.py`, seven read-only checks, exit 1; narrator cap 1,400 → 2,400 | `STEP-00` baseline; `STEP-17` deploy gate |
| `c22d0f00`, `2c42722d` | expired cards can be rebuilt; human-decided cards never | `STEP-14` keeps both sets |
| `3f8d51e0` | the context slice no longer depends on row order | `STEP-02` builds its fingerprint on stable identity for the same reason |
| `2f595277` | card drawer no longer crashes on structured `why` values | — |
| `7075014c` | lapsed tenants stop spending; `dependency_stated` cards ground on the founder's own sentence | `STEP-04` must keep that exception |
| `7e19a1c9` | `INSUFFICIENT_CONTEXT` no longer writes a 9-row receipt every sweep | `STEP-02` |
| `50c50073` | a reset erases every org-scoped conclusion table | `STEP-08` (re-sync) depends on it |
| `9a51d0ea` | the five funnel numbers; objects travel as references; **Sales and Support `default_on: false`** | `STEP-11` (a new domain) — and `D2` |

## 7 · The queries `[PROD]`

All read-only: `conn.read_only = True` (psycopg issues `BEGIN READ ONLY`), `statement_timeout`
45 s, the URL read from `../.env` and never printed. The scripts live in the session scratchpad and
are reproduced in `03-FINDINGS.md` §F for the numbers that matter. The funnel-by-workstream query
becomes `scripts/workstream_funnel.py` in `STEP-00`.

## 8 · What could not be measured

| Not measured | Why | Who can close it |
|---|---|---|
| what any mail **said** | email-body reads were blocked by the session classifier, twice, including after Rohit's explicit instruction | Rohit — a permission rule, or running the queries himself |
| the 258 S1-dropped mails at all | GeniOS deleted their content | the re-sync, `STEP-08` |
| which commit production runs | not visible from the database | Harsh |

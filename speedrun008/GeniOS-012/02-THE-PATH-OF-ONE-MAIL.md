# 02 · The path of one mail, from Gmail to the dashboard, and the 32 places it is lost

**Written for:** Harsh and coding agents. This is the "how it happened" file. It follows one real kind of mail through the code, stage by stage, and numbers every place where it can be lost (**D1–D32**). Each later file (03–08) takes one stretch of this path and gives the fix, unit by unit.

**Code measured at:** `origin/speedrun008` `71e4c4a8` (23 Oct 2026). Production runs `harsh/mvp` `0cc8d83c`, an ancestor; what differs is listed in [04-FOR-HARSH §1 of GeniOS-011](../GeniOS-011/04-FOR-HARSH.md). Paths are relative to the repo root; `genios_engine/` is omitted where it is obvious.

**The running example:** card `i1` on `/preview`. An accelerator passed on Rohit in August, then wrote that it would reconsider later; three follow-up updates got no answer; a meeting with them is on the calendar from August; and today's programme review is a new fact that changes what to send. The ideal card: *write to them now, with this draft, because of the new fact, and it moves the pre-seed goal.*

---

## The production funnel, measured on 4 Oct

| Stage | What reached it |
|---|---|
| Emails in the window | ~470 |
| Emails that reached the Context Graph as filed events | **27** |
| Past meetings in the window | 22 |
| Past meetings that reached the graph | **0** |

The loss is the shape of the funnel, not one bug. Every stage below takes its share.

---

## Stage 0 · Does the chain run at all?

```
platform/scheduler._tick  ──►  api/routes.run_maintenance_sweep  ──►  api/routes.run_sync_sweep (routes.py:1117)
platform/scheduler (light tick, chain_only_on_new_data=True)  ──►  run_sync_sweep
```

| # | Where | What happens | Effect on `i1` |
|---|---|---|---|
| **D1** | `api/routes.py:1042-1077` `_plan_expired(org_id)` → `platform/billing.py:338` `expiry_state(...) == "expired"`; checked at `routes.py:1211-1214`; lapsed orgs removed from the L2/L3/L5 pass at `routes.py:1289-1290`; counter `l1_skipped_plan_expired` at `:1309` | Since commit `7075014c` (4 Oct) both scheduled ticks skip an expired org entirely: no capture, no L3, no L2, no cards. "grace" is not expired; a billing read error fails open. That commit measured Rohit's grace as closed on 21 Sep. | No card is ever built by the schedule. |
| **D2** | `platform/warm_lane.py:135-157` `plan_expired()`, refusal in `enqueue()` `:175-177` | The webhook's fast lane refuses the org at the door. The webhook still ingests (L1) but nothing reasons. | New mail lands but is never judged. |
| — | Still runs, **with no plan check**: `POST /integrations/sync-all` (`routes.py:4178`) → `sync_jobs.enqueue` → `run_one_sync_job` (`:4102`) → `_onboarding_sync_bg` (`:3988`), which checks only `_llm_over_daily_cap` (~`:4011`); also `POST /sync/{connection_id}` (`:2026`), `POST /connections/{id}/backfill`, `/ingest/all` (`:1749`) | **Sync now** is the only door that still makes cards for an expired org. That matches "fewer cards, and only sometimes". | Cards appear only when someone presses Sync now. |
| **D3** | `platform/l4_activation.py` `FEATURE_EXPERT_REVIEW` `:104`, `FEATURE_L2_REASONING` `:117`, `FEATURE_L2_CARDS` `:122`; `NOT_DEFAULT_ON` `:167-203`; `Domain Expertise/Founder Office Expertise/domain.yaml:44-45` `default_on: false` | Onboarding (`platform/intelligence_onboarding.make_tenant_live` `:222`) switches on everything **except** the expert review, the L2 judgment, L2 cards and the Founder Office domain. | Even when the chain runs, no expert ever judges an investor file, and no investor playbook exists for it. |

---

## Stage 1 · L1 capture: is the mail fetched?

```
capture/connectors/composio.py  list query (:402-430)  ──►  _to_objects (:791)  ──►  capture/pipeline
capture/connectors/calendar.py  _fetch (:66)  ──►  _to_raw (:109-191)
```

| # | Where | What happens | Effect on `i1` |
|---|---|---|---|
| **D4** | `capture/connectors/backfill.py:37` `DEFAULT_BACKFILL_DAYS = 60`; `backfill_window_for(connection)` `:73` reads `connections.capture_scope.backfill_days` | The window is 60 days unless an admin PATCHes it per connection (`PATCH /connections/{id}/backfill-window`, ~`routes.py:2909`). The founder's onboarding choice (`integration_preferences…historical_backfill`) is **not** written through. Gmail queries `newer_than:{days}d` on a first sync, then `after:YYYY/MM/DD`. Calendar uses `timeMin = now − days`. | The accelerator's mails (early August) were 77+ days old on 23 Oct: **never fetched**. The August meeting too. |
| **D5** | `routes.py:3617` `_BACKFILL_MAX_ROUNDS = 200` | About 5,000 messages per source per backfill. Not a limit for Rohit today; it will be for a larger mailbox at 365 days. | — |
| **D6** | `api/routes.py:3596-3611` `_need_fetchers` builds its `Connection` with `config={}` | When L2 asks "fetch the earlier mail", the window fetcher uses the **default 60 days**, even after the connection's window is widened. Fetchers are also off unless `GENIOS_NEED_FETCHERS` is set (`capture/acquire/need_fetchers.py:34-39`). | L2 cannot pull the August thread back on demand. |

---

## Stage 2 · L1 gate: is the mail kept?

```
list pass:   gate/rules.noise_rule (:397-464)  N-06 Promotions · N-07 Social · N-03 no-reply/notify
             gate/relevance.LLMRelevanceClassifier.prime (:266-293)  batch judge
full fetch:  gate/rules  N-01 Auto-Submitted · N-04 Precedence · N-02 List-Unsubscribe/List-Id/List-Post/Feedback-ID
             gate/gate.run_gate S1b/S2 (:162-261), _overruling_keep (:53-66)
bypasses:    W-07 sender named in the company brief · W-01 known counterparty · W-02 starred
```

| # | Where | What happens | Effect on the cards |
|---|---|---|---|
| **D7** | `gate/rules.py` N-02 | Mail with a List-Unsubscribe or List-Id header is archived. Boardy sends every intro that way. A soft rule is overruled only if the batch verdict already bought for that mail says keep with relevance ≥ 0.70 (`RESCUE_AT`, `relevance.py:23`). | `b1`, `b3`, `f3` (all via Boardy): archived. |
| **D8** | `gate/rules.py` N-03 / N-06 | No-reply and notification senders, and Gmail's Promotions tab, are archived. Programme portals and the government registration portal send from no-reply addresses. | `f2`, `l1`, `c1`: archived unless the brief names the sender (W-07). |
| **D9** | `gate/relevance.py` `_GATE_BATCH_PROMPT` `:113`, `prime` `:266-293` | The batch judge sees a **masked subject + snippet, cut to 600 characters**. It **never sees the sender's address or domain**, nor whether the mail replies to us. The prompt says introductions and vendor price changes are "ALWAYS KEEP", but has **no class for application or programme status**. Below relevance 0.25 (`DROP_BELOW_RELEVANCE`, `:17`) a mail is archived with only its list snippet. | A short investor reply ("not now, maybe next batch") can read like noise without the sender. |
| — | `capture/parked/drain.py` (S06.U1 ✅), `capture/connectors/composio.py` `_full_message` `:441-467` (S06.U2 ✅) | Fixed on `speedrun008`: an `llm_junk` archive is no longer re-admitted on its snippet, and a refused full fetch parks as DOC-05 instead of passing the snippet off as the body. | Removes noise and fragments; does not bring back the archived founder mail. |

---

## Stage 3 · L1 extraction: what is the mail understood as?

```
capture/esqe/classifier · esqe/detector._detect_all · esqe/importance (ALG-17) · esqe/normalize
contracts/signal.py:210-299  SignalType (16 members)
capture/structured/registry.py:203-218  gcal.event.v1  ──►  capture/structured/mapper.py:392,410-416
```

| # | Where | What happens | Effect on the cards |
|---|---|---|---|
| **D10** | `contracts/signal.py:210-299` | 16 signal types: `commitment_made`, `commitment_due`, `deadline_stated`, `decision_pending`, `decision_made`, `approval_requested`, `contract_renewal`, `financial_obligation`, `risk_flagged`, `opportunity_signal`, `relationship_change`, `information_conflict`, `escalation`, `anomaly`, `availability_change`, `delivery_failure`. There is no intro, meeting, investor interest, application status or request. (The docstring still says "15-member".) | Founder work is typed as the nearest wrong word, or as nothing. A fund's outreach once became `contract_renewal`. |
| **D11** | `contracts/extraction.py:381` `UnclassifiedObservation` → `capture/semantic/open_lane.py` → table `unclassified_observations` (migration 0079) | What fits no type goes to the open lane, which **no rule reads**. 698 candidates, 0 promoted (GeniOS-011 audit). | Lost silently. |
| **D12** | `capture/structured/registry.py:203-218`, `mapper.py` | A calendar event takes the structured path with no model call. It becomes a `meeting` node with `attended` edges. There is no meeting signal type: the intent maps to `schedule`, and start/end become `dates_mentioned`, so the only signal that can fire is `DEADLINE_STATED`. | `f1`, `i3`, `b2` and the meeting behind `i1`: **0 of 22 past meetings reached the graph** on 4 Oct. |
| **D13** | `capture/pipeline.py:515` `_envelope_direction`; extraction fills `ExtractionResult.amounts` | Sent mail is captured and marked outbound. Its amounts are extracted, but **`context/pipeline.py` never writes amounts to the graph**. There is no own-claim lane anywhere. | `p1` (four different traction numbers in the founder's own sent mail): impossible. |

---

## Stage 4 · L3 Context Graph: is the mail filed with its work?

```
context/runner.process_pending (:703)
  └─ context/pipeline.process_event ── correlate_event (correlation.py:616-653) ── find_or_open (:431-470)
  └─ the nine situation writers (pinned by tests/test_rule3_situation_writers_only_shrink.py)
```

| # | Where | What happens | Effect on the cards |
|---|---|---|---|
| **D14** | `context/pipeline.py:2326` `correlations = [] if (is_noise or metadata_only) else correlate_event(...)`; `context/memory_lanes.lane_for`; `context/backfill.backfill_correlations` considers only `outcome='emitted'` | Noise, archived (metadata-only) and anchorless events are never filed. Archived mail stays outside every file even after it is promoted, unless the backfill is re-run. | Every mail lost at D7–D9 is also absent from L3. |
| **D15** | `context/workstreams.py:162-169` `_MEMBERS` drops `visibility_scope='private'` | Private events are correlated but appear in no file. | A personal-looking mail from an investor is invisible to the judgment. |
| **D16** | `platform/funnel.py:54-60` | The funnel has five stages (signals_detected, situations_formed, capability_resolved, decision_emitted, card_delivered) and **no "filed" stage**. | Nobody can see D14–D15. |
| **D17** | `context/correlation.py:73` `CORRELATION_WINDOW_DAYS = 45`; key `(anchor_node_id, domain, generation)`; `situations.refresh_situations` (`situations.py:1086`) writes one situation per correlation | A file is one counterparty node. Inside it, each **keyword domain** and each **45-day generation** opens its own correlation and its own situation (`venture_capital` → `investor_relationship`, `general` → `relationship`…). The reading writers add more on synthetic anchors (outreach node, thread, `campaign:{id}`…). | The accelerator's file holds several live situations at once. |
| **D18** | `context/l2_admission.py` `decide` `:68-113`; `workstreams.lifecycle_for` `:388-409`, `_SITUATIONS` `:327-331` (`where anchor_node_id = :f`, limit 10); `reason/l2/sweep.py:379-383` | Admission sees only situations anchored on the file's own node, so the readings (awaiting reply, overdue promise, meeting…) are invisible to it. With more than one live situation and none named, it returns **HOLD**, and a HOLD stops the L2 judgment becoming the file's review. **This is not purely shadow** (correction to GeniOS-011). | The L2 judgment on `i1` is thrown away and the old lane stays in charge. |
| **D19** | `context/correlation_conversation.py` `find_campaigns` `:308` (≥3 recipients, 36 h), `find_waves` `:614`; only reader `workstream_numbers.numbers_for` `:173` | A broadcast is detected but is not a file or a subject. Each recipient keeps its own situations. The module docstring "NOTHING READS A WAVE YET" (`:64`) is stale. | `i4` (one update to 12 investors, 0 replies) and `s2` (28 prospects): never one card. |
| **D20** | `context/vocabulary.py:263-274` `CLOSED_ANSWERED`/`CLOSED_REPLIED`, `discharged_asks`; `context/open_loops.py:66-77` | **Any** reply on the thread closes every open ask. The basis is `answered` only if the message's observed kind is in the `kinds.yaml` `discharges` table; otherwise `replied`. No model compares the reply with the ask. | `i2` (an investor asked for traction; the reply did not answer it): closed as done. |
| **D21** | `context/delivery.py:70` `record_delivery_failure`, `_original` `:126`; read by `context/waiting.py:199-230` | A bounce is kept (not junk) and linked to our last mail on the same thread. Its only effect is to **retire "awaiting reply"**. No situation, no card. | `i5` (6 bounces, 3 to investors), and part of `c1`: invisible. Worse: the waiting card disappears. |
| **D22** | `context/graph_store.py:40-71` `fact_write_action`, `write_discrepancy` `:875` | A `discrepancies` row is written only when the new fact's rank is **lower** than the held one. Two equal-rank email facts that disagree: the newer **silently supersedes**. There is no field for the tenant's own metrics (unknown names become `other.*`, "never consulted"). | `p1`: even if D13 were fixed, the conflict would vanish. |
| **D23** | `context/backfill.py:131-135` `backfill_correlations(rebuild=True)`; triggered by `backfill_layer2` `:428-447` whenever `deal_nodes_created` is non-zero, including the automatic history replay at `api/routes.py:777-778`; `situations.py:1220` `new_id("sit")` = uuid4 | A rebuild **deletes** every situation of the org, including human resolutions, and re-mints random ids. The docstring at `backfill.py:126-129` says the id is a content hash: false. | Closed cards come back; admissions and decisions are orphaned. |

---

## Stage 5 · L2 Qualification: is the file judged, and does the judgment become a card?

```
api/routes._run_l2_chain (:797+)  ──►  l2.process_pending (:857)  ──►  l4.run_all (:881)
reason/runner.run_all (:1923-2126):
   expert_pass (reason/expert/sweep.py:156-375)          (:2002-2007)
   l2_pass (reason/l2/sweep.py:169-445)                   (:2013-2019)
   shadow_compile (reason/domain_shadow.py:1328+)         (:2029-2039)   ◄── only if a flag is on
      _decide_covered_files (:780-972)  then the situation loop (:1756+)
   legacy per-pack run() loop                             (:2062-2081)
   why_no_card                                            (:2096-2101)
```

| # | Where | What happens | Effect on `i1` |
|---|---|---|---|
| **D24** | `reason/expert/triggers.py:175-196` `triggers_for`, `_crossings` `:132-159` | A file is reviewed only on: first look, a new event or answer, a date moving a rung closer, a correction, or a one-time crossing (`reply_overdue`, `past_normal`). With a single touch there is no "usual gap", so no crossing ever fires. **Time alone is never a trigger.** `FOUNDER_ASKED` is dead (no caller passes `asked=True`). | After the third unanswered update, the file is never looked at again. |
| **D25** | `reason/expert/dossier.py` `read_parts` `:759-813`, `SECTIONS` `:67`; `reason/l2/dossier.py`; `reason/l2/snapshot.py` (40 nodes, 5 seeds) | The judgment reads **one file**: the brief, the file's timeline, its own meetings, promises, numbers, coverage, the kind's playbook, situations, judged-before. It does not read other files, the calendar outside the file, or goal objects. Caps: 8 whole touches, 30 listed, `DOSSIER_CHARS=60_000`. | "Today's programme review is the new fact" cannot be written. |
| **D26** | `reason/bundle/sites.py`, `budget.py` `OWN_BUDGETS` `:63-71` | R-7 (expert) and R-9 (L2) run on `claude-sonnet-5`, thinking off, `max_tokens` 6000/8000. Each has **$2.00/day** and $0.10/$0.15 per call. R-7 reviews at most **10 files per pass**, nearest deadline first. | Fine for a few files a day; too little for a 365-day backfill's first judgment (Step 2). |
| **D27** | `contracts/claim_check.py:38` `CHECK_VERSION = "check.v4"`, `HELD_BECAUSE` `:131-151`; `reason/expert/verify.py:787-793` `_held_question` | Most real-model answers are held (68 of 86 on Haiku, 12 Oct). A held card prints *"What is the next step with {them}? We held the one we found: {why}."* The fix (check.v5, 79% → 18.5% held) sits on `yc2w27-int13b`/`yc2w27-s13b`, 43–44 commits off the head, and its migration `0250_expert_review_attempts.sql` collides with `0250_screen_followup_read_path.sql` on the head. | The weird card. |
| **D28** | `reason/runner.py:2029` (`live_compile` `:1971`, `l3_domains = activated_domains(...)` `:1993`, `platform/config.l1_seam_enabled` `:310`) | `shadow_compile` runs only if the global `use_domain_compiler` is on, or the org has an activated L3 domain, or an `l1_semantic_activation` row. Without one of them, a judged ("covered") file is **never decided and never carded**, silently. Onboarding normally writes both rows, so this bites only an org whose rows were never written or were reset. | Only if the readings show neither row: a perfect judgment, no card. |
| **D29** | `reason/domain_shadow.py` `_FILES_HOME` `:547-553`; `covered_without_situation` exit `:817-823`; `_L2_TO_L3_DOMAIN` `:1040-1053`; `live_lane` `:1056-1083`; `_tenant_pack` `:130-162` | A covered file makes a card only if it has a **home**: a `context_situations` row anchored on it, or one its review explains, in an **activated** domain, with an active tenant pack. `general` maps to no domain, so it is decided in shadow only (`expert_shadow`). `fundraising` maps to `founder_office`, which is off (D3). | `i1` lands in `fundraising` → `founder_office` → not activated → shadow. |
| **D30** | `reason/domain_shadow.py` `_daily_allowance` `:165-186`; `reason/runner.py:551-555` `_budget_used`, `:1089` `budget_per_user_day` (7); seats capped by tier (trial 2, startup 5, growth 15, scale 50) | The day's allowance is 7 × active seats, minus **every signal the org created today from any lane, including earlier sweeps**. S18.U1 made judged files go first *within* a sweep, but a morning sweep's template cards still spend the allowance before an afternoon judgment. | The judged card can still lose its slot. |
| **D31** | `packs/compiler/capability_resolver.py:274-298` `_admission_reason`, `UnsupportedCoverage("unreviewed")` `:820-823`; `domain_shadow.py:1668-1676` (`require_admission=True`), `:1146-1153` (`misfiled_kind`) | Founder Office has six capabilities (investor_relations, program_applications, introductions, registrations_and_recognition, offers_and_joining, external_meetings), all `status: draft`, `review_status: unreviewed`. Only `investor_relationship`/`investor_contact` route (to investor_relations); the other five are `deferred_capabilities` (`no_runtime_trigger`). The compiled lane refuses anything unreviewed. The review sheets (`speedrun008/YC-II W27/review/investor.review.yaml` 146 lines, `program.review.yaml` 121) have every `decision: ''`. Investor know-how lives only here: Sales' copy was retired on 9 Oct, and Sales is `default_on: false`. | Investor, programme, intro, registration and hiring cards get no compiled playbook. |

---

## Stage 6 · L5 Delivery and the dashboard: is the card readable and visible?

```
api/routes._run_l2_chain  ──►  deliver.build_cards (:902)  ──►  deliver/card_builder.build_draft (:1142)
deliver/pipeline.py:1003  state_not_command(headline, level)
dashboard: src/app/dashboard/cards/page.tsx · src/lib/card-read.ts · src/product/internal/dashboard/goals/* · homepage/sections/genios-at-work.tsx
```

| # | Where | What happens | Effect on the cards |
|---|---|---|---|
| **D32** | the L5 card and the three dashboard pages, detailed in [08](08-L5-CARDS-AND-DASHBOARD.md):<br>(a) `deliver/render.py:26` `HEADLINE_CAP = 60`, `card_builder.gold_headline` `:886` cuts the move, `pipeline.py:1003` prefixes "Needs a decision — " (≈42 characters left);<br>(b) `reason/expert/decide.py` `_render` `:305-333` drops `scenarios.act/.best/.worst`, `_play` `:274-302` makes the steps tuple the headline;<br>(c) `api/routes.py:5376-5442` `_card_intelligence` builds the "why" from the subject node's last 4 meetings and 3 promises, the same for every card on that person;<br>(d) `GET /cards` (`deliver/store.py:855-989` `queue()`) returns 13 fields, with no goal and no category;<br>(e) Cards page: goal hard-coded "Not linked to a goal yet" (~`page.tsx:925`), `artifact` (the draft) never rendered;<br>(f) Goals page reads accepted company-brief lines (`GET /v1/company-brief`), progress unknown, `cards: []`, tags `[]`;<br>(g) Home: `const goals = sample ? SAMPLE_GOALS : []` (`genios-at-work.tsx:658`) | Every card that survives D1–D31 still reads garbled, thin and goal-less. |

---

## The whole path on one line

```
D1–D3 run & switches → D4–D6 window & fetchers → D7–D9 gate → D10–D13 words, calendar, sent claims
→ D14–D23 filing, multiplicity, admission, waves, replies, bounces, conflicts, rebuild
→ D24–D31 triggers, dossier, budget, claim check, compile gate, home, cap, Founder Office
→ D32 card writer, card fields, dashboard
```

Where each D is fixed:

| D | File | Step in [09-STEPS](09-STEPS.md) |
|---|---|---|
| D1–D3 | [03](03-RUN-GATE-AND-SWITCHES.md) | Step 1 |
| D4–D13 | [04](04-L1-SIGNALS.md) | Steps 2–3 |
| D14–D23 | [05](05-L3-CONTEXT-GRAPH.md) | Step 4 |
| D24–D31 | [06](06-L2-PLANE-D-AND-R.md) | Step 5 |
| goals | [07](07-GOALS.md) | Step 6 |
| D32 | [08](08-L5-CARDS-AND-DASHBOARD.md) | Step 7 |

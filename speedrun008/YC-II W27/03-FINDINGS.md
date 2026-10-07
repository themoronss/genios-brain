# 03 · Findings — what is broken, what only looked broken, what exists, what is missing

**Written for:** everyone. **Measured:** 2026-10-05, `speedrun008` @ `2dc61dac` and production
(read-only, metadata). **Re-measured the same day after the merge** (`8a472b81`, the `STEP-00`
re-do): F26–F29, E8, and the corrections to F24 and E4. **Root-caused the same day** on scratch
databases, for tree `yc2_w27`: F30–F37, E9–E11. **Measured 2026-10-06 by the golden set**
(`STEP-01`, `yc2_w27/M19`) on a scratch database: F38–F49 and §F.1, the before-score. **Found
2026-10-06 building STEP-02** (`yc2_w27_s02`) **and checking STEP-03**: F50–F55. **Found 2026-10-06
building STEP-04** (`yc2_w27_s04`): F59–F68. **Found 2026-10-06 building STEP-05** (`yc2_w27_s05`): F69–F73. A finding is never deleted; a correction is a new line that
says what it corrects.

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
| F30 | `owns` carries two meanings: declared *company -> deal*, but also written *person -> document* — and read by nine modules | `[CODE]` `context/graph_store.py:171`; `context/documents.py:66, 263`; readers in `context/correlation_people.py`, `outreach_situations.py`, `correlation.py`, `lifecycle/store.py`, `reason/moments/recall.py`, `moments/slice.py`, `meetings/passes.py`, `meetings/prep.py` | a meaning audit, `STEP-17` §3.3 — not in `yc2_w27` |
| F31 | A message fingerprint outlives its event: after a disconnect-with-wipe and a reconnect, every re-synced message is skipped as *seen on screen* — and so is any re-read through `set_aside` | `[CODE]` `api/routes.py:3207-3211`; `capture/screen/fingerprint.py` `claim`; event ids are new on every landing (`capture/landing/normalize.py:33`); `[TEST]` the G7/G8/G10 gates fail exactly this way | `STEP-18` B20 → `yc2_w27/M17.C2.L-data.V0.U02`; ⛔ before `STEP-08` |
| F32 | A decimal number in a parsed model answer aborts the org's whole resolution pass, after the call is paid | `[CODE]` `context/model_audit.py:49` → `platform/canonical.py:51-53`; `context/lifecycle/resolution.py:221`; `[PROD]` latent — resolution calls equal audited runs, hour by hour, since the 3 Oct reset | `STEP-18` B21 |
| F33 | Calibration's one-line fix arms unattended muting, and an armed calibration hides cards: a muted rule's cards vanish unexplained, a mute never lifts, and any applied mute or nudge hides every open card of the pack | `[CODE]` + `[TEST]` reproduced on a scratch Postgres, 2026-10-05 (a loosening nudge: queue 5 → 0) | `yc2_w27/M18` (shadow first); `STEP-18` B22–B24 before arming; `06` D13 |
| F34 | Three tests expire with the calendar — a fixed seed date beside a wall-clock evaluation, or a weekly window: red since 4 Oct, since 22 Sep, and every Monday | `[TEST]` `tests/reason/adapters/test_roster_reaches_the_audit.py`, `tests/context/test_situation_publisher.py`, `tests/test_screen_followups_pg.py` | `yc2_w27/M16.C3`; the pattern is not yet swept (`STEP-17`) |
| F35 | Three Python versions — production 3.11, CI 3.12, local 3.13 — and one guard answered differently on 3.13 | `[CODE]` `Dockerfile:33`; `.github/workflows/ci.yml:17`; `tests/test_l1_seam_activation.py:191-192` | `yc2_w27/M16.C5`; `STEP-17` §3.1 runs CI on 3.11 |
| F36 | The scripts' `--json` output is not pure JSON — two `[db]` lines go to stdout first | `[CODE]` `scripts/_db.py:159-160` | a small unit, not in `yc2_w27` |
| F37 | In the three sweeps that built cards, the funnel counted fewer decisions than cards: 4 → 15, 2 → 3, 1 → 3 | `[PROD]` `pipeline_counters`, 3–4 Oct | `STEP-18` B17 → `yc2_w27/M17.C1` |
| F38 | Two identical runs give the same card with its WHY lines in a different order — the evidence a decision binds is ordered by a minted id, not by content | `[TEST]` `tests/replays/test_engine_runner.py` (`_comparable` compares the card unordered for this reason) | not fixed — `STEP-17` (determinism) |
| F39 | The narrator was asked two different questions about one situation: the quotes of one message (one instant) came back in the database's physical order, and the card's facts in dict insertion order | `[TEST]` found when a recorded case would not replay | ✅ fixed — `yc2_w27/M19.C3.L-logic.V1.U02` (`e730720d`), `V1.U03` (`64110e92`) |
| F40 | A statement nobody could resolve was anchored on a person chosen by random node id — and on the founder's own sent mail it could pick the founder, the account holder shown as the counterparty of his own words | `[CODE]` `context/correlation_dependency.event_parties`; `[TEST]` golden case F25 | ✅ fixed — `yc2_w27/M19.C3.L-logic.V1.U04` (`9e5cede8`) |
| F41 | One case runs two ways: the engine orders by minted ids in places, and its capture and L2 thread pools interleave — on F29 one situation was built from 2 or from 4 evidence spans, and which of two same-day meetings won one counterparty's reading (marked `rebooked: true` though it was held) changed between runs | `[TEST]` 4 runs of F29, prompts diffed | the golden runner pins ids and workers (`engine_runner.pinned_world`); the engine is unchanged — `STEP-17`; the two-meeting collapse is replay 03 m07 |
| F42 | The relevance page asks the model about every calendar event, with *"(no readable text)"* as the item — a paid call per event about nothing | `[CODE]` `capture/esqe/relevance._item_block`, `capture/pipeline.prime_relevance_page` (a calendar event has a `summary`, not a `subject`) | not fixed — a small unit |
| F43 | The domain proposer is wired nowhere: `capture/pipeline.py` calls `tag_domains` without a proposer, so `capture/domain/proposer.py` spends nothing | `[CODE]` | recorded in `tests/replays/model_sites.py`; a product question, not a defect |
| F44 | **The qualification floor is where the founder set dies.** Of the 18 failing must-detect cases, 9 are lost before memory — every one at the floor (importance 840–2,280 against 2,500): introduced contacts' replies, investors' questions, a partner's dated proposal, a programme's deadline. 5 more die at the gate (N-02 unsubscribe header, N-03 no-reply, N-06 Promotions) | `[TEST]` golden set, `qualification_drops` per case | `STEP-03`, `STEP-04`, `STEP-05` |
| F45 | L2's fixpoint does not converge on 3 of 40 cases — the founder's own sent updates, his outreach wave, a portal's no-reply notices — logged `l2_convergence_exceeded` on every sweep | `[TEST]` golden cases F14, F15, F23 | not fixed — `STEP-17` |
| F46 | A signal's evidence quotes the sender's NAME: `deadline_stated` and `opportunity_signal` reach the narrator as *"Mohit Sethi"*, not as the date or the ask | `[TEST]` every narrator prompt of the golden set | not fixed — `STEP-13` (check every claim) |
| F47 | Accelerators and partners are framed as INVESTOR relationships (sales `investor_relationship`, with investor plays) and an incubator's report as a support ticket (`first_response_overdue`) — no play offered fits what was asked | `[TEST]` golden cases F17, F19, F24, F29 | `STEP-09`, `STEP-11` |
| F48 | The meeting follow-through narrator is told the meeting *happened* and asked for a recap — for meetings nobody confirmed took place | `[CODE]` the `meeting_follow_through` guidance in the card templates; `[TEST]` golden cases F07, F29, F40 | `STEP-14`; contradicts Atlas replay 05 |
| F49 | One ask makes several cards: the company's account-admin card, the person's unanswered-email card, and the meeting's | `[TEST]` golden cases F27 (2), F29 (3), F07 (2) | `STEP-09` (one file per workstream) |
| F50 | `run_all` threw the compiled pass's whole result away, so nothing the compiled lane counted reached the sweep's outcomes | `[CODE]` `reason/runner.run_all`, found building STEP-02 | ✅ fixed — `yc2_w27_s02/M20.C6.L-interface.V4.U01` (`a08dd148`) |
| F51 | A live DEFER was suppressed as `shadow`, stayed out of `fired` and `indeterminate`, and the lifecycle pass expired the card — and `why_not` told the founder "the pack is in shadow mode" | `[TEST]` `tests/reason/test_a_defer_keeps_the_card.py` (red on the old code: `resolved: 1`) | ✅ fixed — `M20.C5.L-logic.V0.U01` (`07933472`), `M20.C5.L-interface.V1.U02` (`829f405b`) |
| F52 | A re-run before a compiled signal's authority expires renews nothing — the lane answers "standing" — so a card is replaced at expiry, never renewed | `[CODE]` `reason/domain_shadow._emit_capability_signal`; `[TEST]` the STEP-02 acceptance on F27 | open — `STEP-14` (one living card). The gate decides on the first sweep after the lapse (`RENEW_MARGIN` = 0) |
| F53 | A legacy signal kept open by `no_new_evidence` outlives its authority and is decided every sweep after the lapse | `[CODE]` `reason/runner.py` (no path renews legacy authority on unchanged evidence) | open — `STEP-14`; no worse than before the gate |
| F54 | `sender_known`'s sent-folder half counts only mail sent by an `org_seats` address: the golden tenant has no seat, so W-01 never fires on the golden set — and in production it holds only if the seat's address is the connected mailbox | `[CODE]` `api/routes.KNOWN_FROM_SENT_SQL`; `[TEST]` golden F09 (the founder replied to Boardy; Boardy's answer was dropped `N-02`) | `STEP-04` (who is us) — the golden runner's seat moved there from `STEP-03`: measuring the archive cleanly meant not moving W-01 in the same block |
| F55 | An `llm_junk` drop is not a drop: `drain_parked` re-admits every judged drop with a payload as `emitted` on each heartbeat, without the gate. The mails deleted for good are the N-code drops, which keep no payload | `[CODE]` `capture/parked/drain.py:120-205` | `STEP-03` — the 258 were N-code drops, now archived. **Preserved on purpose:** an archived `llm_junk` is re-admitted exactly as a dropped one was (`c1ffbb6d`); whether the filter's verdict should stand is `STEP-07`'s |
| F56 | The pipeline turned every gate verb it did not know into `emitted` (`{"drop": …, "park": …}.get(action, "emitted")`): the gate's new `archive` published a Boardy nudge as founder mail until the table learned the word | `[TEST]` found building STEP-03 — `tests/capture/connectors/test_push_ingest.py` saw an empty mail `emitted` | ✅ fixed — the verb table is closed; an unknown verb raises and the sweep quarantines it (`e7eace02`) |
| F57 | Correlation membership ignores outcome: a reading (`support_situations`, *first response overdue*) makes every event of a thread a member — a dropped mail too — and every reader of a message's words (`lifecycle/store`, `situation_bso`, `card_builder`, `document_register`, `backfill`, `org_rule_ingest`) selects text by membership. A dropped mail was kept out only by having no prepared text | `[TEST]` the STEP-03 acceptance on F37: with prepared text stored, the resolution model was handed Introly's archived introduction (prompt diff, before `4d1ad2fe` / after) | contained in `STEP-03` — an archive keeps its payload and **no** prepared text (`ff4ba758`), asserted by two tests. Durable fix open — a reader that asks the outcome, `STEP-05`/`06` |
| F58 | An archive made on the connector's fast path holds the list snippet and headers, not the body: N-09/N-06/N-07/N-03 settled from list fields and confident `llm_junk` are never full-fetched | `[CODE]` `capture/connectors/composio.py` (the light pass); `capture/pipeline.py` stores what was fetched | open — promotion (`STEP-05`) and the re-fetch (`STEP-08`) re-fetch by message id |
| F59 | "Who is us" was decided in TWENTY places, not eighteen: meeting prep marked an attendee internal by seat addresses only (any seat, active or not), and screen recall took the seats' addresses from `api/moment_routes._seat_emails` — both missed a declared address | `[CODE]` `reason/meetings/prep.read`; `reason/moments/recall.read` (found writing the U19 guard) | `STEP-04` U24, U25 |
| F60 | A Gmail founder makes every gmail.com sender a "same-domain colleague" in L1's source analysis (`ActorBasis.SAME_DOMAIN`), the support-lane defect U10 fixed, one layer down. **An audit label only**: SAME_DOMAIN and EXTERNAL weigh the same 5000 and nothing reads the basis | `[CODE]` `capture/esqe/source_analyzer.py:428-433` | open — fix when a reader of the basis appears; no behaviour today |
| F61 | The meeting kind calls every meeting a Gmail user organised `INTERNAL` for a Gmail founder (`organiser_domain == owner_domain`). **Written and read by nothing** today (`meeting_kind` has no reader outside the manifest) — but P4, "a meeting with no follow-up", will read it | `[CODE]` `capture/connectors/attendees.read_meeting_kind`; `capture/connectors/calendar.py:168-171` | open — `STEP-10`, before anything reads it: a public owner domain is no domain → `UNKNOWN` |
| F62 | Our domains are now the DECLARED ones only (`platform/self_identity`). Before, the support lane, the deal backfill and engagement inferred them from `orgs.email` or the seats — which made gmail.com ours for a Gmail founder. A multi-seat tenant that never declared its company domain now sees its own company as a counterparty in those three readings | `[CODE]` U09, U10, U11; `tests/test_p4_verify_pg.py` now declares its team's domain | by design — every live tenant declares its domain (`08-FOR-HARSH`); `STEP-07`'s brief should PROPOSE it for one-click confirmation |
| F63 | The identity normalises an address the way person keys are (`+tag` stripped); the SQL that asks "sent by one of us" compares raw `source_events.actor` emails (`= any(:ours)`), so mail sent from a `+tag` address of ours is not counted | `[CODE]` U06 `deliver/timezone_infer`, U07 `api/routes.KNOWN_FROM_SENT_SQL`, U08 `scripts/pipeline_health` | open — low: the design partner has no `+tag` address |
| F64 | An outbound thread is now named after its recipient's ADDRESS ("priya@… — <objective>") — the recipient arrives bare; the repair names it after the person's display name. Better than naming it after us; not yet the name | `[CODE]` `context/pipeline.py` (U17) | open — `STEP-09` names the files |
| F65 | `context/backfill.name_thread_nodes` reads with `store.engine.connect().execute(...)` and never closes the connection | `[CODE]` `context/backfill.py` | open — `STEP-18` |
| F66 | "Us" in three outreach readings is still partial: `cohort.contacted`/`replied` and `organization.contacted` can count one of us, and `read_unanswered_replies` relies on the pipeline's ADDRESS set — a colleague known only by a declared domain can be "owed a reply" | `[CODE]` `context/outreach_situations.py` (U12's report) | open — `STEP-09`, who owns what on a team |
| F67 | `tests/platform/test_warm_lane_pg.py::test_a_burst_coalesces_into_one_chain_run` fails intermittently (≈4 of 11 runs, also alone): it marks rows done by comparing two database `now()` values taken in different transactions | `[TEST]` U01–U18 builder's runs | open — `STEP-17` |
| F68 | The golden set could not show the defect STEP-04 fixed: its founder has ONE address and it is `orgs.email`, and the runner stored the company in `orgs.name` and the founder's name nowhere. Rows 41–44 are production-shaped; F41, F43 and F44 wait on `STEP-05` (sent mail and a Gmail investor's ask never reach memory) | `[TEST]` `tests/replays/engine_runner.py`; §F.1 | partly — the runner now stores the founder as signup does; the rest is `STEP-05` |
| F69 | D20 says a mail below the floor enters memory *"at the confidence it scored"* — and no such confidence exists. ALG-13 composes a signal's confidence at **publish**, after the floor (`conflicts → qualify → lifecycle → publish`), so a floor refusal has an `importance_bp` and no confidence; and a mail whose extraction proposed no signal at all has neither. A below-floor mail enters at one fixed relevance, `BELOW_FLOOR_CONFIDENCE_BP` = 3,000 — under the ranking floor (0.35), stored and queryable, never a gate — and an `l1.below_floor` observation says where it came from. Its `importance_bp` is not a confidence and is not used | `[CODE]` `capture/esqe/review_candidates.py:15-23`, `capture/esqe/finalize.py`; `context/qes_adapter.BELOW_FLOOR_CONFIDENCE_BP` | by design — `STEP-10` may rank below-floor items by what they scored once confidence is composed before the floor |
| F70 | A calendar event's correlation leaves out only our exact ADDRESSES (`internal_emails`): a colleague known only by a declared domain is an outside attendee, so they can anchor a meeting's situation. STEP-04's anchor-pool check (U20) runs in `context/pipeline.process_event` — the mail road — and never reached `context/structured.commit_structured` | `[CODE]` `context/structured.py` (`key in internal`) | ✅ fixed — `STEP-05` C3.U04 (`e1ff99af`): the structured lane asks `platform/self_identity`; red first on the golden-shaped test |
| F71 | `tests/test_recode_parked_documents.py` fails all four of its tests about one run in 64: its module-level Fernet key is random, and when it begins with `-` argparse refuses it as the value of `--crypto-key` (*"expected one argument"*) | `[TEST]` STEP-05's C4.U02 guard run (4 failed; green on the rerun) and the refusal shown in isolation | open — `STEP-17`: pass `--crypto-key=<key>`, or draw the key until it does not start with `-` |
| F72 | A signal type becomes an observation whose evidence is the extraction's FIRST span — often a bare name — and every reader of quotes shows it as something said; on outbound mail it is mirrored onto each recipient. The card narrator was handed *"[received:approval_requested] the account holder wrote: 'Kavitha'"* three times (golden F25). STEP-05's own below-floor mark had the same shape and was removed (C3.U06) | `[CODE]` `context/qes_adapter.py` (`signal_types` → observations, `default_quote`); `deliver/card_builder._QUOTES_SQL` | open — `STEP-13` (check every claim) or `STEP-14` (the card): a mark is not a quote |
| F73 | The two meeting nodes production held before STEP-05 filed their facts at the meeting's START; STEP-05 files them at the calendar's own edit time (C3.U04). Until such a meeting passes, an edit made before its start lands as history against them | `[CODE]` `graph_store.fact_write_action` (an older `occurred_at` is filed as history); `[PROD]` 2 of 34 meetings in memory (STEP-05 §1) | by design — self-clearing; `08-FOR-HARSH` says how to re-date them if a reschedule must land sooner |


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
| E9 | Should `dependency_stated` declare coverage expectations? None is registered for it, so `context/situations.py:428-429` returns *coverage unknown* (−1) — while the gate row says *"all 6 axes present"* | Rohit |
| E10 | Whose mailbox is the second golden set (`STEP-01` §8)? | Rohit |
| E11 | Should a message already captured from the **same** source suppress extraction? `_seen_on_screen` treats any earlier claim, from any source, as canonical — its docstring says the screen copy. `yc2_w27/M17.C2.L-data.V0.U02` only voids claims by events that no longer exist | Rohit |

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
| golden replays — **corrected 2026-10-06** | the line above measured a harness that never called the engine (F23). Replays 01–07 are now judged on it: 7 of 80 mutations driven through a founder case, 73 not expressible yet — see §F.1 | `pytest tests/replays -q` on a scratch database → 350 passed, 100 xfailed, 0 skipped |
| branch divergence | 13 / 28 → merged | `git rev-list --left-right --count origin/harsh/mvp...speedrun008`; `STEP-00` |
| `pipeline_health` on production | **7 / 7 pass** | `baseline/2026-10-05/pipeline_health.txt` |
| inbound mail by fate | 365 = 15 reached reasoning · 18 read, no signal · 67 junked · 258 deleted · 7 kept unread | `baseline/2026-10-05/workstream_funnel.txt` (`scripts/workstream_funnel.py`) |
| **Re-measured in the `STEP-00` re-do, 13:51 UTC** — statements in `baseline/production_state.sql`, output in `baseline/2026-10-05/production_state.txt` | | |
| funnel sweeps since 3 Oct 08:50 UTC | 64; `decision_emitted` written in 3 (values 1–4); `card_delivered` 0 in the last 7 that wrote it | `@sweeps_recorded`, `@funnel_per_stage`, `@funnel_last_8_sweeps` |
| L2 processing runs | 30, all `done`, 0 edge-type errors (3–5 Oct) | `@l2_processing_runs` |
| park queue | 88 attachments (50 dead-lettered, 38 pending) · 95 screen items pending, 162 recovered · 2 mails pending at extraction · 4 mails recovered | `@park_queue` |
| per-sweep decider calls per UTC day | 718 · 477 · 1,204 · 306 (2–5 Oct; 5 Oct to 13:51) | `@model_calls_by_day` |
| resolution calls vs audited model runs | equal hour by hour since the 3 Oct reset; the 24 unaudited calls (3 Oct 06:00–08:59 UTC) predate it | `llm_costs` vs `l2_model_runs`, read-only, 2026-10-05 |
| the database suite on the merged branch | see `STEP-00` §4.2 | `baseline/2026-10-05/suite_with_database.txt` |

### F.1 · The golden board — the before-score (`STEP-01`)

Measured 2026-10-06 at `7caed608`, on a scratch database, by `python scripts/golden_score.py`:
forty synthetic founder cases (one per row of `golden-labels.md`) and the Atlas replays 01–07,
replayed through the real chain — the production sync door, the floor, `_run_l2_chain` — with the
ideal reader's recorded answers (cassettes recorded at `b47239c9`, `06-DECISIONS` D12c: no model
spend). `scripts/golden_score.py --assert-recorded` holds the two lines below to every later run.

```
founder golden set   must-detect  11/32 (8 not expressible)   must-abstain  11/12 (0 not exercised)   forbidden outputs  4
atlas replays 01–07  passing  4/80   blocked  3/80   not expressible  73
```

The two lines above are the board as it stands — every step that moves it re-records them here, and
the history is the paragraphs below. Before STEP-05 they read *must-detect 5/32 (8 not expressible),
must-abstain 5/12 (4 not exercised), forbidden outputs 4; atlas 0/80 passing, 7/80 blocked*.

**Re-recorded 2026-10-06 by `STEP-04`** (`yc2_w27_s04 · M22.C5.L-integration.V3.U05`), with the runner
seating the tenant as signup does and declaring the case's own addresses, and every STEP-04 change in
the engine. The forty cases above did not move — the before-score stands: must-detect **4/30**,
must-abstain **5/10** at `7caed608`. The board grew by STEP-04's four cases (rows 41–44): **F42**
passes (an ask that names the founder is carded about the investor's firm); **F44** is lost before
memory (a Gmail investor's ask publishes no qualified signal — F03, `STEP-05`); **F41** and **F43**
are not exercised (the founder's own sent mail never reaches memory — `STEP-05`, as F36 and F39).

**Re-recorded 2026-10-07 by `STEP-05`** (`yc2_w27_s05 · M23.C5`), every kept item entering memory. The
ten must-detect cases lost **before memory** all reached it — six now pass, four are lost in reasoning
— and every must-abstain case is exercised. Twenty-two cases' chains reached new model questions; the
ideal reader answered them (no spend), by the set's own conventions where one existed, and from the
prompt as written where one did not. One correction to an earlier answer, named: F25's
*"unanswered email — Kavitha Nair"* decider entry (authored at STEP-01, never reached before) said "a
direct question is waiting on us"; Kavitha's mail asks nothing (*"I'll confirm by the 12th once I've
read the documents"*), so the faithful answer is defer — taken with it, F25 stays one offer, one card.

| moved by STEP-05 | from → to |
|---|---|
| F04, F05, F06, F10, F26, F44 | lost before memory → **pass** (the contact's reply, scheduling question or investor ask, below the floor, now in memory with its words) |
| F07, F11, F19, F24 | lost before memory → **lost in reasoning** (`blocked_on` restated in each case: F07 two cards and *"happened"*; F11 no situation reaches the decider; F19 no card names Ekta; F24 no card names the review deck) |
| F36, F39, F41, F43 | not exercised → **pass** (the founder's own sent mail reaches memory, and the decision not to card it is made) |
| F31, F38 | fail → **pass** (the assignment's deadline and the "all set" reach memory) |
| atlas replays | passing 0 → 4, blocked 7 → 3: replay 03 m00 on F26 (the counterparty's proposed time, carded for the founder to answer) and m01 on F39 (the founder's own proposal, not carded), 04 m01 on F38 ("all set" on another channel, no card) and 06 m04 on F14 (a deferred, conditional investor, no card) — each because its input now reaches memory. ⛔ What each mutation's old `blocked_on` named (a typed role model, an abstention vocabulary, a cross-channel matcher, a conditional-deferral state) is still not built: its golden EXPRESSION — the card a founder sees and what memory holds — is what holds, and it is weaker than the mutation's words. The four are marked `possible_today` in their replay specs |

The table below is the board's state now.

| | |
|---|---|
| must-detect that pass · 11 | F04, F05, F06 (an introduced contact's reply owed — STEP-05), F10 (an investor's follow-up — STEP-05), F12, F13, F25 (one offer, one card), F26 (a partner's dated proposal — STEP-05), F28, F42, F44 (a Gmail investor's ask — STEP-05) |
| must-detect lost at the gate · 5 | F01, F02 (a portal's mail on Promotions and no-reply), F03, F09 (the connector's unsubscribe header — archived; promotion is `STEP-05`'s, by Rohit's word), F16 (a bounce from an automated sender) |
| must-detect lost before memory · 0 | — (ten before STEP-05) |
| must-detect lost in reasoning · 7 | F07 (two cards and *"happened"*), F11 (no situation reaches the decider), F17 (an accelerator framed as an investor), F19 (no card names Ekta), F24 (no card names the review deck), F27 and F29 (one ask, several cards) |
| must-detect with no stage to read · 1 | F15 (the founder's outreach wave, typed `anomaly`) |
| not expressible · 8 | F08, F14, F18, F20–F23 (`brief only` — `STEP-15`), F30 (the screen door) |
| must-abstain that pass · 11 | F31 (the assignment), F32, F33, F34 (archived), F35, F36, F37, F38 (an answer elsewhere closes the ask), F39, F41, F43 (the founder's own mail, in memory, not carded) |
| must-abstain not exercised · 0 | — (four before STEP-05) |
| must-abstain that fail · 1 | F40 (a meeting nobody confirmed, recapped) |
| forbidden outputs · 4 | *"happened"* — the follow-through narrator told a meeting took place (F07, F29 ×2, F40; F48) |
| what the numbers judge | the ENGINE, given a faithful reader of every prompt. The model's own mistakes — production junked the real investor mails — are the live evaluation's to measure (`scripts/golden_eval.py --live`, ≈ $0.63 a pass on Haiku 4.5) |
